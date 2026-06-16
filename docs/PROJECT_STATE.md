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
| paid-credit API success records (primary model) | **6** |
| Valid mutation patch produced | **Yes** (S4 run #47 2026-06-11; runs 5 & 6 also produced valid patches) |
| apply reached | **Yes** (runs 5 & 6 apply succeeded; S4 run #47 reached apply and failed at G1) |
| evaluate reached | **Yes** (runs 5 & 6 reached evaluate — first verified evaluate-stage runs) |
| adoption gate passed | **No** (runs 5 & 6 rejected: candidate score regressed below previous_best=729.34) |
| promote reached | **No** |
| promote_approved | false |
| Propose/output-contract hardening | Implemented in PR #84; G1 repeat-multiplier gap closure in PR #91 (merged) |
| run 5 (2026-06-15, Actions run #52 / id 27582285679) | **artifact triage complete** → `evaluate_rejected` (score=494.48 ≤ previous_best=729.34) |
| run 6 (2026-06-16, Actions run #53 / id 27586892217) | **artifact triage complete** → `evaluate_rejected` (score=478.12 ≤ previous_best=729.34) |
| state_id | `phase3_paid_credit_runs_5_6_evaluate_rejected_score_regression` |
| Next action | Project Owner decision: both evaluate-stage candidates regressed below the generation-2 best score (729.34); decide propose-side improvement before any Owner-approved rerun |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite` |
| `data/api_usage_ledger.json` | **6** records with `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true` (2026-06-03 / 2026-06-04 ×3 / 2026-06-11 S4 run #47 / **2026-06-15 run 5** / **2026-06-16 run 6**). Runs 5 & 6 triaged: both `evaluate_rejected`. |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | First 3 runs: no valid mutation patch (propose output-contract failures). S4 run #47: valid mutation_patch.json produced; apply reached and failed at G1 repeat-multiplier runtime allocation risk |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | First three runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |
| GitHub Actions (S4 run #47, 2026-06-11) | Materialize reached; apply reached; apply failed (G1 repeat-multiplier); evaluate / promote not reached |
| GitHub Actions (run 5, #52 / id 27582285679, 2026-06-15) | propose succeeded; apply succeeded (`success=true`, no violations); evaluate reached → `passed_adoption_gate=false`, score=494.48 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs (artifact blob download blocked by network egress policy). |
| GitHub Actions (run 6, #53 / id 27586892217, 2026-06-16) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=false`, score=478.12 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs. |

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

For the 5th record (run 5, 2026-06-15) and 6th record (run 6, 2026-06-16), the API calls
succeeded and **artifact triage is complete** (`scripts/triage_s4_rerun.py`, evidence from
the GitHub Actions job logs because direct artifact blob download is blocked by the network
egress policy). Both runs produced a valid `mutation_patch.json`, applied it successfully,
and **reached the evaluate stage** — the first verified evaluate-stage paid-credit runs.
Both candidates were **rejected by the adoption gate** because the candidate fitness score
regressed below the generation-2 best score (run 5: 494.48; run 6: 478.12; both ≤
previous_best=729.34). `is_tool_failure=false` for both — these are clean negative results,
not pipeline failures. promote was **not reached** in either run (the Promote job was skipped).

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ Incorrect |

The primary-model paid-credit API calls **have been executed** and are recorded in the ledger
(6 success records). The promotion gate was never reached: in runs 1–3 no valid candidate patch
was produced, run #47 failed at apply, and runs 5 & 6 were rejected by the adoption gate
(score regression) before the promote stage.

---

## 5. Mutation patch production

For the first 3 primary-model `success=true` records, **no valid mutation patch was produced**. The
Gemini output failed `propose_mutation.py` validation (`replacement_code` was not valid Python
syntax — a function definition with an empty body).

For S4 run #47 (4th record, 2026-06-11) and for runs 5 & 6 (5th/6th records, 2026-06-15 /
2026-06-16): a valid `mutation_patch.json` **was produced**. The propose/output-contract
hardening (PR #84) functioned correctly.

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

For run 5 (2026-06-15, Actions run #52) and run 6 (2026-06-16, Actions run #53):
* **apply** was **reached and succeeded** — `apply_mutation.py` returned `success=true` with no
  violations and wrote `candidate_detector.py`.
* **evaluate** was **reached** — `evaluate_candidate.py` produced a full `fitness_report.json`.
* **adoption gate** result: **failed** for both. The candidate fitness score regressed below the
  generation-2 best (run 5: score=494.48; run 6: score=478.12; both ≤ previous_best=729.34).
  `is_tool_failure=false` — these are clean negative results.
* **promote** was **not reached** — the Promote Candidate job was skipped in both runs.

`promote_approved` remains `false`.

---

## 7. Next action

**Runs 5 (2026-06-15) and 6 (2026-06-16) have been executed and triaged.** Both produced a
6th and 5th `success=true` record for `gemini-3-flash-preview` in `data/api_usage_ledger.json`
and both classify as `evaluate_rejected` (artifact triage complete via
`scripts/triage_s4_rerun.py`, using the GitHub Actions job logs as the evidence source because
direct artifact blob download is blocked by the network egress policy).

The pipeline now reaches the **evaluate** stage and the adoption gate is functioning: it
correctly **rejected** both candidates because their fitness scores (494.48 and 478.12)
regressed below the generation-2 best score (729.34).

The current next action is:

> **Project Owner decision.** The propose→apply→evaluate path is healthy, but the model's
> mutations are not improving on the existing detector. Decide whether to adjust the
> propose-side prompt/strategy (so candidates target a score above previous_best=729.34)
> before requesting any new Owner-approved paid-credit rerun. No promotion is possible until a
> candidate passes the adoption gate.

`promote_approved` remains `false` until the Project Owner explicitly approves promotion
after a candidate passes the adoption gate.

---

## 8. Non-goals

The SSOT work that introduced this file does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* execute any paid-credit or paid-credit-preflight run;
* promote any candidate or set `promote_approved=true`;
* change `core/**`, `scripts/propose_mutation.py`, `.github/workflows/**`, model names, or budgets.
