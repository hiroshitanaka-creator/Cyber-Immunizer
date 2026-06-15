# S4 Paid-Credit Rerun Checklist (Post-PR #91)

<!--
AI_DOC_META
status: ACTIVE
scope: Human-facing checklist for Project Owner to execute the next Owner-approved S4 paid-credit rerun after PR #91 (G1 gap closure) is merged.
use_for:
  - guiding the Project Owner through pre-run approval, artifact verification, and post-run triage
do_not_use_for:
  - autonomous execution — every rerun requires explicit Project Owner approval
  - changing model names, budgets, API mode, or promotion settings
related:
  - docs/PROJECT_STATE.md
  - data/project_state.json
  - data/api_usage_ledger.json
AI_DOC_META_END
-->

> **Current state (as of PR #91 merge):**
> Phase 3 active — valid mutation patch was produced in S4 run #47; apply reached but failed at
> G1 repeat-multiplier check (now closed by PR #91). Evaluate and promote have not been reached.
> `promote_approved = false`. Next step: Owner-approved S4 rerun.

---

## Pre-Run Authorization Gate

- [ ] **Project Owner has explicitly approved this rerun** in writing (GitHub comment, issue, or
  direct message). No rerun is permitted without this approval.
- [ ] Confirm `data/project_state.json` shows `promotion.promote_approved=false`.
- [ ] When triggering `workflow_dispatch`, set input `promote_approved=false` for the first
  post-PR91 rerun. Setting `promote_approved=true` on a first rerun after a gap closure is
  **not recommended** unless the Project Owner explicitly approves promotion.
- [ ] Confirm `data/project_state.json` shows
  `"state_id": "phase3_s4_g1_gap_closed_pending_owner_approved_next_s4_rerun"`.
- [ ] Confirm no uncommitted changes to `core/**`, `scripts/**`, `.github/**`, or `data/**`
  exist on the target branch.

---

## Trigger Parameters

| Parameter | Required Value | Notes |
|---|---|---|
| workflow_dispatch mode | `gemini-paid-credit` | Do not use `noop` or `offline-sample` for a paid run |
| promote_approved | `false` (recommended for first rerun) | Owner must explicitly set `true` to enable promotion |
| Branch | `main` only | `gemini-paid-credit` is rejected outside `main` by the workflow guard (lines 113–119 of `immunization_loop.yml`) |

> **Never display, log, or record the `GEMINI_API_KEY` value.** It is a GitHub Actions secret
> and must not appear in any artifact, comment, or task report.

---

## Expected Artifacts

After a successful run, verify the following artifacts exist and are non-empty:

| Artifact | Location / Job | Indicates |
|---|---|---|
| `mutation-patch` | `propose` job upload | `mutation_patch.json` was accepted by propose-side checks |
| `api-usage-ledger` | `persist-ledger` job upload | Ledger persisted; new record added with `success=true` |
| `candidate-detector` | `evaluate` job upload | `apply_mutation.py` (a step in the evaluate job) wrote the candidate file |
| `fitness-report` | `evaluate` job upload | `evaluate_candidate.py` completed the fitness run |

---

## Per-Outcome Triage Guide

### A. Evaluate not reached (apply failed again)

Evidence to check:
- GitHub Actions run → `evaluate` job → "Apply mutation patch to candidate file" step logs →
  identify the failing policy check (Step number and constraint name).
- `data/api_usage_ledger.json` → confirm the new ledger record exists with `success=true`.
- `mutation-patch` artifact → inspect `replacement_code` for the pattern that triggered the check.

Action: open a new PR to close the identified gap in `scripts/propose_mutation.py` before the
next rerun.

### B. Apply failed / Adoption gate rejected

Evidence to check:
- `evaluate` job → "Apply mutation patch to candidate file" step logs → Step 7
  (`_check_repeat_mult`) or other policy check.
- If apply succeeded and evaluate ran: `fitness-report` artifact → `adoption_gate_passed` field.
- If adoption gate rejected: `rejection_reasons` list in the fitness report.

Action: diagnose which constraint was violated and determine whether a propose-side pre-screen
can prevent it. Do not change `core/policy.py` constraints.

### C. Evaluate reached — adoption gate eligible

Evidence to check:
- `fitness-report` artifact → `adoption_gate_passed: true`, `fitness_score`, TP/FP/TN/FN.
- `evaluate` job CI logs for any warnings.
- Compare fitness score against `best_score` in `data/genome.json` (baseline: 729.34).

Action: Owner reviews fitness report and decides whether to approve promotion.

### D. Promote eligible (adoption gate passed)

Evidence to check:
- All artifacts present and non-empty (see table above).
- `promote` job CI status = green.
- `data/genome.json` updated with new `generation`, `best_score`, `current_detector_hash`.
- `data/api_usage_ledger.json` contains the new ledger record (verify `persist-ledger` job
  succeeded).

Action: Owner reviews and confirms `core/detector.py` was updated to the promoted candidate.

---

## Ledger Verification (all outcomes)

After any rerun that reaches the Gemini API:

- [ ] Confirm `persist-ledger` job in GitHub Actions **succeeded** (green).
- [ ] Confirm `data/api_usage_ledger.json` contains a new record with the correct
  `timestamp`, `model`, `api_mode`, and `success` value.
- [ ] Do **not** manually edit `data/api_usage_ledger.json`.

---

## Post-Run State Update

After the rerun completes (regardless of outcome):

- [ ] Update `data/project_state.json` → `state_id` and `next_action` to reflect the new state.
- [ ] Update `docs/PROJECT_STATE.md` → Section 1 table (apply/evaluate/promote reached fields).
- [ ] Run `python scripts/update_readme.py` to regenerate the README status block.
- [ ] Run `pytest tests/test_project_state_sync.py -x -q` and confirm all tests pass.
- [ ] Commit all state-sync changes on the appropriate branch.

---

## Hard Constraints (must not be violated)

| Constraint | Reason |
|---|---|
| Do not set `promote_approved = true` without Owner approval | Promotion is an irreversible state change |
| Do not edit `data/api_usage_ledger.json` manually | Ledger is machine evidence; manual edits corrupt the record |
| Do not call `workflow_dispatch` without Owner approval | Paid-credit runs consume real budget |
| Do not change model names, budgets, or API mode | Scope is frozen; changes require Owner decision |
| Do not weaken `core/policy.py` safety constraints | Safety boundary must not be narrowed |
| Do not display or log `GEMINI_API_KEY` | Secret must remain confidential |
