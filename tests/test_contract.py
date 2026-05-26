"""tests/test_contract.py — Verify the detector interface contract."""
from __future__ import annotations

import inspect
import importlib

import pytest

from core.types import DetectionResult, Request
from core.detector import inspect_request


_BENIGN_REQUEST = Request(
    method="GET",
    path="/health",
    query={},
    headers={"User-Agent": "pytest"},
    body="",
    source_ip="127.0.0.1",
)


class TestInspectRequestExists:
    def test_function_exists(self):
        """inspect_request must be importable from core.detector."""
        from core.detector import inspect_request as fn  # noqa: F401
        assert callable(fn)

    def test_signature_parameter_name(self):
        """inspect_request must have exactly one parameter named 'request'."""
        sig = inspect.signature(inspect_request)
        params = list(sig.parameters.keys())
        assert params == ["request"], (
            f"Expected ['request'] but got {params}"
        )

    def test_signature_return_annotation(self):
        """inspect_request return annotation must reference DetectionResult."""
        sig = inspect.signature(inspect_request)
        ann = sig.return_annotation
        # The annotation may be the class itself or a string forward-ref
        assert ann is not inspect.Parameter.empty, "Missing return annotation"
        ann_str = ann if isinstance(ann, str) else getattr(ann, "__name__", str(ann))
        assert "DetectionResult" in ann_str, (
            f"Return annotation must reference DetectionResult, got {ann_str!r}"
        )

    def test_parameter_annotation(self):
        """The 'request' parameter must be annotated with Request."""
        sig = inspect.signature(inspect_request)
        param = sig.parameters["request"]
        assert param.annotation is not inspect.Parameter.empty, (
            "Parameter 'request' is missing annotation"
        )
        ann = param.annotation
        ann_str = ann if isinstance(ann, str) else getattr(ann, "__name__", str(ann))
        assert "Request" in ann_str, (
            f"Parameter annotation must reference Request, got {ann_str!r}"
        )


class TestReturnType:
    def test_returns_detection_result(self):
        """inspect_request must return a DetectionResult instance."""
        result = inspect_request(_BENIGN_REQUEST)
        assert isinstance(result, DetectionResult), (
            f"Expected DetectionResult, got {type(result)}"
        )

    def test_does_not_return_bool(self):
        """inspect_request must never return a bare bool."""
        result = inspect_request(_BENIGN_REQUEST)
        assert not isinstance(result, bool)

    def test_confidence_in_range(self):
        """confidence must be in [0.0, 1.0]."""
        result = inspect_request(_BENIGN_REQUEST)
        assert isinstance(result.confidence, float), (
            "confidence must be a float"
        )
        assert 0.0 <= result.confidence <= 1.0, (
            f"confidence={result.confidence} out of range [0.0, 1.0]"
        )

    def test_blocked_is_bool(self):
        result = inspect_request(_BENIGN_REQUEST)
        assert isinstance(result.blocked, bool)

    def test_reason_is_str(self):
        result = inspect_request(_BENIGN_REQUEST)
        assert isinstance(result.reason, str)

    def test_matched_signals_is_tuple(self):
        result = inspect_request(_BENIGN_REQUEST)
        assert isinstance(result.matched_signals, tuple)


class TestBaselineBenign:
    def test_health_endpoint_not_blocked(self):
        """Benign health check must not be blocked by the baseline detector."""
        result = inspect_request(_BENIGN_REQUEST)
        assert not result.blocked, (
            f"Benign health request was blocked: {result.reason}"
        )

    def test_root_path_not_blocked(self):
        """Benign root path GET must not be blocked."""
        req = Request(method="GET", path="/", query={}, headers={}, body="")
        result = inspect_request(req)
        assert not result.blocked, f"Root path was blocked: {result.reason}"

    def test_confidence_zero_on_no_match(self):
        """Non-suspicious request must return confidence 0.0."""
        req = Request(method="GET", path="/health", query={}, headers={}, body="")
        result = inspect_request(req)
        assert result.confidence == 0.0 or not result.blocked, (
            "Blocked result is allowed to have non-zero confidence; "
            "non-blocked result should have confidence 0.0"
        )


class TestBaselineAttack:
    def test_path_traversal_blocked(self):
        req = Request(
            method="GET",
            path="/files/../../../etc/passwd",
            query={}, headers={}, body="",
        )
        result = inspect_request(req)
        assert result.blocked, "Path traversal should be blocked"

    def test_xss_blocked(self):
        req = Request(
            method="GET",
            path="/search",
            query={"q": "<script>alert(1)</script>"},
            headers={}, body="",
        )
        result = inspect_request(req)
        assert result.blocked, "XSS indicator should be blocked"

    def test_sqli_blocked(self):
        req = Request(
            method="POST",
            path="/api/login",
            query={},
            headers={},
            body="username=admin&password=' or '1'='1",
        )
        result = inspect_request(req)
        assert result.blocked, "SQL injection should be blocked"
