"""tests/test_threat_feed_validation.py — Verify strict threat feed validation.

Tests that malformed threat feed files are rejected in strict mode,
while well-formed feeds load correctly.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from intelligence.threat_feeds import load_active_threats, ThreatRecord


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


def _valid_record(id_: str = "THREAT-001") -> dict:
    return {
        "id": id_,
        "source": "test",
        "summary": "Test threat summary",
        "defensive_focus": "generic",
        "created_at": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests: strict mode rejects malformed files
# ---------------------------------------------------------------------------

class TestStrictModeRejectsInvalid:
    def test_malformed_json_raises_value_error(self):
        p = _write_raw("{not valid json at all")
        with pytest.raises(ValueError, match="[Mm]alformed JSON|JSON"):
            load_active_threats(p, strict=True)

    def test_non_list_top_level_raises_value_error(self):
        p = _write_json({"threats": []})
        with pytest.raises(ValueError, match="list"):
            load_active_threats(p, strict=True)

    def test_non_dict_record_raises_value_error(self):
        p = _write_json(["not a dict"])
        with pytest.raises(ValueError, match="dict"):
            load_active_threats(p, strict=True)

    def test_empty_id_raises_value_error(self):
        bad = _valid_record()
        bad["id"] = ""
        p = _write_json([bad])
        with pytest.raises(ValueError, match="id.*non-empty|non-empty.*id"):
            load_active_threats(p, strict=True)

    def test_empty_summary_raises_value_error(self):
        bad = _valid_record()
        bad["summary"] = ""
        p = _write_json([bad])
        with pytest.raises(ValueError, match="summary"):
            load_active_threats(p, strict=True)

    def test_unknown_defensive_focus_raises_value_error(self):
        bad = _valid_record()
        bad["defensive_focus"] = "unknown-category"
        p = _write_json([bad])
        with pytest.raises(ValueError, match="defensive_focus"):
            load_active_threats(p, strict=True)

    def test_duplicate_ids_raise_value_error(self):
        r1 = _valid_record("DUP-001")
        r2 = _valid_record("DUP-001")
        p = _write_json([r1, r2])
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            load_active_threats(p, strict=True)


# ---------------------------------------------------------------------------
# Tests: strict mode accepts valid files
# ---------------------------------------------------------------------------

class TestStrictModeAcceptsValid:
    def test_real_threats_file_loads(self):
        records = load_active_threats(strict=True)
        assert isinstance(records, list)
        assert len(records) > 0
        for r in records:
            assert isinstance(r, ThreatRecord)

    def test_valid_custom_file_loads(self):
        p = _write_json([_valid_record("T-001"), _valid_record("T-002")])
        records = load_active_threats(p, strict=True)
        assert len(records) == 2
        assert records[0].id == "T-001"

    def test_all_defensive_focus_values_accepted(self):
        records = []
        for i, focus in enumerate(sorted(ThreatRecord._ALLOWED_FOCUSES)):
            records.append({
                "id": f"T-{i:03d}",
                "source": "test",
                "summary": f"Test {focus}",
                "defensive_focus": focus,
                "created_at": "2024-01-01T00:00:00Z",
            })
        p = _write_json(records)
        loaded = load_active_threats(p, strict=True)
        assert len(loaded) == len(ThreatRecord._ALLOWED_FOCUSES)


# ---------------------------------------------------------------------------
# Tests: lenient mode (strict=False) retains legacy behaviour
# ---------------------------------------------------------------------------

class TestLenientModeLegacyBehaviour:
    def test_malformed_json_returns_empty(self):
        p = _write_raw("{not valid")
        records = load_active_threats(p, strict=False)
        assert records == []

    def test_malformed_record_skipped(self):
        p = _write_json([{"id": "", "summary": ""}])
        records = load_active_threats(p, strict=False)
        # Empty id causes ThreatRecord.__post_init__ to raise — record is skipped
        assert records == []
