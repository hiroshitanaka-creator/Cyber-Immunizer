"""tests/test_generalization.py — Unknown-threat generalization measurement (M3)."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.generalization_report as gr
from core.structured_validator import validate_rules_schema

_ROOT = Path(__file__).parent.parent
_HELDOUT = _ROOT / "fixtures" / "generalization_corpus" / "heldout_threats.json"
_RULES = _ROOT / "fixtures" / "structured_rules" / "realistic_baseline.json"


def _heldout() -> list[dict]:
    return json.loads(_HELDOUT.read_text(encoding="utf-8"))


def test_heldout_corpus_is_valid_and_covers_unknowns() -> None:
    cases = _heldout()
    assert isinstance(cases, list) and cases
    tags = {t for c in cases for t in c.get("tags", [])}
    # Must contain BOTH evasive variants of known classes and brand-new classes.
    assert "variant" in tags and "newclass" in tags
    # New classes the proposer was never shown.
    assert {"ssrf", "xxe", "ssti", "nosqli", "ldapi"} & tags
    # Held-out benign near-misses present (to measure false positives on unknowns).
    assert any(c["expected_blocked"] is False for c in cases)
    for c in cases:
        assert "request" in c and "expected_blocked" in c


def test_realistic_rules_schema_valid() -> None:
    assert validate_rules_schema(json.loads(_RULES.read_text(encoding="utf-8"))).get("success") is True


def test_generalization_report_quantifies_the_gap() -> None:
    report = gr.build_report(_RULES, gr._DEFAULT_IN, _HELDOUT)
    # In-distribution detection is strong (the detector is built for these).
    assert report["in_distribution"]["tp_rate"] == 1.0
    # Held-out detection is reported as a fraction in [0, 1].
    ho = report["held_out"]["tp_rate"]
    assert 0.0 <= ho <= 1.0
    # Quality bar that must hold even on unknowns: no false positives on held-out benign.
    assert report["held_out"]["fp_rate"] == 0.0
    # The gap is reported (in-distribution minus held-out); >= 0 by construction.
    assert report["generalization_gap"] >= 0.0


def test_main_runs(capsys) -> None:
    assert gr.main(["--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "held_out" in out and "in_distribution" in out
