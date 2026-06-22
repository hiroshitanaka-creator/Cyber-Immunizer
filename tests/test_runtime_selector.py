"""tests/test_runtime_selector.py — Tests for core.runtime_selector.

Tests cover:
- Default and explicit legacy mode behavior
- Explicit structured-rules mode behavior
- Gate failures (ValueError for invalid combinations)
- No silent fallback from structured mode to legacy
- No forbidden side effects (file/env/network/eval/exec)
- No mutation of request or rules_doc
- Default detector source integrity
"""
from __future__ import annotations

import builtins
import copy
import os
import socket
from pathlib import Path

import pytest

from core.detector import inspect_request
from core.runtime_selector import inspect_request_with_runtime_selector
from core.structured_detector import inspect_request_with_structured_rules
from core.types import DetectionResult, Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def equivalent_rules_doc() -> dict:
    indicators = (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    )

    def rule(indicator: str) -> dict:
        return {
            "id": indicator,
            "field": "surface",
            "operator": "contains_literal",
            "literal": indicator,
            "signal": indicator,
            "confidence": 0.86,
        }

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
        "rules": [rule(indicator) for indicator in indicators],
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


# ---------------------------------------------------------------------------
# Default (legacy) mode — omitted mode argument
# ---------------------------------------------------------------------------

class TestDefaultLegacyMode:
    def test_benign_request_default_mode(self) -> None:
        req = request(body="ordinary benign content")
        assert inspect_request_with_runtime_selector(req) == inspect_request(req)

    def test_single_indicator_default_mode(self) -> None:
        req = request(body="path_traversal_indicator")
        result = inspect_request_with_runtime_selector(req)
        assert result == inspect_request(req)
        assert result.blocked is True
        assert result.confidence == 0.86
        assert result.matched_signals == ("path_traversal_indicator",)

    def test_multi_indicator_default_mode(self) -> None:
        req = request(body="path_traversal_indicator script_injection_indicator sqli_indicator")
        result = inspect_request_with_runtime_selector(req)
        assert result == inspect_request(req)
        assert result.blocked is True
        assert result.confidence == 0.99


# ---------------------------------------------------------------------------
# Explicit legacy mode
# ---------------------------------------------------------------------------

class TestExplicitLegacyMode:
    def test_benign_explicit_legacy(self) -> None:
        req = request(body="safe content")
        assert inspect_request_with_runtime_selector(req, mode="legacy") == inspect_request(req)

    def test_single_indicator_explicit_legacy(self) -> None:
        req = request(body="sqli_indicator")
        result = inspect_request_with_runtime_selector(req, mode="legacy")
        assert result == inspect_request(req)
        assert result.blocked is True
        assert result.matched_signals == ("sqli_indicator",)

    def test_multi_indicator_explicit_legacy(self) -> None:
        req = request(body="command_delimiter_indicator encoded_traversal_indicator")
        result = inspect_request_with_runtime_selector(req, mode="legacy")
        assert result == inspect_request(req)
        assert result.confidence == 0.94


# ---------------------------------------------------------------------------
# Explicit structured-rules mode
# ---------------------------------------------------------------------------

class TestExplicitStructuredMode:
    def test_benign_structured_mode(self) -> None:
        req = request(body="ordinary benign content")
        doc = equivalent_rules_doc()
        result = inspect_request_with_runtime_selector(req, mode="structured_rules", structured_rules_doc=doc)
        assert result == inspect_request_with_structured_rules(req, doc)
        assert result.blocked is False

    def test_single_indicator_structured_mode_matches_legacy(self) -> None:
        req = request(body="path_traversal_indicator")
        doc = equivalent_rules_doc()
        result = inspect_request_with_runtime_selector(req, mode="structured_rules", structured_rules_doc=doc)
        assert result == inspect_request_with_structured_rules(req, doc)
        assert result == inspect_request(req)
        assert result.blocked is True
        assert result.confidence == 0.86
        assert result.matched_signals == ("path_traversal_indicator",)

    def test_multi_indicator_structured_mode_matches_legacy(self) -> None:
        req = request(body="path_traversal_indicator script_injection_indicator sqli_indicator")
        doc = equivalent_rules_doc()
        result = inspect_request_with_runtime_selector(req, mode="structured_rules", structured_rules_doc=doc)
        assert result == inspect_request_with_structured_rules(req, doc)
        assert result == inspect_request(req)
        assert result.confidence == 0.99

    def test_path_indicator_in_path_field(self) -> None:
        req = request(path="/PATH_TRAVERSAL_INDICATOR")
        doc = equivalent_rules_doc()
        result = inspect_request_with_runtime_selector(req, mode="structured_rules", structured_rules_doc=doc)
        assert result == inspect_request(req)

    def test_indicator_in_query(self) -> None:
        req = request(query={"q": "SCRIPT_INJECTION_INDICATOR"})
        doc = equivalent_rules_doc()
        result = inspect_request_with_runtime_selector(req, mode="structured_rules", structured_rules_doc=doc)
        assert result == inspect_request(req)


# ---------------------------------------------------------------------------
# Gate failures
# ---------------------------------------------------------------------------

class TestGateFailures:
    def test_structured_mode_without_doc_raises(self) -> None:
        with pytest.raises(ValueError, match="structured_rules mode requires structured_rules_doc"):
            inspect_request_with_runtime_selector(request(body="x"), mode="structured_rules")

    def test_legacy_mode_with_doc_raises(self) -> None:
        with pytest.raises(ValueError, match="legacy mode does not accept structured_rules_doc"):
            inspect_request_with_runtime_selector(
                request(body="x"), mode="legacy", structured_rules_doc=equivalent_rules_doc()
            )

    def test_unsupported_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported detector runtime mode"):
            inspect_request_with_runtime_selector(
                request(body="x"), mode="auto"  # type: ignore[arg-type]
            )

    def test_unsupported_mode_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported detector runtime mode"):
            inspect_request_with_runtime_selector(
                request(body="x"), mode="unknown_mode"  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# No silent fallback
# ---------------------------------------------------------------------------

def test_structured_mode_missing_doc_does_not_fall_back_to_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(_req: Request) -> DetectionResult:
        raise AssertionError("legacy detector must not be called")

    monkeypatch.setattr("core.runtime_selector.inspect_request", forbidden)
    with pytest.raises(ValueError, match="structured_rules mode requires structured_rules_doc"):
        inspect_request_with_runtime_selector(request(body="path_traversal_indicator"), mode="structured_rules")


# ---------------------------------------------------------------------------
# No forbidden side effects
# ---------------------------------------------------------------------------

def test_no_forbidden_side_effects_legacy_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selector must not touch open/eval/exec/os.environ/socket even in legacy mode."""
    # Import selector before monkeypatching to avoid breaking import machinery.
    from core.runtime_selector import inspect_request_with_runtime_selector as selector  # noqa: PLC0415

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("forbidden side effect API called")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os.environ, "get", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    result = selector(request(body="path_traversal_indicator"))
    assert result.blocked is True


def test_no_forbidden_side_effects_structured_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selector must not touch open/eval/exec/os.environ/socket in structured mode."""
    from core.runtime_selector import inspect_request_with_runtime_selector as selector  # noqa: PLC0415

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("forbidden side effect API called")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "eval", forbidden)
    monkeypatch.setattr(builtins, "exec", forbidden)
    monkeypatch.setattr(os.environ, "get", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    result = selector(
        request(body="path_traversal_indicator"),
        mode="structured_rules",
        structured_rules_doc=equivalent_rules_doc(),
    )
    assert result.blocked is True


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------

def test_selector_does_not_mutate_request_or_rules_doc() -> None:
    req = request(query={"q": "PATH_TRAVERSAL_INDICATOR"})
    before_request = (req.method, req.path, dict(req.query), dict(req.headers), req.body, req.source_ip)
    doc = equivalent_rules_doc()
    before_doc = copy.deepcopy(doc)

    inspect_request_with_runtime_selector(
        req, mode="structured_rules", structured_rules_doc=doc
    )

    assert (req.method, req.path, dict(req.query), dict(req.headers), req.body, req.source_ip) == before_request
    assert doc == before_doc


def test_selector_legacy_mode_does_not_mutate_request() -> None:
    req = request(body="path_traversal_indicator")
    before = (req.method, req.path, req.body, req.source_ip)

    inspect_request_with_runtime_selector(req, mode="legacy")

    assert (req.method, req.path, req.body, req.source_ip) == before


# ---------------------------------------------------------------------------
# Default detector integrity
# ---------------------------------------------------------------------------

def test_default_detector_source_has_no_runtime_selector_or_structured_references() -> None:
    source = Path("core/detector.py").read_text(encoding="utf-8")
    forbidden_terms = (
        "runtime_selector",
        "structured_detector",
        "structured_evaluator",
        "inspect_request_with_structured_rules",
        "evaluate_structured_rules",
    )
    for term in forbidden_terms:
        assert term not in source, f"core/detector.py must not reference {term!r}"
