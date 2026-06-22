"""Tests for latency-aware structured rules evaluation CLI."""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.structured_eval_latency import (
    build_json_report,
    build_markdown,
    main,
    run_evaluation_with_latency,
)


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
            "tags": ["attack", "path-traversal"],
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


def _fake_clock(values: list[float]):
    it = iter(values)
    return lambda: next(it)


class TestRunEvaluationWithLatency:
    def test_per_case_latency_is_recorded(self) -> None:
        clock = _fake_clock([0.0, 0.010, 0.010, 0.030])
        results = run_evaluation_with_latency(_minimal_rules_doc(), _minimal_corpus(), clock=clock)

        cases = results["per_case"]
        assert cases[0]["latency_ms"] == pytest.approx(10.0)
        assert cases[1]["latency_ms"] == pytest.approx(20.0)

    def test_overall_latency_summary_is_recorded(self) -> None:
        clock = _fake_clock([1.0, 1.005, 1.005, 1.020])
        results = run_evaluation_with_latency(_minimal_rules_doc(), _minimal_corpus(), clock=clock)

        overall = results["overall"]
        assert overall["latency_count"] == 2
        assert overall["avg_latency_ms"] == pytest.approx(10.0)
        assert overall["min_latency_ms"] == pytest.approx(5.0)
        assert overall["max_latency_ms"] == pytest.approx(15.0)

    def test_category_latency_summary_is_recorded(self) -> None:
        clock = _fake_clock([0.0, 0.011, 0.011, 0.018])
        results = run_evaluation_with_latency(_minimal_rules_doc(), _minimal_corpus(), clock=clock)

        category = results["per_category"]["path-traversal"]
        assert category["latency_count"] == 1
        assert category["avg_latency_ms"] == pytest.approx(11.0)

    def test_tier_latency_summary_is_recorded(self) -> None:
        corpus = [
            {
                "id": "holdout-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "path-traversal"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]
        clock = _fake_clock([0.0, 0.025])
        results = run_evaluation_with_latency(_minimal_rules_doc(), corpus, clock=clock)

        holdout = results["per_tier"]["holdout"]
        assert holdout["latency_count"] == 1
        assert holdout["avg_latency_ms"] == pytest.approx(25.0)
        assert holdout["TP"] == 1

    def test_exception_case_records_latency_and_exception(self) -> None:
        def boom(*args, **kwargs):
            raise RuntimeError("simulated detector failure")

        clock = _fake_clock([0.0, 0.004])
        with patch("cli.structured_eval_latency.inspect_request_with_structured_rules", side_effect=boom):
            results = run_evaluation_with_latency(_minimal_rules_doc(), [_minimal_corpus()[0]], clock=clock)

        case = results["per_case"][0]
        assert case["outcome"] == "exception"
        assert case["exception"] is True
        assert case["latency_ms"] == pytest.approx(4.0)
        assert results["overall"]["exceptions"] == 1
        assert results["overall"]["latency_count"] == 1

    def test_exception_counts_increment_all_aggregate_buckets(self) -> None:
        corpus = [
            {
                "id": "attack-holdout-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "holdout", "path-traversal"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]

        def boom(*args, **kwargs):
            raise RuntimeError("simulated detector failure")

        clock = _fake_clock([0.0, 0.006])
        with patch("cli.structured_eval_latency.inspect_request_with_structured_rules", side_effect=boom):
            results = run_evaluation_with_latency(_minimal_rules_doc(), corpus, clock=clock)

        assert results["overall"]["exceptions"] == 1
        assert results["per_category"]["path-traversal"]["exceptions"] == 1
        assert results["per_kind"]["attack"]["exceptions"] == 1
        assert results["per_tier"]["holdout"]["exceptions"] == 1
        # The per-case outcome stays the singular "exception" string.
        assert results["per_case"][0]["outcome"] == "exception"

    def test_latency_timer_starts_after_request_construction(self) -> None:
        import cli.structured_eval_latency as mod

        corpus = [
            {
                "id": "attack-001",
                "kind": "attack",
                "expected_blocked": True,
                "tags": ["attack", "path-traversal"],
                "request": {"method": "GET", "path": "/TEST_ATTACK_SIGNAL", "query": {}, "headers": {}, "body": ""},
            }
        ]

        state = {"clock_ticks": 0, "make_request_at_tick": None}
        values = iter([0.0, 0.007])

        def clock() -> float:
            state["clock_ticks"] += 1
            return next(values)

        real_make_request = mod._make_request

        def spy_make_request(entry):
            # Record how many clock ticks were consumed before the Request is built.
            state["make_request_at_tick"] = state["clock_ticks"]
            return real_make_request(entry)

        with patch.object(mod, "_make_request", side_effect=spy_make_request):
            results = run_evaluation_with_latency(_minimal_rules_doc(), corpus, clock=clock)

        # _make_request() ran before the timer started: no clock tick consumed yet.
        assert state["make_request_at_tick"] == 0
        # The measured interval covers only the detector call (0.007 - 0.0 -> 7 ms).
        assert results["per_case"][0]["latency_ms"] == pytest.approx(7.0)


class TestBuildReports:
    def test_json_report_contains_latency_fields(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        report = build_json_report(rules_path, corpus_path)

        assert "avg_latency_ms" in report["overall"]
        assert "max_latency_ms" in report["overall"]
        assert "latency_ms" in report["per_case"][0]
        assert report["overall"]["latency_count"] == 2

    def test_json_report_has_no_latency_note_placeholder(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        report = build_json_report(rules_path, corpus_path)

        assert "latency_note" not in report
        assert "layer2_note" in report

    def test_markdown_report_contains_latency_columns(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        markdown = build_markdown(rules_path, corpus_path)

        assert "Structured Rules Latency Evaluation Report" in markdown
        assert "Avg latency ms" in markdown
        assert "Latency ms" in markdown
        assert "## L2-V3 Tier Results" in markdown

    def test_markdown_has_per_kind_latency_section(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        markdown = build_markdown(rules_path, corpus_path)

        assert "## Per-Kind Results" in markdown
        # Per-kind section exposes pass rate and latency columns.
        assert "Pass rate" in markdown
        assert "Avg latency ms" in markdown
        assert "Max latency ms" in markdown
        # Kind names from the corpus appear as rows.
        assert "attack" in markdown
        assert "benign" in markdown
        # Per-kind heading precedes the tier section in the rendered report.
        assert markdown.index("## Per-Kind Results") < markdown.index("## L2-V3 Tier Results")

    def test_json_and_markdown_preserve_existing_latency_outputs(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        report = build_json_report(rules_path, corpus_path)

        # Existing JSON latency surfaces remain present.
        for key in ("overall", "per_category", "per_kind", "per_tier", "per_case"):
            assert key in report
        assert "avg_latency_ms" in report["overall"]
        assert "max_latency_ms" in report["overall"]
        assert "min_latency_ms" in report["overall"]
        assert "latency_count" in report["overall"]
        assert report["per_category"]["path-traversal"]["avg_latency_ms"] is not None
        assert "latency_ms" in report["per_case"][0]

        markdown = build_markdown(rules_path, corpus_path)
        # Existing Markdown latency surfaces remain present alongside the new section.
        assert "## Overall Results" in markdown
        assert "## Per-Category Results" in markdown
        assert "## Per-Kind Results" in markdown
        assert "## L2-V3 Tier Results" in markdown
        assert "## Per-Case Results" in markdown
        assert "Avg latency ms" in markdown

    def test_main_json_outputs_latency_report(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        captured = io.StringIO()

        with patch("sys.stdout", captured):
            code = main(["--rules", str(rules_path), "--corpus", str(corpus_path), "--json"])

        assert code == 0
        parsed = json.loads(captured.getvalue())
        assert "avg_latency_ms" in parsed["overall"]
        assert "latency_ms" in parsed["per_case"][0]

    def test_main_markdown_outputs_latency_report(self, tmp_path: Path) -> None:
        rules_path = _write_json(tmp_path, "rules.json", _minimal_rules_doc())
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())
        captured = io.StringIO()

        with patch("sys.stdout", captured):
            code = main(["--rules", str(rules_path), "--corpus", str(corpus_path)])

        assert code == 0
        assert "Avg latency ms" in captured.getvalue()

    def test_main_exits_2_on_bad_rules(self, tmp_path: Path) -> None:
        bad_rules = tmp_path / "bad.json"
        bad_rules.write_text('{"schema_version": 99}', encoding="utf-8")
        corpus_path = _write_json(tmp_path, "corpus.json", _minimal_corpus())

        with pytest.raises(SystemExit) as exc_info:
            main(["--rules", str(bad_rules), "--corpus", str(corpus_path)])

        assert exc_info.value.code == 2
