"""tests/test_realistic_ruleset.py — Regression guard for the committed realistic
defensive ruleset against the committed realistic corpus.

This locks in real defensive value: the realistic structured ruleset
(`fixtures/structured_rules/realistic_baseline.json`) must detect every realistic
attack in `fixtures/realistic_corpus/` and must not flag any benign request,
including the counterfactual near-miss benign cases. It uses the real structured
detector path (no mocks).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.runtime_selector import inspect_request_with_runtime_selector
from core.structured_validator import validate_rules_schema
from core.types import Request

_ROOT = Path(__file__).parent.parent
_RULES = _ROOT / "fixtures" / "structured_rules" / "realistic_baseline.json"
_CORPUS = _ROOT / "fixtures" / "realistic_corpus"
_TIER_FILES = (
    "attack_requests.json", "benign_requests.json", "regression_cases.json",
    "holdout_requests.json", "counterfactual_requests.json", "drift_requests.json",
)


def _rules() -> dict:
    return json.loads(_RULES.read_text(encoding="utf-8"))


def _all_cases() -> list[dict]:
    cases: list[dict] = []
    for name in _TIER_FILES:
        cases.extend(json.loads((_CORPUS / name).read_text(encoding="utf-8")))
    return cases


def _request(entry: dict) -> Request:
    req = entry["request"]
    return Request(
        method=req.get("method", "GET"), path=req.get("path", "/"),
        query=dict(req.get("query") or {}), headers=dict(req.get("headers") or {}),
        body=req.get("body", ""), source_ip=req.get("source_ip"),
    )


def test_realistic_ruleset_passes_schema() -> None:
    assert validate_rules_schema(_rules()).get("success") is True


def test_combined_corpus_matches_tier_concatenation() -> None:
    """fixtures/realistic_corpus/all_cases.json must equal the six tier files
    concatenated (in fixed order) so the committed cli/structured_eval evidence
    is reproducible and cannot silently drift from the per-tier files."""
    expected: list[dict] = []
    for name in _TIER_FILES:
        expected.extend(json.loads((_CORPUS / name).read_text(encoding="utf-8")))
    combined = json.loads((_CORPUS / "all_cases.json").read_text(encoding="utf-8"))
    assert combined == expected


def test_realistic_ruleset_detects_all_attacks_no_false_positives() -> None:
    rules = _rules()
    tp = fp = tn = fn = 0
    misses: list[str] = []
    false_alarms: list[str] = []
    for entry in _all_cases():
        result = inspect_request_with_runtime_selector(
            _request(entry), mode="structured_rules", structured_rules_doc=rules
        )
        expected = entry["expected_blocked"]
        if expected and result.blocked:
            tp += 1
        elif expected and not result.blocked:
            fn += 1
            misses.append(entry["id"])
        elif not expected and result.blocked:
            fp += 1
            false_alarms.append(entry["id"])
        else:
            tn += 1
    assert fn == 0, f"missed attacks (false negatives): {misses}"
    assert fp == 0, f"flagged benign (false positives): {false_alarms}"
    assert tp > 0 and tn > 0


@pytest.mark.parametrize("category", ["path-traversal", "xss", "sqli", "cmdi"])
def test_each_required_category_has_detected_attacks(category: str) -> None:
    rules = _rules()
    detected = 0
    for entry in _all_cases():
        if entry["expected_blocked"] and category in entry.get("tags", []):
            result = inspect_request_with_runtime_selector(
                _request(entry), mode="structured_rules", structured_rules_doc=rules
            )
            assert result.blocked, f"{entry['id']} ({category}) not detected"
            detected += 1
    assert detected > 0, f"no attack cases tagged {category}"


def test_counterfactual_benign_not_blocked() -> None:
    """Near-miss benign requests (attack-adjacent vocabulary, no real signature)
    must not be blocked — guards against shallow overfitting."""
    rules = _rules()
    cf = json.loads((_CORPUS / "counterfactual_requests.json").read_text(encoding="utf-8"))
    for entry in cf:
        result = inspect_request_with_runtime_selector(
            _request(entry), mode="structured_rules", structured_rules_doc=rules
        )
        assert result.blocked is False, f"counterfactual {entry['id']} wrongly blocked"
