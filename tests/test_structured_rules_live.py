"""tests/test_structured_rules_live.py — Tests for the live (paid-credit)
structured-rules proposal mode in propose_mutation.py.

All tests mock _call_gemini_api; no real Gemini API call is made and no
google-genai package is required.
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
from core.structured_validator import validate_rules_schema  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def paid_genome() -> dict:
    return {
        "project": "Test",
        "generation": 1,
        "best_score": -1000000.0,
        "max_model_requests_per_run": 1,
        "model_provider": "gemini",
        "api_mode": "gemini_paid_credit",
        "model_name": "gemini-2.0-flash",
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
def env(tmp_path: Path, paid_genome: dict, monkeypatch: pytest.MonkeyPatch) -> dict:
    genome_path = tmp_path / "genome.json"
    genome_path.write_text(json.dumps(paid_genome), encoding="utf-8")
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text("[]", encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
    monkeypatch.setattr(pm, "_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
    monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")
    monkeypatch.setattr(pm, "_OUT_STRUCTURED_RULES", out_dir / "structured_rules.json")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    return {"genome": genome_path, "ledger": ledger_path, "out_dir": out_dir}


def _valid_rules_text() -> str:
    return json.dumps(pm.build_offline_sample_structured_rules())


def _mock_call(raw_text: str, *, error: str = ""):
    captured: dict[str, Any] = {"n": 0, "kwargs": None}

    def call(*args: Any, **kwargs: Any):
        captured["n"] += 1
        captured["kwargs"] = kwargs
        if error:
            return None, None, None, None, error
        return raw_text, 100, 200, None, ""

    return call, captured


# ---------------------------------------------------------------------------
# propose_structured_rules — paid-credit path
# ---------------------------------------------------------------------------

class TestLiveStructuredProposal:
    def test_happy_path_returns_valid_rules(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert err == ""
        assert isinstance(rules, dict)
        assert validate_rules_schema(rules).get("success") is True
        assert cap["n"] == 1
        # ledger recorded a success
        ledger = json.loads(env["ledger"].read_text())
        assert len(ledger) == 1 and ledger[0]["success"] is True

    def test_call_uses_structured_schema_and_system_prompt(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert cap["kwargs"]["response_schema"] is None
        assert cap["kwargs"]["system_instruction"] == pm._STRUCTURED_SYSTEM_PROMPT

    def test_requires_allow_live_model(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=False)
        assert rules is None
        assert "allow-live-model" in err
        assert cap["n"] == 0

    def test_requires_api_key(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert "GEMINI_API_KEY" in err
        assert cap["n"] == 0

    def test_genome_gate_blocks_call(self, tmp_path: Path, paid_genome: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        bad = {**paid_genome, "live_model_enabled": False}
        gp = tmp_path / "g.json"; gp.write_text(json.dumps(bad), encoding="utf-8")
        lp = tmp_path / "l.json"; lp.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", gp)
        monkeypatch.setattr(pm, "_LEDGER_PATH", lp)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert "live_model_enabled" in err
        assert cap["n"] == 0

    def test_invalid_json_is_output_contract_failure(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        call, cap = _mock_call("{not valid json")
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert "not valid JSON" in err
        # the call succeeded; ledger still records the usage
        ledger = json.loads(env["ledger"].read_text())
        assert len(ledger) == 1

    def test_validator_exception_is_output_contract_failure(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parseable JSON with an extreme numeric field (OverflowError in the
        validator) must become a clean output-contract failure, not a traceback."""
        overflow_doc = {
            "schema_version": 1,
            "features": {"surface": {"fields": ["path"], "normalization": ["lowercase"],
                "max_collection_entries": {"query": 1000, "headers": 1000},
                "max_scalar_bytes": {"method": 4096, "path": 1048576, "query.item": 1048576, "header.item": 1048576},
                "body_scan": {"mode": "full", "max_bytes": 1048576}}},
            "rules": [{"id": "r", "field": "surface", "operator": "contains_literal",
                       "literal": "x", "signal": "s", "confidence": 10 ** 400}],
            "decision": {"block_when": "any_rule_matches", "reason": "r",
                         "confidence_strategy": {"type": "fixed", "default": 0.5},
                         "matched_signals": "matched_rule_signals"},
            "fallback": {"blocked": False, "reason": "n", "confidence": 0.0, "matched_signals": []},
        }
        call, cap = _mock_call(json.dumps(overflow_doc))
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert "validator raised" in err
        # The call succeeded; usage is still recorded in the ledger.
        assert len(json.loads(env["ledger"].read_text())) == 1

    def test_schema_invalid_rules_rejected(self, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        call, cap = _mock_call(json.dumps({"schema_version": 1, "rules": "not-a-list"}))
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert "schema validation" in err

    def test_budget_exhausted_refuses_before_call(self, tmp_path: Path, paid_genome: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts import api_budget as budget
        genome = {**paid_genome, "monthly_api_budget_usd": 0.0001}
        gp = tmp_path / "g.json"; gp.write_text(json.dumps(genome), encoding="utf-8")
        existing = [{
            "timestamp": "2026-05-01T00:00:00+00:00", "provider": "gemini",
            "api_mode": "gemini_paid_credit", "model": "gemini-2.0-flash",
            "estimated_cost_usd": 0.0001, "budget_month": budget.current_month_key(),
            "budget_day": budget.current_day_key(), "request_count": 1,
            "success": True, "error": "",
        }]
        lp = tmp_path / "l.json"; lp.write_text(json.dumps(existing), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", gp)
        monkeypatch.setattr(pm, "_LEDGER_PATH", lp)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rules, err = pm.propose_structured_rules(gemini_paid_credit=True, allow_live_model=True)
        assert rules is None
        assert cap["n"] == 0
        assert "budget" in err.lower()


# ---------------------------------------------------------------------------
# main() CLI wiring
# ---------------------------------------------------------------------------

class TestMainCli:
    def test_paid_structured_writes_rules(self, env: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        call, cap = _mock_call(_valid_rules_text())
        monkeypatch.setattr(pm, "_call_gemini_api", call)
        rc = pm.main(["--structured-rules", "--gemini-paid-credit", "--allow-live-model", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["mode"] == "structured-rules-gemini-paid-credit"
        assert (env["out_dir"] / "structured_rules.json").exists()

    def test_structured_rejects_live_model(self, env: dict, capsys: pytest.CaptureFixture) -> None:
        rc = pm.main(["--structured-rules", "--live-model", "--allow-live-model", "--json"])
        assert rc == 1
        assert "live-model" in json.loads(capsys.readouterr().out)["error"]

    def test_structured_requires_a_mode(self, env: dict, capsys: pytest.CaptureFixture) -> None:
        rc = pm.main(["--structured-rules", "--json"])
        assert rc == 1
        assert "offline-sample" in json.loads(capsys.readouterr().out)["error"]

    def test_offline_structured_still_works(self, env: dict, capsys: pytest.CaptureFixture) -> None:
        rc = pm.main(["--structured-rules", "--offline-sample", "--json"])
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["mode"] == "structured-rules-offline-sample"


# ---------------------------------------------------------------------------
# Proposer prompt: comprehensive, precise coverage guidance (M-real ignition)
# ---------------------------------------------------------------------------

def test_structured_prompt_requests_comprehensive_precise_coverage() -> None:
    """The proposer prompt must push broad, multi-signature coverage of the
    canonical threat classes AND precision (no benign over-matching), so a
    candidate can clear the known-attack/regression bar with fp ~ 0."""
    prompt = pm._build_structured_rules_prompt({})
    lower = prompt.lower()
    # Comprehensiveness + multiple signatures per category.
    assert "comprehensive" in lower
    assert "multiple distinct signatures" in lower or "several signatures" in lower
    # Coverage breadth beyond the original four categories.
    for cls in ("path traversal", "sql injection", "xss", "command injection",
                "ssrf", "xxe", "ssti"):
        assert cls in lower, f"prompt missing coverage guidance for {cls!r}"
    # Obfuscation awareness and precision (no benign over-blocking).
    assert "encoding" in lower
    assert "precision" in lower
    # Still strictly defensive — detection signatures, not exploit payloads.
    assert "not" in lower and "exploit payload" in lower
