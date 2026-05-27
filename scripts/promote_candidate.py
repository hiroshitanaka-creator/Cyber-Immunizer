"""scripts/promote_candidate.py — Promote a passing candidate to core/detector.py.

Usage:
    python scripts/promote_candidate.py \\
        --candidate .cyber_immunizer/candidate_detector.py \\
        --report .cyber_immunizer/fitness_report.json \\
        [--json]
        [--detector PATH]   # override output detector path (for tests)
        [--genome PATH]     # override genome.json path (for tests)
        [--history PATH]    # override evolution_history.json path (for tests)
        [--readme PATH]     # override README.md path (for tests)

Exit codes:
    0  Promotion successful
    1  Promotion refused (see output)

SAFETY NOTE:
    This script only copies files and updates JSON data.
    It does NOT call model APIs.
    It does NOT execute generated code.
    It validates the candidate with core.policy BEFORE copying it over
    the production detector.
    The promote job uses GITHUB_TOKEN (write) but no model API secrets.
    The candidate_hash in the report is MANDATORY — no hash means no promotion.
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

from core.policy import run_full_policy  # noqa: E402

_DEFAULT_DETECTOR_PATH = _PROJECT_ROOT / "core" / "detector.py"
_DEFAULT_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DEFAULT_HISTORY_PATH = _PROJECT_ROOT / "data" / "evolution_history.json"
_DEFAULT_README_PATH = _PROJECT_ROOT / "README.md"

# Required fields inside the fitness_report sub-object.
# All must be present and have the correct types.
_REQUIRED_FITNESS_FIELDS: dict[str, type | tuple[type, ...]] = {
    "syntax_ok": bool,
    "ast_policy_ok": bool,
    "contract_ok": bool,
    "passed_adoption_gate": bool,
    "score": (int, float),
    "tp_rate": (int, float),
    "fp_rate": (int, float),
    "fn_rate": (int, float),
    "exception_count": int,
    "rejection_reasons": list,
}


def _refuse(reason: str, as_json: bool) -> int:
    result = {"success": False, "error": reason}
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"REFUSED: {reason}")
    return 1


def _load_history_strict(path: Path) -> tuple[list | None, str]:
    """Load evolution_history.json with fail-closed semantics.

    Promote is refused (fail-closed) if the history file is:
      - missing (FileNotFoundError)
      - unreadable (OSError)
      - malformed JSON (json.JSONDecodeError)
      - top-level value is not a list (e.g. dict, null, string, number)

    Returns:
        (history_list, "")  on success
        (None, error_reason)  on any failure — caller must refuse promotion
    """
    if not path.exists():
        return None, (
            f"evolution_history.json not found at {path} — "
            "promote is fail-closed: missing evolution_history cannot be initialized "
            "automatically. Inspect the repository and restore or bootstrap history "
            "before promoting."
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, (
            f"evolution_history.json contains invalid UTF-8 bytes: {exc} — "
            "promote is fail-closed: evolution_history with encoding errors must not "
            "be overwritten or re-initialized automatically. "
            "Inspect and repair history manually."
        )
    except OSError as exc:
        return None, (
            f"evolution_history.json is unreadable: {exc} — "
            "promote is fail-closed: cannot append to unreadable history."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, (
            f"evolution_history.json contains malformed JSON: {exc} — "
            "promote is fail-closed: malformed history must not be overwritten or "
            "re-initialized automatically. Inspect and repair history manually."
        )
    if not isinstance(data, list):
        return None, (
            f"evolution_history.json top-level value is {type(data).__name__!r}, "
            "expected a list — "
            "promote is fail-closed: invalid history structure must not be overwritten. "
            "Inspect and repair history manually."
        )
    return data, ""


def _validate_fitness_schema(fitness: dict) -> list[str]:
    """Return a list of schema violations in the fitness_report object."""
    errors: list[str] = []
    for field, expected_type in _REQUIRED_FITNESS_FIELDS.items():
        if field not in fitness:
            errors.append(f"fitness_report missing required field: {field!r}")
        elif not isinstance(fitness[field], expected_type):
            actual = type(fitness[field]).__name__
            exp = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else " | ".join(t.__name__ for t in expected_type)
            )
            errors.append(
                f"fitness_report.{field} has wrong type: "
                f"expected {exp}, got {actual!r}"
            )
    return errors


def promote_candidate(
    candidate_path: Path,
    report_path: Path,
    *,
    as_json: bool = False,
    detector_path: Path | None = None,
    genome_path: Path | None = None,
    history_path: Path | None = None,
    readme_path: Path | None = None,
) -> int:
    """Run promotion logic. Returns exit code.

    Path overrides (detector_path, genome_path, history_path, readme_path) are
    provided for use in tests so the real repository files are never mutated.
    """
    detector_path = detector_path or _DEFAULT_DETECTOR_PATH
    genome_path = genome_path or _DEFAULT_GENOME_PATH
    history_path = history_path or _DEFAULT_HISTORY_PATH
    readme_path = readme_path or _DEFAULT_README_PATH

    # --- 1. Check report exists ---
    if not report_path.exists():
        return _refuse(f"fitness report not found: {report_path}", as_json)

    # --- 2. Parse report ---
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _refuse(f"could not parse fitness report: {exc}", as_json)

    if not isinstance(report, dict):
        return _refuse("fitness report is not a JSON object", as_json)

    # --- 3. Mandatory candidate_hash (not optional) ---
    report_hash = report.get("candidate_hash")
    if not report_hash:
        # Also check nested fitness_report for hash
        inner = report.get("fitness_report") or {}
        report_hash = inner.get("candidate_hash")
    if not report_hash:
        return _refuse(
            "candidate_hash is missing from the fitness report — "
            "promotion requires a verified hash to prevent blind trust of artifacts",
            as_json,
        )

    # --- 4. Validate fitness_report schema ---
    fitness = report.get("fitness_report") or report
    schema_errors = _validate_fitness_schema(fitness)
    if schema_errors:
        return _refuse(
            "fitness report schema invalid: " + "; ".join(schema_errors),
            as_json,
        )

    # --- 5. Verify adoption gate ---
    if not fitness.get("passed_adoption_gate", False):
        reasons = fitness.get("rejection_reasons", [])
        return _refuse(
            f"adoption gate not passed: {reasons}",
            as_json,
        )

    # --- 6. Verify ast_policy_ok ---
    if not fitness.get("ast_policy_ok", False):
        return _refuse(
            "fitness report shows ast_policy_ok=False — candidate is not safe to promote",
            as_json,
        )

    # --- 7. Verify fp_rate within limit ---
    fp_rate = float(fitness.get("fp_rate", 1.0))
    try:
        genome_data = json.loads(genome_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _refuse(f"could not read genome file: {exc}", as_json)

    max_fp_rate = float(genome_data.get("max_fp_rate", 0.05))
    if fp_rate > max_fp_rate:
        return _refuse(
            f"fp_rate={fp_rate:.3f} exceeds max_fp_rate={max_fp_rate:.3f}",
            as_json,
        )

    # --- 8. Check candidate file exists ---
    if not candidate_path.exists():
        return _refuse(f"candidate not found: {candidate_path}", as_json)

    # --- 9. Verify candidate hash matches report ---
    source = candidate_path.read_text(encoding="utf-8")
    actual_hash = hashlib.sha256(source.encode()).hexdigest()
    if actual_hash != report_hash:
        return _refuse(
            f"candidate hash mismatch: "
            f"report says {report_hash!r}, actual is {actual_hash!r} — "
            "file may have been tampered with after evaluation",
            as_json,
        )

    # --- 10. Re-validate candidate with core.policy BEFORE copying ---
    policy_result = run_full_policy(candidate_path)
    if not policy_result["valid"]:
        return _refuse(
            "candidate failed re-validation before promotion: "
            + "; ".join(policy_result["violations"]),
            as_json,
        )

    # --- 11. Verify score improvement ---
    candidate_score: float = float(fitness.get("score", -1e9))
    previous_best: float = float(genome_data.get("best_score", -1e9))
    if candidate_score <= previous_best:
        return _refuse(
            f"candidate score {candidate_score:.4f} does not exceed "
            f"current best {previous_best:.4f}",
            as_json,
        )

    # --- 11.5. Pre-load evolution_history BEFORE any mutations (fail-closed) ---
    # Load and validate history NOW, before copying the candidate or updating
    # genome.json.  If the history file is missing, malformed, or non-list,
    # refuse immediately — we must never overwrite or re-initialize a broken
    # audit trail.  This check happens BEFORE any irreversible mutations so
    # that a broken history causes a clean refusal rather than a partial write.
    history, history_err = _load_history_strict(history_path)
    if history_err:
        return _refuse(history_err, as_json)

    # --- 12. Copy candidate to detector_path ---
    shutil.copy2(str(candidate_path), str(detector_path))

    # --- 13. Update genome.json ---
    new_generation = int(genome_data.get("generation", 0)) + 1
    genome_data["generation"] = new_generation
    genome_data["current_detector_hash"] = actual_hash
    genome_data["best_score"] = candidate_score
    genome_data["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    genome_path.write_text(json.dumps(genome_data, indent=2) + "\n", encoding="utf-8")

    # --- 14. Append to evolution_history.json ---
    # history was validated and loaded at step 11.5 (before any mutations).
    # We append a new entry and write it back.  If the file changed between
    # step 11.5 and here that would be a concurrent-modification issue; the
    # existing record is kept as-is from the pre-validation load.
    assert history is not None  # guaranteed by step 11.5 check above

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
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    # --- 15. Update README ---
    readme_update_result = _update_readme(readme_path)

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
        print(f"PROMOTED generation={new_generation} score={candidate_score:.4f}")

    return 0


def _update_readme(readme_path: Path | None = None) -> bool:
    """Call scripts/update_readme.py; return True on success."""
    import subprocess
    try:
        cmd = [sys.executable, str(_PROJECT_ROOT / "scripts" / "update_readme.py")]
        if readme_path is not None:
            cmd.extend(["--readme", str(readme_path)])
        proc = subprocess.run(
            cmd,
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
    # Path overrides — primarily for integration tests that must not touch real files
    parser.add_argument("--detector", default=None, help="Override output detector path")
    parser.add_argument("--genome", default=None, help="Override genome.json path")
    parser.add_argument("--history", default=None, help="Override evolution_history.json path")
    parser.add_argument("--readme", default=None, help="Override README.md path")
    args = parser.parse_args(argv)

    return promote_candidate(
        Path(args.candidate),
        Path(args.report),
        as_json=args.json,
        detector_path=Path(args.detector) if args.detector else None,
        genome_path=Path(args.genome) if args.genome else None,
        history_path=Path(args.history) if args.history else None,
        readme_path=Path(args.readme) if args.readme else None,
    )


if __name__ == "__main__":
    sys.exit(main())
