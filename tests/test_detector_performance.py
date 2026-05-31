"""tests/test_detector_performance.py — Large-payload regression tests for core/detector.py.

These tests verify that the detector handles larger benign request payloads without
timeout, excessive latency, or accidental detection drift.  All payloads use
neutralized symbolic indicators only — no raw exploit-looking strings.

Payload size budget (CI-safe):
  - Body: 256 KiB maximum
  - Query entries: 100 maximum
  - Header entries: 100 maximum
  - Timing iterations: 5 maximum
"""
from __future__ import annotations

import time
from pathlib import Path

from core.detector import inspect_request
from core.types import DetectionResult, Request


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _benign_request(
    body: str = "",
    query: dict | None = None,
    headers: dict | None = None,
) -> Request:
    return Request(
        method="GET",
        path="/api/data",
        query=query or {},
        headers=headers or {"content-type": "text/plain"},
        body=body,
        source_ip="127.0.0.1",
    )


# ---------------------------------------------------------------------------
# Test 1 — large benign body does not false-positive
# ---------------------------------------------------------------------------

def test_large_benign_body_does_not_block() -> None:
    """A 256 KiB benign body must not be blocked and must produce no matched signals."""
    # ~256 KiB: "benign content word " is 20 chars; 256*1024/20 = 13107 repetitions
    body = "benign content word " * (256 * 1024 // 20)
    request = _benign_request(body=body)

    result = inspect_request(request)

    assert isinstance(result, DetectionResult)
    assert result.blocked is False
    assert result.matched_signals == ()
    assert result.reason  # non-empty string


# ---------------------------------------------------------------------------
# Test 2 — neutralized indicator near end of large body is still detected
# ---------------------------------------------------------------------------

def test_indicator_near_end_of_large_body_is_detected() -> None:
    """A neutralized indicator appended near the end of a large body must still be caught.

    This guards against future mutations that truncate or sample only the
    beginning of the inspection surface, causing a false negative.
    """
    prefix = "benign content word " * (256 * 1024 // 20)  # ~256 KiB prefix
    body = prefix + " path_traversal_indicator"
    request = _benign_request(body=body)

    result = inspect_request(request)

    assert result.blocked is True
    assert "path_traversal_indicator" in result.matched_signals
    assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# Test 3 — large headers and query remain bounded
# ---------------------------------------------------------------------------

def test_large_headers_and_query_do_not_timeout_or_false_positive() -> None:
    """100 query entries and 100 header entries with benign values must not block."""
    query = {f"key_{i}": f"value_{i}" for i in range(100)}
    headers = {f"x-header-{i}": f"headerval-{i}" for i in range(100)}
    request = _benign_request(
        body="modest body content",
        query=query,
        headers=headers,
    )

    result = inspect_request(request)

    assert isinstance(result, DetectionResult)
    assert result.blocked is False


# ---------------------------------------------------------------------------
# Test 4 — detector latency stays below a loose ceiling
# ---------------------------------------------------------------------------

def test_large_payload_latency_budget_is_reasonable() -> None:
    """Inspecting a 256 KiB benign request must complete within a loose latency budget.

    Threshold: 500 ms max per call (over 5 iterations).
    This is a regression guard, not a microbenchmark.
    """
    body = "benign content word " * (256 * 1024 // 20)  # ~256 KiB
    request = _benign_request(body=body)

    elapsed_times: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        inspect_request(request)
        elapsed_times.append(time.perf_counter() - t0)

    max_elapsed_s = max(elapsed_times)
    assert max_elapsed_s < 0.5, (
        f"Detector took {max_elapsed_s * 1000:.1f} ms on a 256 KiB body "
        "(threshold: 500 ms). This may indicate a pathological regression."
    )


# ---------------------------------------------------------------------------
# Test 5 — no raw exploit payloads in this test file
# ---------------------------------------------------------------------------

def test_this_file_uses_only_neutralized_indicators() -> None:
    """Verify this test file contains no raw exploit-looking strings.

    Patterns are assembled at runtime so they do not appear as literals in the
    source, which would cause this self-check to trivially fail.

    Allowed: path_traversal_indicator, script_injection_indicator, sqli_indicator,
    command_delimiter_indicator, encoded_traversal_indicator.
    """
    source = Path(__file__).read_text(encoding="utf-8")

    # Assembled at runtime — these patterns must not appear literally in this file.
    forbidden_patterns = [
        "." * 2 + "/",              # path traversal raw token
        "<" + "script" + ">",       # XSS raw token
        "select " + "* " + "from",  # SQLi raw token
        "eval" + "(",               # eval call raw token
    ]

    for pattern in forbidden_patterns:
        count = source.count(pattern)
        assert count == 0, (
            f"Test file must not contain raw exploit-looking string: {pattern!r}. "
            "Use neutralized symbolic indicators (e.g. path_traversal_indicator) instead."
        )
