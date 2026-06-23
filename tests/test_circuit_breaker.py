"""tests/test_circuit_breaker.py — Consecutive-failure circuit breaker (M2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.circuit_breaker as cb

_ROOT = Path(__file__).parent.parent


# --- state machine ----------------------------------------------------------

class TestStateMachine:
    def test_default_state_is_untripped(self) -> None:
        s = cb.default_state()
        assert s["tripped"] is False
        assert s["consecutive_failures"] == 0
        assert s["failure_threshold"] == cb._DEFAULT_THRESHOLD

    def test_failures_trip_at_threshold(self) -> None:
        s = cb.default_state()
        s["failure_threshold"] = 3
        s = cb.record_outcome(s, success=False, reason="a")
        assert s["tripped"] is False and s["consecutive_failures"] == 1
        s = cb.record_outcome(s, success=False, reason="b")
        assert s["tripped"] is False and s["consecutive_failures"] == 2
        s = cb.record_outcome(s, success=False, reason="c")
        assert s["tripped"] is True and s["consecutive_failures"] == 3

    def test_success_resets_counter_but_not_trip(self) -> None:
        s = cb.default_state()
        s["failure_threshold"] = 2
        s = cb.record_outcome(s, success=False)
        s = cb.record_outcome(s, success=False)
        assert s["tripped"] is True
        # A non-paid (offline) success can arrive; it resets the counter but must
        # NOT silently re-open the paid path — only an Owner reset clears the trip.
        s = cb.record_outcome(s, success=True)
        assert s["consecutive_failures"] == 0
        assert s["tripped"] is True

    def test_reset_clears_trip(self) -> None:
        s = cb.default_state()
        s["failure_threshold"] = 1
        s = cb.record_outcome(s, success=False)
        assert s["tripped"] is True
        s = cb.reset_state(s, reason="owner")
        assert s["tripped"] is False and s["consecutive_failures"] == 0
        assert s["last_outcome"] == "reset"

    def test_threshold_override_persists(self) -> None:
        s = cb.record_outcome(cb.default_state(), success=False, threshold=5)
        assert s["failure_threshold"] == 5

    def test_history_is_bounded(self) -> None:
        s = cb.default_state()
        s["failure_threshold"] = 10_000
        for _ in range(cb._HISTORY_LIMIT + 25):
            s = cb.record_outcome(s, success=False)
        assert len(s["history"]) == cb._HISTORY_LIMIT


# --- load/save --------------------------------------------------------------

class TestLoadSave:
    def test_missing_file_yields_default(self, tmp_path: Path) -> None:
        assert cb.load_state(tmp_path / "nope.json") == cb.default_state()

    def test_malformed_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "cb.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            cb.load_state(p)

    def test_non_object_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "cb.json"
        p.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError):
            cb.load_state(p)

    def test_partial_file_backfills(self, tmp_path: Path) -> None:
        p = tmp_path / "cb.json"
        p.write_text(json.dumps({"consecutive_failures": 2}), encoding="utf-8")
        s = cb.load_state(p)
        assert s["consecutive_failures"] == 2
        assert s["failure_threshold"] == cb._DEFAULT_THRESHOLD
        assert s["tripped"] is False

    def test_roundtrip(self, tmp_path: Path) -> None:
        p = tmp_path / "cb.json"
        s = cb.record_outcome(cb.default_state(), success=False, reason="x")
        cb.save_state(p, s)
        assert cb.load_state(p)["consecutive_failures"] == 1


# --- decide_outcome ---------------------------------------------------------

class TestDecideOutcome:
    def test_non_structured_mode_not_counted(self) -> None:
        out, _ = cb.decide_outcome(mode="noop", propose_failed="false",
                                   structured_rules_exists="false", evaluate_result="skipped",
                                   evaluate_passed_gate="", promote_result="skipped")
        assert out is None

    def test_propose_failure_counts(self) -> None:
        out, _ = cb.decide_outcome(mode="structured-gemini-paid-credit", propose_failed="true",
                                   structured_rules_exists="false", evaluate_result="skipped",
                                   evaluate_passed_gate="", promote_result="skipped")
        assert out == "failure"

    def test_no_candidate_counts_as_failure(self) -> None:
        out, _ = cb.decide_outcome(mode="structured-offline-sample", propose_failed="false",
                                   structured_rules_exists="false", evaluate_result="skipped",
                                   evaluate_passed_gate="", promote_result="skipped")
        assert out == "failure"

    def test_published_promotion_is_success(self) -> None:
        out, _ = cb.decide_outcome(mode="structured-gemini-paid-credit", propose_failed="false",
                                   structured_rules_exists="true", evaluate_result="success",
                                   evaluate_passed_gate="true", promote_result="success")
        assert out == "success"

    def test_rolled_back_promotion_is_failure(self) -> None:
        out, _ = cb.decide_outcome(mode="structured-gemini-paid-credit", propose_failed="false",
                                   structured_rules_exists="true", evaluate_result="success",
                                   evaluate_passed_gate="true", promote_result="failure")
        assert out == "failure"

    def test_gate_rejected_is_failure(self) -> None:
        out, _ = cb.decide_outcome(mode="structured-gemini-paid-credit", propose_failed="false",
                                   structured_rules_exists="true", evaluate_result="success",
                                   evaluate_passed_gate="false", promote_result="skipped")
        assert out == "failure"

    def test_gate_passed_but_not_owner_approved_is_success(self) -> None:
        # Owner ran without promote_approved: candidate passed the gate → the loop
        # produced value; this is a success, not a failure.
        out, _ = cb.decide_outcome(mode="structured-gemini-paid-credit", propose_failed="false",
                                   structured_rules_exists="true", evaluate_result="success",
                                   evaluate_passed_gate="true", promote_result="skipped")
        assert out == "success"


# --- CLI --------------------------------------------------------------------

class TestCLI:
    def _state(self, tmp_path: Path, **fields) -> Path:
        p = tmp_path / "cb.json"
        s = cb.default_state()
        s.update(fields)
        cb.save_state(p, s)
        return p

    def test_check_ok_exit_0(self, tmp_path: Path) -> None:
        p = self._state(tmp_path)
        assert cb.main(["--state", str(p), "--check"]) == 0

    def test_check_tripped_exit_1(self, tmp_path: Path) -> None:
        p = self._state(tmp_path, tripped=True)
        assert cb.main(["--state", str(p), "--check"]) == 1

    def test_check_corrupt_state_is_fail_closed(self, tmp_path: Path) -> None:
        p = tmp_path / "cb.json"
        p.write_text("{bad", encoding="utf-8")
        assert cb.main(["--state", str(p), "--check"]) == 1

    def test_check_missing_state_is_ok(self, tmp_path: Path) -> None:
        # Missing file = fresh untripped breaker, not a corruption.
        assert cb.main(["--state", str(tmp_path / "nope.json"), "--check"]) == 0

    def test_record_failure_then_check_trips(self, tmp_path: Path) -> None:
        p = self._state(tmp_path, failure_threshold=1)
        assert cb.main(["--state", str(p), "--record-failure", "--reason", "boom"]) == 0
        assert cb.main(["--state", str(p), "--check"]) == 1

    def test_record_success_resets_counter(self, tmp_path: Path) -> None:
        p = self._state(tmp_path, consecutive_failures=2)
        cb.main(["--state", str(p), "--record-success"])
        assert cb.load_state(p)["consecutive_failures"] == 0

    def test_reset_clears_trip(self, tmp_path: Path) -> None:
        p = self._state(tmp_path, tripped=True, consecutive_failures=3)
        assert cb.main(["--state", str(p), "--reset", "--reason", "owner"]) == 0
        assert cb.main(["--state", str(p), "--check"]) == 0

    def test_record_from_cycle_skips_noncountable(self, tmp_path: Path) -> None:
        p = self._state(tmp_path)
        before = cb.load_state(p)
        assert cb.main(["--state", str(p), "--record-from-cycle", "--mode", "noop"]) == 0
        # Non-countable cycle writes nothing.
        assert cb.load_state(p) == before

    def test_record_from_cycle_records_failure(self, tmp_path: Path) -> None:
        p = self._state(tmp_path, failure_threshold=1)
        rc = cb.main(["--state", str(p), "--record-from-cycle",
                      "--mode", "structured-gemini-paid-credit",
                      "--propose-failed", "false", "--structured-rules-exists", "true",
                      "--evaluate-result", "success", "--evaluate-passed-gate", "false",
                      "--promote-result", "skipped"])
        assert rc == 0
        assert cb.load_state(p)["tripped"] is True

    def test_status_json(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        p = self._state(tmp_path)
        assert cb.main(["--state", str(p), "--status", "--json"]) == 0
        assert "consecutive_failures" in json.loads(capsys.readouterr().out)


# --- committed state + workflow wiring --------------------------------------

def test_committed_state_file_is_valid_and_untripped() -> None:
    state = cb.load_state(_ROOT / "data" / "circuit_breaker.json")
    assert state["tripped"] is False
    assert state["consecutive_failures"] == 0


def test_workflow_gates_paid_runs_and_persists_outcome() -> None:
    wf = (_ROOT / ".github" / "workflows" / "immunization_loop.yml").read_text(encoding="utf-8")
    # Pre-flight gate on paid modes.
    assert "Circuit breaker pre-flight (paid modes)" in wf
    assert "circuit_breaker.py --check" in wf
    # Outcome-recording job.
    assert "persist-circuit-breaker:" in wf
    assert "--record-from-cycle" in wf
    # The gate must precede any paid proposal step in the file.
    gate_idx = wf.index("Circuit breaker pre-flight (paid modes)")
    paid_idx = wf.index("Propose structured rules — gemini-paid-credit")
    assert gate_idx < paid_idx
