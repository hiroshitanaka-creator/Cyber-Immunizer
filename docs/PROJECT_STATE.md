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
4. **Derived summaries** — README status block, `CLAUDE.md`.

Historical docs, old task reports, roadmap snapshots, old PR bodies, and old phase docs **must not** independently define current state.

---

## 1. Current state

| Field | Value |
|---|---|
| Current phase | Phase 3 |
| API mode | gemini_paid_credit |
| Primary model | gemini-3-flash-preview |
| Primary-model paid-credit success records | **7** |
| Run 5 | `evaluate_rejected`; score 494.48 <= previous_best 729.34 |
| Run 6 | `evaluate_rejected`; score 478.12 <= previous_best 729.34 |
| Run 7 | `apply_failed_or_not_reached`; apply-stage AST validation rejected list-comprehension runtime allocation risk |
| Cumulative apply reached | **Yes** |
| Cumulative evaluate reached | **Yes** — Runs 5 and 6 reached evaluate; Run 7 itself did not complete evaluate |
| Adoption gate ever passed | **No** |
| Promote reached | **No** |
| promote_approved | false |
| Propose-side hardening | Preserved from current main / PR #98; do not weaken policy |
| state_id | `phase3_run7_apply_failed_list_comprehension_runtime_allocation_risk` |
| Next action | Add propose-side no-comprehension guidance or pre-screening before another paid-credit rerun |

---

## 2. Machine evidence

| Source | What it proves |
|---|---|
| `data/genome.json` | `live_model_enabled=true`, `api_mode=gemini_paid_credit`, `model_provider=gemini`, `model_name=gemini-3-flash-preview`, `fallback_model_name=gemini-3.1-flash-lite` |
| `data/api_usage_ledger.json` | Latest main has **7** successful primary-model paid-credit records, including Run 7 at `2026-06-16T06:20:37.359083+00:00` with `success=true`, `actual_input_tokens=3142`, `actual_output_tokens=408`, `actual_billable_response_tokens=408`, and `estimated_cost_usd=0.03891` |
| GitHub Actions Run 7 (#54) | Propose Mutation succeeded; Persist API Usage Ledger succeeded; Apply and Evaluate Candidate failed during apply; Finalize Propose Status succeeded; Promote Candidate skipped |

`data/project_state.json` mirrors these machine facts and must not contradict `data/genome.json` or `data/api_usage_ledger.json`.

---

## 3. Meaning of paid-credit API success

`success=true` in `data/api_usage_ledger.json` records **API/token success only** — the Gemini API returned an HTTP 200 response and token usage was recorded. It does **not** mean a valid mutation was applied, evaluated, adopted, or promoted.

Run 7 proves the API/propose/ledger path worked, but it is a fail-closed candidate-policy rejection: the candidate detector used a list comprehension, and authoritative AST policy rejected that runtime allocation risk during apply-stage validation.

---

## 4. apply / evaluate / promote status

For Run 7:

* **apply** was reached and failed at AST validation.
* **evaluate** did **not** complete for Run 7.
* **adoption gate** was not reached for Run 7.
* **promote** was skipped and is not available.

Cumulative `evaluate_reached` remains true because prior runs 5 and 6 reached evaluate. `adoption_gate_ever_passed=false`, `promote_reached=false`, and `promote_approved=false` remain unchanged.

---

## 5. Next action

Before another paid-credit rerun, add propose-side guidance or pre-screening to prevent unsafe allocation-producing syntax from being emitted, including:

* list comprehensions;
* set comprehensions;
* dict comprehensions;
* non-permitted generator expressions.

Do **not** weaken `core/policy.py`. Do **not** rerun until this prevention exists or the Project Owner explicitly decides otherwise.

---

## 6. Non-goals

This Run 7 state-sync does **not**:

* rerun any workflow;
* trigger `workflow_dispatch`;
* call the Gemini API;
* manually edit `data/api_usage_ledger.json`;
* weaken policy or validator logic;
* change model names, budgets, workflow logic, detector logic, or promotion state;
* claim candidate quality is proven;
* claim adoption gate ran for Run 7;
* claim promotion is available.
