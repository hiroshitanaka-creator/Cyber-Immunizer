"""scripts/triage_s4_rerun.py — Deterministic local triage tool for S4 rerun artifacts.

Usage:
    python scripts/triage_s4_rerun.py --artifacts-dir <DIR> [--json] [--markdown <PATH>]

This tool reads artifacts downloaded after a paid-credit S4 rerun and classifies
the pipeline stage reached, adoption gate result, and recommended next action.

It never executes API calls, modifies ledger files, triggers workflow_dispatch,
or reads secrets.

Safety constraints:
  - No network access of any kind.
  - data/api_usage_ledger.json and all frozen files are never written.
  - Secret-pattern strings are detected and suppressed from output.
  - Malformed JSON is classified as tool_failure (fail-closed).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema version for the output format
# ---------------------------------------------------------------------------
_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Secret-detection heuristics (conservative; never emit the value)
# ---------------------------------------------------------------------------
_SECRET_PATTERNS = [
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{35}"),        # Google API key
    re.compile(r"(?i)GEMINI_API_KEY\s*[=:]\s*\S+"),    # explicit assignment
    re.compile(r"(?i)Authorization\s*:\s*\S+"),          # auth header
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"), # bearer token
    re.compile(r"(?i)password\s*[=:]\s*\S{8,}"),        # password assignment
    re.compile(r"(?i)secret\s*[=:]\s*\S{8,}"),          # secret assignment
]

# Artifact filenames (relative to artifacts_dir)
_ARTIFACT_MUTATION_PATCH = "mutation_patch.json"
_ARTIFACT_LEDGER = "api_usage_ledger.json"
_ARTIFACT_CANDIDATE = "candidate_detector.py"
_ARTIFACT_FITNESS = "fitness_report.json"
_ARTIFACT_PROMOTE = "promote_result.json"

# Fields read from fitness_report.json
_FITNESS_FIELDS = [
    "passed_adoption_gate",
    "rejection_reasons",
    "score",
    "tp_rate",
    "fp_rate",
    "fn_rate",
    "candidate_hash",
]

# Classification values
_CLASS_PROPOSE_FAILED = "propose_failed"
_CLASS_APPLY_FAILED = "apply_failed_or_not_reached"
_CLASS_EVALUATE_REJECTED = "evaluate_rejected"
_CLASS_PROMOTE_ELIGIBLE = "promote_eligible"
_CLASS_PROMOTED = "promoted"
_CLASS_TOOL_FAILURE = "tool_failure"


def _contains_secret(text: str) -> bool:
    """Return True if text matches any known secret pattern."""
    return any(p.search(text) for p in _SECRET_PATTERNS)


def _load_json_safe(path: Path) -> tuple[dict | list | None, str | None]:
    """Load JSON from path.  Return (data, None) on success or (None, error_str) on failure.

    Never raises.  Returns (None, reason) for missing, empty, or malformed files.
    """
    if not path.exists():
        return None, f"file not found: {path.name}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read {path.name}: {exc}"

    if not text.strip():
        return None, f"{path.name} is empty"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON in {path.name}: {exc}"

    return data, None


def _scan_artifact_for_secrets(path: Path, warnings: list[str]) -> None:
    """Warn if a file appears to contain secret-like strings.  Never log the value."""
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    if _contains_secret(text):
        warnings.append(
            f"secret-pattern string detected in {path.name} — value suppressed"
        )


def _triage(artifacts_dir: Path) -> dict:
    """Run the deterministic triage logic and return the result dict."""
    evidence: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Artifact presence detection
    # ------------------------------------------------------------------
    mp_path = artifacts_dir / _ARTIFACT_MUTATION_PATCH
    ledger_path = artifacts_dir / _ARTIFACT_LEDGER
    cand_path = artifacts_dir / _ARTIFACT_CANDIDATE
    fitness_path = artifacts_dir / _ARTIFACT_FITNESS
    promote_path = artifacts_dir / _ARTIFACT_PROMOTE

    artifacts_seen = {
        "mutation_patch": mp_path.exists(),
        "api_usage_ledger": ledger_path.exists(),
        "candidate_detector": cand_path.exists(),
        "fitness_report": fitness_path.exists(),
        "promote_result": promote_path.exists(),
    }

    # Scan artifacts for secrets before processing
    for p in [mp_path, ledger_path, cand_path, fitness_path, promote_path]:
        _scan_artifact_for_secrets(p, warnings)

    # ------------------------------------------------------------------
    # Stage 1 — propose: was a mutation patch produced?
    # ------------------------------------------------------------------
    mutation_patch_produced = False
    if artifacts_seen["mutation_patch"]:
        mp_data, mp_err = _load_json_safe(mp_path)
        if mp_data is not None:
            mutation_patch_produced = True
            evidence.append("mutation_patch.json present and valid JSON")
        else:
            warnings.append(f"mutation_patch.json parse error: {mp_err}")
            evidence.append("mutation_patch.json present but malformed")
    else:
        evidence.append("mutation_patch.json absent — propose stage did not produce a patch")

    # Check api_usage_ledger for API success evidence
    if artifacts_seen["api_usage_ledger"]:
        ledger_data, ledger_err = _load_json_safe(ledger_path)
        if ledger_data is not None:
            if isinstance(ledger_data, list) and ledger_data:
                last = ledger_data[-1]
                if isinstance(last, dict):
                    success = last.get("success")
                    model = last.get("model", "unknown")
                    api_mode = last.get("api_mode", "unknown")
                    evidence.append(
                        f"api_usage_ledger last record: model={model} "
                        f"api_mode={api_mode} success={success}"
                    )
            else:
                evidence.append("api_usage_ledger.json present but contains no records")
        else:
            warnings.append(f"api_usage_ledger.json parse error: {ledger_err}")
    else:
        evidence.append("api_usage_ledger.json absent from artifacts dir")

    # ------------------------------------------------------------------
    # Stage 2 — apply: was the candidate file written?
    # ------------------------------------------------------------------
    apply_reached = artifacts_seen["candidate_detector"]
    if apply_reached:
        evidence.append("candidate_detector.py present — apply stage was reached")
    else:
        evidence.append("candidate_detector.py absent — apply stage was not reached (or failed)")

    # ------------------------------------------------------------------
    # Stage 3 — evaluate: was fitness_report.json written?
    # ------------------------------------------------------------------
    evaluate_reached = artifacts_seen["fitness_report"]

    # Fitness report parsing and gate evaluation
    adoption_gate_passed: bool | None = None
    fitness_tool_failure = False
    fitness_rejection_reasons: list[str] = []
    fitness_score: float | None = None

    if evaluate_reached:
        evidence.append("fitness_report.json present — evaluate stage was reached")
        fitness_data, fitness_err = _load_json_safe(fitness_path)
        if fitness_data is None:
            warnings.append(
                f"fitness_report.json parse failed (fail-closed): {fitness_err}"
            )
            fitness_tool_failure = True
            evidence.append("fitness_report.json malformed — classified as tool_failure")
        elif not isinstance(fitness_data, dict):
            warnings.append(
                "fitness_report.json root is not a JSON object (fail-closed)"
            )
            fitness_tool_failure = True
            evidence.append("fitness_report.json has unexpected root type — classified as tool_failure")
        else:
            # Read required fields
            gate_val = fitness_data.get("passed_adoption_gate")
            if gate_val is True:
                adoption_gate_passed = True
                evidence.append("passed_adoption_gate=true in fitness_report.json")
            elif gate_val is False:
                adoption_gate_passed = False
                evidence.append("passed_adoption_gate=false in fitness_report.json")
            else:
                # Missing or unexpected type — fail closed
                warnings.append(
                    f"passed_adoption_gate has unexpected value {gate_val!r} — fail-closed"
                )
                fitness_tool_failure = True
                adoption_gate_passed = None
                evidence.append(
                    f"passed_adoption_gate={gate_val!r} — unexpected, treating as tool_failure"
                )

            # Collect rejection reasons (safe strings only)
            raw_reasons = fitness_data.get("rejection_reasons")
            if isinstance(raw_reasons, list):
                for r in raw_reasons:
                    if isinstance(r, str) and not _contains_secret(r):
                        fitness_rejection_reasons.append(r)
                if fitness_rejection_reasons:
                    evidence.append(
                        "rejection_reasons: " + "; ".join(fitness_rejection_reasons[:5])
                    )

            # Score
            score_val = fitness_data.get("score")
            if isinstance(score_val, (int, float)):
                fitness_score = float(score_val)
                evidence.append(f"fitness score={fitness_score}")

            # Rate fields for evidence (values only, no secrets)
            for rate_field in ("tp_rate", "fp_rate", "fn_rate"):
                val = fitness_data.get(rate_field)
                if isinstance(val, (int, float)):
                    evidence.append(f"{rate_field}={val}")

            # candidate_hash (safe hex string)
            chash = fitness_data.get("candidate_hash")
            if isinstance(chash, str) and re.match(r"^[0-9a-f]{64}$", chash):
                evidence.append(f"candidate_hash={chash[:16]}...")
    else:
        evidence.append("fitness_report.json absent — evaluate stage was not reached")

    # ------------------------------------------------------------------
    # Stage 4 — promote: was promote_result.json written?
    # ------------------------------------------------------------------
    promote_reached = artifacts_seen["promote_result"]
    if promote_reached:
        evidence.append("promote_result.json present — promote stage was reached")
    else:
        evidence.append("promote_result.json absent — promote stage was not reached")

    # ------------------------------------------------------------------
    # Classification logic (deterministic)
    # ------------------------------------------------------------------
    classification: str
    recommended_next_action: str
    requires_owner_approval: bool

    if fitness_tool_failure:
        # Malformed fitness report is a hard tool_failure regardless of other state
        classification = _CLASS_TOOL_FAILURE
        recommended_next_action = (
            "fitness_report.json could not be parsed. "
            "Inspect the raw artifact for corruption. "
            "Re-download the artifact and re-run triage, or diagnose the evaluate job logs."
        )
        requires_owner_approval = False

    elif promote_reached:
        # promote_result.json exists → promote stage was reached
        classification = _CLASS_PROMOTED
        recommended_next_action = (
            "Promote stage was reached. "
            "Verify data/genome.json and data/api_usage_ledger.json were updated. "
            "Run pytest tests/test_project_state_sync.py to confirm state sync."
        )
        requires_owner_approval = True

    elif evaluate_reached and adoption_gate_passed is True:
        # Adoption gate passed but no promote artifact → promote eligible, awaiting approval
        classification = _CLASS_PROMOTE_ELIGIBLE
        recommended_next_action = (
            "Candidate passed adoption gate. "
            "Project Owner must review fitness_report.json and explicitly approve promotion "
            "before triggering a new workflow_dispatch with promote_approved=true."
        )
        requires_owner_approval = True

    elif evaluate_reached and adoption_gate_passed is False:
        # Adoption gate rejected the candidate
        classification = _CLASS_EVALUATE_REJECTED
        reason_str = (
            "; ".join(fitness_rejection_reasons) if fitness_rejection_reasons
            else "see rejection_reasons in fitness_report.json"
        )
        recommended_next_action = (
            f"Candidate failed adoption gate: {reason_str}. "
            "Inspect rejection_reasons and fitness metrics. "
            "Open a new propose-side pre-screen PR to address the rejection pattern, "
            "then request a new Owner-approved rerun."
        )
        requires_owner_approval = False

    elif apply_reached and not evaluate_reached:
        # candidate_detector.py exists but no fitness report — apply reached but evaluate failed
        classification = _CLASS_APPLY_FAILED
        recommended_next_action = (
            "apply stage produced candidate_detector.py but evaluate was not reached. "
            "Inspect the evaluate job logs for the failing policy check or AST violation. "
            "Open a propose-side pre-screen PR to address the gap, "
            "then request a new Owner-approved rerun."
        )
        requires_owner_approval = False

    elif mutation_patch_produced and not apply_reached:
        # Patch was produced but candidate not written — apply failed or not reached
        classification = _CLASS_APPLY_FAILED
        recommended_next_action = (
            "mutation_patch.json was produced but apply did not write candidate_detector.py. "
            "Inspect the apply step logs for policy check failures (e.g. G1 repeat-multiplier). "
            "Open a propose-side pre-screen PR to address the constraint, "
            "then request a new Owner-approved rerun."
        )
        requires_owner_approval = False

    else:
        # No valid mutation patch → propose failed
        classification = _CLASS_PROPOSE_FAILED
        recommended_next_action = (
            "mutation_patch.json was not produced or was malformed. "
            "Inspect propose job logs and api_usage_ledger.json. "
            "If the API call succeeded but the patch was rejected by output-contract checks, "
            "review the propose-side output-contract hardening (PR #84 / #91). "
            "Request a new Owner-approved rerun."
        )
        requires_owner_approval = False

    # ------------------------------------------------------------------
    # Assemble stage_status
    # ------------------------------------------------------------------
    stage_status = {
        "mutation_patch_produced": mutation_patch_produced,
        "apply_reached": apply_reached,
        "evaluate_reached": evaluate_reached,
        "adoption_gate_passed": adoption_gate_passed,
        "promote_reached": promote_reached,
    }

    return {
        "schema_version": _SCHEMA_VERSION,
        "artifacts_dir": str(artifacts_dir),
        "artifacts_seen": artifacts_seen,
        "stage_status": stage_status,
        "decision": {
            "classification": classification,
            "recommended_next_action": recommended_next_action,
            "requires_owner_approval": requires_owner_approval,
        },
        "evidence": evidence,
        "warnings": warnings,
    }


def _render_markdown(result: dict) -> str:
    """Render a Markdown summary of the triage result."""
    d = result["decision"]
    ss = result["stage_status"]
    lines = [
        "# S4 Rerun Triage Summary",
        "",
        f"**Classification:** `{d['classification']}`",
        f"**Requires Owner Approval:** {d['requires_owner_approval']}",
        "",
        "## Recommended Next Action",
        "",
        d["recommended_next_action"],
        "",
        "## Stage Status",
        "",
        "| Stage | Reached |",
        "|---|---|",
        f"| propose (mutation_patch_produced) | {ss['mutation_patch_produced']} |",
        f"| apply | {ss['apply_reached']} |",
        f"| evaluate | {ss['evaluate_reached']} |",
        f"| adoption_gate_passed | {ss['adoption_gate_passed']} |",
        f"| promote | {ss['promote_reached']} |",
        "",
        "## Artifacts Seen",
        "",
    ]
    for name, seen in result["artifacts_seen"].items():
        mark = "✓" if seen else "✗"
        lines.append(f"- {mark} {name}")
    lines.append("")

    if result["evidence"]:
        lines.append("## Evidence")
        lines.append("")
        for e in result["evidence"]:
            lines.append(f"- {e}")
        lines.append("")

    if result["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for w in result["warnings"]:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic local triage for S4 rerun artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--artifacts-dir",
        required=True,
        metavar="DIR",
        help="Directory containing downloaded S4 rerun artifacts.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Print triage result as JSON to stdout (default: human-readable summary).",
    )
    parser.add_argument(
        "--markdown",
        metavar="PATH",
        default=None,
        help="Write a Markdown summary to this file path.",
    )
    args = parser.parse_args(argv)

    artifacts_dir = Path(args.artifacts_dir).resolve()
    if not artifacts_dir.exists():
        print(
            json.dumps({
                "schema_version": _SCHEMA_VERSION,
                "error": f"artifacts_dir does not exist: {artifacts_dir}",
                "classification": _CLASS_TOOL_FAILURE,
            }),
            file=sys.stderr,
        )
        return 2

    result = _triage(artifacts_dir)

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable summary
        d = result["decision"]
        print(f"Classification : {d['classification']}")
        print(f"Requires Owner : {d['requires_owner_approval']}")
        print(f"Next action    : {d['recommended_next_action']}")
        if result["warnings"]:
            print("\nWarnings:")
            for w in result["warnings"]:
                print(f"  ! {w}")

    if args.markdown:
        md_path = Path(args.markdown)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_markdown(result), encoding="utf-8")
        print(f"\nMarkdown summary written to {md_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
