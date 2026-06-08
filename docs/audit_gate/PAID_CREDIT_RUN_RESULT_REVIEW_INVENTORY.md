# Existing Paid-Credit Run Result Review Inventory

<!-- AI_DOC_META
created_by: claude-sonnet-4-6
task: paid-credit run result evidence inventory (docs-only)
pr: 82
date: 2026-06-08
primary_sources: data/api_usage_ledger.json, GitHub Actions runs 26919888348 / 26922191264 / 26924388218
-->

## 1. Verification Scope

**Purpose**: Read-only evidence inventory for the three existing `gemini-3-flash-preview` /
`gemini_paid_credit` / `success=true` records in `data/api_usage_ledger.json`.

**This inventory answers:**

1. What ledger records exist?
2. Which workflow runs correspond to those ledger records?
3. Was a candidate patch generated?
4. Was the candidate patch applied?
5. Was the candidate evaluated?
6. What was the evaluate / adoption-gate result?
7. Was promotion skipped, blocked, or never reached?
8. What does `promote_approved=false` currently mean?
9. What evidence is missing?
10. What should the Project Owner decide next?

**Inventory date**: 2026-06-08

---

## 2. Verified Repository State

| Item | Expected | Verified |
|---|---|---|
| Latest main commit | `ab1101a2ed71be3b45baafbdba7740867885d428` | ✅ `ab1101a` (git log) |
| PR #79 | closed / merged | ✅ merged at 2026-06-08T04:17:50Z, merge commit `d3ed3f23` |
| PR #80 | closed / merged | ✅ merged at 2026-06-08T05:51:43Z, merge commit `7cd189a6` |
| PR #81 | closed / merged | ✅ merged at 2026-06-08T06:12:43Z, head `3eccb043` |
| Open PRs | 0 | ✅ 0 open PRs |
| Current branch | `claude/paid-credit-result-inventory-Tuy8P` | ✅ confirmed |

---

## 3. Ledger Evidence

Full contents of `data/api_usage_ledger.json` (7 records total, verified 2026-06-08):

| # | timestamp | provider | model | api_mode | success | actual_input_tokens | actual_output_tokens | estimated_cost_usd | error |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-06-01T05:58:42Z | gemini | gemini-2.0-flash | gemini_paid_credit | **false** | null | null | 0.003634 | ClientError (non-transient) |
| 2 | 2026-06-02T02:28:54Z | gemini | gemini-2.0-flash | gemini_paid_credit | **false** | null | null | 0.003634 | ClientError status=404 NOT_FOUND |
| 3 | 2026-06-02T02:30:36Z | gemini | gemini-2.0-flash | gemini_paid_credit | **false** | null | null | 0.003634 | ClientError status=404 NOT_FOUND |
| 4 | 2026-06-02T06:07:07Z | gemini | gemini-3.1-flash-lite | gemini_paid_credit | **true** | 1296 | 448 | 0.020216 | (none) |
| 5 | 2026-06-03T23:36:37Z | gemini | **gemini-3-flash-preview** | gemini_paid_credit | **true** | 1296 | 590 | 0.025336 | (none) |
| 6 | 2026-06-04T00:34:12Z | gemini | **gemini-3-flash-preview** | gemini_paid_credit | **true** | 1296 | 562 | 0.025336 | (none) |
| 7 | 2026-06-04T01:33:29Z | gemini | **gemini-3-flash-preview** | gemini_paid_credit | **true** | 1296 | 561 | 0.025336 | (none) |

**Note on `success=true` in the ledger**: This field records whether the Gemini API returned an
HTTP 200 response with token counts. It does NOT record whether `propose_mutation.py` succeeded
in producing a valid mutation patch from that response. See Section 6 for the distinction.

---

## 4. Primary Model Paid-Credit Success Records

The three primary-model records (records #5–#7 above) are the target of this inventory.

| Record | Ledger timestamp | Corresponding workflow run | Run conclusion |
|---|---|---|---|
| #5 | 2026-06-03T23:36:37Z | Run ID 26919888348 (created 2026-06-03T23:36:18Z) | **failure** |
| #6 | 2026-06-04T00:34:12Z | Run ID 26922191264 (created 2026-06-04T00:33:54Z) | **failure** |
| #7 | 2026-06-04T01:33:29Z | Run ID 26924388218 (created 2026-06-04T01:33:11Z) | **failure** |

All three runs were `workflow_dispatch` events on `main` branch.

---

## 5. Workflow Run / Artifact Mapping

### Run #1 — ID 26919888348 (ledger record #5)

| Evidence type | Status | Detail |
|---|---|---|
| workflow_run | **FOUND** | ID 26919888348, event=workflow_dispatch, branch=main, sha=`90d39c86f6f1` |
| Run conclusion | failure | finalize-propose-status job failed |
| ledger artifact | **FOUND (expired)** | `api-usage-ledger`, 667 bytes, expired 2026-06-04T23:36:37Z |
| mutation_patch artifact | **NOT FOUND** | step "Upload mutation patch artifact" = SKIPPED (`patch_exists=false`) |
| candidate_detector artifact | **NOT FOUND** | evaluate job = SKIPPED |
| fitness_report artifact | **NOT FOUND** | evaluate job = SKIPPED |
| apply_result | **NOT FOUND** | apply step never ran |
| evaluate_result | **NOT FOUND** | evaluate job = SKIPPED |
| promotion_result | **NOT REACHED** | promote job = SKIPPED |

### Run #2 — ID 26922191264 (ledger record #6)

| Evidence type | Status | Detail |
|---|---|---|
| workflow_run | **FOUND** | ID 26922191264, event=workflow_dispatch, branch=main, sha=`4482b416d168` |
| Run conclusion | failure | finalize-propose-status job failed |
| ledger artifact | **FOUND (expired)** | `api-usage-ledger`, 697 bytes, expired 2026-06-05T00:34:12Z |
| mutation_patch artifact | **NOT FOUND** | step "Upload mutation patch artifact" = SKIPPED (`patch_exists=false`) |
| candidate_detector artifact | **NOT FOUND** | evaluate job = SKIPPED |
| fitness_report artifact | **NOT FOUND** | evaluate job = SKIPPED |
| apply_result | **NOT FOUND** | apply step never ran |
| evaluate_result | **NOT FOUND** | evaluate job = SKIPPED |
| promotion_result | **NOT REACHED** | promote job = SKIPPED |

### Run #3 — ID 26924388218 (ledger record #7)

| Evidence type | Status | Detail |
|---|---|---|
| workflow_run | **FOUND** | ID 26924388218, event=workflow_dispatch, branch=main, sha=`6b428f147ac5` |
| Run conclusion | failure | finalize-propose-status job failed |
| ledger artifact | **FOUND (expired)** | `api-usage-ledger`, 718 bytes, expired 2026-06-05T01:33:30Z |
| mutation_patch artifact | **NOT FOUND** | step "Upload mutation patch artifact" = SKIPPED (`patch_exists=false`) |
| candidate_detector artifact | **NOT FOUND** | evaluate job = SKIPPED |
| fitness_report artifact | **NOT FOUND** | evaluate job = SKIPPED |
| apply_result | **NOT FOUND** | apply step never ran |
| evaluate_result | **NOT FOUND** | evaluate job = SKIPPED |
| promotion_result | **NOT REACHED** | promote job = SKIPPED |

---

## 6. Candidate Patch Evidence

**Candidate patch: NOT PRODUCED in any of the three runs.**

Source evidence — propose job log for all three runs (identical output):

```json
{
  "success": false,
  "error": "Gemini replacement_code validation failed: replacement_code is not valid Python syntax: expected an indented block after function definition on line 1 (<unknown>, line 3)",
  "patch_path": null
}
```

**Interpretation:**

The Gemini API returned a response (HTTP 200, tokens consumed, recorded as `success=true` in the
ledger). The response contained a `replacement_code` field. `propose_mutation.py` validated the
returned code with Python's `ast.parse()` and found it was syntactically invalid — specifically,
a function definition followed by an empty body (missing the required indented block).

Because `patch_path` was `null` in all three runs, `mutation_patch.json` was never written to
`.cyber_immunizer/`, and the workflow step "Upload mutation patch artifact" was skipped.
As a result, `patch_exists=false` for all three runs.

**Job structure (all three runs identical):**

| Job | Conclusion | Note |
|---|---|---|
| Propose Mutation | success | API call step succeeded; but propose_mutation.py exited non-zero |
| Persist API Usage Ledger | **success** | Ledger committed to main (budget-cap integrity maintained) |
| Apply and Evaluate Candidate | **skipped** | Condition: `patch_exists == 'true'` — was false |
| Finalize Propose Status | **failure** | `PROPOSE_FAILED=true`, surfaced after ledger persist |
| Promote Candidate | **skipped** | Condition: evaluate.passed_adoption_gate == 'true' — never evaluated |

---

## 7. Apply Result Evidence

**Apply result: NOT FOUND — apply step never ran in any of the three runs.**

The `evaluate` job (Job 4 in `immunization_loop.yml`) contains the apply step:

```yaml
- name: Apply mutation patch to candidate file
  run: python scripts/apply_mutation.py ...
```

This job has the condition `if: needs.propose.outputs.patch_exists == 'true'`. Since
`patch_exists=false` in all three runs, the entire evaluate job was skipped, and the apply
step never executed.

---

## 8. Evaluate Result Evidence

**Evaluate result: NOT FOUND — evaluate job was SKIPPED in all three runs.**

The `evaluate_candidate.py` script was never invoked. No `fitness_report.json` artifact was
produced. No `passed_adoption_gate` output was set.

There is no adoption-gate pass/fail result to report from any of the three paid-credit runs.

---

## 9. Promotion Decision State

**Promote job: SKIPPED in all three runs — NOT REACHED.**

The `promote` job has multiple conditions, including:

```yaml
needs.evaluate.outputs.passed_adoption_gate == 'true'
```

Since the evaluate job was skipped (patch_exists=false), `passed_adoption_gate` was never set
to `true`. The promote job was never eligible to run, regardless of the `promote_approved` input.

**`promote_approved` input in the three runs**: The workflow_dispatch `inputs` field returned `{}`
(empty) in the GitHub API for all three runs, meaning the `promote_approved` input was either
not provided or defaulted to `false`. However, this is moot: even if `promote_approved=true` had
been passed, the promote job would still have been skipped because the evaluate job did not run.

---

## 10. promote_approved=false Interpretation

**Current state in `data/genome.json`**:

```json
"promote_approved": null
```

**Note**: `data/genome.json` does not contain a `promote_approved` field. This field appears
only as a `workflow_dispatch` input parameter in `.github/workflows/immunization_loop.yml` and
is represented in the README status block as generated by `scripts/update_readme.py`.

**Correct interpretation of `promote_approved=false`**:

| Claim | Correct? |
|---|---|
| `promote_approved=false` means promotion is not approved | ✅ **Correct** |
| `promote_approved=false` means the Gemini API call was not executed | ❌ **Incorrect** |
| `promote_approved=false` means the paid-credit run has not occurred | ❌ **Incorrect** |

The three `gemini-3-flash-preview` paid-credit API calls were executed on 2026-06-03 and
2026-06-04, recorded in `data/api_usage_ledger.json`, and committed to `main`. The promotion
gate was never reached in any run because no valid candidate patch was produced.

---

## 11. Missing Evidence / Unresolved Questions

| Evidence | Status | Source checked | Reason missing |
|---|---|---|---|
| mutation_patch.json content (any run) | NOT FOUND | GitHub Actions artifacts | Not produced; artifacts would have expired (1-day retention) |
| candidate_detector.py content | NOT FOUND | GitHub Actions artifacts | Never produced (evaluate job skipped) |
| fitness_report.json content | NOT FOUND | GitHub Actions artifacts | Never produced (evaluate job skipped) |
| Actual Gemini response text | NOT FOUND | No log output | propose_mutation.py logs only the error, not the raw API response text |
| Specific line/column of syntax error in Gemini output | PARTIAL | Log shows "line 1 … line 3" only | Raw replacement_code not stored in accessible log |
| workflow_dispatch input values (mode / promote_approved) | UNVERIFIED | GitHub API inputs={} | Inputs not captured in workflow run metadata via API (may have been provided via UI) |
| Whether all 3 runs were manual or scripted | UNVERIFIED | workflow_dispatch event confirmed; actor not checked | Triggering actor identity not retrieved |
| Whether gemini-3.1-flash-lite record #4 produced a patch | NOT SEARCHED | Out of scope (non-primary model) | Not a gemini-3-flash-preview record |

---

## 12. Recommended Next Project Owner Decision

The three paid-credit runs consumed API budget but produced no valid candidate patches due to
a consistent Python syntax error in the Gemini model's output.

**The Project Owner must decide among:**

### Option A — Investigate and remediate the propose_mutation.py / prompt issue

- Root cause: Gemini returned syntactically invalid `replacement_code` (function without body)
  consistently across 3 attempts.
- Possible causes: prompt structure issue, model output format regression, missing few-shot
  examples, `max_output_tokens` constraint (currently 2048 in genome) truncating the output.
- Required action: inspect `scripts/propose_mutation.py` prompt construction, consider prompt
  adjustment or output token limit increase.
- **Requires Project Owner approval** before any `scripts/**` or `core/**` change.

### Option B — Controlled rerun after diagnosis

- If the prompt issue is identified and corrected, a new `workflow_dispatch` with
  `mode=gemini-paid-credit` may be appropriate.
- Budget consumed so far: ~0.076 USD (3 × 0.025336 USD) from June 2026 budget.
- Remaining June 2026 budget: ~9.924 USD (monthly limit 10.0 USD).
- **This is a new paid-credit run decision — out of scope for this inventory task.**

### Option C — Accept current state as-is and close Phase 3 first iteration

- No valid candidate was produced. Promotion cannot proceed.
- The project remains at generation 2 with `best_score=729.34`.
- Further runs require diagnosis of the syntax error root cause.

**Immediate next step recommended**: Option A — root cause investigation of the prompt /
output validation failure before any new run.

---

## 13. Explicit Non-Goals

This inventory task did NOT and must NOT do the following:

- Run `workflow_dispatch`
- Call the Gemini API
- Trigger any GitHub Actions run or re-run
- Edit `data/api_usage_ledger.json`
- Edit `data/genome.json`
- Edit `core/**`
- Edit `.github/**`
- Edit `scripts/**`
- Edit `tests/**`
- Set `promote_approved=true`
- Promote any candidate
- Clean up README historical stale wording
- Infer candidate/evaluate/promotion results not supported by source evidence

---

## 14. Source Evidence Checklist

| Source | Checked | Finding |
|---|---|---|
| `git log --oneline -5` | ✅ | Latest commit = `ab1101a` (PR #81 merge) |
| `git branch --show-current` | ✅ | `claude/paid-credit-result-inventory-Tuy8P` |
| PR #79 via GitHub API | ✅ | closed/merged 2026-06-08T04:17:50Z |
| PR #80 via GitHub API | ✅ | closed/merged 2026-06-08T05:51:43Z |
| PR #81 via GitHub API | ✅ | closed/merged 2026-06-08T06:12:43Z |
| Open PRs | ✅ | 0 open PRs |
| README status block | ✅ | Phase 3 paid-credit success records exist; post-run result review pending |
| `data/api_usage_ledger.json` | ✅ | 7 records; 3 primary success records confirmed |
| `data/genome.json` | ✅ | api_mode=gemini_paid_credit, model=gemini-3-flash-preview, live_model_enabled=true |
| workflow_dispatch runs (GitHub Actions) | ✅ | 16 total; 3 runs match ledger timestamps |
| Run 26919888348 jobs | ✅ | Propose=success, Persist=success, Evaluate=SKIPPED, Finalize=FAILURE, Promote=SKIPPED |
| Run 26922191264 jobs | ✅ | identical job structure |
| Run 26924388218 jobs | ✅ | identical job structure |
| Run 26919888348 propose job log | ✅ | propose_mutation.py error: Python syntax invalid |
| Run 26922191264 propose job log | ✅ | identical error |
| Run 26924388218 propose job log | ✅ | identical error |
| Run 26919888348 finalize log | ✅ | PROPOSE_FAILED=true, PERSIST_RESULT=success |
| Artifacts (all 3 runs) | ✅ | api-usage-ledger only; all expired; no mutation-patch/candidate/fitness |
| `.github/workflows/immunization_loop.yml` | ✅ | Job structure, artifact names, skip conditions confirmed |
| `pytest tests/ -x -q` | ✅ | 1882 passed |
