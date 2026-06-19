"""tests/test_evaluate_candidate.py — Unit tests for scripts/evaluate_candidate.py.

Tests cover:
  A. Resource limiter helpers (_resource_limits_supported, _make_resource_limiter)
  B. Subprocess invocation includes preexec_fn on POSIX
  C. Resource setup / subprocess launch failure is fail-closed
  D. Timeout behavior is preserved
  E. No dangerous real resource abuse (all tests are deterministic and low-cost)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.evaluate_candidate import (
    _EVAL_MAX_ADDRESS_SPACE_BYTES,
    _EVAL_MAX_FILE_SIZE_BYTES,
    _EVAL_MAX_OPEN_FILES,
    _EVAL_MAX_PROCESSES,
    _PROJECT_ROOT as _EVAL_PROJECT_ROOT,
    SandboxBackend,
    _build_docker_command,
    _docker_launcher_env,
    _make_resource_limiter,
    _resource_limits_supported,
    evaluate_candidate,
)

# ---------------------------------------------------------------------------
# Shared test fixtures / helpers
# ---------------------------------------------------------------------------

# Use the actual detector as the minimal candidate — it passes all offline contract checks.
# The tests mock validate() and subprocess.run(), so the candidate content is irrelevant
# to what the tests are asserting; it just needs to clear the contract check gate.
_MINIMAL_CANDIDATE = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")

_FAKE_REJECTED_OUTPUT = json.dumps({
    "passed_adoption_gate": False,
    "score": 0.42,
    "tp_rate": 0.5,
    "fp_rate": 0.1,
})

_FAKE_PASSING_OUTPUT = json.dumps({
    "passed_adoption_gate": True,
    "score": 0.95,
    "tp_rate": 0.9,
    "fp_rate": 0.02,
})


def _fake_proc(stdout: str, returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _write_candidate(tmp_path: Path) -> Path:
    p = tmp_path / "candidate_detector.py"
    p.write_text(_MINIMAL_CANDIDATE, encoding="utf-8")
    return p


_BENIGN_PASS_RESULT = {
    "passed": True,
    "case_results": {
        name: {"blocked": False, "matched_signals": []}
        for name in ["method", "path", "query_keys", "query_values",
                     "header_keys", "header_values", "body", "combined"]
    },
    "failing_cases": [],
    "rejection_reasons": [],
    "harness_error": False,
    "error": None,
}

_BEHAVIORAL_PASS_RESULT = {
    "passed": True,
    "field_results": {
        ind: {f: True for f in ["method", "path", "query_keys", "query_values",
                                  "header_keys", "header_values", "body"]}
        for ind in [
            "path_traversal_indicator", "script_injection_indicator", "sqli_indicator",
            "command_delimiter_indicator", "encoded_traversal_indicator",
        ]
    },
    "missing": [],
    "rejection_reasons": [],
    "harness_error": False,
    "error": None,
}


@pytest.fixture(autouse=True)
def _auto_behavioral_pass(request):
    """Auto-patch run_behavioral_surface_check_subprocess to pass for all existing tests.

    Tests in TestEvaluateCandidateBehavioralSurfaceCheck explicitly patch it themselves
    or run the real pipeline, so they opt out via the marker.
    """
    if request.node.get_closest_marker("no_behavioral_mock"):
        yield
        return
    # Only auto-patch for classes that don't explicitly control behavioral check
    cls = request.node.cls
    if cls is not None and cls.__name__ == "TestEvaluateCandidateBehavioralSurfaceCheck":
        yield
        return
    with patch(
        "scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
        return_value=_BEHAVIORAL_PASS_RESULT,
    ), patch(
        "scripts.evaluate_candidate.run_behavioral_benign_control_check_subprocess",
        return_value=_BENIGN_PASS_RESULT,
    ):
        yield


# ===========================================================================
# A. Resource limiter helpers
# ===========================================================================

class TestResourceLimiterHelpers:
    """_resource_limits_supported() and _make_resource_limiter() behave correctly."""

    def test_resource_limiter_is_available_on_posix(self) -> None:
        """On POSIX, _resource_limits_supported() returns True when resource is importable."""
        if os.name == "posix":
            try:
                import resource  # noqa: F401
                assert _resource_limits_supported() is True
            except ImportError:
                assert _resource_limits_supported() is False
        else:
            assert _resource_limits_supported() is False

    def test_resource_limiter_unavailable_when_module_absent(self) -> None:
        """_resource_limits_supported() returns False when _resource_module is None."""
        with patch("scripts.evaluate_candidate._resource_module", None):
            assert _resource_limits_supported() is False

    def test_make_resource_limiter_returns_callable_on_posix(self) -> None:
        """On POSIX with resource available, _make_resource_limiter returns a callable."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")
        limiter = _make_resource_limiter(timeout_seconds=5)
        assert callable(limiter)

    def test_make_resource_limiter_raises_when_module_absent(self) -> None:
        """_make_resource_limiter raises RuntimeError when _resource_module is None."""
        with patch("scripts.evaluate_candidate._resource_module", None):
            with pytest.raises(RuntimeError, match="resource module"):
                _make_resource_limiter(timeout_seconds=5)

    def test_resource_limiter_sets_expected_limits(self) -> None:
        """Resource limiter must attempt to set RLIMIT_CPU, RLIMIT_AS, RLIMIT_FSIZE, RLIMIT_NOFILE."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        fake_resource = MagicMock()
        fake_resource.RLIMIT_CPU = 0
        fake_resource.RLIMIT_AS = 9
        fake_resource.RLIMIT_FSIZE = 1
        fake_resource.RLIMIT_NOFILE = 7
        fake_resource.RLIMIT_NPROC = 6

        with patch("scripts.evaluate_candidate._resource_module", fake_resource):
            limiter = _make_resource_limiter(timeout_seconds=10)
            limiter()

        set_rlimits = {c.args[0] for c in fake_resource.setrlimit.call_args_list}
        assert fake_resource.RLIMIT_CPU in set_rlimits, "RLIMIT_CPU must be set"
        assert fake_resource.RLIMIT_AS in set_rlimits, "RLIMIT_AS must be set"
        assert fake_resource.RLIMIT_FSIZE in set_rlimits, "RLIMIT_FSIZE must be set"
        assert fake_resource.RLIMIT_NOFILE in set_rlimits, "RLIMIT_NOFILE must be set"

    def test_resource_limiter_sets_nproc_when_available(self) -> None:
        """RLIMIT_NPROC is set when the attribute is present on the resource module."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        fake_resource = MagicMock()
        fake_resource.RLIMIT_CPU = 0
        fake_resource.RLIMIT_AS = 9
        fake_resource.RLIMIT_FSIZE = 1
        fake_resource.RLIMIT_NOFILE = 7
        fake_resource.RLIMIT_NPROC = 6

        with patch("scripts.evaluate_candidate._resource_module", fake_resource):
            limiter = _make_resource_limiter(timeout_seconds=5)
            limiter()

        set_rlimits = {c.args[0] for c in fake_resource.setrlimit.call_args_list}
        assert fake_resource.RLIMIT_NPROC in set_rlimits, "RLIMIT_NPROC must be set when available"

    def test_resource_limiter_cpu_bounded_by_timeout(self) -> None:
        """CPU rlimit soft and hard values must not exceed the requested timeout."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        fake_resource = MagicMock()
        fake_resource.RLIMIT_CPU = 0
        fake_resource.RLIMIT_AS = 9
        fake_resource.RLIMIT_FSIZE = 1
        fake_resource.RLIMIT_NOFILE = 7

        with patch("scripts.evaluate_candidate._resource_module", fake_resource):
            limiter = _make_resource_limiter(timeout_seconds=7)
            limiter()

        cpu_call = next(
            c for c in fake_resource.setrlimit.call_args_list
            if c.args[0] == fake_resource.RLIMIT_CPU
        )
        soft, hard = cpu_call.args[1]
        assert soft >= 1, "CPU soft limit must be at least 1 second"
        assert soft <= 7, "CPU soft limit must not exceed timeout"
        assert hard <= 7, "CPU hard limit must not exceed timeout"

    def test_resource_limiter_address_space_correct(self) -> None:
        """RLIMIT_AS is set to _EVAL_MAX_ADDRESS_SPACE_BYTES."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        fake_resource = MagicMock()
        fake_resource.RLIMIT_CPU = 0
        fake_resource.RLIMIT_AS = 9
        fake_resource.RLIMIT_FSIZE = 1
        fake_resource.RLIMIT_NOFILE = 7

        with patch("scripts.evaluate_candidate._resource_module", fake_resource):
            limiter = _make_resource_limiter(timeout_seconds=5)
            limiter()

        as_call = next(
            c for c in fake_resource.setrlimit.call_args_list
            if c.args[0] == fake_resource.RLIMIT_AS
        )
        soft, hard = as_call.args[1]
        assert soft == _EVAL_MAX_ADDRESS_SPACE_BYTES
        assert hard == _EVAL_MAX_ADDRESS_SPACE_BYTES


# ===========================================================================
# B. Subprocess invocation includes preexec_fn on POSIX
# ===========================================================================

class TestDockerSandboxBackend:
    """Docker sandbox is the production default and is constructed safely."""

    def test_docker_command_has_required_hardening_flags(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        cmd = _build_docker_command(candidate, timeout_seconds=5, baseline_mode=True)
        assert cmd[:3] == ["docker", "run", "--rm"]
        assert ["--network", "none"] == cmd[cmd.index("--network"):cmd.index("--network") + 2]
        assert "--read-only" in cmd
        assert ["--cap-drop", "ALL"] == cmd[cmd.index("--cap-drop"):cmd.index("--cap-drop") + 2]
        assert ["--security-opt", "no-new-privileges"] == cmd[cmd.index("--security-opt"):cmd.index("--security-opt") + 2]
        assert "--pids-limit" in cmd
        assert "--memory" in cmd
        assert "--cpus" in cmd
        assert ["--user", "65534:65534"] == cmd[cmd.index("--user"):cmd.index("--user") + 2]
        assert ["--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m"] == cmd[cmd.index("--tmpfs"):cmd.index("--tmpfs") + 2]
        mounts = [cmd[i + 1] for i, token in enumerate(cmd) if token == "-v"]
        assert f"{_EVAL_PROJECT_ROOT}:/workspace:ro" in mounts
        assert f"{candidate.resolve()}:/candidate/candidate_detector.py:ro" in mounts
        assert "--baseline" in cmd

    def test_docker_launcher_env_strips_secrets(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "x", "GEMINI_API_KEY": "y", "AWS_SECRET_ACCESS_KEY": "z"}):
            env = _docker_launcher_env()
        assert "GITHUB_TOKEN" not in env
        assert "GEMINI_API_KEY" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env

    def test_default_backend_runs_docker_and_records_metadata(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate._run_fitness_in_docker", return_value=_fake_proc(_FAKE_PASSING_OUTPUT)) as run_docker:
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, baseline_mode=True)
        run_docker.assert_called_once()
        assert result["sandbox_backend"] == "docker"
        assert result["sandbox_network"] == "none"
        report = json.loads(report_path.read_text())
        assert report["sandbox_backend"] == "docker"
        assert report["sandbox_read_only"] is True

    def test_docker_unavailable_fails_closed(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate._run_fitness_in_docker", side_effect=OSError("docker sandbox unavailable")):
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)
        assert result["success"] is False
        assert result["passed_adoption_gate"] is False
        assert result["is_tool_failure"] is True
        assert "docker" in result["error"].lower() or "sandbox" in result["error"].lower()
        assert report_path.exists()

    def test_docker_timeout_fails_closed(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate._run_fitness_in_docker", side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=5)):
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)
        assert result["timed_out"] is True
        assert result["is_tool_failure"] is True
        assert result["success"] is False

    def test_malformed_docker_stdout_is_tool_failure(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate._run_fitness_in_docker", return_value=_fake_proc("not json")):
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)
        assert result["is_tool_failure"] is True
        assert "parse" in result["error"].lower()


class TestLegacySubprocessPreexecFn:
    """Explicit legacy backend passes preexec_fn and preserves required kwargs."""

    def test_preexec_fn_present_and_callable_on_posix(self, tmp_path: Path) -> None:
        """On POSIX, subprocess.run must receive a callable preexec_fn."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)) as mock_run:
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        assert mock_run.called
        kwargs = mock_run.call_args.kwargs
        assert "preexec_fn" in kwargs, "preexec_fn must be passed to subprocess.run on POSIX"
        assert callable(kwargs["preexec_fn"]), "preexec_fn must be callable"

    def test_timeout_still_passed_to_subprocess(self, tmp_path: Path) -> None:
        """timeout=timeout_seconds must still be passed to subprocess.run."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)) as mock_run:
                evaluate_candidate(candidate, timeout_seconds=8, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        kwargs = mock_run.call_args.kwargs
        assert kwargs.get("timeout") == 8, "timeout must be passed to subprocess.run"

    def test_safe_env_passed_to_subprocess(self, tmp_path: Path) -> None:
        """env must be the stripped _safe_env() — no secrets."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)) as mock_run:
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        kwargs = mock_run.call_args.kwargs
        env = kwargs.get("env", {})
        sensitive = {"GEMINI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "AWS_SECRET_ACCESS_KEY"}
        leaked = sensitive & set(env.keys())
        assert not leaked, f"Sensitive keys must not reach child env: {leaked}"

    def test_cwd_is_project_root(self, tmp_path: Path) -> None:
        """cwd passed to subprocess must be the project root."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)) as mock_run:
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        kwargs = mock_run.call_args.kwargs
        assert kwargs.get("cwd") == str(_EVAL_PROJECT_ROOT)


# ===========================================================================
# C. Resource setup / subprocess launch failure is fail-closed
# ===========================================================================

class TestFailClosed:
    """Resource setup failure and subprocess launch failure must return is_tool_failure=True."""

    def test_subprocess_oserror_is_tool_failure(self, tmp_path: Path) -> None:
        """OSError from subprocess.run must produce is_tool_failure=True result."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", side_effect=OSError("simulated launch error")):
                result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert result["success"] is False
        assert result["passed_adoption_gate"] is False
        assert result["is_tool_failure"] is True
        assert result["timed_out"] is False
        assert "sandbox" in result["error"].lower() or "docker" in result["error"].lower()
        assert result.get("candidate_hash") is not None
        assert report_path.exists(), "report must be written on subprocess failure"

    def test_subprocess_error_is_tool_failure(self, tmp_path: Path) -> None:
        """subprocess.SubprocessError must produce is_tool_failure=True result."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run",
                       side_effect=subprocess.SubprocessError("simulated subprocess error")):
                result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert result["success"] is False
        assert result["is_tool_failure"] is True
        assert result.get("candidate_hash") is not None
        assert report_path.exists()

    def test_resource_module_none_is_tool_failure(self, tmp_path: Path) -> None:
        """When _resource_module is None (non-POSIX / missing module), result is tool failure."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate._resource_module", None):
            with patch("scripts.evaluate_candidate.validate",
                       return_value={"valid": True, "violations": []}):
                result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        assert result["success"] is False
        assert result["is_tool_failure"] is True
        assert "resource" in result["error"].lower() or "posix" in result["error"].lower()
        assert result.get("candidate_hash") is not None
        assert report_path.exists(), "report must be written even when resource limits unavailable"

    def test_resource_limiter_runtime_error_is_tool_failure(self, tmp_path: Path) -> None:
        """RuntimeError from _make_resource_limiter must produce is_tool_failure=True."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate._make_resource_limiter",
                       side_effect=RuntimeError("simulated resource setup error")):
                with patch("scripts.evaluate_candidate._resource_limits_supported",
                           return_value=True):
                    result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, sandbox_backend=SandboxBackend.LEGACY_RLIMIT)

        assert result["success"] is False
        assert result["is_tool_failure"] is True
        assert "resource" in result["error"].lower() or "limit" in result["error"].lower()
        assert report_path.exists()


# ===========================================================================
# D. Timeout behavior preserved
# ===========================================================================

class TestTimeoutBehavior:
    """Wall-clock timeout must still work and produce a timed_out=True result."""

    def test_timeout_expired_sets_timed_out(self, tmp_path: Path) -> None:
        """subprocess.TimeoutExpired must set timed_out=True and is_tool_failure=True."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        timeout_exc = subprocess.TimeoutExpired(cmd=["python"], timeout=5)
        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate._run_fitness_in_docker", side_effect=timeout_exc):
                result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert result["timed_out"] is True
        assert result["is_tool_failure"] is True
        assert result["success"] is False
        assert result["passed_adoption_gate"] is False
        assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()
        assert result.get("candidate_hash") is not None
        assert report_path.exists(), "report must be written on timeout"

    def test_timeout_error_message_includes_duration(self, tmp_path: Path) -> None:
        """Timeout error message must include the timeout duration."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        timeout_exc = subprocess.TimeoutExpired(cmd=["python"], timeout=12)
        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate._run_fitness_in_docker", side_effect=timeout_exc):
                result = evaluate_candidate(candidate, timeout_seconds=12, report_path=report_path)

        assert "12" in result["error"], "Timeout error must include the timeout duration"


# ===========================================================================
# E. Verify constants are in reasonable ranges (no real resource abuse)
# ===========================================================================

class TestResourceLimitConstants:
    """Resource limit constants must be sane — not so tight they break fitness evaluation."""

    def test_address_space_at_least_256_mib(self) -> None:
        assert _EVAL_MAX_ADDRESS_SPACE_BYTES >= 256 * 1024 * 1024, (
            "Address space limit must be at least 256 MiB to allow fitness evaluation"
        )

    def test_address_space_at_most_2_gib(self) -> None:
        assert _EVAL_MAX_ADDRESS_SPACE_BYTES <= 2 * 1024 * 1024 * 1024, (
            "Address space limit should be bounded to prevent unbounded memory"
        )

    def test_file_size_at_least_1_mib(self) -> None:
        assert _EVAL_MAX_FILE_SIZE_BYTES >= 1024 * 1024, (
            "File size limit must allow at least 1 MiB writes"
        )

    def test_open_files_at_least_32(self) -> None:
        assert _EVAL_MAX_OPEN_FILES >= 32, (
            "Open file limit must allow at least 32 file descriptors for Python runtime"
        )

    def test_process_count_at_least_8(self) -> None:
        assert _EVAL_MAX_PROCESSES >= 8, (
            "Process limit must allow a small number of subprocesses"
        )


# ===========================================================================
# F. Fitness report schema: stage field and required fields
# ===========================================================================


class TestFitnessReportSchema:
    """fitness_report.json must always include the required schema fields."""

    def test_report_has_stage_field(self, tmp_path: Path) -> None:
        """fitness_report.json must include stage='evaluate_candidate'."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)):
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report.get("stage") == "evaluate_candidate"

    def test_report_has_passed_adoption_gate(self, tmp_path: Path) -> None:
        """fitness_report.json must include passed_adoption_gate field."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)):
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert "passed_adoption_gate" in report
        assert isinstance(report["passed_adoption_gate"], bool)

    def test_report_has_is_tool_failure(self, tmp_path: Path) -> None:
        """fitness_report.json must include is_tool_failure field."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)):
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert "is_tool_failure" in report

    def test_report_has_timed_out(self, tmp_path: Path) -> None:
        """fitness_report.json must include timed_out field."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)):
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert "timed_out" in report
        assert isinstance(report["timed_out"], bool)

    def test_report_has_candidate_hash(self, tmp_path: Path) -> None:
        """fitness_report.json must include candidate_hash field."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("subprocess.run", return_value=_fake_proc(_FAKE_REJECTED_OUTPUT)):
                evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert "candidate_hash" in report
        assert report["candidate_hash"] is not None
        assert len(report["candidate_hash"]) == 64


# ===========================================================================
# G. Non-existent candidate → report generated with candidate_hash=null
# ===========================================================================


class TestNonExistentCandidateReport:
    """A non-existent candidate file must produce a report with candidate_hash=null."""

    def test_nonexistent_candidate_generates_report(self, tmp_path: Path) -> None:
        """evaluate_candidate must write fitness_report.json even when file doesn't exist."""
        candidate = tmp_path / "does_not_exist.py"
        report_path = tmp_path / "report.json"

        result = evaluate_candidate(
            candidate, timeout_seconds=5, report_path=report_path
        )

        assert result["success"] is False
        assert result["is_tool_failure"] is True
        assert report_path.exists(), "report must be written when candidate file is missing"

    def test_nonexistent_candidate_report_has_null_hash(self, tmp_path: Path) -> None:
        """Report for a non-existent candidate must have candidate_hash=null."""
        candidate = tmp_path / "does_not_exist.py"
        report_path = tmp_path / "report.json"

        evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert report.get("candidate_hash") is None

    def test_nonexistent_candidate_report_stage(self, tmp_path: Path) -> None:
        """Report for non-existent candidate must have stage='evaluate_candidate'."""
        candidate = tmp_path / "does_not_exist.py"
        report_path = tmp_path / "report.json"

        evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert report.get("stage") == "evaluate_candidate"


# ===========================================================================
# H. AST validation failure → report generated with candidate_hash populated
# ===========================================================================


class TestAstFailureReport:
    """AST validation failure must produce a report with candidate_hash."""

    def test_ast_failure_generates_report(self, tmp_path: Path) -> None:
        """AST validation failure must write fitness_report.json."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": False, "violations": ["forbidden import"]}):
            result = evaluate_candidate(
                candidate, timeout_seconds=5, report_path=report_path
            )

        assert result["is_tool_failure"] is True
        assert report_path.exists(), "report must be written on AST validation failure"

    def test_ast_failure_report_has_candidate_hash(self, tmp_path: Path) -> None:
        """Report on AST failure must include the candidate's hash."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": False, "violations": ["forbidden"]}):
            evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert report.get("candidate_hash") is not None
        assert len(report["candidate_hash"]) == 64

    def test_ast_failure_report_has_stage(self, tmp_path: Path) -> None:
        """Report on AST failure must have stage='evaluate_candidate'."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": False, "violations": ["violation"]}):
            evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert report.get("stage") == "evaluate_candidate"

    def test_ast_failure_report_violations_populated(self, tmp_path: Path) -> None:
        """Report on AST failure must include the violation list."""
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        violations = ["forbidden import: os", "dunder access denied"]

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": False, "violations": violations}):
            evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert report.get("violations") == violations


# ===========================================================================
# I. No secrets in fitness report
# ===========================================================================


class TestNoSecretsInReport:
    """fitness_report.json must not contain secret-like env vars or raw payloads."""

    _SECRET_KEYS = [
        "GEMINI_API_KEY",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "OPENAI_API_KEY",
    ]

    def test_no_secret_env_vars_in_report_on_failure(self, tmp_path: Path) -> None:
        """fitness_report.json must not contain secret env-var names on failure."""
        if not _resource_limits_supported():
            pytest.skip("POSIX resource limits not available on this platform")

        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        # Inject fake secrets into the environment to verify they are stripped
        fake_env = {k: "FAKE_SECRET_VALUE" for k in self._SECRET_KEYS}

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch.dict(os.environ, fake_env):
                with patch("subprocess.run",
                           side_effect=OSError("simulated launch error")):
                    evaluate_candidate(
                        candidate, timeout_seconds=5, report_path=report_path
                    )

        report_text = report_path.read_text()
        for key in self._SECRET_KEYS:
            assert "FAKE_SECRET_VALUE" not in report_text, (
                f"Secret value for {key} must not appear in fitness_report.json"
            )

    def test_safe_env_strips_secrets_from_subprocess(self, tmp_path: Path) -> None:
        """_safe_env() must strip all known secret env vars before subprocess launch."""
        from scripts.evaluate_candidate import _safe_env
        import os

        fake_env = {k: "SECRET_VALUE" for k in self._SECRET_KEYS}
        with patch.dict(os.environ, fake_env):
            safe = _safe_env()

        for key in self._SECRET_KEYS:
            assert key not in safe, (
                f"{key} must be stripped by _safe_env() — must not reach subprocess"
            )


def _make_mock_proc(returncode: int, stdout: str, stderr: str = "") -> SimpleNamespace:
    """Create a mock subprocess.CompletedProcess-like object for tests."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ===========================================================================
# Behavioral surface check integration with evaluate_candidate
# ===========================================================================

class TestEvaluateCandidateBehavioralSurfaceCheck:
    """evaluate_candidate soft-rejects behavioral surface failures before fitness."""

    def _write_candidate(self, tmp_path: Path) -> Path:
        """Write a candidate that passes static checks."""
        p = tmp_path / "candidate.py"
        p.write_text(_MINIMAL_CANDIDATE, encoding="utf-8")
        return p

    def test_behavioral_failure_is_soft_reject(self, tmp_path: Path) -> None:
        """Behavioral surface check failure must be is_tool_failure=False."""
        from scripts.evaluate_candidate import evaluate_candidate

        p = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        behavioral_fail = {
            "passed": False,
            "field_results": {f: False for f in ["method", "path", "query_keys",
                                                   "query_values", "header_keys",
                                                   "header_values", "body"]},
            "missing": ["method", "header_keys", "header_values"],
            "rejection_reasons": [
                "missing_request_surface:method",
                "missing_request_surface:header_keys",
                "missing_request_surface:header_values",
            ],
            "harness_error": False,
            "error": None,
        }

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
                       return_value=behavioral_fail):
                result = evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        assert not result["success"]
        assert result["is_tool_failure"] is False
        assert "missing_request_surface:method" in result["rejection_reasons"]

    def test_behavioral_harness_error_is_tool_failure(self, tmp_path: Path) -> None:
        """Behavioral subprocess crash must be is_tool_failure=True."""
        from scripts.evaluate_candidate import evaluate_candidate

        p = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        harness_fail = {
            "passed": False,
            "field_results": {},
            "missing": [],
            "rejection_reasons": [],
            "harness_error": True,
            "error": "behavioral check subprocess timed out",
        }

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
                       return_value=harness_fail):
                result = evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        assert not result["success"]
        assert result["is_tool_failure"] is True

    def test_report_includes_behavioral_check_entry(self, tmp_path: Path) -> None:
        """Written report must include request_surface_coverage_behavioral in contract_checks."""
        from scripts.evaluate_candidate import evaluate_candidate
        import json

        p = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        behavioral_fail = {
            "passed": False,
            "field_results": {"method": False, "path": True, "query_keys": True,
                               "query_values": True, "header_keys": False,
                               "header_values": False, "body": True},
            "missing": ["method", "header_keys", "header_values"],
            "rejection_reasons": [
                "missing_request_surface:method",
                "missing_request_surface:header_keys",
                "missing_request_surface:header_values",
            ],
            "harness_error": False,
            "error": None,
        }

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
                       return_value=behavioral_fail):
                evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        names = {c["name"] for c in report.get("contract_checks", [])}
        assert "request_surface_coverage_behavioral" in names

    def test_behavioral_check_result_has_field_results_in_report(self, tmp_path: Path) -> None:
        """The behavioral check entry in report must include field_results detail."""
        from scripts.evaluate_candidate import evaluate_candidate
        import json

        p = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        behavioral_pass = {
            "passed": True,
            "field_results": {f: True for f in ["method", "path", "query_keys",
                                                   "query_values", "header_keys",
                                                   "header_values", "body"]},
            "missing": [],
            "rejection_reasons": [],
            "harness_error": False,
            "error": None,
        }

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
                       return_value=behavioral_pass):
                with patch("subprocess.run") as mock_sub:
                    mock_sub.return_value = _make_mock_proc(
                        returncode=1, stdout=json.dumps({"passed_adoption_gate": False,
                                                          "rejection_reasons": ["score <= best"],
                                                          "score": 0.0})
                    )
                    evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        behavioral_entries = [c for c in report.get("contract_checks", [])
                               if c["name"] == "request_surface_coverage_behavioral"]
        assert len(behavioral_entries) == 1
        assert "field_results" in behavioral_entries[0]["details"]

    def test_indicator_aware_rejection_in_report(self, tmp_path: Path) -> None:
        """Report must propagate indicator-aware rejection reasons from behavioral check."""
        from scripts.evaluate_candidate import evaluate_candidate

        p = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        behavioral_fail = {
            "passed": False,
            "field_results": {
                "path_traversal_indicator": {f: True for f in [
                    "method", "path", "query_keys", "query_values",
                    "header_keys", "header_values", "body",
                ]},
                "sqli_indicator": {f: False for f in [
                    "method", "path", "query_keys", "query_values",
                    "header_keys", "header_values", "body",
                ]},
                "script_injection_indicator": {f: True for f in [
                    "method", "path", "query_keys", "query_values",
                    "header_keys", "header_values", "body",
                ]},
                "command_delimiter_indicator": {f: True for f in [
                    "method", "path", "query_keys", "query_values",
                    "header_keys", "header_values", "body",
                ]},
                "encoded_traversal_indicator": {f: True for f in [
                    "method", "path", "query_keys", "query_values",
                    "header_keys", "header_values", "body",
                ]},
            },
            "missing": [
                {"indicator": "sqli_indicator", "surface": s}
                for s in ["method", "path", "query_keys", "query_values",
                          "header_keys", "header_values", "body"]
            ],
            "rejection_reasons": [
                "missing_baseline_symbolic_indicator_runtime:sqli_indicator",
                "missing_request_surface:method:sqli_indicator",
                "missing_request_surface:method",
            ],
            "harness_error": False,
            "error": None,
        }

        with patch("scripts.evaluate_candidate.validate",
                   return_value={"valid": True, "violations": []}):
            with patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess",
                       return_value=behavioral_fail):
                result = evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        assert not result["success"]
        assert result["is_tool_failure"] is False
        assert "missing_baseline_symbolic_indicator_runtime:sqli_indicator" in result["rejection_reasons"]

        report = json.loads(report_path.read_text())
        behavioral_entries = [c for c in report.get("contract_checks", [])
                               if c["name"] == "request_surface_coverage_behavioral"]
        assert len(behavioral_entries) == 1
        entry = behavioral_entries[0]
        assert isinstance(entry["details"]["field_results"], dict)
        # indicator-aware rejection reasons appear in report
        assert any(
            "missing_baseline_symbolic_indicator_runtime" in r
            for r in entry["rejection_reasons"]
        )

    def test_unreachable_code_candidate_soft_rejected_in_full_pipeline(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """End-to-end: candidate with unreachable surface code is soft-rejected by Step 2b."""
        from scripts.evaluate_candidate import evaluate_candidate

        # Build a candidate using core/detector.py outside region but with unreachable
        # surface code in the mutation region — passes static checks, fails behavioral.
        base = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        _MS = "# === MUTATION_START ==="
        _ME = "# === MUTATION_END ==="
        ms_idx = base.index(_MS)
        me_idx = base.index(_ME)
        unreachable_region = (
            '    tokens = ("path_traversal_indicator", "script_injection_indicator",'
            ' "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")\n'
            '    if False:\n'
            '        surface_list = []\n'
            '        surface_list.append(request.method.lower())\n'
            '        surface_list.append(request.path.lower())\n'
            '        for k, v in request.query.items():\n'
            '            surface_list.append(k.lower())\n'
            '            surface_list.append(v.lower())\n'
            '        for k, v in request.headers.items():\n'
            '            surface_list.append(k.lower())\n'
            '            surface_list.append(v.lower())\n'
            '        surface_list.append(request.body.lower())\n'
            '    surface = request.body.lower()\n'
            '    for token in tokens:\n'
            '        if token in surface:\n'
            '            return DetectionResult(blocked=True, reason="match",'
            ' confidence=0.9, matched_signals=(token,))\n'
            '    return DetectionResult(blocked=False, reason="clean",'
            ' confidence=0.0, matched_signals=())\n'
        )
        candidate_source = (
            base[: ms_idx + len(_MS)] + "\n" + unreachable_region + "    " + base[me_idx:]
        )
        p = tmp_path / "candidate.py"
        p.write_text(candidate_source, encoding="utf-8")
        report_path = tmp_path / "report.json"

        # Run without mocking validate or behavioral check. In local test environments
        # without Docker, emulate the Docker runner while preserving the production
        # function boundary that behavioral checks use.
        from scripts import candidate_contract

        def _fake_docker_runner(*, candidate_path, command, timeout_seconds, project_root=None):
            mapped = [
                str(project_root or _PROJECT_ROOT) if a == candidate_contract.CONTAINER_WORKSPACE
                else str(candidate_path) if a == candidate_contract.CONTAINER_CANDIDATE
                else a
                for a in command
            ]
            return subprocess.run(
                mapped, capture_output=True, text=True, timeout=timeout_seconds,
                cwd=str(project_root or _PROJECT_ROOT),
            )

        monkeypatch.setattr(candidate_contract, "run_candidate_runtime_in_docker", _fake_docker_runner)
        result = evaluate_candidate(p, timeout_seconds=30, report_path=report_path)

        assert not result["success"]
        assert result["is_tool_failure"] is False, (
            f"Expected soft reject, got tool failure: {result['error']}"
        )
        assert any("missing_request_surface" in r for r in result["rejection_reasons"]), (
            f"Expected surface rejection reasons, got: {result['rejection_reasons']}"
        )


# ===========================================================================
# F. Behavioral benign-control evaluation integration
# ===========================================================================

class TestEvaluateCandidateBehavioralBenignControls:
    """Benign-control contract failures reject before fitness evaluation."""

    def test_benign_control_failure_is_soft_rejection_without_fitness(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        benign_fail = {
            "passed": False,
            "case_results": {"method": {"blocked": True, "matched_signals": []}},
            "failing_cases": ["method"],
            "rejection_reasons": ["benign_control_blocked"],
            "harness_error": False,
            "error": None,
        }
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess", return_value=_BEHAVIORAL_PASS_RESULT), \
             patch("scripts.evaluate_candidate.run_behavioral_benign_control_check_subprocess", return_value=benign_fail), \
             patch("subprocess.run") as mock_run:
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert result["is_tool_failure"] is False
        assert result["passed_adoption_gate"] is False
        assert result["fitness_report"] is None
        assert "benign_control_blocked" in result["rejection_reasons"]
        assert any(c["name"] == "behavioral_benign_controls" for c in result["contract_checks"])
        mock_run.assert_not_called()

    def test_benign_control_harness_failure_is_tool_failure(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        benign_harness_fail = {
            "passed": False,
            "case_results": {},
            "failing_cases": ["method"],
            "rejection_reasons": ["benign_control_malformed_result"],
            "harness_error": True,
            "error": "behavioral benign-control check failed to launch",
        }
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess", return_value=_BEHAVIORAL_PASS_RESULT), \
             patch("scripts.evaluate_candidate.run_behavioral_benign_control_check_subprocess", return_value=benign_harness_fail), \
             patch("subprocess.run") as mock_run:
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        assert result["is_tool_failure"] is True
        assert result["fitness_report"] is None
        assert any(c["name"] == "behavioral_benign_controls" for c in result["contract_checks"])
        mock_run.assert_not_called()

    def test_score_transparency_remains_for_fitness_path(self, tmp_path: Path) -> None:
        candidate = _write_candidate(tmp_path)
        report_path = tmp_path / "report.json"
        with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
             patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess", return_value=_BEHAVIORAL_PASS_RESULT), \
             patch("scripts.evaluate_candidate.run_behavioral_benign_control_check_subprocess", return_value=_BENIGN_PASS_RESULT), \
             patch("subprocess.run", return_value=_fake_proc(_FAKE_PASSING_OUTPUT)):
            result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path, baseline_mode=True)

        assert result["fitness_report"] is not None
        assert "score_components" in result["fitness_report"]
        assert "adoption_decision" in result["fitness_report"]
        assert any(c["name"] == "behavioral_benign_controls" for c in result["contract_checks"])
