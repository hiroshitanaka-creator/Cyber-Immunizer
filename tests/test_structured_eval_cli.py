"""Tests for the structured rules evaluation CLI (cli.structured_eval)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.structured_eval import (
    EvalError,
    build_json_report,
    build_markdown,
    load_corpus,
    load_rules,
    main,
    run_evaluation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_rules_doc() -> dict:
    return {
        "schema_version": 1,
        "features": {
            "surface": {
                "fields": ["path", "query.values", "body"],
                "normalization": ["lowercase"],
                "max_collection_entries": {"query": 100, "headers": 100},
                "max_scalar_bytes": {
                    "method": 64,
                    "path": 4096,
                    "query.item": 4096,
                    "header.item": 4096,
                },
                "body_scan": {"mode": "full", "max_bytes": 524288},
            }
        },
        "rules": [
            {
                "id": "r1",
                "field": "surface",
                "operator": "contains_literal",
                "literal": "test_attack_signal",
                "signal": "test_attack_signal",
                "confidence": 0.9,
            }
        ],
        "decision": {
            "block_when": "any_rule_matches",
            "reason": "test attack signal matched",
            "confidence_strategy": {"type": "fixed", "default": 0.9},
            "matched_signals": "matched_rule_signals",
        },
        "fallback": {
            "blocked": False,
            "reason": "no attack signal matched",
            "confidence": 0.0,
            "matched_signals": [],
        },
    }


def _minimal_corpus() -> list[dict]:
    return [
        {
            "id": "attack-001",
            "kind": "attack",
            "expected_blocked": True,
            "tags": ["attack", "test-category"],
            "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
        },
        {
            "id": "benign-001",
            "kind": "benign",
            "expected_blocked": False,
            "tags": ["benign", "baseline"],
            "request": {"method": "GET", "path": "/safe", "query": {}, "headers": {}, "body": ""},
        },
    ]


def _write_json(tmp_path: Path, name: str, data: object) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_rules
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_valid_document_returns_dict(self, tmp_path: Path) -> None:
        p = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        result = load_rules(p)
        assert isinstance(result, dict)
        assert result["schema_version"] == 1

    def test_invalid_json_raises_eval_error(self, tmp_path: Path) -> None:
        p = tmp_path / "rules.json"
        p.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(EvalError, match="not valid JSON"):
            load_rules(p)

    def test_non_object_raises_eval_error(self, tmp_path: Path) -> None:
        p = _write_json(tmp_path, "rules.json", [1, 2, 3])
        with pytest.raises(EvalError, match="must be a JSON object"):
            load_rules(p)

    def test_schema_violation_raises_eval_error(self, tmp_path: Path) -> None:
        doc = _minimal_rules_doc()
        doc["schema_version"] = 99
        p = _write_json(tmp_path, "rules.json", doc)
        with pytest.raises(EvalError, match="validation failed"):
            load_rules(p)

    def test_missing_file_raises_oserror(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            load_rules(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# load_corpus
# ---------------------------------------------------------------------------

class TestLoadCorpus:
    def test_valid_corpus_returns_list(self, tmp_path: Path) -> None:
        p = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        result = load_corpus(p)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_invalid_json_raises_eval_error(self, tmp_path: Path) -> None:
        p = tmp_path / "corpus.json"
        p.write_text("[ not valid json", encoding="utf-8")
        with pytest.raises(EvalError, match="not valid JSON"):
            load_corpus(p)

    def test_non_list_raises_eval_error(self, tmp_path: Path) -> None:
        p = _write_json(tmp_path, "corpus.json", {"key": "value"})
        with pytest.raises(EvalError, match="must be a JSON array"):
            load_corpus(p)

    def test_entry_missing_request_raises_eval_error(self, tmp_path: Path) -> None:
        corpus = [{"id": "x", "expected_blocked": True}]
        p = _write_json(tmp_path, "corpus.json", corpus)
        with pytest.raises(EvalError, match="missing 'request'"):
            load_corpus(p)

    def test_entry_missing_expected_blocked_raises_eval_error(self, tmp_path: Path) -> None:
        corpus = [{"id": "x", "request": {"method": "GET", "path": "/"}}]
        p = _write_json(tmp_path, "corpus.json", corpus)
        with pytest.raises(EvalError, match="missing 'expected_blocked'"):
            load_corpus(p)

    def test_source_ip_null_is_accepted(self, tmp_path: Path) -> None:
        corpus = [{"request": {"source_ip": None}, "expected_blocked": False}]
        p = _write_json(tmp_path, "corpus.json", corpus)
        result = load_corpus(p)
        assert result[0]["request"]["source_ip"] is None

    def test_build_json_report_null_path_raises_eval_error(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        bad_corpus = [{"request": {"path": None}, "expected_blocked": True}]
        corpus_path = _write_json(tmp_path, "corpus.json", bad_corpus)
        with pytest.raises(EvalError, match="must be a string or absent"):
            build_json_report(rules_path, corpus_path)


@pytest.mark.parametrize("bad_entry,match", [
    # expected_blocked type errors
    ({"request": {}, "expected_blocked": "true"}, "must be a JSON boolean"),
    ({"request": {}, "expected_blocked": 1}, "must be a JSON boolean"),
    ({"request": {}, "expected_blocked": None}, "must be a JSON boolean"),
    # request field must be a dict
    ({"request": "not-a-dict", "expected_blocked": True}, "'request' must be a JSON object"),
    # request scalar field type errors (method/path/body/source_ip)
    ({"request": {"method": 123}, "expected_blocked": True}, "must be a string or absent"),
    ({"request": {"path": []}, "expected_blocked": True}, "must be a string or absent"),
    ({"request": {"body": {}}, "expected_blocked": True}, "must be a string or absent"),
    ({"request": {"source_ip": 12345}, "expected_blocked": True}, "must be a string or absent"),
    # explicit null for method/path/body must be rejected (present but not a string)
    ({"request": {"method": None}, "expected_blocked": True}, "must be a string or absent"),
    ({"request": {"path": None}, "expected_blocked": True}, "must be a string or absent"),
    ({"request": {"body": None}, "expected_blocked": True}, "must be a string or absent"),
    # request mapping field type errors (query/headers must be dict)
    ({"request": {"query": "?x=1"}, "expected_blocked": True}, "must be a JSON object or absent"),
    ({"request": {"headers": []}, "expected_blocked": True}, "must be a JSON object or absent"),
    # request mapping field value type errors (values must be str)
    ({"request": {"query": {"q": 1}}, "expected_blocked": True}, r"'query'\["),
    ({"request": {"headers": {"Host": 80}}, "expected_blocked": True}, r"'headers'\["),
    # optional top-level field type errors
    ({"request": {}, "expected_blocked": True, "id": 42}, "must be a string or absent"),
    ({"request": {}, "expected_blocked": True, "kind": 1}, "must be a string or absent"),
    # tags must be a list of strings
    ({"request": {}, "expected_blocked": True, "tags": "attack"}, "must be a list of strings"),
    ({"request": {}, "expected_blocked": True, "tags": ["attack", 2]}, r"'tags'\["),
    # entry must be a dict
    ("not-a-dict", "must be a JSON object"),
])
def test_load_corpus_rejects_malformed(tmp_path: Path, bad_entry: object, match: str) -> None:
    p = _write_json(tmp_path, "corpus.json", [bad_entry])
    with pytest.raises(EvalError, match=match):
        load_corpus(p)


# ---------------------------------------------------------------------------
# run_evaluation
# ---------------------------------------------------------------------------

class TestRunEvaluation:
    def test_true_positive_detected(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "attack-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "test-category"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert results["overall"]["TP"] == 1
        assert results["overall"]["FP"] == 0
        assert results["overall"]["FN"] == 0
        assert results["overall"]["TN"] == 0

    def test_true_negative_for_benign(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "benign-001",
                "kind": "benign",
                "expected_blocked": False,
                "tags": ["benign", "baseline"],
                "request": {"method": "GET", "path": "/safe", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert results["overall"]["TN"] == 1
        assert results["overall"]["TP"] == 0
        assert results["overall"]["FP"] == 0
        assert results["overall"]["FN"] == 0

    def test_false_negative_when_attack_not_detected(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "attack-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "test-category"],
                "request": {"method": "GET", "path": "/no_signal_here", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert results["overall"]["FN"] == 1
        assert results["overall"]["TP"] == 0

    def test_false_positive_when_benign_blocked(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "benign-001",
                "kind": "benign",
                "expected_blocked": False,
                "tags": ["benign", "baseline"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert results["overall"]["FP"] == 1
        assert results["overall"]["TN"] == 0

    def test_per_category_aggregation(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "attack-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "path-traversal"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
            {
                "id": "attack-002",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "sqli"],
                "request": {"method": "POST", "path": "/safe", "query": {}, "headers": {}, "body": ""},
            },
        ]
        results = run_evaluation(rules, corpus)
        cats = results["per_category"]
        assert "path-traversal" in cats
        assert "sqli" in cats
        assert cats["path-traversal"]["TP"] == 1
        assert cats["sqli"]["FN"] == 1

    def test_tags_without_category_gives_uncategorized(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "x",
                "kind": "attack",
                "expected_blocked": False,
                "tags": ["benign"],
                "request": {"method": "GET", "path": "/", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert "uncategorized" in results["per_category"]

    def test_per_case_outcome_field(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "tp-case",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "test"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        results = run_evaluation(rules, corpus)
        assert results["per_case"][0]["outcome"] == "TP"
        assert results["per_case"][0]["matched_signals"] == ["test_attack_signal"]

    def test_empty_corpus_returns_zero_counts(self) -> None:
        results = run_evaluation(_minimal_rules_doc(), [])
        assert results["overall"]["TP"] == 0
        assert results["overall"]["exceptions"] == 0
        assert results["per_category"] == {}
        assert results["per_case"] == []

    def test_per_kind_aggregated_by_kind_field(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "a1",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "test"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
            {
                "id": "h1",
                "kind": "holdout",
                "expected_blocked": True,
                "tags": ["attack", "test"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
            {
                "id": "b1",
                "kind": "benign",
                "expected_blocked": False,
                "tags": ["benign", "test"],
                "request": {"method": "GET", "path": "/safe", "query": {}, "headers": {}, "body": ""},
            },
        ]
        results = run_evaluation(rules, corpus)
        pk = results["per_kind"]
        assert "attack" in pk
        assert "holdout" in pk
        assert "benign" in pk
        assert pk["attack"]["TP"] == 1
        assert pk["holdout"]["TP"] == 1
        assert pk["benign"]["TN"] == 1

    def test_per_kind_in_result_keys(self) -> None:
        results = run_evaluation(_minimal_rules_doc(), _minimal_corpus())
        assert "per_kind" in results

    def test_per_tier_key_in_results(self) -> None:
        results = run_evaluation(_minimal_rules_doc(), _minimal_corpus())
        assert "per_tier" in results

    def test_per_tier_aggregates_holdout_drift_counterfactual_by_tag(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "h1",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "test-cat"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
            {
                "id": "d1",
                "kind": "benign",
                "expected_blocked": False,
                "tags": ["benign", "drift"],
                "request": {"method": "GET", "path": "/safe", "query": {}, "headers": {}, "body": ""},
            },
            {
                "id": "c1",
                "kind": "benign",
                "expected_blocked": False,
                "tags": ["benign", "counterfactual"],
                "request": {"method": "GET", "path": "/safe", "query": {}, "headers": {}, "body": ""},
            },
        ]
        results = run_evaluation(rules, corpus)
        pt = results["per_tier"]
        assert "holdout" in pt
        assert "drift" in pt
        assert "counterfactual" in pt
        assert pt["holdout"]["TP"] == 1
        assert pt["drift"]["TN"] == 1
        assert pt["counterfactual"]["TN"] == 1

    def test_per_tier_entry_counts_in_multiple_tiers(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "multi",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "drift", "test-cat"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
        ]
        results = run_evaluation(rules, corpus)
        pt = results["per_tier"]
        assert pt["holdout"]["TP"] == 1
        assert pt["drift"]["TP"] == 1
        assert "counterfactual" not in pt

    def test_per_tier_empty_when_no_tier_tags(self) -> None:
        results = run_evaluation(_minimal_rules_doc(), _minimal_corpus())
        assert results["per_tier"] == {}

    def test_per_tier_exception_increments_exceptions_only(self) -> None:
        rules = _minimal_rules_doc()
        corpus = [
            {
                "id": "exc1",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            },
        ]
        from unittest.mock import patch
        with patch("cli.structured_eval.inspect_request_with_structured_rules", side_effect=RuntimeError("boom")):
            results = run_evaluation(rules, corpus)
        pt = results["per_tier"]
        assert pt["holdout"]["exceptions"] == 1
        assert pt["holdout"]["TP"] == 0
        assert pt["holdout"]["FN"] == 0


# ---------------------------------------------------------------------------
# build_markdown
# ---------------------------------------------------------------------------

class TestBuildMarkdown:
    def test_markdown_contains_required_sections(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        md = build_markdown(rules_path, corpus_path)
        assert "# Cyber-Immunizer Structured Rules Evaluation Report" in md
        assert "## Overall Results" in md
        assert "## Per-Category Results" in md
        assert "## Per-Case Results" in md
        assert "## Layer 2 Context" in md

    def test_markdown_contains_case_ids(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        md = build_markdown(rules_path, corpus_path)
        assert "attack-001" in md
        assert "benign-001" in md

    def test_markdown_shows_tp_in_overall(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        md = build_markdown(rules_path, corpus_path)
        assert "True Positive (TP) | 1" in md

    def test_markdown_has_per_kind_section(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        md = build_markdown(rules_path, corpus_path)
        assert "## Per-Kind Results" in md
        assert "attack" in md
        assert "benign" in md

    def test_markdown_has_latency_note(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        md = build_markdown(rules_path, corpus_path)
        assert "latency" in md.lower()
        assert "L2-V2" in md

    def test_invalid_rules_raises_eval_error(self, tmp_path: Path) -> None:
        bad_rules = tmp_path / "bad.json"
        bad_rules.write_text("{\"schema_version\": 99}", encoding="utf-8")
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        with pytest.raises(EvalError):
            build_markdown(bad_rules, corpus_path)

    def test_markdown_has_l2v3_tier_section(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        tier_corpus = [
            {
                "id": "h1",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "test-cat"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        corpus_path = _write_json(tmp_path, "corpus.json", tier_corpus)
        md = build_markdown(rules_path, corpus_path)
        assert "## L2-V3 Tier Results" in md
        assert "holdout" in md


# ---------------------------------------------------------------------------
# build_json_report
# ---------------------------------------------------------------------------

class TestBuildJsonReport:
    def test_json_report_structure(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        assert "rules_path" in report
        assert "corpus_path" in report
        assert "overall" in report
        assert "per_category" in report
        assert "per_case" in report

    def test_json_overall_has_rates(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        overall = report["overall"]
        assert "tp_rate" in overall
        assert "fp_rate" in overall
        assert "fn_rate" in overall
        assert "total_cases" in overall

    def test_json_overall_counts_correct(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        overall = report["overall"]
        assert overall["TP"] == 1
        assert overall["TN"] == 1
        assert overall["FP"] == 0
        assert overall["FN"] == 0
        assert overall["total_cases"] == 2
        assert overall["tp_rate"] == 1.0
        assert overall["fp_rate"] == 0.0

    def test_json_per_case_includes_matched_signals(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        tp_case = next(c for c in report["per_case"] if c["outcome"] == "TP")
        assert "test_attack_signal" in tp_case["matched_signals"]

    def test_json_has_per_kind(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        assert "per_kind" in report
        assert "attack" in report["per_kind"]
        assert "benign" in report["per_kind"]
        assert "pass_rate" in report["per_kind"]["attack"]

    def test_json_has_latency_note(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        assert "latency_note" in report

    def test_json_has_per_tier(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        report = build_json_report(rules_path, corpus_path)
        assert "per_tier" in report

    def test_json_per_tier_has_pass_rate(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        tier_corpus = [
            {
                "id": "h1",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "test-cat"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        corpus_path = _write_json(tmp_path, "corpus.json", tier_corpus)
        report = build_json_report(rules_path, corpus_path)
        assert "holdout" in report["per_tier"]
        assert "pass_rate" in report["per_tier"]["holdout"]
        assert report["per_tier"]["holdout"]["TP"] == 1
        assert report["per_tier"]["holdout"]["pass_rate"] == 1.0


# ---------------------------------------------------------------------------
# Integration: fixtures round-trip
# ---------------------------------------------------------------------------

class TestFixturesRoundTrip:
    """Verify the bundled fixtures are valid and produce expected results."""

    _REPO_ROOT = Path(__file__).parent.parent
    _RULES_PATH = _REPO_ROOT / "fixtures" / "structured_rules" / "symbolic_equivalent.json"
    _CORPUS_PATH = _REPO_ROOT / "fixtures" / "evaluation_corpus" / "symbolic_corpus.json"

    def test_symbolic_rules_validates(self) -> None:
        result = load_rules(self._RULES_PATH)
        assert result["schema_version"] == 1

    def test_symbolic_corpus_loads(self) -> None:
        corpus = load_corpus(self._CORPUS_PATH)
        assert len(corpus) == 10

    def test_symbolic_corpus_has_five_attacks_five_benign(self) -> None:
        corpus = load_corpus(self._CORPUS_PATH)
        attacks = [e for e in corpus if e.get("kind") == "attack"]
        benigns = [e for e in corpus if e.get("kind") == "benign"]
        assert len(attacks) == 5
        assert len(benigns) == 5

    def test_symbolic_rules_on_symbolic_corpus_all_correct(self) -> None:
        rules_doc = load_rules(self._RULES_PATH)
        corpus = load_corpus(self._CORPUS_PATH)
        results = run_evaluation(rules_doc, corpus)
        overall = results["overall"]
        assert overall["TP"] == 5
        assert overall["FP"] == 0
        assert overall["TN"] == 5
        assert overall["FN"] == 0
        assert overall["exceptions"] == 0

    def test_symbolic_corpus_has_all_four_attack_categories(self) -> None:
        corpus = load_corpus(self._CORPUS_PATH)
        all_tags = {tag for entry in corpus for tag in entry.get("tags", [])}
        for expected_cat in ("path-traversal", "xss", "sqli", "cmdi"):
            assert expected_cat in all_tags, f"Missing attack category: {expected_cat}"

    def test_markdown_report_runs_on_fixtures(self) -> None:
        md = build_markdown(self._RULES_PATH, self._CORPUS_PATH)
        assert "# Cyber-Immunizer Structured Rules Evaluation Report" in md
        assert "## Per-Category Results" in md

    def test_json_report_runs_on_fixtures(self) -> None:
        report = build_json_report(self._RULES_PATH, self._CORPUS_PATH)
        assert report["overall"]["TP"] == 5
        assert report["overall"]["FP"] == 0
        assert "path-traversal" in report["per_category"]
        assert "xss" in report["per_category"]
        assert "sqli" in report["per_category"]
        assert "cmdi" in report["per_category"]

    def test_per_category_fixtures_validate(self) -> None:
        rules_dir = self._REPO_ROOT / "fixtures" / "structured_rules"
        for name in ("path_traversal_only.json", "xss_only.json", "sqli_only.json", "cmdi_only.json"):
            doc = load_rules(rules_dir / name)
            assert doc["schema_version"] == 1


# ---------------------------------------------------------------------------
# main() CLI entry point
# ---------------------------------------------------------------------------

class TestMainCLI:
    def test_main_markdown_output(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = main(["--rules", str(rules_path), "--corpus", str(corpus_path)])
        assert code == 0
        output = captured.getvalue()
        assert "# Cyber-Immunizer Structured Rules Evaluation Report" in output

    def test_main_json_output(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = main(["--rules", str(rules_path), "--corpus", str(corpus_path), "--json"])
        assert code == 0
        parsed = json.loads(captured.getvalue())
        assert "overall" in parsed
        assert "per_category" in parsed

    def test_main_exits_2_on_invalid_rules(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{\"schema_version\": 999}", encoding="utf-8")
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        with pytest.raises(SystemExit) as exc_info:
            main(["--rules", str(bad), "--corpus", str(corpus_path)])
        assert exc_info.value.code == 2

    def test_main_exits_2_on_missing_rules(self, tmp_path: Path) -> None:
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        with pytest.raises(SystemExit) as exc_info:
            main(["--rules", str(tmp_path / "nonexistent.json"), "--corpus", str(corpus_path)])
        assert exc_info.value.code == 2

    def test_main_missing_required_args_exits_nonzero(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_main_exits_2_on_malformed_corpus(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        bad_corpus = tmp_path / "bad.json"
        bad_corpus.write_text('[{"request": {}, "expected_blocked": "true"}]', encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--rules", str(rules_path), "--corpus", str(bad_corpus)])
        assert exc_info.value.code == 2

    def test_main_exits_2_on_null_body_corpus(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        bad_corpus = [{"request": {"body": None}, "expected_blocked": True}]
        corpus_path = _write_json(tmp_path, "corpus.json", bad_corpus)
        with pytest.raises(SystemExit) as exc_info:
            main(["--rules", str(rules_path), "--corpus", str(corpus_path)])
        assert exc_info.value.code == 2
