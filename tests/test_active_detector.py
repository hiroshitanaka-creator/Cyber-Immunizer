"""tests/test_active_detector.py — Tests for the active-detector runtime resolver.

Covers:
- legacy mode (default) dispatches to core.detector.inspect_request
- structured_rules mode dispatches to the structured path
- fail-safe fallback to legacy on missing / corrupt / oversize / invalid rules
- fail-safe fallback to legacy on unreadable genome and unknown mode
- the DetectionResult contract (never bool, never raises)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.active_detector import inspect_active
from core.detector import inspect_request
from core.types import DetectionResult, Request

_SYMBOLIC_RULES = Path("fixtures/structured_rules/symbolic_equivalent.json")


def _req(path: str = "/", query: dict | None = None, body: str = "") -> Request:
    return Request(method="GET", path=path, query=query or {}, headers={}, body=body)


def _write_genome(tmp_path: Path, **fields) -> Path:
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(fields), encoding="utf-8")
    return p


# --- legacy mode -----------------------------------------------------------

def test_shipped_genome_active_detector_is_consistent_and_safe() -> None:
    # The repository genome's detector_mode reflects the latest owner-approved
    # promotion: it ships "structured_rules" after the run #80 structured
    # promotion, and an owner-approved rollback would return it to "legacy".
    # The shipped genome's active detector must honor the DetectionResult
    # contract in either mode, keep a clearly-benign request allowed, and —
    # when legacy — stay equivalent to inspect_request. (Explicit-legacy
    # equivalence is also covered by test_explicit_legacy_mode_matches_inspect_request.)
    genome = json.loads(Path("data/genome.json").read_text(encoding="utf-8"))
    mode = genome.get("detector_mode", "legacy")
    for r in (_req(path="/x/PATH_TRAVERSAL_INDICATOR"), _req(path="/clean")):
        result = inspect_active(r)
        assert isinstance(result, DetectionResult)
        assert not isinstance(result, bool)
    assert inspect_active(_req(path="/clean")).blocked is False
    if mode == "legacy":
        for r in (_req(path="/x/PATH_TRAVERSAL_INDICATOR"), _req(path="/clean")):
            assert inspect_active(r) == inspect_request(r)


def test_explicit_legacy_mode_matches_inspect_request(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="legacy")
    r = _req(query={"q": "SQLI_INDICATOR"})
    assert inspect_active(r, genome_path=genome) == inspect_request(r)


def test_unknown_mode_falls_back_to_legacy(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="nonsense")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=genome) == inspect_request(r)


def test_unreadable_genome_falls_back_to_legacy(tmp_path: Path) -> None:
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=tmp_path / "missing.json") == inspect_request(r)


# --- structured_rules mode -------------------------------------------------

def test_structured_mode_uses_structured_rules(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    result = inspect_active(r, genome_path=genome, active_rules_path=_SYMBOLIC_RULES)
    assert isinstance(result, DetectionResult)
    assert result.blocked is True
    assert "symbolic_path_traversal" in result.matched_signals


def test_structured_mode_benign_is_not_blocked(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    r = _req(path="/home")
    result = inspect_active(r, genome_path=genome, active_rules_path=_SYMBOLIC_RULES)
    assert result.blocked is False


def test_structured_mode_reads_path_from_genome(tmp_path: Path) -> None:
    genome = _write_genome(
        tmp_path,
        detector_mode="structured_rules",
        active_structured_rules_path=str(_SYMBOLIC_RULES.resolve()),
    )
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    result = inspect_active(r, genome_path=genome)
    assert result.blocked is True


# --- fail-safe fallbacks in structured mode --------------------------------

def test_missing_rules_falls_back_to_legacy(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=genome, active_rules_path=tmp_path / "nope.json") == inspect_request(r)


def test_corrupt_rules_falls_back_to_legacy(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=genome, active_rules_path=bad) == inspect_request(r)


def test_invalid_schema_rules_falls_back_to_legacy(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    bad = tmp_path / "schema.json"
    bad.write_text(json.dumps({"schema_version": 1, "rules": "not-a-list"}), encoding="utf-8")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=genome, active_rules_path=bad) == inspect_request(r)


def test_oversize_rules_falls_back_to_legacy(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    big = tmp_path / "big.json"
    big.write_text("0" * (1_048_576 + 10), encoding="utf-8")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    assert inspect_active(r, genome_path=genome, active_rules_path=big) == inspect_request(r)


def test_validator_exception_falls_back_to_legacy(tmp_path: Path) -> None:
    """A rules file that makes validate_rules_schema raise (e.g. OverflowError on a
    huge confidence) must fall back to legacy, not propagate the exception."""
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    rules = tmp_path / "overflow.json"
    rules.write_text(json.dumps({
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
    }), encoding="utf-8")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    # Must not raise; must equal the legacy result.
    assert inspect_active(r, genome_path=genome, active_rules_path=rules) == inspect_request(r)


def test_never_returns_bool(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    result = inspect_active(r, genome_path=genome, active_rules_path=_SYMBOLIC_RULES)
    assert not isinstance(result, bool)
    assert isinstance(result, DetectionResult)
