"""tests/test_s4_rerun_triage.py — Unit tests for scripts/triage_s4_rerun.py.

Tests use tmp_path (pytest fixture) with synthetic artifacts.
No API calls, no filesystem writes outside tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import the module under test directly (not via CLI)
import sys

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.triage_s4_rerun import _triage, main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_MUTATION_PATCH = {
    "schema_version": 1,
    "target_function": "is_attack",
    "replacement_code": "def is_attack(req): return False",
    "rationale": "test patch",
}

_MINIMAL_LEDGER = [
    {
        "timestamp": "2026-06-15T00:00:00+00:00",
        "provider": "gemini",
        "api_mode": "gemini_paid_credit",
        "model": "gemini-3-flash-preview",
        "success": True,
    }
]

_FITNESS_PASSED = {
    "passed_adoption_gate": True,
    "rejection_reasons": [],
    "score": 850.0,
    "tp_rate": 0.95,
    "fp_rate": 0.02,
    "fn_rate": 0.05,
    "candidate_hash": "a" * 64,
}

_FITNESS_REJECTED = {
    "passed_adoption_gate": False,
    "rejection_reasons": ["fp_rate too high", "score below threshold"],
    "score": 300.0,
    "tp_rate": 0.70,
    "fp_rate": 0.30,
    "fn_rate": 0.30,
    "candidate_hash": "b" * 64,
}


def _write(dir_: Path, filename: str, data: object) -> Path:
    p = dir_ / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_text(dir_: Path, filename: str, content: str) -> Path:
    p = dir_ / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1: No artifacts — propose/evaluate/promote not reached
# ---------------------------------------------------------------------------

def test_no_artifacts_propose_failed(tmp_path: Path) -> None:
    result = _triage(tmp_path)

    assert result["schema_version"] == 1
    assert result["artifacts_seen"]["mutation_patch"] is False
    assert result["artifacts_seen"]["api_usage_ledger"] is False
    assert result["artifacts_seen"]["candidate_detector"] is False
    assert result["artifacts_seen"]["fitness_report"] is False
    assert result["artifacts_seen"]["promote_result"] is False

    ss = result["stage_status"]
    assert ss["mutation_patch_produced"] is False
    assert ss["apply_reached"] is False
    assert ss["evaluate_reached"] is False
    assert ss["adoption_gate_passed"] is None
    assert ss["promote_reached"] is False

    assert result["decision"]["classification"] == "propose_failed"
    assert result["decision"]["requires_owner_approval"] is False


# ---------------------------------------------------------------------------
# Test 2: mutation_patch + ledger only — apply/evaluate not reached
# ---------------------------------------------------------------------------

def test_patch_and_ledger_only_apply_not_reached(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)

    result = _triage(tmp_path)

    assert result["artifacts_seen"]["mutation_patch"] is True
    assert result["artifacts_seen"]["api_usage_ledger"] is True
    assert result["artifacts_seen"]["candidate_detector"] is False
    assert result["artifacts_seen"]["fitness_report"] is False

    ss = result["stage_status"]
    assert ss["mutation_patch_produced"] is True
    assert ss["apply_reached"] is False
    assert ss["evaluate_reached"] is False
    assert ss["adoption_gate_passed"] is None
    assert ss["promote_reached"] is False

    assert result["decision"]["classification"] == "apply_failed_or_not_reached"
    assert result["decision"]["requires_owner_approval"] is False


# ---------------------------------------------------------------------------
# Test 3: candidate_detector present, fitness_report absent — apply reached, evaluate not
# ---------------------------------------------------------------------------

def test_candidate_present_no_fitness_apply_reached(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")

    result = _triage(tmp_path)

    assert result["artifacts_seen"]["candidate_detector"] is True
    assert result["artifacts_seen"]["fitness_report"] is False

    ss = result["stage_status"]
    assert ss["apply_reached"] is True
    assert ss["evaluate_reached"] is False
    assert ss["adoption_gate_passed"] is None

    assert result["decision"]["classification"] == "apply_failed_or_not_reached"
    assert result["decision"]["requires_owner_approval"] is False


# ---------------------------------------------------------------------------
# Test 4: fitness_report with passed_adoption_gate=False — evaluate_rejected
# ---------------------------------------------------------------------------

def test_fitness_report_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_REJECTED)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["apply_reached"] is True
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is False

    assert result["decision"]["classification"] == "evaluate_rejected"
    assert result["decision"]["requires_owner_approval"] is False
    # rejection_reasons should appear in evidence or recommended_next_action
    combined = " ".join(result["evidence"]) + " " + result["decision"]["recommended_next_action"]
    assert "fp_rate too high" in combined or "rejection_reasons" in combined


# ---------------------------------------------------------------------------
# Test 5: fitness_report with passed_adoption_gate=True — promote_eligible + owner approval
# ---------------------------------------------------------------------------

def test_fitness_report_passed_promote_eligible(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is True
    assert ss["promote_reached"] is False

    assert result["decision"]["classification"] == "promote_eligible"
    assert result["decision"]["requires_owner_approval"] is True


# ---------------------------------------------------------------------------
# Test 6: Malformed fitness_report — tool_failure (fail-closed)
# ---------------------------------------------------------------------------

def test_malformed_fitness_report_tool_failure(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    # Write invalid JSON
    (tmp_path / "fitness_report.json").write_text("{bad json: [}", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    # A warning must be emitted
    assert any("malformed" in w.lower() or "parse" in w.lower() for w in result["warnings"])
    # requires_owner_approval is False for tool_failure (no automatic action)
    assert result["decision"]["requires_owner_approval"] is False


# ---------------------------------------------------------------------------
# Test 7: fitness_report with non-object root — tool_failure
# ---------------------------------------------------------------------------

def test_fitness_report_array_root_tool_failure(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    # Root is a list, not a dict — unexpected type
    _write(tmp_path, "fitness_report.json", [{"passed_adoption_gate": True}])

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any("unexpected" in w.lower() or "root" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 8: fitness_report with missing passed_adoption_gate — fail-closed
# ---------------------------------------------------------------------------

def test_fitness_report_missing_gate_field_tool_failure(tmp_path: Path) -> None:
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    # passed_adoption_gate is absent
    _write(tmp_path, "fitness_report.json", {
        "score": 500.0,
        "rejection_reasons": [],
        "tp_rate": 0.8,
        "fp_rate": 0.1,
        "fn_rate": 0.2,
        "candidate_hash": "c" * 64,
    })

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any("unexpected" in w.lower() or "fail-closed" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 9: Secret-pattern string in artifact — suppressed from output
# ---------------------------------------------------------------------------

def test_secret_in_artifact_not_leaked(tmp_path: Path) -> None:
    secret_value = "AIzaSyExampleSecretKeyThatShouldNeverAppear1234567"
    # Embed a secret-like string in mutation_patch.json
    patch_with_secret = {**_MINIMAL_MUTATION_PATCH, "rationale": f"key={secret_value}"}
    _write(tmp_path, "mutation_patch.json", patch_with_secret)

    result = _triage(tmp_path)

    # The secret value must not appear in any output field
    output_text = json.dumps(result)
    assert secret_value not in output_text, (
        "Secret-pattern value must never appear in triage output"
    )
    # A warning about the secret detection should exist
    assert any("secret" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 10: All artifacts present including promote_result — classified as promoted
# ---------------------------------------------------------------------------

def test_all_artifacts_promoted(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED)
    _write(tmp_path, "promote_result.json", {"promoted": True, "generation": 2})

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["promote_reached"] is True
    assert result["decision"]["classification"] == "promoted"
    assert result["decision"]["requires_owner_approval"] is True


# ---------------------------------------------------------------------------
# Test 11: Malformed mutation_patch — recorded as warning, apply not reached
# ---------------------------------------------------------------------------

def test_malformed_mutation_patch_classified(tmp_path: Path) -> None:
    (tmp_path / "mutation_patch.json").write_text("{not valid json", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["artifacts_seen"]["mutation_patch"] is True
    assert result["stage_status"]["mutation_patch_produced"] is False
    assert any("malformed" in w.lower() or "parse" in w.lower() for w in result["warnings"])
    assert result["decision"]["classification"] == "propose_failed"


# ---------------------------------------------------------------------------
# Test 12: Empty fitness_report.json — tool_failure
# ---------------------------------------------------------------------------

def test_empty_fitness_report_tool_failure(tmp_path: Path) -> None:
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    (tmp_path / "fitness_report.json").write_text("", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any(w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 13: Output JSON contains required top-level keys
# ---------------------------------------------------------------------------

def test_output_schema_keys_present(tmp_path: Path) -> None:
    result = _triage(tmp_path)

    required_keys = {
        "schema_version",
        "artifacts_dir",
        "artifacts_seen",
        "stage_status",
        "decision",
        "evidence",
        "warnings",
    }
    assert required_keys <= result.keys()

    decision_keys = {"classification", "recommended_next_action", "requires_owner_approval"}
    assert decision_keys <= result["decision"].keys()

    stage_keys = {
        "mutation_patch_produced",
        "apply_reached",
        "evaluate_reached",
        "adoption_gate_passed",
        "promote_reached",
    }
    assert stage_keys <= result["stage_status"].keys()


# ---------------------------------------------------------------------------
# Test 14: CLI --json flag produces valid JSON on stdout
# ---------------------------------------------------------------------------

def test_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)

    rc = main(["--artifacts-dir", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["schema_version"] == 1
    assert "decision" in parsed


# ---------------------------------------------------------------------------
# Test 15: CLI --markdown flag writes a file
# ---------------------------------------------------------------------------

def test_cli_markdown_output(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED)

    md_path = tmp_path / "summary.md"
    rc = main(["--artifacts-dir", str(tmp_path), "--json", "--markdown", str(md_path)])

    assert rc == 0
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "# S4 Rerun Triage Summary" in content
    assert "promote_eligible" in content


# ---------------------------------------------------------------------------
# Test 16: Non-existent artifacts_dir returns exit code 2
# ---------------------------------------------------------------------------

def test_nonexistent_artifacts_dir(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    nonexistent = tmp_path / "does_not_exist"
    rc = main(["--artifacts-dir", str(nonexistent), "--json"])
    assert rc == 2


# ---------------------------------------------------------------------------
# Test 17: Secret in candidate_detector.py suppressed
# ---------------------------------------------------------------------------

def test_secret_in_candidate_detector_suppressed(tmp_path: Path) -> None:
    secret_value = "AIzaSyAnotherFakeKeyForTestingPurposesOnly12345"
    _write_text(tmp_path, "candidate_detector.py", f"API_KEY = '{secret_value}'\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_value not in output_text
    assert any("secret" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test 18: rejection_reasons with secret-like content suppressed
# ---------------------------------------------------------------------------

def test_rejection_reasons_secret_suppressed(tmp_path: Path) -> None:
    secret_in_reason = "AIzaSyFakeTokenInRejectionReason99999999999"
    fitness_with_secret_reason = {
        "passed_adoption_gate": False,
        "rejection_reasons": [f"key={secret_in_reason}", "score too low"],
        "score": 100.0,
        "tp_rate": 0.5,
        "fp_rate": 0.5,
        "fn_rate": 0.5,
        "candidate_hash": "d" * 64,
    }
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", fitness_with_secret_reason)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_in_reason not in output_text
