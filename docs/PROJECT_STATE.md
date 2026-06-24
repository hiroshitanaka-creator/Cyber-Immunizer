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
| paid-credit API success records (primary model) | **19** |
| Valid mutation patch produced | **Yes** (S4 run #47 2026-06-11; runs 5, 6 & 8 also produced valid patches; runs 11, 12 & 13 produced patches that reached evaluate but were rejected — `missing_baseline_symbolic_indicator_runtime`) |
| apply reached | **Yes** (runs 5, 6, 8, 11, 12 & 13 apply succeeded; S4 run #47 reached apply and failed at G1) |
| evaluate reached | **Yes** (runs 5, 6 & 8 reached evaluate and were processed; runs 11, 12 & 13 reached evaluate → rejected as `evaluate_rejected`) |
| adoption gate passed | **Yes (run 8, 2026-06-17)** — runs 5 & 6 were rejected (score regression under old formula); run 8 passed the adoption gate for the first time |
| promote reached | **Yes (run 8, 2026-06-17)** — promote was reached; original push failed (push-race; hardened in PR #115); candidate recovered via owner-audited recovery 2026-06-18 |
| promote_approved | **true** — generation 4 promoted via owner-approved paid-credit run #59 and active on main; score 948.04; hash ebb8799d… |
| Generation | **4** (promoted 2026-06-18) |
| best_score | **948.04** (generation 4, hash ebb8799d…) |
| Propose/output-contract hardening | Implemented in PR #84; G1 repeat-multiplier gap closure in PR #91 (merged) |
| run 5 (2026-06-15, Actions run #52 / id 27582285679) | **artifact triage complete** → `evaluate_rejected` (score=494.48 ≤ previous_best=729.34 under old formula — historical record) |
| run 6 (2026-06-16, Actions run #53 / id 27586892217) | **artifact triage complete** → `evaluate_rejected` (score=478.12 ≤ previous_best=729.34 under old formula — historical record) |
| run 7 (2026-06-16T06:20:37, untriaged) | API/token success only — no artifact or job-log triage available |
| run 8 (2026-06-17, id 27683267711) | **artifact triage complete** → `promote_push_failed_recovered` — adoption gate passed; promote reached; original push failed (push-race); **candidate recovered and promoted to generation 3 via owner-audited recovery 2026-06-18** |
| run #59 (2026-06-18) | **owner-approved paid-credit promotion complete** → API/token success, proposal produced, apply reached, candidate contract checks passed, evaluate reached, adoption gate passed, promote reached, and promoted/merged as generation 4 (score 948.04, hash ebb8799d…). |
| run 10 (2026-06-19T14:43:51, untriaged) | API/token success only — no artifact or job-log triage available |
| run 11 (2026-06-21T07:22:43, run #64 / id 27897133424) | **triage complete** → `evaluate_rejected` — Gemini dropped all five symbolic indicator strings (`missing_baseline_symbolic_indicator_runtime`); Promote Candidate skipped |
| run 12 (2026-06-21T07:29:34, run #65 / id 27897282725) | **triage complete** → `evaluate_rejected` — same `missing_baseline_symbolic_indicator_runtime` rejection |
| run 13 (2026-06-21T07:35:14, run #66 / id 27897419170) | **triage complete** → `evaluate_rejected` — same `missing_baseline_symbolic_indicator_runtime` rejection; propose-prompt hardening implemented in PR #156 |
| run 14 (2026-06-22T02:32:07, untriaged) | API/token success only — no artifact or job-log triage available |
| run 15 (2026-06-23T10:44:04, untriaged) | API/token success only — no artifact or job-log triage available |
| run #71 (2026-06-23, id 28063817339) | **triage complete** → first ignition; **legacy** gemini-paid-credit mode (raw-Python path); no structured candidate; legacy Promote Candidate skipped |
| runs #72-#74 (2026-06-23, id 28064261701 / 28064587565 / 28064742034) | **triage complete** → `structured_evaluate_rejected` — structured-gemini-paid-credit + structured_baseline; each produced a structured candidate with fp_rate 0.0 but failed the adoption gate (regression/holdout/drift floors). After 3 consecutive structured gate failures the **circuit breaker TRIPPED** (`data/circuit_breaker.json`: tripped=true, 3/3); detector_mode stayed legacy (no unsafe promotion). Motivated the realistic baseline-floor fix + proposer strengthening. |
| Propose-side baseline-preservation hardening | **Implemented** (Gemini propose prompt now requires preserving all five symbolic indicators, the full request inspection surface, and the non-blocking fallback) |
| Score-schema migration | **Implemented** — `changed_lines` removed from score formula (generation-invariant scoring). `best_score` migrated from 729.34 (old formula) to 939.34 (generation 2 under new formula), then to **947.66** (generation 3, run 8 candidate, 2026-06-18). |
| state_id | `phase3_generation4_paid_credit_promotion_active` |
| Layer 2 value-validation evidence | **Owner-accepted (2026-06-23)** — see `docs/value_validation/LAYER2_REALISTIC_EVALUATION_SUMMARY.md`. On a small canonical neutralized corpus, the promoted gen-4 detector's symbolic capability detected 0.0% of realistic threats; a structured ruleset detected 100.0% (FP 0.0%, all adaptive floors 1.0). Acceptance is bounded: it validates the evaluation path and quantifies the symbolic wall + a safe route to close it. It does **not** claim the promoted runtime detector detects realistic threats or is production-WAF ready. |
| Structured-rules promotion path (R3) | **Implemented** — `core/active_detector.py` (runtime resolver) + `scripts/promote_structured_candidate.py` (fail-closed, self re-evaluating, `--owner-approved` required) allow a validated structured ruleset to become the active detector via `genome.detector_mode`. Default `detector_mode="legacy"` keeps runtime behavior unchanged. |
| Next action | Treat generation 4 as the audited Phase 3 baseline; owner decision required before any next paid-credit experiment. Layer 2 evaluation path validated and Owner-accepted (bounded); the structured-rules promotion path (R3) now exists. Evolving the promoted detector to realistic capability via that path (with an Owner-supplied realistic corpus, and/or live LLM proposal under paid-credit approval — R4) remains future, owner-gated work (design-doc phases 5–7). |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite`, `generation=4`, `best_score=948.04`, `current_detector_hash=ebb8799d…` (generation 4 promoted via owner-approved paid-credit run #59 on 2026-06-18) |
| `data/api_usage_ledger.json` | **19** primary-model paid-credit success records (`provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true`). Timestamps: 2026-06-03 / 2026-06-04 ×3 / 2026-06-11 / 2026-06-15 / 2026-06-16 ×2 / 2026-06-17 / 2026-06-18 / 2026-06-19 / 2026-06-21 ×3 / 2026-06-22 / 2026-06-23 ×5 (runs #71-#74 ignition). **Proves API/token success count and timestamp/cost fields only.** Does **not** prove apply, evaluate, adoption-gate, or promote stage outcomes — do not infer stage results from ledger success alone. |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | First 3 runs: no valid mutation patch (propose output-contract failures). S4 run #47: valid mutation_patch.json produced; apply reached and failed at G1 repeat-multiplier runtime allocation risk |
| GitHub Actions (runs 26919888348 / 26922191264 / 26924388218) | First three runs concluded `failure` at finalize-propose-status; evaluate / promote jobs skipped |
| GitHub Actions (S4 run #47, 2026-06-11) | Materialize reached; apply reached; apply failed (G1 repeat-multiplier); evaluate / promote not reached |
| GitHub Actions (run 5, #52 / id 27582285679, 2026-06-15) | propose succeeded; apply succeeded (`success=true`, no violations); evaluate reached → `passed_adoption_gate=false`, score=494.48 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs (artifact blob download blocked by network egress policy). |
| GitHub Actions (run 6, #53 / id 27586892217, 2026-06-16) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=false`, score=478.12 ≤ previous_best=729.34, `is_tool_failure=false`; promote job **skipped**. Evidence from job logs. |
| GitHub Actions (run 8, id 27683267711, 2026-06-17) | propose succeeded; apply succeeded; evaluate reached → `passed_adoption_gate=true` (first adoption gate pass); promote stage reached; `promote_candidate.py` and README status update succeeded locally; final git push failed — `main` advanced after `persist-ledger` committed the API usage ledger entry (push-race condition). Original promote **failed**. `is_tool_failure=true`. Evidence: GitHub Actions run 27683267711 job logs / run context. Push-race hardening merged in PR #115. |
| Owner-audited recovery (2026-06-18) | Historical generation 3 recovery: candidate hash verified (c488855e…) against run 8 job-log fitness report. `promote_candidate.py` re-executed locally. `core/detector.py` updated to generation 3 (score 947.66). `data/genome.json` and `data/evolution_history.json` updated. No Gemini API call; no new paid-credit run. |
| Generation 4 paid-credit promotion (2026-06-18, run #59) | Current active baseline: API/token success recorded, candidate promoted and merged as generation 4 (score 948.04, hash ebb8799d…). |

Machine evidence (`data/genome.json`, `data/evolution_history.json`, `data/api_usage_ledger.json`, and current HEAD) establishes generation 4 as the active baseline. `data/project_state.json` records that current state and now matches the ledger's 19 primary-model paid-credit success records. Stage outcomes (apply/evaluate/adoption-gate/promote) are derived from GitHub Actions job logs, promotion path, and committed state, not from the ledger alone.

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
The candidate was not promoted to `main` via the original run 8 workflow (push-race). The push-race hardening was merged separately in PR #115. The candidate was subsequently recovered via owner-audited PR #117 and promoted to generation 3 on main.

---

## 4. Meaning of promote_approved=true (current state)

`promote_approved` is now `true` as of 2026-06-18 (run 8 candidate recovery PR).

| Claim | Correct? |
|---|---|
| `promote_approved=true` means the run 8 candidate was promoted to `core/detector.py` | ✅ Correct |
| `promote_approved=true` means generation 4 is now active (score 948.04) | ✅ Correct |
| `promote_approved=true` means a new paid-credit run was executed | ❌ Incorrect — no new API call was made |
| `promote_approved=true` means the generation 4 promotion has been merged to main | ✅ Correct — run #59 promotion merged on 2026-06-18; generation 4 is now active on main |

The primary-model paid-credit API calls **have been executed** and are recorded in the ledger
(15 success records). Run 8 (2026-06-17) passed the adoption gate. The candidate was recovered
via owner-audited recovery on 2026-06-18: hash verified against run 8 job-log fitness report,
`promote_candidate.py` re-executed, generation 3 written. Recovery was completed via
owner-audited PR #117 (merged 2026-06-18). That recovery is historical; generation 4 is now active on main after run #59 promotion.

The ledger now contains **15** primary-model `success=true` records. Some records, including run 10 (2026-06-19T14:43:51+00:00), run 14 (2026-06-22T02:32:07+00:00), and run 15 (2026-06-23T10:44:04+00:00), are API/token success only unless separately triaged from job logs/artifacts. They must not be treated as evidence that apply, evaluate, or promote were reached.

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
  `persist-ledger` committed the API usage ledger entry (push-race condition). The original
  promote push **failed**. The push-race hardening was merged in PR #115.
* `is_tool_failure=true` (infrastructure failure, not an evaluate rejection).
* **Recovery (2026-06-18)**: candidate hash verified (c488855e…) against run 8 job-log fitness
  report. `promote_candidate.py` re-executed. `core/detector.py` updated to generation 3
  (score 947.66). No new Gemini API call. `promote_approved` set to `true`. This is historical context; generation 4 is the current active baseline.

`promote_approved` remains `true`; generation 3 recovery is historical, and generation 4 is now the active audited baseline after run #59.

---

## 7. Next action

**Run 8 candidate recovered and promoted to generation 3 (2026-06-18).** The candidate from
run 8 (id 27683267711) passed the adoption gate on 2026-06-17. The original promote push failed
(push-race; hardened in PR #115). On 2026-06-18, an owner-audited recovery was executed:
candidate hash verified (c488855e…) against run 8 job-log fitness report; `promote_candidate.py`
re-executed; `core/detector.py` updated to generation 3 (score 947.66); `data/genome.json` and
`data/evolution_history.json` updated. No new Gemini API call was made. This recovery is historical context; generation 4 is now active after run #59.

The current next action is:

> **Generation 4 is the audited Phase 3 baseline; owner decision required before any next paid-credit experiment**
> — no automatic paid-credit run. Run #59 promotion has merged; generation 4 is active on main.

`promote_approved` is `true`. PR #117 merged on 2026-06-18. Generation 4 is now active on main after owner-approved paid-credit run #59.
The next paid-credit run (when owner-approved) will target `previous_best=948.04`.

---

## 8. Non-goals of the run 8 recovery PR

The run 8 candidate recovery PR does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* execute any new paid-credit or paid-credit-preflight run;
* create or duplicate any ledger record in `data/api_usage_ledger.json`;
* change `scripts/propose_mutation.py`, `.github/workflows/**`, model names, or budgets.

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
row in section 1). The promotion rules are unchanged. The run 8 candidate has been promoted
to generation 3 via owner-audited PR #117 and is now active on main. The original run 8
workflow still failed at the final promote push, but recovery completed through PR #117
without a new API call, workflow_dispatch, or paid-credit run.
