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
| Valid mutation patch produced | **Yes** (Run 7 produced a patch/artifact for apply) |
| apply reached | **Yes** — Run 7 failed closed during AST policy validation |
| evaluate reached | **No** — Run 7 evaluation did not complete because apply failed |
| adoption gate ever passed | **No** |
| promote reached | **No** — Run 7 promote job was skipped |
| promote_approved | false |
| Latest triage classification | `apply_failed_or_not_reached` |
| Latest root cause | Candidate detector used a list comprehension; AST policy rejected it as runtime allocation risk |
| state_id | `phase3_run7_apply_failed_list_comprehension_runtime_allocation_risk` |
| Next action | Add propose-side guidance/pre-screening that prevents list/set/dict comprehensions and non-permitted generator expressions before any rerun, or await Owner decision |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite` |
| `data/api_usage_ledger.json` on main | **5** records with `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true`, including the Run 7 record around `2026-06-16T06:20:37.359083+00:00` with `estimated_input_chars=11775` |
| GitHub Actions Run 7 (`Cyber-Immunizer Evolution Loop`, run number #54) | Propose Mutation succeeded; Persist API Usage Ledger succeeded; Apply and Evaluate Candidate failed; Finalize Propose Status succeeded; Promote Candidate skipped |
| Apply job log | `success: false`, `candidate_path: null`, `error: candidate failed AST validation`; violation included runtime allocation risk from a list comprehension |
| Earlier paid-credit runs | Runs 5 and 6 reached apply/evaluate but were rejected below `previous_best=729.34`; earlier S4 run #47 reached apply and failed at G1 repeat-multiplier runtime allocation risk |

`data/project_state.json` mirrors these machine facts. `data/api_usage_ledger.json` is machine evidence and must not be manually edited in this state-sync PR.

---

## 3. Meaning of paid-credit API success

`success=true` in `data/api_usage_ledger.json` records **API/token success only** — the Gemini API returned an HTTP 200 response and token usage was recorded. It does **not** mean a valid candidate passed apply, evaluation, adoption, or promotion.

For Run 7, propose succeeded and the ledger was persisted, but the candidate was rejected by the apply-stage AST policy before evaluation completed.

---

## 4. Meaning of promote_approved=false

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ Correct |
| `promote_approved=false` means the Gemini API call was not executed | ❌ Incorrect |
| `promote_approved=false` means a candidate is promotion-eligible | ❌ Incorrect |

The Run 7 paid-credit API call was executed and persisted. Promotion was not available because apply failed safely and the adoption gate was not reached.

---

## 5. Run 7 apply / evaluate / promote status

Run 7 is classified as `apply_failed_or_not_reached`.

* **propose** succeeded.
* **ledger persistence** succeeded.
* **apply** was reached and failed closed during AST validation.
* **evaluate** did **not** complete because apply failed.
* **adoption gate** was **not reached**.
* **promote** was skipped / not reached.

Root cause: Gemini generated a candidate detector that used a list comprehension. The authoritative AST policy rejects list comprehensions as runtime allocation risk. This is a candidate-policy failure, not a repository infrastructure failure. The fail-closed behavior is correct and the policy must not be weakened.

---

## 6. Next action

Before another paid-credit rerun, add propose-side guidance or pre-screening so Gemini output cannot contain list comprehensions, set comprehensions, dict comprehensions, or non-permitted generator expressions. Do **not** weaken `core/policy.py`. Do **not** rerun until that prevention exists or the Project Owner explicitly decides otherwise.

---

## 7. Non-goals

This state-sync work does **not**:

* make any Gemini API call;
* trigger any `workflow_dispatch`;
* rerun any workflow;
* edit `data/api_usage_ledger.json`;
* promote any candidate or set `promote_approved=true`;
* change `core/**`, `.github/workflows/**`, model names, or budgets;
* claim candidate quality is proven;
* claim the adoption gate ran.
