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
  - docs/ADAPTIVE_SECURITY_GAME_MODEL.md
  - README.md
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
| paid-credit API success records (primary model) | **8** |
| Valid mutation patch produced | **Yes** (S4 run #47 2026-06-11; runs 5, 6 & 7 also produced valid patches) |
| apply reached | **Yes** (runs 5, 6 & 7 apply succeeded; S4 run #47 reached apply and failed at G1) |
| evaluate reached | **Yes** (runs 5, 6 & 7 reached evaluate) |
| adoption gate passed | **Yes** (run 7 passed; runs 5 & 6 rejected for score regression under old formula — historical records) |
| promote reached | **Yes** (run 7 reached promote stage; final push failed — see run 7 triage) |
| promote_approved | false — candidate was not promoted (push-race failure before commit) |
| Propose/output-contract hardening | Implemented in PR #84; G1 repeat-multiplier gap closure in PR #91 (merged) |
| run 5 (2026-06-15, Actions run #52 / id 27582285679) | **artifact triage complete** → `evaluate_rejected` (score=494.48 ≤ previous_best=729.34 under old formula — historical record) |
| run 6 (2026-06-16, Actions run #53 / id 27586892217) | **artifact triage complete** → `evaluate_rejected` (score=478.12 ≤ previous_best=729.34 under old formula — historical record) |
| run 7 (2026-06-17, Actions run id 27683267711) | **artifact triage complete** → `promote_push_failed` (adoption gate passed, promote reached, final push failed: push-race — main advanced after persist-ledger step; push-race hardening in PR #115; candidate not promoted; genome not advanced) |
| Propose-side baseline-preservation hardening | **Implemented** (Gemini propose prompt now requires preserving all five symbolic indicators, the full request inspection surface, and the non-blocking fallback) |
| Score-schema migration | **Implemented** — `changed_lines` removed from score formula (generation-invariant scoring). `best_score` migrated from 729.34 (old formula, generation-era baseline) to **939.34** (current detector under new formula). This is a score-schema migration only, not a promotion. |
| state_id | `phase3_paid_credit_run7_promote_push_failed_owner_recovery_pending` |
| Next action | Owner-audited candidate recovery for run 7 (promote_push_failed). Candidate passed adoption gate and promote was reached but final push failed (push-race). Recovery requires separate Owner-approved PR. No new paid-credit run until recovery decision is made. |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite`, `best_score=939.34` (migrated to generation-invariant formula) |
| `data/api_usage_ledger.json` | **8** records with `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true` (2026-06-03 / 2026-06-04 ×3 / 2026-06-11 S4 run #47 / **2026-06-15 run 5** / **2026-06-16T01 run 6** / **2026-06-16T06 (7th, untriaged)** / **2026-06-17 run 7**). Runs 5 & 6 are triaged: both `evaluate_rejected`. Run 7 is triaged: `promote_push_failed`. The 7th success record (2026-06-16T06) is API/token success only and untriaged; do not infer apply/evaluate/promote from ledger success alone. |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | First 3 runs: no valid mutation patch (propose output-contract failures). S4 run #47: valid mutation_patch.json produced; apply reached and failed at G1 repeat-multiplier runtime allocation risk |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | First three runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |
| GitHub Actions (S4 run #47, 2026-06-11) | Materialize reached; apply reached; apply failed (G1 repeat-multiplier); evaluate / promote not reached |
| GitHub Actions (run 5, #52 / id 27582285679, 2026-06-15) | propose succeeded; apply succeeded (`success=true`, no violations); evaluate reached → `passed_adoption_gate=false`, score=494.48 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs (artifact blob download blocked by network egress policy). |
| GitHub Actions (run 6, #53 / id 27586892217, 2026-06-16) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=false`, score=478.12 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs. |
| GitHub Actions (run 7, id 27683267711, 2026-06-17) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=true`; promote job **reached** → `promote_candidate.py` succeeded locally, README update succeeded locally, final push **failed** (push-race: main had advanced after persist-ledger step). Candidate not committed to main. Genome not advanced. Classification: `promote_push_failed`. Push-race hardening handled in PR #115. |

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

For the 5th record (run 5, 2026-06-15) and 6th record (run 6, 2026-06-16T01), the API calls
succeeded and **artifact triage is complete** (`scripts/triage_s4_rerun.py`, evidence from
the GitHub Actions job logs because direct artifact blob download is blocked by the network
egress policy). Both runs produced a valid `mutation_patch.json`, applied it successfully,
and **reached the evaluate stage** — the first verified evaluate-stage paid-credit runs.
Both candidates were **rejected by the adoption gate** because the candidate fitness score
regressed below the generation-2 best score (run 5: 494.48; run 6: 478.12; both ≤
previous_best=729.34). `is_tool_failure=false` for both — these are clean negative results,
not pipeline failures. promote was **not reached** in either run (the Promote job was skipped).

A 7th primary-model `success=true` ledger record is present (2026-06-16T06:20:37+00:00,
`model=gemini-3-flash-preview`). This records API/token success only. It remains untriaged
and must not be treated as evidence that a new valid patch, apply, evaluate, adoption-gate
result, or promotion stage was reached.

For the 8th record (run 7, 2026-06-17T10:43:08+00:00, github_actions_run_id=27683267711),
artifact triage is complete. The API call succeeded, a valid `mutation_patch.json` was
produced, apply succeeded, evaluate was reached, and the **adoption gate was passed** for
the first time. The promote stage was reached. However, the **final push failed** due to a
push-race: `main` had advanced after the `persist-ledger` step committed the API usage
ledger entry. `promote_candidate.py` succeeded locally and the README update succeeded
locally, but the commit-and-push to `main` was rejected. The candidate was not promoted and
the genome was not advanced. Classification: `promote_push_failed`. Workflow push-race
hardening was handled separately in PR #115.

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ Incorrect |

The primary-model paid-credit API calls **have been executed** and are recorded in the ledger
(8 success records). The promotion gate was reached in run 7 but promotion did not complete:
in runs 1–3 no valid candidate patch was produced, run #47 failed at apply, runs 5 & 6 were
rejected by the adoption gate (score regression), and run 7 reached promote but the final push
failed due to a push-race. `promote_approved` remains `false` because the candidate was never
committed to `main`.

---

## 5. Mutation patch production

For the first 3 primary-model `success=true` records, **no valid mutation patch was produced**. The
Gemini output failed `propose_mutation.py` validation (`replacement_code` was not valid Python
syntax — a function definition with an empty body).

For S4 run #47 (4th record, 2026-06-11) and for runs 5, 6 & 7 (5th/6th/8th records,
2026-06-15 / 2026-06-16T01 / 2026-06-17): a valid `mutation_patch.json` **was produced**.
The propose/output-contract hardening (PR #84) functioned correctly.

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

For run 5 (2026-06-15, Actions run #52) and run 6 (2026-06-16T01, Actions run #53):
* **apply** was **reached and succeeded** — `apply_mutation.py` returned `success=true` with no
  violations and wrote `candidate_detector.py`.
* **evaluate** was **reached** — `evaluate_candidate.py` produced a full `fitness_report.json`.
* **adoption gate** result: **failed** for both. The candidate fitness score regressed below the
  generation-2 best (run 5: score=494.48; run 6: score=478.12; both ≤ previous_best=729.34).
  `is_tool_failure=false` — these are clean negative results.
* **promote** was **not reached** — the Promote Candidate job was skipped in both runs.

For run 7 (2026-06-17, Actions run id 27683267711):
* **apply** was **reached and succeeded**.
* **evaluate** was **reached** — `evaluate_candidate.py` produced a full `fitness_report.json`.
* **adoption gate** result: **passed** — first adoption gate pass in the project.
* **promote** was **reached** — `promote_candidate.py` succeeded locally and README update
  succeeded locally. The final push-and-commit to `main` **failed** due to a push-race:
  `main` had advanced after the `persist-ledger` step committed the API usage ledger entry.
  The candidate was not committed to `main`. This is an infrastructure failure, not a
  score/quality rejection. Classification: `promote_push_failed`, `is_tool_failure=true`.
  Workflow push-race hardening handled separately in PR #115.

`promote_approved` remains `false` — the candidate was never committed to `main`.

---

## 7. Next action

**Run 7 (2026-06-17, github_actions_run_id=27683267711) has been executed and triaged.**
It produced the 8th `success=true` record for `gemini-3-flash-preview` in
`data/api_usage_ledger.json` and classifies as `promote_push_failed`.

**First adoption gate pass:** Run 7 is the first paid-credit run where the candidate
passed the adoption gate. The promote stage was reached. `promote_candidate.py` succeeded
locally and the README update succeeded locally, but the final push to `main` was rejected
because `main` had advanced after the `persist-ledger` step committed the API usage ledger
entry (push-race). The candidate was not promoted. The genome was not advanced.
Workflow push-race hardening was handled separately in PR #115.

The current next action is:

> **Owner-audited candidate recovery for run 7.** The run 7 candidate passed the adoption
> gate and reached promote, but the final push failed due to a push-race (not a quality
> failure). Recovery requires a separate Owner-approved PR to apply the candidate changes
> and promote correctly. No new paid-credit run should be started until the recovery
> decision is made. No promotion occurs in this PR.

`promote_approved` remains `false` until the Project Owner explicitly approves promotion
via the candidate recovery process.

---

## 8. Non-goals

The SSOT work that introduced this file does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* execute any paid-credit or paid-credit-preflight run;
* promote any candidate or set `promote_approved=true`;
* change `core/**`, `scripts/propose_mutation.py`, `.github/workflows/**`, model names, or budgets.

---

## 9. Planning-only architecture references

The following documents exist as planning-only architecture references. They do **not** change
current runtime behavior and must not be interpreted as implemented current state:

- `docs/ADAPTIVE_SECURITY_GAME_MODEL.md`: Planning-only architecture document describing the
  Adaptive Security Game model. Merged in PR #106 as a planning layer. Does not implement
  adaptive tournament scoring, new adoption gates, new metrics, or memory model behavior.
- `README.md`: Now declares a static-to-adaptive paradigm shift at high visibility (PR #109).
  This is an aspirational/roadmap declaration. It does not implement adaptive scoring,
  new gates, new metrics, or memory model behavior.

Current-state interpretation remains governed by machine evidence, `data/project_state.json`,
and this file (`docs/PROJECT_STATE.md`). The adoption-gate score formula has been migrated
to generation-invariant scoring (`changed_lines` removed from score; see Score-schema migration
row in section 1). The promotion rules are unchanged. No candidate has been promoted.
