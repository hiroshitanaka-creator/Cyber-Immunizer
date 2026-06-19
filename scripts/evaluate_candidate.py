"""scripts/evaluate_candidate.py — Evaluate a candidate detector in a Docker sandbox.

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
    Production candidate fitness runs inside a Docker sandbox by default. The
    sandbox disables networking, uses a read-only root filesystem and read-only
    mounts, drops Linux capabilities, sets no-new-privileges, runs as non-root,
    constrains CPU/memory/PIDs, uses an isolated /tmp tmpfs, and receives only
    explicit non-secret environment variables. The legacy POSIX rlimit
    subprocess backend remains available only through an explicit local-dev/test
    opt-in and is never selected silently.
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
from typing import Literal

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_mutation import validate  # noqa: E402
from scripts.candidate_contract import (  # noqa: E402
    run_candidate_contract_checks,
    run_behavioral_surface_check_subprocess,
    run_behavioral_benign_control_check_subprocess,
    build_candidate_runtime_docker_command,
    docker_available,
    docker_launcher_env,
    DOCKER_IMAGE,
    DOCKER_NON_ROOT_USER,
    DOCKER_MEMORY_LIMIT,
    DOCKER_CPU_LIMIT,
    DOCKER_PIDS_LIMIT,
    DOCKER_TMPFS,
    CONTAINER_WORKSPACE,
    CONTAINER_CANDIDATE,
    run_candidate_runtime_in_docker,
)

_REPORT_PATH = _PROJECT_ROOT / ".cyber_immunizer" / "fitness_report.json"
_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_SCORE_FORMULA = (
    "1000*tp_rate - 2000*fp_rate - 1500*fn_rate - "
    "50*exception_count - 0.02*code_chars"
)

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


class SandboxBackend:
    DOCKER = "docker"
    LEGACY_RLIMIT = "legacy-rlimit"


SandboxBackendName = Literal["docker", "legacy-rlimit"]

_DOCKER_IMAGE = DOCKER_IMAGE
_DOCKER_NON_ROOT_USER = DOCKER_NON_ROOT_USER
_DOCKER_MEMORY_LIMIT = DOCKER_MEMORY_LIMIT
_DOCKER_CPU_LIMIT = DOCKER_CPU_LIMIT
_DOCKER_PIDS_LIMIT = DOCKER_PIDS_LIMIT
_DOCKER_TMPFS = DOCKER_TMPFS
_CONTAINER_WORKSPACE = CONTAINER_WORKSPACE
_CONTAINER_CANDIDATE = CONTAINER_CANDIDATE


def _sandbox_metadata(backend: str) -> dict:
    if backend == SandboxBackend.DOCKER:
        return {
            "sandbox_backend": SandboxBackend.DOCKER,
            "sandbox_image": _DOCKER_IMAGE,
            "sandbox_network": "none",
            "sandbox_read_only": True,
            "sandbox_user": _DOCKER_NON_ROOT_USER,
            "sandbox_cap_drop": "ALL",
            "sandbox_no_new_privileges": True,
            "sandbox_pids_limit": int(_DOCKER_PIDS_LIMIT),
            "sandbox_memory_limit": _DOCKER_MEMORY_LIMIT,
            "sandbox_cpus": _DOCKER_CPU_LIMIT,
            "sandbox_tmpfs": _DOCKER_TMPFS,
        }
    return {"sandbox_backend": SandboxBackend.LEGACY_RLIMIT}


def _docker_launcher_env() -> dict[str, str]:
    """Return minimal env for launching docker without propagating secrets."""
    return docker_launcher_env()


def _docker_available() -> bool:
    """Return True only when docker version succeeds."""
    return docker_available()

def _build_docker_command(candidate_path: Path, timeout_seconds: int, baseline_mode: bool) -> list[str]:
    command = [
        "python", "-m", "core.fitness",
        "--candidate", _CONTAINER_CANDIDATE,
        "--json",
    ]
    if baseline_mode:
        command.append("--baseline")
    return build_candidate_runtime_docker_command(
        candidate_path=candidate_path,
        command=command,
        project_root=_PROJECT_ROOT,
    )

def _run_fitness_in_docker(candidate_path: Path, timeout_seconds: int, baseline_mode: bool):
    command = [
        "python", "-m", "core.fitness",
        "--candidate", _CONTAINER_CANDIDATE,
        "--json",
    ]
    if baseline_mode:
        command.append("--baseline")
    return run_candidate_runtime_in_docker(
        candidate_path=candidate_path,
        command=command,
        timeout_seconds=timeout_seconds,
        project_root=_PROJECT_ROOT,
    )

def _run_fitness_legacy_rlimit(candidate_path: Path, timeout_seconds: int, baseline_mode: bool):
    if _resource_limits_supported():
        preexec_fn = _make_resource_limiter(timeout_seconds)
    else:
        raise RuntimeError(
            "candidate evaluation requires POSIX resource limits for legacy backend; "
            "platform is not POSIX or resource module is unavailable"
        )
    cmd = [sys.executable, "-m", "core.fitness", "--candidate", str(candidate_path), "--json"]
    if baseline_mode:
        cmd.append("--baseline")
    return subprocess.run(
        cmd,
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=_safe_env(),
        preexec_fn=preexec_fn,
    )


def evaluate_candidate(
    candidate_path: Path,
    *,
    timeout_seconds: int = 5,
    report_path: Path | None = None,
    baseline_mode: bool = False,
    soft_reject: bool = False,
    sandbox_backend: SandboxBackendName = SandboxBackend.DOCKER,
) -> dict:
    """Validate then evaluate candidate in a Docker sandbox by default.

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
            "contract_checks": [],
            "rejection_reasons": [f"candidate file not found: {candidate_path}"],
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

    sandbox_meta = _sandbox_metadata(sandbox_backend)

    # --- Step 2b: Behavioral request-surface check (Docker sandbox, no secrets) ---
    behavioral_raw = run_behavioral_surface_check_subprocess(
        candidate_path, timeout_seconds=min(float(timeout_seconds), 30.0)
    )
    behavioral_check_entry = {
        "name": "request_surface_coverage_behavioral",
        "passed": behavioral_raw["passed"],
        "details": {
            "field_results": behavioral_raw.get("field_results", {}),
            "missing_surface_fields": behavioral_raw.get("missing", []),
        },
        "rejection_reasons": behavioral_raw.get("rejection_reasons", []),
    }
    # All subsequent result dicts include both static and behavioral checks
    all_contract_checks = contract_result["contract_checks"] + [behavioral_check_entry]

    if behavioral_raw.get("harness_error"):
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": behavioral_raw.get("rejection_reasons", []),
            "fitness_report": None,
            "error": behavioral_raw.get("error", "behavioral surface check harness error"),
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": behavioral_raw.get("rejection_reasons", []),
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    if not behavioral_raw["passed"]:
        reasons = behavioral_raw["rejection_reasons"]
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": reasons,
            "fitness_report": None,
            "error": f"behavioral surface check failed: {'; '.join(reasons)}",
            "is_tool_failure": False,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": reasons,
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    # --- Step 2c: Behavioral benign-control check (Docker sandbox, no secrets) ---
    benign_raw = run_behavioral_benign_control_check_subprocess(
        candidate_path, timeout_seconds=min(float(timeout_seconds), 30.0)
    )
    benign_check_entry = {
        "name": "behavioral_benign_controls",
        "passed": benign_raw["passed"],
        "details": {
            "case_results": benign_raw.get("case_results", {}),
            "failing_cases": benign_raw.get("failing_cases", []),
        },
        "rejection_reasons": benign_raw.get("rejection_reasons", []),
    }
    all_contract_checks = all_contract_checks + [benign_check_entry]

    if benign_raw.get("harness_error"):
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": benign_raw.get("rejection_reasons", []),
            "fitness_report": None,
            "error": benign_raw.get("error", "behavioral benign-control check harness error"),
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": benign_raw.get("rejection_reasons", []),
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    if not benign_raw["passed"]:
        reasons = benign_raw["rejection_reasons"]
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": reasons,
            "fitness_report": None,
            "error": f"behavioral benign-control check failed: {'; '.join(reasons)}",
            "is_tool_failure": False,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": reasons,
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    # --- Step 3: Run fitness evaluation in the requested sandbox backend ---
    if sandbox_backend not in {SandboxBackend.DOCKER, SandboxBackend.LEGACY_RLIMIT}:
        result = {
            "success": False,
            "passed_adoption_gate": False,
            "timed_out": False,
            "return_code": None,
            "violations": [],
            "fitness_report": None,
            "error": f"unsupported sandbox backend: {sandbox_backend}",
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": [],
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    try:
        if sandbox_backend == SandboxBackend.DOCKER:
            proc = _run_fitness_in_docker(candidate_path, timeout_seconds, baseline_mode)
        else:
            proc = _run_fitness_legacy_rlimit(candidate_path, timeout_seconds, baseline_mode)
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
            "error": f"evaluation sandbox timed out after {timeout_seconds}s",
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": [],
            **sandbox_meta,
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
            "error": f"sandbox execution failed: {exc}",
            "is_tool_failure": True,
            "candidate_hash": candidate_hash,
            "contract_checks": all_contract_checks,
            "rejection_reasons": [],
            **sandbox_meta,
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
            "contract_checks": all_contract_checks,
            "rejection_reasons": [],
            **sandbox_meta,
        }
        _write_report(result, candidate_hash, report_path)
        return result

    previous_best = _load_previous_best_score()
    fitness_report["score_components"] = _build_score_components(fitness_report)
    fitness_report["adoption_decision"] = _build_adoption_decision(
        fitness_report,
        previous_best=previous_best,
        baseline_mode=baseline_mode,
    )
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
        "contract_checks": all_contract_checks,
        "rejection_reasons": list(fitness_report.get("rejection_reasons", [])),
        **sandbox_meta,
    }
    _write_report(result, candidate_hash, report_path)
    return result


def _load_previous_best_score(genome_path: Path = _GENOME_PATH) -> float:
    """Load the current best score without mutating project state."""
    try:
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return -1e9
    try:
        return float(genome.get("best_score", -1e9))
    except (TypeError, ValueError):
        return -1e9


def _build_score_components(fitness_report: dict) -> dict:
    """Return score formula inputs and signed contribution terms.

    This mirrors the existing adoption score formula exactly and keeps
    changed_lines diagnostic-only.
    """
    tp_rate = float(fitness_report.get("tp_rate", 0.0))
    fp_rate = float(fitness_report.get("fp_rate", 0.0))
    fn_rate = float(fitness_report.get("fn_rate", 0.0))
    exception_count = int(fitness_report.get("exception_count", 0))
    code_chars = int(fitness_report.get("code_chars", 0))
    changed_lines = int(fitness_report.get("changed_lines", 0))
    score = float(fitness_report.get("score", 0.0))
    return {
        "tp_rate": tp_rate,
        "fp_rate": fp_rate,
        "fn_rate": fn_rate,
        "exception_count": exception_count,
        "code_chars": code_chars,
        "changed_lines": changed_lines,
        "contributions": {
            "tp_reward": 1000.0 * tp_rate,
            "fp_penalty": -2000.0 * fp_rate,
            "fn_penalty": -1500.0 * fn_rate,
            "exception_penalty": -50.0 * exception_count,
            "code_size_penalty": -0.02 * code_chars,
        },
        "diagnostics": {
            "changed_lines": changed_lines,
            "changed_lines_is_score_component": False,
        },
        "formula": _SCORE_FORMULA,
        "score": score,
    }


def _reason_code(reason: str) -> str:
    if reason.startswith("fp_rate="):
        return "hard_gate_failed_fp_rate"
    if reason.startswith("regression_pass_rate="):
        return "hard_gate_failed_regression_pass_rate"
    if reason.startswith("avg_latency_ms="):
        return "hard_gate_failed_avg_latency"
    if reason.startswith("score=") and "<= previous_best=" in reason:
        return "candidate_score_not_above_previous_best"
    return "candidate_evaluation_failed"


def _build_adoption_decision(
    fitness_report: dict,
    *,
    previous_best: float,
    baseline_mode: bool = False,
) -> dict:
    """Expose a machine-readable adoption decision without changing gates."""
    candidate_score = float(fitness_report.get("score", 0.0))
    strictly_exceeds = candidate_score > previous_best
    passed_adoption_gate = bool(fitness_report.get("passed_adoption_gate", False))
    raw_reasons = [str(r) for r in fitness_report.get("rejection_reasons", [])]
    reason_codes = [_reason_code(reason) for reason in raw_reasons]
    if not baseline_mode and not strictly_exceeds and "candidate_score_not_above_previous_best" not in reason_codes:
        reason_codes.append("candidate_score_not_above_previous_best")
    hard_gates_passed = passed_adoption_gate or (
        "candidate_score_not_above_previous_best" in reason_codes
        and all(code == "candidate_score_not_above_previous_best" for code in reason_codes)
    )
    if not passed_adoption_gate and not reason_codes:
        reason_codes.append("candidate_evaluation_failed")
    return {
        "previous_best": previous_best,
        "candidate_score": candidate_score,
        "strictly_exceeds_previous_best": strictly_exceeds,
        "hard_gates_passed": hard_gates_passed,
        "adoption_gate_passed": passed_adoption_gate,
        "rejection_reasons": reason_codes,
    }


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
        "score_components": fitness.get("score_components") if isinstance(fitness, dict) else None,
        "adoption_decision": fitness.get("adoption_decision") if isinstance(fitness, dict) else None,
        "return_code": result.get("return_code"),
        "contract_checks": result.get("contract_checks", []),
        "rejection_reasons": result.get("rejection_reasons", []),
        "sandbox_backend": result.get("sandbox_backend"),
        "sandbox_image": result.get("sandbox_image"),
        "sandbox_network": result.get("sandbox_network"),
        "sandbox_read_only": result.get("sandbox_read_only"),
        "sandbox_user": result.get("sandbox_user"),
        "sandbox_cap_drop": result.get("sandbox_cap_drop"),
        "sandbox_no_new_privileges": result.get("sandbox_no_new_privileges"),
        "sandbox_pids_limit": result.get("sandbox_pids_limit"),
        "sandbox_memory_limit": result.get("sandbox_memory_limit"),
        "sandbox_cpus": result.get("sandbox_cpus"),
        "sandbox_tmpfs": result.get("sandbox_tmpfs"),
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
        "--sandbox-backend",
        choices=[SandboxBackend.DOCKER, SandboxBackend.LEGACY_RLIMIT],
        default=SandboxBackend.DOCKER,
        help="Fitness sandbox backend (default: docker; legacy-rlimit is explicit local-dev/test fallback).",
    )
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
        sandbox_backend=args.sandbox_backend,
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
