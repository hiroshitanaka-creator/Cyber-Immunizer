"""Offline pre-paid-credit readiness gate.

Deterministic local checks only: no Gemini, no external API, no workflow dispatch,
and no paid-credit execution.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.offline_validation import sha256_text  # noqa: E402

EXPECTED_PHASE = 3
EXPECTED_GENERATION = 3
EXPECTED_BEST_SCORE = 947.66
EXPECTED_DETECTOR_HASH = "c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6"
FROZEN_PREFIXES = (".github/workflows/", "core/detector.py", "data/api_usage_ledger.json", "data/genome.json", "data/evolution_history.json")


def _reason(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_artifact_status() -> tuple[str, list[dict[str, str]]]:
    candidate = _PROJECT_ROOT / ".cyber_immunizer" / "candidate_detector.py"
    if not candidate.exists():
        return "not_applicable", []
    try:
        from scripts.candidate_contract import run_candidate_contract_checks
        base = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        result = run_candidate_contract_checks(candidate, base_source=base)
    except Exception as exc:  # noqa: BLE001 - readiness must fail closed
        return "fail", [_reason("candidate_materialization_failed", f"Candidate artifact check failed: {type(exc).__name__}: {exc}")]
    if result.get("passed"):
        return "pass", []
    return "fail", [_reason(str(r).split(":", 1)[0], str(r)) for r in result.get("rejection_reasons", [])]


def run_readiness() -> dict[str, Any]:
    checks: dict[str, str] = {}
    reasons: list[dict[str, str]] = []
    metadata: dict[str, Any] = {}

    genome = _load_json(_PROJECT_ROOT / "data" / "genome.json")
    state = _load_json(_PROJECT_ROOT / "data" / "project_state.json")
    detector_source = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
    detector_hash = sha256_text(detector_source)

    phase = int(str(state.get("current_phase", "phase_0")).split("_")[-1])
    generation = genome.get("generation")
    best_score = genome.get("best_score")
    recorded_hash = genome.get("current_detector_hash")
    metadata.update({"phase": phase, "generation": generation, "best_score": best_score, "detector_hash": recorded_hash})

    state_ok = phase == EXPECTED_PHASE and generation == EXPECTED_GENERATION and best_score == EXPECTED_BEST_SCORE and recorded_hash == EXPECTED_DETECTOR_HASH
    checks["state_consistency"] = "pass" if state_ok else "fail"
    if not state_ok:
        reasons.append(_reason("state_consistency_mismatch", "Phase, generation, best_score, or recorded detector hash does not match expected generation 3 readiness state."))

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
        from scripts.propose_mutation import _SAMPLE_MUTATION
        new_source, err, issues = _apply_replacement(detector_source, _SAMPLE_MUTATION["replacement_code"])
        apply_ok = bool(new_source) and not err and not issues
    except Exception as exc:  # noqa: BLE001
        apply_ok = False
        issues = [_reason("candidate_materialization_failed", f"Mutation apply validation readiness raised {type(exc).__name__}: {exc}")]
    checks["mutation_apply_validation"] = "pass" if apply_ok else "fail"
    if not apply_ok:
        if issues and isinstance(issues[0], dict):
            reasons.extend(issues)
        else:
            reasons.extend(_reason(getattr(i, "code", "candidate_materialization_failed"), getattr(i, "detail", str(i))) for i in issues)

    cand_status, cand_reasons = _candidate_artifact_status()
    checks["candidate_artifacts"] = cand_status
    reasons.extend(cand_reasons)

    diff = subprocess.run(["git", "diff", "--name-only"], cwd=_PROJECT_ROOT, check=False, text=True, capture_output=True)
    changed = diff.stdout.splitlines() if diff.returncode == 0 else []
    frozen_changed = [p for p in changed if p == "core/detector.py" or any(p.startswith(pref) for pref in FROZEN_PREFIXES)]
    checks["frozen_file_drift"] = "pass" if not frozen_changed else "fail"
    if frozen_changed:
        reasons.append(_reason("frozen_file_drift", f"Frozen files have uncommitted drift: {frozen_changed}."))

    checks["offline_only"] = "pass"
    ready = all(status in ("pass", "not_applicable") for status in checks.values())
    return {"ready": ready, "checks": checks, "rejection_reasons": reasons, "metadata": metadata}


def main() -> int:
    result = run_readiness()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
