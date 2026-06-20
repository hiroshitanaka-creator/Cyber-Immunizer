from __future__ import annotations

import builtins
import copy
import os
import socket
from pathlib import Path

import pytest

from core.detector import inspect_request
from core.structured_detector import inspect_request_with_structured_rules
from core.types import DetectionResult, Request


def request(**kwargs) -> Request:
    defaults = {
        "method": "GET",
        "path": "/api/data",
        "query": {},
        "headers": {"content-type": "text/plain"},
        "body": "",
        "source_ip": "127.0.0.1",
    }
    defaults.update(kwargs)
    return Request(**defaults)


def rule(rule_id: str, literal: str, signal: str | None = None, confidence: float = 0.86) -> dict:
    return {
        "id": rule_id,
        "field": "surface",
        "operator": "contains_literal",
        "literal": literal,
        "signal": signal or literal,
        "confidence": confidence,
    }


def equivalent_rules_doc() -> dict:
    indicators = (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    )
    return {
        "schema_version": 1,
        "features": {
            "surface": {
                "fields": [
                    "method",
                    "path",
                    "query.keys",
                    "query.values",
                    "headers.keys",
                    "headers.values",
                    "body",
                ],
                "normalization": ["lowercase"],
                "max_collection_entries": {"query": 1000, "headers": 1000},
                "max_scalar_bytes": {
                    "method": 4096,
                    "path": 1048576,
                    "query.item": 1048576,
                    "header.item": 1048576,
                },
                "body_scan": {"mode": "full", "max_bytes": 1048576},
            }
        },
        "rules": [rule(indicator, indicator) for indicator in indicators],
        "decision": {
            "block_when": "any_rule_matches",
            "reason": "suspicious indicator matched",
            "confidence_strategy": {
                "type": "bounded_match_count",
                "default": 0.86,
                "two_matches": 0.94,
                "three_or_more_matches": 0.99,
            },
            "matched_signals": "matched_rule_signals",
        },
        "fallback": {
            "blocked": False,
            "reason": "no suspicious indicator matched",
            "confidence": 0.0,
            "matched_signals": [],
        },
    }


def test_adapter_returns_detection_result_and_blocks_match() -> None:
    result = inspect_request_with_structured_rules(
        request(path="/PATH_TRAVERSAL_INDICATOR"), equivalent_rules_doc()
    )
    assert type(result) is DetectionResult
    assert result.blocked is True
    assert result.reason == "suspicious indicator matched"
    assert result.confidence == 0.86
    assert result.matched_signals == ("path_traversal_indicator",)


def test_adapter_returns_non_blocking_fallback_on_no_match() -> None:
    assert inspect_request_with_structured_rules(request(body="benign"), equivalent_rules_doc()) == DetectionResult(
        False, "no suspicious indicator matched", 0.0, ()
    )


def test_invalid_schema_document_returns_non_blocking_detection_result() -> None:
    doc = equivalent_rules_doc()
    doc["schema_version"] = 2
    result = inspect_request_with_structured_rules(request(body="path_traversal_indicator"), doc)
    assert type(result) is DetectionResult
    assert result == DetectionResult(False, "no suspicious indicator matched", 0.0, ())


@pytest.mark.parametrize("malformed_doc", [None, [], "not a dict", {"fallback": {"blocked": True}}])
def test_malformed_rules_document_does_not_raise(malformed_doc) -> None:
    result = inspect_request_with_structured_rules(request(body="path_traversal_indicator"), malformed_doc)
    assert type(result) is DetectionResult
    assert result.blocked is False
    assert result.matched_signals == ()


def test_unsupported_operator_returns_fallback_through_validation() -> None:
    doc = equivalent_rules_doc()
    doc["rules"][0]["operator"] = "regex"
    result = inspect_request_with_structured_rules(request(body="path_traversal_indicator"), doc)
    assert result == DetectionResult(False, "no suspicious indicator matched", 0.0, ())


def test_adapter_does_not_mutate_request_or_rules_doc() -> None:
    req = request(query={"q": "PATH_TRAVERSAL_INDICATOR"})
    before_request = (req.method, req.path, dict(req.query), dict(req.headers), req.body, req.source_ip)
    doc = equivalent_rules_doc()
    before_doc = copy.deepcopy(doc)

    inspect_request_with_structured_rules(req, doc)

    assert (req.method, req.path, dict(req.query), dict(req.headers), req.body, req.source_ip) == before_request
    assert doc == before_doc


def test_adapter_does_not_use_files_network_environment_eval_or_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("forbidden side effect API called")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os.environ, "get", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    result = inspect_request_with_structured_rules(request(body="PATH_TRAVERSAL_INDICATOR"), equivalent_rules_doc())
    assert result.blocked is True


def test_default_detector_source_has_no_structured_integration_references() -> None:
    source = Path("core/detector.py").read_text(encoding="utf-8")
    forbidden = (
        "structured_detector",
        "structured_evaluator",
        "inspect_request_with_structured_rules",
        "evaluate_structured_rules",
    )
    assert all(term not in source for term in forbidden)


def test_default_detector_still_requires_no_explicit_structured_rules() -> None:
    req = request(path="/PATH_TRAVERSAL_INDICATOR")
    baseline = inspect_request(req)
    structured = inspect_request_with_structured_rules(req, equivalent_rules_doc())
    assert baseline == structured
