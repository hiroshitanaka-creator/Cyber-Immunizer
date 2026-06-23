"""tests/test_promote_structured_candidate.py — Tests for structured-rules promotion.

Covers:
- happy path: re-evaluates live, promotes, flips genome to structured_rules mode
- fail-closed: missing --owner-approved, invalid schema, gate not passed,
  parity-equivalent rules, missing evolution_history
- no writes occur on refusal
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.promote_structured_candidate as psc
from scripts.promote_structured_candidate import main

_DETECT_TOKEN = "special_threat_token"  # unknown to the legacy detector


def _req(path: str = "/", query: dict | None = None, body: str = "") -> dict:
    return {"method": "GET", "path": path, "query": query or {}, "headers": {}, "body": body}


def _entry(id_: str, kind: str, blocked: bool, tags: list[str], request: dict) -> dict:
    return {"id": id_, "kind": kind, "expected_blocked": blocked, "tags": tags, "request": request}


def _write_corpus(corpus_dir: Path, token: str = _DETECT_TOKEN) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "attack_requests.json": [
            _entry("a1", "attack", True, ["attack", "xss"], _req(query={"x": token})),
            _entry("a2", "attack", True, ["attack", "sqli"], _req(path="/" + token)),
        ],
        "benign_requests.json": [
            _entry("b1", "benign", False, ["benign"], _req(path="/home")),
            _entry("b2", "benign", False, ["benign"], _req(path="/about")),
        ],
        "regression_cases.json": [
            _entry("r1", "regression", True, ["regression"], _req(query={"x": token})),
            _entry("r2", "regression", False, ["regression"], _req(path="/ok")),
        ],
        "holdout_requests.json": [
            _entry("h1", "holdout", True, ["attack", "holdout"], _req(query={"y": token})),
        ],
        "counterfactual_requests.json": [
            _entry("c1", "counterfactual", False, ["benign", "counterfactual"], _req(path="/threat-report")),
        ],
        "drift_requests.json": [
            _entry("d1", "drift", True, ["attack", "drift"], _req(path="/d/" + token)),
        ],
    }
    for name, data in files.items():
        (corpus_dir / name).write_text(json.dumps(data), encoding="utf-8")


def _detecting_rules(token: str = _DETECT_TOKEN) -> dict:
    return {
        "schema_version": 1,
        "features": {"surface": {
            "fields": ["method", "path", "query.keys", "query.values", "headers.keys", "headers.values", "body"],
            "normalization": ["lowercase"],
            "max_collection_entries": {"query": 1000, "headers": 1000},
            "max_scalar_bytes": {"method": 4096, "path": 1048576, "query.item": 1048576, "header.item": 1048576},
            "body_scan": {"mode": "full", "max_bytes": 1048576}}},
        "rules": [
            {"id": "t", "field": "surface", "operator": "contains_literal",
             "literal": token, "signal": "threat", "confidence": 0.9},
        ],
        "decision": {"block_when": "any_rule_matches", "reason": "threat",
                     "confidence_strategy": {"type": "fixed", "default": 0.9},
                     "matched_signals": "matched_rule_signals"},
        "fallback": {"blocked": False, "reason": "none", "confidence": 0.0, "matched_signals": []},
    }


def _setup(tmp_path: Path, *, best_score: float = 1.0) -> dict:
    corpus = tmp_path / "corpus"
    _write_corpus(corpus)
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps(_detecting_rules()), encoding="utf-8")
    genome = tmp_path / "genome.json"
    genome.write_text(json.dumps({"generation": 4, "best_score": best_score, "detector_mode": "legacy"}), encoding="utf-8")
    history = tmp_path / "history.json"
    history.write_text(json.dumps([{"generation": 4, "detector_hash": "x", "score": best_score, "passed_adoption_gate": True}]), encoding="utf-8")
    return {
        "corpus": corpus, "rules": rules, "genome": genome, "history": history,
        "active": tmp_path / "active.json",
    }


def _common_args(s: dict, *, owner: bool) -> list[str]:
    args = [
        "--rules", str(s["rules"]), "--corpus-dir", str(s["corpus"]),
        "--genome", str(s["genome"]), "--history", str(s["history"]),
        "--active-rules-out", str(s["active"]), "--json",
    ]
    if owner:
        args.append("--owner-approved")
    return args


def test_happy_path_promotes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    s = _setup(tmp_path)
    rc = main(_common_args(s, owner=True))
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["promoted"] is True
    assert report["mode"] == "structured_rules"
    genome = json.loads(s["genome"].read_text())
    assert genome["detector_mode"] == "structured_rules"
    assert genome["generation"] == 5
    assert genome["best_score"] == report["score"]
    assert genome["current_detector_hash"] == report["detector_hash"]
    assert s["active"].exists()
    history = json.loads(s["history"].read_text())
    assert len(history) == 2
    assert history[-1]["mode"] == "structured_rules"


def test_refuse_without_owner_approved(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    s = _setup(tmp_path)
    rc = main(_common_args(s, owner=False))
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert report["promoted"] is False
    # no writes
    genome = json.loads(s["genome"].read_text())
    assert genome["detector_mode"] == "legacy"
    assert not s["active"].exists()


def test_refuse_invalid_schema(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    s = _setup(tmp_path)
    s["rules"].write_text(json.dumps({"schema_version": 1, "rules": "not-a-list"}), encoding="utf-8")
    rc = main(_common_args(s, owner=True))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["promoted"] is False
    assert json.loads(s["genome"].read_text())["detector_mode"] == "legacy"


def test_refuse_when_gate_not_passed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # best_score very high -> candidate cannot beat it -> score-improvement fails.
    s = _setup(tmp_path, best_score=1_000_000.0)
    rc = main(_common_args(s, owner=True))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["promoted"] is False
    assert json.loads(s["genome"].read_text())["detector_mode"] == "legacy"


def test_refuse_parity_equivalent_to_legacy(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # The symbolic_equivalent ruleset produces identical outcomes to the legacy
    # detector on the symbolic data/ corpus -> parity guard must reject.
    s = _setup(tmp_path)
    s["rules"].write_text(Path("fixtures/structured_rules/symbolic_equivalent.json").read_text(), encoding="utf-8")
    args = [
        "--rules", str(s["rules"]),  # no --corpus-dir => uses repo data/ symbolic corpus
        "--genome", str(s["genome"]), "--history", str(s["history"]),
        "--active-rules-out", str(s["active"]), "--owner-approved", "--json",
    ]
    rc = main(args)
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert report["promoted"] is False
    assert "parity" in report["reason"].lower() or "adoption gate" in report["reason"].lower()
    assert json.loads(s["genome"].read_text())["detector_mode"] == "legacy"


def test_refuse_missing_history(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    s = _setup(tmp_path)
    s["history"].unlink()
    rc = main(_common_args(s, owner=True))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["promoted"] is False
    assert not s["active"].exists()


def test_refuse_non_regular_rules_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A directory (non-regular file) as --rules is refused before any read."""
    s = _setup(tmp_path)
    a_dir = tmp_path / "rules_dir"
    a_dir.mkdir()
    args = [
        "--rules", str(a_dir), "--corpus-dir", str(s["corpus"]),
        "--genome", str(s["genome"]), "--history", str(s["history"]),
        "--active-rules-out", str(s["active"]), "--owner-approved", "--json",
    ]
    rc = main(args)
    assert rc == 1
    assert "not a regular file" in json.loads(capsys.readouterr().out)["reason"]
    assert not s["active"].exists()


def test_refuse_validator_exception(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A rules file that makes the validator raise (OverflowError) is a clean refusal."""
    s = _setup(tmp_path)
    s["rules"].write_text(json.dumps({
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
    rc = main(_common_args(s, owner=True))
    assert rc == 1
    assert "validation raised" in json.loads(capsys.readouterr().out)["reason"]
    assert not s["active"].exists()


def test_refuse_when_rules_file_changes_during_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """TOCTOU guard: if the rules file changes between validation and the gate, refuse."""
    s = _setup(tmp_path)

    def mutating_eval(rules_path, *, genome_path, baseline_mode, corpus_paths):
        # Simulate the file being replaced after the first read; return a pass.
        rules_path.write_text(rules_path.read_text(encoding="utf-8") + "\n ", encoding="utf-8")
        return ({"passed_adoption_gate": True, "score": 999.0, "tp_rate": 1.0,
                 "fp_rate": 0.0, "fn_rate": 0.0, "avg_latency_ms": 0.1}, False)

    monkeypatch.setattr(psc, "evaluate_structured_rules", mutating_eval)
    rc = main(_common_args(s, owner=True))
    assert rc == 1
    assert "changed during evaluation" in json.loads(capsys.readouterr().out)["reason"]
    assert json.loads(s["genome"].read_text())["detector_mode"] == "legacy"
