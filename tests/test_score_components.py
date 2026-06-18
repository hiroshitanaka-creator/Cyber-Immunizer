"""Score transparency tests for offline candidate evaluation reports."""
from __future__ import annotations

import math

from scripts.evaluate_candidate import _build_adoption_decision, _build_score_components


def _report(**overrides: object) -> dict:
    report = {
        "tp_rate": 1.0,
        "fp_rate": 0.0,
        "fn_rate": 0.0,
        "exception_count": 0,
        "code_chars": 2617,
        "changed_lines": 0,
        "score": 947.66,
        "passed_adoption_gate": False,
        "rejection_reasons": ["score=947.6600 <= previous_best=947.6600"],
    }
    report.update(overrides)
    return report


def test_score_components_exposes_formula_inputs_and_contributions() -> None:
    components = _build_score_components(_report())

    assert components["tp_rate"] == 1.0
    assert components["fp_rate"] == 0.0
    assert components["fn_rate"] == 0.0
    assert components["exception_count"] == 0
    assert components["code_chars"] == 2617
    assert components["changed_lines"] == 0
    assert components["formula"] == (
        "1000*tp_rate - 2000*fp_rate - 1500*fn_rate - "
        "50*exception_count - 0.02*code_chars"
    )


def test_contribution_terms_sum_to_final_score() -> None:
    components = _build_score_components(_report())

    contribution_sum = sum(components["contributions"].values())

    assert math.isclose(contribution_sum, components["score"], rel_tol=0.0, abs_tol=1e-9)


def test_changed_lines_is_diagnostic_only_and_does_not_affect_score() -> None:
    with_no_changed_lines = _build_score_components(_report(changed_lines=0))
    with_many_changed_lines = _build_score_components(_report(changed_lines=999))

    assert with_many_changed_lines["diagnostics"] == {
        "changed_lines": 999,
        "changed_lines_is_score_component": False,
    }
    assert with_many_changed_lines["score"] == with_no_changed_lines["score"]
    assert with_many_changed_lines["contributions"] == with_no_changed_lines["contributions"]
    assert "changed_lines" not in with_many_changed_lines["contributions"]


def test_generation3_equal_score_does_not_self_adopt() -> None:
    decision = _build_adoption_decision(_report(), previous_best=947.66)

    assert decision == {
        "previous_best": 947.66,
        "candidate_score": 947.66,
        "strictly_exceeds_previous_best": False,
        "hard_gates_passed": True,
        "adoption_gate_passed": False,
        "rejection_reasons": ["candidate_score_not_above_previous_best"],
    }


def test_score_below_previous_best_does_not_pass_adoption() -> None:
    decision = _build_adoption_decision(
        _report(score=947.65, rejection_reasons=["score=947.6500 <= previous_best=947.6600"]),
        previous_best=947.66,
    )

    assert decision["strictly_exceeds_previous_best"] is False
    assert decision["adoption_gate_passed"] is False
    assert decision["rejection_reasons"] == ["candidate_score_not_above_previous_best"]


def test_score_above_previous_best_passes_score_threshold_when_hard_gates_pass() -> None:
    decision = _build_adoption_decision(
        _report(score=947.67, passed_adoption_gate=True, rejection_reasons=[]),
        previous_best=947.66,
    )

    assert decision["strictly_exceeds_previous_best"] is True
    assert decision["hard_gates_passed"] is True
    assert decision["adoption_gate_passed"] is True
    assert decision["rejection_reasons"] == []


def test_hard_gate_failure_prevents_adoption_even_when_score_above_previous_best() -> None:
    decision = _build_adoption_decision(
        _report(
            score=1000.0,
            passed_adoption_gate=False,
            rejection_reasons=["fp_rate=0.100 > max_fp_rate=0.050"],
        ),
        previous_best=947.66,
    )

    assert decision["strictly_exceeds_previous_best"] is True
    assert decision["hard_gates_passed"] is False
    assert decision["adoption_gate_passed"] is False
    assert decision["rejection_reasons"] == ["hard_gate_failed_fp_rate"]


def test_rejection_reason_codes_are_precise_and_machine_readable() -> None:
    decision = _build_adoption_decision(
        _report(
            passed_adoption_gate=False,
            rejection_reasons=[
                "regression_pass_rate=0.000 < 1.000",
                "avg_latency_ms=101.00 > max_avg_latency_ms=100.00",
            ],
        ),
        previous_best=947.66,
    )

    assert decision["rejection_reasons"] == [
        "hard_gate_failed_regression_pass_rate",
        "hard_gate_failed_avg_latency",
        "candidate_score_not_above_previous_best",
    ]


def test_evaluation_report_contains_structured_score_components_and_decision(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch

    from scripts.evaluate_candidate import evaluate_candidate

    candidate = tmp_path / "candidate_detector.py"
    candidate.write_text((Path(__file__).parent.parent / "core" / "detector.py").read_text(), encoding="utf-8")
    report_path = tmp_path / "fitness_report.json"
    fitness_stdout = {
        "passed_adoption_gate": False,
        "score": 947.66,
        "tp_rate": 1.0,
        "fp_rate": 0.0,
        "fn_rate": 0.0,
        "exception_count": 0,
        "code_chars": 2617,
        "changed_lines": 12,
        "rejection_reasons": ["score=947.6600 <= previous_best=947.6600"],
    }

    with patch("scripts.evaluate_candidate.validate", return_value={"valid": True, "violations": []}), \
        patch("scripts.evaluate_candidate.run_behavioral_surface_check_subprocess", return_value={
            "passed": True,
            "field_results": {},
            "missing": [],
            "rejection_reasons": [],
            "harness_error": False,
            "error": None,
        }), \
        patch("subprocess.run", return_value=SimpleNamespace(returncode=1, stdout=__import__('json').dumps(fitness_stdout), stderr="")):
        result = evaluate_candidate(candidate, timeout_seconds=5, report_path=report_path)

    report = __import__('json').loads(report_path.read_text())
    assert result["fitness_report"]["score_components"] == report["score_components"]
    assert report["score_components"]["diagnostics"]["changed_lines_is_score_component"] is False
    assert report["adoption_decision"]["rejection_reasons"] == ["candidate_score_not_above_previous_best"]
