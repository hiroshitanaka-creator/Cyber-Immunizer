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


# ---------------------------------------------------------------------------
# 7. Codex P2 — prompt / request-payload redaction
# ---------------------------------------------------------------------------


class TestCodexP2PromptRedaction:
    """Codex P2: str(exc) must never expose submitted prompt text in error output.

    If the google-genai SDK echoes back the request payload (user prompt,
    system prompt, or contents array) in an exception message, the formatter
    must strip those fragments before they reach the returned error string,
    the ledger, or CI logs.
    """

    # --- _sanitize_gemini_error_message direct tests ---

    def test_sanitizer_strips_exact_forbidden_user_prompt(self) -> None:
        user_prompt = "Inspect this detector code and propose a mutation."
        raw = f"400 Bad Request: field error in contents[0].parts[0].text='{user_prompt}'"
        sanitized = pm._sanitize_gemini_error_message(raw, forbidden_substrings=(user_prompt,))
        assert user_prompt not in sanitized

    def test_sanitizer_strips_exact_forbidden_system_prompt(self) -> None:
        system_prompt = "You are a defensive security code assistant."
        raw = f"Request rejected — system_instruction='{system_prompt}' is too long"
        sanitized = pm._sanitize_gemini_error_message(raw, forbidden_substrings=(system_prompt,))
        assert system_prompt not in sanitized

    def test_sanitizer_strips_contents_payload_section(self) -> None:
        raw = 'Error: "contents": [{"role": "user", "parts": [{"text": "secret prompt"}]}]'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "secret prompt" not in sanitized
        assert "[contents redacted]" in sanitized

    def test_sanitizer_strips_current_mutation_region(self) -> None:
        raw = (
            "400 Bad Request — Current mutation region:\n"
            "    return DetectionResult(blocked=False, reason='no match', "
            "confidence=0.0, matched_signals=())\n"
            "End of payload"
        )
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "Current mutation region" not in sanitized
        assert "DetectionResult" not in sanitized
        assert "[mutation region redacted]" in sanitized

    def test_sanitizer_strips_mutation_start_marker(self) -> None:
        raw = "Payload too large: === MUTATION_START ===\n    pass\n=== MUTATION_END ==="
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "MUTATION_START" not in sanitized
        assert "pass" not in sanitized

    def test_sanitizer_preserves_status_code_after_forbidden_strip(self) -> None:
        user_prompt = "very secret prompt text"
        raw = f"403 PERMISSION_DENIED: contents contained '{user_prompt}'"
        sanitized = pm._sanitize_gemini_error_message(raw, forbidden_substrings=(user_prompt,))
        assert user_prompt not in sanitized
        assert "403" in sanitized

    def test_sanitizer_preserves_api_error_code_after_strip(self) -> None:
        user_prompt = "detect path traversal"
        raw = f"400 INVALID_ARGUMENT: schema mismatch in field from '{user_prompt}'"
        sanitized = pm._sanitize_gemini_error_message(raw, forbidden_substrings=(user_prompt,))
        assert user_prompt not in sanitized
        assert "INVALID_ARGUMENT" in sanitized

    def test_sanitizer_noop_when_no_forbidden_substrings(self) -> None:
        raw = "403 PERMISSION_DENIED: API_KEY_INVALID"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sanitized == raw

    # --- _format_gemini_error_detail with forbidden_substrings ---

    def test_formatter_strips_user_prompt_from_exception_message(self) -> None:
        user_prompt = "Please propose a mutation for this detector."
        exc = RuntimeError(
            f"400 Bad Request: contents[0].text = '{user_prompt}' is invalid"
        )
        detail = pm._format_gemini_error_detail(
            exc, forbidden_substrings=(user_prompt,)
        )
        assert user_prompt not in detail

    def test_formatter_strips_llm_system_prompt_from_exception_message(self) -> None:
        system_prompt = pm._LLM_SYSTEM_PROMPT
        # Embed the full system prompt in the exception message, then verify that
        # neither the full string nor its opening sentinel survives in the output.
        sentinel = system_prompt[:80] if len(system_prompt) >= 80 else system_prompt
        exc = RuntimeError(f"Request rejected: system_instruction='{system_prompt}'")
        detail = pm._format_gemini_error_detail(
            exc, forbidden_substrings=(system_prompt,)
        )
        assert sentinel not in detail

    def test_formatter_status_code_present_after_forbidden_strip(self) -> None:
        class FakeClientError(Exception):
            status_code = 403

        user_prompt = "user prompt content that must not leak"
        exc = FakeClientError(
            f"PERMISSION_DENIED: prompt '{user_prompt}' was rejected"
        )
        detail = pm._format_gemini_error_detail(
            exc, forbidden_substrings=(user_prompt,)
        )
        assert user_prompt not in detail
        assert "status=403" in detail

    def test_formatter_detector_mutation_region_stripped(self) -> None:
        mutation_region = (
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no suspicious indicator matched',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )"
        )
        exc = RuntimeError(
            f"400 Bad Request: Current mutation region:\n{mutation_region}\nEnd"
        )
        detail = pm._format_gemini_error_detail(exc)
        assert "DetectionResult" not in detail
        assert "blocked=False" not in detail

    # --- _call_gemini_api end-to-end: prompt must not appear in error ---

    def test_call_gemini_api_does_not_expose_user_prompt_in_error(self) -> None:
        """If the SDK echoes back the user prompt in the exception, it is stripped."""
        user_prompt = "TOP SECRET DETECTOR PROMPT CONTENT MUST NOT LEAK"

        class FakeClientError(Exception):
            status_code = 400

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f"400 INVALID_ARGUMENT: contents[0].text = '{user_prompt}'"
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", user_prompt, 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert user_prompt not in err
        assert "400" in err or "FakeClientError" in err

    def test_call_gemini_api_does_not_expose_system_prompt_in_error(self) -> None:
        """If the SDK echoes back the full system prompt in the exception, it is stripped."""
        # Embed the full system prompt in the exception so forbidden_substrings
        # can match and replace it.  Then verify the opening sentinel is gone.
        system_sentinel = pm._LLM_SYSTEM_PROMPT[:60]

        class FakeClientError(Exception):
            status_code = 400

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f"400 INVALID_ARGUMENT: system_instruction='{pm._LLM_SYSTEM_PROMPT}'"
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "safe prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert system_sentinel not in err

    def test_call_gemini_api_status_code_still_present_after_prompt_strip(self) -> None:
        """Status code remains in the error even when prompt text is stripped."""
        user_prompt = "secret prompt that must not appear in logs"

        class FakeClientError(Exception):
            status_code = 403

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f"403 PERMISSION_DENIED: prompt '{user_prompt}' rejected"
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", user_prompt, 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert user_prompt not in err
        assert "403" in err


# ---------------------------------------------------------------------------
# 8. Codex P2 (extended) — JSON/repr-encoded prompt-carrying fields
# ---------------------------------------------------------------------------


class TestCodexP2JsonEncoding:
    """JSON/repr-encoded system_instruction and related request fields must be redacted.

    If the google-genai SDK echoes a JSON request body in an error message, the
    system prompt may appear as:
        "system_instruction": "You are a defensive security code assistant..."
    with \\n sequences for newlines.  The verbatim forbidden_substrings pass
    (step 1) cannot match JSON-encoded forms; the structural JSON key-value
    patterns (step 5) must catch them.
    """

    # --- _sanitize_gemini_error_message: JSON double-quoted form ---

    def test_json_double_quoted_system_instruction_redacted(self) -> None:
        """JSON "system_instruction": "..." containing a prompt fragment is redacted."""
        sentinel = pm._LLM_SYSTEM_PROMPT[:60]
        raw = f'"system_instruction": "{sentinel}"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[system instruction redacted]" in sanitized

    def test_json_escaped_newlines_in_system_instruction_redacted(self) -> None:
        """JSON-encoded system_instruction with \\n escape sequences is redacted."""
        import json as _json
        # A multi-line system-prompt-like value — json.dumps adds outer quotes
        # and converts real newlines to \\n sequences.
        multi_line = "Security assistant.\nStrict rules.\nNever expose secrets."
        json_encoded = _json.dumps(multi_line)  # e.g. '"Security assistant.\\nStrict rules.\\n..."'
        raw = '"system_instruction": ' + json_encoded
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "Security assistant" not in sanitized
        assert "Strict rules" not in sanitized
        assert "[system instruction redacted]" in sanitized

    # --- _sanitize_gemini_error_message: Python single-quoted form ---

    def test_single_quoted_system_instruction_redacted(self) -> None:
        """Python repr 'system_instruction': '...' is redacted."""
        sentinel = "You are a defensive security"
        raw = f"'system_instruction': '{sentinel}'"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[system instruction redacted]" in sanitized

    # --- _sanitize_gemini_error_message: assignment-style ---

    def test_assignment_style_system_instruction_redacted(self) -> None:
        """Assignment-style system_instruction="..." is redacted."""
        sentinel = "You are a defensive assistant"
        raw = f'system_instruction="{sentinel} — with details"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[system instruction redacted]" in sanitized

    # --- "parts" and "text" fields ---

    def test_parts_array_redacted(self) -> None:
        """JSON "parts": [...] payload is redacted."""
        raw = '"parts": [{"text": "This is the submitted prompt content"}]'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "submitted prompt content" not in sanitized
        assert "[parts redacted]" in sanitized

    def test_text_field_redacted(self) -> None:
        """JSON "text": "..." field carrying prompt text is redacted."""
        raw = '"text": "Improve coverage for path-traversal patterns."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "Improve coverage" not in sanitized
        assert "[text redacted]" in sanitized

    def test_single_quoted_text_field_redacted(self) -> None:
        """Python repr 'text': '...' field is redacted."""
        raw = "'text': 'Detect SQL injection patterns.'"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "Detect SQL injection" not in sanitized
        assert "[text redacted]" in sanitized

    # --- Safe API diagnostics must survive ---

    def test_permission_denied_survives_redaction(self) -> None:
        """PERMISSION_DENIED API error reason is preserved after field redaction."""
        sentinel = pm._LLM_SYSTEM_PROMPT[:50]
        raw = f'403 PERMISSION_DENIED: "system_instruction": "{sentinel}"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "PERMISSION_DENIED" in sanitized

    def test_status_code_and_error_code_survive_redaction(self) -> None:
        """Status code and API error code survive JSON field redaction."""
        raw = '400 INVALID_ARGUMENT: "system_instruction": "some prompt text"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "some prompt text" not in sanitized
        assert "400" in sanitized
        assert "INVALID_ARGUMENT" in sanitized

    def test_api_key_invalid_message_not_over_redacted(self) -> None:
        """API_KEY_INVALID and short API error messages are not over-redacted."""
        raw = "401 UNAUTHENTICATED: API_KEY_INVALID"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "API_KEY_INVALID" in sanitized
        assert "UNAUTHENTICATED" in sanitized

    def test_safe_message_with_no_prompt_fields_unchanged(self) -> None:
        """A message with no prompt-carrying fields passes through unchanged."""
        raw = "403 PERMISSION_DENIED: billing account required"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sanitized == raw

    # --- _call_gemini_api end-to-end ---

    def test_call_gemini_api_json_system_instruction_not_in_error(self) -> None:
        """_call_gemini_api: ClientError echoing JSON system_instruction → stripped."""
        sentinel = pm._LLM_SYSTEM_PROMPT[:60]

        class FakeClientError(Exception):
            status_code = 400

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f'400 INVALID_ARGUMENT: {{"system_instruction": "{sentinel}"}}'
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "safe user prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert sentinel not in err
        assert "400" in err or "FakeClientError" in err


# ---------------------------------------------------------------------------
# 9. TestCodexP2ReprStyle
#    Python repr / bare-assignment text= and parts= forms must be redacted.
# ---------------------------------------------------------------------------


class TestCodexP2ReprStyle:
    """Bare assignment-style text= and parts= in Python repr must be redacted.

    The google-genai SDK may surface error strings that include a Python repr
    of the request object, e.g.:

        Part(text='You are a defensive security code assistant...')
        GenerateContentConfig(..., parts=[Part(text='detector prompt...')])

    Step 5 of _sanitize_gemini_error_message must catch bare text= / parts=
    forms (in addition to JSON-quoted "text": / "parts": forms) so prompt text
    in repr-style echoes never reaches the ledger or logs.
    """

    def test_bare_text_equals_single_quoted_redacted(self) -> None:
        """text='...' (bare key, single-quoted value) is redacted."""
        raw = "text='You are a defensive security code assistant.'"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "You are a defensive" not in sanitized
        assert "[text redacted]" in sanitized

    def test_bare_text_equals_double_quoted_redacted(self) -> None:
        """text=\"...\" (bare key, double-quoted value) is redacted."""
        raw = 'text="You are a defensive security code assistant."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "You are a defensive" not in sanitized
        assert "[text redacted]" in sanitized

    def test_part_repr_text_field_redacted(self) -> None:
        """Part(text='...') Python repr form is redacted."""
        sentinel = "detector mutation region sentinel XYZ"
        raw = f"Part(text='{sentinel}')"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[text redacted]" in sanitized

    def test_generate_content_config_parts_repr_redacted(self) -> None:
        """GenerateContentConfig repr with parts=[Part(text='...')] is redacted."""
        sentinel = "secret-prompt-content-ABC"
        raw = f"GenerateContentConfig(system_instruction=..., parts=[Part(text='{sentinel}')])"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized

    def test_bare_parts_equals_list_redacted(self) -> None:
        """parts=['...'] (bare key, list value) is redacted."""
        raw = "parts=['prompt part one', 'prompt part two']"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "prompt part one" not in sanitized
        assert "[parts redacted]" in sanitized

    def test_context_word_not_false_positive(self) -> None:
        """The word 'context' in an error message is not incorrectly redacted."""
        raw = "Error context: invalid parameter value for the request"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "context" in sanitized
        assert sanitized == raw

    def test_status_code_survives_repr_redaction(self) -> None:
        """HTTP status code and API error code survive repr-style text redaction."""
        raw = "400 INVALID_ARGUMENT: Part(text='prompt text')"
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "prompt text" not in sanitized
        assert "400" in sanitized
        assert "INVALID_ARGUMENT" in sanitized


# ---------------------------------------------------------------------------
# 10. TestCodexP2IndexedFieldPaths
#    Indexed request field path forms such as contents[0].parts[0].text must
#    be redacted by _sanitize_gemini_error_message.
# ---------------------------------------------------------------------------


class TestCodexP2IndexedFieldPaths:
    """Indexed field path echo from SDK/API errors must be redacted.

    The google-genai SDK or HTTP layer may echo the submitted request body as
    dotted/indexed paths in error messages, for example:

        contents[0].parts[0].text = "You are a defensive security..."
        request.contents[0].parts[0].text: "detector mutation region..."
        system_instruction.parts[0].text = "You are..."

    Step 7 of _sanitize_gemini_error_message must catch these forms so prompt
    text and detector mutation regions never reach the ledger or logs.
    """

    # --- bracket-index, equals separator ---

    def test_contents_bracket_equals_redacted(self) -> None:
        """contents[0].parts[0].text = '...' is redacted."""
        raw = 'contents[0].parts[0].text = "This is the detector prompt text."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "detector prompt text" not in sanitized
        assert "[text redacted]" in sanitized

    # --- bracket-index, colon separator ---

    def test_contents_bracket_colon_redacted(self) -> None:
        """contents[0].parts[0].text: '...' (colon separator) is redacted."""
        raw = 'contents[0].parts[0].text: "This is the detector prompt text."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "detector prompt text" not in sanitized
        assert "[text redacted]" in sanitized

    # --- dot-numeric index notation ---

    def test_contents_dot_numeric_index_redacted(self) -> None:
        """contents.0.parts.0.text = '...' (dot-numeric index) is redacted."""
        raw = 'contents.0.parts.0.text = "This is the detector prompt text."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "detector prompt text" not in sanitized
        assert "[text redacted]" in sanitized

    # --- request.contents prefix ---

    def test_request_contents_indexed_redacted(self) -> None:
        """request.contents[0].parts[0].text = '...' is redacted."""
        raw = 'request.contents[0].parts[0].text = "This is the detector prompt text."'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "detector prompt text" not in sanitized
        assert "[text redacted]" in sanitized

    # --- system_instruction path ---

    def test_system_instruction_parts_text_redacted(self) -> None:
        """system_instruction.parts[0].text = '...' yields [system instruction redacted]."""
        sentinel = "You are a defensive security code assistant"
        raw = f'system_instruction.parts[0].text = "{sentinel} — confidential"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[system instruction redacted]" in sanitized
        assert "[text redacted]" not in sanitized

    # --- escaped characters in value ---

    def test_escaped_chars_in_indexed_text_redacted(self) -> None:
        """Escaped newlines/quotes inside an indexed text value are redacted."""
        import json as _json
        json_val = _json.dumps("Line1\nLine2 with \"quotes\"")
        raw = "contents[0].parts[0].text = " + json_val
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "Line1" not in sanitized
        assert "Line2" not in sanitized
        assert "[text redacted]" in sanitized

    # --- safe diagnostic fields survive ---

    def test_status_code_survives_indexed_redaction(self) -> None:
        """HTTP status code and API error code survive indexed text-field redaction."""
        raw = '400 INVALID_ARGUMENT: contents[0].parts[0].text = "prompt text"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "prompt text" not in sanitized
        assert "400" in sanitized
        assert "INVALID_ARGUMENT" in sanitized

    def test_permission_denied_survives_indexed_redaction(self) -> None:
        """PERMISSION_DENIED API reason is preserved after indexed text-field redaction."""
        raw = '403 PERMISSION_DENIED: request.contents[0].parts[0].text = "secret"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "secret" not in sanitized
        assert "PERMISSION_DENIED" in sanitized

    # --- _call_gemini_api end-to-end ---

    def test_call_gemini_api_indexed_contents_text_not_in_error(self) -> None:
        """_call_gemini_api: ClientError with indexed contents[0].parts[0].text → stripped."""
        sentinel = "detector-mutation-region-sentinel-XYZ"

        class FakeClientError(Exception):
            status_code = 400

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f'400 INVALID_ARGUMENT: contents[0].parts[0].text = "{sentinel}"'
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "safe user prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert sentinel not in err
        assert "[text redacted]" in err

    # --- additional coverage: dot-numeric index forms ---

    def test_request_contents_dot_numeric_colon_redacted(self) -> None:
        """request.contents.0.parts.0.text: '...' (dot-numeric index, colon) is redacted."""
        raw = 'request.contents.0.parts.0.text: "detector prompt text"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "detector prompt text" not in sanitized
        assert "[text redacted]" in sanitized

    def test_system_instruction_parts_dot_numeric_colon_redacted(self) -> None:
        """system_instruction.parts.0.text: '...' (dot-numeric index, colon) is redacted."""
        sentinel = "You are a defensive security code assistant"
        raw = f'system_instruction.parts.0.text: "{sentinel} — top secret"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert sentinel not in sanitized
        assert "[system instruction redacted]" in sanitized
        assert "[text redacted]" not in sanitized

    def test_parts_bracket_equals_redacted(self) -> None:
        """Standalone parts[0].text = '...' is redacted."""
        raw = 'parts[0].text = "prompt text here"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "prompt text here" not in sanitized
        assert "[text redacted]" in sanitized

    def test_parts_dot_numeric_colon_redacted(self) -> None:
        """Standalone parts.0.text: '...' (dot-numeric, colon) is redacted."""
        raw = 'parts.0.text: "prompt text here"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "prompt text here" not in sanitized
        assert "[text redacted]" in sanitized

    # --- mutation region markers inside indexed text values ---

    def test_mutation_region_marker_in_indexed_text_redacted(self) -> None:
        """Mutation region marker inside an indexed text value is redacted."""
        raw = r'contents[0].parts[0].text = "Current mutation region: import os; os.system(\"rm\")"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "import os" not in sanitized
        assert "Current mutation region" not in sanitized

    def test_mutation_start_marker_in_indexed_text_redacted(self) -> None:
        """MUTATION_START marker inside an indexed text value is redacted."""
        raw = r'contents[0].parts[0].text = "=== MUTATION_START === some injected code"'
        sanitized = pm._sanitize_gemini_error_message(raw)
        assert "some injected code" not in sanitized
        assert "MUTATION_START" not in sanitized

    # --- _call_gemini_api end-to-end with system_instruction path ---

    def test_call_gemini_api_system_instruction_parts_text_not_in_error(self) -> None:
        """_call_gemini_api: ClientError with system_instruction.parts[0].text → stripped."""
        sentinel = pm._LLM_SYSTEM_PROMPT[:60]

        class FakeClientError(Exception):
            status_code = 400

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            FakeClientError(
                f'400 INVALID_ARGUMENT: system_instruction.parts[0].text = "{sentinel}"'
            ),
        ])

        with _patch_genai(mock_genai, mock_genai_types):
            _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "safe user prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert sentinel not in err
        assert "[system instruction redacted]" in err
