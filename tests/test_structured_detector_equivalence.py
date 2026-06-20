from __future__ import annotations

import pytest

from core.detector import inspect_request
from core.structured_detector import inspect_request_with_structured_rules
from core.test_attacker import load_test_cases
from core.types import DetectionResult, Request
from tests.test_structured_detector_integration import equivalent_rules_doc, request


def assert_equivalent(request_obj: Request) -> None:
    baseline = inspect_request(request_obj)
    structured = inspect_request_with_structured_rules(request_obj, equivalent_rules_doc())

    assert type(structured) is DetectionResult
    assert structured.blocked is baseline.blocked
    assert structured.reason == baseline.reason
    assert structured.confidence == baseline.confidence
    assert structured.matched_signals == baseline.matched_signals


@pytest.mark.parametrize(
    "sample",
    [
        request(path="/files/PATH_TRAVERSAL_INDICATOR"),
        request(query={"q": "SCRIPT_INJECTION_INDICATOR"}),
        request(headers={"x-test": "SQLI_INDICATOR"}),
        request(body="prefix COMMAND_DELIMITER_INDICATOR suffix"),
        request(body="prefix ENCODED_TRAVERSAL_INDICATOR suffix"),
        request(path="/PATH_TRAVERSAL_INDICATOR", query={"q": "SCRIPT_INJECTION_INDICATOR"}, body="SQLI_INDICATOR"),
        request(body="ordinary benign content"),
        request(body="PaTh_TrAvErSaL_InDiCaToR"),
        request(body="a" * (524288 - len(" path_traversal_indicator")) + " path_traversal_indicator"),
        request(path="/no/match", query={"q": "safe"}, headers={"x-safe": "true"}, body="safe"),
    ],
)
def test_sample_level_equivalence_with_current_detector(sample: Request) -> None:
    assert_equivalent(sample)


@pytest.mark.parametrize(
    ("body", "expected_confidence", "expected_signals"),
    [
        ("path_traversal_indicator", 0.86, ("path_traversal_indicator",)),
        (
            "path_traversal_indicator script_injection_indicator",
            0.94,
            ("path_traversal_indicator", "script_injection_indicator"),
        ),
        (
            "path_traversal_indicator script_injection_indicator sqli_indicator command_delimiter_indicator",
            0.99,
            ("path_traversal_indicator", "script_injection_indicator", "sqli_indicator", "command_delimiter_indicator"),
        ),
    ],
)
def test_confidence_and_matched_signal_order_equivalence(body: str, expected_confidence: float, expected_signals: tuple[str, ...]) -> None:
    req = request(body=body)
    structured = inspect_request_with_structured_rules(req, equivalent_rules_doc())
    baseline = inspect_request(req)
    assert structured == baseline
    assert structured.confidence == expected_confidence
    assert structured.matched_signals == expected_signals


def test_large_body_near_end_indicator_matches_current_detector() -> None:
    req = request(body="benign content word " * (256 * 1024 // 20) + " path_traversal_indicator")
    assert_equivalent(req)


def test_body_content_beyond_configured_structured_budget_is_outside_structured_scanning() -> None:
    doc = equivalent_rules_doc()
    limit = doc["features"]["surface"]["body_scan"]["max_bytes"]
    result = inspect_request_with_structured_rules(request(body="a" * limit + " path_traversal_indicator"), doc)
    assert result == DetectionResult(False, "no suspicious indicator matched", 0.0, ())


def _main_and_adaptive_corpus_cases():
    return load_test_cases(require_adaptive_tiers=True)


def test_corpus_level_equivalence_for_main_and_adaptive_tiers() -> None:
    cases = _main_and_adaptive_corpus_cases()
    assert {"benign", "attack", "regression", "holdout", "counterfactual", "drift"} <= {case.kind for case in cases}

    for case in cases:
        baseline = inspect_request(case.request)
        structured = inspect_request_with_structured_rules(case.request, equivalent_rules_doc())
        assert structured.blocked is baseline.blocked, case.id
        assert structured.matched_signals == baseline.matched_signals, case.id
