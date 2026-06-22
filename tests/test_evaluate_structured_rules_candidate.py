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
"""
from __future__ import annotations

import json
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
            "drift_pass_rate", "mode", "rules_path",
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
