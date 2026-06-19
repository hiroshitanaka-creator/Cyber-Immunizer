"""tests/test_corpus_schema.py — Verify strict corpus schema validation.

Tests that malformed or poisoned corpus/state files are rejected, including:
- expected_blocked string coercion prevention
- query/headers type enforcement
- missing required fields
- duplicate ID rejection
- malformed JSON rejection
- validate_state.py CLI
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.test_attacker import load_test_cases, _load_corpus_file, _validate_corpus_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(data: object) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    json.dump(data, tmp)
    tmp.flush()
    return Path(tmp.name)


def _write_raw(text: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(text)
    tmp.flush()
    return Path(tmp.name)


def _benign_record(id_: str = "b-001") -> dict:
    return {
        "id": id_,
        "kind": "benign",
        "expected_blocked": False,
        "request": {"method": "GET", "path": "/", "query": {}, "headers": {}, "body": ""},
    }


def _attack_record(id_: str = "a-001") -> dict:
    return {
        "id": id_,
        "kind": "attack",
        "expected_blocked": True,
        "request": {"method": "GET", "path": "/atk", "query": {}, "headers": {}, "body": ""},
    }


# ---------------------------------------------------------------------------
# Tests: expected_blocked strict bool enforcement
# ---------------------------------------------------------------------------

class TestExpectedBlockedStrictBool:
    def test_string_false_rejected(self):
        bad = _benign_record()
        bad["expected_blocked"] = "false"
        p = _write_json([bad])
        with pytest.raises(ValueError, match="expected_blocked.*bool"):
            _load_corpus_file(p, "benign", False, set())

    def test_string_true_rejected(self):
        bad = _benign_record()
        bad["expected_blocked"] = "true"
        p = _write_json([bad])
        with pytest.raises(ValueError, match="expected_blocked.*bool"):
            _load_corpus_file(p, "benign", False, set())

    def test_int_zero_rejected(self):
        bad = _benign_record()
        bad["expected_blocked"] = 0
        p = _write_json([bad])
        with pytest.raises(ValueError, match="expected_blocked.*bool"):
            _load_corpus_file(p, "benign", False, set())

    def test_int_one_rejected(self):
        bad = _benign_record()
        bad["expected_blocked"] = 1
        p = _write_json([bad])
        with pytest.raises(ValueError, match="expected_blocked.*bool"):
            _load_corpus_file(p, "benign", False, set())

    def test_bool_false_accepted(self):
        good = _benign_record()
        good["expected_blocked"] = False
        p = _write_json([good])
        _load_corpus_file(p, "benign", False, set())  # should not raise

    def test_bool_true_accepted(self):
        good = _attack_record()
        good["expected_blocked"] = True
        p = _write_json([good])
        _load_corpus_file(p, "attack", True, set())  # should not raise


# ---------------------------------------------------------------------------
# Tests: request field type enforcement
# ---------------------------------------------------------------------------

class TestRequestFieldTypes:
    def test_query_with_int_value_rejected(self):
        bad = _benign_record()
        bad["request"]["query"] = {"x": 1}
        p = _write_json([bad])
        with pytest.raises(ValueError, match="query"):
            _load_corpus_file(p, "benign", False, set())

    def test_headers_with_int_value_rejected(self):
        bad = _benign_record()
        bad["request"]["headers"] = {"Authorization": 42}
        p = _write_json([bad])
        with pytest.raises(ValueError, match="headers"):
            _load_corpus_file(p, "benign", False, set())

    def test_method_as_int_rejected(self):
        bad = _benign_record()
        bad["request"]["method"] = 404
        p = _write_json([bad])
        with pytest.raises(ValueError, match="method"):
            _load_corpus_file(p, "benign", False, set())

    def test_request_as_list_rejected(self):
        bad = _benign_record()
        bad["request"] = ["GET", "/"]
        p = _write_json([bad])
        with pytest.raises(ValueError, match="request"):
            _load_corpus_file(p, "benign", False, set())


# ---------------------------------------------------------------------------
# Tests: missing required fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_missing_request_field_rejected(self):
        bad = {"id": "b-001", "kind": "benign", "expected_blocked": False}
        p = _write_json([bad])
        with pytest.raises(ValueError, match="request.*missing|missing.*request"):
            _load_corpus_file(p, "benign", False, set())

    def test_missing_id_field_rejected(self):
        bad = {"kind": "benign", "expected_blocked": False,
               "request": {"method": "GET", "path": "/"}}
        p = _write_json([bad])
        with pytest.raises(ValueError, match="id.*non-empty|non-empty.*id"):
            _load_corpus_file(p, "benign", False, set())

    def test_empty_id_rejected(self):
        bad = _benign_record()
        bad["id"] = ""
        p = _write_json([bad])
        with pytest.raises(ValueError, match="id.*non-empty|non-empty.*id"):
            _load_corpus_file(p, "benign", False, set())


# ---------------------------------------------------------------------------
# Tests: duplicate IDs
# ---------------------------------------------------------------------------

class TestDuplicateIds:
    def test_duplicate_ids_rejected(self):
        r1 = _benign_record("dup-001")
        r2 = _benign_record("dup-001")
        p = _write_json([r1, r2])
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            _load_corpus_file(p, "benign", False, set())

    def test_unique_ids_accepted(self):
        r1 = _benign_record("uniq-001")
        r2 = _benign_record("uniq-002")
        p = _write_json([r1, r2])
        _load_corpus_file(p, "benign", False, set())  # should not raise


# ---------------------------------------------------------------------------
# Tests: malformed JSON
# ---------------------------------------------------------------------------

class TestMalformedJson:
    def test_invalid_json_raises_value_error(self):
        p = _write_raw("{not valid json")
        with pytest.raises(ValueError, match="[Mm]alformed JSON|JSON"):
            _load_corpus_file(p, "benign", False, set())

    def test_non_list_top_level_raises_value_error(self):
        p = _write_json({"records": []})
        with pytest.raises(ValueError, match="list"):
            _load_corpus_file(p, "benign", False, set())

    def test_null_top_level_raises_value_error(self):
        p = _write_json(None)
        with pytest.raises(ValueError, match="list"):
            _load_corpus_file(p, "benign", False, set())


# ---------------------------------------------------------------------------
# Tests: validate_state.py CLI and genome/history checks
# ---------------------------------------------------------------------------

class TestValidateStateCLI:
    def test_current_repo_state_passes(self):
        """validate_state.py must pass on the current unmodified repository."""
        from scripts.validate_state import validate_all
        result = validate_all()
        assert result["success"], (
            f"validate_state failed on real data: {result['violations']}"
        )
        assert len(result["checked_files"]) >= 7

    def test_invalid_genome_send_secrets_true_fails(self, tmp_path):
        from scripts.validate_state import _check_genome
        genome = {
            "generation": 0,
            "best_score": 0.0,
            "max_fp_rate": 0.05,
            "min_regression_pass_rate": 1.0,
            "max_model_requests_per_run": 1,
            "send_repository_full_text": False,
            "send_raw_payloads": False,
            "send_secrets": True,  # should fail
        }
        p = tmp_path / "genome.json"
        p.write_text(json.dumps(genome))
        violations = _check_genome(p)
        assert any("send_secrets" in v for v in violations), (
            f"Expected send_secrets violation, got: {violations}"
        )

    def test_invalid_genome_max_model_requests_2_fails(self, tmp_path):
        from scripts.validate_state import _check_genome
        genome = {
            "generation": 0,
            "best_score": 0.0,
            "max_fp_rate": 0.05,
            "min_regression_pass_rate": 1.0,
            "max_model_requests_per_run": 2,  # should fail
            "send_repository_full_text": False,
            "send_raw_payloads": False,
            "send_secrets": False,
        }
        p = tmp_path / "genome.json"
        p.write_text(json.dumps(genome))
        violations = _check_genome(p)
        assert any("max_model_requests_per_run" in v for v in violations), (
            f"Expected max_model_requests_per_run violation, got: {violations}"
        )

    def test_malformed_evolution_history_fails(self, tmp_path):
        from scripts.validate_state import _check_evolution_history
        bad_history = [
            {"generation": "not-an-int", "passed_adoption_gate": True}
        ]
        p = tmp_path / "evolution_history.json"
        p.write_text(json.dumps(bad_history))
        violations = _check_evolution_history(p)
        assert len(violations) > 0, "Expected violations for non-int generation"

    def test_evolution_history_non_hex_hash_fails(self, tmp_path):
        from scripts.validate_state import _check_evolution_history
        bad_history = [
            {"generation": 0, "detector_hash": "not-a-hex-hash", "passed_adoption_gate": False}
        ]
        p = tmp_path / "evolution_history.json"
        p.write_text(json.dumps(bad_history))
        violations = _check_evolution_history(p)
        assert any("detector_hash" in v for v in violations), (
            f"Expected detector_hash violation, got: {violations}"
        )

    def test_evolution_history_bool_gate_non_bool_fails(self, tmp_path):
        from scripts.validate_state import _check_evolution_history
        bad_history = [
            {"generation": 0, "passed_adoption_gate": "yes"}
        ]
        p = tmp_path / "evolution_history.json"
        p.write_text(json.dumps(bad_history))
        violations = _check_evolution_history(p)
        assert any("passed_adoption_gate" in v for v in violations), (
            f"Expected passed_adoption_gate violation, got: {violations}"
        )


# ---------------------------------------------------------------------------
# Tests: load_test_cases integration
# ---------------------------------------------------------------------------

class TestLoadTestCasesStrict:
    def test_real_data_loads_successfully(self):
        """The real corpus files must load without errors under strict validation."""
        cases = load_test_cases()
        assert len(cases) > 0

    def test_poisoned_benign_file_rejected(self, tmp_path):
        bad = _benign_record()
        bad["expected_blocked"] = "false"
        benign_p = tmp_path / "benign_requests.json"
        benign_p.write_text(json.dumps([bad]))

        from pathlib import Path as _P
        _DATA_DIR = _P(__file__).parent.parent / "data"

        with pytest.raises(ValueError):
            load_test_cases(
                benign_path=benign_p,
                attack_path=_DATA_DIR / "attack_requests.json",
                regression_path=_DATA_DIR / "regression_cases.json",
            )
