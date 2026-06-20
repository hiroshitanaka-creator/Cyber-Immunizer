from __future__ import annotations

import builtins
import os
import socket
from pathlib import Path

import pytest

from core.detector import inspect_request
from core.structured_evaluator import evaluate_structured_rules
from core.types import DetectionResult, Request


def rules_doc(*, rules: list[dict] | None = None, block_when: str = "any_rule_matches", strategy: dict | None = None, fields: list[str] | None = None, minimum_match_count: int | None = None, max_collection_entries: dict | None = None, max_scalar_bytes: dict | None = None, body_max_bytes: int = 524288) -> dict:
    decision = {
        "block_when": block_when,
        "reason": "suspicious indicator matched",
        "confidence_strategy": strategy or {"type": "fixed", "default": 0.7},
        "matched_signals": "matched_rule_signals",
    }
    if minimum_match_count is not None:
        decision["minimum_match_count"] = minimum_match_count
    return {
        "schema_version": 1,
        "features": {
            "surface": {
                "fields": fields or ["method", "path", "query.keys", "query.values", "headers.keys", "headers.values", "body"],
                "normalization": ["lowercase"],
                "max_collection_entries": max_collection_entries or {"query": 100, "headers": 100},
                "max_scalar_bytes": max_scalar_bytes or {"method": 64, "path": 4096, "query.item": 4096, "header.item": 4096},
                "body_scan": {"mode": "full", "max_bytes": body_max_bytes},
            }
        },
        "rules": rules or [rule("r1", "contains_literal", "path_traversal_indicator", "path_traversal_indicator", 0.86)],
        "decision": decision,
        "fallback": {"blocked": False, "reason": "no suspicious indicator matched", "confidence": 0.0, "matched_signals": []},
    }


def rule(rule_id: str, operator: str, literal: str, signal: str | None = None, confidence: float = 0.7) -> dict:
    return {"id": rule_id, "field": "surface", "operator": operator, "literal": literal, "signal": signal or rule_id, "confidence": confidence}


def request(**kwargs) -> Request:
    defaults = {"method": "GET", "path": "/api/data", "query": {}, "headers": {"content-type": "text/plain"}, "body": ""}
    defaults.update(kwargs)
    return Request(**defaults)


def test_valid_matching_document_blocks_and_returns_detection_result() -> None:
    result = evaluate_structured_rules(request(body="xx PATH_TRAVERSAL_INDICATOR yy"), rules_doc())
    assert type(result) is DetectionResult
    assert result.blocked is True
    assert result.reason == "suspicious indicator matched"
    assert result.confidence == 0.7
    assert result.matched_signals == ("path_traversal_indicator",)


def test_valid_non_matching_document_returns_fallback() -> None:
    result = evaluate_structured_rules(request(body="benign"), rules_doc())
    assert result == DetectionResult(False, "no suspicious indicator matched", 0.0, ())


@pytest.mark.parametrize(
    ("operator", "literal", "path"),
    [
        ("contains_literal", "admin", "/v1/admin/settings"),
        ("equals_literal", "/exact", "/exact"),
        ("starts_with_literal", "/api", "/api/data"),
        ("ends_with_literal", "/tail", "/long/tail"),
    ],
)
def test_each_operator_matches_requested_surface(operator: str, literal: str, path: str) -> None:
    doc = rules_doc(rules=[rule("op", operator, literal)], fields=["path"])
    assert evaluate_structured_rules(request(path=path), doc).blocked is True


def test_decision_mode_any_rule_matches() -> None:
    doc = rules_doc(rules=[rule("a", "contains_literal", "one"), rule("b", "contains_literal", "two")])
    assert evaluate_structured_rules(request(body="one"), doc).blocked is True


def test_decision_mode_all_rules_match_requires_every_rule() -> None:
    doc = rules_doc(block_when="all_rules_match", rules=[rule("a", "contains_literal", "one"), rule("b", "contains_literal", "two")])
    assert evaluate_structured_rules(request(body="one"), doc).blocked is False
    assert evaluate_structured_rules(request(body="one two"), doc).blocked is True


def test_decision_mode_minimum_match_count_uses_threshold() -> None:
    doc = rules_doc(block_when="minimum_match_count", minimum_match_count=2, rules=[rule("a", "contains_literal", "one"), rule("b", "contains_literal", "two"), rule("c", "contains_literal", "three")])
    assert evaluate_structured_rules(request(body="one"), doc).blocked is False
    assert evaluate_structured_rules(request(body="one three"), doc).blocked is True


def test_confidence_strategies() -> None:
    req = request(body="one two three")
    rules = [rule("a", "contains_literal", "one", confidence=0.3), rule("b", "contains_literal", "two", confidence=0.6), rule("c", "contains_literal", "three", confidence=0.9)]
    assert evaluate_structured_rules(req, rules_doc(rules=rules, strategy={"type": "fixed", "default": 0.42})).confidence == 0.42
    assert evaluate_structured_rules(req, rules_doc(rules=rules, strategy={"type": "bounded_match_count", "default": 0.1, "two_matches": 0.2, "three_or_more_matches": 0.99})).confidence == 0.99
    assert evaluate_structured_rules(req, rules_doc(rules=rules, strategy={"type": "maximum_matched_confidence"})).confidence == 0.9


def test_bounded_match_count_unspecified_keys_fall_back_to_default() -> None:
    doc = rules_doc(rules=[rule("a", "contains_literal", "one"), rule("b", "contains_literal", "two")], strategy={"type": "bounded_match_count", "default": 0.55})
    assert evaluate_structured_rules(request(body="one two"), doc).confidence == 0.55


def test_matched_signals_follow_rule_order_not_request_discovery_order() -> None:
    doc = rules_doc(rules=[rule("first", "contains_literal", "later", "first_signal"), rule("second", "contains_literal", "earlier", "second_signal")])
    assert evaluate_structured_rules(request(body="earlier later"), doc).matched_signals == ("first_signal", "second_signal")


def test_invalid_schema_document_returns_fallback_without_exception() -> None:
    doc = rules_doc()
    doc["schema_version"] = 2
    assert evaluate_structured_rules(request(body="path_traversal_indicator"), doc) == DetectionResult(False, "no suspicious indicator matched", 0.0, ())


def test_unsupported_operator_returns_fallback_without_crash() -> None:
    doc = rules_doc()
    doc["rules"][0]["operator"] = "regex"
    assert evaluate_structured_rules(request(body="path_traversal_indicator"), doc).blocked is False


def test_python_like_payload_is_data_not_executed(tmp_path: Path) -> None:
    target = tmp_path / "would_exist_if_executed"
    payload = f"__import__('pathlib').Path({str(target)!r}).write_text('x')"
    doc = rules_doc(rules=[rule("payload", "contains_literal", payload)])
    result = evaluate_structured_rules(request(body=payload), doc)
    assert result.blocked is True
    assert not target.exists()


def test_evaluator_does_not_use_files_network_environment_eval_or_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("forbidden side effect API called")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os.environ, "get", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    assert evaluate_structured_rules(request(body="path_traversal_indicator"), rules_doc()).blocked is True


@pytest.mark.parametrize("bad_request", [object(), Request(method="GET", path="/", query={}, headers={}, body="\ud800")])
def test_invalid_request_values_return_fallback_without_raising(bad_request) -> None:
    assert evaluate_structured_rules(bad_request, rules_doc()).blocked is False


def test_unencodable_rule_strings_are_rejected_to_fallback() -> None:
    doc = rules_doc()
    doc["rules"][0]["literal"] = "\ud800"
    assert evaluate_structured_rules(request(body="anything"), doc).blocked is False


def test_collection_traversal_respects_max_collection_entries() -> None:
    query = {"first": "benign", "second": "path_traversal_indicator"}
    doc = rules_doc(max_collection_entries={"query": 1, "headers": 100})
    assert evaluate_structured_rules(request(query=query), doc).blocked is False


def test_scalar_extraction_respects_max_scalar_bytes() -> None:
    query = {"first": "a" * 12 + "path_traversal_indicator"}
    doc = rules_doc(max_scalar_bytes={"method": 64, "path": 4096, "query.item": 8, "header.item": 4096})
    assert evaluate_structured_rules(request(query=query), doc).blocked is False


def test_body_scan_detects_indicator_near_end_of_configured_budget() -> None:
    prefix = "a" * (524288 - len(" path_traversal_indicator"))
    result = evaluate_structured_rules(request(body=prefix + " path_traversal_indicator"), rules_doc())
    assert result.blocked is True
    assert result.matched_signals == ("path_traversal_indicator",)


def test_body_content_beyond_configured_max_bytes_is_not_scanned() -> None:
    body = "a" * 524288 + " path_traversal_indicator"
    assert evaluate_structured_rules(request(body=body), rules_doc()).blocked is False


def symbolic_equivalent_rules() -> dict:
    return rules_doc(
        rules=[
            rule("path", "contains_literal", "path_traversal_indicator", "path_traversal_indicator"),
            rule("script", "contains_literal", "script_injection_indicator", "script_injection_indicator"),
            rule("sqli", "contains_literal", "sqli_indicator", "sqli_indicator"),
            rule("cmd", "contains_literal", "command_delimiter_indicator", "command_delimiter_indicator"),
            rule("encoded", "contains_literal", "encoded_traversal_indicator", "encoded_traversal_indicator"),
        ],
        strategy={"type": "bounded_match_count", "default": 0.86, "two_matches": 0.94, "three_or_more_matches": 0.99},
    )


@pytest.mark.parametrize(
    "sample",
    [
        request(path="/PATH_TRAVERSAL_INDICATOR"),
        request(query={"q": "SCRIPT_INJECTION_INDICATOR"}),
        request(headers={"x": "SQLI_INDICATOR"}),
        request(body="COMMAND_DELIMITER_INDICATOR and ENCODED_TRAVERSAL_INDICATOR"),
        request(body="ordinary benign content"),
    ],
)
def test_symbolic_equivalent_rules_match_current_detector_samples(sample: Request) -> None:
    structured = evaluate_structured_rules(sample, symbolic_equivalent_rules())
    baseline = inspect_request(sample)
    assert structured.blocked is baseline.blocked
    assert structured.matched_signals == baseline.matched_signals


def test_evaluator_is_not_integrated_into_detector_source() -> None:
    source = Path("core/detector.py").read_text(encoding="utf-8")
    assert "structured_evaluator" not in source
    assert "evaluate_structured_rules" not in source
