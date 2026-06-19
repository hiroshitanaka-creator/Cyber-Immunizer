"""tests/test_adaptive_floor.py — Verify adaptive floor gate and tier loading.

Tests cover:
- _compute_tier_pass_rate: correct rate computation, None for absent tiers
- _adaptive_floor_gate: threshold enforcement, absent-tier bypass
- load_test_cases: optional holdout/counterfactual/drift loading
- FitnessReport: default adaptive floor fields
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.fitness import _adaptive_floor_gate, _compute_tier_pass_rate
from core.test_attacker import load_test_cases
from core.types import FitnessReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    *,
    kind: str,
    expected_blocked: bool,
    actual_blocked: bool,
    exception: str | None = None,
) -> dict:
    return {
        "id": "x",
        "kind": kind,
        "expected_blocked": expected_blocked,
        "actual_blocked": actual_blocked,
        "exception": exception,
        "latency_ms": 0.0,
    }


def _write_json(data: object) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    json.dump(data, tmp)
    tmp.flush()
    return Path(tmp.name)


def _holdout_record(id_: str, blocked: bool) -> dict:
    return {
        "id": id_,
        "kind": "holdout",
        "expected_blocked": blocked,
        "request": {
            "method": "GET",
            "path": f"/holdout/{id_}",
            "query": {},
            "headers": {},
            "body": "",
        },
    }


def _counterfactual_record(id_: str) -> dict:
    return {
        "id": id_,
        "kind": "counterfactual",
        "expected_blocked": False,
        "request": {
            "method": "GET",
            "path": f"/cf/{id_}",
            "query": {},
            "headers": {},
            "body": "",
        },
    }


def _drift_record(id_: str) -> dict:
    return {
        "id": id_,
        "kind": "drift",
        "expected_blocked": True,
        "request": {
            "method": "GET",
            "path": f"/drift/{id_}",
            "query": {},
            "headers": {},
            "body": "",
        },
    }


# ---------------------------------------------------------------------------
# Tests: _compute_tier_pass_rate
# ---------------------------------------------------------------------------

class TestComputeTierPassRate:
    def test_no_cases_returns_none(self):
        results = [_make_result(kind="benign", expected_blocked=False, actual_blocked=False)]
        assert _compute_tier_pass_rate(results, "holdout") is None

    def test_empty_results_returns_none(self):
        assert _compute_tier_pass_rate([], "holdout") is None

    def test_all_pass_returns_one(self):
        results = [
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),
            _make_result(kind="holdout", expected_blocked=False, actual_blocked=False),
        ]
        assert _compute_tier_pass_rate(results, "holdout") == 1.0

    def test_all_fail_returns_zero(self):
        results = [
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=False),
            _make_result(kind="holdout", expected_blocked=False, actual_blocked=True),
        ]
        assert _compute_tier_pass_rate(results, "holdout") == 0.0

    def test_mixed_returns_correct_rate(self):
        results = [
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),   # pass
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=False),  # fail
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),   # pass
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),   # pass
        ]
        rate = _compute_tier_pass_rate(results, "holdout")
        assert rate == pytest.approx(0.75)

    def test_exception_counts_as_failure(self):
        results = [
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),
            _make_result(
                kind="holdout",
                expected_blocked=True,
                actual_blocked=False,
                exception="RuntimeError",
            ),
        ]
        rate = _compute_tier_pass_rate(results, "holdout")
        assert rate == pytest.approx(0.5)

    def test_only_matching_kind_counted(self):
        results = [
            _make_result(kind="benign", expected_blocked=False, actual_blocked=True),  # benign FP
            _make_result(kind="holdout", expected_blocked=True, actual_blocked=True),  # holdout pass
        ]
        assert _compute_tier_pass_rate(results, "holdout") == 1.0
        assert _compute_tier_pass_rate(results, "benign") == 0.0

    def test_counterfactual_kind(self):
        results = [
            _make_result(kind="counterfactual", expected_blocked=False, actual_blocked=False),
        ]
        assert _compute_tier_pass_rate(results, "counterfactual") == 1.0

    def test_drift_kind(self):
        results = [
            _make_result(kind="drift", expected_blocked=True, actual_blocked=False),
        ]
        assert _compute_tier_pass_rate(results, "drift") == 0.0


# ---------------------------------------------------------------------------
# Tests: _adaptive_floor_gate
# ---------------------------------------------------------------------------

class TestAdaptiveFloorGate:
    _DEFAULTS = dict(
        min_holdout_pass_rate=0.5,
        min_counterfactual_pass_rate=0.5,
        min_drift_pass_rate=0.5,
    )

    def test_all_none_passes(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=None,
            counterfactual_rate=None,
            drift_rate=None,
            **self._DEFAULTS,
        )
        assert passed is True
        assert reasons == []

    def test_all_above_threshold_passes(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=0.8,
            counterfactual_rate=0.9,
            drift_rate=0.6,
            **self._DEFAULTS,
        )
        assert passed is True
        assert reasons == []

    def test_all_at_threshold_passes(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=0.5,
            counterfactual_rate=0.5,
            drift_rate=0.5,
            **self._DEFAULTS,
        )
        assert passed is True

    def test_holdout_below_threshold_fails(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=0.4,
            counterfactual_rate=None,
            drift_rate=None,
            **self._DEFAULTS,
        )
        assert passed is False
        assert any("holdout" in r for r in reasons)

    def test_counterfactual_below_threshold_fails(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=None,
            counterfactual_rate=0.3,
            drift_rate=None,
            **self._DEFAULTS,
        )
        assert passed is False
        assert any("counterfactual" in r for r in reasons)

    def test_drift_below_threshold_fails(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=None,
            counterfactual_rate=None,
            drift_rate=0.0,
            **self._DEFAULTS,
        )
        assert passed is False
        assert any("drift" in r for r in reasons)

    def test_all_below_threshold_produces_three_reasons(self):
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=0.1,
            counterfactual_rate=0.2,
            drift_rate=0.3,
            **self._DEFAULTS,
        )
        assert passed is False
        assert len(reasons) == 3

    def test_none_rate_skips_that_tier(self):
        # holdout absent (None) → not checked even if others fail
        passed, reasons = _adaptive_floor_gate(
            holdout_rate=None,
            counterfactual_rate=1.0,
            drift_rate=1.0,
            **self._DEFAULTS,
        )
        assert passed is True
        assert not any("holdout" in r for r in reasons)


# ---------------------------------------------------------------------------
# Tests: load_test_cases with adaptive tiers
# ---------------------------------------------------------------------------

class TestLoadTestCasesAdaptiveTiers:
    _DATA_DIR = Path(__file__).parent.parent / "data"

    def test_missing_holdout_file_skipped(self, tmp_path):
        """With require_adaptive_tiers=False, absent files are silently skipped."""
        cases = load_test_cases(
            benign_path=self._DATA_DIR / "benign_requests.json",
            attack_path=self._DATA_DIR / "attack_requests.json",
            regression_path=self._DATA_DIR / "regression_cases.json",
            holdout_path=tmp_path / "nonexistent_holdout.json",
            counterfactual_path=tmp_path / "nonexistent_cf.json",
            drift_path=tmp_path / "nonexistent_drift.json",
            require_adaptive_tiers=False,
        )
        assert all(c.kind in {"benign", "attack", "regression"} for c in cases)

    def test_missing_tier_raises_by_default(self, tmp_path):
        """Missing adaptive tier file raises ValueError when require_adaptive_tiers=True (the default)."""
        with pytest.raises(ValueError, match="Required adaptive tier file not found"):
            load_test_cases(
                benign_path=self._DATA_DIR / "benign_requests.json",
                attack_path=self._DATA_DIR / "attack_requests.json",
                regression_path=self._DATA_DIR / "regression_cases.json",
                holdout_path=tmp_path / "nonexistent_holdout.json",
                counterfactual_path=tmp_path / "nonexistent_cf.json",
                drift_path=tmp_path / "nonexistent_drift.json",
            )

    def test_holdout_cases_loaded_with_correct_kind(self, tmp_path):
        p = _write_json([
            _holdout_record("h-001", True),
            _holdout_record("h-002", False),
        ])
        cases = load_test_cases(
            benign_path=self._DATA_DIR / "benign_requests.json",
            attack_path=self._DATA_DIR / "attack_requests.json",
            regression_path=self._DATA_DIR / "regression_cases.json",
            holdout_path=p,
            counterfactual_path=tmp_path / "nonexistent_cf.json",
            drift_path=tmp_path / "nonexistent_drift.json",
            require_adaptive_tiers=False,
        )
        holdout_cases = [c for c in cases if c.kind == "holdout"]
        assert len(holdout_cases) == 2
        assert any(c.id == "h-001" and c.expected_blocked is True for c in holdout_cases)
        assert any(c.id == "h-002" and c.expected_blocked is False for c in holdout_cases)

    def test_counterfactual_cases_loaded_with_correct_kind(self, tmp_path):
        p = _write_json([_counterfactual_record("cf-t-001")])
        cases = load_test_cases(
            benign_path=self._DATA_DIR / "benign_requests.json",
            attack_path=self._DATA_DIR / "attack_requests.json",
            regression_path=self._DATA_DIR / "regression_cases.json",
            holdout_path=tmp_path / "nonexistent.json",
            counterfactual_path=p,
            drift_path=tmp_path / "nonexistent.json",
            require_adaptive_tiers=False,
        )
        cf_cases = [c for c in cases if c.kind == "counterfactual"]
        assert len(cf_cases) == 1
        assert cf_cases[0].id == "cf-t-001"
        assert cf_cases[0].expected_blocked is False

    def test_drift_cases_loaded_with_correct_kind(self, tmp_path):
        p = _write_json([_drift_record("dr-t-001")])
        cases = load_test_cases(
            benign_path=self._DATA_DIR / "benign_requests.json",
            attack_path=self._DATA_DIR / "attack_requests.json",
            regression_path=self._DATA_DIR / "regression_cases.json",
            holdout_path=tmp_path / "nonexistent.json",
            counterfactual_path=tmp_path / "nonexistent.json",
            drift_path=p,
            require_adaptive_tiers=False,
        )
        drift_cases = [c for c in cases if c.kind == "drift"]
        assert len(drift_cases) == 1
        assert drift_cases[0].id == "dr-t-001"
        assert drift_cases[0].expected_blocked is True

    def test_real_data_loads_all_tiers(self):
        """Real fixture files must load successfully for all 6 tiers."""
        cases = load_test_cases()
        kinds = {c.kind for c in cases}
        assert "benign" in kinds
        assert "attack" in kinds
        assert "holdout" in kinds
        assert "counterfactual" in kinds
        assert "drift" in kinds

    def test_real_holdout_file_has_cases(self):
        cases = load_test_cases()
        holdout = [c for c in cases if c.kind == "holdout"]
        assert len(holdout) >= 1

    def test_adaptive_tier_schema_violation_raises(self, tmp_path):
        """A holdout record with expected_blocked as string must be rejected."""
        bad = _holdout_record("bad-001", True)
        bad["expected_blocked"] = "true"  # string instead of bool
        p = _write_json([bad])
        with pytest.raises(ValueError, match="expected_blocked.*bool"):
            load_test_cases(
                benign_path=self._DATA_DIR / "benign_requests.json",
                attack_path=self._DATA_DIR / "attack_requests.json",
                regression_path=self._DATA_DIR / "regression_cases.json",
                holdout_path=p,
                counterfactual_path=tmp_path / "nonexistent.json",
                drift_path=tmp_path / "nonexistent.json",
                require_adaptive_tiers=False,
            )


# ---------------------------------------------------------------------------
# Tests: FitnessReport adaptive floor defaults
# ---------------------------------------------------------------------------

class TestFitnessReportAdaptiveFloorDefaults:
    def _make_report(self, **overrides) -> FitnessReport:
        base = dict(
            syntax_ok=True, ast_policy_ok=True, contract_ok=True,
            timed_out=False, exception_count=0,
            true_positive=0, false_positive=0, true_negative=0, false_negative=0,
            total_cases=0, tp_rate=0.0, fp_rate=0.0, fn_rate=0.0,
            avg_latency_ms=0.0, code_chars=0, changed_lines=0, score=0.0,
            passed_adoption_gate=False, rejection_reasons=(),
        )
        base.update(overrides)
        return FitnessReport(**base)

    def test_holdout_pass_rate_default_is_one(self):
        assert self._make_report().holdout_pass_rate == 1.0

    def test_counterfactual_pass_rate_default_is_one(self):
        assert self._make_report().counterfactual_pass_rate == 1.0

    def test_drift_pass_rate_default_is_one(self):
        assert self._make_report().drift_pass_rate == 1.0

    def test_adaptive_floor_passed_default_is_true(self):
        assert self._make_report().adaptive_floor_passed is True

    def test_adaptive_floor_rejection_reasons_default_is_empty(self):
        assert self._make_report().adaptive_floor_rejection_reasons == ()

    def test_custom_floor_values_stored(self):
        r = self._make_report(
            holdout_pass_rate=0.6,
            counterfactual_pass_rate=0.7,
            drift_pass_rate=0.8,
            adaptive_floor_passed=False,
            adaptive_floor_rejection_reasons=("holdout too low",),
        )
        assert r.holdout_pass_rate == 0.6
        assert r.counterfactual_pass_rate == 0.7
        assert r.drift_pass_rate == 0.8
        assert r.adaptive_floor_passed is False
        assert "holdout too low" in r.adaptive_floor_rejection_reasons
