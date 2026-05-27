"""tests/test_promote_candidate.py — Verify promotion gate enforcement.

All tests use tmp_path and the promote_candidate path-override arguments so
that real repository files (core/detector.py, data/genome.json, etc.) are
never mutated during the test suite.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts.promote_candidate import _validate_fitness_schema, promote_candidate

_PROJECT_ROOT = Path(__file__).parent.parent
_REAL_DETECTOR = _PROJECT_ROOT / "core" / "detector.py"
_REAL_GENOME = _PROJECT_ROOT / "data" / "genome.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _real_detector_hash() -> str:
    source = _REAL_DETECTOR.read_text(encoding="utf-8")
    return hashlib.sha256(source.encode()).hexdigest()


def _make_isolated_genome(tmp_path: Path, *, best_score: float = -1e9) -> Path:
    """Write an isolated genome.json into tmp_path."""
    real = json.loads(_REAL_GENOME.read_text(encoding="utf-8"))
    real["best_score"] = best_score
    real["generation"] = 0
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(real, indent=2))
    return p


def _make_isolated_history(tmp_path: Path) -> Path:
    p = tmp_path / "evolution_history.json"
    p.write_text("[]")
    return p


def _make_isolated_readme(tmp_path: Path) -> Path:
    p = tmp_path / "README.md"
    p.write_text("# Test README\n<!-- CYBER_IMMUNIZER_STATUS_START -->\n<!-- CYBER_IMMUNIZER_STATUS_END -->\n")
    return p


def _make_isolated_detector_out(tmp_path: Path) -> Path:
    """Return a path where promote will write the promoted detector."""
    return tmp_path / "promoted_detector.py"


def _copy_real_candidate(tmp_path: Path) -> Path:
    """Copy the real detector into tmp_path as a candidate."""
    dest = tmp_path / "candidate_detector.py"
    shutil.copy2(str(_REAL_DETECTOR), str(dest))
    return dest


def _make_passing_report(
    tmp_path: Path,
    candidate_path: Path,
    *,
    score: float = 999.0,
) -> Path:
    """Write a passing fitness report whose hash matches candidate_path."""
    source = candidate_path.read_text(encoding="utf-8")
    h = hashlib.sha256(source.encode()).hexdigest()
    report = {
        "success": True,
        "passed_adoption_gate": True,
        "timed_out": False,
        "return_code": 0,
        "violations": [],
        "error": "",
        "candidate_hash": h,
        "fitness_report": {
            "syntax_ok": True,
            "ast_policy_ok": True,
            "contract_ok": True,
            "timed_out": False,
            "exception_count": 0,
            "true_positive": 5,
            "false_positive": 0,
            "true_negative": 5,
            "false_negative": 0,
            "total_cases": 15,
            "tp_rate": 1.0,
            "fp_rate": 0.0,
            "fn_rate": 0.0,
            "avg_latency_ms": 0.5,
            "code_chars": 500,
            "changed_lines": 5,
            "score": score,
            "passed_adoption_gate": True,
            "rejection_reasons": [],
            "candidate_hash": h,
        },
    }
    p = tmp_path / "fitness_report.json"
    p.write_text(json.dumps(report, indent=2))
    return p


def _make_failing_report(
    tmp_path: Path,
    candidate_path: Path,
    *,
    reason: str = "fp_rate too high",
) -> Path:
    source = candidate_path.read_text(encoding="utf-8")
    h = hashlib.sha256(source.encode()).hexdigest()
    report = {
        "success": False,
        "passed_adoption_gate": False,
        "timed_out": False,
        "return_code": 1,
        "violations": [],
        "error": "adoption gate not passed",
        "candidate_hash": h,
        "fitness_report": {
            "syntax_ok": True,
            "ast_policy_ok": True,
            "contract_ok": True,
            "timed_out": False,
            "exception_count": 0,
            "true_positive": 5,
            "false_positive": 10,
            "true_negative": 0,
            "false_negative": 0,
            "total_cases": 15,
            "tp_rate": 1.0,
            "fp_rate": 1.0,
            "fn_rate": 0.0,
            "avg_latency_ms": 0.5,
            "code_chars": 500,
            "changed_lines": 5,
            "score": -1000.0,
            "passed_adoption_gate": False,
            "rejection_reasons": [reason],
            "candidate_hash": h,
        },
    }
    p = tmp_path / "fitness_report_fail.json"
    p.write_text(json.dumps(report, indent=2))
    return p


def _promote(
    tmp_path: Path,
    candidate_path: Path,
    report_path: Path,
    *,
    best_score: float = -1e9,
) -> tuple[int, Path, Path, Path]:
    """Run promote_candidate with isolated paths; return (exit_code, genome, history, detector_out)."""
    genome_path = _make_isolated_genome(tmp_path, best_score=best_score)
    history_path = _make_isolated_history(tmp_path)
    readme_path = _make_isolated_readme(tmp_path)
    detector_out = _make_isolated_detector_out(tmp_path)

    exit_code = promote_candidate(
        candidate_path,
        report_path,
        as_json=True,
        detector_path=detector_out,
        genome_path=genome_path,
        history_path=history_path,
        readme_path=readme_path,
    )
    return exit_code, genome_path, history_path, detector_out


# ---------------------------------------------------------------------------
# Refusal tests
# ---------------------------------------------------------------------------

class TestPromoteRefusal:
    def test_refuses_missing_report(self, tmp_path):
        candidate = _copy_real_candidate(tmp_path)
        genome = _make_isolated_genome(tmp_path)
        history = _make_isolated_history(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        detector_out = _make_isolated_detector_out(tmp_path)

        exit_code = promote_candidate(
            candidate,
            tmp_path / "nonexistent_report.json",
            as_json=True,
            detector_path=detector_out,
            genome_path=genome,
            history_path=history,
            readme_path=readme,
        )
        assert exit_code != 0, "Should refuse when report is missing"

    def test_refuses_failed_adoption_gate(self, tmp_path):
        candidate = _copy_real_candidate(tmp_path)
        report = _make_failing_report(tmp_path, candidate)

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse when adoption gate failed"

    def test_refuses_without_score_improvement(self, tmp_path):
        """Score must strictly improve on the current best."""
        candidate = _copy_real_candidate(tmp_path)
        # Report claims score=100; genome best is 5000
        report = _make_passing_report(tmp_path, candidate, score=100.0)

        exit_code, _, _, _ = _promote(tmp_path, candidate, report, best_score=5000.0)
        assert exit_code != 0, "Should refuse when score doesn't improve"

    def test_refuses_missing_candidate_file(self, tmp_path):
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate)

        # Delete the candidate after creating the report so hash matches but file is gone
        candidate.unlink()

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse missing candidate file"

    def test_refuses_missing_hash_in_report(self, tmp_path):
        """candidate_hash is mandatory — missing it must refuse."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate)

        # Remove candidate_hash from the report
        data = json.loads(report.read_text())
        del data["candidate_hash"]
        if "candidate_hash" in data.get("fitness_report", {}):
            del data["fitness_report"]["candidate_hash"]
        report.write_text(json.dumps(data))

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse when candidate_hash is missing"

    def test_refuses_hash_mismatch(self, tmp_path):
        """Candidate file tampered after evaluation — hash mismatch must refuse."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate)

        # Tamper with the candidate after the report was written
        candidate.write_text(
            candidate.read_text(encoding="utf-8") + "\n# tampered\n",
            encoding="utf-8",
        )

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse when hash doesn't match"

    def test_refuses_malformed_report(self, tmp_path):
        """Malformed JSON in report must refuse."""
        candidate = _copy_real_candidate(tmp_path)
        bad_report = tmp_path / "bad_report.json"
        bad_report.write_text("{not valid json", encoding="utf-8")

        genome = _make_isolated_genome(tmp_path)
        history = _make_isolated_history(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        detector_out = _make_isolated_detector_out(tmp_path)

        exit_code = promote_candidate(
            candidate,
            bad_report,
            as_json=True,
            detector_path=detector_out,
            genome_path=genome,
            history_path=history,
            readme_path=readme,
        )
        assert exit_code != 0, "Should refuse malformed JSON report"

    def test_refuses_report_with_ast_policy_false(self, tmp_path):
        """Report with ast_policy_ok=False must refuse even if gate says passed."""
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": False,  # <-- unsafe
                "contract_ok": True,
                "passed_adoption_gate": True,  # report claims passed — must still refuse
                "score": 999.0,
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "unsafe_report.json"
        report.write_text(json.dumps(report_data))

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse when ast_policy_ok=False"

    def test_refuses_report_with_fp_rate_above_max(self, tmp_path):
        """fp_rate exceeding genome max_fp_rate must refuse."""
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": 999.0,
                "tp_rate": 1.0,
                "fp_rate": 0.99,   # far above max_fp_rate (0.05)
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "highfp_report.json"
        report.write_text(json.dumps(report_data))

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse fp_rate above max_fp_rate"

    def test_refuses_report_with_missing_fitness_field(self, tmp_path):
        """Missing required fitness field 'score' must refuse."""
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                # "score" is missing
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "missing_field_report.json"
        report.write_text(json.dumps(report_data))

        exit_code, _, _, _ = _promote(tmp_path, candidate, report)
        assert exit_code != 0, "Should refuse when required fitness field is missing"


# ---------------------------------------------------------------------------
# Fail-closed evolution_history tests
# ---------------------------------------------------------------------------

class TestPromoteHistoryFailClosed:
    """Verify that promote_candidate refuses when evolution_history.json is
    missing, malformed, or has an invalid top-level type.

    None of these failures may cause evolution_history.json to be
    overwritten with [] or any other content, nor may they allow
    core/detector.py or data/genome.json to be modified.
    """

    # ------------------------------------------------------------------ #
    # Helpers shared by history tests
    # ------------------------------------------------------------------ #

    def _make_test_environment(self, tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
        """Return (candidate, report, genome, detector_out, readme) paths."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate, score=999.0)
        genome = _make_isolated_genome(tmp_path, best_score=-1e9)
        detector_out = _make_isolated_detector_out(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        return candidate, report, genome, detector_out, readme

    def _run_promote_with_history(
        self,
        tmp_path: Path,
        history_path: Path,
    ) -> tuple[int, Path, Path]:
        """Run promote using the provided history_path; return (exit_code, genome, detector_out)."""
        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        exit_code = promote_candidate(
            candidate,
            report,
            as_json=True,
            detector_path=detector_out,
            genome_path=genome,
            history_path=history_path,
            readme_path=readme,
        )
        return exit_code, genome, detector_out

    # ------------------------------------------------------------------ #
    # 1. Malformed evolution_history.json
    # ------------------------------------------------------------------ #

    def test_refuses_malformed_evolution_history(self, tmp_path):
        """Malformed JSON in evolution_history.json must refuse promote."""
        history = tmp_path / "evolution_history.json"
        history.write_text("{not valid json!!!", encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is malformed JSON"

    def test_malformed_history_error_mentions_fail_closed(self, tmp_path):
        """Refusal for malformed history must mention fail-closed in the error output."""
        import io
        from contextlib import redirect_stdout

        history = tmp_path / "evolution_history.json"
        history.write_text("{not valid json!!!", encoding="utf-8")

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        output = buf.getvalue()
        assert exit_code != 0
        # The JSON error output must be machine-readable and mention the problem
        error_data = json.loads(output)
        assert error_data["success"] is False
        assert "evolution_history" in error_data["error"].lower() or \
               "malformed" in error_data["error"].lower() or \
               "fail-closed" in error_data["error"].lower(), (
                   f"Error message should mention evolution_history/malformed/fail-closed, got: {error_data['error']}"
               )

    # ------------------------------------------------------------------ #
    # 2. Missing evolution_history.json
    # ------------------------------------------------------------------ #

    def test_refuses_missing_evolution_history(self, tmp_path):
        """Missing evolution_history.json must refuse promote."""
        history = tmp_path / "evolution_history.json"
        # Do NOT create the file

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is missing"

    def test_missing_history_error_mentions_missing(self, tmp_path):
        """Refusal for missing history must mention the problem in JSON output."""
        import io
        from contextlib import redirect_stdout

        history = tmp_path / "evolution_history.json"
        # Do NOT create the file

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        output = buf.getvalue()
        assert exit_code != 0
        error_data = json.loads(output)
        assert error_data["success"] is False
        assert "evolution_history" in error_data["error"].lower() or \
               "missing" in error_data["error"].lower() or \
               "not found" in error_data["error"].lower(), (
                   f"Error message should mention missing/not found, got: {error_data['error']}"
               )

    # ------------------------------------------------------------------ #
    # 3 & 4. Top-level non-list values
    # ------------------------------------------------------------------ #

    def test_refuses_dict_evolution_history(self, tmp_path):
        """Top-level JSON object (dict) in evolution_history.json must refuse."""
        history = tmp_path / "evolution_history.json"
        history.write_text('{"generation": 1}', encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is a top-level dict"

    def test_refuses_null_evolution_history(self, tmp_path):
        """Top-level JSON null in evolution_history.json must refuse."""
        history = tmp_path / "evolution_history.json"
        history.write_text("null", encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is top-level null"

    def test_refuses_string_evolution_history(self, tmp_path):
        """Top-level JSON string in evolution_history.json must refuse."""
        history = tmp_path / "evolution_history.json"
        history.write_text('"some string"', encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is top-level string"

    def test_refuses_number_evolution_history(self, tmp_path):
        """Top-level JSON number in evolution_history.json must refuse."""
        history = tmp_path / "evolution_history.json"
        history.write_text("42", encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json is top-level number"

    # ------------------------------------------------------------------ #
    # 5. Failed promote must NOT overwrite history with []
    # ------------------------------------------------------------------ #

    def test_does_not_overwrite_history_on_malformed(self, tmp_path):
        """Malformed evolution_history.json must NOT be overwritten with [] on failure."""
        history = tmp_path / "evolution_history.json"
        original_content = "{not valid json!!!"
        history.write_text(original_content, encoding="utf-8")

        self._run_promote_with_history(tmp_path, history)

        # File must be unchanged
        assert history.read_text(encoding="utf-8") == original_content, (
            "promote must not overwrite evolution_history.json when it is malformed"
        )

    def test_does_not_overwrite_history_on_missing(self, tmp_path):
        """Missing evolution_history.json must NOT be created/initialized on failure."""
        history = tmp_path / "evolution_history.json"
        # Do NOT create the file

        self._run_promote_with_history(tmp_path, history)

        assert not history.exists(), (
            "promote must not create evolution_history.json when it was missing and promote failed"
        )

    def test_does_not_overwrite_history_on_non_list(self, tmp_path):
        """Non-list evolution_history.json must NOT be overwritten on failure."""
        history = tmp_path / "evolution_history.json"
        original_content = '{"key": "value"}'
        history.write_text(original_content, encoding="utf-8")

        self._run_promote_with_history(tmp_path, history)

        assert history.read_text(encoding="utf-8") == original_content, (
            "promote must not overwrite evolution_history.json when it is a non-list"
        )

    # ------------------------------------------------------------------ #
    # 6–8. Failed promote must NOT modify detector/genome/README
    # ------------------------------------------------------------------ #

    def test_does_not_touch_detector_on_history_failure(self, tmp_path):
        """When history is invalid, core/detector.py must not be modified."""
        history = tmp_path / "evolution_history.json"
        history.write_text("null", encoding="utf-8")

        _, _, detector_out = self._run_promote_with_history(tmp_path, history)

        assert not detector_out.exists(), (
            "promote must not write to the detector output path when history is invalid"
        )

    def test_does_not_touch_genome_on_history_failure(self, tmp_path):
        """When history is invalid, genome.json must not be modified."""
        history = tmp_path / "evolution_history.json"
        history.write_text("null", encoding="utf-8")

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        original_genome = genome.read_text(encoding="utf-8")

        promote_candidate(
            candidate, report, as_json=True,
            detector_path=detector_out, genome_path=genome,
            history_path=history, readme_path=readme,
        )

        assert genome.read_text(encoding="utf-8") == original_genome, (
            "promote must not modify genome.json when evolution_history is invalid"
        )

    def test_real_detector_not_modified_on_history_failure(self, tmp_path):
        """The real core/detector.py must not be modified when history is invalid."""
        original_hash = _real_detector_hash()

        history = tmp_path / "evolution_history.json"
        history.write_text("null", encoding="utf-8")

        self._run_promote_with_history(tmp_path, history)

        new_hash = _real_detector_hash()
        assert original_hash == new_hash, (
            "core/detector.py must not be modified during a failed promotion due to invalid history"
        )

    # ------------------------------------------------------------------ #
    # 9. Valid history still works (regression check)
    # ------------------------------------------------------------------ #

    def test_valid_history_allows_normal_promote(self, tmp_path):
        """A valid evolution_history.json still allows a successful promotion."""
        history = _make_isolated_history(tmp_path)  # writes []

        exit_code, _, detector_out = self._run_promote_with_history(tmp_path, history)
        assert exit_code == 0, "Normal promote must succeed with valid history"
        assert detector_out.exists(), "Detector must be written on success"

    def test_valid_non_empty_history_appends_entry(self, tmp_path):
        """Promote appends to an existing non-empty history."""
        history = tmp_path / "evolution_history.json"
        existing_entry = {
            "generation": 0,
            "detector_hash": "abc123",
            "score": 1.0,
            "passed_adoption_gate": True,
            "rejection_reasons": [],
            "promoted_at": "2026-01-01T00:00:00Z",
        }
        history.write_text(json.dumps([existing_entry], indent=2), encoding="utf-8")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code == 0, "Promote must succeed when history has existing valid entries"

        loaded = json.loads(history.read_text(encoding="utf-8"))
        assert len(loaded) == 2, "History must have 2 entries after promotion"
        assert loaded[0] == existing_entry, "Existing entry must be preserved"
        assert loaded[1]["generation"] == 1

    # ------------------------------------------------------------------ #
    # 10. JSON output mode — error is machine-readable
    # ------------------------------------------------------------------ #

    def test_json_output_on_missing_history(self, tmp_path):
        """In JSON mode, missing history error must be machine-readable JSON."""
        import io
        from contextlib import redirect_stdout

        history = tmp_path / "evolution_history.json"
        # Do NOT create the file

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        assert exit_code != 0
        output = buf.getvalue().strip()
        # Must be parseable JSON
        error_data = json.loads(output)
        assert "success" in error_data
        assert error_data["success"] is False
        assert "error" in error_data
        assert isinstance(error_data["error"], str)
        assert len(error_data["error"]) > 0

    def test_json_output_on_malformed_history(self, tmp_path):
        """In JSON mode, malformed history error must be machine-readable JSON."""
        import io
        from contextlib import redirect_stdout

        history = tmp_path / "evolution_history.json"
        history.write_text("{broken", encoding="utf-8")

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        assert exit_code != 0
        output = buf.getvalue().strip()
        error_data = json.loads(output)
        assert error_data["success"] is False
        assert isinstance(error_data["error"], str)
        assert len(error_data["error"]) > 0

    # ------------------------------------------------------------------ #
    # 11. Invalid UTF-8 bytes in evolution_history.json (Codex P2 fix)
    # ------------------------------------------------------------------ #

    def test_refuses_invalid_utf8_evolution_history(self, tmp_path):
        """evolution_history.json containing invalid UTF-8 bytes must refuse promote."""
        history = tmp_path / "evolution_history.json"
        # Write raw bytes that are not valid UTF-8
        history.write_bytes(b"\xff\xfe[invalid utf-8 content]")

        exit_code, _, _ = self._run_promote_with_history(tmp_path, history)
        assert exit_code != 0, "Must refuse when evolution_history.json has invalid UTF-8"

    def test_invalid_utf8_history_json_output_is_machine_readable(self, tmp_path):
        """--json mode must produce machine-readable JSON (not a traceback) for invalid UTF-8."""
        import io
        from contextlib import redirect_stdout

        history = tmp_path / "evolution_history.json"
        history.write_bytes(b"\x80\x81\x82 not valid utf-8")

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        assert exit_code != 0
        output = buf.getvalue().strip()
        # Must be parseable JSON — not a Python traceback
        error_data = json.loads(output)
        assert error_data["success"] is False
        assert "error" in error_data
        assert isinstance(error_data["error"], str)
        assert len(error_data["error"]) > 0
        # Must mention the encoding problem
        msg = error_data["error"].lower()
        assert (
            "utf-8" in msg
            or "utf8" in msg
            or "encoding" in msg
            or "evolution_history" in msg
            or "fail-closed" in msg
        ), f"Error must mention UTF-8/encoding/evolution_history, got: {error_data['error']!r}"

    def test_invalid_utf8_history_not_overwritten(self, tmp_path):
        """Invalid-UTF-8 evolution_history.json must NOT be overwritten on failure."""
        history = tmp_path / "evolution_history.json"
        original_bytes = b"\xff\xfe[invalid utf-8]"
        history.write_bytes(original_bytes)

        self._run_promote_with_history(tmp_path, history)

        assert history.read_bytes() == original_bytes, (
            "promote must not overwrite evolution_history.json with invalid UTF-8"
        )

    def test_invalid_utf8_history_does_not_touch_detector(self, tmp_path):
        """When history has invalid UTF-8, the detector output must not be written."""
        history = tmp_path / "evolution_history.json"
        history.write_bytes(b"\xff\xfe invalid utf-8")

        _, _, detector_out = self._run_promote_with_history(tmp_path, history)

        assert not detector_out.exists(), (
            "promote must not write to the detector path when history has invalid UTF-8"
        )

    def test_invalid_utf8_history_does_not_touch_genome(self, tmp_path):
        """When history has invalid UTF-8, genome.json must not be modified."""
        history = tmp_path / "evolution_history.json"
        history.write_bytes(b"\xff\xfe invalid utf-8")

        candidate, report, genome, detector_out, readme = self._make_test_environment(tmp_path)
        original_genome = genome.read_text(encoding="utf-8")

        promote_candidate(
            candidate, report, as_json=True,
            detector_path=detector_out, genome_path=genome,
            history_path=history, readme_path=readme,
        )

        assert genome.read_text(encoding="utf-8") == original_genome, (
            "promote must not modify genome.json when evolution_history has invalid UTF-8"
        )

    def test_invalid_utf8_history_does_not_touch_real_detector(self, tmp_path):
        """The real core/detector.py must be unchanged when history has invalid UTF-8."""
        original_hash = _real_detector_hash()

        history = tmp_path / "evolution_history.json"
        history.write_bytes(b"\xff\xfe invalid utf-8")

        self._run_promote_with_history(tmp_path, history)

        assert _real_detector_hash() == original_hash, (
            "core/detector.py must not be modified when history has invalid UTF-8"
        )


# ---------------------------------------------------------------------------
# Success tests
# ---------------------------------------------------------------------------

class TestPromoteSuccess:
    def test_updates_genome_on_successful_promotion(self, tmp_path):
        """After promotion, genome generation increments and best_score updates."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate, score=999.0)

        exit_code, genome_path, _, _ = _promote(
            tmp_path, candidate, report, best_score=-1e9
        )
        assert exit_code == 0, "Promotion should succeed with valid inputs"

        genome = json.loads(genome_path.read_text())
        assert genome["generation"] == 1, "Generation should increment to 1"
        assert genome["best_score"] == 999.0, "best_score should be updated"

    def test_updates_history_on_successful_promotion(self, tmp_path):
        """After promotion, evolution_history.json gets a new entry."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate, score=999.0)

        exit_code, _, history_path, _ = _promote(
            tmp_path, candidate, report, best_score=-1e9
        )
        assert exit_code == 0, "Promotion should succeed"

        history = json.loads(history_path.read_text())
        assert len(history) == 1, "History should have exactly one entry"
        entry = history[0]
        assert entry["generation"] == 1
        assert entry["passed_adoption_gate"] is True
        assert "promoted_at" in entry

    def test_writes_detector_to_output_path(self, tmp_path):
        """After promotion, the detector_path contains the candidate content."""
        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate, score=999.0)

        exit_code, _, _, detector_out = _promote(
            tmp_path, candidate, report, best_score=-1e9
        )
        assert exit_code == 0, "Promotion should succeed"
        assert detector_out.exists(), "Detector output file should exist"

        promoted_source = detector_out.read_text(encoding="utf-8")
        candidate_source = candidate.read_text(encoding="utf-8")
        assert promoted_source == candidate_source, (
            "Promoted detector content must match the candidate"
        )

    def test_real_detector_not_mutated(self, tmp_path):
        """The real core/detector.py must be unchanged after a test promotion."""
        original_hash = _real_detector_hash()

        candidate = _copy_real_candidate(tmp_path)
        report = _make_passing_report(tmp_path, candidate, score=999.0)
        _promote(tmp_path, candidate, report, best_score=-1e9)

        new_hash = _real_detector_hash()
        assert original_hash == new_hash, (
            "core/detector.py must not be modified during test promotion"
        )

    def test_second_promotion_requires_score_improvement(self, tmp_path):
        """A second promotion with a lower score must be refused."""
        candidate = _copy_real_candidate(tmp_path)
        report1 = _make_passing_report(tmp_path, candidate, score=500.0)

        exit_code1, genome_path, history_path, detector_out = _promote(
            tmp_path, candidate, report1, best_score=-1e9
        )
        assert exit_code1 == 0, "First promotion should succeed"

        # Second attempt with worse score against the now-updated genome
        report2 = tmp_path / "fitness_report2.json"
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()
        report2_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": 100.0,   # worse than 500.0
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report2.write_text(json.dumps(report2_data))

        exit_code2 = promote_candidate(
            candidate,
            report2,
            as_json=True,
            detector_path=detector_out,
            genome_path=genome_path,
            history_path=history_path,
            readme_path=tmp_path / "README.md",
        )
        assert exit_code2 != 0, "Second promotion with worse score should be refused"


# ---------------------------------------------------------------------------
# PR-E: fitness schema bool hardening (#12)
# ---------------------------------------------------------------------------

def _make_valid_fitness() -> dict:
    """Return a minimal valid fitness dict for direct schema unit tests."""
    return {
        "syntax_ok": True,
        "ast_policy_ok": True,
        "contract_ok": True,
        "passed_adoption_gate": True,
        "score": 1.0,
        "tp_rate": 1.0,
        "fp_rate": 0.0,
        "fn_rate": 0.0,
        "exception_count": 0,
        "rejection_reasons": [],
    }


class TestFitnessSchemaBoolHardening:
    """PR-E: fitness_report schema bool hardening (backlog #12).

    Python's ``bool`` is a subclass of ``int``, so ``isinstance(True, int)``
    returns ``True``.  The previous ``isinstance``-based type check therefore
    allowed ``score: true`` and similar corrupt fitness reports to pass
    schema validation.

    This test class verifies that the hardened ``_validate_fitness_schema``
    rejects:
    - bool values in numeric fields (score, tp_rate, fp_rate, fn_rate, exception_count)
    - NaN and ±Infinity in any numeric field
    - rate field values outside [0.0, 1.0]
    - exception_count < 0 or of type float

    And that it still accepts:
    - valid int/float values for numeric fields
    - rate values in [0.0, 1.0]
    - exception_count 0 or positive int
    - ``bool`` values in genuine boolean fields (passed_adoption_gate, etc.)
    """

    # ------------------------------------------------------------------
    # 1–7  Bool rejection in numeric fields
    # ------------------------------------------------------------------

    def test_schema_rejects_bool_score_true(self):
        """score=True must be rejected (bool is not a valid numeric field value)."""
        fitness = _make_valid_fitness()
        fitness["score"] = True
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for score=True"
        assert any("score" in e for e in errors), f"Error must mention 'score': {errors}"

    def test_schema_rejects_bool_score_false(self):
        """score=False must be rejected."""
        fitness = _make_valid_fitness()
        fitness["score"] = False
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for score=False"
        assert any("score" in e for e in errors), f"Error must mention 'score': {errors}"

    def test_schema_rejects_bool_tp_rate_true(self):
        """tp_rate=True must be rejected."""
        fitness = _make_valid_fitness()
        fitness["tp_rate"] = True
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for tp_rate=True"
        assert any("tp_rate" in e for e in errors), f"Error must mention 'tp_rate': {errors}"

    def test_schema_rejects_bool_fp_rate_false(self):
        """fp_rate=False must be rejected."""
        fitness = _make_valid_fitness()
        fitness["fp_rate"] = False
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fp_rate=False"
        assert any("fp_rate" in e for e in errors), f"Error must mention 'fp_rate': {errors}"

    def test_schema_rejects_bool_fn_rate_true(self):
        """fn_rate=True must be rejected."""
        fitness = _make_valid_fitness()
        fitness["fn_rate"] = True
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fn_rate=True"
        assert any("fn_rate" in e for e in errors), f"Error must mention 'fn_rate': {errors}"

    def test_schema_rejects_bool_exception_count_true(self):
        """exception_count=True must be rejected."""
        fitness = _make_valid_fitness()
        fitness["exception_count"] = True
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for exception_count=True"
        assert any("exception_count" in e for e in errors), (
            f"Error must mention 'exception_count': {errors}"
        )

    def test_schema_rejects_bool_exception_count_false(self):
        """exception_count=False must be rejected."""
        fitness = _make_valid_fitness()
        fitness["exception_count"] = False
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for exception_count=False"
        assert any("exception_count" in e for e in errors), (
            f"Error must mention 'exception_count': {errors}"
        )

    # ------------------------------------------------------------------
    # 8–11  NaN / Infinity rejection
    # ------------------------------------------------------------------

    def test_schema_rejects_nan_score(self):
        """score=NaN must be rejected (not finite)."""
        fitness = _make_valid_fitness()
        fitness["score"] = float("nan")
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for score=NaN"
        assert any("score" in e for e in errors), f"Error must mention 'score': {errors}"

    def test_schema_rejects_infinity_score(self):
        """score=Infinity must be rejected (not finite)."""
        fitness = _make_valid_fitness()
        fitness["score"] = float("inf")
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for score=Infinity"
        assert any("score" in e for e in errors), f"Error must mention 'score': {errors}"

    def test_schema_rejects_nan_tp_rate(self):
        """tp_rate=NaN must be rejected."""
        fitness = _make_valid_fitness()
        fitness["tp_rate"] = float("nan")
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for tp_rate=NaN"
        assert any("tp_rate" in e for e in errors), f"Error must mention 'tp_rate': {errors}"

    def test_schema_rejects_infinity_fp_rate(self):
        """fp_rate=Infinity must be rejected."""
        fitness = _make_valid_fitness()
        fitness["fp_rate"] = float("inf")
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fp_rate=Infinity"
        assert any("fp_rate" in e for e in errors), f"Error must mention 'fp_rate': {errors}"

    # ------------------------------------------------------------------
    # 12–13  Rate fields out of [0.0, 1.0]
    # ------------------------------------------------------------------

    def test_schema_rejects_tp_rate_below_zero(self):
        """tp_rate=-0.1 must be rejected (below 0.0)."""
        fitness = _make_valid_fitness()
        fitness["tp_rate"] = -0.1
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for tp_rate=-0.1"
        assert any("tp_rate" in e for e in errors), f"Error must mention 'tp_rate': {errors}"

    def test_schema_rejects_fp_rate_above_one(self):
        """fp_rate=1.1 must be rejected (above 1.0)."""
        fitness = _make_valid_fitness()
        fitness["fp_rate"] = 1.1
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fp_rate=1.1"
        assert any("fp_rate" in e for e in errors), f"Error must mention 'fp_rate': {errors}"

    # ------------------------------------------------------------------
    # 14–15  exception_count violations
    # ------------------------------------------------------------------

    def test_schema_rejects_negative_exception_count(self):
        """exception_count=-1 must be rejected (must be >= 0)."""
        fitness = _make_valid_fitness()
        fitness["exception_count"] = -1
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for exception_count=-1"
        assert any("exception_count" in e for e in errors), (
            f"Error must mention 'exception_count': {errors}"
        )

    def test_schema_rejects_float_exception_count(self):
        """exception_count=0.0 must be rejected (float, not int)."""
        fitness = _make_valid_fitness()
        fitness["exception_count"] = 0.0
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for exception_count=0.0"
        assert any("exception_count" in e for e in errors), (
            f"Error must mention 'exception_count': {errors}"
        )

    # ------------------------------------------------------------------
    # 16–18  Valid values must pass
    # ------------------------------------------------------------------

    def test_schema_accepts_valid_int_float_score(self):
        """Valid int and float score values must produce no schema errors."""
        for v in (0, 1, -1, 0.0, 1.5, -999.9, 0.001):
            fitness = _make_valid_fitness()
            fitness["score"] = v
            errors = _validate_fitness_schema(fitness)
            assert not errors, f"score={v!r} should be valid, got errors: {errors}"

    def test_schema_accepts_valid_rate_fields(self):
        """Valid tp_rate/fp_rate/fn_rate in [0.0, 1.0] must produce no errors."""
        for v in (0, 1, 0.0, 0.5, 1.0, 0.999):
            for field in ("tp_rate", "fp_rate", "fn_rate"):
                fitness = _make_valid_fitness()
                fitness[field] = v
                errors = _validate_fitness_schema(fitness)
                assert not errors, (
                    f"{field}={v!r} should be valid, got errors: {errors}"
                )

    def test_schema_accepts_valid_exception_count(self):
        """exception_count=0 and =1 (strict int) must produce no schema errors."""
        for v in (0, 1, 5, 100):
            fitness = _make_valid_fitness()
            fitness["exception_count"] = v
            errors = _validate_fitness_schema(fitness)
            assert not errors, (
                f"exception_count={v!r} should be valid, got errors: {errors}"
            )

    # ------------------------------------------------------------------
    # 19  Genuine boolean field must NOT be broken
    # ------------------------------------------------------------------

    def test_schema_accepts_bool_passed_adoption_gate(self):
        """passed_adoption_gate=True is a genuine bool field and must be accepted."""
        fitness = _make_valid_fitness()
        fitness["passed_adoption_gate"] = True
        errors = _validate_fitness_schema(fitness)
        assert not errors, (
            f"passed_adoption_gate=True (genuine bool field) should be valid, "
            f"got errors: {errors}"
        )

    def test_schema_accepts_bool_syntax_ok_and_ast_policy_ok(self):
        """syntax_ok=True and ast_policy_ok=True are genuine bool fields."""
        fitness = _make_valid_fitness()
        fitness["syntax_ok"] = True
        fitness["ast_policy_ok"] = True
        errors = _validate_fitness_schema(fitness)
        assert not errors, (
            f"syntax_ok/ast_policy_ok=True should be valid, got errors: {errors}"
        )

    # ------------------------------------------------------------------
    # 20  End-to-end: invalid schema refuses promote, no side effects
    # ------------------------------------------------------------------

    def test_promote_refuses_bool_score_no_side_effects(self, tmp_path):
        """score=True in fitness report: promote must refuse and leave all files unchanged.

        Specifically verifies:
        - exit code is non-zero
        - JSON error output is machine-readable and contains 'score'
        - core/detector.py is not modified (via real hash check)
        - genome.json is not modified
        - evolution_history.json is not modified
        - README.md is not modified
        """
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        # Build a fitness report with score=True (bool-as-number)
        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": True,          # ← bool in numeric field
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "bool_score_report.json"
        report.write_text(json.dumps(report_data))

        genome = _make_isolated_genome(tmp_path, best_score=-1e9)
        history = _make_isolated_history(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        detector_out = _make_isolated_detector_out(tmp_path)
        original_genome = genome.read_text(encoding="utf-8")
        original_history = history.read_text(encoding="utf-8")
        original_readme = readme.read_text(encoding="utf-8")
        original_real_detector_hash = _real_detector_hash()

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        output = buf.getvalue()

        # Exit code must be non-zero
        assert exit_code != 0, "Must refuse when score=True (bool-as-number)"

        # JSON error output must be machine-readable and mention 'score'
        error_data = json.loads(output)
        assert error_data["success"] is False
        assert "error" in error_data
        assert "score" in error_data["error"], (
            f"Error message must mention field 'score', got: {error_data['error']!r}"
        )

        # No side effects: detector_out must not have been written
        assert not detector_out.exists(), (
            "promote must not write detector when schema is invalid"
        )
        # genome.json must be unchanged
        assert genome.read_text(encoding="utf-8") == original_genome, (
            "promote must not modify genome.json when schema is invalid"
        )
        # evolution_history.json must be unchanged
        assert history.read_text(encoding="utf-8") == original_history, (
            "promote must not modify evolution_history.json when schema is invalid"
        )
        # README must be unchanged
        assert readme.read_text(encoding="utf-8") == original_readme, (
            "promote must not modify README when schema is invalid"
        )
        # Real core/detector.py must be unchanged
        assert _real_detector_hash() == original_real_detector_hash, (
            "core/detector.py must not be modified when schema is invalid"
        )

    def test_json_output_contains_field_name_for_bool_fields(self, tmp_path):
        """JSON mode error output must name the offending field for each bool violation."""
        bool_field_cases = [
            ("score", True),
            ("tp_rate", True),
            ("fp_rate", False),
            ("fn_rate", True),
            ("exception_count", True),
        ]
        for field, bool_val in bool_field_cases:
            candidate = _copy_real_candidate(tmp_path)
            source = candidate.read_text(encoding="utf-8")
            h = hashlib.sha256(source.encode()).hexdigest()

            fitness_data = {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": 999.0,
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            }
            fitness_data[field] = bool_val

            report_data = {"candidate_hash": h, "fitness_report": fitness_data}
            report = tmp_path / f"report_bool_{field}.json"
            report.write_text(json.dumps(report_data))

            genome = _make_isolated_genome(tmp_path, best_score=-1e9)
            history = _make_isolated_history(tmp_path)
            readme = _make_isolated_readme(tmp_path)
            detector_out = _make_isolated_detector_out(tmp_path)

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = promote_candidate(
                    candidate, report, as_json=True,
                    detector_path=detector_out, genome_path=genome,
                    history_path=history, readme_path=readme,
                )
            output = buf.getvalue()

            assert exit_code != 0, f"Must refuse for {field}={bool_val!r}"
            error_data = json.loads(output)
            assert error_data["success"] is False
            assert field in error_data["error"], (
                f"Error must mention field name {field!r} for {field}={bool_val!r}, "
                f"got: {error_data['error']!r}"
            )

    # ------------------------------------------------------------------
    # Codex P2: huge-int OverflowError protection
    # _validate_fitness_schema and promote_candidate must never raise an
    # uncaught exception when numeric fields contain very large integers
    # (e.g. 2**10000) parsed from attacker-supplied JSON.
    # ------------------------------------------------------------------

    _HUGE_INT = 2 ** 10_000  # far exceeds float range (~1.8e308)

    def test_schema_huge_int_score_does_not_raise(self):
        """_validate_fitness_schema must not raise for score=huge_int.

        Python int is always finite; the new _is_finite_number avoids float()
        conversion, so no OverflowError is possible inside schema validation.
        """
        fitness = _make_valid_fitness()
        fitness["score"] = self._HUGE_INT
        # Must not raise — result (error list) may be empty or non-empty
        try:
            errors = _validate_fitness_schema(fitness)
        except Exception as exc:
            raise AssertionError(
                f"_validate_fitness_schema raised unexpectedly for score=huge_int: {exc!r}"
            ) from exc

    def test_schema_huge_int_score_is_valid(self):
        """score=huge_int passes schema validation (int is finite by definition).

        The OverflowError guard is in promote_candidate step-11 (float conversion),
        not in schema validation — so schema sees no error here.
        """
        fitness = _make_valid_fitness()
        fitness["score"] = self._HUGE_INT
        errors = _validate_fitness_schema(fitness)
        assert not errors, (
            f"score=huge_int should pass schema validation (int is finite), "
            f"got errors: {errors}"
        )

    def test_schema_rejects_huge_int_tp_rate(self):
        """tp_rate=huge_int must be rejected as out of range [0.0, 1.0].

        No OverflowError — Python's native int/float comparison is used.
        """
        fitness = _make_valid_fitness()
        fitness["tp_rate"] = self._HUGE_INT
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for tp_rate=huge_int"
        assert any("tp_rate" in e for e in errors), (
            f"Error must mention 'tp_rate': {errors}"
        )

    def test_schema_rejects_huge_int_fp_rate(self):
        """fp_rate=huge_int must be rejected as out of range [0.0, 1.0]."""
        fitness = _make_valid_fitness()
        fitness["fp_rate"] = self._HUGE_INT
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fp_rate=huge_int"
        assert any("fp_rate" in e for e in errors), (
            f"Error must mention 'fp_rate': {errors}"
        )

    def test_schema_rejects_huge_int_fn_rate(self):
        """fn_rate=huge_int must be rejected as out of range [0.0, 1.0]."""
        fitness = _make_valid_fitness()
        fitness["fn_rate"] = self._HUGE_INT
        errors = _validate_fitness_schema(fitness)
        assert errors, "Expected schema error for fn_rate=huge_int"
        assert any("fn_rate" in e for e in errors), (
            f"Error must mention 'fn_rate': {errors}"
        )

    def test_promote_huge_int_score_no_traceback_json_refusal(self, tmp_path):
        """promote_candidate --json with score=huge_int must produce JSON refusal.

        Flow:
        1. Schema validation passes (huge int is finite by definition).
        2. Step-11 float(score) raises OverflowError — caught, refused cleanly.
        3. Output is machine-readable JSON with success=false and mentions 'score'.
        4. No side effects on any files.
        """
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        # Write a fitness report with score = 2**10000 (valid JSON big integer)
        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": self._HUGE_INT,
                "tp_rate": 1.0,
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "huge_int_score_report.json"
        report.write_text(json.dumps(report_data))

        genome = _make_isolated_genome(tmp_path, best_score=-1e9)
        history = _make_isolated_history(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        detector_out = _make_isolated_detector_out(tmp_path)
        original_genome = genome.read_text(encoding="utf-8")
        original_history = history.read_text(encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        output = buf.getvalue()

        # Must not traceback — output must be valid JSON
        result = json.loads(output)

        # Must refuse (score overflows float at step-11)
        assert exit_code != 0, (
            "promote_candidate must refuse for huge int score (float overflow at step-11)"
        )
        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], str) and result["error"], (
            "error field must be a non-empty string"
        )
        assert "score" in result["error"], (
            f"JSON error must mention 'score', got: {result['error']!r}"
        )

        # No side effects
        assert not detector_out.exists(), (
            "detector must not be written when score overflows"
        )
        assert genome.read_text(encoding="utf-8") == original_genome, (
            "genome.json must not be modified when score overflows"
        )
        assert history.read_text(encoding="utf-8") == original_history, (
            "evolution_history.json must not be modified when score overflows"
        )

    def test_promote_huge_int_rate_no_traceback_no_side_effects(self, tmp_path):
        """promote_candidate --json with tp_rate=huge_int: schema error, no traceback, no side effects.

        Schema validation rejects huge int tp_rate (out of range [0.0, 1.0])
        using native Python int/float comparison — no OverflowError.
        """
        candidate = _copy_real_candidate(tmp_path)
        source = candidate.read_text(encoding="utf-8")
        h = hashlib.sha256(source.encode()).hexdigest()

        report_data = {
            "candidate_hash": h,
            "fitness_report": {
                "syntax_ok": True,
                "ast_policy_ok": True,
                "contract_ok": True,
                "passed_adoption_gate": True,
                "score": 999.0,
                "tp_rate": self._HUGE_INT,   # huge int → out of range [0,1]
                "fp_rate": 0.0,
                "fn_rate": 0.0,
                "exception_count": 0,
                "rejection_reasons": [],
            },
        }
        report = tmp_path / "huge_int_rate_report.json"
        report.write_text(json.dumps(report_data))

        genome = _make_isolated_genome(tmp_path, best_score=-1e9)
        history = _make_isolated_history(tmp_path)
        readme = _make_isolated_readme(tmp_path)
        detector_out = _make_isolated_detector_out(tmp_path)
        original_genome = genome.read_text(encoding="utf-8")
        original_history = history.read_text(encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = promote_candidate(
                candidate, report, as_json=True,
                detector_path=detector_out, genome_path=genome,
                history_path=history, readme_path=readme,
            )
        output = buf.getvalue()

        # Output must be valid JSON (no traceback)
        result = json.loads(output)

        # Must refuse at schema validation (tp_rate out of range)
        assert exit_code != 0, "Must refuse when tp_rate=huge_int (out of range)"
        assert result["success"] is False
        assert "tp_rate" in result["error"], (
            f"Error must mention 'tp_rate', got: {result['error']!r}"
        )

        # No side effects
        assert not detector_out.exists(), (
            "detector must not be written when schema is invalid"
        )
        assert genome.read_text(encoding="utf-8") == original_genome, (
            "genome.json must not be modified when schema is invalid"
        )
        assert history.read_text(encoding="utf-8") == original_history, (
            "evolution_history.json must not be modified when schema is invalid"
        )
