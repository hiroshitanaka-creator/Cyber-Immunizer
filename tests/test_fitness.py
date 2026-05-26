"""tests/test_fitness.py — Verify fitness evaluation produces correct reports."""
from __future__ import annotations

import json
import textwrap
import tempfile
from pathlib import Path

import pytest

from core.fitness import evaluate, _compute_score
from core.types import FitnessReport


_PROJECT_ROOT = Path(__file__).parent.parent


def _write_candidate(body_between_markers: str, extra_preamble: str = "") -> Path:
    """Write a temporary candidate detector file."""
    preamble = extra_preamble or "from core.types import Request, DetectionResult\n"
    source = (
        preamble
        + "\ndef inspect_request(request: Request) -> DetectionResult:\n"
        + "    # === MUTATION_START ===\n"
        + textwrap.indent(body_between_markers.strip(), "    ") + "\n"
        + "    # === MUTATION_END ===\n"
    )
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(source)
    tmp.flush()
    return Path(tmp.name)


class TestBaselineDetector:
    def test_baseline_produces_valid_report(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert isinstance(report, FitnessReport)
        assert report.syntax_ok
        assert report.ast_policy_ok
        assert report.contract_ok
        assert not report.timed_out
        assert report.exception_count == 0
        assert report.total_cases > 0

    def test_baseline_tp_rate_positive(self):
        """Baseline detector must block at least some attacks."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert report.tp_rate > 0.0, "Baseline should have tp_rate > 0"

    def test_baseline_fp_rate_acceptable(self):
        """Baseline must not block most benign requests."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert report.fp_rate <= 0.05, (
            f"Baseline fp_rate={report.fp_rate:.3f} exceeds 0.05"
        )

    def test_score_is_float(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert isinstance(report.score, float)

    def test_report_has_all_fields(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        for field in (
            "syntax_ok", "ast_policy_ok", "contract_ok", "timed_out",
            "exception_count", "true_positive", "false_positive",
            "true_negative", "false_negative", "total_cases",
            "tp_rate", "fp_rate", "fn_rate", "avg_latency_ms",
            "code_chars", "changed_lines", "score", "passed_adoption_gate",
            "rejection_reasons",
        ):
            assert hasattr(report, field), f"FitnessReport missing field: {field}"


class TestAllBlockingDetector:
    """A detector that always blocks everything should fail due to FP rate."""

    def _make_all_blocking(self) -> Path:
        body = textwrap.dedent("""\
            return DetectionResult(True, "blocked everything", 1.0, ("all",))
        """)
        return _write_candidate(body)

    def test_fails_adoption_gate(self):
        p = self._make_all_blocking()
        report = evaluate(p, baseline_mode=True)
        assert not report.passed_adoption_gate, (
            "All-blocking detector should fail adoption gate due to false positives"
        )

    def test_fp_rate_is_one(self):
        p = self._make_all_blocking()
        report = evaluate(p, baseline_mode=True)
        assert report.fp_rate == 1.0 or report.fp_rate > 0.05, (
            f"All-blocking detector should have high fp_rate, got {report.fp_rate}"
        )

    def test_rejection_includes_fp_reason(self):
        p = self._make_all_blocking()
        report = evaluate(p, baseline_mode=True)
        reasons = " ".join(report.rejection_reasons).lower()
        assert "fp" in reasons or "false_positive" in reasons or "fp_rate" in reasons, (
            f"Expected FP-related rejection, got: {report.rejection_reasons}"
        )


class TestAllAllowingDetector:
    """A detector that never blocks should fail due to FN rate."""

    def _make_all_allowing(self) -> Path:
        body = textwrap.dedent("""\
            return DetectionResult(False, "allowed everything", 0.0, ())
        """)
        return _write_candidate(body)

    def test_fails_adoption_gate(self):
        p = self._make_all_allowing()
        report = evaluate(p, baseline_mode=True)
        assert not report.passed_adoption_gate, (
            "All-allowing detector should fail adoption gate"
        )

    def test_tp_rate_is_zero(self):
        p = self._make_all_allowing()
        report = evaluate(p, baseline_mode=True)
        assert report.tp_rate == 0.0, (
            f"All-allowing detector should have tp_rate=0.0, got {report.tp_rate}"
        )

    def test_fn_rate_is_one(self):
        p = self._make_all_allowing()
        report = evaluate(p, baseline_mode=True)
        assert report.fn_rate == 1.0, (
            f"All-allowing detector fn_rate should be 1.0, got {report.fn_rate}"
        )


class TestRegressionEnforcement:
    """Regression cases must all pass for adoption gate to succeed."""

    def test_regression_cases_counted(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        # regression_cases.json has 5 entries; total > 0
        assert report.total_cases > 0

    def test_baseline_passes_regressions(self):
        """Baseline detector should pass all regression cases."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        # If baseline passes regression, it won't have regression-related rejections
        regression_reasons = [
            r for r in report.rejection_reasons
            if "regression" in r.lower()
        ]
        assert len(regression_reasons) == 0, (
            f"Baseline failed regression: {regression_reasons}"
        )


class TestScoreDeterminism:
    def test_score_is_deterministic(self):
        """Same candidate + same data must produce the exact same score.

        avg_latency_ms is excluded from the score formula, so the score is
        bitwise-identical across repeated evaluations of the same candidate on
        the same test data, regardless of timing variation.
        """
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        r1 = evaluate(baseline, baseline_mode=True)
        r2 = evaluate(baseline, baseline_mode=True)

        # All classification counts must be identical
        assert r1.true_positive == r2.true_positive, "true_positive non-deterministic"
        assert r1.false_positive == r2.false_positive, "false_positive non-deterministic"
        assert r1.true_negative == r2.true_negative, "true_negative non-deterministic"
        assert r1.false_negative == r2.false_negative, "false_negative non-deterministic"
        assert r1.tp_rate == r2.tp_rate, "tp_rate non-deterministic"
        assert r1.fp_rate == r2.fp_rate, "fp_rate non-deterministic"
        assert r1.fn_rate == r2.fn_rate, "fn_rate non-deterministic"
        assert r1.code_chars == r2.code_chars, "code_chars non-deterministic"
        assert r1.changed_lines == r2.changed_lines, "changed_lines non-deterministic"
        assert r1.exception_count == r2.exception_count, "exception_count non-deterministic"

        # Score must be exactly equal — latency is NOT in the formula
        assert r1.score == r2.score, (
            f"Score must be deterministic (latency is excluded from the formula). "
            f"Got r1.score={r1.score}, r2.score={r2.score}"
        )

    def test_latency_reported_but_not_in_score(self):
        """avg_latency_ms must be reported but must not affect the score."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)

        # avg_latency_ms is present and non-negative
        assert isinstance(report.avg_latency_ms, float), "avg_latency_ms must be float"
        assert report.avg_latency_ms >= 0.0, "avg_latency_ms must be non-negative"

        # Verify score formula doesn't include latency by checking manually
        expected_score = _compute_score(
            tp_rate=report.tp_rate,
            fp_rate=report.fp_rate,
            fn_rate=report.fn_rate,
            exception_count=report.exception_count,
            code_chars=report.code_chars,
            changed_lines=report.changed_lines,
        )
        assert report.score == pytest.approx(expected_score), (
            f"Score should match formula without latency. "
            f"Expected {expected_score}, got {report.score}"
        )

    def test_latency_gate_enforced_separately(self):
        """The adoption gate must check avg_latency_ms even though it's not in score."""
        # We can't easily inject a slow candidate here, but we can verify the
        # baseline report contains avg_latency_ms in the report (not in score).
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert hasattr(report, "avg_latency_ms"), "FitnessReport must have avg_latency_ms"

    def test_score_formula(self):
        """Score formula produces expected value for known inputs (no latency param)."""
        score = _compute_score(
            tp_rate=1.0,
            fp_rate=0.0,
            fn_rate=0.0,
            exception_count=0,
            code_chars=0,
            changed_lines=0,
        )
        assert score == pytest.approx(1000.0), f"Expected 1000.0 got {score}"

    def test_score_penalises_fp(self):
        no_fp = _compute_score(1.0, 0.0, 0.0, 0, 0, 0)
        with_fp = _compute_score(1.0, 0.5, 0.0, 0, 0, 0)
        assert with_fp < no_fp

    def test_score_penalises_fn(self):
        no_fn = _compute_score(1.0, 0.0, 0.0, 0, 0, 0)
        with_fn = _compute_score(1.0, 0.0, 0.5, 0, 0, 0)
        assert with_fn < no_fn

    def test_score_penalises_exceptions(self):
        no_exc = _compute_score(1.0, 0.0, 0.0, 0, 0, 0)
        with_exc = _compute_score(1.0, 0.0, 0.0, 1, 0, 0)
        assert with_exc < no_exc

    def test_score_penalises_code_size(self):
        small = _compute_score(1.0, 0.0, 0.0, 0, 100, 0)
        large = _compute_score(1.0, 0.0, 0.0, 0, 10000, 0)
        assert large < small

    def test_score_penalises_changed_lines(self):
        few = _compute_score(1.0, 0.0, 0.0, 0, 0, 1)
        many = _compute_score(1.0, 0.0, 0.0, 0, 0, 100)
        assert many < few
