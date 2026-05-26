"""tests/test_types.py — Verify deep immutability of the Request type.

Request.query and Request.headers must be stored as MappingProxyType so that
neither the mapping nor the values can be mutated after construction.  This
prevents candidate code from accidentally (or intentionally) modifying shared
request state across evaluation calls.
"""
from __future__ import annotations

from types import MappingProxyType

import pytest

from core.types import DetectionResult, Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(**kwargs) -> Request:
    defaults = dict(
        method="GET",
        path="/test",
        query={},
        headers={},
        body="",
    )
    defaults.update(kwargs)
    return Request(**defaults)


# ---------------------------------------------------------------------------
# Request immutability tests
# ---------------------------------------------------------------------------

class TestRequestQueryImmutability:
    def test_query_is_mapping_proxy(self):
        req = _make_request(query={"k": "v"})
        assert isinstance(req.query, MappingProxyType), (
            "request.query must be a MappingProxyType"
        )

    def test_query_write_raises_type_error(self):
        req = _make_request(query={"k": "v"})
        with pytest.raises(TypeError):
            req.query["k"] = "mutated"  # type: ignore[index]

    def test_query_delete_raises_type_error(self):
        req = _make_request(query={"k": "v"})
        with pytest.raises(TypeError):
            del req.query["k"]  # type: ignore[attr-defined]

    def test_query_set_new_key_raises_type_error(self):
        req = _make_request(query={})
        with pytest.raises(TypeError):
            req.query["new_key"] = "value"  # type: ignore[index]

    def test_original_dict_mutation_does_not_affect_request(self):
        """Mutating the dict passed to the constructor must not affect query."""
        d = {"original": "value"}
        req = _make_request(query=d)
        d["original"] = "mutated"
        d["extra"] = "injected"
        assert req.query["original"] == "value", (
            "Mutation of the source dict after construction must not affect request.query"
        )
        assert "extra" not in req.query, (
            "Keys added to source dict after construction must not appear in request.query"
        )

    def test_query_preserves_values(self):
        req = _make_request(query={"a": "1", "b": "2"})
        assert req.query["a"] == "1"
        assert req.query["b"] == "2"

    def test_empty_query_is_proxy(self):
        req = _make_request(query={})
        assert isinstance(req.query, MappingProxyType)
        assert len(req.query) == 0


class TestRequestHeadersImmutability:
    def test_headers_is_mapping_proxy(self):
        req = _make_request(headers={"Content-Type": "application/json"})
        assert isinstance(req.headers, MappingProxyType), (
            "request.headers must be a MappingProxyType"
        )

    def test_headers_write_raises_type_error(self):
        req = _make_request(headers={"X-Custom": "value"})
        with pytest.raises(TypeError):
            req.headers["X-Custom"] = "mutated"  # type: ignore[index]

    def test_headers_delete_raises_type_error(self):
        req = _make_request(headers={"X-Custom": "value"})
        with pytest.raises(TypeError):
            del req.headers["X-Custom"]  # type: ignore[attr-defined]

    def test_headers_set_new_key_raises_type_error(self):
        req = _make_request(headers={})
        with pytest.raises(TypeError):
            req.headers["Authorization"] = "Bearer token"  # type: ignore[index]

    def test_original_dict_mutation_does_not_affect_request(self):
        d = {"Content-Type": "text/html"}
        req = _make_request(headers=d)
        d["Content-Type"] = "application/json"
        d["X-Injected"] = "evil"
        assert req.headers["Content-Type"] == "text/html", (
            "Mutation of the source dict after construction must not affect request.headers"
        )
        assert "X-Injected" not in req.headers, (
            "Keys injected into source dict must not appear in request.headers"
        )

    def test_headers_preserves_values(self):
        req = _make_request(headers={"A": "1", "B": "2"})
        assert req.headers["A"] == "1"
        assert req.headers["B"] == "2"


class TestRequestFrozenDataclass:
    def test_method_is_immutable(self):
        req = _make_request(method="GET")
        with pytest.raises((TypeError, AttributeError)):
            req.method = "POST"  # type: ignore[misc]

    def test_path_is_immutable(self):
        req = _make_request(path="/original")
        with pytest.raises((TypeError, AttributeError)):
            req.path = "/mutated"  # type: ignore[misc]

    def test_body_is_immutable(self):
        req = _make_request(body="original body")
        with pytest.raises((TypeError, AttributeError)):
            req.body = "mutated body"  # type: ignore[misc]

    def test_query_field_is_immutable(self):
        """Cannot replace the entire query mapping."""
        req = _make_request(query={"k": "v"})
        with pytest.raises((TypeError, AttributeError)):
            req.query = {}  # type: ignore[misc]

    def test_headers_field_is_immutable(self):
        """Cannot replace the entire headers mapping."""
        req = _make_request(headers={"H": "v"})
        with pytest.raises((TypeError, AttributeError)):
            req.headers = {}  # type: ignore[misc]


class TestDetectionResultImmutability:
    def test_blocked_is_immutable(self):
        r = DetectionResult(blocked=True, reason="test", confidence=0.8, matched_signals=())
        with pytest.raises((TypeError, AttributeError)):
            r.blocked = False  # type: ignore[misc]

    def test_confidence_is_immutable(self):
        r = DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
        with pytest.raises((TypeError, AttributeError)):
            r.confidence = 0.9  # type: ignore[misc]

    def test_matched_signals_is_tuple(self):
        r = DetectionResult(blocked=True, reason="m", confidence=0.9, matched_signals=("a", "b"))
        assert isinstance(r.matched_signals, tuple)


class TestRequestDetectorCompatibility:
    """Ensure that the real detector works correctly with the immutable Request."""

    def test_detector_accepts_proxy_request(self):
        from core.detector import inspect_request
        req = _make_request(query={"k": "safe"}, headers={"X-H": "v"})
        result = inspect_request(req)
        assert isinstance(result, DetectionResult)

    def test_detector_does_not_mutate_query(self):
        from core.detector import inspect_request
        req = _make_request(query={"k": "safe"})
        original_keys = set(req.query.keys())
        inspect_request(req)
        assert set(req.query.keys()) == original_keys, (
            "Detector must not mutate request.query"
        )

    def test_detector_does_not_mutate_headers(self):
        from core.detector import inspect_request
        req = _make_request(headers={"X-Header": "value"})
        original_keys = set(req.headers.keys())
        inspect_request(req)
        assert set(req.headers.keys()) == original_keys, (
            "Detector must not mutate request.headers"
        )
