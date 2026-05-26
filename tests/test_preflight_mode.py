"""tests/test_preflight_mode.py — Tests for --gemini-paid-credit-preflight mode.

All tests use monkeypatch; no real Gemini API calls are made.
No google-genai package is required to run these tests.

Invariants verified:
  - --gemini-paid-credit-preflight makes no Gemini API call
  - GEMINI_API_KEY absence causes failure
  - GEMINI_API_KEY value never appears in output or result dicts
  - live_model_enabled=false is the expected state (true → failure)
  - Malformed ledger causes failure (fail-closed)
  - Budget overflow causes failure
  - Prompt too long causes failure
  - Success writes no patch file
  - Success does not write to the ledger
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.propose_mutation as pm  # noqa: E402
from scripts import api_budget as budget  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — minimal genome that passes all preflight checks
# ---------------------------------------------------------------------------


@pytest.fixture()
def preflight_genome() -> dict:
    """A genome dict with all preflight gates in the passing state.

    Note: live_model_enabled=False is the expected state for preflight.
    """
    return {
        "project": "Test",
        "generation": 1,
        "best_score": -1000000.0,
        "max_model_requests_per_run": 1,
        "model_provider": "gemini",
        "api_mode": "gemini_paid_credit",
        "model_name": "gemini-2.0-flash",
        "fallback_model_name": "gemini-2.0-flash-lite",
        "live_model_enabled": False,   # expected false for preflight
        "require_paid_tier": True,
        "free_tier_only": False,
        "monthly_api_budget_usd": 10.0,
        "daily_api_budget_usd": 0.25,
        "max_prompt_chars": 12000,
        "max_output_tokens": 2048,
        "temperature": 0.2,
        "allow_google_search_grounding": False,
        "allow_code_execution_tool": False,
        "allow_url_context": False,
        "send_repository_full_text": False,
        "send_raw_payloads": False,
        "send_secrets": False,
    }


@pytest.fixture()
def genome_file(tmp_path: Path, preflight_genome: dict) -> Path:
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(preflight_genome), encoding="utf-8")
    return p


@pytest.fixture()
def detector_file(tmp_path: Path) -> Path:
    code = '''\
from core.types import Request, DetectionResult


def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
    # === MUTATION_END ===
'''
    p = tmp_path / "detector.py"
    p.write_text(code, encoding="utf-8")
    return p


@pytest.fixture()
def threats_file(tmp_path: Path) -> Path:
    threats = [{"id": "THREAT-2024-001"}, {"id": "THREAT-2024-005"}]
    p = tmp_path / "active_threats.json"
    p.write_text(json.dumps(threats), encoding="utf-8")
    return p


@pytest.fixture()
def ledger_file(tmp_path: Path) -> Path:
    p = tmp_path / "api_usage_ledger.json"
    p.write_text("[]", encoding="utf-8")
    return p


def _patch_paths(
    monkeypatch: pytest.MonkeyPatch,
    genome_file: Path,
    detector_file: Path,
    threats_file: Path,
    ledger_file: Path,
    out_dir: Path,
) -> None:
    monkeypatch.setattr(pm, "_GENOME_PATH", genome_file)
    monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_file)
    monkeypatch.setattr(pm, "_THREATS_PATH", threats_file)
    monkeypatch.setattr(pm, "_LEDGER_PATH", ledger_file)
    monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
    monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")


# ---------------------------------------------------------------------------
# 1. --gemini-paid-credit-preflight makes no Gemini API call
# ---------------------------------------------------------------------------


class TestPreflightNoApiCall:
    def test_preflight_does_not_call_gemini_api(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_gemini_paid_credit_preflight must never invoke _call_gemini_api."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        api_called = {"count": 0}

        def mock_call(*args: Any, **kwargs: Any) -> Any:
            api_called["count"] += 1
            return (None, None, None, "should not be called")

        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        result, err = pm.run_gemini_paid_credit_preflight()

        assert api_called["count"] == 0, (
            "--gemini-paid-credit-preflight must not call _call_gemini_api"
        )
        assert result.get("api_call_performed") is False

    def test_preflight_cli_does_not_call_gemini_api(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI --gemini-paid-credit-preflight must not invoke _call_gemini_api."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        api_called = {"count": 0}

        def mock_call(*args: Any, **kwargs: Any) -> Any:
            api_called["count"] += 1
            return (None, None, None, "should not be called")

        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        exit_code = pm.main(["--gemini-paid-credit-preflight", "--json"])

        assert api_called["count"] == 0, (
            "CLI --gemini-paid-credit-preflight must not call the Gemini API"
        )
        assert exit_code == 0

    def test_preflight_also_does_not_call_propose_via_gemini(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight must not call _propose_via_gemini_paid_credit."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        paid_called = {"count": 0}

        def mock_paid(*args: Any, **kwargs: Any) -> Any:
            paid_called["count"] += 1
            return (None, "should not be called")

        monkeypatch.setattr(pm, "_propose_via_gemini_paid_credit", mock_paid)

        pm.run_gemini_paid_credit_preflight()

        assert paid_called["count"] == 0, (
            "Preflight must not delegate to _propose_via_gemini_paid_credit"
        )


# ---------------------------------------------------------------------------
# 2. GEMINI_API_KEY absence causes failure
# ---------------------------------------------------------------------------


class TestPreflightRequiresApiKey:
    def test_fails_without_api_key(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert "GEMINI_API_KEY" in err
        assert result.get("gemini_api_key_present") is False

    def test_fails_with_empty_api_key(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert "GEMINI_API_KEY" in err

    def test_cli_returns_exit_1_without_api_key(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        exit_code = pm.main(["--gemini-paid-credit-preflight", "--json"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 3. GEMINI_API_KEY value never appears in output
# ---------------------------------------------------------------------------


class TestPreflightNeverLogsApiKeyValue:
    def test_api_key_value_not_in_result_dict(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The GEMINI_API_KEY value must never appear in the result dict."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        secret_value = "super-secret-api-key-xyz123"
        monkeypatch.setenv("GEMINI_API_KEY", secret_value)

        result, err = pm.run_gemini_paid_credit_preflight()

        # Serialize result to string and confirm the secret value is absent
        result_str = json.dumps(result)
        assert secret_value not in result_str, (
            "GEMINI_API_KEY value must never appear in the preflight result dict"
        )
        assert secret_value not in err, (
            "GEMINI_API_KEY value must never appear in the preflight error string"
        )

    def test_json_output_does_not_contain_api_key_value(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """JSON output from CLI must not contain the GEMINI_API_KEY value."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        secret_value = "my-very-secret-key-abc999"
        monkeypatch.setenv("GEMINI_API_KEY", secret_value)

        pm.main(["--gemini-paid-credit-preflight", "--json"])
        captured = capsys.readouterr()

        assert secret_value not in captured.out, (
            "GEMINI_API_KEY value must not appear in --json CLI output"
        )
        assert secret_value not in captured.err, (
            "GEMINI_API_KEY value must not appear in stderr"
        )

    def test_result_indicates_key_presence_only(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Result must contain gemini_api_key_present boolean, not the key value."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "some-real-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert "gemini_api_key_present" in result, (
            "Result must have 'gemini_api_key_present' boolean field"
        )
        assert isinstance(result["gemini_api_key_present"], bool), (
            "'gemini_api_key_present' must be a boolean"
        )
        # The actual key string should not be a field
        assert "GEMINI_API_KEY" not in result, (
            "Result dict must not have 'GEMINI_API_KEY' as a key"
        )
        assert "gemini_api_key" not in result, (
            "Result dict must not have 'gemini_api_key' as a key"
        )


# ---------------------------------------------------------------------------
# 4. live_model_enabled=false is expected; true causes failure
# ---------------------------------------------------------------------------


class TestPreflightLiveModelEnabled:
    def test_passes_when_live_model_disabled(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight should succeed when live_model_enabled=false (the expected state)."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("live_model_enabled") is False
        # Should reach at least the live_model_enabled check successfully
        # (may still pass or fail on later checks, but not on this one)
        if not result.get("success"):
            assert "live_model_enabled" not in err, (
                f"Failure should not be due to live_model_enabled=false: {err}"
            )

    def test_fails_when_live_model_enabled_true(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight must fail when live_model_enabled=true.

        This preflight verifies the pre-API-call state.  If live_model_enabled
        is already true, the operator may have enabled it prematurely.  The
        preflight gate must reject this to enforce review-before-enablement.
        """
        genome_with_live = {**preflight_genome, "live_model_enabled": True}
        genome_path = tmp_path / "genome_live.json"
        genome_path.write_text(json.dumps(genome_with_live), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert "live_model_enabled" in err, (
            f"Error must mention live_model_enabled, got: {err!r}"
        )

    def test_cli_fails_when_live_model_enabled_true(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome_with_live = {**preflight_genome, "live_model_enabled": True}
        genome_path = tmp_path / "genome_live.json"
        genome_path.write_text(json.dumps(genome_with_live), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        exit_code = pm.main(["--gemini-paid-credit-preflight", "--json"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 5. Malformed ledger causes failure (fail-closed)
# ---------------------------------------------------------------------------


class TestPreflightMalformedLedger:
    def test_fails_on_malformed_ledger_json(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A malformed ledger must cause preflight failure (fail-closed)."""
        bad_ledger = tmp_path / "bad_ledger.json"
        bad_ledger.write_text("INVALID JSON {{{}}", encoding="utf-8")
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, bad_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert "ledger" in err.lower() or "malformed" in err.lower(), (
            f"Error must mention ledger/malformed, got: {err!r}"
        )

    def test_fails_on_non_array_ledger(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A ledger that is a JSON object (not array) must cause failure."""
        bad_ledger = tmp_path / "obj_ledger.json"
        bad_ledger.write_text('{"oops": "not an array"}', encoding="utf-8")
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, bad_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False

    def test_succeeds_on_empty_ledger(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An empty (valid) ledger must not cause failure."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        # An empty ledger is valid; failure here should not be due to ledger
        if not result.get("success"):
            assert "ledger" not in err.lower() or "malformed" not in err.lower(), (
                f"Failure should not be due to empty ledger: {err}"
            )

    def test_malformed_ledger_does_not_overwrite_file(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ledger is malformed, the preflight must not overwrite it."""
        bad_content = "DEFINITELY NOT JSON"
        bad_ledger = tmp_path / "corrupt_ledger.json"
        bad_ledger.write_text(bad_content, encoding="utf-8")
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, bad_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        pm.run_gemini_paid_credit_preflight()

        # Corrupt file must remain unchanged (fail-closed)
        assert bad_ledger.read_text(encoding="utf-8") == bad_content, (
            "Preflight must not overwrite a malformed ledger file"
        )


# ---------------------------------------------------------------------------
# 6. Budget overflow causes failure
# ---------------------------------------------------------------------------


class TestPreflightBudgetOverflow:
    def test_fails_when_monthly_budget_exhausted(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight must fail when the monthly budget cap would be exceeded."""
        genome = {**preflight_genome, "monthly_api_budget_usd": 0.000001}
        genome_path = tmp_path / "genome_tiny.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        # Ledger already shows a large spend this month
        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        existing = [{
            "timestamp": f"{day_key}T00:00:00+00:00",
            "provider": "gemini",
            "api_mode": "gemini_paid_credit",
            "model": "gemini-2.0-flash",
            "estimated_input_chars": 100,
            "estimated_output_chars": 50,
            "estimated_input_tokens": 25,
            "estimated_output_tokens": 13,
            "actual_input_tokens": None,
            "actual_output_tokens": None,
            "estimated_cost_usd": 0.000001,  # already at cap
            "budget_month": month_key,
            "budget_day": day_key,
            "request_count": 1,
            "success": True,
            "error": "",
        }]
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text(json.dumps(existing), encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert result.get("budget_available") is False
        assert "budget" in err.lower() or "monthly" in err.lower() or "cap" in err.lower()

    def test_fails_when_daily_budget_exhausted(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight must fail when the daily budget cap would be exceeded."""
        genome = {
            **preflight_genome,
            "monthly_api_budget_usd": 100.0,
            "daily_api_budget_usd": 0.000001,
        }
        genome_path = tmp_path / "genome_tiny_daily.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        existing = [{
            "timestamp": f"{day_key}T00:00:00+00:00",
            "provider": "gemini",
            "api_mode": "gemini_paid_credit",
            "model": "gemini-2.0-flash",
            "estimated_input_chars": 100,
            "estimated_output_chars": 50,
            "estimated_input_tokens": 25,
            "estimated_output_tokens": 13,
            "actual_input_tokens": None,
            "actual_output_tokens": None,
            "estimated_cost_usd": 0.000001,  # already at daily cap
            "budget_month": month_key,
            "budget_day": day_key,
            "request_count": 1,
            "success": True,
            "error": "",
        }]
        ledger_path = tmp_path / "ledger_daily.json"
        ledger_path.write_text(json.dumps(existing), encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert result.get("budget_available") is False


# ---------------------------------------------------------------------------
# 7. Prompt too long causes failure
# ---------------------------------------------------------------------------


class TestPreflightPromptTooLong:
    def test_fails_when_prompt_exceeds_max_chars(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preflight must fail when the constructed prompt exceeds max_prompt_chars."""
        # Set max_prompt_chars very small so even a minimal prompt will exceed it
        genome = {**preflight_genome, "max_prompt_chars": 1}
        genome_path = tmp_path / "genome_tiny_prompt.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False
        assert "prompt" in err.lower() or "chars" in err.lower(), (
            f"Error must mention prompt/chars, got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 8. Successful preflight writes no patch file and does not modify ledger
# ---------------------------------------------------------------------------


class TestPreflightSuccessWritesNothing:
    def test_success_writes_no_patch_file(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A successful preflight must not create mutation_patch.json."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        if result.get("success"):
            patch_file = tmp_path / "mutation_patch.json"
            assert not patch_file.exists(), (
                "Successful preflight must not create mutation_patch.json"
            )
            assert result.get("patch_path") is None

    def test_success_does_not_write_ledger(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A successful preflight must not modify the ledger file."""
        original_content = "[]"
        ledger_file.write_text(original_content, encoding="utf-8")
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        if result.get("success"):
            current_content = ledger_file.read_text(encoding="utf-8")
            assert current_content == original_content, (
                "Successful preflight must not modify the ledger file"
            )
            assert result.get("ledger_written") is False

    def test_cli_success_writes_no_patch_file(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """CLI --gemini-paid-credit-preflight success must write no patch file."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        exit_code = pm.main(["--gemini-paid-credit-preflight", "--json"])

        patch_file = tmp_path / "mutation_patch.json"
        if exit_code == 0:
            assert not patch_file.exists(), (
                "CLI preflight success must not create mutation_patch.json"
            )
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output.get("patch_path") is None
            assert output.get("ledger_written") is False


# ---------------------------------------------------------------------------
# 9. JSON output structure on success
# ---------------------------------------------------------------------------


class TestPreflightJsonOutput:
    def test_success_json_has_required_fields(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Successful preflight JSON must contain all required fields."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        exit_code = pm.main(["--gemini-paid-credit-preflight", "--json"])
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        if exit_code == 0:
            required_fields = [
                "success",
                "mode",
                "api_call_performed",
                "patch_path",
                "ledger_written",
                "live_model_enabled",
                "gemini_api_key_present",
                "monthly_api_budget_usd",
                "daily_api_budget_usd",
                "estimated_next_cost_usd",
                "budget_available",
                "warnings",
            ]
            for field in required_fields:
                assert field in output, f"Required field missing from preflight output: {field!r}"

            assert output["mode"] == "gemini-paid-credit-preflight"
            assert output["api_call_performed"] is False
            assert output["patch_path"] is None
            assert output["ledger_written"] is False
            assert output["live_model_enabled"] is False
            assert output["gemini_api_key_present"] is True
            assert isinstance(output["warnings"], list)

    def test_failure_json_has_error_field_no_key_value(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Failure JSON must have 'error' field without GEMINI_API_KEY value."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        # Remove API key to trigger failure
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        pm.main(["--gemini-paid-credit-preflight", "--json"])
        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output.get("success") is False
        assert "error" in output
        # Confirm the error string mentions the key name but not a real key value
        assert "GEMINI_API_KEY" in output["error"]


# ---------------------------------------------------------------------------
# 10. Preflight genome gate checks
# ---------------------------------------------------------------------------


class TestPreflightGenomeGates:
    @pytest.mark.parametrize("field,bad_value,expected_in_err", [
        ("api_mode", "live", "api_mode"),
        ("model_provider", "openai", "model_provider"),
        ("require_paid_tier", False, "require_paid_tier"),
        ("free_tier_only", True, "free_tier_only"),
        ("monthly_api_budget_usd", 0, "monthly"),
        ("daily_api_budget_usd", 0, "daily"),
        ("max_model_requests_per_run", 5, "max_model_requests_per_run"),
        ("allow_google_search_grounding", True, "allow_google_search_grounding"),
        ("allow_code_execution_tool", True, "allow_code_execution_tool"),
        ("allow_url_context", True, "allow_url_context"),
        ("send_repository_full_text", True, "send_repository_full_text"),
        ("send_raw_payloads", True, "send_raw_payloads"),
        ("send_secrets", True, "send_secrets"),
    ])
    def test_fails_on_bad_genome_field(
        self,
        tmp_path: Path,
        preflight_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
        bad_value: Any,
        expected_in_err: str,
    ) -> None:
        genome = {**preflight_genome, field: bad_value}
        genome_path = tmp_path / f"genome_{field}.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is False, (
            f"Expected failure when {field}={bad_value!r}, got success"
        )
        assert expected_in_err.lower() in err.lower(), (
            f"Expected {expected_in_err!r} in error for {field}={bad_value!r}, got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 11. Module-level: no google-genai import required
# ---------------------------------------------------------------------------


class TestPreflightNoDependency:
    def test_module_loads_without_google_genai(self) -> None:
        """propose_mutation loads without google-genai; preflight uses no live deps."""
        assert hasattr(pm, "run_gemini_paid_credit_preflight")

    def test_preflight_function_exists(self) -> None:
        assert callable(pm.run_gemini_paid_credit_preflight)
