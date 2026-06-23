<!--
AI_DOC_META
status: OPERATOR RUNBOOK (user-facing manual for an existing executable feature)
scope: How the consecutive-failure circuit breaker protects paid runs, and how the
  Project Owner inspects and resets it.
authority: User-facing manual for scripts/circuit_breaker.py + the immunization_loop
  persist-circuit-breaker job. Describes existing behavior; does NOT define runtime
  state or current-state SSOT.
do_not_use_for:
  - changing the trip threshold without Owner intent
  - re-arming paid runs by editing state by hand instead of an audited --reset
AI_DOC_META_END
-->

# Circuit Breaker Runbook (M2 self-healing)

The autonomous loop spends paid API credit each cycle. If cycles keep failing,
continuing to fire paid runs only burns credit. The **circuit breaker** counts
**consecutive failed structured-evolution cycles** and, once a threshold is
reached, **trips** — paid runs are refused (fail-closed) until the Project Owner
resets it.

## What counts as a failure

The success/failure decision for a cycle is computed in Python
(`scripts/circuit_breaker.py: decide_outcome`) from the CI job results, so it is
unit-tested rather than encoded in fragile shell:

| Cycle outcome | Counted as |
|---|---|
| Proposal failed (no usable candidate) | **failure** |
| No structured candidate produced | **failure** |
| Candidate missed the adoption gate | **failure** |
| Promotion rolled back by the pre-publish health check / push failed | **failure** |
| Promotion published and healthy | **success** (resets counter) |
| Candidate passed the gate but promotion was not Owner-approved this run | **success** |
| noop / non-structured / inconclusive | not counted (nothing written) |

A **success resets** `consecutive_failures` to 0 but does **not** clear a tripped
breaker — once tripped, only an Owner `--reset` re-arms paid runs. (Free offline
cycles are not gated and could otherwise silently re-open the paid path the Owner
controls.)

## State

`data/circuit_breaker.json`:

```json
{
  "schema_version": 1,
  "consecutive_failures": 0,
  "failure_threshold": 3,
  "tripped": false,
  "last_outcome": null,
  "last_reason": "",
  "last_updated": null,
  "history": []
}
```

## How it gates paid runs

The propose job runs a fail-closed pre-flight on **paid modes only**
(`gemini-paid-credit`, `structured-gemini-paid-credit`):

```bash
python scripts/circuit_breaker.py --check
```

`--check` exits non-zero (refuses the run) if the breaker is **tripped** OR if the
state file is **unreadable/malformed** — it can never fail open. `noop`, offline,
and preflight modes are free and are never gated.

After each structured cycle on `main`, the `persist-circuit-breaker` job records
the outcome and commits `data/circuit_breaker.json` (rebase-retry, no API key,
write scoped to that file).

## Owner commands

```bash
# Inspect current state
python scripts/circuit_breaker.py --status            # human-readable
python scripts/circuit_breaker.py --status --json     # machine-readable

# Re-arm paid runs after fixing the underlying cause (audited reset)
python scripts/circuit_breaker.py --reset --reason "owner: fixed corpus/rules"

# Adjust the threshold while resetting/recording (persisted)
python scripts/circuit_breaker.py --reset --threshold 5 --reason "owner: widen tolerance"
```

When the breaker trips, the run log shows:

```
::error::circuit breaker is TRIPPED — paid runs refused until owner reset. tripped=True consecutive_failures=3/3 ...
```

Fix the underlying cause (e.g. corpus drift, ineffective rules) first, then
`--reset`. Resetting without fixing the cause will simply trip again.
