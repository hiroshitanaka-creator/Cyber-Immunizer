"""tests/test_gemini_paid_credit.py — Tests for the --gemini-paid-credit mode
in propose_mutation.py.

All tests use monkeypatch; no real Gemini API calls are made.
No google-genai package is required to run these tests.
"""
from __future__ import annotations

import json
import sys
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
            lambda *args, **kwargs: (mock_response_text, 100, 50, ""),
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
            lambda *args, **kwargs: (None, None, None, "Gemini API call failed: timeout"),
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
            lambda *a, **kw: (valid_response_text, 100, 50, ""),
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
            lambda *a, **kw: (None, None, None, "Gemini API call failed: timeout"),
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
            lambda *a, **kw: (None, None, None, "Gemini API call failed: timeout"),
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
            lambda *a, **kw: (valid_response_text, 100, 50, ""),
        )

        result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert err == "", f"Expected success, got: {err}"
        assert result is not None
        ledger = json.loads(ledger_path.read_text())
        assert len(ledger) == 1
        assert ledger[0]["success"] is True


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
            lambda *a, **kw: (valid_response_text, 100, 50, ""),
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
            return None, None, None, "Should not reach here"

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
