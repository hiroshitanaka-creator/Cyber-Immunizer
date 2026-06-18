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
import tempfile
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_mutation import validate  # noqa: E402
from scripts.candidate_contract import run_candidate_contract_checks  # noqa: E402

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

    A fitness_report.json (or the path specified by report_path) is written for
    EVERY exit path — including AST failures and candidate-not-found — so that
    CI artifacts always carry diagnostic information.
    """
    report_path = report_path or _REPORT_PATH

    # --- Pre-step: Attempt to compute candidate hash before any validation ---
    # Computed here so it is available even in early-exit paths (e.g. AST failure).
    # Hash is None when the file cannot be read (handled fail-closed below).
    candidate_hash: str | None = None
    try:
        _raw = candidate_path.read_text(encoding="utf-8")
        candidate_hash = hashlib.sha256(_raw.encode()).hexdigest()
    except OSError:
        pass

    # --- Pre-step: Guard for missing candidate file (fail-closed) ---
    if not candidate_path.exists():
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": [f"candidate file not found: {candidate_path}"],
            "fitness_report": None,
            "error": f"candidate file not found: {candidate_path}",
            "is_tool_failure": True,
            "candidate_hash": None,
        }
        _write_report(result, None, report_path)
        return result

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
            "candidate_hash": candidate_hash,
            "contract_checks": [],
            "rejection_reasons": val_result["violations"],
        }
        _write_report(result, candidate_hash, report_path)
        return result

    # candidate_hash was computed in the pre-step above; no need to re-read.

    # --- Step 2: Offline contract checks (static, fail-closed, no API/network) ---
    _base_source: str | None = None
    try:
        _base_source = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
    except OSError:
        pass
    contract_result = run_candidate_contract_checks(
        candidate_path, reported_hash=candidate_hash, base_source=_base_source
    )
    if not contract_result["passed"]:
        reasons = contract_result["rejection_reasons"]
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": reasons,
            "fitness_report": None,
            "error": f"offline contract check failed: {'; '.join(reasons)}",
            "is_tool_failure": False,  # contract rejection is a soft rejection
            "candidate_hash": candidate_hash,
            "contract_checks": contract_result["contract_checks"],
            "rejection_reasons": reasons,
        }
        _write_report(result, candidate_hash, report_path)
        return result

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
                "contract_checks": contract_result["contract_checks"],
                "rejection_reasons": [],
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
            "contract_checks": contract_result["contract_checks"],
            "rejection_reasons": [],
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
            "contract_checks": contract_result["contract_checks"],
            "rejection_reasons": [],
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
            "contract_checks": contract_result["contract_checks"],
            "rejection_reasons": [],
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
            "contract_checks": contract_result["contract_checks"],
            "rejection_reasons": [],
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
        "contract_checks": contract_result["contract_checks"],
        "rejection_reasons": list(fitness_report.get("rejection_reasons", [])),
    }
    _write_report(result, candidate_hash, report_path)
    return result


def _write_report(result: dict, candidate_hash: str | None, report_path: Path) -> None:
    """Write structured fitness report JSON atomically.

    Outputs a normalised schema that always includes 'stage' and 'candidate_hash'.
    The 'fitness_report' key carries the raw fitness subprocess output (or null on
    failure) under the canonical name that promote_candidate.py reads.  The 'metrics'
    key is an alias kept for backward-compat with CI tooling.
    No secret env vars or raw payloads are included: the fitness subprocess runs with
    _safe_env() which strips all secrets, and only its JSON stdout is stored here.
    Uses a temp-write + fsync + os.replace to avoid partial writes; raises OSError on
    failure (fail-closed — the caller must not suppress this).
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fitness = result.get("fitness_report")
    payload = {
        "stage": "evaluate_candidate",
        "success": result.get("success", False),
        "passed_adoption_gate": result.get("passed_adoption_gate", False),
        "is_tool_failure": result.get("is_tool_failure", True),
        "timed_out": result.get("timed_out", False),
        "candidate_hash": candidate_hash,
        "violations": result.get("violations", []),
        "error": result.get("error", ""),
        "fitness_report": fitness,
        "metrics": fitness,
        "return_code": result.get("return_code"),
        "contract_checks": result.get("contract_checks", []),
        "rejection_reasons": result.get("rejection_reasons", []),
    }
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=report_path.parent,
            prefix=f".{report_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(payload, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, report_path)
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


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
        "--report",
        default=None,
        metavar="PATH",
        help=(
            "Write structured JSON fitness report to PATH. "
            "Defaults to .cyber_immunizer/fitness_report.json when omitted."
        ),
    )
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
        report_path=Path(args.report) if args.report else None,
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
