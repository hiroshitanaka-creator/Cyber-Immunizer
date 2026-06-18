"""Offline pre-paid-credit readiness gate.

Deterministic local checks only: no Gemini, no external API, no workflow dispatch,
and no paid-credit execution.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.offline_validation import hash_consistency_issues, sha256_text  # noqa: E402

EXPECTED_PHASE = 3
EXPECTED_GENERATION = 3
EXPECTED_BEST_SCORE = 947.66
EXPECTED_DETECTOR_HASH = "c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6"
FROZEN_PATHS = (
    ".github/workflows/",
    "core/detector.py",
    "data/api_usage_ledger.json",
    "data/genome.json",
    "data/evolution_history.json",
)


def _reason(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _is_frozen_path(path: str) -> bool:
    return path == "core/detector.py" or path in FROZEN_PATHS or any(
        path.startswith(prefix) for prefix in FROZEN_PATHS if prefix.endswith("/")
    )


def _read_text(path: Path, missing_code: str, unreadable_code: str) -> tuple[str | None, dict[str, str] | None]:
    if not path.exists():
        return None, _reason(missing_code, f"Required file is missing: {path}.")
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, _reason(unreadable_code, f"Required file is unreadable: {path}: {exc}.")


def _load_json(path: Path, *, missing_code: str, unreadable_code: str, unparseable_code: str) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    text, err = _read_text(path, missing_code, unreadable_code)
    if err:
        return None, err
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError as exc:
        return None, _reason(unparseable_code, f"Required JSON file is unparseable: {path}: {exc}.")
    if not isinstance(data, dict):
        return None, _reason(unparseable_code, f"Required JSON file must contain an object: {path}.")
    return data, None


def _git_diff_names(project_root: Path, args: list[str]) -> tuple[list[str], dict[str, str] | None]:
    result = subprocess.run(
        ["git", *args], cwd=project_root, check=False, text=True, capture_output=True
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git diff failed").strip()
        return [], _reason("git_diff_failed", detail)
    return [line for line in result.stdout.splitlines() if line], None


def _check_frozen_drift(project_root: Path, base_ref: str | None) -> tuple[dict[str, str], list[dict[str, str]]]:
    checks: dict[str, str] = {}
    reasons: list[dict[str, str]] = []

    for check_name, code, args in (
        ("frozen_worktree_drift", "frozen_worktree_drift", ["diff", "--name-only"]),
        ("frozen_index_drift", "frozen_index_drift", ["diff", "--cached", "--name-only"]),
    ):
        changed, err = _git_diff_names(project_root, args)
        frozen = [path for path in changed if _is_frozen_path(path)]
        if err:
            checks[check_name] = "fail"
            reasons.append(err)
        elif frozen:
            checks[check_name] = "fail"
            reasons.append(_reason(code, f"Frozen files changed: {frozen}."))
        else:
            checks[check_name] = "pass"

    if base_ref is None:
        checks["frozen_committed_drift"] = "not_applicable"
    else:
        changed, err = _git_diff_names(project_root, ["diff", "--name-only", f"{base_ref}...HEAD"])
        frozen = [path for path in changed if _is_frozen_path(path)]
        if err:
            checks["frozen_committed_drift"] = "fail"
            reasons.append(err)
        elif frozen:
            checks["frozen_committed_drift"] = "fail"
            reasons.append(_reason("frozen_committed_drift", f"Frozen files changed since {base_ref}: {frozen}."))
        else:
            checks["frozen_committed_drift"] = "pass"

    return checks, reasons


def _candidate_artifact_status(project_root: Path, base_source: str | None) -> tuple[str, list[dict[str, str]]]:
    candidate = project_root / ".cyber_immunizer" / "candidate_detector.py"
    report_path = project_root / ".cyber_immunizer" / "apply_report.json"
    if not candidate.exists():
        return "not_applicable", []
    if base_source is None:
        return "fail", [_reason("candidate_materialization_failed", "Base detector source is unavailable for candidate contract checks.")]
    try:
        candidate_source = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        return "fail", [_reason("candidate_materialization_failed", f"Candidate artifact is unreadable: {exc}.")]
    if not report_path.exists():
        return "fail", [_reason("candidate_report_missing", f"Candidate exists but report is missing: {report_path}.")]
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "fail", [_reason("candidate_materialization_failed", f"Candidate report is unreadable or malformed: {exc}.")]
    if not isinstance(report, dict):
        return "fail", [_reason("candidate_materialization_failed", "Candidate report must be a JSON object.")]
    reported_hash = report.get("candidate_hash")
    if not isinstance(reported_hash, str) or not reported_hash:
        return "fail", [_reason("candidate_report_hash_missing", "Candidate report is missing candidate_hash.")]
    hash_issues = hash_consistency_issues(candidate_source, reported_hash, report)
    if hash_issues:
        reasons = []
        for issue in hash_issues:
            code = "candidate_report_hash_mismatch" if issue.code == "candidate_hash_mismatch" else issue.code
            reasons.append(_reason(code, issue.detail))
        return "fail", reasons
    try:
        from scripts.candidate_contract import run_candidate_contract_checks
        result = run_candidate_contract_checks(candidate, reported_hash=reported_hash, base_source=base_source)
    except Exception as exc:  # noqa: BLE001 - readiness must fail closed
        return "fail", [_reason("candidate_materialization_failed", f"Candidate contract check failed: {type(exc).__name__}: {exc}")]
    if result.get("passed"):
        return "pass", []
    return "fail", [_reason(str(r).split(":", 1)[0], str(r)) for r in result.get("rejection_reasons", [])]


def run_readiness(project_root: Path | None = None, *, base_ref: str | None = None) -> dict[str, Any]:
    project_root = (project_root or _PROJECT_ROOT).resolve()
    checks: dict[str, str] = {}
    reasons: list[dict[str, str]] = []
    metadata: dict[str, Any] = {}

    genome, err = _load_json(
        project_root / "data" / "genome.json",
        missing_code="state_file_missing",
        unreadable_code="state_file_unreadable",
        unparseable_code="state_file_unparseable",
    )
    if err:
        reasons.append(err)
    state, err = _load_json(
        project_root / "data" / "project_state.json",
        missing_code="state_file_missing",
        unreadable_code="project_state_unreadable",
        unparseable_code="state_file_unparseable",
    )
    if err:
        reasons.append(err)
    detector_source, err = _read_text(
        project_root / "core" / "detector.py",
        "detector_file_unreadable",
        "detector_file_unreadable",
    )
    if err:
        reasons.append(err)

    phase = generation = best_score = recorded_hash = None
    if isinstance(state, dict):
        try:
            phase = int(str(state.get("current_phase", "")).split("_")[-1])
        except (TypeError, ValueError):
            reasons.append(_reason("phase_parse_failed", "Could not parse current_phase from project_state.json."))
    if isinstance(genome, dict):
        generation = genome.get("generation")
        best_score = genome.get("best_score")
        recorded_hash = genome.get("current_detector_hash")
    metadata.update({"phase": phase, "generation": generation, "best_score": best_score, "detector_hash": recorded_hash})

    state_ok = phase == EXPECTED_PHASE and generation == EXPECTED_GENERATION and best_score == EXPECTED_BEST_SCORE and recorded_hash == EXPECTED_DETECTOR_HASH
    checks["state_consistency"] = "pass" if state_ok else "fail"
    if not state_ok:
        reasons.append(_reason("state_consistency_mismatch", "Phase, generation, best_score, or recorded detector hash does not match expected generation 3 readiness state."))

    detector_hash = sha256_text(detector_source) if detector_source is not None else None
    hash_ok = detector_hash == recorded_hash == EXPECTED_DETECTOR_HASH
    checks["detector_hash"] = "pass" if hash_ok else "fail"
    if not hash_ok:
        reasons.append(_reason("detector_hash_mismatch", "Current detector hash does not match recorded detector_hash."))

    try:
        from scripts import candidate_contract
        available = callable(getattr(candidate_contract, "run_candidate_contract_checks", None))
    except Exception:  # noqa: BLE001
        available = False
    checks["candidate_contract_available"] = "pass" if available else "fail"
    if not available:
        reasons.append(_reason("candidate_contract_checker_missing", "Candidate contract checker from PR #119 is not importable or missing run_candidate_contract_checks."))

    try:
        from scripts.propose_mutation import _SAMPLE_MUTATION, validate_proposal_output
        proposal_result = validate_proposal_output(json.dumps(_SAMPLE_MUTATION))
        proposal_ok = bool(proposal_result.get("valid"))
    except Exception as exc:  # noqa: BLE001
        proposal_ok = False
        proposal_result = {"rejection_reasons": [_reason("proposal_output_unparseable", f"Proposal validation readiness raised {type(exc).__name__}: {exc}")]}
    checks["proposal_validation"] = "pass" if proposal_ok else "fail"
    if not proposal_ok:
        reasons.extend(proposal_result.get("rejection_reasons", []))

    try:
        from scripts.apply_mutation import _apply_replacement
        from scripts.offline_validation import outside_region_issues
        from scripts.propose_mutation import _SAMPLE_MUTATION
        new_source, err_msg, issues = _apply_replacement(detector_source or "", _SAMPLE_MUTATION["replacement_code"])
        region_issues = outside_region_issues(new_source, detector_source) if new_source and detector_source else []
        apply_ok = bool(new_source) and not err_msg and not issues and not region_issues
        issues = [*issues, *region_issues]
    except Exception as exc:  # noqa: BLE001
        apply_ok = False
        issues = [_reason("candidate_materialization_failed", f"Mutation apply validation readiness raised {type(exc).__name__}: {exc}")]
    checks["mutation_apply_validation"] = "pass" if apply_ok else "fail"
    if not apply_ok:
        if issues and isinstance(issues[0], dict):
            reasons.extend(issues)
        else:
            reasons.extend(_reason(getattr(i, "code", "candidate_materialization_failed"), getattr(i, "detail", str(i))) for i in issues)

    cand_status, cand_reasons = _candidate_artifact_status(project_root, detector_source)
    checks["candidate_artifacts"] = cand_status
    reasons.extend(cand_reasons)

    drift_checks, drift_reasons = _check_frozen_drift(project_root, base_ref)
    checks.update(drift_checks)
    reasons.extend(drift_reasons)

    checks["offline_only"] = "pass"
    ready = all(status in ("pass", "not_applicable") for status in checks.values())
    return {"ready": ready, "checks": checks, "rejection_reasons": reasons, "metadata": metadata}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline pre-paid-credit readiness gate")
    parser.add_argument("--project-root", default=None, help="Repository root to check")
    parser.add_argument("--base-ref", default=None, help="Optional base ref/sha for committed frozen-file drift")
    args = parser.parse_args(argv)
    result = run_readiness(Path(args.project_root) if args.project_root else None, base_ref=args.base_ref)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
