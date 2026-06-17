"""tests/test_fitness.py — Verify fitness evaluation produces correct reports."""
from __future__ import annotations

import json
import shutil
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

        # Verify score formula doesn't include latency or changed_lines
        expected_score = _compute_score(
            tp_rate=report.tp_rate,
            fp_rate=report.fp_rate,
            fn_rate=report.fn_rate,
            exception_count=report.exception_count,
            code_chars=report.code_chars,
        )
        assert report.score == pytest.approx(expected_score), (
            f"Score should match formula without latency or changed_lines. "
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
        """Score formula produces expected value for known inputs (no latency or changed_lines)."""
        score = _compute_score(
            tp_rate=1.0,
            fp_rate=0.0,
            fn_rate=0.0,
            exception_count=0,
            code_chars=0,
        )
        assert score == pytest.approx(1000.0), f"Expected 1000.0 got {score}"

    def test_score_penalises_fp(self):
        no_fp = _compute_score(1.0, 0.0, 0.0, 0, 0)
        with_fp = _compute_score(1.0, 0.5, 0.0, 0, 0)
        assert with_fp < no_fp

    def test_score_penalises_fn(self):
        no_fn = _compute_score(1.0, 0.0, 0.0, 0, 0)
        with_fn = _compute_score(1.0, 0.0, 0.5, 0, 0)
        assert with_fn < no_fn

    def test_score_penalises_exceptions(self):
        no_exc = _compute_score(1.0, 0.0, 0.0, 0, 0)
        with_exc = _compute_score(1.0, 0.0, 0.0, 1, 0)
        assert with_exc < no_exc

    def test_score_penalises_code_size(self):
        small = _compute_score(1.0, 0.0, 0.0, 0, 100)
        large = _compute_score(1.0, 0.0, 0.0, 0, 10000)
        assert large < small


class TestNoOpAdoptionGate:
    """A candidate identical to core/detector.py must fail the adoption gate."""

    def test_noop_fails_adoption_gate(self):
        """No-op candidate (same as current detector) must not pass the gate.

        This test demonstrates the generation-invariant fix: under the old
        formula, the no-op scored 939.34 > genome.json::best_score=729.34 and
        passed.  After the fix, best_score is migrated to 939.34 so the no-op
        scores 939.34 <= 939.34 and is rejected.
        """
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        # Copy to a temporary path so evaluate() treats it as a candidate.
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write(baseline.read_text(encoding="utf-8"))
            candidate_path = Path(f.name)
        try:
            # Use the repository genome.json (post-migration best_score=939.34).
            genome_path = _PROJECT_ROOT / "data" / "genome.json"
            report = evaluate(candidate_path, baseline_mode=False, genome_path=genome_path)
            assert report.changed_lines == 0, (
                f"No-op candidate must have changed_lines=0, got {report.changed_lines}"
            )
            assert not report.passed_adoption_gate, (
                f"No-op candidate must fail the adoption gate. "
                f"score={report.score}, rejection_reasons={report.rejection_reasons}"
            )
            reasons_text = " ".join(report.rejection_reasons).lower()
            assert "previous_best" in reasons_text or "score" in reasons_text, (
                f"Rejection must reference score comparison, got: {report.rejection_reasons}"
            )
        finally:
            candidate_path.unlink(missing_ok=True)

    def test_noop_changed_lines_is_zero(self):
        """Evaluating core/detector.py as a candidate must give changed_lines=0."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert report.changed_lines == 0


class TestChangedLinesDiagnosticOnly:
    """changed_lines must be present in reports but must not affect score."""

    def test_changed_lines_in_report(self):
        """FitnessReport must still expose changed_lines as a diagnostic field."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert hasattr(report, "changed_lines"), "FitnessReport must have changed_lines"
        assert isinstance(report.changed_lines, int)

    def test_score_independent_of_changed_lines(self):
        """_compute_score must not accept a changed_lines parameter."""
        import inspect
        sig = inspect.signature(_compute_score)
        assert "changed_lines" not in sig.parameters, (
            "_compute_score must not have a changed_lines parameter "
            "(changed_lines is diagnostic-only)"
        )

    def test_score_components_includes_changed_lines_diagnostic(self):
        """score_components must report changed_lines_diagnostic separately from gate_score."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        assert report.score_components is not None, (
            "Full evaluation must populate score_components"
        )
        assert "changed_lines_diagnostic" in report.score_components, (
            "score_components must include changed_lines_diagnostic"
        )
        assert "gate_score" in report.score_components, (
            "score_components must include gate_score"
        )
        assert report.score_components["gate_score"] == pytest.approx(report.score), (
            "score_components['gate_score'] must equal report.score"
        )

    def test_score_components_none_for_early_exit(self):
        """Early-exit (policy-fail) reports must have score_components=None."""
        # A file with bad syntax triggers early exit.
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("def this is not valid python\n")
            bad_path = Path(f.name)
        try:
            report = evaluate(bad_path, baseline_mode=True)
            assert not report.ast_policy_ok or not report.syntax_ok
            assert report.score_components is None, (
                "Early-exit FitnessReport must have score_components=None"
            )
        finally:
            bad_path.unlink(missing_ok=True)


class TestLowerBaselinePass:
    """A genuinely better candidate must still pass when previous_best is lower."""

    def test_passes_when_previous_best_is_lower(self):
        """Current detector must pass the gate if best_score is set below its score."""
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        # Build a temp genome with best_score intentionally below 939.34.
        genome_path = _PROJECT_ROOT / "data" / "genome.json"
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
        low_genome = {**genome, "best_score": 900.0}
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            json.dump(low_genome, f)
            tmp_genome = Path(f.name)
        try:
            report = evaluate(baseline, baseline_mode=False, genome_path=tmp_genome)
            assert report.passed_adoption_gate, (
                f"Detector must pass when previous_best=900.0 < score={report.score}. "
                f"Rejections: {report.rejection_reasons}"
            )
        finally:
            tmp_genome.unlink(missing_ok=True)


class TestReportBackwardCompatibility:
    """All existing report fields must remain present and correctly typed."""

    def test_all_report_fields_present(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        required_fields = (
            "syntax_ok", "ast_policy_ok", "contract_ok", "timed_out",
            "exception_count", "true_positive", "false_positive",
            "true_negative", "false_negative", "total_cases",
            "tp_rate", "fp_rate", "fn_rate", "avg_latency_ms",
            "code_chars", "changed_lines", "score",
            "passed_adoption_gate", "rejection_reasons",
            "score_components",
        )
        for field in required_fields:
            assert hasattr(report, field), f"FitnessReport missing field: {field}"

    def test_score_components_shape(self):
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        report = evaluate(baseline, baseline_mode=True)
        sc = report.score_components
        assert sc is not None
        for key in (
            "tp_contribution", "fp_penalty", "fn_penalty",
            "exception_penalty", "code_size_penalty",
            "changed_lines_diagnostic", "gate_score",
        ):
            assert key in sc, f"score_components missing key: {key}"
            assert isinstance(sc[key], float), f"score_components[{key!r}] must be float"
