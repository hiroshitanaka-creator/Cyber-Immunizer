"""tests/test_detector_case_normalization.py

Contract tests proving that neutralized threat indicators are matched
case-insensitively and that matched_signals remain normalized lowercase.

All indicators are symbolic/neutralized — no raw exploit strings.
No network calls, no process calls, no real API calls.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from core.detector import inspect_request
from core.types import DetectionResult, Request

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Canonical definitions
# ---------------------------------------------------------------------------

_LOWERCASE_INDICATORS: list[str] = [
    "path_traversal_indicator",
    "script_injection_indicator",
    "sqli_indicator",
    "command_delimiter_indicator",
    "encoded_traversal_indicator",
]

_UPPERCASE_INDICATORS: list[str] = [ind.upper() for ind in _LOWERCASE_INDICATORS]

_MIXEDCASE_INDICATORS: list[str] = [
    "PaTh_TrAvErSaL_InDiCaToR",
    "ScRiPt_InJeCtIoN_InDiCaToR",
    "SqLi_InDiCaToR",
    "CoMmAnD_DeLiMiTeR_InDiCaToR",
    "EnCoDeD_TrAvErSaL_InDiCaToR",
]


def _make_request(
    *,
    path: str = "/",
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    body: str = "",
) -> Request:
    return Request(
        method="GET",
        path=path,
        query=query or {},
        headers=headers or {},
        body=body,
    )


# ---------------------------------------------------------------------------
# Test 1 — uppercase fixture-style indicators are detected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", _UPPERCASE_INDICATORS)
def test_uppercase_fixture_style_indicators_are_detected(indicator: str) -> None:
    """Uppercase symbolic indicators must be blocked; matched_signals hold lowercase form."""
    canonical = indicator.lower()

    # Place indicator in path
    result_path = inspect_request(_make_request(path=f"/api/{indicator}"))
    assert isinstance(result_path, DetectionResult)
    assert result_path.blocked is True
    assert canonical in result_path.matched_signals

    # Place indicator in query
    result_query = inspect_request(_make_request(query={"q": indicator}))
    assert result_query.blocked is True
    assert canonical in result_query.matched_signals

    # Place indicator in body
    result_body = inspect_request(_make_request(body=f"data={indicator}"))
    assert result_body.blocked is True
    assert canonical in result_body.matched_signals


# ---------------------------------------------------------------------------
# Test 2 — mixed-case indicators are detected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mixed, canonical",
    list(zip(_MIXEDCASE_INDICATORS, _LOWERCASE_INDICATORS)),
)
def test_mixed_case_indicators_are_detected(mixed: str, canonical: str) -> None:
    """Mixed-case symbolic indicators must be blocked; matched_signals hold lowercase form."""
    # Place in path
    result_path = inspect_request(_make_request(path=f"/api/{mixed}"))
    assert result_path.blocked is True
    assert canonical in result_path.matched_signals

    # Place in query
    result_query = inspect_request(_make_request(query={"input": mixed}))
    assert result_query.blocked is True
    assert canonical in result_query.matched_signals

    # Place in headers
    result_headers = inspect_request(
        _make_request(headers={"X-Custom-Header": mixed})
    )
    assert result_headers.blocked is True
    assert canonical in result_headers.matched_signals

    # Place in body
    result_body = inspect_request(_make_request(body=f"payload={mixed}"))
    assert result_body.blocked is True
    assert canonical in result_body.matched_signals


# ---------------------------------------------------------------------------
# Test 3 — matched_signals are normalized lowercase
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", _UPPERCASE_INDICATORS + _MIXEDCASE_INDICATORS)
def test_matched_signals_are_lowercase_canonical(indicator: str) -> None:
    """Every item in matched_signals must be lowercase; the raw input form must not appear."""
    result = inspect_request(_make_request(path=f"/check/{indicator}"))
    assert result.blocked is True
    for signal in result.matched_signals:
        assert signal == signal.lower(), (
            f"matched_signals must be lowercase; got {signal!r}"
        )
    # The uppercase/mixed input form itself must not be echoed verbatim
    assert indicator not in result.matched_signals


# ---------------------------------------------------------------------------
# Test 4 — JSON attack fixtures remain compatible with detector normalization
# ---------------------------------------------------------------------------


def _build_request_from_json(req_obj: dict) -> Request:
    return Request(
        method=req_obj.get("method", "GET"),
        path=req_obj.get("path", "/"),
        query=req_obj.get("query") or {},
        headers=req_obj.get("headers") or {},
        body=req_obj.get("body") or "",
        source_ip=req_obj.get("source_ip"),
    )


def test_attack_request_fixtures_with_uppercase_indicators_still_block() -> None:
    """All attack_requests.json cases with expected_blocked=true must still block."""
    fixture_path = REPO_ROOT / "data" / "attack_requests.json"
    cases = json.loads(fixture_path.read_text())
    blocking_cases = [c for c in cases if c.get("expected_blocked") is True]
    assert blocking_cases, "attack_requests.json must contain at least one expected_blocked=true case"
    for case in blocking_cases:
        request = _build_request_from_json(case["request"])
        result = inspect_request(request)
        assert result.blocked is True, (
            f"Case {case['id']!r}: expected blocked=True but got blocked={result.blocked}"
        )
        assert result.matched_signals, (
            f"Case {case['id']!r}: expected non-empty matched_signals but got {result.matched_signals!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 — JSON regression fixtures remain compatible with detector normalization
# ---------------------------------------------------------------------------


def test_regression_case_fixtures_with_uppercase_indicators_still_match_contract() -> None:
    """regression_cases.json cases must satisfy blocked==expected_blocked contract."""
    fixture_path = REPO_ROOT / "data" / "regression_cases.json"
    cases = json.loads(fixture_path.read_text())
    assert cases, "regression_cases.json must be non-empty"
    for case in cases:
        expected = case["expected_blocked"]
        request = _build_request_from_json(case["request"])
        result = inspect_request(request)
        assert result.blocked is expected, (
            f"Case {case['id']!r}: expected blocked={expected} but got blocked={result.blocked}"
        )
        if expected:
            assert result.matched_signals, (
                f"Case {case['id']!r}: expected non-empty matched_signals but got {result.matched_signals!r}"
            )
        else:
            assert result.matched_signals == (), (
                f"Case {case['id']!r}: expected empty matched_signals but got {result.matched_signals!r}"
            )


# ---------------------------------------------------------------------------
# Test 6 — benign uppercase text does not false-positive
# ---------------------------------------------------------------------------


_BENIGN_INPUTS = [
    ("path", "/STATUS_OK/HEALTH_CHECK_READY"),
    ("query", {"status": "NORMAL_STATUS_OK"}),
    ("headers", {"X-Client": "USER_AGENT_TEST"}),
    ("body", "ACTION=SUBMIT&RESULT=SUCCESS_CONFIRMED"),
]


@pytest.mark.parametrize("field,value", _BENIGN_INPUTS)
def test_benign_uppercase_non_indicator_text_does_not_block(
    field: str, value: object
) -> None:
    """Uppercase text that is not a known indicator must not be blocked."""
    if field == "path":
        request = _make_request(path=str(value))
    elif field == "query":
        request = _make_request(query=dict(value))  # type: ignore[arg-type]
    elif field == "headers":
        request = _make_request(headers=dict(value))  # type: ignore[arg-type]
    else:
        request = _make_request(body=str(value))

    result = inspect_request(request)
    assert result.blocked is False, (
        f"Benign input in {field!r} must not be blocked; got blocked=True, "
        f"matched_signals={result.matched_signals!r}"
    )
    assert result.matched_signals == ()


# ---------------------------------------------------------------------------
# Test 7 — this test file contains no raw exploit-looking strings
# ---------------------------------------------------------------------------


def test_this_file_uses_only_neutralized_indicators() -> None:
    """The source of this test file must not contain raw exploit-looking strings."""
    this_file = pathlib.Path(__file__)
    source = this_file.read_text()

    # Forbidden patterns are assembled at runtime so they do not appear literally.
    forbidden_patterns: list[str] = [
        ".." + "/",
        "<" + "script" + ">",
        "select" + " * from",
        "eval" + "(",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in source, (
            f"Test file must not contain raw exploit-looking string: {pattern!r}"
        )
