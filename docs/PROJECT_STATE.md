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
| Valid mutation patch produced | **Yes** (S4 run #47 2026-06-11; runs 5, 6 & 8 also produced valid patches) |
| apply reached | **Yes** (runs 5, 6 & 8 apply succeeded; S4 run #47 reached apply and failed at G1) |
| evaluate reached | **Yes** (runs 5, 6 & 8 reached evaluate) |
| adoption gate passed | **Yes (run 8, 2026-06-17)** — runs 5 & 6 were rejected (score regression under old formula); run 8 passed the adoption gate for the first time |
| promote reached | **Yes (run 8, 2026-06-17)** — promote was reached but the final push failed (push-race condition; hardened in PR #115) |
| promote_approved | false — candidate was not promoted (promote push failed; no completed promotion) |
| Propose/output-contract hardening | Implemented in PR #84; G1 repeat-multiplier gap closure in PR #91 (merged) |
| run 5 (2026-06-15, Actions run #52 / id 27582285679) | **artifact triage complete** → `evaluate_rejected` (score=494.48 ≤ previous_best=729.34 under old formula — historical record) |
| run 6 (2026-06-16, Actions run #53 / id 27586892217) | **artifact triage complete** → `evaluate_rejected` (score=478.12 ≤ previous_best=729.34 under old formula — historical record) |
| run 7 (2026-06-16T06:20:37, untriaged) | API/token success only — no artifact or job-log triage available |
| run 8 (2026-06-17, id 27683267711) | **artifact triage complete** → `promote_push_failed` — adoption gate passed, promote reached, final push failed (push-race; main advanced after persist-ledger commit). Candidate not promoted. |
| Propose-side baseline-preservation hardening | **Implemented** (Gemini propose prompt now requires preserving all five symbolic indicators, the full request inspection surface, and the non-blocking fallback) |
| Score-schema migration | **Implemented** — `changed_lines` removed from score formula (generation-invariant scoring). `best_score` migrated from 729.34 (old formula, generation-era baseline) to **939.34** (current detector under new formula). This is a score-schema migration only, not a promotion. |
| state_id | `phase3_run8_adoption_gate_passed_promote_push_failed_await_owner_recovery` |
| Next action | Owner-audited candidate recovery after run 8 promote push failure. The candidate from run 8 passed the adoption gate but was not promoted due to a push-race. Candidate recovery is a separate future PR; no paid-credit rerun is the next step. |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite`, `best_score=939.34` (migrated to generation-invariant formula) |
| `data/api_usage_ledger.json` | **8** primary-model paid-credit success records (`provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true`). Timestamps: 2026-06-03 / 2026-06-04 ×3 / 2026-06-11 / 2026-06-15 / 2026-06-16 ×2 / 2026-06-17. **Proves API/token success count and timestamp/cost fields only.** Does **not** prove apply, evaluate, adoption-gate, or promote stage outcomes — do not infer stage results from ledger success alone. |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | First 3 runs: no valid mutation patch (propose output-contract failures). S4 run #47: valid mutation_patch.json produced; apply reached and failed at G1 repeat-multiplier runtime allocation risk |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | First three runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |
| GitHub Actions (S4 run #47, 2026-06-11) | Materialize reached; apply reached; apply failed (G1 repeat-multiplier); evaluate / promote not reached |
| GitHub Actions (run 5, #52 / id 27582285679, 2026-06-15) | propose succeeded; apply succeeded (`success=true`, no violations); evaluate reached → `passed_adoption_gate=false`, score=494.48 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs (artifact blob download blocked by network egress policy). |
| GitHub Actions (run 6, #53 / id 27586892217, 2026-06-16) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=false`, score=478.12 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs. |
| GitHub Actions (run 8, id 27683267711, 2026-06-17) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=true` (first adoption gate pass); promote stage reached; `promote_candidate.py` and README status update succeeded locally; final git push failed — `main` advanced after `persist-ledger` committed the API usage ledger entry (push-race condition). Candidate **not promoted**. `is_tool_failure=true`. Evidence: GitHub Actions run 27683267711 job logs / run context. Push-race hardening merged in PR #115. |

`data/project_state.json` mirrors these machine facts and must not contradict `data/genome.json` or `data/api_usage_ledger.json` (API/token success count). Stage outcomes (apply/evaluate/adoption-gate/promote) are derived from GitHub Actions job logs and artifact triage, not from the ledger alone.

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

A 7th primary-model `success=true` ledger record is present (2026-06-16T06:20:37+00:00,
`model=gemini-3-flash-preview`). This records API/token success only. No artifact or job-log
triage is available; it must not be treated as evidence that apply, evaluate, or promote were
reached.

An 8th primary-model `success=true` ledger record is present (2026-06-17T10:43:08+00:00,
`model=gemini-3-flash-preview`, GitHub Actions run id 27683267711). Triage classification:
`promote_push_failed`. apply was reached and succeeded; evaluate was reached and the candidate
passed the adoption gate for the first time. The promote stage was reached; `promote_candidate.py`
and the README status update succeeded locally, but the final git push failed because `main`
had advanced after `persist-ledger` committed the API usage ledger entry (push-race condition).
The candidate was not promoted to `main`. The push-race hardening was merged separately in PR #115.

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ Incorrect |

The primary-model paid-credit API calls **have been executed** and are recorded in the ledger
(7 success records). The promotion gate was never reached: in runs 1–3 no valid candidate patch
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

For run 8 (2026-06-17, Actions run id 27683267711):
* **apply** was **reached and succeeded**.
* **evaluate** was **reached** — the candidate passed the adoption gate for the first time.
* **adoption gate** result: **passed** — first time an adoption gate pass has been recorded.
* **promote** was **reached** — `promote_candidate.py` succeeded locally and the README status
  update succeeded locally, but the final git push failed. `main` had advanced after
  `persist-ledger` committed the API usage ledger entry (push-race condition). The candidate
  was **not promoted** to `main`. The push-race hardening was merged in PR #115.
* `is_tool_failure=true` (infrastructure failure, not an evaluate rejection).

`promote_approved` remains `false` — no completed promotion has occurred.

---

## 7. Next action

**Run 8 (2026-06-17, id 27683267711) passed the adoption gate** — the first time this has
occurred. The promote stage was reached. However, the final promote push failed due to a
push-race condition: `main` had advanced (the `persist-ledger` step committed the API usage
ledger entry) after the Promote Candidate job started, causing a non-fast-forward push
rejection. The candidate was not promoted.

The push-race hardening was merged separately in PR #115 (`fix(workflow): fail fast on stale
promote target`).

The current next action is:

> **Owner-audited candidate recovery after run 8 promote push failure.** The run 8 candidate
> passed the adoption gate but was lost due to a push-race. The Project Owner must decide
> whether to recover the run 8 candidate (a separate future PR) or wait for a fresh
> Owner-approved paid-credit rerun against `previous_best=939.34`. No new paid-credit
> run is required as an immediate next step.

`promote_approved` remains `false` until the Project Owner explicitly approves promotion
after a candidate passes the adoption gate and a completed promotion PR is merged.

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
