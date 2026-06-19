"""tests/test_candidate_contract.py — Tests for scripts/candidate_contract.py.

Covers:
  A. check_baseline_symbolic_indicators — static check for all five indicators
  B. check_request_surface_coverage — static AST check
  C. check_request_surface_coverage_behavioral — runtime surface check
  D. check_mutation_region_integrity — marker presence / uniqueness / boundary
  E. check_candidate_hash_consistency — hash comparison
  F. run_candidate_contract_checks — combined runner + integration
  G. Adoption gate: generation 3 current detector must NOT pass against previous_best=947.66
  H. evaluate_candidate report includes contract_checks field
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts import candidate_contract
from scripts.candidate_contract import (
    BASELINE_SYMBOLIC_INDICATORS,
    REQUEST_SURFACE_FIELDS,
    ContractCheckResult,
    check_baseline_symbolic_indicators,
    check_candidate_hash_consistency,
    check_mutation_region_integrity,
    check_request_surface_coverage,
    check_request_surface_coverage_behavioral,
    run_behavioral_surface_check_subprocess,
    run_behavioral_benign_control_check_subprocess,
    run_candidate_contract_checks,
)


@pytest.fixture(autouse=True)
def _fake_docker_runner_when_docker_absent(monkeypatch, request):
    """Keep behavioral contract tests deterministic in containers without Docker.

    Production code still uses Docker by default; this test-only fixture emulates the
    Docker runner boundary for behavioral-result regression tests when Docker is not
    installed in the local test environment. Tests marked no_docker_runner_mock inspect
    the real Docker command/availability helpers directly.
    """
    if request.node.cls is not None and request.node.cls.__name__ == "TestCandidateRuntimeDockerSandbox":
        yield
        return
    if candidate_contract.docker_available():
        yield
        return

    def _fake_docker_runner(*, candidate_path, command, timeout_seconds, project_root=None):
        root = project_root or _PROJECT_ROOT
        mapped = [
            str(root) if arg == candidate_contract.CONTAINER_WORKSPACE
            else str(candidate_path) if arg == candidate_contract.CONTAINER_CANDIDATE
            else arg
            for arg in command
        ]
        return subprocess.run(
            mapped,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(root),
        )

    monkeypatch.setattr(candidate_contract, "run_candidate_runtime_in_docker", _fake_docker_runner)
    yield

# ---------------------------------------------------------------------------
# Shared synthetic candidate templates (safe — uses only neutralized indicators)
# ---------------------------------------------------------------------------

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="

# Full-coverage candidate: all 5 indicators, all 7 surface fields, valid markers
_FULL_CANDIDATE = """\
\"\"\"Full-coverage test candidate.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = []
    surface_list.append(request.method.lower())
    surface_list.append(request.path.lower())
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface_list.append(request.body.lower())
    surface = " ".join(surface_list)
    matched = []
    for token in tokens:
        if token in surface:
            matched.append(token)
    if matched:
        return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=tuple(matched))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Missing sqli_indicator only (docstring intentionally omits the indicator name)
_MISSING_SQLI = """\
\"\"\"Candidate with one indicator omitted from token list.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = []
    surface_list.append(request.method.lower())
    surface_list.append(request.path.lower())
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface_list.append(request.body.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Missing path_traversal_indicator AND sqli_indicator
_MISSING_TWO_INDICATORS = """\
\"\"\"Candidate with two indicators omitted from token list.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("script_injection_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = []
    surface_list.append(request.method.lower())
    surface_list.append(request.path.lower())
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface_list.append(request.body.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Body and path only — no method/query/headers
_BODY_PATH_ONLY = """\
\"\"\"Only inspects body and path.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface = request.path.lower() + " " + request.body.lower()
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Checks query values only (not query keys or header keys)
_QUERY_VALUES_ONLY = """\
\"\"\"Only checks query/header values, not keys.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for v in request.query.values():
        surface_list.append(v.lower())
    for v in request.headers.values():
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# No mutation markers at all
_NO_MARKERS = """\
\"\"\"No mutation markers.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
"""

_BASE_SOURCE_FOR_BOUNDARY = """\
\"\"\"Base for boundary test.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface = request.body.lower()
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate where the OUTSIDE region (before MUTATION_START) differs from base
_OUTSIDE_CHANGED = """\
\"\"\"Outside-region changed — extra comment before marker.\"\"\"
from core.types import Request, DetectionResult

# extra line injected outside mutation region
def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface = request.body.lower()
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""


def _load_inspect_fn(tmp_path: Path, source: str):
    """Write source to temp file, load module, return inspect_request callable."""
    p = tmp_path / "candidate.py"
    p.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_test_candidate", p)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.inspect_request


# ===========================================================================
# A. Baseline symbolic indicator checks
# ===========================================================================

class TestBaselineSymbolicIndicators:
    """check_baseline_symbolic_indicators rejects candidates missing any indicator."""

    def test_full_candidate_passes(self) -> None:
        result = check_baseline_symbolic_indicators(_FULL_CANDIDATE)
        assert result.passed
        assert result.rejection_reasons == ()

    def test_missing_one_indicator_rejected(self) -> None:
        result = check_baseline_symbolic_indicators(_MISSING_SQLI)
        assert not result.passed
        assert "missing_baseline_symbolic_indicator:sqli_indicator" in result.rejection_reasons

    def test_missing_one_indicator_only_flags_that_one(self) -> None:
        result = check_baseline_symbolic_indicators(_MISSING_SQLI)
        assert len(result.rejection_reasons) == 1

    def test_missing_two_indicators_rejected(self) -> None:
        result = check_baseline_symbolic_indicators(_MISSING_TWO_INDICATORS)
        assert not result.passed
        assert "missing_baseline_symbolic_indicator:path_traversal_indicator" in result.rejection_reasons
        assert "missing_baseline_symbolic_indicator:sqli_indicator" in result.rejection_reasons

    def test_missing_two_indicators_two_reasons(self) -> None:
        result = check_baseline_symbolic_indicators(_MISSING_TWO_INDICATORS)
        assert len(result.rejection_reasons) == 2

    def test_empty_source_all_rejected(self) -> None:
        result = check_baseline_symbolic_indicators("")
        assert not result.passed
        assert len(result.rejection_reasons) == len(BASELINE_SYMBOLIC_INDICATORS)

    def test_details_lists_missing_and_present(self) -> None:
        result = check_baseline_symbolic_indicators(_MISSING_SQLI)
        assert "sqli_indicator" in result.details["missing"]
        assert "path_traversal_indicator" in result.details["present"]

    def test_result_is_frozen_dataclass(self) -> None:
        result = check_baseline_symbolic_indicators(_FULL_CANDIDATE)
        assert isinstance(result, ContractCheckResult)
        with pytest.raises((AttributeError, TypeError)):
            result.passed = False  # type: ignore[misc]

    def test_actual_detector_passes(self) -> None:
        """Current generation 3 core/detector.py passes the baseline indicator check."""
        detector = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        result = check_baseline_symbolic_indicators(detector)
        assert result.passed, f"Detector fails baseline check: {result.rejection_reasons}"


# ===========================================================================
# B. Request surface coverage — static AST
# ===========================================================================

class TestRequestSurfaceCoverageStatic:
    """Static AST check rejects candidates that skip request surface fields."""

    def test_full_candidate_passes(self) -> None:
        result = check_request_surface_coverage(_FULL_CANDIDATE)
        assert result.passed
        assert result.rejection_reasons == ()

    def test_body_path_only_rejected(self) -> None:
        result = check_request_surface_coverage(_BODY_PATH_ONLY)
        assert not result.passed

    def test_body_path_only_missing_method(self) -> None:
        result = check_request_surface_coverage(_BODY_PATH_ONLY)
        assert "missing_request_surface:method" in result.rejection_reasons

    def test_body_path_only_missing_query(self) -> None:
        result = check_request_surface_coverage(_BODY_PATH_ONLY)
        assert "missing_request_surface:query_keys" in result.rejection_reasons
        assert "missing_request_surface:query_values" in result.rejection_reasons

    def test_body_path_only_missing_headers(self) -> None:
        result = check_request_surface_coverage(_BODY_PATH_ONLY)
        assert "missing_request_surface:header_keys" in result.rejection_reasons
        assert "missing_request_surface:header_values" in result.rejection_reasons

    def test_query_values_only_flags_missing_query_keys(self) -> None:
        """Candidate using request.query.values() only must flag missing query_keys."""
        result = check_request_surface_coverage(_QUERY_VALUES_ONLY)
        assert not result.passed
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_query_values_only_flags_missing_header_keys(self) -> None:
        """Candidate using request.headers.values() only must flag missing header_keys."""
        result = check_request_surface_coverage(_QUERY_VALUES_ONLY)
        assert "missing_request_surface:header_keys" in result.rejection_reasons

    def test_result_name_correct(self) -> None:
        result = check_request_surface_coverage(_FULL_CANDIDATE)
        assert result.name == "request_surface_coverage"

    def test_actual_detector_passes(self) -> None:
        detector = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        result = check_request_surface_coverage(detector)
        assert result.passed, f"Detector fails surface check: {result.rejection_reasons}"


# ===========================================================================
# C. Request surface coverage — behavioral
# ===========================================================================

class TestRequestSurfaceCoverageBehavioral:
    """Behavioral check rejects candidates that miss surface fields at runtime."""

    def test_full_candidate_passes(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _FULL_CANDIDATE)
        result = check_request_surface_coverage_behavioral(fn)
        assert result.passed

    def test_body_path_only_rejected(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _BODY_PATH_ONLY)
        result = check_request_surface_coverage_behavioral(fn)
        assert not result.passed

    def test_body_path_only_misses_method(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _BODY_PATH_ONLY)
        result = check_request_surface_coverage_behavioral(fn)
        assert "missing_request_surface:method" in result.rejection_reasons

    def test_body_path_only_misses_query_keys(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _BODY_PATH_ONLY)
        result = check_request_surface_coverage_behavioral(fn)
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_query_values_only_misses_query_keys(self, tmp_path: Path) -> None:
        """Candidate using .values() for query misses indicators in query keys."""
        fn = _load_inspect_fn(tmp_path, _QUERY_VALUES_ONLY)
        result = check_request_surface_coverage_behavioral(fn)
        assert not result.passed
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_query_values_only_misses_header_keys(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _QUERY_VALUES_ONLY)
        result = check_request_surface_coverage_behavioral(fn)
        assert "missing_request_surface:header_keys" in result.rejection_reasons

    def test_result_name_correct(self, tmp_path: Path) -> None:
        fn = _load_inspect_fn(tmp_path, _FULL_CANDIDATE)
        result = check_request_surface_coverage_behavioral(fn)
        assert result.name == "request_surface_coverage_behavioral"


# ===========================================================================
# D. Mutation-region integrity
# ===========================================================================

class TestMutationRegionIntegrity:
    """check_mutation_region_integrity rejects missing/ambiguous/changed markers."""

    def test_valid_markers_pass(self) -> None:
        result = check_mutation_region_integrity(_FULL_CANDIDATE)
        assert result.passed

    def test_missing_markers_rejected(self) -> None:
        result = check_mutation_region_integrity(_NO_MARKERS)
        assert not result.passed
        assert "mutation_region_missing" in result.rejection_reasons

    def test_missing_start_only(self) -> None:
        source = _FULL_CANDIDATE.replace(_MUTATION_START, "")
        result = check_mutation_region_integrity(source)
        assert not result.passed
        assert "mutation_region_missing" in result.rejection_reasons

    def test_missing_end_only(self) -> None:
        source = _FULL_CANDIDATE.replace(_MUTATION_END, "")
        result = check_mutation_region_integrity(source)
        assert not result.passed
        assert "mutation_region_missing" in result.rejection_reasons

    def test_duplicate_start_marker_ambiguous(self) -> None:
        source = _FULL_CANDIDATE.replace(
            _MUTATION_START, _MUTATION_START + "\n    " + _MUTATION_START
        )
        result = check_mutation_region_integrity(source)
        assert not result.passed
        assert "mutation_region_ambiguous" in result.rejection_reasons

    def test_end_before_start_boundary_violation(self) -> None:
        # Swap the markers so END appears before START
        swapped = _FULL_CANDIDATE.replace(_MUTATION_START, "__TMP__")
        swapped = swapped.replace(_MUTATION_END, _MUTATION_START)
        swapped = swapped.replace("__TMP__", _MUTATION_END)
        result = check_mutation_region_integrity(swapped)
        assert not result.passed
        assert "mutation_region_boundary_violation" in result.rejection_reasons

    def test_outside_region_changed_detected(self) -> None:
        result = check_mutation_region_integrity(_OUTSIDE_CHANGED, _BASE_SOURCE_FOR_BOUNDARY)
        assert not result.passed
        assert "outside_mutation_region_changed" in result.rejection_reasons

    def test_valid_replacement_with_base_passes(self) -> None:
        # Replace only the mutation region content — outside unchanged
        new = _BASE_SOURCE_FOR_BOUNDARY.replace(
            "    surface = request.body.lower()",
            "    surface = request.body.lower() + \" extra\"",
        )
        result = check_mutation_region_integrity(new, _BASE_SOURCE_FOR_BOUNDARY)
        assert result.passed

    def test_result_name_correct(self) -> None:
        result = check_mutation_region_integrity(_FULL_CANDIDATE)
        assert result.name == "mutation_region_integrity"

    def test_actual_detector_passes(self) -> None:
        """Current core/detector.py must pass mutation region integrity check."""
        detector = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        result = check_mutation_region_integrity(detector)
        assert result.passed


# ===========================================================================
# E. Candidate hash consistency
# ===========================================================================

class TestCandidateHashConsistency:
    """check_candidate_hash_consistency rejects mismatched hashes."""

    def test_correct_hash_passes(self, tmp_path: Path) -> None:
        p = tmp_path / "c.py"
        p.write_text("content", encoding="utf-8")
        actual = hashlib.sha256(b"content").hexdigest()
        result = check_candidate_hash_consistency(p, actual)
        assert result.passed

    def test_wrong_hash_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "c.py"
        p.write_text("content", encoding="utf-8")
        result = check_candidate_hash_consistency(p, "a" * 64)
        assert not result.passed
        assert "candidate_hash_mismatch" in result.rejection_reasons

    def test_none_hash_passes(self, tmp_path: Path) -> None:
        p = tmp_path / "c.py"
        p.write_text("content", encoding="utf-8")
        result = check_candidate_hash_consistency(p, None)
        assert result.passed
        assert result.details["reported_hash"] is None

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.py"
        result = check_candidate_hash_consistency(p, None)
        assert not result.passed
        assert "candidate_hash_mismatch" in result.rejection_reasons

    def test_details_include_actual_hash(self, tmp_path: Path) -> None:
        p = tmp_path / "c.py"
        p.write_text("hello", encoding="utf-8")
        result = check_candidate_hash_consistency(p, None)
        assert "actual_hash" in result.details
        assert len(result.details["actual_hash"]) == 64

    def test_hash_is_sha256_hex(self, tmp_path: Path) -> None:
        p = tmp_path / "c.py"
        p.write_text("hello", encoding="utf-8")
        expected = hashlib.sha256("hello".encode("utf-8")).hexdigest()
        result = check_candidate_hash_consistency(p, expected)
        assert result.passed


# ===========================================================================
# F. run_candidate_contract_checks — combined runner
# ===========================================================================

class TestRunCandidateContractChecks:
    """Combined runner produces consistent structured output."""

    def _write(self, tmp_path: Path, source: str) -> Path:
        p = tmp_path / "candidate.py"
        p.write_text(source, encoding="utf-8")
        return p

    def test_full_candidate_passes(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_candidate_contract_checks(p)
        assert result["passed"]
        assert result["rejection_reasons"] == []

    def test_result_has_contract_checks_list(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_candidate_contract_checks(p)
        assert isinstance(result["contract_checks"], list)
        assert len(result["contract_checks"]) > 0

    def test_result_has_candidate_hash(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_candidate_contract_checks(p)
        assert result["candidate_hash"] is not None
        assert len(result["candidate_hash"]) == 64

    def test_missing_indicator_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _MISSING_SQLI)
        result = run_candidate_contract_checks(p)
        assert not result["passed"]
        assert any(
            "missing_baseline_symbolic_indicator:sqli_indicator" in r
            for r in result["rejection_reasons"]
        )

    def test_body_path_only_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _BODY_PATH_ONLY)
        result = run_candidate_contract_checks(p)
        assert not result["passed"]
        assert any("missing_request_surface" in r for r in result["rejection_reasons"])

    def test_missing_markers_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _NO_MARKERS)
        result = run_candidate_contract_checks(p)
        assert not result["passed"]
        assert "mutation_region_missing" in result["rejection_reasons"]

    def test_outside_region_changed_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _OUTSIDE_CHANGED)
        result = run_candidate_contract_checks(p, base_source=_BASE_SOURCE_FOR_BOUNDARY)
        assert not result["passed"]
        assert "outside_mutation_region_changed" in result["rejection_reasons"]

    def test_hash_mismatch_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_candidate_contract_checks(p, reported_hash="b" * 64)
        assert not result["passed"]
        assert "candidate_hash_mismatch" in result["rejection_reasons"]

    def test_nonexistent_candidate_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "ghost.py"
        result = run_candidate_contract_checks(p)
        assert not result["passed"]
        assert result["candidate_hash"] is None

    def test_contract_checks_items_have_required_keys(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_candidate_contract_checks(p)
        for check in result["contract_checks"]:
            assert "name" in check
            assert "passed" in check
            assert "details" in check
            assert "rejection_reasons" in check

    def test_actual_detector_passes(self) -> None:
        """Current core/detector.py passes all combined contract checks."""
        detector_path = _PROJECT_ROOT / "core" / "detector.py"
        result = run_candidate_contract_checks(detector_path)
        assert result["passed"], f"Detector fails: {result['rejection_reasons']}"

    def test_query_values_only_rejected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _QUERY_VALUES_ONLY)
        result = run_candidate_contract_checks(p)
        assert not result["passed"]
        assert any("missing_request_surface" in r for r in result["rejection_reasons"])


# ===========================================================================
# G. Adoption gate: generation 3 must NOT pass against previous_best=947.66
# ===========================================================================

class TestAdoptionGateGeneration3:
    """The adoption gate rejects a score equal to previous_best."""

    def test_score_equal_to_previous_best_fails_gate(self) -> None:
        """Score=947.66 against previous_best=947.66 must not pass (gate requires strictly >)."""
        from core.fitness import _adoption_gate

        gate_passed, reasons = _adoption_gate(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=True,
            timed_out=False,
            exception_count=0,
            regression_pass_rate=1.0,
            fp_rate=0.0,
            avg_latency_ms=0.0,
            score=947.66,
            previous_best_score=947.66,
            baseline_mode=False,
            max_fp_rate=0.05,
            min_regression_pass_rate=1.0,
            max_avg_latency_ms=100.0,
        )

        assert not gate_passed, (
            "Score equal to previous_best must NOT pass the adoption gate"
        )
        assert any("947.66" in r for r in reasons), (
            f"Rejection reason must reference the score; got: {reasons}"
        )

    def test_score_below_previous_best_fails_gate(self) -> None:
        """Score < previous_best must not pass the adoption gate."""
        from core.fitness import _adoption_gate

        gate_passed, _ = _adoption_gate(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=True,
            timed_out=False,
            exception_count=0,
            regression_pass_rate=1.0,
            fp_rate=0.0,
            avg_latency_ms=0.0,
            score=947.65,
            previous_best_score=947.66,
            baseline_mode=False,
            max_fp_rate=0.05,
            min_regression_pass_rate=1.0,
            max_avg_latency_ms=100.0,
        )
        assert not gate_passed

    def test_score_strictly_above_passes_gate(self) -> None:
        """Score strictly > previous_best with all other conditions met must pass."""
        from core.fitness import _adoption_gate

        gate_passed, reasons = _adoption_gate(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=True,
            timed_out=False,
            exception_count=0,
            regression_pass_rate=1.0,
            fp_rate=0.0,
            avg_latency_ms=0.0,
            score=948.00,
            previous_best_score=947.66,
            baseline_mode=False,
            max_fp_rate=0.05,
            min_regression_pass_rate=1.0,
            max_avg_latency_ms=100.0,
        )
        assert gate_passed, f"Score above previous_best must pass: {reasons}"

    def test_current_detector_passes_contract_checks_except_adoption_gate(self) -> None:
        """Current detector passes static contract checks (it's a valid generation 3 file)."""
        detector_path = _PROJECT_ROOT / "core" / "detector.py"
        result = run_candidate_contract_checks(detector_path)
        assert result["passed"], (
            f"Current detector must pass static contract checks: {result['rejection_reasons']}"
        )


# ===========================================================================
# H. evaluate_candidate report includes contract_checks
# ===========================================================================

class TestEvaluateCandidateContractChecksInReport:
    """evaluate_candidate report must include contract_checks field."""

    def _write_candidate(self, tmp_path: Path) -> Path:
        p = tmp_path / "candidate.py"
        p.write_text(_FULL_CANDIDATE, encoding="utf-8")
        return p

    def test_report_has_contract_checks_on_ast_failure(self, tmp_path: Path) -> None:
        """Report must include contract_checks (empty list) on AST validation failure."""
        from scripts.evaluate_candidate import evaluate_candidate

        candidate = self._write_candidate(tmp_path)
        report_path = tmp_path / "report.json"

        with patch(
            "scripts.evaluate_candidate.validate",
            return_value={"valid": False, "violations": ["forbidden import"]},
        ):
            evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        assert "contract_checks" in report
        assert isinstance(report["contract_checks"], list)

    def test_report_has_contract_checks_on_contract_failure(self, tmp_path: Path) -> None:
        """Report must include contract_checks when contract check fails."""
        from scripts.evaluate_candidate import evaluate_candidate

        # Candidate missing sqli_indicator
        p = tmp_path / "candidate.py"
        p.write_text(_MISSING_SQLI, encoding="utf-8")
        report_path = tmp_path / "report.json"

        with patch(
            "scripts.evaluate_candidate.validate",
            return_value={"valid": True, "violations": []},
        ):
            result = evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        assert not result["passed_adoption_gate"]
        assert result.get("is_tool_failure") is False  # contract failure is not a tool failure
        report = json.loads(report_path.read_text())
        assert "contract_checks" in report
        checks = report["contract_checks"]
        assert isinstance(checks, list)
        assert len(checks) > 0
        names = {c["name"] for c in checks}
        assert "baseline_symbolic_indicators" in names

    def test_report_contract_checks_have_pass_fail_info(self, tmp_path: Path) -> None:
        """Each contract check in the report must have name, passed, rejection_reasons."""
        from scripts.evaluate_candidate import evaluate_candidate

        p = tmp_path / "candidate.py"
        p.write_text(_MISSING_SQLI, encoding="utf-8")
        report_path = tmp_path / "report.json"

        with patch(
            "scripts.evaluate_candidate.validate",
            return_value={"valid": True, "violations": []},
        ):
            evaluate_candidate(p, timeout_seconds=5, report_path=report_path)

        report = json.loads(report_path.read_text())
        for check in report["contract_checks"]:
            assert "name" in check
            assert "passed" in check
            assert "rejection_reasons" in check


# ===========================================================================
# I. Tightened static request-surface coverage: bare access / .get() / str()
#    do NOT count; .items() or both .keys() and .values() are required
# ===========================================================================

# Candidate using .get() on query and headers (not .items()/.keys()/.values())
_QUERY_GET_ONLY = """\
\"\"\"Candidate accessing query and header values via .get().\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = []
    surface_list.append(request.method.lower())
    surface_list.append(request.path.lower())
    surface_list.append(str(request.query.get("x", "")).lower())
    surface_list.append(str(request.headers.get("x", "")).lower())
    surface_list.append(request.body.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate using str(request.query) and str(request.headers)
_STR_QUERY_HEADERS = """\
\"\"\"Candidate stringifying query and headers objects.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface = (request.method.lower() + " " + request.path.lower() + " "
               + str(request.query).lower() + " " + str(request.headers).lower()
               + " " + request.body.lower())
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate assigning bare request.query / request.headers to local vars
_BARE_QUERY_HEADERS = """\
\"\"\"Candidate assigning query and headers to local variables without iteration.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    q = request.query
    h = request.headers
    surface = (request.method.lower() + " " + request.path.lower() + " "
               + str(q).lower() + " " + str(h).lower() + " " + request.body.lower())
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate iterating only .keys() on query and headers (no values)
_QUERY_KEYS_ONLY_CANDIDATE = """\
\"\"\"Candidate iterating only keys of query and headers.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k in request.query.keys():
        surface_list.append(k.lower())
    for k in request.headers.keys():
        surface_list.append(k.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate using both .keys() and .values() (no .items()) — should pass
_BOTH_KEYS_AND_VALUES = """\
\"\"\"Candidate iterating query and header keys and values separately.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k in request.query.keys():
        surface_list.append(k.lower())
    for v in request.query.values():
        surface_list.append(v.lower())
    for k in request.headers.keys():
        surface_list.append(k.lower())
    for v in request.headers.values():
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""


class TestRequestSurfaceCoverageTightened:
    """Tightened static check: .get()/bare/str() do not satisfy coverage."""

    def test_query_get_rejected_missing_query_keys(self) -> None:
        result = check_request_surface_coverage(_QUERY_GET_ONLY)
        assert not result.passed
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_query_get_rejected_missing_query_values(self) -> None:
        result = check_request_surface_coverage(_QUERY_GET_ONLY)
        assert "missing_request_surface:query_values" in result.rejection_reasons

    def test_headers_get_rejected_missing_header_keys(self) -> None:
        result = check_request_surface_coverage(_QUERY_GET_ONLY)
        assert "missing_request_surface:header_keys" in result.rejection_reasons

    def test_headers_get_rejected_missing_header_values(self) -> None:
        result = check_request_surface_coverage(_QUERY_GET_ONLY)
        assert "missing_request_surface:header_values" in result.rejection_reasons

    def test_str_query_rejected_missing_query_keys(self) -> None:
        result = check_request_surface_coverage(_STR_QUERY_HEADERS)
        assert not result.passed
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_str_query_rejected_missing_query_values(self) -> None:
        result = check_request_surface_coverage(_STR_QUERY_HEADERS)
        assert "missing_request_surface:query_values" in result.rejection_reasons

    def test_str_headers_rejected_missing_header_keys(self) -> None:
        result = check_request_surface_coverage(_STR_QUERY_HEADERS)
        assert "missing_request_surface:header_keys" in result.rejection_reasons

    def test_str_headers_rejected_missing_header_values(self) -> None:
        result = check_request_surface_coverage(_STR_QUERY_HEADERS)
        assert "missing_request_surface:header_values" in result.rejection_reasons

    def test_bare_query_rejected_missing_query_keys(self) -> None:
        result = check_request_surface_coverage(_BARE_QUERY_HEADERS)
        assert not result.passed
        assert "missing_request_surface:query_keys" in result.rejection_reasons

    def test_bare_query_rejected_missing_query_values(self) -> None:
        result = check_request_surface_coverage(_BARE_QUERY_HEADERS)
        assert "missing_request_surface:query_values" in result.rejection_reasons

    def test_bare_headers_rejected_missing_header_keys(self) -> None:
        result = check_request_surface_coverage(_BARE_QUERY_HEADERS)
        assert "missing_request_surface:header_keys" in result.rejection_reasons

    def test_bare_headers_rejected_missing_header_values(self) -> None:
        result = check_request_surface_coverage(_BARE_QUERY_HEADERS)
        assert "missing_request_surface:header_values" in result.rejection_reasons

    def test_keys_only_rejected_missing_query_values(self) -> None:
        result = check_request_surface_coverage(_QUERY_KEYS_ONLY_CANDIDATE)
        assert not result.passed
        assert "missing_request_surface:query_values" in result.rejection_reasons

    def test_keys_only_rejected_missing_header_values(self) -> None:
        result = check_request_surface_coverage(_QUERY_KEYS_ONLY_CANDIDATE)
        assert "missing_request_surface:header_values" in result.rejection_reasons

    def test_keys_only_does_not_flag_missing_keys(self) -> None:
        result = check_request_surface_coverage(_QUERY_KEYS_ONLY_CANDIDATE)
        assert "missing_request_surface:query_keys" not in result.rejection_reasons
        assert "missing_request_surface:header_keys" not in result.rejection_reasons

    def test_both_keys_and_values_passes_query_coverage(self) -> None:
        result = check_request_surface_coverage(_BOTH_KEYS_AND_VALUES)
        assert "missing_request_surface:query_keys" not in result.rejection_reasons
        assert "missing_request_surface:query_values" not in result.rejection_reasons

    def test_both_keys_and_values_passes_header_coverage(self) -> None:
        result = check_request_surface_coverage(_BOTH_KEYS_AND_VALUES)
        assert "missing_request_surface:header_keys" not in result.rejection_reasons
        assert "missing_request_surface:header_values" not in result.rejection_reasons

    def test_both_keys_and_values_full_pass(self) -> None:
        result = check_request_surface_coverage(_BOTH_KEYS_AND_VALUES)
        assert result.passed, f"Unexpected failures: {result.rejection_reasons}"

    def test_actual_detector_still_passes(self) -> None:
        """Generation 3 core/detector.py must still pass the tightened check."""
        detector = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
        result = check_request_surface_coverage(detector)
        assert result.passed, f"Detector fails tightened check: {result.rejection_reasons}"


# ===========================================================================
# J. Behavioral request-surface coverage — subprocess
# ===========================================================================

# All surface accesses are in an unreachable if False block.
# Static AST check passes (it sees all accesses); runtime only detects body.
_UNREACHABLE_SURFACE = """\
\"\"\"Candidate hiding all surface accesses in unreachable if False block.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    if False:
        surface_list = []
        surface_list.append(request.method.lower())
        surface_list.append(request.path.lower())
        for k, v in request.query.items():
            surface_list.append(k.lower())
            surface_list.append(v.lower())
        for k, v in request.headers.items():
            surface_list.append(k.lower())
            surface_list.append(v.lower())
        surface_list.append(request.body.lower())
    surface = request.body.lower()
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Headers in unreachable code; runtime inspects everything except headers.
_HEADER_BLIND_SPOT_UNREACHABLE = """\
\"\"\"Candidate with header access only in unreachable code.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    if False:
        for k, v in request.headers.items():
            pass
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Method in unreachable code; runtime inspects everything except method.
_METHOD_BLIND_SPOT_UNREACHABLE = """\
\"\"\"Candidate with method access only in unreachable code.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    if False:
        _ = request.method.lower()
    surface_list = [request.path.lower(), request.body.lower()]
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Query in unreachable code; runtime inspects everything except query.
_QUERY_BLIND_SPOT_UNREACHABLE = """\
\"\"\"Candidate with query access only in unreachable code.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    tokens = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    if False:
        for k, v in request.query.items():
            pass
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    for token in tokens:
        if token in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(token,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""


class TestBehavioralSurfaceContractSubprocess:
    """Behavioral subprocess check catches runtime blind spots that static AST misses."""

    def _write(self, tmp_path: Path, source: str) -> Path:
        p = tmp_path / "candidate.py"
        p.write_text(source, encoding="utf-8")
        return p

    # -- Static passes / behavioral fails (regression tests) --

    def test_unreachable_passes_static_check(self) -> None:
        """Unreachable-code candidate must pass the static AST check."""
        result = check_request_surface_coverage(_UNREACHABLE_SURFACE)
        assert result.passed, (
            "Static check should not detect unreachable code; behavioral check must catch it"
        )

    def test_unreachable_fails_behavioral_check(self, tmp_path: Path) -> None:
        """Unreachable-code candidate must fail behavioral subprocess check."""
        p = self._write(tmp_path, _UNREACHABLE_SURFACE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]
        assert not result["harness_error"]

    def test_unreachable_missing_method(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _UNREACHABLE_SURFACE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:method" in result["rejection_reasons"]

    def test_unreachable_missing_query_keys(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _UNREACHABLE_SURFACE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:query_keys" in result["rejection_reasons"]

    def test_unreachable_missing_header_keys(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _UNREACHABLE_SURFACE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:header_keys" in result["rejection_reasons"]

    def test_unreachable_body_still_detected(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _UNREACHABLE_SURFACE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        # body is reachable runtime code; all 5 indicators must be detected there
        for ind in BASELINE_SYMBOLIC_INDICATORS:
            assert result["field_results"][ind]["body"] is True

    # -- Header blind spot --

    def test_header_blind_spot_passes_static(self) -> None:
        result = check_request_surface_coverage(_HEADER_BLIND_SPOT_UNREACHABLE)
        assert result.passed, "Static check should pass (headers.items() visible in AST)"

    def test_header_blind_spot_fails_behavioral(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _HEADER_BLIND_SPOT_UNREACHABLE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]

    def test_header_blind_spot_missing_header_keys(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _HEADER_BLIND_SPOT_UNREACHABLE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:header_keys" in result["rejection_reasons"]

    def test_header_blind_spot_missing_header_values(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _HEADER_BLIND_SPOT_UNREACHABLE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:header_values" in result["rejection_reasons"]

    # -- Method blind spot --

    def test_method_blind_spot_fails_behavioral(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _METHOD_BLIND_SPOT_UNREACHABLE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]
        assert "missing_request_surface:method" in result["rejection_reasons"]

    # -- Query blind spot --

    def test_query_blind_spot_fails_behavioral(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _QUERY_BLIND_SPOT_UNREACHABLE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]
        assert "missing_request_surface:query_keys" in result["rejection_reasons"]
        assert "missing_request_surface:query_values" in result["rejection_reasons"]

    # -- Full candidate passes --

    def test_full_candidate_passes_behavioral(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert result["passed"]
        assert not result["harness_error"]

    def test_actual_detector_passes_behavioral(self) -> None:
        detector_path = _PROJECT_ROOT / "core" / "detector.py"
        result = run_behavioral_surface_check_subprocess(detector_path, timeout_seconds=30)
        assert result["passed"], f"Detector fails behavioral check: {result['rejection_reasons']}"

    # -- Harness safety --

    def test_subprocess_isolation_sys_exit_does_not_crash_parent(self, tmp_path: Path) -> None:
        """Candidate calling sys.exit() must not crash the parent process."""
        p = tmp_path / "candidate.py"
        p.write_text("import sys\nsys.exit(42)\n", encoding="utf-8")
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=10)
        # subprocess exits non-zero → harness_error; parent survives
        assert result["harness_error"]

    def test_broken_candidate_returns_harness_error_false(self, tmp_path: Path) -> None:
        """Candidate that raises during inspect_request is a soft reject, not harness error."""
        bad = """\
from core.types import Request, DetectionResult
def inspect_request(request: Request) -> DetectionResult:
    raise RuntimeError("candidate error")
"""
        p = self._write(tmp_path, bad)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=10)
        # Candidate raises during field tests — all fields False — soft reject
        assert not result["passed"]
        assert not result["harness_error"]

    def test_result_dict_has_required_keys(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _FULL_CANDIDATE)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        for key in ("passed", "field_results", "missing", "rejection_reasons", "harness_error"):
            assert key in result, f"Missing key: {key}"


# ===========================================================================
# K. Behavioral indicator coverage — P2 regression tests
#    Verifies all 5 baseline indicators are exercised at runtime (5 × 7 = 35)
# ===========================================================================

# Candidate that has all 5 indicator names present statically (in a comment within
# the mutation region) but only blocks path_traversal_indicator at runtime.
# Static baseline check passes; behavioral check must fail for the other 4.
_PATH_TRAVERSAL_ONLY_RUNTIME = """\
\"\"\"Only detects path_traversal_indicator at runtime; others in dead comment only.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    # Neutralized static names for baseline check:
    # script_injection_indicator sqli_indicator command_delimiter_indicator encoded_traversal_indicator
    surface_list = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k, v in request.query.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    for k, v in request.headers.items():
        surface_list.append(k.lower())
        surface_list.append(v.lower())
    surface = " ".join(surface_list)
    if "path_traversal_indicator" in surface:
        return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=("path_traversal_indicator",))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""

# Candidate that detects all 5 indicators on all surfaces EXCEPT sqli_indicator
# in header values — all other 34/35 cases pass.
_SQLI_HEADER_VALUES_BLIND = """\
\"\"\"All indicators on all surfaces except sqli_indicator in header values.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    ALL_TOKENS = ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    NON_SQLI = ("path_traversal_indicator", "script_injection_indicator", "command_delimiter_indicator", "encoded_traversal_indicator")
    parts = [request.method.lower(), request.path.lower(), request.body.lower()]
    for k, v in request.query.items():
        parts.append(k.lower())
        parts.append(v.lower())
    for k, v in request.headers.items():
        parts.append(k.lower())
    surface = " ".join(parts)
    for tok in ALL_TOKENS:
        if tok in surface:
            return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(tok,))
    for hv in request.headers.values():
        hv_lower = hv.lower()
        for tok in NON_SQLI:
            if tok in hv_lower:
                return DetectionResult(blocked=True, reason="match", confidence=0.9, matched_signals=(tok,))
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=())
    # === MUTATION_END ===
"""


class TestBehavioralIndicatorCoverage:
    """P2 regression tests: behavioral check exercises all 5 baseline indicators."""

    def _write(self, tmp_path: Path, source: str) -> Path:
        p = tmp_path / "candidate.py"
        p.write_text(source, encoding="utf-8")
        return p

    # --- Test A: path_traversal_indicator only at runtime ---

    def test_path_traversal_only_passes_static_baseline(self) -> None:
        """Static baseline check must pass (all 5 names present in source text)."""
        result = check_baseline_symbolic_indicators(_PATH_TRAVERSAL_ONLY_RUNTIME)
        assert result.passed, (
            "Static baseline check must pass when all 5 names appear as dead comments"
        )

    def test_path_traversal_only_passes_static_surface(self) -> None:
        """Static surface check must pass (uses .items() on query and headers)."""
        result = check_request_surface_coverage(_PATH_TRAVERSAL_ONLY_RUNTIME)
        assert result.passed, f"Static surface check must pass: {result.rejection_reasons}"

    def test_path_traversal_only_fails_behavioral(self, tmp_path: Path) -> None:
        """Candidate that only detects path_traversal_indicator must fail behavioral check."""
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]
        assert not result["harness_error"]

    def test_path_traversal_only_missing_sqli_runtime(self, tmp_path: Path) -> None:
        """sqli_indicator is never detected — must produce indicator-level rejection reason."""
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_baseline_symbolic_indicator_runtime:sqli_indicator" in result["rejection_reasons"]

    def test_path_traversal_only_missing_script_injection_runtime(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_baseline_symbolic_indicator_runtime:script_injection_indicator" in result["rejection_reasons"]

    def test_path_traversal_only_path_traversal_not_missing(self, tmp_path: Path) -> None:
        """path_traversal_indicator IS detected on all surfaces — no runtime missing reason."""
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_baseline_symbolic_indicator_runtime:path_traversal_indicator" not in result["rejection_reasons"]

    def test_path_traversal_only_field_results_nested(self, tmp_path: Path) -> None:
        """field_results must be a nested {indicator: {surface: bool}} dict."""
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert isinstance(result["field_results"], dict)
        for ind in BASELINE_SYMBOLIC_INDICATORS:
            assert ind in result["field_results"], f"Indicator {ind!r} missing from field_results"
            for surf in REQUEST_SURFACE_FIELDS:
                assert surf in result["field_results"][ind], f"Surface {surf!r} missing for {ind!r}"

    def test_path_traversal_only_missing_is_list_of_dicts(self, tmp_path: Path) -> None:
        """missing must be a list of {'indicator': ..., 'surface': ...} dicts."""
        p = self._write(tmp_path, _PATH_TRAVERSAL_ONLY_RUNTIME)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert isinstance(result["missing"], list)
        for item in result["missing"]:
            assert "indicator" in item
            assert "surface" in item

    # --- Test B: sqli_indicator blind on header_values only ---

    def test_sqli_header_values_blind_fails_behavioral(self, tmp_path: Path) -> None:
        """Candidate missing sqli on header_values must fail behavioral check."""
        p = self._write(tmp_path, _SQLI_HEADER_VALUES_BLIND)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert not result["passed"]
        assert not result["harness_error"]

    def test_sqli_header_values_blind_indicator_surface_reason(self, tmp_path: Path) -> None:
        """Failure reason must include missing_request_surface:header_values:sqli_indicator."""
        p = self._write(tmp_path, _SQLI_HEADER_VALUES_BLIND)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_request_surface:header_values:sqli_indicator" in result["rejection_reasons"]

    def test_sqli_header_values_blind_no_other_surface_missing(self, tmp_path: Path) -> None:
        """Only header_values:sqli must be missing — all other 34 cases pass."""
        p = self._write(tmp_path, _SQLI_HEADER_VALUES_BLIND)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        # Exactly one (indicator, surface) pair missing
        assert result["missing"] == [{"indicator": "sqli_indicator", "surface": "header_values"}]

    def test_sqli_header_values_blind_no_indicator_level_reason(self, tmp_path: Path) -> None:
        """sqli_indicator IS detected on other surfaces — no indicator-level runtime reason."""
        p = self._write(tmp_path, _SQLI_HEADER_VALUES_BLIND)
        result = run_behavioral_surface_check_subprocess(p, timeout_seconds=30)
        assert "missing_baseline_symbolic_indicator_runtime:sqli_indicator" not in result["rejection_reasons"]

    # --- Test C: generation 3 detector passes all 35 cases ---

    def test_actual_detector_passes_all_35_cases(self) -> None:
        """core/detector.py must pass all 5 indicators × 7 surfaces = 35 behavioral cases."""
        result = run_behavioral_surface_check_subprocess(
            _PROJECT_ROOT / "core" / "detector.py", timeout_seconds=30
        )
        assert result["passed"], (
            f"Detector fails behavioral indicator matrix: {result['rejection_reasons']}"
        )
        assert not result["harness_error"]
        assert result["missing"] == []

    def test_actual_detector_all_indicator_surface_true(self) -> None:
        """Every indicator/surface cell in field_results must be True for the real detector."""
        result = run_behavioral_surface_check_subprocess(
            _PROJECT_ROOT / "core" / "detector.py", timeout_seconds=30
        )
        for ind in BASELINE_SYMBOLIC_INDICATORS:
            for surf in REQUEST_SURFACE_FIELDS:
                assert result["field_results"][ind][surf] is True, (
                    f"Detector fails for indicator={ind!r} surface={surf!r}"
                )


# ===========================================================================
# I. Behavioral benign-control checks
# ===========================================================================

_ALWAYS_BLOCKING_BENIGN = """\
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    return DetectionResult(blocked=True, reason="always", confidence=1.0, matched_signals=())
"""

_MATCHED_SIGNAL_BENIGN = """\
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    return DetectionResult(blocked=False, reason="clean", confidence=0.0, matched_signals=("benign_signal",))
"""

_EXCEPTION_BENIGN = """\
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    raise RuntimeError("synthetic benign failure")
"""

_MALFORMED_BENIGN = """\
from core.types import Request, DetectionResult

def inspect_request(request: Request):
    return {"blocked": False, "matched_signals": []}
"""


def _write_benign_candidate(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "benign_candidate.py"
    p.write_text(source, encoding="utf-8")
    return p


class TestBehavioralBenignControlCheck:
    """Benign synthetic requests must not be blocked or matched."""

    def test_generation_3_detector_passes_benign_controls(self) -> None:
        result = run_behavioral_benign_control_check_subprocess(_PROJECT_ROOT / "core" / "detector.py")
        assert result["passed"] is True
        assert result["failing_cases"] == []
        assert result["rejection_reasons"] == []

    def test_always_blocking_candidate_fails(self, tmp_path: Path) -> None:
        result = run_behavioral_benign_control_check_subprocess(_write_benign_candidate(tmp_path, _ALWAYS_BLOCKING_BENIGN))
        assert result["passed"] is False
        assert "benign_control_blocked" in result["rejection_reasons"]

    def test_matched_signal_on_benign_candidate_fails(self, tmp_path: Path) -> None:
        result = run_behavioral_benign_control_check_subprocess(_write_benign_candidate(tmp_path, _MATCHED_SIGNAL_BENIGN))
        assert result["passed"] is False
        assert "benign_control_matched_signal" in result["rejection_reasons"]

    def test_exception_on_benign_candidate_fails(self, tmp_path: Path) -> None:
        result = run_behavioral_benign_control_check_subprocess(_write_benign_candidate(tmp_path, _EXCEPTION_BENIGN))
        assert result["passed"] is False
        assert "benign_control_exception" in result["rejection_reasons"]

    def test_malformed_runtime_result_fails(self, tmp_path: Path) -> None:
        result = run_behavioral_benign_control_check_subprocess(_write_benign_candidate(tmp_path, _MALFORMED_BENIGN))
        assert result["passed"] is False
        assert "benign_control_malformed_result" in result["rejection_reasons"]

    def test_all_benign_surfaces_are_exercised(self) -> None:
        result = run_behavioral_benign_control_check_subprocess(_PROJECT_ROOT / "core" / "detector.py")
        assert set(result["case_results"]) == {*REQUEST_SURFACE_FIELDS, "combined"}

    def test_benign_strings_only_are_embedded_in_harness(self) -> None:
        from scripts import candidate_contract
        harness = candidate_contract._BEHAVIORAL_BENIGN_CONTROL_SCRIPT
        for token in [
            "BENIGN_METHOD", "/safe/path", "benign_query_key", "benign_query_value",
            "benign_header_key", "benign_header_value", "benign_body_text",
        ]:
            assert token in harness
        for indicator in BASELINE_SYMBOLIC_INDICATORS:
            assert indicator not in harness


def _write_candidate_for_docker_test(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "candidate.py"
    p.write_text(source, encoding="utf-8")
    return p

# ---------------------------------------------------------------------------
# K. Docker sandbox runner construction
# ---------------------------------------------------------------------------

class TestCandidateRuntimeDockerSandbox:
    def test_candidate_runtime_docker_command_has_required_hardening_flags(self, tmp_path: Path) -> None:
        candidate = _write_candidate_for_docker_test(tmp_path, _FULL_CANDIDATE)
        cmd = candidate_contract.build_candidate_runtime_docker_command(
            candidate_path=candidate,
            command=["python", "-c", "print('ok')", candidate_contract.CONTAINER_WORKSPACE, candidate_contract.CONTAINER_CANDIDATE],
            project_root=_PROJECT_ROOT,
        )
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
        assert f"{_PROJECT_ROOT}:/workspace:ro" in mounts
        assert f"{candidate.resolve()}:/candidate/candidate_detector.py:ro" in mounts

    def test_docker_available_is_strict_false_on_nonzero_json_stdout(self) -> None:
        fake = subprocess.CompletedProcess(
            args=["docker"],
            returncode=1,
            stdout='{"passed_adoption_gate": true}',
            stderr="simulated docker failure",
        )
        with patch("scripts.candidate_contract.subprocess.run", return_value=fake):
            assert candidate_contract.docker_available() is False

    def test_behavioral_surface_uses_docker_runner(self, tmp_path: Path, monkeypatch) -> None:
        candidate = _write_candidate_for_docker_test(tmp_path, _FULL_CANDIDATE)
        calls = []

        def _fake_runner(*, candidate_path, command, timeout_seconds, project_root=None):
            calls.append({"candidate_path": candidate_path, "command": command, "timeout_seconds": timeout_seconds})
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps({
                    "success": True,
                    "field_results": {i: {s: True for s in REQUEST_SURFACE_FIELDS} for i in BASELINE_SYMBOLIC_INDICATORS},
                    "missing": [],
                }),
                stderr="",
            )

        monkeypatch.setattr(candidate_contract, "run_candidate_runtime_in_docker", _fake_runner)
        result = run_behavioral_surface_check_subprocess(candidate, timeout_seconds=7)
        assert result["passed"] is True
        assert calls and calls[0]["candidate_path"] == candidate
        assert candidate_contract.CONTAINER_CANDIDATE in calls[0]["command"]

    def test_behavioral_benign_control_uses_docker_runner(self, tmp_path: Path, monkeypatch) -> None:
        candidate = _write_candidate_for_docker_test(tmp_path, _FULL_CANDIDATE)
        calls = []

        def _fake_runner(*, candidate_path, command, timeout_seconds, project_root=None):
            calls.append({"candidate_path": candidate_path, "command": command, "timeout_seconds": timeout_seconds})
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps({
                    "success": True,
                    "case_results": {},
                    "failing_cases": [],
                    "rejection_reasons": [],
                }),
                stderr="",
            )

        monkeypatch.setattr(candidate_contract, "run_candidate_runtime_in_docker", _fake_runner)
        result = run_behavioral_benign_control_check_subprocess(candidate, timeout_seconds=7)
        assert result["passed"] is True
        assert calls and calls[0]["candidate_path"] == candidate
        assert candidate_contract.CONTAINER_CANDIDATE in calls[0]["command"]
