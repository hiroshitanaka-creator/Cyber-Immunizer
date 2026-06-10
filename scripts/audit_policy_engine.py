"""scripts/audit_policy_engine.py — Policy Engine for the machine audit gate.

Evaluates an Audit Packet (built by ``scripts/build_audit_packet.py``) against
fixed, fail-closed policy rules and computes whether an APPROVE verdict is even
allowed. The LLM auditor does not decide this; it may only emit APPROVE when
this engine exits 0.

Trust model:

* Only ``machine_facts`` are trusted directly (they were collected by script).
* ``judgment_inputs`` are LLM claims. A claim counts ONLY when ``claim`` is
  true, ``claimed_by`` is set, and the referenced ``evidence_report`` passes
  ``scripts/validate_audit_evidence.py`` re-run by THIS engine at evaluation
  time. A bare ``"claim": true`` with no verifiable evidence is a HOLD reason,
  not an approval input — self-reports cannot be laundered through the packet.
* head-SHA freshness is verified against ``--current-head-sha``; omitting the
  flag is itself a HOLD reason (fail closed), because an unverified packet may
  describe an outdated head.

Modes:

* ``--mode full`` (default) — the reception-gate evaluation. Every machine-fact
  rule and every judgment input is blocking. Exit 0 means APPROVE_ALLOWED.
* ``--mode ci-gate`` — the GitHub Actions required-check evaluation. Only rules
  that are deterministic at CI time block (PR open / not merged, head-SHA
  freshness, SSOT consistency, packet structure). Rules that CI cannot decide
  are reported as warnings, not failures: CI status of sibling checks (circular
  — this gate is itself a check), unresolved threads (resolving a thread does
  not re-trigger pull_request events; enforced instead by branch protection's
  "Require conversation resolution"), frozen-path allowance (Project Owner
  context CI cannot know), and judgment inputs (filled after collection).
  A ci-gate pass is verdict ``CI_GATE_PASS`` and NEVER ``APPROVE_ALLOWED`` —
  it must not be citable as permission to approve.

Usage:
    python scripts/audit_policy_engine.py --packet packet.json \
        [--mode full|ci-gate] --current-head-sha <sha> [--base-ref origin/main] \
        [--allow-frozen scripts/] [--root <repo>] [--json]

Exit codes:
    0  full: APPROVE allowed (APPROVE_ALLOWED) / ci-gate: gate passed (CI_GATE_PASS)
    1  full: HOLD / ci-gate: CI_GATE_FAIL (see reasons)
    2  Packet invalid (PACKET_INVALID; audit cannot proceed)

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_audit_evidence import validate_report  # noqa: E402

PACKET_SCHEMA_VERSION = 1

_JUDGMENT_KEYS = ("task_conditions_met", "scope_semantics_ok", "code_findings_resolved")


# ---------------------------------------------------------------------------
# Structural validation (stdlib mirror of schemas/gpt_audit_packet.schema.json)
# ---------------------------------------------------------------------------


def _get(packet: dict, dotted: str):
    node = packet
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


_REQUIRED_PATHS: list[tuple[str, type | tuple[type, ...]]] = [
    ("packet_schema_version", int),
    ("generated_by", str),
    ("source", str),
    ("machine_facts.pr.number", int),
    ("machine_facts.pr.state", str),
    ("machine_facts.pr.merged", bool),
    ("machine_facts.pr.draft", bool),
    ("machine_facts.pr.base_ref", str),
    ("machine_facts.pr.base_sha", str),
    ("machine_facts.pr.head_ref", str),
    ("machine_facts.pr.head_sha", str),
    ("machine_facts.pr.changed_files", list),
    ("machine_facts.ci.classification", str),
    ("machine_facts.ci.head_sha", str),
    ("machine_facts.ci.check_runs", list),
    ("machine_facts.ci.excluded_checks", list),
    ("machine_facts.review_threads.total", int),
    ("machine_facts.review_threads.unresolved", int),
    ("machine_facts.review_threads.unresolved_p1_p2", int),
    ("machine_facts.review_threads.threads", list),
    ("machine_facts.frozen_paths.frozen_prefixes", list),
    ("machine_facts.frozen_paths.touched", list),
    ("machine_facts.ssot.consistent", bool),
    ("judgment_inputs", dict),
]


def validate_packet_structure(packet: dict) -> list[str]:
    errors: list[str] = []
    for path, expected in _REQUIRED_PATHS:
        value = _get(packet, path)
        if value is None:
            errors.append(f"packet: missing required field {path!r}")
            continue
        # bool is a subclass of int — require exact bool where bool is expected
        if expected is int and isinstance(value, bool):
            errors.append(f"packet: field {path!r} must be int, got bool")
        elif not isinstance(value, expected):
            errors.append(f"packet: field {path!r} has wrong type {type(value).__name__}")
    if packet.get("packet_schema_version") != PACKET_SCHEMA_VERSION:
        errors.append(
            f"packet: packet_schema_version must be {PACKET_SCHEMA_VERSION}, "
            f"got {packet.get('packet_schema_version')!r}"
        )
    judgment = packet.get("judgment_inputs")
    if isinstance(judgment, dict):
        for key in _JUDGMENT_KEYS:
            if key not in judgment:
                errors.append(f"packet: judgment_inputs missing key {key!r}")
        for key in judgment:
            if key not in _JUDGMENT_KEYS:
                errors.append(f"packet: judgment_inputs has unknown key {key!r}")
    return errors


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


# Finding categories that block in ci-gate mode (deterministic at CI time).
# Everything else is advisory in ci-gate mode and blocking in full mode.
_CI_GATE_ENFORCED = {"pr_state", "pr_merged", "head_freshness", "ssot"}


def evaluate_machine_facts(
    packet: dict,
    current_head_sha: str | None,
    allow_frozen: list[str],
) -> list[tuple[str, str]]:
    """Apply the fixed machine-fact rules. Returns (category, message) findings."""
    findings: list[tuple[str, str]] = []
    facts = packet["machine_facts"]
    pr = facts["pr"]

    if pr["state"] != "open":
        findings.append(("pr_state", f"pr_state={pr['state']} (must be open)"))
    if pr["merged"]:
        findings.append(("pr_merged", "pr_already_merged"))
    if pr["draft"]:
        findings.append(("pr_draft", "pr_is_draft"))

    if current_head_sha is None:
        findings.append(
            (
                "head_freshness",
                "head_sha_freshness_unverified (--current-head-sha not supplied; fail closed)",
            )
        )
    elif current_head_sha != pr["head_sha"]:
        findings.append(
            (
                "head_freshness",
                f"head_sha_stale (packet={pr['head_sha']}, current={current_head_sha})",
            )
        )

    ci = facts["ci"]
    if ci["classification"] != "SUCCESS":
        findings.append(("ci_status", f"ci_status={ci['classification']} (must be SUCCESS)"))
    if ci["head_sha"] != pr["head_sha"]:
        findings.append(
            ("ci_status", "ci_head_sha_mismatch (CI result is not for the packet head SHA)")
        )

    threads = facts["review_threads"]
    if threads["unresolved"] > 0:
        findings.append(
            ("threads", f"unresolved_threads={threads['unresolved']} (must be 0)")
        )
    if threads["unresolved_p1_p2"] > 0:
        findings.append(
            ("threads", f"unresolved_p1_p2={threads['unresolved_p1_p2']} (must be 0)")
        )

    blocked = [
        p
        for p in facts["frozen_paths"]["touched"]
        if not any(p.startswith(pfx) for pfx in allow_frozen)
    ]
    if blocked:
        findings.append(
            (
                "frozen",
                "frozen_paths_touched="
                + ",".join(blocked)
                + " (requires explicit Project Owner allowance via --allow-frozen)",
            )
        )

    if not facts["ssot"]["consistent"]:
        findings.append(
            ("ssot", "ssot_inconsistent (data/project_state.json vs docs/PROJECT_STATE.md)")
        )

    return findings


def evaluate_judgment_inputs(
    packet: dict,
    root: Path,
    base_ref: str | None,
) -> list[str]:
    """Honor a judgment claim only if its evidence report verifies. Returns HOLD reasons.

    The engine re-runs scripts/validate_audit_evidence.py itself; it never
    trusts a recorded "validation passed" assertion.
    """
    reasons: list[str] = []
    verified_reports: dict[str, dict] = {}
    for key in _JUDGMENT_KEYS:
        entry = packet["judgment_inputs"].get(key) or {}
        claim = entry.get("claim")
        claimed_by = entry.get("claimed_by")
        report = entry.get("evidence_report")
        if claim is not True:
            reasons.append(f"judgment:{key} claim is {claim!r} (must be true with evidence)")
            continue
        if not claimed_by:
            reasons.append(f"judgment:{key} has no claimed_by")
            continue
        if not report:
            reasons.append(
                f"judgment:{key} claim=true but no evidence_report — "
                "bare self-report is not acceptable"
            )
            continue
        report_path = Path(report)
        if not report_path.is_absolute():
            report_path = root / report_path
        if report not in verified_reports:
            verified_reports[report] = validate_report(report_path, root, base_ref)
        result = verified_reports[report]
        if not result["valid"]:
            head = "; ".join(result["errors"][:3])
            reasons.append(
                f"judgment:{key} evidence_report failed validation "
                f"({len(result['errors'])} error(s): {head})"
            )
    return reasons


def evaluate(
    packet: dict,
    root: Path,
    current_head_sha: str | None = None,
    base_ref: str | None = None,
    allow_frozen: list[str] | None = None,
    mode: str = "full",
) -> dict:
    """Evaluate the packet. Returns the machine verdict document.

    mode="full": every finding blocks; exit verdict APPROVE_ALLOWED / HOLD.
    mode="ci-gate": only _CI_GATE_ENFORCED categories block; the rest (and the
    judgment inputs) are warnings; verdict CI_GATE_PASS / CI_GATE_FAIL with
    approve_allowed always false — a CI-gate pass is not approval permission.
    """
    if mode not in ("full", "ci-gate"):
        raise ValueError(f"unknown mode {mode!r}")
    structural = validate_packet_structure(packet)
    if structural:
        return {
            "machine_verdict": "PACKET_INVALID",
            "approve_allowed": False,
            "mode": mode,
            "reasons": structural,
            "warnings": [],
        }

    findings = evaluate_machine_facts(packet, current_head_sha, allow_frozen or [])
    if mode == "full":
        reasons = [msg for _, msg in findings]
        reasons += evaluate_judgment_inputs(packet, root, base_ref)
        return {
            "machine_verdict": "APPROVE_ALLOWED" if not reasons else "HOLD",
            "approve_allowed": not reasons,
            "mode": mode,
            "reasons": reasons,
            "warnings": [],
        }

    reasons = [msg for cat, msg in findings if cat in _CI_GATE_ENFORCED]
    warnings = [msg for cat, msg in findings if cat not in _CI_GATE_ENFORCED]
    warnings += [
        f"(not evaluated at CI time) {msg}"
        for msg in evaluate_judgment_inputs(packet, root, base_ref)
    ]
    return {
        "machine_verdict": "CI_GATE_PASS" if not reasons else "CI_GATE_FAIL",
        "approve_allowed": False,
        "mode": mode,
        "reasons": reasons,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer audit policy engine")
    parser.add_argument("--packet", required=True, help="Path to the audit packet JSON")
    parser.add_argument(
        "--mode",
        choices=["full", "ci-gate"],
        default="full",
        help="full: reception-gate evaluation (default); ci-gate: required-check subset",
    )
    parser.add_argument(
        "--current-head-sha",
        default=None,
        help="Current PR head SHA for the freshness lock (omitting it is a HOLD reason)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Base git ref passed through to evidence-report validation",
    )
    parser.add_argument(
        "--allow-frozen",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Frozen path prefix explicitly allowed by the Project Owner (repeatable)",
    )
    parser.add_argument("--root", default=str(_PROJECT_ROOT), help="Repository root")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "machine_verdict": "PACKET_INVALID",
            "approve_allowed": False,
            "mode": args.mode,
            "reasons": [f"cannot read packet: {exc}"],
            "warnings": [],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2

    result = evaluate(
        packet,
        Path(args.root),
        current_head_sha=args.current_head_sha,
        base_ref=args.base_ref,
        allow_frozen=args.allow_frozen,
        mode=args.mode,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"machine_verdict: {result['machine_verdict']}")
        for r in result["reasons"]:
            print(f"  - {r}")
        for w in result["warnings"]:
            print(f"  ~ warning: {w}")

    if result["machine_verdict"] == "PACKET_INVALID":
        return 2
    return 0 if result["machine_verdict"] in ("APPROVE_ALLOWED", "CI_GATE_PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
