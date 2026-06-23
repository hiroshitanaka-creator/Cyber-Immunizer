"""tests/test_evolution_cycle_offline.py — Offline self-evolution cycle (M1 plumbing).

Proves the autonomous loop runs end-to-end WITHOUT any API call:
  propose (structured, offline-sample) -> evaluate (adoption gate) -> promote
The live variant swaps step 1 for `--structured-rules --gemini-paid-credit`
(Owner-gated); this test fixes the orchestration the workflow will drive.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.propose_mutation as pm
import scripts.promote_structured_candidate as psc
from scripts.evaluate_structured_rules_candidate import main as eval_main


def test_offline_self_evolution_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture) -> None:
    out_dir = tmp_path / "out"
    rules_out = out_dir / "structured_rules.json"
    monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
    monkeypatch.setattr(pm, "_OUT_STRUCTURED_RULES", rules_out)
    monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")

    # 1. PROPOSE — structured rules, offline, no API.
    assert pm.main(["--structured-rules", "--offline-sample", "--json"]) == 0
    assert rules_out.exists()
    capsys.readouterr()

    # 2. EVALUATE — through the real adoption gate (baseline; symbolic data/ corpus
    #    matches the offline-sample symbolic rules).
    assert eval_main(["--rules", str(rules_out), "--baseline", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed_adoption_gate"] is True

    # 3. PROMOTE — decoupled activation into an isolated genome.
    genome = tmp_path / "genome.json"
    genome.write_text(json.dumps({
        "generation": 4, "best_score": 1.0,
        "detector_mode": "legacy", "current_detector_hash": "abc",
    }), encoding="utf-8")
    history = tmp_path / "history.json"
    history.write_text("[]", encoding="utf-8")
    active = tmp_path / "active.json"
    rc = psc.main([
        "--rules", str(rules_out), "--baseline", "--owner-approved",
        "--genome", str(genome), "--history", str(history),
        "--active-rules-out", str(active), "--json",
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["promoted"] is True

    # End-to-end result: active detector switched; legacy lineage untouched.
    g = json.loads(genome.read_text())
    assert g["detector_mode"] == "structured_rules"
    assert g["active_structured_rules_hash"]
    assert g["generation"] == 4 and g["best_score"] == 1.0
    assert g["current_detector_hash"] == "abc"
    assert active.exists()
