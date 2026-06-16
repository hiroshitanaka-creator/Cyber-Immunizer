"""tests/test_evaluate_promote_contract.py — Regression tests for the
evaluate_candidate → promote_candidate report contract.

Verifies that promote_candidate correctly reads fitness reports produced by
evaluate_candidate, including the fitness_report canonical key and the metrics
alias fallback added in Phase 2.

All tests use tmp_path and the promote_candidate path-override arguments so
that real repository files are never mutated.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.promote_candidate import promote_candidate

_PROJECT_ROOT = Path(__file__).parent.parent
_REAL_DETECTOR = _PROJECT_ROOT / "core" / "detector.py"
_REAL_GENOME = _PROJECT_ROOT / "data" / "genome.json"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FITNESS_DATA_PASSING = {
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
    "score": 9999.0,
    "passed_adoption_gate": True,
    "rejection_reasons": [],
}


def _candidate_hash(candidate_path: Path) -> str:
    source = candidate_path.read_text(encoding="utf-8")
    return hashlib.sha256(source.encode()).hexdigest()


def _make_genome(tmp_path: Path, *, best_score: float = -1e9) -> Path:
    real = json.loads(_REAL_GENOME.read_text(encoding="utf-8"))
    real["best_score"] = best_score
    real["generation"] = 0
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(real, indent=2))
    return p


def _make_history(tmp_path: Path) -> Path:
    p = tmp_path / "evolution_history.json"
    p.write_text("[]")
    return p


def _make_readme(tmp_path: Path) -> Path:
    p = tmp_path / "README.md"
    p.write_text(
        "# Test\n"
        "<!-- CYBER_IMMUNIZER_STATUS_START -->\n"
        "<!-- CYBER_IMMUNIZER_STATUS_END -->\n"
    )
    return p


def _make_detector_out(tmp_path: Path) -> Path:
    return tmp_path / "promoted_detector.py"


def _copy_real_candidate(tmp_path: Path) -> Path:
    dest = tmp_path / "candidate_detector.py"
    shutil.copy2(str(_REAL_DETECTOR), str(dest))
    return dest


def _write_report(tmp_path: Path, payload: dict, *, name: str = "fitness_report.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload, indent=2))
    return p


def _promote(
    tmp_path: Path,
    candidate_path: Path,
    report_path: Path,
    *,
    best_score: float = -1e9,
) -> int:
    return promote_candidate(
        candidate_path,
        report_path,
        as_json=True,
        detector_path=_make_detector_out(tmp_path),
        genome_path=_make_genome(tmp_path, best_score=best_score),
        history_path=_make_history(tmp_path),
        readme_path=_make_readme(tmp_path),
    )


def _passing_report_with_fitness_key(candidate_path: Path) -> dict:
    """Build a passing report using the canonical 'fitness_report' key."""
    h = _candidate_hash(candidate_path)
    fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": h}
    return {
        "stage": "evaluate_candidate",
        "success": True,
        "passed_adoption_gate": True,
        "is_tool_failure": False,
        "timed_out": False,
        "candidate_hash": h,
        "violations": [],
        "error": "",
        "fitness_report": fitness,
        "metrics": fitness,
        "return_code": 0,
    }


def _passing_report_with_metrics_only(candidate_path: Path) -> dict:
    """Build a passing report using only the 'metrics' key (no fitness_report)."""
    h = _candidate_hash(candidate_path)
    fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": h}
    return {
        "stage": "evaluate_candidate",
        "success": True,
        "passed_adoption_gate": True,
        "is_tool_failure": False,
        "timed_out": False,
        "candidate_hash": h,
        "violations": [],
        "error": "",
        "fitness_report": None,
        "metrics": fitness,
        "return_code": 0,
    }


# ---------------------------------------------------------------------------
# Tests: fitness_report canonical key
# ---------------------------------------------------------------------------

class TestFitnessReportKeyContract:
    """promote_candidate correctly reads fitness data from evaluate_candidate reports."""

    def test_fitness_report_key_passes_promote_parsing(self, tmp_path: Path) -> None:
        """Report with fitness_report key is accepted by promote_candidate."""
        candidate = _copy_real_candidate(tmp_path)
        report_data = _passing_report_with_fitness_key(candidate)
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc == 0, "Report with fitness_report key must be accepted by promote_candidate"

    def test_metrics_key_fallback_passes_promote_parsing(self, tmp_path: Path) -> None:
        """Report with only metrics key (fitness_report=None) is accepted via fallback."""
        candidate = _copy_real_candidate(tmp_path)
        report_data = _passing_report_with_metrics_only(candidate)
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc == 0, "Report with metrics key (fitness_report=None) must succeed via fallback"

    def test_fitness_report_takes_precedence_over_metrics(self, tmp_path: Path) -> None:
        """When both keys present, fitness_report is used (not metrics)."""
        candidate = _copy_real_candidate(tmp_path)
        h = _candidate_hash(candidate)
        passing_fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": h}
        # metrics carries a failing schema; fitness_report carries the passing data
        report_data = {
            "stage": "evaluate_candidate",
            "success": True,
            "passed_adoption_gate": True,
            "is_tool_failure": False,
            "timed_out": False,
            "candidate_hash": h,
            "violations": [],
            "error": "",
            "fitness_report": passing_fitness,
            "metrics": {"passed_adoption_gate": False, "score": -1.0},
            "return_code": 0,
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc == 0, "fitness_report key must take precedence over metrics key"

    def test_neither_key_fails_schema(self, tmp_path: Path) -> None:
        """Report with neither fitness_report nor metrics fails schema validation."""
        candidate = _copy_real_candidate(tmp_path)
        h = _candidate_hash(candidate)
        report_data = {
            "stage": "evaluate_candidate",
            "success": True,
            "passed_adoption_gate": True,
            "is_tool_failure": False,
            "timed_out": False,
            "candidate_hash": h,
            "violations": [],
            "error": "",
            "return_code": 0,
            # no fitness_report, no metrics
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "Report without fitness_report or metrics must fail schema validation"


# ---------------------------------------------------------------------------
# Tests: promotion gates unchanged (regression guard)
# ---------------------------------------------------------------------------

class TestPromoteGatesUnchanged:
    """Promotion gates must be intact after Phase 2 changes."""

    def test_passed_adoption_gate_false_refused(self, tmp_path: Path) -> None:
        """promote_candidate refuses when passed_adoption_gate=False in fitness data."""
        candidate = _copy_real_candidate(tmp_path)
        h = _candidate_hash(candidate)
        fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": h, "passed_adoption_gate": False,
                   "score": -999.0, "rejection_reasons": ["score regression"]}
        report_data = {
            "stage": "evaluate_candidate",
            "success": False,
            "passed_adoption_gate": False,
            "is_tool_failure": False,
            "timed_out": False,
            "candidate_hash": h,
            "violations": [],
            "error": "adoption gate not passed",
            "fitness_report": fitness,
            "metrics": fitness,
            "return_code": 0,
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "passed_adoption_gate=false must cause promotion refusal"

    def test_missing_candidate_hash_refused(self, tmp_path: Path) -> None:
        """promote_candidate refuses when candidate_hash is absent."""
        candidate = _copy_real_candidate(tmp_path)
        fitness = {**_FITNESS_DATA_PASSING}
        report_data = {
            "stage": "evaluate_candidate",
            "success": True,
            "passed_adoption_gate": True,
            "is_tool_failure": False,
            "timed_out": False,
            "violations": [],
            "error": "",
            "fitness_report": fitness,
            "metrics": fitness,
            "return_code": 0,
            # no candidate_hash anywhere
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "Missing candidate_hash must cause promotion refusal"

    def test_hash_mismatch_refused(self, tmp_path: Path) -> None:
        """promote_candidate refuses when candidate file hash doesn't match report."""
        candidate = _copy_real_candidate(tmp_path)
        wrong_hash = "a" * 64
        fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": wrong_hash}
        report_data = {
            "stage": "evaluate_candidate",
            "success": True,
            "passed_adoption_gate": True,
            "is_tool_failure": False,
            "timed_out": False,
            "candidate_hash": wrong_hash,
            "violations": [],
            "error": "",
            "fitness_report": fitness,
            "metrics": fitness,
            "return_code": 0,
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "Hash mismatch must cause promotion refusal"

    def test_policy_revalidation_still_runs(self, tmp_path: Path) -> None:
        """promote_candidate re-runs core.policy before promotion and refuses on failure."""
        candidate = _copy_real_candidate(tmp_path)
        report_data = _passing_report_with_fitness_key(candidate)
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": False, "violations": ["simulated policy failure"]}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "Policy re-validation failure must cause promotion refusal"

    def test_metrics_fallback_still_enforces_passed_adoption_gate(self, tmp_path: Path) -> None:
        """metrics fallback does not bypass the adoption gate check."""
        candidate = _copy_real_candidate(tmp_path)
        h = _candidate_hash(candidate)
        fitness = {**_FITNESS_DATA_PASSING, "candidate_hash": h, "passed_adoption_gate": False,
                   "score": -1.0, "rejection_reasons": ["score too low"]}
        report_data = {
            "stage": "evaluate_candidate",
            "success": False,
            "passed_adoption_gate": False,
            "is_tool_failure": False,
            "timed_out": False,
            "candidate_hash": h,
            "violations": [],
            "error": "adoption gate not passed",
            "fitness_report": None,
            "metrics": fitness,
            "return_code": 0,
        }
        report_path = _write_report(tmp_path, report_data)

        with patch("scripts.promote_candidate.run_full_policy",
                   return_value={"valid": True, "violations": []}):
            rc = _promote(tmp_path, candidate, report_path)

        assert rc != 0, "metrics fallback must still enforce passed_adoption_gate=false refusal"
