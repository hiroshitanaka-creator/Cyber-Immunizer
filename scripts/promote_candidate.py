"""scripts/promote_candidate.py — Promote a passing candidate to core/detector.py.

Usage:
    python scripts/promote_candidate.py \\
        --candidate .cyber_immunizer/candidate_detector.py \\
        --report .cyber_immunizer/fitness_report.json \\
        [--json]

Exit codes:
    0  Promotion successful
    1  Promotion refused (see output)

SAFETY NOTE:
    This script only copies files and updates JSON data.
    It does NOT call model APIs.
    It does NOT execute generated code.
    It does NOT make more than one git commit (if git integration is added).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DETECTOR_PATH = _PROJECT_ROOT / "core" / "detector.py"
_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_HISTORY_PATH = _PROJECT_ROOT / "data" / "evolution_history.json"


def _refuse(reason: str, as_json: bool) -> int:
    result = {"success": False, "error": reason}
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"REFUSED: {reason}")
    return 1


def promote_candidate(
    candidate_path: Path,
    report_path: Path,
    *,
    as_json: bool = False,
) -> int:
    """Run promotion logic. Returns exit code."""

    # --- 1. Check report exists ---
    if not report_path.exists():
        return _refuse(f"fitness report not found: {report_path}", as_json)

    # --- 2. Parse report ---
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _refuse(f"could not parse fitness report: {exc}", as_json)

    # --- 3. Verify adoption gate ---
    fitness = report.get("fitness_report") or report
    if not fitness.get("passed_adoption_gate", False):
        reasons = fitness.get("rejection_reasons", [])
        return _refuse(
            f"adoption gate not passed: {reasons}",
            as_json,
        )

    # --- 4. Check candidate exists ---
    if not candidate_path.exists():
        return _refuse(f"candidate not found: {candidate_path}", as_json)

    # --- 5. Verify score improvement ---
    try:
        genome = json.loads(_GENOME_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return _refuse(f"could not read genome.json: {exc}", as_json)

    candidate_score: float = float(fitness.get("score", -1e9))
    previous_best: float = float(genome.get("best_score", -1e9))

    if candidate_score <= previous_best:
        return _refuse(
            f"candidate score {candidate_score:.2f} does not exceed "
            f"current best {previous_best:.2f}",
            as_json,
        )

    # --- 6. Optionally verify hash ---
    source = candidate_path.read_text(encoding="utf-8")
    actual_hash = hashlib.sha256(source.encode()).hexdigest()
    report_hash = report.get("candidate_hash") or fitness.get("candidate_hash")
    if report_hash and actual_hash != report_hash:
        return _refuse(
            f"candidate hash mismatch: expected {report_hash!r}, got {actual_hash!r}",
            as_json,
        )

    # --- 7. Copy candidate to core/detector.py ---
    shutil.copy2(str(candidate_path), str(_DETECTOR_PATH))

    # --- 8. Update genome.json ---
    new_generation = int(genome.get("generation", 0)) + 1
    genome["generation"] = new_generation
    genome["current_detector_hash"] = actual_hash
    genome["best_score"] = candidate_score
    genome["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    _GENOME_PATH.write_text(json.dumps(genome, indent=2) + "\n", encoding="utf-8")

    # --- 9. Append to evolution_history.json ---
    try:
        history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        history = []

    history_entry = {
        "generation": new_generation,
        "detector_hash": actual_hash,
        "score": candidate_score,
        "passed_adoption_gate": True,
        "rejection_reasons": [],
        "promoted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "tp_rate": fitness.get("tp_rate"),
        "fp_rate": fitness.get("fp_rate"),
        "fn_rate": fitness.get("fn_rate"),
        "avg_latency_ms": fitness.get("avg_latency_ms"),
        "total_cases": fitness.get("total_cases"),
    }
    history.append(history_entry)
    _HISTORY_PATH.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    # --- 10. Update README ---
    readme_update_result = _update_readme()

    result = {
        "success": True,
        "generation": new_generation,
        "score": candidate_score,
        "detector_hash": actual_hash,
        "readme_updated": readme_update_result,
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"PROMOTED generation={new_generation} score={candidate_score:.2f}")

    return 0


def _update_readme() -> bool:
    """Call scripts/update_readme.py; return True on success."""
    import subprocess
    try:
        proc = subprocess.run(
            [sys.executable, str(_PROJECT_ROOT / "scripts" / "update_readme.py")],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer promotion")
    parser.add_argument("--candidate", required=True, help="Candidate detector path")
    parser.add_argument("--report", required=True, help="Fitness report JSON path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    return promote_candidate(
        Path(args.candidate),
        Path(args.report),
        as_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
