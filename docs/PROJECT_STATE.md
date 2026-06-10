# Project State — Single Source of Truth
This file is the human-readable current-state source for Cyber-Immunizer.
For current-state interpretation, use this file together with `data/project_state.json` and machine evidence.
If README.md, CLAUDE.md, roadmap docs, task reports, PR bodies, or historical phase docs conflict with this file, this file wins for current-state interpretation.
Historical documents preserve past state and must not be treated as current-state contradictions.

<!--
AI_DOC_META
status: CANONICAL
scope: Single source of truth for Cyber-Immunizer current-state interpretation. Pairs with data/project_state.json (machine-readable) and machine evidence (main HEAD, data/api_usage_ledger.json, data/genome.json, CI).
use_for:
  - determining the current project state deterministically
  - resolving conflicts between README / CLAUDE / roadmap / task reports / historical docs
do_not_use_for:
  - executing paid-credit runs
  - changing model names / budgets / promotion behavior
related:
  - data/project_state.json
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
AI_DOC_META_END
-->

---

## Current-state authority order

Future auditors (GPT / Claude / Codex) must interpret current state using this authority order:

1. **Machine evidence** — latest `main` HEAD, `data/api_usage_ledger.json`, `data/genome.json`, GitHub Actions / CI results.
2. `data/project_state.json` — machine-readable current-state source.
3. `docs/PROJECT_STATE.md` — this file, human-readable current-state source.
4. **Derived summaries** — `README.md` status block, `CLAUDE.md`.

Historical docs, old task reports, roadmap snapshots, old PR bodies, and old phase docs **must not** independently define current state.

---

## 1. Current state

| Field | Value |
|---|---|
| Current phase | Phase 3 |
| Phase 3 activation | Complete (PR #58–#62) |
| live_model_enabled | true |
| API mode | gemini_paid_credit |
| Model provider | gemini |
| Primary model | gemini-3-flash-preview |
| Fallback model | gemini-3.1-flash-lite |
| paid-credit API success records (primary model) | 3 |
| Valid mutation patch produced | **No** |
| apply / evaluate / promote reached | **No** (all three) |
| promote_approved | false |
| state_id | `phase3_paid_credit_api_success_patch_not_produced` |
| Next action | Fix propose / output-contract root cause before any new paid-credit run |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite` |
| `data/api_usage_ledger.json` | Exactly 3 records with `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true` (2026-06-03 / 2026-06-04) |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | For those 3 runs: no valid mutation patch produced; apply / evaluate / promote not reached |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | All three `workflow_dispatch` runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |

`data/project_state.json` mirrors these machine facts and must not contradict `data/genome.json` or `data/api_usage_ledger.json`.

---

## 3. Meaning of paid-credit API success

`success=true` in `data/api_usage_ledger.json` records **API/token success only** — the Gemini API
returned an HTTP 200 response and token usage was recorded. It does **not** mean a valid mutation
patch was produced. For all 3 primary-model success records, `propose_mutation.py` rejected the
returned `replacement_code` as syntactically invalid Python, so no `mutation_patch.json` was written.

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ Incorrect |

The 3 primary-model paid-credit API calls **were executed** and are recorded in the ledger. The
promotion gate was never reached because no valid candidate patch was produced.

---

## 5. No valid mutation patch was produced

For the 3 primary-model `success=true` records, **no valid mutation patch was produced**. The
Gemini output failed `propose_mutation.py` validation (`replacement_code` was not valid Python
syntax — a function definition with an empty body), so `patch_exists=false` for all three runs.

---

## 6. apply / evaluate / promote were not reached

For those same 3 runs:

* **apply** was not reached.
* **evaluate** was not reached (evaluate job skipped; no `fitness_report.json`, no adoption-gate result).
* **promote** was not reached (promote job skipped; never eligible).

There is no adoption-gate pass/fail result from any of the 3 paid-credit runs.

---

## 7. Next action

Fix the **propose / output-contract root cause** (Gemini returning syntactically invalid
`replacement_code`) **before any new paid-credit run**. That remediation is a separate,
Project-Owner-approved task and is **out of scope for the SSOT PR that introduced this file**.

---

## 8. Non-goals

The SSOT work that introduced this file does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* execute any paid-credit or paid-credit-preflight run;
* promote any candidate or set `promote_approved=true`;
* change `core/**`, `scripts/propose_mutation.py`, `.github/workflows/**`, model names, or budgets.
