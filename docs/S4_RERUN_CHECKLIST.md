# S4 Paid-Credit Rerun Checklist (Post-PR #98 / Run 7 Readiness)

<!--
AI_DOC_META
status: ACTIVE
scope: Human-facing checklist for Project Owner to review readiness for the next Owner-approved paid-credit rerun (Run 7) after PR #98 (propose-side baseline-preservation hardening) is merged.
use_for:
  - guiding the Project Owner through pre-run approval, artifact verification, and post-run triage for the next Owner-approved paid-credit rerun after PR #98
do_not_use_for:
  - autonomous execution — every rerun requires explicit Project Owner approval
  - changing model names, budgets, API mode, or promotion settings
related:
  - docs/PROJECT_STATE.md
  - data/project_state.json
  - data/api_usage_ledger.json
AI_DOC_META_END
-->

> **Current state (as of PR #98 merge):**
> Phase 3 active — runs 5 and 6 reached apply and evaluate, but both were rejected by
> the adoption gate because candidate scores regressed below `previous_best=729.34`
> (run 5: 494.48; run 6: 478.12). PR #98 merged propose-side baseline-preservation
> hardening so Gemini guidance now requires preserving all five symbolic indicators,
> the full request surface, and the `blocked=False` fallback while aiming strictly
> above `previous_best`. `promote_approved=false`. Next step: Project Owner review
> before any Owner-approved paid-credit rerun.
>
> **Note:** PR #98 does **not** prove candidate quality. It only hardens the propose
> prompt before the next paid-credit test. Promotion remains unavailable until a
> candidate passes the adoption gate and the Project Owner explicitly approves promotion.

---

## Pre-Run Authorization Gate

- [ ] **Project Owner has explicitly approved this rerun** in writing (GitHub comment, issue, or
  direct message). No rerun is permitted without this approval.
- [ ] Confirm `data/project_state.json` shows `promotion.promote_approved=false`.
- [ ] Confirm `data/project_state.json` shows:
  - `"state_id": "phase3_propose_side_baseline_preservation_hardened_await_owner_approved_rerun"`
  - `"next_action": "propose_side_baseline_preservation_hardened_await_owner_approved_rerun_review"`
- [ ] Confirm latest `main` includes PR #98 merge
  (merge commit `bbc3b2bab8c0bda80daf316fb735e8456ecc5354`).
- [ ] When triggering `workflow_dispatch`, set input `promote_approved=false` for the next
  post-PR98 rerun (Run 7). Setting `promote_approved=true` on a rerun after a propose-side
  prompt change is **not recommended** unless the Project Owner explicitly approves promotion.
- [ ] Confirm no uncommitted or unrelated changes to `core/**`, `scripts/**`, `.github/**`, or
  `data/**` exist on the target branch.

---

## Trigger Parameters

This section governs the **next Owner-approved paid-credit rerun after PR #98** (referred to as
**Run 7**).

| Parameter | Required Value | Notes |
|---|---|---|
| workflow_dispatch mode | `gemini-paid-credit` | Do not use `noop` or `offline-sample` for a paid run |
| promote_approved | `false` (recommended for Run 7) | Owner must explicitly set `true` to enable promotion |
| Branch | `main` only | `gemini-paid-credit` is rejected outside `main` by the workflow guard (lines 113–119 of `immunization_loop.yml`) |

> **PR #98 does not prove candidate quality.** It only hardens the propose prompt before the
> next paid-credit test. Promotion remains unavailable until a candidate passes the adoption
> gate and the Project Owner explicitly approves promotion. Keep `promote_approved=false` as the
> recommended value for Run 7 unless the Project Owner explicitly approves promotion.

> **Never display, log, or record the `GEMINI_API_KEY` value.** It is a GitHub Actions secret
> and must not appear in any artifact, comment, or task report.

---

## Expected Artifacts

After a successful run, verify the following artifacts exist and are non-empty:

| Artifact | Location / Job | Indicates |
|---|---|---|
| `mutation-patch` | `propose` job upload | `mutation_patch.json` was accepted by propose-side checks |
| `api-usage-ledger` | `propose` job upload; `persist-ledger` downloads and commits it | Ledger changed and must be persisted before the run is considered budget-consistent |
| `candidate-detector` | `evaluate` job upload after the apply step | `apply_mutation.py` wrote the candidate file |
| `fitness-report` | `evaluate` job upload after the evaluation step | `evaluate_candidate.py` completed the fitness run |

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

## Local Triage Tool

After downloading artifacts from a completed S4 rerun, use `scripts/triage_s4_rerun.py`
to classify the pipeline stage reached and get a recommended next action deterministically.
The tool is **read-only**: it never calls any API, never modifies ledger files, never promotes
a candidate, and suppresses secret-pattern strings from all output.

```bash
# Download artifacts from the GitHub Actions run into a local directory, then:
python scripts/triage_s4_rerun.py --artifacts-dir /path/to/artifacts --json

# Optionally write a Markdown summary:
python scripts/triage_s4_rerun.py --artifacts-dir /path/to/artifacts --json --markdown triage_summary.md
```

**Supported artifact directory layouts:**

The tool supports both flat and subdirectory layouts. Flat takes priority.

| Layout | Example path |
|---|---|
| Flat (preferred) | `artifacts/mutation_patch.json` |
| Subdirectory (fallback) | `artifacts/mutation-patch/mutation_patch.json` |

When downloading via `actions/download-artifact`, GitHub typically creates subdirectory
layout. Either layout works without any `--artifacts-dir` adjustment.

**Expected artifacts in `--artifacts-dir` (current workflow):**

| Filename | GitHub Actions artifact | Indicates |
|---|---|---|
| `mutation_patch.json` | `mutation-patch` | propose reached |
| `api_usage_ledger.json` | `api-usage-ledger` | ledger updated |
| `candidate_detector.py` | `candidate-detector` | apply reached |
| `fitness_report.json` | `fitness-report` | evaluate reached |

> **Note:** `promote_result.json` is **not generated by the current workflow** and is not
> listed above. The `promoted` classification is future-reserved for a workflow that emits
> this artifact. Absence of `promote_result.json` is the expected outcome in all current runs.

**fitness_report.json format:**
The tool handles both shapes that `evaluate_candidate.py` may produce:

- Flat: `{"passed_adoption_gate": bool, "score": float, ...}`
- Wrapper: `{"success": bool, "fitness_report": {"passed_adoption_gate": bool, ...}, ...}`

**Classifications returned:**

| Classification | Meaning | Malformed JSON policy |
|---|---|---|
| `propose_failed` | No valid patch produced; also if `mutation_patch.json` is malformed | warning, not tool_failure |
| `apply_failed_or_not_reached` | Patch produced but `candidate_detector.py` not written | — |
| `evaluate_rejected` | Adoption gate failed (`passed_adoption_gate=false`) | — |
| `promote_eligible` | Gate passed — requires Owner review (`requires_owner_approval=true`) | — |
| `promoted` | `promote_result.json` present (future-reserved; not current workflow) | — |
| `tool_failure` | `fitness_report.json` malformed, wrong root type, or `passed_adoption_gate` not bool | fail-closed |

**Important:** `promote_eligible` does **not** trigger promotion.
The current standard workflow promotes only within the same run when `promote_approved=true`
is set; starting a new run with `promote_approved=true` proposes a **new** mutation, it does
not promote the already-evaluated candidate. Project Owner must decide the next steps.

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
