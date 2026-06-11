# Task Report — G1 Repeat Multiplier Gap Closure

Date: 2026-06-11

## Summary

Closed the paid-credit budget estimation gap where a retry-capable Gemini run
could be checked against a one-attempt estimate even though
`max_model_requests_per_run` permits multiple bounded `generate_content` attempts.
The fix keeps `max_output_tokens` as a token cap (not a character count), and
applies the request-attempt budget as the only repeat multiplier for output-token
and input-token cost estimates.

## Canonical State Checked

- `data/project_state.json`
  - `state_id`: `phase3_propose_output_contract_hardened_pending_owner_review`
  - `next_action`: `review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun`
  - no-API tests required; paid-credit run / workflow_dispatch / Gemini API call forbidden.
- `docs/PROJECT_STATE.md`
  - Phase 3; owner review required before any owner-approved paid-credit rerun.
  - `promote_approved=false`; no promotion in scope.
- Task-relevant machine evidence checked:
  - `data/genome.json` confirms Gemini paid-credit settings and `max_model_requests_per_run=1` in the current canonical genome.
  - `data/api_usage_ledger.json` was inspected as machine evidence only and was not edited by this task.

## Allowed / Forbidden Scope

Allowed files for this task:

- `scripts/propose_mutation.py`
- `tests/test_propose_output_contract.py`
- `docs/task_reports/TASK_REPORT_G1_REPEAT_MULTIPLIER_GAP_CLOSURE_20260612.md`

Forbidden files not changed by this task:

- `.github/**`
- `core/**`
- `data/**`
- ledger files, including `data/api_usage_ledger.json`
- `README.md`, `CLAUDE.md`, `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md`

## Changes Made

| File | Change |
|---|---|
| `scripts/propose_mutation.py` | Added bounded request-attempt budget and paid-credit estimation helpers; paid-credit live calls now budget for every permitted attempt; ledger diagnostic token estimates use the same bounded attempt count; overrun comparison remains per-response rather than inflated by retry allowance. |
| `tests/test_propose_output_contract.py` | Added no-API regression coverage proving output tokens are multiplied only by the bounded request-attempt budget, the retry hard cap is honored, and Gemini 3 thinking allowance is applied per attempt. |
| `docs/task_reports/TASK_REPORT_G1_REPEAT_MULTIPLIER_GAP_CLOSURE_20260612.md` | Added this task report and Codex Review comment resolution table. |

## Codex Review Comment Resolution

| Codex Review comment | Classification | Action taken | Files changed | Remaining risk |
|---|---|---|---|---|
| Paid-credit budget estimation priced only one Gemini request even though the retry loop can perform multiple bounded `generate_content` attempts under `max_model_requests_per_run`, leaving retry-capable runs under-budgeted. | FIXED_IN_THIS_TASK | Added `_effective_request_attempt_budget()` and `_estimated_paid_credit_budget()` so the budget gate multiplies input-token and output-token estimates by the same bounded attempt count passed to `_call_gemini_api()`. Added regression tests for the repeat multiplier and retry hard cap. | `scripts/propose_mutation.py`; `tests/test_propose_output_contract.py` | Low. The estimate is conservative for allowed attempts, but actual billing for failed transient attempts may still be unavailable from the SDK response; the ledger remains estimate-based by design. |
| `max_output_tokens` must remain a token cap and must not be re-estimated through the conservative character-to-token multiplier while closing the retry multiplier gap. | FIXED_IN_THIS_TASK | Kept `max_output_tokens` as per-attempt output tokens, added Gemini 3 thinking allowance per attempt, and applied only the bounded request-attempt multiplier. Added tests proving `max_output_tokens=100` with three attempts yields `300` estimated output tokens, not a character-multiplied value. | `scripts/propose_mutation.py`; `tests/test_propose_output_contract.py` | Low. Future pricing/model changes may require updating the cost table outside this task's allowed files. |

## Verification Commands and Results

- `python -m py_compile scripts/propose_mutation.py tests/test_propose_output_contract.py` — passed.
- `python -m pytest tests/test_propose_output_contract.py -q` — passed, 30 tests.

## No-API Confirmation

No Gemini API call, paid-credit run, `workflow_dispatch`, promotion, model-name
change, budget-setting change, or ledger edit was performed in this task.
