"""scripts/evaluate_candidate.py — Evaluate a candidate detector in a subprocess.

Usage:
    python scripts/evaluate_candidate.py \\
        --candidate .cyber_immunizer/candidate_detector.py \\
        --timeout 5 \\
        [--json]

Exit codes:
    0  Candidate passed adoption gate
    1  Validation failed, timeout, or adoption gate failed

SAFETY NOTE:
    Candidate code is never executed with secrets or write permissions.
    The evaluation subprocess has no access to GEMINI_API_KEY or git tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_mutation import validate  # noqa: E402

_REPORT_PATH = _PROJECT_ROOT / ".cyber_immunizer" / "fitness_report.json"


def _safe_env() -> dict[str, str]:
    """Return a stripped environment for the evaluation subprocess.

    No secrets, no API keys, no write tokens.
    """
    allowed_keys = {
        "PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE",
        "TMPDIR", "TMP", "TEMP",
    }
    return {k: v for k, v in os.environ.items() if k in allowed_keys}


def evaluate_candidate(
    candidate_path: Path,
    *,
    timeout_seconds: int = 5,
    report_path: Path | None = None,
    baseline_mode: bool = False,
) -> dict:
    """Validate then evaluate candidate in a sandboxed subprocess.

    Returns a result dict.
    """
    report_path = report_path or _REPORT_PATH

    # --- Step 1: AST validation (fast, in-process) ---
    val_result = validate(candidate_path)
    if not val_result["valid"]:
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": val_result["violations"],
            "fitness_report": None,
            "error": "AST validation failed",
        }
        return result

    # --- Step 2: Compute candidate hash ---
    source = candidate_path.read_text(encoding="utf-8")
    candidate_hash = hashlib.sha256(source.encode()).hexdigest()

    # --- Step 3: Run fitness evaluation in subprocess ---
    cmd = [
        sys.executable,
        "-m", "core.fitness",
        "--candidate", str(candidate_path),
        "--json",
    ]
    if baseline_mode:
        cmd.append("--baseline")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_safe_env(),
        )
        timed_out = False
        return_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": True,
            "return_code": None,
            "violations": [],
            "fitness_report": None,
            "error": f"evaluation subprocess timed out after {timeout_seconds}s",
        }
        # Write a failure report
        _write_report(result, candidate_hash, report_path)
        return result

    # --- Step 4: Parse fitness report ---
    fitness_report: dict | None = None
    parse_error = ""
    try:
        fitness_report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        parse_error = f"could not parse fitness output: {exc}\nstdout={stdout!r}"

    if fitness_report is None:
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": return_code,
            "violations": [],
            "fitness_report": None,
            "error": parse_error or f"empty fitness output (stderr={stderr!r})",
        }
        _write_report(result, candidate_hash, report_path)
        return result

    passed = bool(fitness_report.get("passed_adoption_gate", False))
    fitness_report["candidate_hash"] = candidate_hash

    result = {
        "success": passed,
        "passed_adoption_gate": passed,
        "timed_out": False,
        "return_code": return_code,
        "violations": [],
        "fitness_report": fitness_report,
        "error": "" if passed else "adoption gate not passed",
        "candidate_hash": candidate_hash,
    }
    _write_report(result, candidate_hash, report_path)
    return result


def _write_report(result: dict, candidate_hash: str, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**result, "candidate_hash": candidate_hash}
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer candidate evaluator")
    parser.add_argument("--candidate", required=True, help="Path to candidate detector")
    parser.add_argument("--timeout", type=int, default=5, help="Subprocess timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--baseline", action="store_true", help="Baseline evaluation mode")
    args = parser.parse_args(argv)

    result = evaluate_candidate(
        Path(args.candidate),
        timeout_seconds=args.timeout,
        baseline_mode=args.baseline,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print("SUCCESS: candidate passed adoption gate")
        else:
            print(f"FAILURE: {result['error']}")
            if result.get("violations"):
                for v in result["violations"]:
                    print(f"  violation: {v}")
            if result.get("fitness_report"):
                fr = result["fitness_report"]
                print(f"  score={fr.get('score'):.2f}  tp={fr.get('tp_rate'):.3f}  fp={fr.get('fp_rate'):.3f}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
