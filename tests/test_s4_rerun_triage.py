"""tests/test_s4_rerun_triage.py — Unit tests for scripts/triage_s4_rerun.py.

Tests use tmp_path (pytest fixture) with synthetic artifacts.
No API calls, no filesystem writes outside tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.triage_s4_rerun import (
    _triage,
    _extract_fitness_payload,
    _safe_text,
    main,
)

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

# Flat fitness_report shape (core.fitness module output stored directly)
_FITNESS_PASSED_FLAT = {
    "passed_adoption_gate": True,
    "rejection_reasons": [],
    "score": 850.0,
    "tp_rate": 0.95,
    "fp_rate": 0.02,
    "fn_rate": 0.05,
    "candidate_hash": "a" * 64,
}

_FITNESS_REJECTED_FLAT = {
    "passed_adoption_gate": False,
    "rejection_reasons": ["fp_rate too high", "score below threshold"],
    "score": 300.0,
    "tp_rate": 0.70,
    "fp_rate": 0.30,
    "fn_rate": 0.30,
    "candidate_hash": "b" * 64,
}

# Evaluator-wrapper shape (evaluate_candidate.py _write_report() output)
_FITNESS_PASSED_WRAPPER = {
    "success": True,
    "passed_adoption_gate": True,
    "timed_out": False,
    "return_code": 0,
    "violations": [],
    "fitness_report": {
        "passed_adoption_gate": True,
        "rejection_reasons": [],
        "score": 900.0,
        "tp_rate": 0.96,
        "fp_rate": 0.01,
        "fn_rate": 0.04,
        "candidate_hash": "e" * 64,
    },
    "error": "",
    "is_tool_failure": False,
    "candidate_hash": "e" * 64,
}

_FITNESS_REJECTED_WRAPPER = {
    "success": False,
    "passed_adoption_gate": False,
    "timed_out": False,
    "return_code": 0,
    "violations": [],
    "fitness_report": {
        "passed_adoption_gate": False,
        "rejection_reasons": ["score did not improve", "fp_rate too high"],
        "score": 300.0,
        "tp_rate": 0.70,
        "fp_rate": 0.30,
        "fn_rate": 0.30,
        "candidate_hash": "f" * 64,
    },
    "error": "adoption gate not passed",
    "is_tool_failure": False,
    "candidate_hash": "f" * 64,
}


def _write(dir_: Path, filename: str, data: object) -> Path:
    p = dir_ / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_text(dir_: Path, filename: str, content: str) -> Path:
    p = dir_ / filename
    p.write_text(content, encoding="utf-8")
    return p


# ===========================================================================
# Original 18 tests (maintained)
# ===========================================================================

# Test 1
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


# Test 2
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


# Test 3
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


# Test 4 (flat shape)
def test_fitness_report_rejected_flat(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_REJECTED_FLAT)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["apply_reached"] is True
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is False

    assert result["decision"]["classification"] == "evaluate_rejected"
    assert result["decision"]["requires_owner_approval"] is False
    combined = " ".join(result["evidence"]) + " " + result["decision"]["recommended_next_action"]
    assert "fp_rate too high" in combined or "rejection_reasons" in combined


# Test 5 (flat shape)
def test_fitness_report_passed_promote_eligible_flat(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_FLAT)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is True
    assert ss["promote_reached"] is False

    assert result["decision"]["classification"] == "promote_eligible"
    assert result["decision"]["requires_owner_approval"] is True


# Test 6
def test_malformed_fitness_report_tool_failure(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    (tmp_path / "fitness_report.json").write_text("{bad json: [}", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any("malformed" in w.lower() or "parse" in w.lower() for w in result["warnings"])
    assert result["decision"]["requires_owner_approval"] is False


# Test 7
def test_fitness_report_array_root_tool_failure(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", [{"passed_adoption_gate": True}])

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any("unexpected" in w.lower() or "root" in w.lower() for w in result["warnings"])


# Test 8
def test_fitness_report_missing_gate_field_tool_failure(tmp_path: Path) -> None:
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
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


# Test 9
def test_secret_in_artifact_not_leaked(tmp_path: Path) -> None:
    secret_value = "AIzaSyExampleSecretKeyThatShouldNeverAppear1234567"
    patch_with_secret = {**_MINIMAL_MUTATION_PATCH, "rationale": f"key={secret_value}"}
    _write(tmp_path, "mutation_patch.json", patch_with_secret)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_value not in output_text
    assert any("secret" in w.lower() for w in result["warnings"])


# Test 10 — future-reserved: promote_result.json present → promoted classification
def test_all_artifacts_promoted(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", _MINIMAL_LEDGER)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_FLAT)
    _write(tmp_path, "promote_result.json", {"promoted": True, "generation": 2})

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["promote_reached"] is True
    assert result["decision"]["classification"] == "promoted"
    assert result["decision"]["requires_owner_approval"] is True


# Test 11
def test_malformed_mutation_patch_classified(tmp_path: Path) -> None:
    (tmp_path / "mutation_patch.json").write_text("{not valid json", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["artifacts_seen"]["mutation_patch"] is True
    assert result["stage_status"]["mutation_patch_produced"] is False
    assert any("malformed" in w.lower() or "parse" in w.lower() for w in result["warnings"])
    assert result["decision"]["classification"] == "propose_failed"


# Test 12
def test_empty_fitness_report_tool_failure(tmp_path: Path) -> None:
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    (tmp_path / "fitness_report.json").write_text("", encoding="utf-8")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"
    assert any(w for w in result["warnings"])


# Test 13
def test_output_schema_keys_present(tmp_path: Path) -> None:
    result = _triage(tmp_path)

    required_keys = {
        "schema_version", "artifacts_dir", "artifacts_seen",
        "stage_status", "decision", "evidence", "warnings",
    }
    assert required_keys <= result.keys()

    decision_keys = {"classification", "recommended_next_action", "requires_owner_approval"}
    assert decision_keys <= result["decision"].keys()

    stage_keys = {
        "mutation_patch_produced", "apply_reached", "evaluate_reached",
        "adoption_gate_passed", "promote_reached",
    }
    assert stage_keys <= result["stage_status"].keys()


# Test 14
def test_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)

    rc = main(["--artifacts-dir", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed["schema_version"] == 1
    assert "decision" in parsed


# Test 15
def test_cli_markdown_output(tmp_path: Path) -> None:
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_FLAT)

    md_path = tmp_path / "summary.md"
    rc = main(["--artifacts-dir", str(tmp_path), "--json", "--markdown", str(md_path)])

    assert rc == 0
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "# S4 Rerun Triage Summary" in content
    assert "promote_eligible" in content


# Test 16
def test_nonexistent_artifacts_dir(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    nonexistent = tmp_path / "does_not_exist"
    rc = main(["--artifacts-dir", str(nonexistent), "--json"])
    assert rc == 2


# Test 17
def test_secret_in_candidate_detector_suppressed(tmp_path: Path) -> None:
    secret_value = "AIzaSyAnotherFakeKeyForTestingPurposesOnly12345"
    _write_text(tmp_path, "candidate_detector.py", f"API_KEY = '{secret_value}'\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_FLAT)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_value not in output_text
    assert any("secret" in w.lower() for w in result["warnings"])


# Test 18
def test_rejection_reasons_secret_suppressed_flat(tmp_path: Path) -> None:
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


# ===========================================================================
# New tests — evaluator wrapper shape
# ===========================================================================

# Test 19
def test_wrapper_shape_rejected(tmp_path: Path) -> None:
    """evaluator wrapper fitness_report with passed_adoption_gate=false → evaluate_rejected."""
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_REJECTED_WRAPPER)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is False
    assert result["decision"]["classification"] == "evaluate_rejected"
    assert result["decision"]["requires_owner_approval"] is False


# Test 20
def test_wrapper_shape_passed_promote_eligible(tmp_path: Path) -> None:
    """evaluator wrapper fitness_report with passed_adoption_gate=true → promote_eligible."""
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_WRAPPER)

    result = _triage(tmp_path)

    ss = result["stage_status"]
    assert ss["evaluate_reached"] is True
    assert ss["adoption_gate_passed"] is True
    assert result["decision"]["classification"] == "promote_eligible"
    assert result["decision"]["requires_owner_approval"] is True


# Test 21
def test_wrapper_rejection_reasons_in_output(tmp_path: Path) -> None:
    """Nested rejection_reasons are reflected in evidence or recommended_next_action."""
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_REJECTED_WRAPPER)

    result = _triage(tmp_path)

    combined = " ".join(result["evidence"]) + " " + result["decision"]["recommended_next_action"]
    assert "score did not improve" in combined or "fp_rate too high" in combined


# Test 22
def test_wrapper_rejection_reasons_secret_suppressed(tmp_path: Path) -> None:
    """Nested fitness_report.rejection_reasons with a secret value are suppressed."""
    secret = "AIzaSySecretInNestedRejectionReasonXXXXXXXXXXXX"
    wrapper_with_secret = {
        **_FITNESS_REJECTED_WRAPPER,
        "fitness_report": {
            **_FITNESS_REJECTED_WRAPPER["fitness_report"],
            "rejection_reasons": [f"token={secret}", "score below threshold"],
        },
    }
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", wrapper_with_secret)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret not in output_text
    assert result["decision"]["classification"] == "evaluate_rejected"


# ===========================================================================
# New tests — secret-safe rendering edge cases
# ===========================================================================

# Test 23
def test_ledger_model_field_secret_suppressed(tmp_path: Path) -> None:
    """api_usage_ledger 'model' field containing secret pattern must not appear in output."""
    secret_model = "AIzaSyFakeModelNameWithSecretPatternXXXXXXXXXXX"
    ledger_with_secret_model = [{
        **_MINIMAL_LEDGER[0],
        "model": secret_model,
    }]
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", ledger_with_secret_model)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_model not in output_text


# Test 24
def test_ledger_api_mode_field_secret_suppressed(tmp_path: Path) -> None:
    """api_usage_ledger 'api_mode' field containing secret pattern must not appear in output."""
    secret_mode = "AIzaSyFakeApiModeWithSecretPatternXXXXXXXXXXXXX"
    ledger_with_secret_mode = [{
        **_MINIMAL_LEDGER[0],
        "api_mode": secret_mode,
    }]
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write(tmp_path, "api_usage_ledger.json", ledger_with_secret_mode)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_mode not in output_text


# Test 25
def test_unexpected_gate_value_secret_suppressed(tmp_path: Path) -> None:
    """passed_adoption_gate with a secret-like string value must not leak into output."""
    secret_gate_value = "AIzaSyFakeGateValueNeverShouldAppearXXXXXXXXXX"
    fitness_bad_gate = {
        "passed_adoption_gate": secret_gate_value,  # not a bool
        "score": 500.0,
        "rejection_reasons": [],
        "tp_rate": 0.8,
        "fp_rate": 0.1,
        "fn_rate": 0.2,
        "candidate_hash": "g" * 64,
    }
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", fitness_bad_gate)

    result = _triage(tmp_path)

    output_text = json.dumps(result)
    assert secret_gate_value not in output_text
    assert result["decision"]["classification"] == "tool_failure"


# Test 26
def test_markdown_output_no_secrets(tmp_path: Path) -> None:
    """Markdown output must not contain secret-pattern values from fitness_report."""
    secret = "AIzaSySecretInScoreOrHashNeverToAppearXXXXXXXXX"
    fitness_with_secret = {
        "passed_adoption_gate": False,
        "rejection_reasons": [f"code={secret}"],
        "score": 300.0,
        "tp_rate": 0.5,
        "fp_rate": 0.5,
        "fn_rate": 0.5,
        "candidate_hash": "h" * 64,
    }
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", fitness_with_secret)

    md_path = tmp_path / "triage.md"
    main(["--artifacts-dir", str(tmp_path), "--json", "--markdown", str(md_path)])

    md_content = md_path.read_text(encoding="utf-8")
    assert secret not in md_content


# ===========================================================================
# New tests — artifact subdirectory layout
# ===========================================================================

# Test 27
def test_artifact_subdir_layout_classification(tmp_path: Path) -> None:
    """Artifacts in subdirectory layout are found and classified correctly."""
    # Create subdirectory layout
    (tmp_path / "mutation-patch").mkdir()
    (tmp_path / "candidate-detector").mkdir()
    (tmp_path / "fitness-report").mkdir()

    _write(tmp_path / "mutation-patch", "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(
        tmp_path / "candidate-detector", "candidate_detector.py",
        "def is_attack(req): return False\n"
    )
    _write(tmp_path / "fitness-report", "fitness_report.json", _FITNESS_PASSED_FLAT)

    result = _triage(tmp_path)

    assert result["artifacts_seen"]["mutation_patch"] is True
    assert result["artifacts_seen"]["candidate_detector"] is True
    assert result["artifacts_seen"]["fitness_report"] is True
    assert result["stage_status"]["mutation_patch_produced"] is True
    assert result["stage_status"]["apply_reached"] is True
    assert result["stage_status"]["evaluate_reached"] is True
    assert result["stage_status"]["adoption_gate_passed"] is True
    assert result["decision"]["classification"] == "promote_eligible"
    # Evidence should mention the subdir layout
    subdir_evidence = [e for e in result["evidence"] if "subdir" in e]
    assert len(subdir_evidence) > 0


# Test 28
def test_flat_layout_takes_priority_over_subdir(tmp_path: Path) -> None:
    """Flat file takes priority over subdirectory file when both exist."""
    # Create flat patch (valid) and subdir patch (malformed)
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)

    (tmp_path / "mutation-patch").mkdir()
    (tmp_path / "mutation-patch" / "mutation_patch.json").write_text(
        "{malformed", encoding="utf-8"
    )

    result = _triage(tmp_path)

    # Should use the flat (valid) file → mutation_patch_produced=True
    assert result["stage_status"]["mutation_patch_produced"] is True
    # No parse warning for mutation_patch
    mp_warnings = [w for w in result["warnings"] if "mutation_patch" in w and "parse" in w.lower()]
    assert len(mp_warnings) == 0


# ===========================================================================
# New tests — promote_eligible semantics
# ===========================================================================

# Test 29
def test_promote_eligible_action_no_misleading_workflow_dispatch(tmp_path: Path) -> None:
    """promote_eligible recommended_next_action must not instruct the Owner to trigger a
    new workflow_dispatch to promote the same already-evaluated candidate.
    The current workflow promotes only within the same run; a new run proposes a new mutation."""
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_FLAT)

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "promote_eligible"
    action = result["decision"]["recommended_next_action"]
    # The action must NOT instruct "trigger a new workflow_dispatch with promote_approved=true"
    # (which would start a brand-new propose run, not promote this candidate).
    # It's OK to MENTION promote_approved=true as context, but not as an instruction to re-run.
    assert "trigger" not in action.lower() or "workflow_dispatch" not in action
    # Must explain that current workflow promotes only within the same run
    assert "same run" in action or "does not promote" in action


# Test 30
def test_promote_eligible_requires_owner_approval(tmp_path: Path) -> None:
    """promote_eligible always sets requires_owner_approval=true."""
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    _write(tmp_path, "fitness_report.json", _FITNESS_PASSED_WRAPPER)

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "promote_eligible"
    assert result["decision"]["requires_owner_approval"] is True


# ===========================================================================
# New tests — _extract_fitness_payload unit tests
# ===========================================================================

# Test 31
def test_extract_fitness_payload_flat() -> None:
    """_extract_fitness_payload returns the dict itself for flat shape."""
    flat = {"passed_adoption_gate": True, "score": 800.0, "rejection_reasons": []}
    payload = _extract_fitness_payload(flat)
    assert payload is not None
    assert payload["passed_adoption_gate"] is True


# Test 32
def test_extract_fitness_payload_wrapper() -> None:
    """_extract_fitness_payload returns nested fitness_report for wrapper shape."""
    nested = {"passed_adoption_gate": False, "score": 200.0, "rejection_reasons": ["too low"]}
    wrapper = {"success": False, "passed_adoption_gate": False, "fitness_report": nested}
    payload = _extract_fitness_payload(wrapper)
    assert payload is not None
    assert payload is nested  # must return the INNER dict (which has full metrics)


# Test 33
def test_extract_fitness_payload_missing_gate_returns_none() -> None:
    """_extract_fitness_payload returns None if passed_adoption_gate is absent."""
    assert _extract_fitness_payload({"score": 500.0}) is None


# Test 34
def test_extract_fitness_payload_non_bool_gate_returns_none() -> None:
    """_extract_fitness_payload returns None if passed_adoption_gate is not a bool."""
    assert _extract_fitness_payload({"passed_adoption_gate": "yes"}) is None
    assert _extract_fitness_payload({"passed_adoption_gate": 1}) is None
    assert _extract_fitness_payload({"passed_adoption_gate": None}) is None


# ===========================================================================
# New tests — _safe_text unit tests
# ===========================================================================

# ===========================================================================
# New tests — invalid UTF-8 artifact robustness
# ===========================================================================

# Test 38
def test_invalid_utf8_fitness_report_is_tool_failure(tmp_path: Path) -> None:
    """fitness_report.json with invalid UTF-8 bytes → tool_failure (fail-closed)."""
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    _write_text(tmp_path, "candidate_detector.py", "def is_attack(req): return False\n")
    (tmp_path / "fitness_report.json").write_bytes(b"\xff\xfe invalid utf-8 content")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "tool_failure"


# Test 39
def test_invalid_utf8_mutation_patch_is_propose_failed(tmp_path: Path) -> None:
    """mutation_patch.json with invalid UTF-8 bytes → propose_failed."""
    (tmp_path / "mutation_patch.json").write_bytes(b"\xff\xfe invalid utf-8 content")

    result = _triage(tmp_path)

    assert result["decision"]["classification"] == "propose_failed"
    # A warning about the unreadable file must be present
    assert any(
        "utf" in w.lower() or "invalid" in w.lower() or "cannot read" in w.lower()
        for w in result["warnings"]
    )


# Test 40
def test_invalid_utf8_candidate_detector_no_crash(tmp_path: Path) -> None:
    """candidate_detector.py with invalid UTF-8 bytes must not crash the triage tool."""
    _write(tmp_path, "mutation_patch.json", _MINIMAL_MUTATION_PATCH)
    (tmp_path / "candidate_detector.py").write_bytes(b"\xff\xfe invalid utf-8 content")

    result = _triage(tmp_path)

    # Tool must not crash and must return a valid classification
    assert result["decision"]["classification"] in {
        "apply_failed_or_not_reached",
        "evaluate_rejected",
        "promote_eligible",
        "tool_failure",
        "propose_failed",
    }


# ===========================================================================
# _safe_text unit tests
# ===========================================================================

# Test 35
def test_safe_text_passes_through_clean_string() -> None:
    assert _safe_text("score too low") == "score too low"
    assert _safe_text("gemini-3-flash-preview") == "gemini-3-flash-preview"


# Test 36
def test_safe_text_suppresses_google_api_key() -> None:
    secret = "AIzaSyFakeApiKeyForTestingPurposesOnly123456"
    result = _safe_text(f"key={secret}")
    assert secret not in result
    assert "[SUPPRESSED_SECRET_PATTERN]" in result


# Test 37
def test_safe_text_handles_non_string_input() -> None:
    assert _safe_text(True) == "True"
    assert _safe_text(42) == "42"
    assert _safe_text(None) == "None"
