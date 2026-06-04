"""tests/test_gemini_paid_credit.py — Tests for the --gemini-paid-credit mode
in propose_mutation.py.

All tests use monkeypatch; no real Gemini API calls are made.
No google-genai package is required to run these tests.
"""
from __future__ import annotations

import json
import sys
import time as _time_module
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.propose_mutation as pm  # noqa: E402
from scripts import api_budget as budget  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def live_paid_genome() -> dict:
    """A genome dict with all paid-credit gates enabled."""
    return {
        "project": "Test",
        "generation": 1,
        "best_score": -1000000.0,
        "max_model_requests_per_run": 1,
        "model_provider": "gemini",
        "api_mode": "gemini_paid_credit",
        "model_name": "gemini-2.0-flash",
        "fallback_model_name": "gemini-2.0-flash-lite",
        "live_model_enabled": True,
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
def genome_file(tmp_path: Path, live_paid_genome: dict) -> Path:
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(live_paid_genome), encoding="utf-8")
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


@pytest.fixture()
def valid_patch() -> dict:
    """A patch dict that passes all validation checks (no '__' in code)."""
    return {
        "mutation_rationale": "Improve coverage for path traversal patterns.",
        "target_threats": ["THREAT-2024-001"],
        "expected_improvement": "Higher TP rate.",
        "risk": "Low — additive logic only.",
        "replacement_code": (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path-traversal', 'sqli', 'xss', 'cmd-delim']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        boost = min(1.0, 0.5 + 0.12 * len(matched))\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched: ' + matched[0],\n"
            "            confidence=boost,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        ),
    }


def _patch_paths(monkeypatch: pytest.MonkeyPatch, genome_file: Path,
                 detector_file: Path, threats_file: Path,
                 ledger_file: Path, out_dir: Path) -> None:
    monkeypatch.setattr(pm, "_GENOME_PATH", genome_file)
    monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_file)
    monkeypatch.setattr(pm, "_THREATS_PATH", threats_file)
    monkeypatch.setattr(pm, "_LEDGER_PATH", ledger_file)
    monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
    monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")


# ---------------------------------------------------------------------------
# 1. --gemini-paid-credit without --allow-live-model refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresAllowFlag:
    def test_refuses_without_allow_live_model(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=False
        )
        assert patch_result is None
        assert "--allow-live-model" in err

    def test_cli_refuses_without_allow_flag(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        result = pm.main(["--gemini-paid-credit", "--json"])
        assert result == 1


# ---------------------------------------------------------------------------
# 2. --gemini-paid-credit without GEMINI_API_KEY refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresApiKey:
    def test_refuses_without_api_key(
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

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "GEMINI_API_KEY" in err

    def test_refuses_empty_key(
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

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "GEMINI_API_KEY" in err


# ---------------------------------------------------------------------------
# 3. --gemini-paid-credit with live_model_enabled=false refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresLiveEnabled:
    def test_refuses_when_live_disabled(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "live_model_enabled": False}
        genome_path = tmp_path / "genome_disabled.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "live_model_enabled" in err


# ---------------------------------------------------------------------------
# 4. --gemini-paid-credit with require_paid_tier=false refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresPaidTier:
    def test_refuses_when_require_paid_tier_false(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "require_paid_tier": False}
        genome_path = tmp_path / "genome_notpaid.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "require_paid_tier" in err


# ---------------------------------------------------------------------------
# 5. --gemini-paid-credit with free_tier_only=true refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRefusesFreeTierOnly:
    def test_refuses_when_free_tier_only_true(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "free_tier_only": True}
        genome_path = tmp_path / "genome_freetier.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "free_tier_only" in err


# ---------------------------------------------------------------------------
# 6. --gemini-paid-credit with monthly_api_budget_usd=0 refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresMonthlyBudget:
    def test_refuses_when_monthly_budget_zero(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "monthly_api_budget_usd": 0}
        genome_path = tmp_path / "genome_nomonth.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "monthly" in err.lower()

    def test_refuses_when_monthly_budget_negative(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "monthly_api_budget_usd": -1.0}
        genome_path = tmp_path / "genome_negmonth.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "monthly" in err.lower()


# ---------------------------------------------------------------------------
# 7. --gemini-paid-credit with daily_api_budget_usd=0 refuses
# ---------------------------------------------------------------------------


class TestPaidCreditRequiresDailyBudget:
    def test_refuses_when_daily_budget_zero(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "daily_api_budget_usd": 0}
        genome_path = tmp_path / "genome_nodaily.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "daily" in err.lower()


# ---------------------------------------------------------------------------
# 8. Budget overflow refuses before Gemini call
# ---------------------------------------------------------------------------


class TestBudgetOverflowRefuses:
    def test_monthly_overflow_refuses_before_call(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Monthly budget already exhausted → refusal without calling Gemini."""
        genome = {**live_paid_genome, "monthly_api_budget_usd": 0.001}
        genome_path = tmp_path / "genome_tiny.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        # Ledger already has a large spend this month
        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        existing = [{
            "timestamp": "2026-05-01T00:00:00+00:00",
            "provider": "gemini",
            "api_mode": "gemini_paid_credit",
            "model": "gemini-2.0-flash",
            "estimated_input_chars": 100,
            "estimated_output_chars": 50,
            "estimated_input_tokens": 25,
            "estimated_output_tokens": 13,
            "actual_input_tokens": None,
            "actual_output_tokens": None,
            "estimated_cost_usd": 0.001,  # already at cap
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

        # Track whether _call_gemini_api was invoked
        call_count = {"n": 0}
        original_call = pm._call_gemini_api

        def mock_call(*args: Any, **kwargs: Any) -> Any:
            call_count["n"] += 1
            return original_call(*args, **kwargs)

        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        # Budget check should have fired, not the API call
        assert call_count["n"] == 0
        assert "budget" in err.lower() or "monthly" in err.lower()


# ---------------------------------------------------------------------------
# 9. Prompt secret scan rejects secrets
# ---------------------------------------------------------------------------


class TestPaidCreditSecretScan:
    @pytest.mark.parametrize("secret", [
        "GITHUB_TOKEN",
        "GEMINI_API_KEY",
        "password=s3cr3t",
        "BEGIN PRIVATE KEY",
    ])
    def test_preflight_scan_catches_secrets(self, secret: str) -> None:
        prompt = f"Benign text. {secret}. More benign text."
        err = pm._preflight_secret_scan(prompt)
        assert err != ""
        assert "Preflight" in err


# ---------------------------------------------------------------------------
# 10. Schema validation rejects extra fields
# ---------------------------------------------------------------------------


class TestPaidCreditSchemaExtraFields:
    def test_rejects_extra_field(self) -> None:
        data = {
            "mutation_rationale": "test",
            "target_threats": [],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": "    pass",
            "INJECTED": "bad",
        }
        err = pm._validate_patch_schema(data)
        assert err != ""
        assert "INJECTED" in err or "extra" in err.lower()


# ---------------------------------------------------------------------------
# 11. Schema validation rejects missing fields
# ---------------------------------------------------------------------------


class TestPaidCreditSchemaMissingFields:
    @pytest.mark.parametrize("missing", list(pm._REQUIRED_PATCH_FIELDS))
    def test_rejects_missing_field(self, missing: str) -> None:
        data: dict = {
            "mutation_rationale": "ok",
            "target_threats": [],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": "    pass",
        }
        del data[missing]
        err = pm._validate_patch_schema(data)
        assert err != ""
        assert missing in err or "missing" in err.lower()


# ---------------------------------------------------------------------------
# 12. Unsafe replacement_code rejected before writing patch
# ---------------------------------------------------------------------------


class TestPaidCreditUnsafeCode:
    @pytest.mark.parametrize("bad_code", [
        "import os",
        "eval('x')",
        "exec('print(1)')",
        "open('/etc/passwd')",
        "subprocess.run(['ls'])",
        "import socket",
        "os.system('ls')",
        "x = obj.__dict__",
        "import pathlib",
        "import shutil",
        "import urllib",
        "import requests",
    ])
    def test_rejects_forbidden_token(self, bad_code: str) -> None:
        err = pm._validate_replacement_code(bad_code)
        assert err != "", f"Expected rejection for: {bad_code!r}"


# ---------------------------------------------------------------------------
# 13. Mocked Gemini success writes mutation_patch.json
# ---------------------------------------------------------------------------


class TestPaidCreditMockedSuccess:
    def test_success_writes_patch(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        valid_patch: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        patch_path = tmp_path / "mutation_patch.json"
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        # Mock _propose_via_gemini_paid_credit to return valid patch
        monkeypatch.setattr(
            pm, "_propose_via_gemini_paid_credit",
            lambda genome, det, key, ledger: (valid_patch, ""),
        )

        result = pm.main(["--gemini-paid-credit", "--allow-live-model", "--json"])
        assert result == 0
        assert patch_path.exists()
        data = json.loads(patch_path.read_text())
        assert data["mutation_rationale"] == valid_patch["mutation_rationale"]

    def test_success_json_output_has_mode(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        valid_patch: dict,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        monkeypatch.setattr(
            pm, "_propose_via_gemini_paid_credit",
            lambda genome, det, key, ledger: (valid_patch, ""),
        )

        pm.main(["--gemini-paid-credit", "--allow-live-model", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["mode"] == "gemini-paid-credit"


# ---------------------------------------------------------------------------
# 14. Mocked Gemini success appends usage ledger
# ---------------------------------------------------------------------------


class TestPaidCreditLedgerAppend:
    def test_appends_usage_record_on_success(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After a successful paid call, the ledger gets a new entry."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Valid patch that passes all validation
        valid_response = {
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": (
                "    surface = request.path.lower()\n"
                "    indicators = ['traversal', 'sqli']\n"
                "    matched = [i for i in indicators if i in surface]\n"
                "    if matched:\n"
                "        return DetectionResult(\n"
                "            blocked=True,\n"
                "            reason='matched',\n"
                "            confidence=0.7,\n"
                "            matched_signals=tuple(matched),\n"
                "        )\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        }

        # Mock the raw Gemini call, not the whole paid-credit function
        mock_response_text = json.dumps(valid_response)
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *args, **kwargs: (mock_response_text, 100, 50, None, ""),
        )

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert err == "", f"Expected success, got: {err}"
        assert patch_result is not None

        # Verify ledger was updated
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1
        assert ledger[0]["success"] is True
        assert ledger[0]["model"] == live_paid_genome["model_name"]
        assert ledger[0]["api_mode"] == "gemini_paid_credit"

    def test_appends_failure_record_when_api_fails(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the API call fails, a failure record is still appended."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Simulate API failure
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *args, **kwargs: (None, None, None, None, "Gemini API call failed: timeout"),
        )

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "failed" in err.lower()

        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1
        assert ledger[0]["success"] is False
        assert "timeout" in ledger[0]["error"] or "failed" in ledger[0]["error"]


# ---------------------------------------------------------------------------
# 15. Additional safety gates for gemini-paid-credit
# ---------------------------------------------------------------------------


class TestPaidCreditAdditionalGates:
    def test_refuses_url_context_enabled(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "allow_url_context": True}
        genome_path = tmp_path / "g.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        patch_result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert patch_result is None
        assert "url_context" in err.lower()

    def test_refuses_send_repository_text(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "send_repository_full_text": True}
        genome_path = tmp_path / "g.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        patch_result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert patch_result is None
        assert "send_repository_full_text" in err

    def test_refuses_send_raw_payloads(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "send_raw_payloads": True}
        genome_path = tmp_path / "g.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        patch_result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert patch_result is None
        assert "send_raw_payloads" in err

    def test_refuses_send_secrets(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        genome = {**live_paid_genome, "send_secrets": True}
        genome_path = tmp_path / "g.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        patch_result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert patch_result is None
        assert "send_secrets" in err

    def test_existing_live_model_mode_unaffected(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--live-model mode still works independently of --gemini-paid-credit."""
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        # live_model_enabled is True in genome_file, but GEMINI_API_KEY not set
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "GEMINI_API_KEY" in err


# ---------------------------------------------------------------------------
# 16. Tests never call real Gemini API — verify no real import at top-level
# ---------------------------------------------------------------------------


class TestNoDependencyRequired:
    def test_module_loads_without_google_genai(self) -> None:
        """propose_mutation imports successfully without google-genai."""
        # We already imported pm at the top; if this passes, the import is lazy.
        assert hasattr(pm, "propose_mutation")
        assert hasattr(pm, "_propose_via_gemini_paid_credit")

    def test_api_budget_loads_without_google_genai(self) -> None:
        """api_budget imports successfully (standard library only)."""
        assert hasattr(budget, "load_ledger")
        assert hasattr(budget, "strict_load_ledger")
        assert hasattr(budget, "assert_budget_available")
        assert hasattr(budget, "append_usage_record")


# ---------------------------------------------------------------------------
# 17. Ledger write failures are hard errors in gemini-paid-credit mode
# ---------------------------------------------------------------------------


class TestPaidCreditLedgerFailures:
    """Verify that ledger recording failures prevent patch success.

    After a Gemini API call, the budget ledger MUST be updated.  If
    append_usage_record raises (e.g., corrupt ledger), the function must
    return an error regardless of whether the API call succeeded.  This
    prevents the budget cap from becoming fail-open.
    """

    @pytest.fixture()
    def all_paths(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
    ) -> dict:
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        return {
            "genome_path": genome_path,
            "detector_file": detector_file,
            "threats_file": threats_file,
            "ledger_path": ledger_path,
            "tmp_path": tmp_path,
        }

    def test_api_success_but_ledger_failure_returns_error(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When API succeeds but ledger write fails, no patch is returned.

        An API call whose cost cannot be recorded makes the budget cap
        fail-open for future calls — it must be treated as an error.
        """
        paths = all_paths
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            paths["ledger_path"],
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Mock API to succeed with valid JSON
        valid_response_text = json.dumps({
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": (
                "    surface = request.path.lower()\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (valid_response_text, 100, 50, None, ""),
        )

        # Make the ledger file corrupt AFTER budget check but before append
        # by corrupting the ledger after the genome/budget reads succeed.
        # We mock append_usage_record directly to raise ValueError.
        from scripts import api_budget as ab

        def corrupt_append(*args: Any, **kwargs: Any) -> None:
            raise ValueError("Simulated corrupt ledger during write")

        monkeypatch.setattr(ab, "append_usage_record", corrupt_append)

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert result is None, "No patch should be returned when ledger write fails"
        assert err != "", "An error must be returned when ledger write fails"
        assert "ledger" in err.lower() or "budget" in err.lower() or "append" in err.lower() or "record" in err.lower(), (
            f"Error must mention ledger/budget, got: {err!r}"
        )

    def test_api_failure_records_failure_in_ledger(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When API fails, a failure record is written to the ledger and error returned."""
        paths = all_paths
        ledger_path = paths["ledger_path"]
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            ledger_path,
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Simulate API failure
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (None, None, None, None, "Gemini API call failed: timeout"),
        )

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert result is None
        assert "failed" in err.lower() or "timeout" in err.lower()

        # Failure record must still be written
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1, "Failure record must be appended to ledger"
        assert ledger[0]["success"] is False

    def test_api_failure_and_ledger_failure_returns_compound_error(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When both API fails and ledger write fails, compound error is returned."""
        paths = all_paths
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            paths["ledger_path"],
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Simulate API failure
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (None, None, None, None, "Gemini API call failed: timeout"),
        )

        # Simulate ledger write failure
        from scripts import api_budget as ab

        def corrupt_append(*args: Any, **kwargs: Any) -> None:
            raise ValueError("Corrupt ledger on write")

        monkeypatch.setattr(ab, "append_usage_record", corrupt_append)

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert result is None
        assert err != ""
        # Should mention both the API error and the ledger error
        assert "failed" in err.lower() or "timeout" in err.lower(), (
            f"Expected API error in message, got: {err!r}"
        )
        assert "ledger" in err.lower() or "record" in err.lower() or "additionally" in err.lower(), (
            f"Expected ledger error in message, got: {err!r}"
        )

    def test_success_with_valid_ledger_returns_patch(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sanity check: API success + valid ledger → patch returned."""
        paths = all_paths
        ledger_path = paths["ledger_path"]
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            ledger_path,
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        valid_response_text = json.dumps({
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": (
                "    surface = request.path.lower()\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (valid_response_text, 100, 50, None, ""),
        )

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert err == "", f"Expected success, got: {err}"
        assert result is not None
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1
        assert ledger[0]["success"] is True

    # ------------------------------------------------------------------ #
    # PHASE2.5-HARDENING-EXTRA-001
    # Stricter behavioral regressions: prove that when a mocked Gemini API
    # call SUCCEEDS but append_usage_record() fails, propose_mutation refuses
    # to return a patch.  Unlike the tests above, these also pin down:
    #   - _call_gemini_api was invoked exactly once (failure is AFTER the
    #     API call, not a pre-call gate rejection), and
    #   - append_usage_record was attempted exactly once (the write was
    #     genuinely tried, not skipped/swallowed).
    # No real Gemini API call is made; no GEMINI_API_KEY secret is required.
    # ------------------------------------------------------------------ #

    # A valid patch JSON accepted by the schema/AST validators.  Uses only
    # neutralized symbolic indicators — no raw exploit-looking payloads.
    _VALID_RESPONSE_TEXT = json.dumps({
        "mutation_rationale": "Improve detection coverage.",
        "target_threats": ["THREAT-2024-001"],
        "expected_improvement": "Higher TP rate.",
        "risk": "Low.",
        "replacement_code": (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator: ' + matched[0],\n"
            "            confidence=0.7,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        ),
    })

    def test_paid_credit_api_success_but_ledger_write_oserror_returns_no_patch(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """API success + OSError on ledger write → no patch, fail-closed.

        An OSError (e.g. disk full, permission denied) while recording usage
        after a successful API call must NOT yield a patch: the budget cap
        would otherwise become fail-open for future calls.
        """
        paths = all_paths
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            paths["ledger_path"],
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Mocked API SUCCESS — valid patch JSON + actual token counts, no error.
        mock_call = MagicMock(return_value=(self._VALID_RESPONSE_TEXT, 100, 50, None, ""))
        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        # Ledger write raises OSError.  Patch on the api_budget module so the
        # `from scripts import api_budget as budget` alias inside the function
        # resolves to this mock.
        mock_append = MagicMock(side_effect=OSError("simulated ledger write failure"))
        monkeypatch.setattr(budget, "append_usage_record", mock_append)

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )

        assert result is None, "No patch may be returned when ledger write fails"
        assert err != "", "A non-empty error must be returned on ledger write failure"
        assert any(
            phrase in err.lower()
            for phrase in (
                "ledger write failed",
                "cannot confirm budget",
                "recorded",
                "refusing",
            )
        ), f"Error must describe ledger write failure, got: {err!r}"

        # Failure occurred AFTER a single successful API call, not before it.
        assert mock_call.call_count == 1, (
            f"_call_gemini_api must be called exactly once, got {mock_call.call_count}"
        )
        assert mock_append.call_count == 1, (
            f"append_usage_record must be attempted exactly once, "
            f"got {mock_append.call_count}"
        )

    def test_paid_credit_api_success_but_ledger_write_valueerror_returns_no_patch(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """API success + ValueError on ledger write → no patch, fail-closed.

        append_usage_record() can raise ValueError for corrupt/malformed
        ledger state.  The caller must treat it as a hard failure.
        """
        paths = all_paths
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            paths["ledger_path"],
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        mock_call = MagicMock(return_value=(self._VALID_RESPONSE_TEXT, 100, 50, None, ""))
        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        mock_append = MagicMock(side_effect=ValueError("simulated corrupt ledger"))
        monkeypatch.setattr(budget, "append_usage_record", mock_append)

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )

        assert result is None, "No patch may be returned when ledger write fails"
        assert err != "", "A non-empty error must be returned on ledger write failure"
        assert any(
            phrase in err.lower()
            for phrase in (
                "ledger write failed",
                "cannot confirm budget",
                "refusing",
            )
        ), f"Error must describe ledger write failure, got: {err!r}"

        assert mock_call.call_count == 1, (
            f"_call_gemini_api must be called exactly once, got {mock_call.call_count}"
        )
        assert mock_append.call_count == 1, (
            f"append_usage_record must be attempted exactly once, "
            f"got {mock_append.call_count}"
        )

    def test_paid_credit_api_error_and_ledger_write_failure_reports_both(
        self,
        all_paths: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """API error + ledger write failure → both causes preserved in error.

        When both the API call and the usage-record write fail, diagnostics
        must retain both the original API error and the ledger-write failure.
        """
        paths = all_paths
        _patch_paths(
            monkeypatch,
            paths["genome_path"],
            paths["detector_file"],
            paths["threats_file"],
            paths["ledger_path"],
            paths["tmp_path"],
        )
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Mocked API ERROR — no raw text, no token counts, non-empty api_err.
        mock_call = MagicMock(
            return_value=(None, None, None, None, "simulated Gemini API error")
        )
        monkeypatch.setattr(pm, "_call_gemini_api", mock_call)

        mock_append = MagicMock(side_effect=OSError("simulated ledger write failure"))
        monkeypatch.setattr(budget, "append_usage_record", mock_append)

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )

        assert result is None, "No patch may be returned when API and ledger both fail"
        assert err != "", "A non-empty error must be returned"
        # The original API error cause must be preserved.
        assert "simulated gemini api error" in err.lower(), (
            f"Error must preserve the API error cause, got: {err!r}"
        )
        # The ledger-write failure cause must also be preserved.
        assert any(
            phrase in err.lower()
            for phrase in (
                "ledger write failed",
                "cannot confirm budget",
                "refusing",
            )
        ), f"Error must also describe ledger write failure, got: {err!r}"

        assert mock_call.call_count == 1, (
            f"_call_gemini_api must be called exactly once, got {mock_call.call_count}"
        )
        assert mock_append.call_count == 1, (
            f"append_usage_record must be attempted exactly once, "
            f"got {mock_append.call_count}"
        )


# ---------------------------------------------------------------------------
# 18. api_usage_ledger missing / malformed → fail-closed in live paid path (#3)
# ---------------------------------------------------------------------------


class TestPaidCreditLedgerMissingFailClosed:
    """Verify that the live API budget path fails-closed when api_usage_ledger.json
    is missing, malformed, or has an invalid top-level type.

    Backlog #3: api_usage_ledger.json missing is fail-open → must become fail-closed.
    A missing ledger means past spend is unknown; allowing the API call would
    make the budget cap fail-open.
    """

    # ------------------------------------------------------------------ #
    # 1. Missing ledger refuses the API call
    # ------------------------------------------------------------------ #

    def test_missing_ledger_refuses_paid_credit(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing api_usage_ledger.json must refuse the --gemini-paid-credit call."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        missing_ledger = tmp_path / "api_usage_ledger.json"
        # DO NOT create the ledger

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, missing_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is missing"
        assert err, "Must produce an error message"
        assert (
            "budget state unknown" in err.lower()
            or "not usable" in err.lower()
            or "not found" in err.lower()
            or "missing" in err.lower()
        ), f"Error must mention ledger problem (budget state unknown), got: {err!r}"

    # ------------------------------------------------------------------ #
    # 2. Malformed ledger refuses the API call
    # ------------------------------------------------------------------ #

    def test_malformed_ledger_refuses_paid_credit(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed api_usage_ledger.json must refuse the --gemini-paid-credit call."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        bad_ledger = tmp_path / "api_usage_ledger.json"
        bad_ledger.write_text("{NOT_VALID_JSON!!!", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, bad_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is malformed"
        assert err, "Must produce an error message"

    # ------------------------------------------------------------------ #
    # 3. Top-level dict ledger refuses the API call
    # ------------------------------------------------------------------ #

    def test_dict_ledger_refuses_paid_credit(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Top-level JSON object in api_usage_ledger.json must refuse the API call."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        dict_ledger = tmp_path / "api_usage_ledger.json"
        dict_ledger.write_text('{"this": "is wrong"}', encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, dict_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is a dict"
        assert err, "Must produce an error message"

    # ------------------------------------------------------------------ #
    # 4. Top-level null ledger refuses the API call
    # ------------------------------------------------------------------ #

    def test_null_ledger_refuses_paid_credit(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Top-level JSON null in api_usage_ledger.json must refuse the API call."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        null_ledger = tmp_path / "api_usage_ledger.json"
        null_ledger.write_text("null", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, null_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is null"
        assert err, "Must produce an error message"

    # ------------------------------------------------------------------ #
    # 5. Missing ledger is NOT treated as [] (zero spend)
    # ------------------------------------------------------------------ #

    def test_missing_ledger_not_silently_treated_as_empty(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A missing ledger must produce a ledger-specific error, not proceed as if empty."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        missing_ledger = tmp_path / "api_usage_ledger.json"
        # DO NOT create

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, missing_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert err
        # The error must be about the ledger/budget state, not just a generic budget
        # overflow (which would imply the missing ledger was treated as []).
        assert "ledger" in err.lower() or "budget state unknown" in err.lower() or \
               "not usable" in err.lower() or "not found" in err.lower(), (
                   f"Error should reference ledger unavailability, got: {err!r}"
               )

    # ------------------------------------------------------------------ #
    # 6. Budget error mentions "budget state unknown"
    # ------------------------------------------------------------------ #

    def test_missing_ledger_error_mentions_budget_state_unknown(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Error for missing ledger must include the phrase 'budget state unknown'."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        missing_ledger = tmp_path / "api_usage_ledger.json"

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, missing_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert "budget state unknown" in err.lower(), (
            f"Error must mention 'budget state unknown' for missing ledger, got: {err!r}"
        )

    # ------------------------------------------------------------------ #
    # 7. Valid ledger still passes (regression guard)
    # ------------------------------------------------------------------ #

    def test_valid_ledger_passes_budget_check(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A valid, empty ledger must not cause false budget failures."""
        # ledger_file fixture writes [] to the file
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        valid_response_text = json.dumps({
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": (
                "    surface = request.path.lower()\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (valid_response_text, 100, 50, None, ""),
        )

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert err == "", f"Valid ledger should allow API call, got: {err}"
        assert patch_result is not None, "Valid ledger should allow patch to be returned"

    # ------------------------------------------------------------------ #
    # 8. Missing ledger does NOT cause API call to be performed
    # ------------------------------------------------------------------ #

    def test_missing_ledger_prevents_api_call(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ledger is missing, the Gemini API must NOT be called."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        missing_ledger = tmp_path / "api_usage_ledger.json"

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, missing_ledger, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        api_called = []

        def mock_api_call(*args: Any, **kwargs: Any) -> tuple:
            api_called.append(True)
            return None, None, None, None, "Should not reach here"

        monkeypatch.setattr(pm, "_call_gemini_api", mock_api_call)

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None
        assert err
        assert not api_called, (
            "Gemini API must NOT be called when the ledger is missing; "
            f"api_called={api_called}"
        )


# ---------------------------------------------------------------------------
# 19. Retry inside _call_gemini_api does NOT cause multiple ledger writes
# ---------------------------------------------------------------------------


class TestPaidCreditRetryDoesNotWriteLedgerPerAttempt:
    """Verify that internal retry in _call_gemini_api does not cause the paid-credit
    path to write more than one ledger record per propose_mutation call.

    The retry loop is entirely contained inside _call_gemini_api; the ledger
    responsibility belongs to _propose_via_gemini_paid_credit and must remain
    there — exactly one write per external call, regardless of how many
    internal retries occurred.
    """

    def test_paid_credit_retry_does_not_write_ledger_per_attempt(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When _call_gemini_api retries internally and succeeds, ledger is written once."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Simulate _call_gemini_api itself retrying internally by having it
        # succeed on first call (retry already happened inside before returning).
        # We verify that append_usage_record is called exactly once — not once
        # per retry attempt.
        valid_response_text = json.dumps({
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": (
                "    surface = request.path.lower()\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })

        # Track ledger append calls
        append_call_count: list[int] = [0]
        from scripts import api_budget as ab
        original_append = ab.append_usage_record

        def counting_append(*args: Any, **kwargs: Any) -> Any:
            append_call_count[0] += 1
            return original_append(*args, **kwargs)

        monkeypatch.setattr(ab, "append_usage_record", counting_append)

        # Mock _call_gemini_api to return success (representing a call that
        # internally retried once before succeeding — the ledger must not know
        # about those internal attempts).
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *a, **kw: (valid_response_text, 100, 50, None, ""),
        )
        # Prevent actual sleep in case real _call_gemini_api were used
        monkeypatch.setattr(_time_module, "sleep", lambda _: None)

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert err == "", f"Expected success, got: {err}"
        assert patch_result is not None

        assert append_call_count[0] == 1, (
            f"append_usage_record must be called exactly once per propose_mutation call, "
            f"got {append_call_count[0]} calls"
        )
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1, f"Ledger must have exactly 1 record, got {len(ledger)}"


# ---------------------------------------------------------------------------
# 20. paid-credit path passes max_model_requests_per_run as max_attempts
# ---------------------------------------------------------------------------


class TestPaidCreditMaxAttemptsFromGenome:
    """Verify that max_model_requests_per_run controls generate_content call count.

    With max_model_requests_per_run=1 (the current default gate), a transient
    failure must NOT be retried — the actual generate_content call count is 1.
    This keeps actual API calls in lockstep with the budget estimate and the
    ledger record.
    """

    def test_paid_credit_max_requests_one_no_retry_on_transient(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With max_model_requests_per_run=1, transient failure uses 1 attempt (no retry)."""
        genome = {**live_paid_genome, "max_model_requests_per_run": 1}
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(_time_module, "sleep", lambda _: None)

        # Track actual _call_gemini_api invocations AND the max_attempts passed in.
        captured_max_attempts: list[int] = []
        original_call = pm._call_gemini_api

        def tracking_call(*args: Any, **kwargs: Any) -> Any:
            captured_max_attempts.append(kwargs.get("max_attempts", pm._GEMINI_API_MAX_ATTEMPTS))
            # Simulate a transient failure that _call_gemini_api would handle internally.
            # Since max_attempts=1 is passed, no retry should occur.
            return None, None, None, None, "Gemini API call failed after 1 attempt: transient error TimeoutError"

        monkeypatch.setattr(pm, "_call_gemini_api", tracking_call)

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )

        assert patch_result is None
        assert len(captured_max_attempts) == 1, (
            "_call_gemini_api should be called exactly once by the paid-credit path"
        )
        assert captured_max_attempts[0] == 1, (
            f"max_attempts passed to _call_gemini_api should be 1 "
            f"(from max_model_requests_per_run=1), got {captured_max_attempts[0]}"
        )
        # Ledger must still be written (failure record)
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1, "Failure record must be written even when transient"
        assert ledger[0]["success"] is False

    def test_live_path_passes_max_model_requests_as_max_attempts(
        self,
        tmp_path: Path,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_propose_via_gemini_live passes max_model_requests_per_run to _call_gemini_api."""
        genome = {
            "project": "Test",
            "generation": 1,
            "model_provider": "gemini",
            "model_name": "gemini-2.0-flash",
            "max_prompt_chars": 12000,
            "max_output_tokens": 2048,
            "temperature": 0.2,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
            "allow_google_search_grounding": False,
            "allow_code_execution_tool": False,
            "monthly_api_budget_usd": 0,
            "free_tier_only": True,
        }
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_file)

        captured_max_attempts: list[int] = []

        def tracking_call(*args: Any, **kwargs: Any) -> Any:
            captured_max_attempts.append(kwargs.get("max_attempts", pm._GEMINI_API_MAX_ATTEMPTS))
            return None, None, None, None, "Gemini API call failed after 1 attempt: transient error TimeoutError"

        monkeypatch.setattr(pm, "_call_gemini_api", tracking_call)

        result, err = pm._propose_via_gemini_live(
            genome, detector_file.read_text(), "fake-key"
        )

        assert result is None
        assert len(captured_max_attempts) == 1
        assert captured_max_attempts[0] == 1, (
            f"max_attempts should be 1 (max_model_requests_per_run=1), "
            f"got {captured_max_attempts[0]}"
        )


# ---------------------------------------------------------------------------
# 21. Conservative multilingual estimate refuses before API call (Codex P2 aware)
# ---------------------------------------------------------------------------


class TestConservativeMultilingualBudgetRefusal:
    """Proves the 2x conservative INPUT estimate participates in the pre-call budget gate.

    These tests verify:
    A. A large multilingual/code/symbol-heavy INPUT prompt triggers budget refusal
       (max_output_tokens is kept very small so only input drives the estimate).
    B. A small budget is no longer blocked solely because of output-cap re-estimation
       (Codex P2 regression guard: max_output_tokens must be used directly, not
       passed through estimate_tokens_from_chars).
    C. The same Codex P2 fix applies in the preflight cost estimation site.
    """

    def test_conservative_multilingual_estimate_refuses_before_api_call(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conservative 2x INPUT estimate of multilingual prompt must refuse before API call.

        max_output_tokens is set to 16 so output cost is negligible; refusal must
        come from the conservative INPUT estimate, not from output-cap re-estimation.

        Budget = $0.001, system_prompt (~2682 chars) + user_prompt drives refusal:
          - 2x input estimate: ceil(~3200 * 2.0) tokens → input_cost > $0.001  ✗ refused
          - chars/4 input estimate: ceil(~3200 / 4) tokens → input_cost < $0.001  ✓ passed

        _call_gemini_api must NOT be invoked; the pre-call budget gate must fire first.
        Uses only neutralized symbolic indicators — no raw payload strings.
        """
        # Multilingual/code/symbol-heavy prompt: Japanese text + Python-like code
        # + neutralised symbolic indicator names + punctuation-heavy content.
        multilingual_prompt = (
            "このコードはセキュリティの脆弱性を検出します。\n"
            "以下のPythonコードを分析してください:\n"
            "def check_request(req):\n"
            "    surface = req.path.lower() + ' ' + req.body.lower()\n"
            "    indicators = [\n"
            "        'path_traversal_indicator',\n"
            "        'sqli_indicator',\n"
            "        'script_injection_indicator',\n"
            "        'command_delimiter_indicator',\n"
            "    ]\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        confidence = min(1.0, 0.5 + 0.1 * len(matched))\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator: ' + matched[0],\n"
            "            confidence=confidence,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no indicator matched',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
            "# 記号テスト !@#$%^&*()_+-=[]{}|;':\",./<>?\n"
            "# 攻撃パターンの指標検出: path_traversal_indicator sqli_indicator\n"
        )
        monkeypatch.setattr(pm, "_build_user_prompt", lambda g, d: multilingual_prompt)

        # max_output_tokens=16 → output cost ≈ $0.000013 (negligible).
        # Budget $0.001 is between new 2x input estimate and old chars/4 estimate:
        #   full_prompt ≈ 2682(sys) + 1 + ~550(user) = ~3233 chars
        #   2x input: ceil(3233*2)/1M*$0.20 ≈ $0.0013  > $0.001  → refused ✓
        #   chars/4:  ceil(3233/4)/1M*$0.20 ≈ $0.00016 < $0.001  → would pass ✓
        genome = {
            **live_paid_genome,
            "monthly_api_budget_usd": 0.001,
            "daily_api_budget_usd": 0.001,
            "max_output_tokens": 16,
            "live_model_enabled": True,
        }
        genome_path = tmp_path / "genome_multilingual.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        # Empty ledger — zero prior spend; the estimate alone must exceed the budget.
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Track whether _call_gemini_api is invoked — it must NOT be.
        api_call_was_made: list[bool] = []

        def mock_api_call(*args: Any, **kwargs: Any) -> Any:
            api_call_was_made.append(True)
            return None, None, None, None, "must not reach here"

        monkeypatch.setattr(pm, "_call_gemini_api", mock_api_call)

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)

        assert result is None, (
            "propose_mutation must return None when conservative INPUT estimate exceeds budget"
        )
        assert err, "Must produce a non-empty error message"
        assert any(word in err.lower() for word in ("budget", "monthly", "daily")), (
            f"Error must mention budget/monthly/daily, got: {err!r}"
        )
        assert not api_call_was_made, (
            "_call_gemini_api must NOT be called when conservative INPUT estimate exceeds budget; "
            "the pre-call budget gate must fire first"
        )

    def test_output_token_cap_is_not_reestimated_as_characters(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Codex P2 regression: max_output_tokens must not be re-estimated via char multiplier.

        With the buggy code (estimate_tokens_from_chars(max_output_tokens * 4)):
          est_output_tokens = ceil(2048 * 4 * 2.0) = 16384 → ~$0.013 → exceeds $0.01 → blocked

        With the correct code (est_output_tokens = max_output_tokens):
          est_output_tokens = 2048 → ~$0.0016 → within $0.01 → allowed

        This test must fail under the buggy implementation and pass under the fix.
        _call_gemini_api is mocked; no real API call is made.
        """
        # Short safe prompt using only neutralized indicators
        short_prompt = (
            "# Improve detection for path_traversal_indicator and sqli_indicator.\n"
            "# Use only neutralized symbolic indicators.\n"
        )
        monkeypatch.setattr(pm, "_build_user_prompt", lambda g, d: short_prompt)

        # Budget $0.01 is above the correct estimate (~$0.003) but below the buggy
        # estimate (~$0.014) for max_output_tokens=2048.
        genome = {
            **live_paid_genome,
            "monthly_api_budget_usd": 0.01,
            "daily_api_budget_usd": 0.01,
            "max_output_tokens": 2048,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
        }
        genome_path = tmp_path / "genome_codex_p2.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        valid_response = json.dumps({
            "mutation_rationale": "Improve coverage for path_traversal_indicator.",
            "target_threats": ["THREAT-2024-001"],
            "expected_improvement": "Higher TP rate.",
            "risk": "Low — additive logic only.",
            "replacement_code": (
                "    surface = request.path.lower() + ' ' + request.body.lower()\n"
                "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
                "    matched = [ind for ind in indicators if ind in surface]\n"
                "    if matched:\n"
                "        return DetectionResult(\n"
                "            blocked=True,\n"
                "            reason='indicator: ' + matched[0],\n"
                "            confidence=0.7,\n"
                "            matched_signals=tuple(matched),\n"
                "        )\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })

        api_call_count: list[int] = []

        def mock_api_call(*args: Any, **kwargs: Any) -> Any:
            api_call_count.append(1)
            return valid_response, 500, 200, None, ""

        monkeypatch.setattr(pm, "_call_gemini_api", mock_api_call)

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)

        assert err == "", (
            f"Budget $0.01 must be sufficient when max_output_tokens=2048 is used directly "
            f"(not re-estimated as chars). Got error: {err!r}"
        )
        assert result is not None, (
            "propose_mutation must return a patch when budget is sufficient. "
            "If this fails, max_output_tokens is likely still being re-estimated "
            "via estimate_tokens_from_chars (Codex P2 bug)."
        )
        assert len(api_call_count) == 1, (
            f"_call_gemini_api must be called exactly once, got {len(api_call_count)}"
        )

    def test_preflight_output_token_cap_is_not_reestimated_as_characters(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Codex P2 regression for preflight site: max_output_tokens must not be re-estimated.

        run_gemini_paid_credit_preflight has the same output estimation site.
        With budget=$0.01 and max_output_tokens=2048:
          - Correct code: est_output_tokens=2048 → ~$0.003 < $0.01 → preflight succeeds
          - Buggy code:   est_output_tokens=16384 → ~$0.014 > $0.01 → preflight fails

        This test guards the second estimation site in propose_mutation.py.
        live_model_enabled=False is the expected state for preflight.
        """
        short_prompt = (
            "# Improve detection for path_traversal_indicator.\n"
        )
        monkeypatch.setattr(pm, "_build_user_prompt", lambda g, d: short_prompt)

        genome = {
            **live_paid_genome,
            "monthly_api_budget_usd": 0.01,
            "daily_api_budget_usd": 0.01,
            "max_output_tokens": 2048,
            "live_model_enabled": False,  # expected state for preflight
        }
        genome_path = tmp_path / "genome_preflight_p2.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        result, err = pm.run_gemini_paid_credit_preflight()

        assert result.get("success") is True, (
            f"Preflight must succeed when budget $0.01 is sufficient for max_output_tokens=2048. "
            f"If this fails, the preflight output estimation site may still be using "
            f"estimate_tokens_from_chars on the token cap (Codex P2 bug). err={err!r}"
        )
        assert err == "", f"Expected no error, got: {err!r}"
        assert result.get("budget_available") is True

    def test_paid_credit_ledger_uses_output_token_cap_not_char_reestimate(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ledger estimated_output_tokens must match the pre-call gate, not a char-re-estimate.

        Key invariant: ledger[0]["estimated_output_tokens"] == genome["max_output_tokens"]

        With the old bug: estimate_tokens_from_chars(2048*4*2.0) = 16384 was stored.
        With the fix: max_output_tokens = 2048 is stored directly.

        This prevents accounting drift where future budget checks see inflated spend
        because the ledger recorded 8x more output tokens than the gate estimated.
        """
        short_prompt = (
            "# Improve detection for path_traversal_indicator and sqli_indicator.\n"
        )
        monkeypatch.setattr(pm, "_build_user_prompt", lambda g, d: short_prompt)

        genome = {
            **live_paid_genome,
            "monthly_api_budget_usd": 0.01,
            "daily_api_budget_usd": 0.01,
            "max_output_tokens": 2048,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
        }
        genome_path = tmp_path / "genome_ledger_check.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file, ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        valid_response = json.dumps({
            "mutation_rationale": "Improve detection coverage.",
            "target_threats": ["THREAT-2024-001"],
            "expected_improvement": "Higher TP rate.",
            "risk": "Low.",
            "replacement_code": (
                "    surface = request.path.lower() + ' ' + request.body.lower()\n"
                "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
                "    matched = [ind for ind in indicators if ind in surface]\n"
                "    if matched:\n"
                "        return DetectionResult(\n"
                "            blocked=True,\n"
                "            reason='indicator: ' + matched[0],\n"
                "            confidence=0.7,\n"
                "            matched_signals=tuple(matched),\n"
                "        )\n"
                "    return DetectionResult(\n"
                "        blocked=False,\n"
                "        reason='no match',\n"
                "        confidence=0.0,\n"
                "        matched_signals=(),\n"
                "    )\n"
            ),
        })
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *args, **kwargs: (valid_response, 400, 150, None, ""),
        )

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)

        assert err == "", f"Expected success, got: {err!r}"
        assert result is not None

        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1, f"Expected 1 ledger record, got {len(ledger)}"

        rec = ledger[0]
        # KEY INVARIANT: ledger output tokens must equal the token cap, not a
        # char-derived re-estimate.  Before the fix, this was 16384 (8x inflated).
        assert rec["estimated_output_tokens"] == genome["max_output_tokens"], (
            f"Ledger estimated_output_tokens={rec['estimated_output_tokens']} "
            f"must equal max_output_tokens={genome['max_output_tokens']}. "
            "If 16384, the ledger accounting is using the buggy char re-estimate."
        )
        assert rec["estimated_output_tokens"] != 16384, (
            "Ledger must NOT store 16384 output tokens — that is the Codex P2 bug "
            "(estimate_tokens_from_chars(max_output_tokens * 4 * 2.0))."
        )
        # Cost in ledger must be consistent with output=2048 tokens, not 16384.
        # gemini-2.0-flash output rate: $0.80/1M tokens
        # With 16384 output tokens: cost contribution ≈ $0.0131 alone
        # With 2048 output tokens:  cost contribution ≈ $0.0016
        # Any cost above $0.005 for this prompt would indicate inflated output accounting.
        assert rec["estimated_cost_usd"] < 0.005, (
            f"Ledger cost ${rec['estimated_cost_usd']:.6f} is too high — likely caused by "
            f"output token inflation from char re-estimation (expected < $0.005 for "
            f"max_output_tokens=2048 with a short input prompt)."
        )


# ---------------------------------------------------------------------------
# Thinking-budget inclusion in budget estimates (Codex P2)
# ---------------------------------------------------------------------------

class TestThinkingBudgetInEstimation:
    """Verify that Gemini 3 thinking tokens are included in budget estimates.

    For gemini-3 models (running with thinking_level="low"), a conservative
    allowance (_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS) is added to
    max_output_tokens for cost estimation and ledger recording.
    For gemini-2 models the behaviour is unchanged.
    """

    _VALID_RESPONSE = json.dumps({
        "mutation_rationale": "Improve coverage.",
        "target_threats": ["THREAT-2024-001"],
        "expected_improvement": "Higher TP rate.",
        "risk": "Low.",
        "replacement_code": (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator: ' + matched[0],\n"
            "            confidence=0.7,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        ),
    })

    def _gemini3_genome(self, live_paid_genome: dict, max_output_tokens: int = 2048) -> dict:
        return {
            **live_paid_genome,
            "model_name": "gemini-3-flash-preview",
            "fallback_model_name": "gemini-3.1-flash-lite",
            "max_output_tokens": max_output_tokens,
            "monthly_api_budget_usd": 10.0,
            "daily_api_budget_usd": 1.0,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
        }

    def test_gemini3_ledger_includes_thinking_tokens(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ledger estimated_output_tokens for gemini-3 = max_output_tokens + thinking estimate."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = self._gemini3_genome(live_paid_genome)
        genome_path = tmp_path / "genome_g3.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 400, 150, None, ""))

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert err == "", f"Expected success, got: {err!r}"

        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1
        rec = ledger[0]
        expected = genome["max_output_tokens"] + pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS
        assert rec["estimated_output_tokens"] == expected, (
            f"estimated_output_tokens={rec['estimated_output_tokens']} "
            f"expected max_output_tokens({genome['max_output_tokens']}) "
            f"+ thinking_budget({pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS}) = {expected}"
        )

    def test_gemini2_ledger_unchanged(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """For gemini-2 models, estimated_output_tokens must still equal max_output_tokens."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = {
            **live_paid_genome,
            "model_name": "gemini-2.0-flash",
            "max_output_tokens": 2048,
            "monthly_api_budget_usd": 10.0,
            "daily_api_budget_usd": 1.0,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
        }
        genome_path = tmp_path / "genome_g2.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 400, 150, None, ""))

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert err == "", f"Expected success, got: {err!r}"

        ledger = json.loads(ledger_path.read_text())
        rec = ledger[0]
        assert rec["estimated_output_tokens"] == genome["max_output_tokens"], (
            f"gemini-2 model must not add thinking budget. "
            f"Got {rec['estimated_output_tokens']}, expected {genome['max_output_tokens']}"
        )

    def test_append_usage_record_receives_thinking_inclusive_tokens(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """append_usage_record's estimated_output_tokens must include thinking budget for gemini-3."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = self._gemini3_genome(live_paid_genome, max_output_tokens=512)
        genome_path = tmp_path / "genome_g3_append.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 200, 100, None, ""))

        captured: list[dict] = []
        original_append = budget.append_usage_record

        def capturing_append(path, **kwargs: Any) -> None:
            captured.append(dict(kwargs))
            original_append(path, **kwargs)

        monkeypatch.setattr(budget, "append_usage_record", capturing_append)

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert err == "", f"Expected success, got: {err!r}"

        assert len(captured) == 1, "append_usage_record must be called exactly once"
        expected_tokens = genome["max_output_tokens"] + pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS
        assert captured[0]["estimated_output_tokens"] == expected_tokens, (
            f"append_usage_record received estimated_output_tokens="
            f"{captured[0]['estimated_output_tokens']}, "
            f"expected {expected_tokens} (max_output_tokens={genome['max_output_tokens']} "
            f"+ thinking_budget={pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS})"
        )


# ---------------------------------------------------------------------------
# Actual thinking tokens in ledger (Codex P2: do not treat low as 1024-cap)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CR-65-MIN-03: Invalid model response must not create mutation_patch.json
# ---------------------------------------------------------------------------


class TestInvalidResponseNoPatchArtifact:
    """CR-65-MIN-03: Invalid Gemini/model response must not create mutation_patch.json.

    These tests prove that when _propose_via_gemini_paid_credit returns a
    validation error, the CLI does not write mutation_patch.json to disk.
    No real Gemini API call is made; monkeypatch/mocks only.
    """

    def test_forbidden_token_response_no_patch_file(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI must not write mutation_patch.json when validation returns an error.

        Simulates the case where _propose_via_gemini_paid_credit rejects
        replacement_code containing a forbidden token, returning (None, error).
        The patch file artifact boundary must be respected: no patch on disk.
        """
        patch_path = tmp_path / "mutation_patch.json"
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        monkeypatch.setattr(
            pm, "_propose_via_gemini_paid_credit",
            lambda genome, det, key, ledger: (
                None,
                "Gemini replacement_code validation failed: "
                "replacement_code contains forbidden token 'import'. "
                "Unsafe replacement_code rejected before writing patch.",
            ),
        )

        result = pm.main(["--gemini-paid-credit", "--allow-live-model", "--json"])
        assert result != 0, "CLI must exit nonzero when replacement_code validation fails"
        assert not patch_path.exists(), (
            "mutation_patch.json must NOT be created when replacement_code validation fails"
        )

    def test_invalid_replacement_code_via_call_boundary_no_patch(
        self,
        tmp_path: Path,
        genome_file: Path,
        detector_file: Path,
        threats_file: Path,
        ledger_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Forbidden token in _call_gemini_api response → validator rejects → no patch file.

        Mocks _call_gemini_api to return raw JSON containing 'import os' in
        replacement_code. _parse_and_validate_response must reject it and no
        mutation_patch.json must be written to disk.
        """
        patch_path = tmp_path / "mutation_patch.json"
        _patch_paths(monkeypatch, genome_file, detector_file, threats_file, ledger_file, tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
        monkeypatch.setattr(pm, "_build_user_prompt", lambda g, d: "# short safe prompt\n")

        invalid_response = json.dumps({
            "mutation_rationale": "ok",
            "target_threats": ["T1"],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": "import os\n    return os.system('ls')",
        })
        monkeypatch.setattr(
            pm, "_call_gemini_api",
            lambda *args, **kwargs: (invalid_response, 100, 50, None, ""),
        )

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, (
            "Must return no patch when replacement_code contains forbidden token"
        )
        assert err != "", "Must return a non-empty error string"
        assert "import" in err or "forbidden" in err.lower(), (
            f"Error must mention forbidden token, got: {err!r}"
        )
        assert not patch_path.exists(), (
            "mutation_patch.json must NOT be written when replacement_code validation fails "
            "(CR-65-MIN-03 artifact boundary test)"
        )


class TestActualThinkingTokensInLedger:
    """Ledger records actual_thinking_tokens / actual_billable_response_tokens."""

    _VALID_RESPONSE = json.dumps({
        "mutation_rationale": "Improve coverage.",
        "target_threats": ["THREAT-2024-001"],
        "expected_improvement": "Higher TP rate.",
        "risk": "Low.",
        "replacement_code": (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator: ' + matched[0],\n"
            "            confidence=0.7,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        ),
    })

    def _gemini3_genome(self, live_paid_genome: dict) -> dict:
        return {
            **live_paid_genome,
            "model_name": "gemini-3-flash-preview",
            "fallback_model_name": "gemini-3.1-flash-lite",
            "max_output_tokens": 512,
            "monthly_api_budget_usd": 10.0,
            "daily_api_budget_usd": 1.0,
            "live_model_enabled": True,
            "max_model_requests_per_run": 1,
        }

    def test_ledger_records_actual_thinking_tokens_when_present(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When response includes thoughts_token_count, ledger records actual_thinking_tokens."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = self._gemini3_genome(live_paid_genome)
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        # 200 output tokens + 400 thinking tokens = 600 billable (within estimate)
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 300, 200, 400, ""))

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert err == "", f"Expected success, got: {err!r}"

        rec = json.loads(ledger_path.read_text())[0]
        assert rec["actual_thinking_tokens"] == 400, (
            f"Expected actual_thinking_tokens=400, got {rec['actual_thinking_tokens']!r}"
        )
        assert rec["actual_billable_response_tokens"] == 600, (
            f"Expected actual_billable_response_tokens=600, got {rec['actual_billable_response_tokens']!r}"
        )

    def test_ledger_cost_uses_actual_when_it_exceeds_estimate(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If actual_billable_response_tokens > est_output_tokens, cost is not under-recorded."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = self._gemini3_genome(live_paid_genome)
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # est_output_tokens = 512 + 1024 = 1536
        # actual: 500 output + 2000 thinking = 2500 billable → exceeds estimate → fail-closed
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 300, 500, 2000, ""))

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        # Actual exceeded estimate → fail-closed, no patch returned
        assert result is None
        assert "exceeded" in err or "overrun" in err or "pre-call estimate" in err, (
            f"Error must mention overrun, got: {err!r}"
        )

        rec = json.loads(ledger_path.read_text())[0]
        # Ledger must record actual values, not just estimate
        assert rec["actual_thinking_tokens"] == 2000
        assert rec["actual_billable_response_tokens"] == 2500
        # estimated_output_tokens in ledger must use max(estimate, actual)
        assert rec["estimated_output_tokens"] == 2500, (
            f"estimated_output_tokens must be max(1536, 2500)=2500, got {rec['estimated_output_tokens']!r}"
        )

    def test_ledger_falls_back_to_estimate_when_no_thinking_tokens(
        self,
        tmp_path: Path,
        live_paid_genome: dict,
        detector_file: Path,
        threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When thoughts_token_count is absent, ledger uses conservative estimate (no overrun)."""
        monkeypatch.setattr(pm, "_build_user_prompt",
                            lambda g, d: "# short safe prompt\n")
        genome = self._gemini3_genome(live_paid_genome)
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("[]", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        _patch_paths(monkeypatch, genome_path, detector_file, threats_file,
                     ledger_path, out_dir)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        # No thinking tokens in response (None)
        monkeypatch.setattr(pm, "_call_gemini_api",
                            lambda *a, **kw: (self._VALID_RESPONSE, 300, 400, None, ""))

        result, err = pm.propose_mutation(gemini_paid_credit=True, allow_live_model=True)
        assert err == "", f"Expected success, got: {err!r}"

        rec = json.loads(ledger_path.read_text())[0]
        assert rec["actual_thinking_tokens"] is None
        # estimated_output_tokens stays at pre-call estimate when no actual thinking data
        expected_est = genome["max_output_tokens"] + pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS
        assert rec["estimated_output_tokens"] == expected_est, (
            f"Fallback estimate expected {expected_est}, got {rec['estimated_output_tokens']!r}"
        )
