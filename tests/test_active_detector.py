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

def test_default_genome_is_legacy_and_matches_inspect_request() -> None:
    # The repository genome ships detector_mode="legacy".
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


def test_never_returns_bool(tmp_path: Path) -> None:
    genome = _write_genome(tmp_path, detector_mode="structured_rules")
    r = _req(path="/x/PATH_TRAVERSAL_INDICATOR")
    result = inspect_active(r, genome_path=genome, active_rules_path=_SYMBOLIC_RULES)
    assert not isinstance(result, bool)
    assert isinstance(result, DetectionResult)
