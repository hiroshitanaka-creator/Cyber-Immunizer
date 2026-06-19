"""Regression tests for PR-B schema validator edge cases.

These tests cover the review findings that must be fixed before PR #131 can
merge:
- validate_state.py must catch duplicate corpus IDs across corpus files.
- corpus kind must be type-checked before set membership.
- threat-feed defensive_focus must be type-checked before set membership.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.test_attacker import _load_corpus_file
from intelligence.threat_feeds import load_active_threats
from scripts.validate_state import validate_all


def _request() -> dict:
    return {
        "method": "GET",
        "path": "/",
        "query": {},
        "headers": {},
        "body": "",
    }


def _corpus_record(
    *,
    id_: str,
    kind: object,
    expected_blocked: bool,
) -> dict:
    return {
        "id": id_,
        "kind": kind,
        "expected_blocked": expected_blocked,
        "request": _request(),
    }


def _threat_record(*, defensive_focus: object = "generic") -> dict:
    return {
        "id": "THREAT-EDGE-001",
        "source": "test",
        "summary": "schema edge case",
        "defensive_focus": defensive_focus,
        "created_at": "2026-06-19T00:00:00Z",
    }


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestCorpusKindTypeValidation:
    def test_kind_list_raises_value_error(self, tmp_path: Path):
        corpus = tmp_path / "corpus.json"
        _write_json(
            corpus,
            [_corpus_record(id_="case-kind-list", kind=[], expected_blocked=False)],
        )

        with pytest.raises(ValueError, match="kind.*str"):
            _load_corpus_file(corpus, "benign", False, set())

    def test_kind_dict_raises_value_error(self, tmp_path: Path):
        corpus = tmp_path / "corpus.json"
        _write_json(
            corpus,
            [_corpus_record(id_="case-kind-dict", kind={}, expected_blocked=False)],
        )

        with pytest.raises(ValueError, match="kind.*str"):
            _load_corpus_file(corpus, "benign", False, set())


class TestThreatFeedDefensiveFocusTypeValidation:
    def test_defensive_focus_list_raises_value_error(self, tmp_path: Path):
        feed = tmp_path / "active_threats.json"
        _write_json(feed, [_threat_record(defensive_focus=[])])

        with pytest.raises(ValueError, match="defensive_focus.*str"):
            load_active_threats(feed, strict=True)

    def test_defensive_focus_dict_raises_value_error(self, tmp_path: Path):
        feed = tmp_path / "active_threats.json"
        _write_json(feed, [_threat_record(defensive_focus={})])

        with pytest.raises(ValueError, match="defensive_focus.*str"):
            load_active_threats(feed, strict=True)


class TestValidateStateCrossFileDuplicateIds:
    def test_validate_all_catches_duplicate_corpus_ids_across_files(self, tmp_path: Path):
        data_dir = tmp_path

        _write_json(
            data_dir / "genome.json",
            {
                "generation": 0,
                "best_score": 0.0,
                "max_fp_rate": 0.05,
                "min_regression_pass_rate": 1.0,
                "max_model_requests_per_run": 1,
                "send_repository_full_text": False,
                "send_raw_payloads": False,
                "send_secrets": False,
            },
        )
        _write_json(data_dir / "evolution_history.json", [])
        _write_json(data_dir / "project_state.json", {})
        _write_json(data_dir / "active_threats.json", [_threat_record()])

        duplicate_id = "duplicate-across-files"
        _write_json(
            data_dir / "benign_requests.json",
            [
                _corpus_record(
                    id_=duplicate_id,
                    kind="benign",
                    expected_blocked=False,
                )
            ],
        )
        _write_json(
            data_dir / "attack_requests.json",
            [
                _corpus_record(
                    id_=duplicate_id,
                    kind="attack",
                    expected_blocked=True,
                )
            ],
        )
        _write_json(data_dir / "regression_cases.json", [])

        result = validate_all(data_dir)

        assert result["success"] is False
        assert any("Duplicate corpus record id" in v for v in result["violations"]), (
            f"Expected cross-file duplicate ID violation, got: {result['violations']}"
        )
