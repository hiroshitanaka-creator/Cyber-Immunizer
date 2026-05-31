"""scripts/evaluate_candidate.py — Evaluate a candidate detector in a subprocess.

Usage:
    python scripts/evaluate_candidate.py \\
        --candidate .cyber_immunizer/candidate_detector.py \\
        --timeout 5 \\
        [--json] \\
        [--soft-reject]

Exit codes (default mode):
    0  Candidate passed adoption gate
    1  Tool failure, AST violation, timeout, or adoption gate failed

Exit codes with --soft-reject:
    0  Adoption gate evaluation completed (regardless of gate outcome)
    1  Tool failure only (AST violation, timeout, subprocess crash, parse error)

The --soft-reject flag lets the CI workflow distinguish "tool broken" (exit 1)
from "candidate evaluated but rejected by gate" (exit 0 + passed_adoption_gate=false).
This prevents a legitimate soft-rejection from being treated as a workflow error.

SAFETY NOTE:
    Candidate code is never executed with secrets or write permissions.
    The evaluation subprocess has no access to GEMINI_API_KEY or git tokens.
    On POSIX/Linux, the subprocess is also bounded by physical resource limits
    (CPU time, address space, file size, open files, process count) to prevent
    a malicious or buggy candidate from exhausting runner resources before the
    wall-clock timeout triggers.
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

# ---------------------------------------------------------------------------
# Physical resource limits for the evaluation subprocess
# ---------------------------------------------------------------------------

# Conditional import: `resource` is POSIX-only.  _resource_module is None on
# non-POSIX platforms (Windows).  This module-level variable can be monkeypatched
# in tests to verify that the correct rlimits are applied.
try:
    import resource as _resource_module
except ImportError:
    _resource_module = None  # type: ignore[assignment]

_EVAL_MAX_ADDRESS_SPACE_BYTES = 768 * 1024 * 1024   # 768 MiB — enough for Python fitness
_EVAL_MAX_FILE_SIZE_BYTES = 16 * 1024 * 1024         # 16 MiB
_EVAL_MAX_OPEN_FILES = 64
_EVAL_MAX_PROCESSES = 32


def _resource_limits_supported() -> bool:
    """Return True if POSIX physical resource limits can be applied."""
    return os.name == "posix" and _resource_module is not None


def _make_resource_limiter(timeout_seconds: int):
    """Return a callable suitable for subprocess.run preexec_fn.

    When called in the child process (before exec), it applies rlimits that
    bound CPU time, address space, file sizes, open-file count, and process
    count so that a malicious or buggy candidate cannot exhaust runner resources.

    Raises RuntimeError if the resource module is unavailable.
    """
    if _resource_module is None:
        raise RuntimeError(
            "resource module is unavailable; cannot apply physical resource limits"
        )

    def _apply_limits() -> None:
        cpu_seconds = max(1, int(timeout_seconds))
        _resource_module.setrlimit(
            _resource_module.RLIMIT_CPU, (cpu_seconds, cpu_seconds)
        )
        _resource_module.setrlimit(
            _resource_module.RLIMIT_AS,
            (_EVAL_MAX_ADDRESS_SPACE_BYTES, _EVAL_MAX_ADDRESS_SPACE_BYTES),
        )
        _resource_module.setrlimit(
            _resource_module.RLIMIT_FSIZE,
            (_EVAL_MAX_FILE_SIZE_BYTES, _EVAL_MAX_FILE_SIZE_BYTES),
        )
        _resource_module.setrlimit(
            _resource_module.RLIMIT_NOFILE,
            (_EVAL_MAX_OPEN_FILES, _EVAL_MAX_OPEN_FILES),
        )
        if hasattr(_resource_module, "RLIMIT_NPROC"):
            _resource_module.setrlimit(
                _resource_module.RLIMIT_NPROC,
                (_EVAL_MAX_PROCESSES, _EVAL_MAX_PROCESSES),
            )

    return _apply_limits


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
    soft_reject: bool = False,
) -> dict:
    """Validate then evaluate candidate in a sandboxed subprocess.

    Returns a result dict with keys:
        success: bool               — True only if adoption gate passed
        passed_adoption_gate: bool  — True if gate passed
        timed_out: bool
        return_code: int | None
        violations: list[str]
        fitness_report: dict | None
        error: str
        is_tool_failure: bool       — True if something broke (not a soft rejection)
        candidate_hash: str | None

    When soft_reject=True, the caller can use is_tool_failure to determine
    whether to exit 1 (tool broken) or exit 0 (gate evaluated, candidate rejected).
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
            "is_tool_failure": True,  # AST violation is always a hard failure
        }
        return result

    # --- Step 2: Compute candidate hash ---
    source = candidate_path.read_text(encoding="utf-8")
    candidate_hash = hashlib.sha256(source.encode()).hexdigest()

    # --- Step 3: Build physical resource limiter (fail closed if unsupported) ---
    # On Linux/POSIX, resource limits are mandatory.  We never run untrusted
    # candidate code without rlimits; if they cannot be set, we fail closed.
    if _resource_limits_supported():
        try:
            preexec_fn = _make_resource_limiter(timeout_seconds)
        except RuntimeError as exc:
            result = {
                "success": False,
                "passed_adoption_gate": False,
                "timed_out": False,
                "return_code": None,
                "violations": [],
                "fitness_report": None,
                "error": f"resource limit setup failed: {exc}",
                "is_tool_failure": True,
                "candidate_hash": candidate_hash,
            }
            _write_report(result, candidate_hash, report_path)
            return result
    else:
        # Non-POSIX or resource module unavailable: fail closed rather than run
        # the candidate without physical resource limits.
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": [],
            "fitness_report": None,
            "error": (
                "candidate evaluation requires POSIX resource limits; "
                "platform is not POSIX or resource module is unavailable"
            ),
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    # --- Step 4: Run fitness evaluation in subprocess ---
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
            preexec_fn=preexec_fn,
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
            "is_tool_failure": True,  # timeout is a tool failure
            "candidate_hash": candidate_hash,
        }
        _write_report(result, candidate_hash, report_path)
        return result
    except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": [],
            "fitness_report": None,
            "error": f"subprocess launch failed: {exc}",
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    # --- Step 5: Parse fitness report ---
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
            "is_tool_failure": True,  # parse failure is a tool failure
            "candidate_hash": candidate_hash,
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
        "is_tool_failure": False,  # gate evaluated cleanly — not a tool failure
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
    parser.add_argument(
        "--soft-reject",
        action="store_true",
        help=(
            "Exit 0 when the adoption gate evaluated cleanly (even if candidate was rejected). "
            "Exit 1 only on tool failures (AST violation, timeout, subprocess crash). "
            "Useful in CI to distinguish 'workflow broken' from 'candidate didn't pass gate'."
        ),
    )
    args = parser.parse_args(argv)

    result = evaluate_candidate(
        Path(args.candidate),
        timeout_seconds=args.timeout,
        baseline_mode=args.baseline,
        soft_reject=args.soft_reject,
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
                score = fr.get("score", 0)
                tp = fr.get("tp_rate", 0)
                fp = fr.get("fp_rate", 0)
                print(f"  score={score:.2f}  tp={tp:.3f}  fp={fp:.3f}")

    # Determine exit code
    if args.soft_reject:
        # Exit 1 only for tool failures; exit 0 for clean gate evaluations
        return 1 if result.get("is_tool_failure", True) else 0
    else:
        return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
