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
| paid-credit API success records (primary model) | **5** |
| Valid mutation patch produced | **Yes** (S4 run #47, 2026-06-11) — run 5 outcome pending triage |
| apply reached | **Yes** (confirmed for runs 1–4) — run 5 outcome pending artifact triage |
| evaluate reached | **No** (confirmed for runs 1–4) — run 5 outcome pending artifact triage |
| promote reached | **No** |
| promote_approved | false |
| Propose/output-contract hardening | Implemented in PR #84; G1 repeat-multiplier gap closure in PR #91 (merged) |
| run 5 (2026-06-15) | API success recorded; apply/evaluate/promote outcome — artifact triage pending |
| state_id | `phase3_paid_credit_record_5_recorded_pending_artifact_triage` |
| Next action | Triage latest paid-credit run artifacts using `scripts/triage_s4_rerun.py`; update apply/evaluate/promote state |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite` |
| `data/api_usage_ledger.json` | **5** records with `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true` (2026-06-03 / 2026-06-04 ×3 / 2026-06-11 S4 run #47 / **2026-06-15 run 5**). Run 5 apply/evaluate/promote outcome not yet triaged. |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | First 3 runs: no valid mutation patch (propose output-contract failures). S4 run #47: valid mutation_patch.json produced; apply reached and failed at G1 repeat-multiplier runtime allocation risk |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | First three runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |
| GitHub Actions (S4 run #47, 2026-06-11) | Materialize reached; apply reached; apply failed (G1 repeat-multiplier); evaluate / promote not reached |

`data/project_state.json` mirrors these machine facts and must not contradict `data/genome.json` or `data/api_usage_ledger.json`.

---

## 3. Meaning of paid-credit API success

`success=true` in `data/api_usage_ledger.json` records **API/token success only** — the Gemini API
returned an HTTP 200 response and token usage was recorded. It does **not** mean a valid mutation
patch was produced or that apply/evaluate/promote were reached.

For the first 3 primary-model success records, `propose_mutation.py` rejected the
returned `replacement_code` as syntactically invalid Python, so no `mutation_patch.json` was written.

For the 4th record (S4 run #47, 2026-06-11), `propose_mutation.py` accepted the
`replacement_code` and wrote a valid `mutation_patch.json`. `apply_mutation.py` was reached
but failed at the G1 repeat-multiplier runtime allocation risk check (Step 7 of apply).

For the 5th record (run 5, 2026-06-15), the API call succeeded (`success=true`). The
apply/evaluate/promote outcome of this run has **not yet been determined**. Use
`scripts/triage_s4_rerun.py --artifacts-dir <DIR>` against the downloaded artifacts to
classify the outcome and determine the next action.

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ Incorrect |

The primary-model paid-credit API calls **have been executed** and are recorded in the ledger
(5 success records). The promotion gate was never reached in verified runs 1–4 because no valid
candidate patch was produced; run 5 (2026-06-15) outcome is pending artifact triage.

---

## 5. Mutation patch production

For the first 3 primary-model `success=true` records, **no valid mutation patch was produced**. The
Gemini output failed `propose_mutation.py` validation (`replacement_code` was not valid Python
syntax — a function definition with an empty body).

For S4 run #47 (4th record, 2026-06-11): a valid `mutation_patch.json` **was produced**. The
propose/output-contract hardening (PR #84) functioned correctly.

---

## 6. apply / evaluate / promote status

For the first 3 runs: apply, evaluate, and promote were **not reached**.

For S4 run #47:
* **apply** was **reached** — `apply_mutation.py` ran and failed at Step 7 (G1 repeat-multiplier
  runtime allocation risk: `confidence` expression used `float * runtime_var`).
* **evaluate** was **not reached** (apply failed; evaluate job skipped).
* **promote** was **not reached** (never eligible).

There is no adoption-gate pass/fail result from runs 1–4.
`promote_approved` remains `false`.

For run 5 (2026-06-15): apply/evaluate/promote outcome is **pending artifact triage**.
Do not assume any stage was reached until the triage tool confirms it from the downloaded artifacts.

---

## 7. Next action

**Run 5 (2026-06-15) has been executed.** A 5th `success=true` record for
`gemini-3-flash-preview` was added to `data/api_usage_ledger.json` at 2026-06-15T23:07:00Z.
**PR #91 (G1 gap closure) is merged.** The G1 repeat-multiplier gap has been closed.

The current next action is:

> **Triage the run 5 artifacts** using `scripts/triage_s4_rerun.py --artifacts-dir <DIR>`.
> Download the artifacts (`mutation-patch`, `api-usage-ledger`, `candidate-detector`,
> `fitness-report`) from the GitHub Actions run, run the triage tool, and update
> `data/project_state.json` apply/evaluate/promote fields based on the triage result.

`promote_approved` remains `false` until the Project Owner explicitly approves promotion
after reviewing the triage output and fitness report.

---

## 8. Non-goals

The SSOT work that introduced this file does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* execute any paid-credit or paid-credit-preflight run;
* promote any candidate or set `promote_approved=true`;
* change `core/**`, `scripts/propose_mutation.py`, `.github/workflows/**`, model names, or budgets.
