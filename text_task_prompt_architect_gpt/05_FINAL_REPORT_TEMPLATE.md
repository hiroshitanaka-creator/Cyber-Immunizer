# 05_FINAL_REPORT_TEMPLATE.md

# Final Report Template

## 0. Purpose

このテンプレートは、Codex / Claude / GPT Agent / その他AI実行者がタスク完了時に提出する最終報告の標準形式です。

目的は、作業完了の主張を、第三者が検証できる証跡付きの報告に変換することです。

最終報告は、成果アピールではありません。  
最終報告は、作業結果、検証結果、未解決リスク、merge readinessを判断するための監査資料です。

---

## 1. Required Status Values

最終報告のステータスは、以下のいずれかに限定します。

| Status | Meaning |
|---|---|
| COMPLETE | 必須作業が完了し、必須検証が通過し、重大な未解決リスクがない |
| COMPLETE WITH RISKS | 作業は完了したが、CI未確認・一部検証不能・軽微リスクなどが残る |
| BLOCKED | 安全または正確に進めるための情報・権限・成果物が不足している |
| FAILED | 作業を試みたが、要求された状態に到達できなかった |

`COMPLETE` を使う条件は厳格です。  
CIが必要なタスクでCI未確認の場合、原則として `COMPLETE WITH RISKS` または `BLOCKED` にします。

---

## 2. Final Report Template

```markdown
# Final Report: PLACEHOLDER_TASK_TITLE

## 0. Final Status

Status: COMPLETE / COMPLETE WITH RISKS / BLOCKED / FAILED

One-sentence summary:

PLACEHOLDER_ONE_SENTENCE_SUMMARY

---

## 1. Executive Summary

### What was requested

PLACEHOLDER_REQUEST_SUMMARY

### What was done

PLACEHOLDER_COMPLETED_WORK_SUMMARY

### What was not done

PLACEHOLDER_NOT_DONE_OR_NOT_APPLICABLE

### Why the final status is justified

PLACEHOLDER_STATUS_JUSTIFICATION

---

## 2. Repository State

| Item | Value |
|---|---|
| Repository | PLACEHOLDER_REPOSITORY_URL |
| Base branch | PLACEHOLDER_BASE_BRANCH |
| Working branch | PLACEHOLDER_WORKING_BRANCH |
| Pull request | PLACEHOLDER_PR_URL_OR_NONE |
| Starting commit | PLACEHOLDER_STARTING_SHA_OR_UNKNOWN |
| Final commit | PLACEHOLDER_FINAL_SHA_OR_UNKNOWN |
| CI status | PASS / FAIL / PENDING / UNKNOWN / NOT APPLICABLE |

---

## 3. Scope Compliance

### Allowed scope

| Allowed path | Touched? | Notes |
|---|---:|---|
| PLACEHOLDER_ALLOWED_PATH | Yes / No | PLACEHOLDER |

### Forbidden scope

| Forbidden path | Touched? | Notes |
|---|---:|---|
| PLACEHOLDER_FORBIDDEN_PATH | Yes / No | PLACEHOLDER |

### Scope statement

- Unrelated refactors: Yes / No
- Unrelated formatting changes: Yes / No
- Dependency changes: Yes / No
- Workflow changes: Yes / No
- Security boundary changes: Yes / No

If any answer above is `Yes`, explain why it was necessary and authorized.

---

## 4. Changed Files

| File | Change Type | Purpose | Risk |
|---|---|---|---|
| PLACEHOLDER_FILE | Added / Modified / Deleted | PLACEHOLDER | Low / Medium / High |

### Diff Summary

```text
PLACEHOLDER_GIT_DIFF_STAT_OR_SUMMARY
```

---

## 5. Work Completed

### Completed item 1: PLACEHOLDER

- What changed:
- Why it changed:
- Evidence:
- Related files:

### Completed item 2: PLACEHOLDER

- What changed:
- Why it changed:
- Evidence:
- Related files:

### Completed item 3: PLACEHOLDER

- What changed:
- Why it changed:
- Evidence:
- Related files:

---

## 6. Tests and Validation

### Commands Run

| Command | Result | Notes |
|---|---|---|
| `PLACEHOLDER_COMMAND` | PASS / FAIL / NOT RUN | PLACEHOLDER |

### Required Checks

| Check | Required? | Result | Evidence |
|---|---:|---|---|
| Unit tests | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Integration tests | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Regression tests | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Negative tests | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Lint | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Type check | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Format check | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| JSON/YAML validation | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| Docker/sandbox validation | Yes / No | PASS / FAIL / NOT RUN | PLACEHOLDER |
| CI status | Yes / No | PASS / FAIL / PENDING / UNKNOWN | PLACEHOLDER |

### Failed or Not Run Checks

For each failed or not-run check:

#### Check: PLACEHOLDER

- Required by task: Yes / No
- Reason:
- Impact:
- Related to this change: Yes / No / Unknown
- Follow-up required:

---

## 7. CI Evidence

If CI exists or is required, include this section.

| Workflow | Run ID / URL | Commit | Status | Notes |
|---|---|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | PASS / FAIL / PENDING / UNKNOWN | PLACEHOLDER |

### Failed Jobs

| Job | Step | Failure Summary | Related to Task? |
|---|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | Yes / No / Unknown |

If CI could not be checked, state:

```text
CI could not be verified. Merge readiness cannot be fully claimed.
```

---

## 8. Evidence

### Files Inspected

| File | Reason |
|---|---|
| PLACEHOLDER_FILE | PLACEHOLDER_REASON |

### Important Evidence

- PLACEHOLDER_EVIDENCE_1
- PLACEHOLDER_EVIDENCE_2
- PLACEHOLDER_EVIDENCE_3

### Before / After Behavior

| Behavior | Before | After | Evidence |
|---|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | PLACEHOLDER |

---

## 9. Security and Safety Assessment

| Question | Answer | Notes |
|---|---|---|
| Were security checks weakened? | Yes / No | PLACEHOLDER |
| Was fail-closed behavior preserved? | Yes / No / N/A | PLACEHOLDER |
| Were secrets or credentials used? | Yes / No | PLACEHOLDER |
| Were logs checked for sensitive leakage? | Yes / No / N/A | PLACEHOLDER |
| Was network behavior added or changed? | Yes / No | PLACEHOLDER |
| Was subprocess, filesystem, Docker, or sandbox behavior changed? | Yes / No | PLACEHOLDER |
| Were permissions broadened? | Yes / No | PLACEHOLDER |

### Security Impact Summary

PLACEHOLDER_SECURITY_IMPACT_SUMMARY

---

## 10. Documentation Assessment

| Documentation Item | Required? | Updated? | Notes |
|---|---:|---:|---|
| README | Yes / No | Yes / No / N/A | PLACEHOLDER |
| docs/ | Yes / No | Yes / No / N/A | PLACEHOLDER |
| Task report | Yes / No | Yes / No / N/A | PLACEHOLDER |
| PR description | Yes / No | Yes / No / N/A | PLACEHOLDER |

### Documentation Consistency Statement

PLACEHOLDER_DOC_CONSISTENCY_STATEMENT

---

## 11. Risk Assessment

### Remaining Risks

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| PLACEHOLDER_RISK | Low / Medium / High | Low / Medium / High | PLACEHOLDER |

### Regression Risk

PLACEHOLDER_REGRESSION_RISK

### Operational Risk

PLACEHOLDER_OPERATIONAL_RISK

### Security Risk

PLACEHOLDER_SECURITY_RISK

### Cost / API Risk

PLACEHOLDER_COST_API_RISK

---

## 12. Deviations from Original Task

List any deviations.

| Deviation | Reason | Impact | Approved? |
|---|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | Yes / No / N/A |

If there were no deviations:

```text
No deviations from the requested scope.
```

---

## 13. Stop Conditions Encountered

| Stop Condition | Encountered? | Resolution |
|---|---:|---|
| Required file missing | Yes / No | PLACEHOLDER |
| Required validation unavailable | Yes / No | PLACEHOLDER |
| Scope expansion required | Yes / No | PLACEHOLDER |
| Security boundary unclear | Yes / No | PLACEHOLDER |
| CI unavailable | Yes / No | PLACEHOLDER |
| Repository state mismatch | Yes / No | PLACEHOLDER |

If any stop condition was encountered and work continued, explain why continuing was safe.

---

## 14. Merge Readiness

Choose one:

- Merge ready
- Not merge ready
- Cannot determine

### Merge Readiness Rationale

PLACEHOLDER_MERGE_READINESS_RATIONALE

### Required Before Merge

- PLACEHOLDER_REQUIRED_BEFORE_MERGE_1
- PLACEHOLDER_REQUIRED_BEFORE_MERGE_2

If no action is required:

```text
No additional required action identified before merge.
```

---

## 15. Follow-Up Recommendations

These are not part of the completed task unless explicitly stated.

| Priority | Recommendation | Reason |
|---|---|---|
| P1 | PLACEHOLDER | PLACEHOLDER |
| P2 | PLACEHOLDER | PLACEHOLDER |
| P3 | PLACEHOLDER | PLACEHOLDER |

---

## 16. Final Self-Audit

Before submitting this report, confirm:

- [ ] I inspected the final diff.
- [ ] I stayed within allowed scope.
- [ ] I did not make unrelated refactors.
- [ ] I did not weaken security checks.
- [ ] I did not remove or weaken tests.
- [ ] I ran required validations or documented why not.
- [ ] I checked CI or documented why not.
- [ ] I provided evidence for completion.
- [ ] I documented remaining risks.
- [ ] I used the correct final status.

---

## 17. Final Statement

PLACEHOLDER_FINAL_STATEMENT
```

---

## 3. Compact Final Report Template

Use this for small tasks only.

```markdown
# Final Report: PLACEHOLDER

Status: COMPLETE / COMPLETE WITH RISKS / BLOCKED / FAILED

## Summary

PLACEHOLDER

## Changed Files

| File | Purpose |
|---|---|
| PLACEHOLDER | PLACEHOLDER |

## Validation

| Command | Result |
|---|---|
| PLACEHOLDER | PASS / FAIL / NOT RUN |

## Evidence

- PLACEHOLDER
- PLACEHOLDER

## Risks

- PLACEHOLDER

## CI

PASS / FAIL / PENDING / UNKNOWN / NOT APPLICABLE

## Final Status Rationale

PLACEHOLDER
```

---

## 4. Status Selection Rules

### Use COMPLETE only when:

- Required work is done.
- Required tests pass.
- Required CI is passing or not applicable.
- No forbidden changes were made.
- No significant unresolved risk remains.
- Final evidence is sufficient.

### Use COMPLETE WITH RISKS when:

- Work is mostly done.
- Some non-critical validation could not be run.
- CI is pending or unavailable.
- Remaining risks are known and documented.
- Human review is still needed before merge.

### Use BLOCKED when:

- Required information is missing.
- Required files or artifacts are unavailable.
- Required validation cannot be performed.
- Security boundary is unclear.
- Required permission is missing.
- Continuing would require unsafe assumptions.

### Use FAILED when:

- The task was attempted.
- The requested end state was not achieved.
- Tests fail due to the attempted changes.
- The implementation approach did not work.
- The task needs redesign.

---

## 5. Evidence Standards

A final report is insufficient if it contains only claims.

Bad:

```text
Tests passed.
```

Good:

```text
Ran `python -m pytest tests/test_candidate_contract.py`; result: 18 passed in 1.42s.
```

Bad:

```text
CI looks fine.
```

Good:

```text
GitHub Actions workflow `ci.yml` on commit `abc123` completed successfully. No failed jobs observed.
```

Bad:

```text
No security issue.
```

Good:

```text
No workflow permissions were changed, no network calls were added, fail-closed validation path remains unchanged, and negative test `test_rejects_missing_attestation` passes.
```

---

## 6. Notes for Task Prompt Architect GPT

When requesting a final report from an AI agent:

- Require exact commands.
- Require command results.
- Require changed files table.
- Require CI status.
- Require remaining risks.
- Require final status taxonomy.
- Do not allow vague completion claims.
- Do not allow merge readiness claims without CI evidence.
- Do not allow security claims without file-level or behavior-level evidence.
