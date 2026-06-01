"""tests/test_gemini_error_diagnostics.py — Tests for _format_gemini_error_detail
and the improved _call_gemini_api error string.

All tests use mocks only.  No real Gemini API calls are made.
No google-genai package is required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.propose_mutation as pm  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_genai_modules(generate_side_effects):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = generate_side_effects
    mock_genai_types = MagicMock()
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_genai.types = mock_genai_types
    return mock_genai, mock_genai_types, mock_client


def _patch_genai(mock_genai, mock_genai_types):
    return patch.dict("sys.modules", {
        "google": MagicMock(genai=mock_genai),
        "google.genai": mock_genai,
        "google.genai.types": mock_genai_types,
    })


# ---------------------------------------------------------------------------
# 1. _format_gemini_error_detail — class name
# ---------------------------------------------------------------------------


class TestFormatGeminiErrorDetailClassName:
    def test_includes_exception_class_name(self) -> None:
        class MyCustomError(Exception):
            pass

        detail = pm._format_gemini_error_detail(MyCustomError("something went wrong"))
        assert "MyCustomError" in detail

    def test_includes_builtin_exception_class_name(self) -> None:
        detail = pm._format_gemini_error_detail(ValueError("bad value"))
        assert "ValueError" in detail

    def test_includes_runtime_error_class_name(self) -> None:
        detail = pm._format_gemini_error_detail(RuntimeError("boom"))
        assert "RuntimeError" in detail


# ---------------------------------------------------------------------------
# 2. _format_gemini_error_detail — status_code / code attribute
# ---------------------------------------------------------------------------


class TestFormatGeminiErrorDetailStatusCode:
    def test_includes_status_code_when_present(self) -> None:
        class FakeClientError(Exception):
            status_code = 403

        detail = pm._format_gemini_error_detail(FakeClientError("Forbidden"))
        assert "403" in detail
        assert "status=403" in detail

    def test_includes_code_attribute_when_no_status_code(self) -> None:
        class FakeCodeError(Exception):
            code = 401

        detail = pm._format_gemini_error_detail(FakeCodeError("Unauthorized"))
        assert "401" in detail
        assert "status=401" in detail

    def test_omits_status_when_not_present(self) -> None:
        detail = pm._format_gemini_error_detail(RuntimeError("plain error"))
        assert "status=" not in detail

    def test_omits_status_when_none(self) -> None:
        class NoStatusError(Exception):
            status_code = None

        detail = pm._format_gemini_error_detail(NoStatusError("no status"))
        assert "status=" not in detail

    def test_omits_status_when_non_integer(self) -> None:
        class StrStatusError(Exception):
            status_code = "403"

        detail = pm._format_gemini_error_detail(StrStatusError("string status"))
        assert "status=" not in detail

    def test_status_code_takes_precedence_over_code(self) -> None:
        class BothAttrsError(Exception):
            status_code = 403
            code = 999

        detail = pm._format_gemini_error_detail(BothAttrsError("both"))
        assert "status=403" in detail
        assert "status=999" not in detail


# ---------------------------------------------------------------------------
# 3. _format_gemini_error_detail — sanitized str(exc) in output
# ---------------------------------------------------------------------------


class TestFormatGeminiErrorDetailMessage:
    def test_includes_exception_message(self) -> None:
        detail = pm._format_gemini_error_detail(RuntimeError("API key not valid"))
        assert "API key not valid" in detail

    def test_includes_status_code_from_message(self) -> None:
        class FakeError(Exception):
            status_code = 400

        detail = pm._format_gemini_error_detail(FakeError("Bad Request: invalid schema"))
        assert "Bad Request" in detail
        assert "invalid schema" in detail

    def test_empty_exception_message_handled(self) -> None:
        detail = pm._format_gemini_error_detail(RuntimeError(""))
        assert "RuntimeError" in detail


# ---------------------------------------------------------------------------
# 4. _format_gemini_error_detail — redacts GEMINI_API_KEY env value
# ---------------------------------------------------------------------------


class TestFormatGeminiErrorDetailRedactsApiKey:
    def test_redacts_gemini_api_key_env_value_in_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "AIza_super_secret_key_value_12345"
        monkeypatch.setenv("GEMINI_API_KEY", secret)

        exc = RuntimeError(f"Request failed: key={secret} was rejected")
        detail = pm._format_gemini_error_detail(exc)
        assert secret not in detail
        assert "[REDACTED]" in detail

    def test_does_not_redact_when_env_key_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        exc = RuntimeError("some safe message without a key value")
        detail = pm._format_gemini_error_detail(exc)
        assert "some safe message without a key value" in detail

    def test_redacts_bearer_token_in_message(self) -> None:
        exc = RuntimeError("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.abc.xyz")
        detail = pm._format_gemini_error_detail(exc)
        assert "eyJhbGciOiJSUzI1NiJ9" not in detail
        assert "[REDACTED]" in detail

    def test_redacts_api_key_assignment_pattern(self) -> None:
        exc = RuntimeError("request rejected: api_key=AIzaSyVeryLongTokenValue12345abcdef")
        detail = pm._format_gemini_error_detail(exc)
        assert "AIzaSyVeryLongTokenValue12345abcdef" not in detail
        assert "[REDACTED]" in detail

    def test_does_not_redact_short_values_in_api_key_pattern(self) -> None:
        exc = RuntimeError("api_key=short")
        detail = pm._format_gemini_error_detail(exc)
        assert "short" in detail


# ---------------------------------------------------------------------------
# 5. _format_gemini_error_detail — truncation
# ---------------------------------------------------------------------------


class TestFormatGeminiErrorDetailTruncation:
    def test_truncates_very_long_message(self) -> None:
        long_msg = "x" * 2000
        detail = pm._format_gemini_error_detail(RuntimeError(long_msg))
        # The detail string itself must not be enormous (class name + status + msg cap)
        # The message portion is capped at _GEMINI_ERROR_MAX_MSG_LEN
        assert len(detail) <= len("RuntimeError: ") + pm._GEMINI_ERROR_MAX_MSG_LEN + len("…") + 5

    def test_truncates_at_default_max_len(self) -> None:
        long_msg = "a" * (pm._GEMINI_ERROR_MAX_MSG_LEN + 100)
        detail = pm._format_gemini_error_detail(RuntimeError(long_msg))
        assert "…" in detail

    def test_does_not_truncate_short_message(self) -> None:
        short_msg = "short error message"
        detail = pm._format_gemini_error_detail(RuntimeError(short_msg))
        assert "…" not in detail
        assert short_msg in detail

    def test_custom_max_len_respected(self) -> None:
        msg = "a" * 100
        detail = pm._format_gemini_error_detail(RuntimeError(msg), max_len=20)
        assert "…" in detail
        # The detail should include at most 20 chars of msg + ellipsis
        assert len(detail) <= len("RuntimeError: ") + 20 + len("…") + 5


# ---------------------------------------------------------------------------
# 6. _call_gemini_api returns error with useful detail on non-transient error
# ---------------------------------------------------------------------------


class TestCallGeminiApiErrorDetail:
    def test_non_transient_error_includes_status_and_message(self) -> None:
        """_call_gemini_api error string includes status code and exception message."""

        class FakeClientError(Exception):
            status_code = 403

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError("API key not valid. Please pass a valid API key."),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            raw_text, inp, out, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert "non-transient" in err
        assert "FakeClientError" in err
        assert "403" in err
        assert "API key not valid" in err

    def test_non_transient_error_without_status_includes_message(self) -> None:
        """Error detail is included even when no status_code attribute is present."""
        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            ValueError("Schema validation failed: unexpected field 'extra'"),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            raw_text, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert "ValueError" in err
        assert "Schema validation failed" in err

    def test_transient_error_detail_also_included(self) -> None:
        """Detail is included for transient errors too (all attempts exhausted)."""

        class Fake429(Exception):
            status_code = 429

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake429("Too Many Requests: quota exceeded"),
            Fake429("Too Many Requests: quota exceeded"),
            Fake429("Too Many Requests: quota exceeded"),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            raw_text, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert "transient" in err
        assert "Fake429" in err
        assert "429" in err
        assert "quota exceeded" in err

    def test_error_does_not_expose_api_key_in_exception_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the exception message somehow contains the API key, it is redacted."""
        secret = "AIza_actual_secret_value_in_exc_msg"
        monkeypatch.setenv("GEMINI_API_KEY", secret)

        class LeakyError(Exception):
            status_code = 401

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            LeakyError(f"Invalid key: {secret}"),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                secret, "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert secret not in err
        assert "[REDACTED]" in err

    def test_error_format_preserves_attempt_count_and_classification(self) -> None:
        """The prefix ('after N attempt(s): transient/non-transient') is unchanged."""

        class Fake403(Exception):
            status_code = 403

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake403("Permission denied"),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert "Gemini API call failed after 1 attempt:" in err
        assert "non-transient error" in err
        assert "Fake403" in err
