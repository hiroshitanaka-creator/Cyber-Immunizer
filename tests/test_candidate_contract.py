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
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.candidate_contract import (
    BASELINE_SYMBOLIC_INDICATORS,
    REQUEST_SURFACE_FIELDS,
    ContractCheckResult,
    check_baseline_symbolic_indicators,
    check_candidate_hash_consistency,
    check_mutation_region_integrity,
    check_request_surface_coverage,
    check_request_surface_coverage_behavioral,
    run_candidate_contract_checks,
)

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
