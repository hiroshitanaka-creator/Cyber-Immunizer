"""tests/test_evaluate_structured_rules_candidate.py — Tests for PR-E1 evaluation script.

Tests cover:
1. CLI requires explicit --rules (no auto-load from .cyber_immunizer/**)
2. Equivalent structured rules evaluate successfully
3. Runtime selector is actually called with mode="structured_rules" and explicit doc
4. Malformed JSON is a tool failure (exit 1, success=False)
5. Invalid schema is candidate rejection (success=False, evaluation_completed=True)
6. No default report file written (no .cyber_immunizer/** output)
7. Explicit --report-path writes report
8. No forbidden side effects (no sockets, no subprocess)
9. core/detector.py has no runtime_selector/structured references
10. Genome load failure is a tool failure (fail-closed)
11. code_chars uses JSON doc character count (not 0)
12. Oversized rules file is a tool failure (Fix 1)
13. Forbidden --report-path is rejected (Fix 2)
14. Parity guard rejects behavior-equivalent rules without --baseline (Fix 3)
15. Genome threshold validation rejects invalid values (Fix 4)
16. Duplicate keys in rules JSON are rejected (Fix 5)
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.evaluate_structured_rules_candidate as mod
from scripts.evaluate_structured_rules_candidate import main
from core.types import DetectionResult, Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def equivalent_rules_doc() -> dict:
    """Return the same equivalent structured rules doc used by existing selector tests."""
    indicators = (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    )

    def rule(indicator: str) -> dict:
        return {
            "id": indicator,
            "field": "surface",
            "operator": "contains_literal",
            "literal": indicator,
            "signal": indicator,
            "confidence": 0.86,
        }

    return {
        "schema_version": 1,
        "features": {
            "surface": {
                "fields": [
                    "method",
                    "path",
                    "query.keys",
                    "query.values",
                    "headers.keys",
                    "headers.values",
                    "body",
                ],
                "normalization": ["lowercase"],
                "max_collection_entries": {"query": 1000, "headers": 1000},
                "max_scalar_bytes": {
                    "method": 4096,
                    "path": 1048576,
                    "query.item": 1048576,
                    "header.item": 1048576,
                },
                "body_scan": {"mode": "full", "max_bytes": 1048576},
            }
        },
        "rules": [rule(indicator) for indicator in indicators],
        "decision": {
            "block_when": "any_rule_matches",
            "reason": "suspicious indicator matched",
            "confidence_strategy": {
                "type": "bounded_match_count",
                "default": 0.86,
                "two_matches": 0.94,
                "three_or_more_matches": 0.99,
            },
            "matched_signals": "matched_rule_signals",
        },
        "fallback": {
            "blocked": False,
            "reason": "no suspicious indicator matched",
            "confidence": 0.0,
            "matched_signals": [],
        },
    }


def write_rules(tmp_path: Path, rules_doc: dict) -> Path:
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(rules_doc), encoding="utf-8")
    return p


def permissive_genome() -> dict:
    """Return a genome dict with thresholds set so all gates except parity pass."""
    return {
        "best_score": -1e9,
        "max_fp_rate": 1.0,
        "min_regression_pass_rate": 0.0,
        "max_avg_latency_ms": 1e9,
        "min_holdout_pass_rate": 0.0,
        "min_counterfactual_pass_rate": 0.0,
        "min_drift_pass_rate": 0.0,
    }


# ---------------------------------------------------------------------------
# 1. CLI requires explicit --rules (no auto-load)
# ---------------------------------------------------------------------------

class TestCliRequiresExplicitRules:
    def test_missing_rules_flag_exits_nonzero(self) -> None:
        """main() without --rules must fail (argparse SystemExit with non-zero code)."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_does_not_auto_load_cyber_immunizer_rules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The script must not silently load .cyber_immunizer/structured_rules.json."""
        monkeypatch.chdir(tmp_path)
        # Create a .cyber_immunizer dir with a rules file to prove it is NOT read.
        cyber_dir = tmp_path / ".cyber_immunizer"
        cyber_dir.mkdir()
        (cyber_dir / "structured_rules.json").write_text(
            json.dumps(equivalent_rules_doc()), encoding="utf-8"
        )
        # Running without --rules should fail with SystemExit, not silently evaluate.
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# 2. Equivalent rules evaluate successfully
# ---------------------------------------------------------------------------

class TestEquivalentRulesEvaluate:
    def test_json_output_schema_valid(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Equivalent rules doc produces schema_valid=True in JSON output."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["schema_valid"] is True

    def test_evaluation_completes_with_cases(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Equivalent rules doc evaluates against real local test cases (total_cases > 0)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["total_cases"] > 0

    def test_mode_is_structured_rules(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Report mode field must be 'structured_rules'."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["mode"] == "structured_rules"

    def test_rules_path_in_report(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Report must include the rules_path field."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert "rules_path" in report

    def test_equivalent_rules_pass_adoption_gate(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Equivalent rules doc (tp_rate=1.0, fp_rate=0.0) should pass the adoption gate."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["passed_adoption_gate"] is True
        assert exit_code == 0

    def test_code_chars_is_nonzero(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """code_chars must equal the JSON doc character count (never 0)."""
        rules_doc = equivalent_rules_doc()
        rules_path = write_rules(tmp_path, rules_doc)
        main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert "code_chars" in report, "report must include code_chars"
        expected_chars = len(json.dumps(rules_doc))
        assert report["code_chars"] == expected_chars
        assert report["code_chars"] > 0

    def test_equivalent_rules_do_not_pass_gate_without_baseline_when_best_score_high(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Equivalent rules must not pass the adoption gate when previous_best_score > possible score.

        With code_chars=len(raw_text) the score is:
            1000 * tp_rate - 0.02 * code_chars  (perfect tp/fp/fn/exception)
        For any non-trivial JSON doc, 0.02 * code_chars > 0.
        A genome with best_score=999.0 ensures even a perfect run cannot pass without --baseline.
        This proves code_chars=0 is NOT used (which would yield score=1000.0 and pass the gate).
        """
        genome = {
            "best_score": 999.0,
            "max_fp_rate": 0.05,
            "min_regression_pass_rate": 1.0,
            "max_avg_latency_ms": 100.0,
            "min_holdout_pass_rate": 0.0,
            "min_counterfactual_pass_rate": 0.0,
            "min_drift_pass_rate": 0.0,
        }
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)

        assert report["code_chars"] > 0, "code_chars must be > 0"
        # score = 1000 - 0.02 * code_chars < 1000 < 999 is impossible —
        # but 1000 - 0.02 * code_chars < 999.0 when code_chars > 50.
        # Any realistic JSON doc is >> 50 chars, so the gate must fail.
        assert report["passed_adoption_gate"] is False
        assert exit_code == 1
        # Confirm the score is below the high previous_best.
        assert report["score"] < 999.0


# ---------------------------------------------------------------------------
# 3. Runtime selector is actually used
# ---------------------------------------------------------------------------

class TestRuntimeSelectorUsed:
    def test_selector_called_with_structured_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """inspect_request_with_runtime_selector must be called with mode='structured_rules'."""
        calls: list[dict] = []

        def recording_selector(request: Request, *, mode: str, structured_rules_doc=None) -> DetectionResult:
            calls.append({"mode": mode, "structured_rules_doc": structured_rules_doc})
            return DetectionResult(blocked=False, reason="test", confidence=0.0, matched_signals=())

        monkeypatch.setattr(mod, "inspect_request_with_runtime_selector", recording_selector)

        rules_doc = equivalent_rules_doc()
        rules_path = write_rules(tmp_path, rules_doc)
        main(["--rules", str(rules_path), "--json", "--soft-reject"])

        assert len(calls) > 0, "inspect_request_with_runtime_selector was never called"
        for call in calls:
            assert call["mode"] == "structured_rules", (
                f"Expected mode='structured_rules', got {call['mode']!r}"
            )

    def test_selector_called_with_explicit_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The structured_rules_doc passed to the selector must match the loaded doc."""
        received_docs: list[dict] = []

        def recording_selector(request: Request, *, mode: str, structured_rules_doc=None) -> DetectionResult:
            if structured_rules_doc is not None:
                received_docs.append(structured_rules_doc)
            return DetectionResult(blocked=False, reason="test", confidence=0.0, matched_signals=())

        monkeypatch.setattr(mod, "inspect_request_with_runtime_selector", recording_selector)

        rules_doc = equivalent_rules_doc()
        rules_path = write_rules(tmp_path, rules_doc)
        main(["--rules", str(rules_path), "--json", "--soft-reject"])

        assert received_docs, "No structured_rules_doc was passed to the selector"
        # All calls should receive the same doc (loaded from file).
        for doc in received_docs:
            assert doc == rules_doc, "structured_rules_doc does not match the loaded rules"


# ---------------------------------------------------------------------------
# 4. Malformed JSON is a tool failure
# ---------------------------------------------------------------------------

class TestMalformedJsonToolFailure:
    def test_malformed_json_exits_1(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Malformed JSON file must exit 1 (tool failure)."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text("{not valid json", encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1

    def test_malformed_json_reports_success_false(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Malformed JSON report must have success=False."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text("{bad", encoding="utf-8")
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False

    def test_malformed_json_error_identifies_parse_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Error message must mention malformed JSON or parse failure."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text("{not: json}", encoding="utf-8")
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert "malformed" in error_text or "json" in error_text or "parse" in error_text

    def test_malformed_json_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool failures exit 1 even with --soft-reject."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text("{bad json again", encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 5. Invalid schema is candidate rejection, not crash
# ---------------------------------------------------------------------------

class TestInvalidSchemaIsRejection:
    def test_invalid_schema_default_exits_1(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Invalid schema exits 1 by default (gate failed)."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1

    def test_invalid_schema_soft_reject_exits_0(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Invalid schema exits 0 with --soft-reject (evaluation completed, not tool failure)."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 0

    def test_invalid_schema_success_false(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Invalid schema: success=False (matches passed_adoption_gate)."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False

    def test_invalid_schema_evaluation_completed_true(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Invalid schema: evaluation_completed=True (ran to completion, not a tool failure)."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["evaluation_completed"] is True

    def test_invalid_schema_schema_valid_false(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Invalid schema: schema_valid=False."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["schema_valid"] is False

    def test_invalid_schema_passed_adoption_gate_false(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Invalid schema: passed_adoption_gate=False."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["passed_adoption_gate"] is False

    def test_invalid_schema_has_rejection_reasons(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Invalid schema report must include rejection_reasons mentioning schema/validation."""
        bad_doc = {"schema_version": 99, "rules": []}
        rules_path = write_rules(tmp_path, bad_doc)
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        reasons = report.get("rejection_reasons", [])
        assert reasons, "rejection_reasons must not be empty for schema failure"
        reasons_text = " ".join(reasons).lower()
        assert "schema" in reasons_text or "validation" in reasons_text


# ---------------------------------------------------------------------------
# 6. No default report write
# ---------------------------------------------------------------------------

class TestNoDefaultReportWrite:
    def test_no_cyber_immunizer_files_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Running without --report-path must not write any .cyber_immunizer/** file."""
        monkeypatch.chdir(tmp_path)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--soft-reject"])
        cyber_dir = tmp_path / ".cyber_immunizer"
        if cyber_dir.exists():
            written = list(cyber_dir.glob("**/*"))
            assert not written, f"Unexpected .cyber_immunizer files: {written}"

    def test_no_report_json_created_without_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Without --report-path, no structured_rules_fitness_report.json should appear."""
        monkeypatch.chdir(tmp_path)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--soft-reject"])
        # No report file anywhere in tmp_path except the rules file itself.
        all_json = [p for p in tmp_path.rglob("*.json") if p != rules_path]
        assert not all_json, f"Unexpected JSON files written: {all_json}"


# ---------------------------------------------------------------------------
# 7. Explicit --report-path writes report
# ---------------------------------------------------------------------------

class TestExplicitReportPath:
    def test_report_written_to_explicit_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path causes the report to be written to that exact path."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        report_path = tmp_path / "my_report.json"
        main(["--rules", str(rules_path), "--json", "--soft-reject", "--report-path", str(report_path)])
        assert report_path.exists(), f"Expected report at {report_path}"

    def test_report_file_contains_required_fields(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Written report must contain the key fields from the spec."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        report_path = tmp_path / "report.json"
        main(["--rules", str(rules_path), "--json", "--soft-reject", "--report-path", str(report_path)])
        written = json.loads(report_path.read_text(encoding="utf-8"))
        required_fields = [
            "success", "evaluation_completed", "schema_valid", "passed_adoption_gate",
            "true_positive", "false_positive", "true_negative", "false_negative",
            "exception_count", "total_cases", "tp_rate", "fp_rate", "fn_rate",
            "avg_latency_ms", "score", "code_chars", "rejection_reasons",
            "adaptive_floor_passed", "holdout_pass_rate", "counterfactual_pass_rate",
            "drift_pass_rate", "score_comparison_mode", "mode", "rules_path",
        ]
        for field in required_fields:
            assert field in written, f"Required field {field!r} missing from written report"

    def test_report_file_matches_json_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Written report content must match the JSON printed to stdout."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        report_path = tmp_path / "report.json"
        main(["--rules", str(rules_path), "--json", "--soft-reject", "--report-path", str(report_path)])
        captured = capsys.readouterr()
        stdout_report = json.loads(captured.out)
        file_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert stdout_report == file_report


# ---------------------------------------------------------------------------
# 8. No forbidden side effects
# ---------------------------------------------------------------------------

class TestNoForbiddenSideEffects:
    def test_no_network_socket_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Script must not create any network socket during evaluation."""
        socket_calls: list = []

        class _ForbiddenSocket:
            def __init__(self, *args, **kwargs) -> None:
                socket_calls.append(args)
                raise AssertionError("network socket must not be created")

        monkeypatch.setattr(socket, "socket", _ForbiddenSocket)

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert not socket_calls, f"Socket was created unexpectedly: {socket_calls}"

    def test_no_subprocess_run_called(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Script must not launch subprocesses during evaluation."""
        subprocess_calls: list = []

        def _forbidden_run(*args, **kwargs):
            subprocess_calls.append(args)
            raise AssertionError("subprocess.run must not be called")

        monkeypatch.setattr(subprocess, "run", _forbidden_run)

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert not subprocess_calls, f"subprocess.run was called unexpectedly: {subprocess_calls}"

    def test_no_extra_implicit_file_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Script must not read from .cyber_immunizer/** implicitly."""
        monkeypatch.chdir(tmp_path)
        # Place a sentinel file in .cyber_immunizer to detect if it is read.
        cyber_dir = tmp_path / ".cyber_immunizer"
        cyber_dir.mkdir()
        sentinel = cyber_dir / "structured_rules.json"
        sentinel.write_text(json.dumps({"sentinel": True}), encoding="utf-8")

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        # Use a separate genome to avoid needing the project's data/ directory.
        main(["--rules", str(rules_path), "--json", "--soft-reject"])

        # The sentinel file must remain untouched (we can't detect reads, but
        # verifying no writes ensures .cyber_immunizer is not used as an output).
        assert sentinel.read_text(encoding="utf-8") == json.dumps({"sentinel": True})


# ---------------------------------------------------------------------------
# 9. No default detector integration
# ---------------------------------------------------------------------------

class TestNoDefaultDetectorIntegration:
    def test_detector_py_has_no_runtime_selector_references(self) -> None:
        """core/detector.py must not reference runtime_selector or structured paths."""
        source = Path("core/detector.py").read_text(encoding="utf-8")
        forbidden_terms = (
            "runtime_selector",
            "structured_detector",
            "structured_evaluator",
            "inspect_request_with_structured_rules",
            "evaluate_structured_rules",
        )
        for term in forbidden_terms:
            assert term not in source, (
                f"core/detector.py must not reference {term!r} — "
                "structured rules must not be wired into the default detector"
            )


# ---------------------------------------------------------------------------
# 10. Genome load failure is a tool failure (fail-closed)
# ---------------------------------------------------------------------------

class TestGenomeLoadFailure:
    def test_malformed_genome_is_tool_failure(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Malformed genome.json must be treated as a tool failure (exit 1, success=False)."""
        bad_genome = tmp_path / "genome.json"
        bad_genome.write_text("{not valid json", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(bad_genome)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["passed_adoption_gate"] is False

    def test_malformed_genome_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome load failure is a tool failure; --soft-reject does not suppress it."""
        bad_genome = tmp_path / "genome.json"
        bad_genome.write_text("{bad genome}", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(bad_genome)])
        assert exit_code == 1

    def test_missing_explicit_genome_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-existent genome path must be treated as a tool failure (exit 1)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        missing_genome = tmp_path / "does_not_exist.json"
        exit_code = main(["--rules", str(rules_path), "--json",
                          "--genome", str(missing_genome)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False

    def test_missing_genome_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Missing genome with --soft-reject still exits 1 (tool failure)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        missing_genome = tmp_path / "no_genome.json"
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(missing_genome)])
        assert exit_code == 1

    def test_genome_failure_error_message_mentions_genome(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome load failure error message must identify the genome as the source."""
        bad_genome = tmp_path / "genome.json"
        bad_genome.write_text("{bad}", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--genome", str(bad_genome)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert "genome" in error_text

    def test_load_test_cases_failure_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """load_test_cases raising an exception must be treated as a tool failure."""
        def failing_load_test_cases(**kwargs):
            raise ValueError("simulated corpus load failure")

        monkeypatch.setattr(mod, "load_test_cases", failing_load_test_cases)

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_load_test_cases_failure_soft_reject_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """load_test_cases failure with --soft-reject still exits 1 (tool failure)."""
        def failing_load_test_cases(**kwargs):
            raise ValueError("simulated corpus failure")

        monkeypatch.setattr(mod, "load_test_cases", failing_load_test_cases)

        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 12. File size limit (Fix 1)
# ---------------------------------------------------------------------------

class TestFileSizeLimit:
    def test_oversized_rules_file_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Rules file exceeding _MAX_RULES_FILE_BYTES must be a tool failure."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_bytes(b"x" * (mod._MAX_RULES_FILE_BYTES + 1))
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_oversized_rules_file_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Oversized file is a tool failure; --soft-reject does not suppress it."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_bytes(b"y" * (mod._MAX_RULES_FILE_BYTES + 1))
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1

    def test_oversized_rules_file_not_parsed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Oversized rules file must not reach json.loads (error must cite size, not parse failure)."""
        rules_path = tmp_path / "rules.json"
        # Non-JSON content that is oversized. If json.loads were called, the error
        # would mention malformed/parse. The size check fires first.
        rules_path.write_bytes(b"A" * (mod._MAX_RULES_FILE_BYTES + 100))
        main(["--rules", str(rules_path), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert any(kw in error_text for kw in ("size", "bytes", "limit", "oversized")), (
            f"Expected size-related error, got: {error_text!r}"
        )


# ---------------------------------------------------------------------------
# 13. Forbidden --report-path (Fix 2)
# ---------------------------------------------------------------------------

class TestForbiddenReportPath:
    def test_report_path_data_dir_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting data/** must exit 1."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / "data" / "report.json")
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1

    def test_report_path_core_dir_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting core/** must exit 1."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / "core" / "x.json")
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1

    def test_report_path_github_dir_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .github/** must exit 1."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".github" / "x.json")
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1

    def test_report_path_tmp_path_works(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path outside frozen paths must succeed (report is written)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        report_path = tmp_path / "report.json"
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", str(report_path)])
        assert exit_code == 0
        assert report_path.exists()


# ---------------------------------------------------------------------------
# 14. Parity guard (Fix 3)
# ---------------------------------------------------------------------------

class TestParityGuard:
    def test_equivalent_rules_fail_adoption_gate_without_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Without --baseline, behavior-equivalent rules must fail the adoption gate.

        Uses a permissive genome so all other gates pass — only the parity guard rejects.
        """
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(permissive_genome()), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["passed_adoption_gate"] is False
        assert exit_code == 1

    def test_equivalent_rules_pass_with_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """With --baseline, parity guard is skipped and equivalent rules can pass."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["passed_adoption_gate"] is True
        assert exit_code == 0

    def test_parity_rejection_reason_mentions_no_behavior_improvement(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Parity guard rejection reason must mention no_behavior_improvement or equivalent."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(permissive_genome()), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        reasons_text = " ".join(report.get("rejection_reasons", []))
        assert "no_behavior_improvement" in reasons_text or "no improvement" in reasons_text.lower()

    def test_score_comparison_mode_field_in_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Completed evaluation must include score_comparison_mode='structured_rules_parity_guard'."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--baseline"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report.get("score_comparison_mode") == "structured_rules_parity_guard"


# ---------------------------------------------------------------------------
# 15. Genome threshold validation (Fix 4)
# ---------------------------------------------------------------------------

class TestGenomeThresholdValidation:
    def test_genome_nan_best_score_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome with NaN best_score must be treated as a tool failure."""
        monkeypatch.setattr(mod, "_load_genome", lambda path: {
            "best_score": float("nan"),
            "max_fp_rate": 0.05,
            "min_regression_pass_rate": 1.0,
            "max_avg_latency_ms": 100.0,
            "min_holdout_pass_rate": 0.0,
            "min_counterfactual_pass_rate": 0.0,
            "min_drift_pass_rate": 0.0,
        })
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_string_threshold_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome with a string-typed threshold must be treated as a tool failure."""
        genome = {
            "best_score": "not_a_number",
            "max_fp_rate": 0.05,
            "min_regression_pass_rate": 1.0,
            "max_avg_latency_ms": 100.0,
        }
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_out_of_range_rate_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome with a rate threshold outside [0.0, 1.0] must be a tool failure."""
        genome = {
            "best_score": 948.0,
            "max_fp_rate": 1.5,  # > 1.0 — invalid rate
            "min_regression_pass_rate": 1.0,
            "max_avg_latency_ms": 100.0,
        }
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_threshold_error_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Invalid genome threshold is a tool failure; --soft-reject does not suppress it."""
        genome = {"best_score": 948.0, "max_fp_rate": -0.1, "min_regression_pass_rate": 1.0,
                  "max_avg_latency_ms": 100.0}
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 16. Duplicate keys in rules JSON (Fix 5)
# ---------------------------------------------------------------------------

class TestDuplicateKeyRejection:
    def test_duplicate_top_level_key_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Rules JSON with duplicate top-level key must be a tool failure."""
        raw = '{"schema_version": 1, "schema_version": 2, "rules": []}'
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(raw, encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_duplicate_nested_key_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Rules JSON with duplicate key in a nested object must be a tool failure."""
        raw = '{"schema_version": 1, "rules": [{"id": "x", "id": "y"}]}'
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(raw, encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_duplicate_key_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Duplicate key is a tool failure; --soft-reject does not suppress it."""
        raw = '{"schema_version": 1, "schema_version": 99}'
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(raw, encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 17. .cyber_immunizer/** report-path rejection (third-pass Fix 1)
# ---------------------------------------------------------------------------

class TestCyberImmunzerReportPathRejected:
    def test_report_path_cyber_immunizer_fitness_report_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .cyber_immunizer/fitness_report.json must exit 1."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".cyber_immunizer" / "fitness_report.json")
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1

    def test_report_path_cyber_immunizer_structured_rules_report_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .cyber_immunizer/structured_rules_fitness_report.json must exit 1."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(
            mod._PROJECT_ROOT / ".cyber_immunizer" / "structured_rules_fitness_report.json"
        )
        exit_code = main(["--rules", str(rules_path), "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 18. Non-UTF-8 rules file is a tool failure (third-pass Fix 2)
# ---------------------------------------------------------------------------

class TestNonUtf8RulesFile:
    def test_binary_rules_file_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Binary (non-UTF-8) rules file must be a tool failure (success=False, exit 1)."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_bytes(b"\xff\xfe binary content \x00\x01")
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_invalid_utf8_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-UTF-8 rules file is a tool failure; --soft-reject does not suppress it."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_bytes(b"\x80\x81\x82 invalid utf-8")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 19. Deeply nested JSON (RecursionError) is a tool failure (third-pass Fix 3)
# ---------------------------------------------------------------------------

class TestDeeplyNestedJson:
    def test_deeply_nested_json_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Deeply nested JSON that causes RecursionError must return a structured tool failure."""
        # Build JSON with nesting depth that exceeds Python's recursion limit.
        depth = 10_000
        raw = "[" * depth + "]" * depth
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(raw, encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        # Must produce parseable JSON output (not a traceback).
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_deeply_nested_json_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Deeply nested JSON tool failure is not suppressed by --soft-reject."""
        depth = 10_000
        raw = "[" * depth + "]" * depth
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(raw, encoding="utf-8")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 20. Genome JSON must be an object, not an array or scalar (third-pass Fix 4)
# ---------------------------------------------------------------------------

class TestGenomeJsonMustBeObject:
    def test_genome_array_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json containing a JSON array must be a tool failure (not a crash)."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text("[]", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_array_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json array is a tool failure; --soft-reject does not suppress it."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text("[1, 2, 3]", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 21. Duplicate keys in genome JSON are rejected (third-pass Fix 5)
# ---------------------------------------------------------------------------

class TestGenomeDuplicateKeyRejection:
    def test_genome_duplicate_best_score_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json with duplicate best_score key must be a tool failure."""
        raw = '{"best_score": 948.0, "best_score": 999.0, "max_fp_rate": 0.05}'
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_duplicate_max_fp_rate_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json with duplicate max_fp_rate key must be a tool failure."""
        raw = '{"best_score": 948.0, "max_fp_rate": 0.05, "max_fp_rate": 1.0}'
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False


# ---------------------------------------------------------------------------
# 22. Non-regular --rules path is a tool failure (fourth-pass Fix 1)
# ---------------------------------------------------------------------------

class TestNonRegularRulesPath:
    def test_directory_rules_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A directory passed as --rules must be a tool failure (exit 1, evaluation_completed=False)."""
        rules_dir = tmp_path / "rules_dir"
        rules_dir.mkdir()
        exit_code = main(["--rules", str(rules_dir), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_directory_rules_path_error_mentions_not_regular(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool failure for a directory rules path must describe the file-type problem."""
        rules_dir = tmp_path / "not_a_file"
        rules_dir.mkdir()
        main(["--rules", str(rules_dir), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert any(kw in error_text for kw in ("not a regular", "regular file", "stat")), (
            f"Expected file-type error, got: {error_text!r}"
        )

    def test_directory_rules_path_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-regular file is a tool failure; --soft-reject does not suppress it."""
        rules_dir = tmp_path / "dir_as_rules"
        rules_dir.mkdir()
        exit_code = main(["--rules", str(rules_dir), "--json", "--soft-reject"])
        assert exit_code == 1

    def test_fifo_rules_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A FIFO passed as --rules must be a tool failure (no blocking on read)."""
        fifo_path = tmp_path / "rules.fifo"
        os.mkfifo(str(fifo_path))
        exit_code = main(["--rules", str(fifo_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False


# ---------------------------------------------------------------------------
# 23. Deeply nested genome JSON raises RecursionError → tool failure (fourth-pass Fix 2)
# ---------------------------------------------------------------------------

class TestDeeplyNestedGenome:
    def test_deeply_nested_genome_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json with deep nesting that raises RecursionError must be a tool failure."""
        depth = 10_000
        nested = "[" * depth + "]" * depth
        raw = '{"best_score": ' + nested + "}"
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)  # Must be parseable JSON, not a traceback
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_deeply_nested_genome_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Deeply nested genome is a tool failure; --soft-reject does not suppress it."""
        depth = 10_000
        nested = "[" * depth + "]" * depth
        raw = '{"best_score": ' + nested + "}"
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 24. All-tiers parity guard: adaptive-tier improvement is not rejected (fourth-pass Fix 3)
# ---------------------------------------------------------------------------

class TestParityGuardAllTiers:
    def test_adaptive_tier_only_difference_not_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Parity guard must NOT reject when structured rules differ from legacy on adaptive tiers.

        The monkeypatched legacy detector returns blocked=False for any request
        whose path contains 'holdout' or 'drift' (simulating a legacy detector blind
        to adaptive-tier threats). Structured rules still catch them. Since all-case
        outcomes differ, parity guard allows the candidate through.
        """
        from core.types import DetectionResult

        original_legacy = mod._legacy_inspect_request

        def adaptive_blind_legacy(request):
            path = request.path or ""
            if "holdout" in path or "drift" in path:
                return DetectionResult(
                    blocked=False, reason="legacy blind", confidence=0.0, matched_signals=()
                )
            return original_legacy(request)

        monkeypatch.setattr(mod, "_legacy_inspect_request", adaptive_blind_legacy)

        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(permissive_genome()), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)

        reasons_text = " ".join(report.get("rejection_reasons", []))
        assert "no_behavior_improvement" not in reasons_text, (
            "Parity guard must not reject when structured rules improve on adaptive tiers"
        )
        assert exit_code == 0

    def test_fully_equivalent_all_tiers_still_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Parity guard still rejects when structured rules are identical to legacy on all tiers."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(permissive_genome()), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["passed_adoption_gate"] is False
        reasons_text = " ".join(report.get("rejection_reasons", []))
        assert "no_behavior_improvement" in reasons_text
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 25. Report write OSError is a structured tool failure (fourth-pass Fix 4)
# ---------------------------------------------------------------------------

class TestReportWriteFailure:
    def test_mkdir_oserror_is_structured_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """If report-path parent mkdir fails (parent is a file), emit structured failure JSON."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        # Create a regular file at the location that mkdir would try to use as a directory.
        parent_blocker = tmp_path / "not_a_dir"
        parent_blocker.write_text("blocker", encoding="utf-8")
        bad_report = str(parent_blocker / "report.json")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", bad_report])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)  # Must be parseable JSON (not a traceback)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_write_failure_error_mentions_write(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Report write failure error must identify the write as the source of the problem."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        parent_blocker = tmp_path / "not_a_dir2"
        parent_blocker.write_text("blocker", encoding="utf-8")
        bad_report = str(parent_blocker / "report.json")
        main(["--rules", str(rules_path), "--json", "--soft-reject",
               "--report-path", bad_report])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert any(kw in error_text for kw in ("write", "report", "failed")), (
            f"Expected write-related error, got: {error_text!r}"
        )

    def test_report_write_failure_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Report write failure is a tool failure; --soft-reject does not suppress it."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        parent_blocker = tmp_path / "not_a_dir3"
        parent_blocker.write_text("blocker", encoding="utf-8")
        bad_report = str(parent_blocker / "report.json")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", bad_report])
        assert exit_code == 1

    def test_successful_report_write_file_before_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """When report-path write succeeds, file and stdout JSON are identical (write-first ordering)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        report_path = tmp_path / "subdir" / "report.json"
        main(["--rules", str(rules_path), "--json", "--baseline",
               "--report-path", str(report_path)])
        captured = capsys.readouterr()
        assert report_path.exists()
        stdout_report = json.loads(captured.out)
        file_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert stdout_report == file_report


# ---------------------------------------------------------------------------
# 26. Genome regular-file guard + size limit (fifth-pass Fix 1)
# ---------------------------------------------------------------------------

class TestGenomeFileGuard:
    def test_fifo_genome_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A FIFO passed as --genome must be a tool failure (no blocking on read)."""
        fifo_path = tmp_path / "genome.fifo"
        os.mkfifo(str(fifo_path))
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(fifo_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_directory_genome_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A directory passed as --genome must be a tool failure."""
        genome_dir = tmp_path / "genome_dir"
        genome_dir.mkdir()
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_dir)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_non_regular_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-regular genome is a tool failure; --soft-reject does not suppress it."""
        genome_dir = tmp_path / "genome_as_dir"
        genome_dir.mkdir()
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_dir)])
        assert exit_code == 1

    def test_oversized_genome_file_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """genome.json exceeding _MAX_GENOME_FILE_BYTES must be a tool failure."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_bytes(b"x" * (mod._MAX_GENOME_FILE_BYTES + 1))
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_oversized_genome_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Oversized genome is a tool failure; --soft-reject does not suppress it."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_bytes(b"y" * (mod._MAX_GENOME_FILE_BYTES + 1))
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        assert exit_code == 1

    def test_non_utf8_genome_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A non-UTF-8 binary genome file must be a structured tool failure (UnicodeDecodeError)."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_bytes(b"\xff\xfe binary content")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_non_utf8_genome_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Non-UTF-8 genome is a tool failure; --soft-reject does not suppress it."""
        genome_path = tmp_path / "genome.json"
        genome_path.write_bytes(b"\xff\xfe binary content")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--genome", str(genome_path)])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 27. Schema validation exceptions are structured tool failures (fifth-pass Fix 2)
# ---------------------------------------------------------------------------

class TestSchemaValidationExceptions:
    def test_schema_validation_overflow_error_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """OverflowError from validate_rules_schema must be a structured tool failure."""
        def raising_validate(doc):
            raise OverflowError("simulated overflow in schema validation")

        monkeypatch.setattr(mod, "validate_rules_schema", raising_validate)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_schema_validation_recursion_error_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """RecursionError from validate_rules_schema must be a structured tool failure."""
        def raising_validate(doc):
            raise RecursionError("simulated recursion in schema validation")

        monkeypatch.setattr(mod, "validate_rules_schema", raising_validate)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_schema_validation_type_error_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """TypeError from validate_rules_schema must be a structured tool failure."""
        def raising_validate(doc):
            raise TypeError("simulated type error in schema validation")

        monkeypatch.setattr(mod, "validate_rules_schema", raising_validate)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_schema_validation_exception_soft_reject_still_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Schema validation exception is a tool failure; --soft-reject does not suppress it."""
        def raising_validate(doc):
            raise OverflowError("simulated")

        monkeypatch.setattr(mod, "validate_rules_schema", raising_validate)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 28. Genome threshold validation overflow-safe (fifth-pass Fix 3)
# ---------------------------------------------------------------------------

class TestGenomeThresholdOverflow:
    def test_genome_huge_integer_best_score_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome best_score as a huge integer (overflows float) must be a tool failure."""
        # Python json.loads returns arbitrary-precision ints; float(10**400) raises OverflowError
        huge = "1" + "0" * 400
        raw = (
            '{"best_score": ' + huge
            + ', "max_fp_rate": 0.05, "min_regression_pass_rate": 1.0,'
            ' "max_avg_latency_ms": 100.0}'
        )
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_huge_integer_max_fp_rate_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Genome max_fp_rate as a huge integer (overflows float) must be a tool failure."""
        huge = "9" * 400
        raw = (
            '{"best_score": 948.0, "max_fp_rate": ' + huge
            + ', "min_regression_pass_rate": 1.0, "max_avg_latency_ms": 100.0}'
        )
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(raw, encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--genome", str(genome_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_to_finite_float_rejects_overflow(self) -> None:
        """_to_finite_float must return an error for integers that overflow float."""
        fval, err = mod._to_finite_float(10 ** 400)
        assert fval is None
        assert err is not None
        assert "overflow" in err.lower() or "too large" in err.lower()

    def test_to_finite_float_accepts_normal_int(self) -> None:
        """_to_finite_float must succeed for normal integer values."""
        fval, err = mod._to_finite_float(42)
        assert err is None
        assert fval == 42.0

    def test_to_finite_float_rejects_bool(self) -> None:
        """_to_finite_float must reject bool values."""
        fval, err = mod._to_finite_float(True)
        assert fval is None
        assert err is not None

    def test_to_finite_float_rejects_nan(self) -> None:
        """_to_finite_float must reject NaN."""
        fval, err = mod._to_finite_float(float("nan"))
        assert fval is None
        assert err is not None


# ---------------------------------------------------------------------------
# 29. Non-regular existing --report-path rejected before write (fifth-pass Fix 4)
# ---------------------------------------------------------------------------

class TestNonRegularExistingReportTarget:
    def test_fifo_report_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An existing FIFO at --report-path must exit 1 before evaluation (no blocking)."""
        fifo_path = tmp_path / "report.fifo"
        os.mkfifo(str(fifo_path))
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", str(fifo_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_fifo_report_path_error_mentions_not_regular(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """FIFO report-path error message must describe the file-type problem."""
        fifo_path = tmp_path / "report2.fifo"
        os.mkfifo(str(fifo_path))
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--json", "--soft-reject",
               "--report-path", str(fifo_path)])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        error_text = (report.get("error", "") + " ".join(report.get("rejection_reasons", []))).lower()
        assert "not a regular file" in error_text or "regular" in error_text

    def test_existing_directory_report_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An existing directory at --report-path (outside forbidden paths) must exit 1."""
        report_dir = tmp_path / "output_dir"
        report_dir.mkdir()
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", str(report_dir)])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False


# ---------------------------------------------------------------------------
# 30. Deterministic monkeypatch-based RecursionError tests (fifth-pass Fix 5)
# ---------------------------------------------------------------------------

class TestMonkeypatchedRecursionErrors:
    def test_rules_json_hook_recursion_error_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """RecursionError raised by object_pairs_hook during rules JSON parsing is a structured tool failure."""
        def raising_hook(pairs):
            raise RecursionError("forced recursion in object_pairs_hook")

        monkeypatch.setattr(mod, "_reject_duplicate_keys", raising_hook)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        # Must be parseable JSON from the test's own json.loads (not monkeypatched)
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_load_recursion_error_is_tool_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """RecursionError from _load_genome must be a structured tool failure."""
        def raising_load_genome(path):
            raise RecursionError("forced recursion in _load_genome")

        monkeypatch.setattr(mod, "_load_genome", raising_load_genome)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_genome_load_recursion_error_soft_reject_still_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """RecursionError from _load_genome is a tool failure; --soft-reject does not suppress it."""
        def raising_load_genome(path):
            raise RecursionError("forced recursion")

        monkeypatch.setattr(mod, "_load_genome", raising_load_genome)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject"])
        assert exit_code == 1


# ---------------------------------------------------------------------------
# 31. Forbidden --report-path .git/** and .grok/** (seventh-pass Fix 1)
# ---------------------------------------------------------------------------

class TestForbiddenReportPathGitGrok:
    def test_report_path_git_config_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .git/config must exit 1 as a tool failure."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".git" / "config")
        exit_code = main(["--rules", str(rules_path), "--json",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_path_git_head_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .git/HEAD must exit 1 as a tool failure."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".git" / "HEAD")
        exit_code = main(["--rules", str(rules_path), "--json",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_path_grok_report_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .grok/report.json must exit 1 as a tool failure."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".grok" / "report.json")
        exit_code = main(["--rules", str(rules_path), "--json",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_path_grok_nested_report_rejects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--report-path targeting .grok/nested/report.json must exit 1 as a tool failure."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".grok" / "nested" / "report.json")
        exit_code = main(["--rules", str(rules_path), "--json",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_path_git_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Forbidden .git/** report-path is a tool failure; --soft-reject does not suppress it."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".git" / "config")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_report_path_grok_soft_reject_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Forbidden .grok/** report-path is a tool failure; --soft-reject does not suppress it."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        forbidden = str(mod._PROJECT_ROOT / ".grok" / "report.json")
        exit_code = main(["--rules", str(rules_path), "--json", "--soft-reject",
                          "--report-path", forbidden])
        assert exit_code == 1
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["success"] is False
        assert report["evaluation_completed"] is False


# ---------------------------------------------------------------------------
# 17. Corpus selection: --corpus-dir and per-tier overrides
#     (Owner-supplied external neutralized corpus through the real gate path)
# ---------------------------------------------------------------------------

def _attack_entry(i: int) -> dict:
    return {
        "id": f"ext-attack-{i}",
        "kind": "attack",
        "expected_blocked": True,
        "tags": ["attack", "path-traversal"],
        "request": {
            "method": "GET",
            "path": f"/ext/a{i}/PATH_TRAVERSAL_INDICATOR",
            "query": {},
            "headers": {},
            "body": "",
        },
    }


def _benign_entry(i: int) -> dict:
    return {
        "id": f"ext-benign-{i}",
        "kind": "benign",
        "expected_blocked": False,
        "tags": ["benign"],
        "request": {"method": "GET", "path": f"/ext/b{i}", "query": {}, "headers": {}, "body": ""},
    }


def _regression_entry(i: int) -> dict:
    return {
        "id": f"ext-reg-{i}",
        "kind": "regression",
        "expected_blocked": False,
        "tags": ["regression"],
        "request": {"method": "GET", "path": f"/ext/r{i}", "query": {}, "headers": {}, "body": ""},
    }


def _blocking_tier_entry(kind: str) -> dict:
    return {
        "id": f"ext-{kind}-0",
        "kind": kind,
        "expected_blocked": True,
        "tags": [kind, "path-traversal"],
        "request": {
            "method": "GET",
            "path": f"/ext/{kind}/PATH_TRAVERSAL_INDICATOR",
            "query": {},
            "headers": {},
            "body": "",
        },
    }


def write_corpus_dir(base: Path, *, n_benign: int, n_attack: int, n_reg: int) -> Path:
    """Write a complete, neutralized external corpus directory and return its path."""
    d = base / "ext_corpus"
    d.mkdir()
    (d / "benign_requests.json").write_text(
        json.dumps([_benign_entry(i) for i in range(n_benign)]), encoding="utf-8"
    )
    (d / "attack_requests.json").write_text(
        json.dumps([_attack_entry(i) for i in range(n_attack)]), encoding="utf-8"
    )
    (d / "regression_cases.json").write_text(
        json.dumps([_regression_entry(i) for i in range(n_reg)]), encoding="utf-8"
    )
    (d / "holdout_requests.json").write_text(
        json.dumps([_blocking_tier_entry("holdout")]), encoding="utf-8"
    )
    (d / "counterfactual_requests.json").write_text(
        json.dumps([{
            "id": "ext-cf-0",
            "kind": "counterfactual",
            "expected_blocked": False,
            "tags": ["counterfactual"],
            "request": {"method": "GET", "path": "/ext/cf-benign", "query": {}, "headers": {}, "body": ""},
        }]),
        encoding="utf-8",
    )
    (d / "drift_requests.json").write_text(
        json.dumps([_blocking_tier_entry("drift")]), encoding="utf-8"
    )
    return d


class TestResolveCorpusPaths:
    def test_returns_none_when_no_dir_and_no_overrides(self) -> None:
        overrides = {tier: None for tier in mod._CORPUS_TIER_FILENAMES}
        assert mod._resolve_corpus_paths(None, overrides) is None

    def test_corpus_dir_populates_all_tiers(self, tmp_path: Path) -> None:
        overrides = {tier: None for tier in mod._CORPUS_TIER_FILENAMES}
        res = mod._resolve_corpus_paths(tmp_path, overrides)
        assert res is not None
        assert set(res) == set(mod._CORPUS_TIER_FILENAMES)
        assert res["attack"] == tmp_path / "attack_requests.json"
        assert res["counterfactual"] == tmp_path / "counterfactual_requests.json"

    def test_override_wins_over_dir(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_attack.json"
        overrides = {tier: None for tier in mod._CORPUS_TIER_FILENAMES}
        overrides["attack"] = custom
        res = mod._resolve_corpus_paths(tmp_path, overrides)
        assert res is not None
        assert res["attack"] == custom
        assert res["benign"] == tmp_path / "benign_requests.json"

    def test_override_only_no_dir(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_attack.json"
        overrides = {tier: None for tier in mod._CORPUS_TIER_FILENAMES}
        overrides["attack"] = custom
        res = mod._resolve_corpus_paths(None, overrides)
        assert res == {"attack": custom}

    def test_load_test_cases_kwargs_filters_none(self) -> None:
        assert mod._load_test_cases_kwargs(None) == {}
        assert mod._load_test_cases_kwargs({}) == {}
        p = Path("/tmp/a.json")
        assert mod._load_test_cases_kwargs({"attack": p, "benign": None}) == {"attack_path": p}


class TestCorpusDirIntegration:
    def test_corpus_dir_used_for_evaluation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """--corpus-dir routes the supplied external corpus through the full gate path."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(
            ["--rules", str(rules_path), "--corpus-dir", str(corpus_dir), "--baseline", "--json"]
        )
        report = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        # main tiers = benign + attack + regression = 3 + 2 + 2
        assert report["total_cases"] == 7
        assert report["passed_adoption_gate"] is True
        assert report["true_positive"] == 2  # 2 attack cases blocked by the equivalent rules
        assert report["false_positive"] == 0

    def test_attack_path_override_changes_total(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A per-tier override replaces only that tier; the rest fall back to data/."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        main(["--rules", str(rules_path), "--baseline", "--json"])
        default_total = json.loads(capsys.readouterr().out)["total_cases"]

        data_attack_count = len(
            json.loads((mod._PROJECT_ROOT / "data" / "attack_requests.json").read_text(encoding="utf-8"))
        )
        one_attack = tmp_path / "one_attack.json"
        one_attack.write_text(json.dumps([_attack_entry(0)]), encoding="utf-8")
        main(["--rules", str(rules_path), "--attack-path", str(one_attack), "--baseline", "--json"])
        override_total = json.loads(capsys.readouterr().out)["total_cases"]

        assert override_total == default_total - data_attack_count + 1

    def test_missing_corpus_dir_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(
            ["--rules", str(rules_path), "--corpus-dir", str(tmp_path / "does_not_exist"),
             "--baseline", "--json"]
        )
        report = json.loads(capsys.readouterr().out)
        assert exit_code == 1
        assert report["success"] is False
        assert report["evaluation_completed"] is False

    def test_empty_main_tier_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An external corpus with an empty attack tier is rejected (no false green)."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        (corpus_dir / "attack_requests.json").write_text("[]", encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        rc = main(["--rules", str(rules_path), "--corpus-dir", str(corpus_dir),
                   "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert report["success"] is False
        assert "incomplete main tier" in str(report.get("rejection_reasons"))

    def test_attack_tier_with_no_positive_label_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An attack file with only expected_blocked=false records has zero positive
        attack cases (tp_rate would be 0); the gate must refuse, not pass green."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        no_pos = [{
            "id": f"np-{i}", "kind": "attack", "expected_blocked": False,
            "tags": ["attack"], "request": {"method": "GET", "path": f"/ok{i}", "query": {}, "headers": {}, "body": ""},
        } for i in range(2)]
        (corpus_dir / "attack_requests.json").write_text(json.dumps(no_pos), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        rc = main(["--rules", str(rules_path), "--corpus-dir", str(corpus_dir),
                   "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert "incomplete main tier" in str(report.get("rejection_reasons"))

    def test_benign_outcome_in_attack_file_does_not_satisfy_benign_tier(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A kind='attack' record with expected_blocked=false must not stand in for
        an empty benign tier (false-green guard counts presence by kind)."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        (corpus_dir / "benign_requests.json").write_text("[]", encoding="utf-8")
        # attack file: valid attacks PLUS a benign-outcome record that still has kind=attack
        attacks = [_attack_entry(0), _attack_entry(1), {
            "id": "sneaky", "kind": "attack", "expected_blocked": False,
            "tags": ["attack"], "request": {"method": "GET", "path": "/ok", "query": {}, "headers": {}, "body": ""},
        }]
        (corpus_dir / "attack_requests.json").write_text(json.dumps(attacks), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        rc = main(["--rules", str(rules_path), "--corpus-dir", str(corpus_dir),
                   "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert "incomplete main tier" in str(report.get("rejection_reasons"))

    def test_non_regular_corpus_path_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A directory passed as a per-tier corpus path is rejected before reading."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        a_dir = tmp_path / "attack_as_dir"
        a_dir.mkdir()
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        rc = main(["--rules", str(rules_path), "--corpus-dir", str(corpus_dir),
                   "--attack-path", str(a_dir), "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert "not a regular file" in str(report.get("rejection_reasons"))

    def test_tier_kind_mismatch_is_tool_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A holdout file whose records carry kind='attack' is rejected (avoids false tier green)."""
        corpus_dir = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        (corpus_dir / "holdout_requests.json").write_text(
            json.dumps([{
                "id": "h-bad", "kind": "attack", "expected_blocked": True,
                "tags": ["attack", "holdout"], "request": _attack_entry(0)["request"],
            }]), encoding="utf-8")
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        rc = main(["--rules", str(rules_path), "--corpus-dir", str(corpus_dir),
                   "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert "kind=" in str(report.get("rejection_reasons"))

    def test_default_still_uses_data_corpus(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """No corpus args => data/ corpus (backward compatible)."""
        rules_path = write_rules(tmp_path, equivalent_rules_doc())
        exit_code = main(["--rules", str(rules_path), "--baseline", "--json"])
        report = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        expected_total = (
            len(json.loads((mod._PROJECT_ROOT / "data" / "benign_requests.json").read_text(encoding="utf-8")))
            + len(json.loads((mod._PROJECT_ROOT / "data" / "attack_requests.json").read_text(encoding="utf-8")))
            + len(json.loads((mod._PROJECT_ROOT / "data" / "regression_cases.json").read_text(encoding="utf-8")))
        )
        assert report["total_cases"] == expected_total


# ---------------------------------------------------------------------------
# Structured-to-structured baseline: when a structured ruleset is the ACTIVE
# detector, score-improvement and parity must be graded against IT, not legacy.
# ---------------------------------------------------------------------------

def _inert_rules_doc() -> dict:
    doc = equivalent_rules_doc()
    doc["rules"] = [{
        "id": "no_match", "field": "surface", "operator": "contains_literal",
        "literal": "zzqq_nomatch_zzz", "signal": "no_match", "confidence": 0.5,
    }]
    return doc


def _structured_active_genome(tmp_path: Path, *, best_score: float, active_score: float, active_path: Path) -> Path:
    g = tmp_path / "genome.json"
    g.write_text(json.dumps({
        "generation": 4, "best_score": best_score, "detector_mode": "structured_rules",
        "active_structured_rules_score": active_score,
        "active_structured_rules_path": str(active_path),
    }), encoding="utf-8")
    return g


class TestStructuredToStructuredBaseline:
    def test_score_improvement_uses_active_structured_score(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A candidate beating the active structured score (1.0) but below a huge
        legacy best_score (1e9) must PASS — the gate uses the active baseline."""
        corpus = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        candidate = write_rules(tmp_path, equivalent_rules_doc())  # detects the corpus
        active_path = tmp_path / "active.json"
        active_path.write_text(json.dumps(_inert_rules_doc()), encoding="utf-8")  # different outcomes
        genome = _structured_active_genome(tmp_path, best_score=1e9, active_score=1.0, active_path=active_path)
        rc = main(["--rules", str(candidate), "--corpus-dir", str(corpus),
                   "--genome", str(genome), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert report["passed_adoption_gate"] is True

    def test_parity_checked_against_active_structured_ruleset(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A candidate identical to the ACTIVE structured ruleset is parity-rejected,
        even though it differs from the legacy detector."""
        corpus = write_corpus_dir(tmp_path, n_benign=3, n_attack=2, n_reg=2)
        rules_doc = equivalent_rules_doc()
        candidate = write_rules(tmp_path, rules_doc)
        active_path = tmp_path / "active.json"
        active_path.write_text(json.dumps(rules_doc), encoding="utf-8")  # identical to candidate
        genome = _structured_active_genome(tmp_path, best_score=1e9, active_score=1.0, active_path=active_path)
        rc = main(["--rules", str(candidate), "--corpus-dir", str(corpus),
                   "--genome", str(genome), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert report["passed_adoption_gate"] is False
        assert "active structured ruleset" in str(report.get("rejection_reasons"))
