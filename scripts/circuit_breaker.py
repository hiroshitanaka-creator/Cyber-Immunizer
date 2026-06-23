"""scripts/circuit_breaker.py — Consecutive-failure circuit breaker for the autonomous loop (M2).

The autonomous self-evolution loop spends paid API credit each cycle. If cycles
keep failing — the proposer produces nothing usable, the candidate keeps missing
the adoption gate, or a promotion keeps getting rolled back by the pre-publish
health check — continuing to fire paid runs only burns credit without value. The
circuit breaker counts CONSECUTIVE failed structured-evolution cycles and, once a
threshold is reached, TRIPS: paid runs are refused (fail-closed) until the Project
Owner explicitly resets it.

Design (stdlib only, mirrors scripts/api_budget.py):
  - State lives in ``data/circuit_breaker.json`` (operational state, not the
    canonical genome/project_state — kept decoupled so the breaker never rewrites
    audit lineage).
  - A single SUCCESS resets ``consecutive_failures`` to 0, but does NOT auto-clear
    a tripped breaker: once tripped, only an Owner ``--reset`` re-arms paid runs.
    (Successes can still arrive from non-paid offline cycles, which must not
    silently re-open the paid path the Owner deliberately controls.)
  - ``--check`` is fail-closed: a tripped breaker OR an unreadable/malformed state
    file both refuse (exit 1), so the gate can never fail open.

SAFETY: read-only except for the explicit record/reset subcommands, which only
touch ``data/circuit_breaker.json``. No network, no Gemini API, no candidate code.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_STATE_PATH = _PROJECT_ROOT / "data" / "circuit_breaker.json"

_DEFAULT_THRESHOLD = 3
_HISTORY_LIMIT = 50

# Modes that constitute a real structured self-evolution cycle. Only these are
# counted by the breaker; noop / preflight / legacy-raw-Python modes are not.
_EVOLUTION_MODES = frozenset({"structured-offline-sample", "structured-gemini-paid-credit"})


def default_state() -> dict:
    """Return a fresh, untripped breaker state."""
    return {
        "schema_version": 1,
        "consecutive_failures": 0,
        "failure_threshold": _DEFAULT_THRESHOLD,
        "tripped": False,
        "last_outcome": None,
        "last_reason": "",
        "last_updated": None,
        "history": [],
    }


def load_state(path: Path) -> dict:
    """Load breaker state. A missing file yields a fresh default state.

    Raises ValueError if the file exists but is malformed or structurally invalid,
    so a corrupt state cannot silently read as "not tripped" (fail-closed at the
    --check gate, which treats a load error as refuse).
    """
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"circuit breaker state is unreadable/malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("circuit breaker state must be a JSON object")
    # Backfill any missing keys from the default so older/partial files load.
    merged = default_state()
    merged.update({k: data[k] for k in data})
    if not isinstance(merged.get("history"), list):
        raise ValueError("circuit breaker 'history' must be a JSON array")
    return merged


def save_state(path: Path, state: dict) -> None:
    """Write breaker state to *path* (creates parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_tripped(state: dict) -> bool:
    return bool(state.get("tripped", False))


def _append_history(state: dict, entry: dict) -> None:
    history = list(state.get("history", []))
    history.append(entry)
    state["history"] = history[-_HISTORY_LIMIT:]


def record_outcome(
    state: dict, *, success: bool, reason: str = "",
    now: datetime | None = None, threshold: int | None = None,
) -> dict:
    """Return a new state with one outcome recorded.

    SUCCESS resets ``consecutive_failures`` to 0 but does NOT clear a tripped
    breaker — only an Owner reset re-arms paid runs. FAILURE increments the
    counter and trips the breaker once it reaches ``failure_threshold``.
    """
    state = dict(state)
    if now is None:
        now = datetime.now(timezone.utc)
    if threshold is not None:
        state["failure_threshold"] = int(threshold)
    thr = int(state.get("failure_threshold", _DEFAULT_THRESHOLD))

    if success:
        state["consecutive_failures"] = 0
        outcome = "success"
    else:
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        if state["consecutive_failures"] >= thr:
            state["tripped"] = True
        outcome = "failure"

    state["last_outcome"] = outcome
    state["last_reason"] = reason
    state["last_updated"] = now.isoformat()
    _append_history(state, {
        "timestamp": now.isoformat(),
        "outcome": outcome,
        "reason": reason,
        "consecutive_failures_after": state["consecutive_failures"],
        "tripped_after": bool(state.get("tripped", False)),
    })
    return state


def reset_state(state: dict, *, now: datetime | None = None, reason: str = "") -> dict:
    """Owner reset: clear the trip and the consecutive-failure counter."""
    state = dict(state)
    if now is None:
        now = datetime.now(timezone.utc)
    state["consecutive_failures"] = 0
    state["tripped"] = False
    state["last_outcome"] = "reset"
    state["last_reason"] = reason or "owner reset"
    state["last_updated"] = now.isoformat()
    _append_history(state, {
        "timestamp": now.isoformat(),
        "outcome": "reset",
        "reason": reason or "owner reset",
        "consecutive_failures_after": 0,
        "tripped_after": False,
    })
    return state


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes", "y"}


def decide_outcome(
    *, mode: str | None, propose_failed: str | None, structured_rules_exists: str | None,
    evaluate_result: str | None, evaluate_passed_gate: str | None, promote_result: str | None,
) -> tuple[str | None, str]:
    """Map CI job results to a breaker outcome.

    Returns ``(outcome, reason)`` where outcome is ``"success"``, ``"failure"``,
    or ``None`` (not a countable cycle — do not record). Decision lives in Python
    so it is unit-testable rather than encoded in fragile workflow shell.
    """
    mode = (mode or "").strip()
    if mode not in _EVOLUTION_MODES:
        return None, f"mode {mode!r} is not a structured evolution cycle; not counted"
    if _truthy(propose_failed):
        return "failure", "proposal failed (no usable candidate produced)"
    if not _truthy(structured_rules_exists):
        return "failure", "no structured candidate was produced"

    pr = (promote_result or "").strip().lower()
    if pr == "success":
        return "success", "structured promotion published and healthy"
    if pr == "failure":
        return "failure", "structured promotion failed the pre-publish health check or push"

    # promote was skipped (not owner-approved this run, or gate not passed).
    if _truthy(evaluate_passed_gate):
        return "success", "structured candidate passed the adoption gate (promotion not owner-approved this run)"
    er = (evaluate_result or "").strip().lower()
    if er in {"success", "failure"}:
        return "failure", "structured candidate did not pass the adoption gate"
    return None, "no conclusive structured evaluation outcome to record"


def _format_status(state: dict) -> str:
    return (
        f"tripped={state.get('tripped')} "
        f"consecutive_failures={state.get('consecutive_failures')}/"
        f"{state.get('failure_threshold')} "
        f"last_outcome={state.get('last_outcome')!r} "
        f"last_reason={state.get('last_reason')!r}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consecutive-failure circuit breaker for the autonomous loop.")
    parser.add_argument("--state", default=None, metavar="PATH")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--threshold", type=int, default=None,
                        help="Override and persist the failure threshold when recording/resetting.")
    parser.add_argument("--reason", default="")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="Exit 1 if the breaker is tripped or its state is unreadable (gate).")
    group.add_argument("--status", action="store_true")
    group.add_argument("--record-success", action="store_true", dest="record_success")
    group.add_argument("--record-failure", action="store_true", dest="record_failure")
    group.add_argument("--reset", action="store_true")
    group.add_argument("--record-from-cycle", action="store_true", dest="record_from_cycle",
                       help="Decide success/failure from CI job results, then record.")

    # Inputs for --record-from-cycle.
    parser.add_argument("--mode", default=None)
    parser.add_argument("--propose-failed", default=None, dest="propose_failed")
    parser.add_argument("--structured-rules-exists", default=None, dest="structured_rules_exists")
    parser.add_argument("--evaluate-result", default=None, dest="evaluate_result")
    parser.add_argument("--evaluate-passed-gate", default=None, dest="evaluate_passed_gate")
    parser.add_argument("--promote-result", default=None, dest="promote_result")

    args = parser.parse_args(argv)
    state_path = Path(args.state) if args.state else _DEFAULT_STATE_PATH

    # --check is fail-closed: a load error (corrupt state) must refuse.
    if args.check:
        try:
            state = load_state(state_path)
        except ValueError as exc:
            print(f"::error::circuit breaker check refused: {exc}", file=sys.stderr)
            return 1
        if is_tripped(state):
            print(f"::error::circuit breaker is TRIPPED — paid runs refused until owner reset. {_format_status(state)}",
                  file=sys.stderr)
            return 1
        print(f"circuit breaker OK ({_format_status(state)})")
        return 0

    try:
        state = load_state(state_path)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    if args.status:
        print(json.dumps(state, indent=2, ensure_ascii=False) if args.json else _format_status(state))
        return 0

    if args.reset:
        new_state = reset_state(state, reason=args.reason)
        if args.threshold is not None:
            new_state["failure_threshold"] = int(args.threshold)
        save_state(state_path, new_state)
    elif args.record_success or args.record_failure:
        new_state = record_outcome(state, success=args.record_success, reason=args.reason,
                                   threshold=args.threshold)
        save_state(state_path, new_state)
    elif args.record_from_cycle:
        outcome, reason = decide_outcome(
            mode=args.mode, propose_failed=args.propose_failed,
            structured_rules_exists=args.structured_rules_exists,
            evaluate_result=args.evaluate_result, evaluate_passed_gate=args.evaluate_passed_gate,
            promote_result=args.promote_result,
        )
        if outcome is None:
            print(f"circuit breaker: not recording — {reason}")
            if args.json:
                print(json.dumps({"recorded": False, "reason": reason}, indent=2))
            return 0
        new_state = record_outcome(state, success=(outcome == "success"), reason=reason,
                                   threshold=args.threshold)
        save_state(state_path, new_state)
    else:  # pragma: no cover - mutually exclusive group guarantees a branch
        parser.error("no action selected")
        return 2

    print(json.dumps(new_state, indent=2, ensure_ascii=False) if args.json else _format_status(new_state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
