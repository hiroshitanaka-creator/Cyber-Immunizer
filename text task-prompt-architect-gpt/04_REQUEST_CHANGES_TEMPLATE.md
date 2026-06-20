# 04_REQUEST_CHANGES_TEMPLATE.md

# Request Changes Task Prompt Template

## 0. Purpose

このテンプレートは、PR監査で見つかった問題を、実行者が修正できる具体的なタスクプロンプトに変換するためのものです。

目的は、指摘を曖昧なレビューコメントで終わらせず、修正範囲、禁止事項、検証、証跡、完了条件を固定することです。

Request Changes用タスクプロンプトは、必ず狭く作ります。  
監査指摘の修正以外を許可してはいけません。

---

## 1. Core Rules

Request Changesタスクでは、以下を必ず守ります。

- 修正対象は監査指摘に限定する。
- unrelated refactorを禁止する。
- テスト削除を禁止する。
- セキュリティ境界の弱体化を禁止する。
- 既存の正常動作を壊さない。
- CIを確認する。
- 修正後に差分を自己監査する。
- 各指摘に対して、修正内容と検証方法を対応させる。

---

## 2. Request Changes Prompt

```markdown
# Request Changes Task: PLACEHOLDER_TITLE

## 0. Mission

Your mission is to fix the blocking audit findings in PLACEHOLDER_PR_URL without broadening the PR scope.

This is not a general cleanup task.  
This is a targeted repair task.

You must fix only the issues listed below, preserve existing behavior outside the findings, and provide evidence that each finding was resolved.

Final status must be one of:

- COMPLETE
- COMPLETE WITH RISKS
- BLOCKED
- FAILED

---

## 1. Target

- Repository: PLACEHOLDER_REPOSITORY_URL
- Pull Request: PLACEHOLDER_PR_URL
- PR number: PLACEHOLDER_PR_NUMBER
- Base branch: PLACEHOLDER_BASE_BRANCH
- Head branch: PLACEHOLDER_HEAD_BRANCH
- Current head SHA: PLACEHOLDER_HEAD_SHA_OR_UNKNOWN
- Audit source: PLACEHOLDER_AUDIT_SOURCE
- Related review comments: PLACEHOLDER_REVIEW_COMMENT_URLS_OR_NONE

If the PR head has changed since the audit, re-check the relevant diff before editing.

---

## 2. Findings to Fix

Fix only the following findings.

### Finding 1

- Severity: PLACEHOLDER_P0_P1_P2
- Category: PLACEHOLDER_CATEGORY
- File:
- Evidence:
- Problem:
- Required fix:
- Required verification:

### Finding 2

- Severity: PLACEHOLDER_P0_P1_P2
- Category: PLACEHOLDER_CATEGORY
- File:
- Evidence:
- Problem:
- Required fix:
- Required verification:

Do not introduce unrelated changes while fixing these findings.

---

## 3. Non-Negotiable Rules

### Scope Rules

- Do not make unrelated refactors.
- Do not reformat unrelated files.
- Do not rename unrelated symbols.
- Do not change behavior outside the audit findings.
- Do not edit files outside the allowed changes list unless you stop and report why scope expansion is required.

### Security Rules

- Do not weaken security checks.
- Do not replace fail-closed behavior with fail-open behavior.
- Do not suppress errors to make tests pass.
- Do not broaden allowlists without tests and justification.
- Do not expose secrets, tokens, credentials, or private data.
- Do not add real-world offensive behavior.

### Test Rules

- Do not remove tests.
- Do not weaken assertions.
- Do not mark tests as skipped unless the reason is explicit and justified.
- Add regression tests for each fixed finding where practical.
- Add negative tests for security-sensitive findings.

### CI Rules

- Do not claim merge readiness unless CI is checked.
- If CI is unavailable, report that explicitly.
- If CI fails, identify whether the failure is related to the PR.

---

## 4. Required Reconnaissance

Before editing, inspect:

- The current PR diff
- The files containing each finding
- Existing tests around the affected behavior
- Relevant docs, if documentation consistency was part of the finding
- CI status and failed jobs, if any
- Review comments and unresolved threads, if any

Final report must list what was inspected.

---

## 5. Required Work

Complete the following in order.

### Step 1: Confirm Findings Still Apply

For each finding:

- Re-read the current file.
- Confirm whether the issue still exists.
- If already fixed, record evidence and do not change that area unnecessarily.
- If the PR changed materially, adjust only as needed to resolve the original finding.

### Step 2: Implement Targeted Fixes

For each confirmed finding:

- Make the smallest safe change that resolves the issue.
- Preserve surrounding behavior.
- Preserve existing public interfaces unless the finding requires otherwise.
- Use existing project conventions.
- Avoid broad abstractions unless required.

### Step 3: Add or Update Tests

For each finding:

- Add a regression test.
- Add a negative test if the issue is security-sensitive.
- Update existing tests only if the expected behavior legitimately changed.
- Do not reduce test strictness.

### Step 4: Update Documentation

Update documentation only if:

- The finding involves stale or incorrect docs.
- The fix changes documented behavior.
- A task report is required by repository convention.

Do not add speculative roadmap claims.

### Step 5: Self-Inspect Diff

Before final report:

- Inspect the final diff.
- Confirm only allowed files changed.
- Confirm no unrelated formatting churn.
- Confirm each finding maps to a fix and validation.
- Confirm tests are not weakened.

---

## 6. Allowed Changes

You may edit only:

- PLACEHOLDER_ALLOWED_FILE_1
- PLACEHOLDER_ALLOWED_FILE_2
- PLACEHOLDER_ALLOWED_TEST_FILE_1
- PLACEHOLDER_ALLOWED_DOC_FILE_1

You may create only:

- PLACEHOLDER_ALLOWED_NEW_TEST_FILE
- PLACEHOLDER_ALLOWED_TASK_REPORT

If a necessary fix requires other files, stop and report BLOCKED with the required scope expansion.

---

## 7. Forbidden Changes

Do not edit:

- PLACEHOLDER_FORBIDDEN_FILE_OR_DIR_1
- PLACEHOLDER_FORBIDDEN_FILE_OR_DIR_2

Default forbidden changes:

- `.github/workflows/**` unless the finding explicitly targets workflow behavior
- Dependency files unless the finding explicitly requires dependency changes
- Generated files
- Secrets or credential files
- Unrelated docs
- Unrelated tests
- Unrelated formatting
- Public API surfaces not implicated by the finding

---

## 8. Validation Requirements

Run the narrowest meaningful tests first, then broader checks.

### Required Targeted Tests

```bash
PLACEHOLDER_TARGETED_TEST_COMMAND_1
PLACEHOLDER_TARGETED_TEST_COMMAND_2
```

### Required Broader Checks

```bash
PLACEHOLDER_BROADER_CHECK_COMMAND_1
PLACEHOLDER_BROADER_CHECK_COMMAND_2
```

### Required Diff Checks

```bash
git diff --check
git diff --stat
```

### CI Verification

If a PR exists:

- Check latest CI status.
- Record workflow names.
- Record failed jobs, if any.
- Record whether failures are related to this repair.

If CI cannot be checked, final status cannot be plain COMPLETE unless CI is explicitly out of scope.

---

## 9. Evidence Requirements

Final report must include a finding-by-finding resolution table.

| Finding | Fix | Test / Verification | Evidence | Status |
|---|---|---|---|---|
| Finding 1 | PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | Fixed / Not applicable / Blocked |
| Finding 2 | PLACEHOLDER | PLACEHOLDER | PLACEHOLDER | Fixed / Not applicable / Blocked |

Also include:

- Changed files
- Commands run
- Test results
- CI status
- Diff summary
- Remaining risks
- Confirmation of no forbidden changes

---

## 10. Definition of Done

The task is complete only if:

- [ ] Each listed finding was re-checked.
- [ ] Each still-valid finding was fixed.
- [ ] No unrelated changes were made.
- [ ] No forbidden files were edited.
- [ ] Security boundary was not weakened.
- [ ] Tests were added or updated for each finding where practical.
- [ ] Required validation commands passed.
- [ ] CI status was checked or inability was documented.
- [ ] Final diff was inspected.
- [ ] Final report maps each finding to fix and verification.
- [ ] Remaining risks are documented.

---

## 11. Stop Conditions

Stop and report BLOCKED if:

- PR cannot be accessed.
- PR head changed so much that the audit findings cannot be mapped safely.
- A required file is missing.
- The fix requires forbidden files.
- The fix requires a broader architectural decision.
- Required tests cannot be run.
- CI failure cannot be distinguished from task-related failure.
- A security boundary is unclear.
- Fixing one finding would contradict another requirement.
- The requested change would require unsafe, unauthorized, or secret-dependent behavior.

BLOCKED report must include:

- What was checked
- Which finding is blocked
- Why it is blocked
- What decision or artifact is required

---

## 12. Final Report Format

Use this exact format.

### Summary

State what findings were fixed.

### Finding Resolution

| Finding | Status | Fix | Verification |
|---|---|---|---|
| PLACEHOLDER | Fixed / Not applicable / Blocked | PLACEHOLDER | PLACEHOLDER |

### Changed Files

| File | Purpose | Finding |
|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER |

### Validation

| Command | Result | Notes |
|---|---|---|
| PLACEHOLDER | PASS / FAIL / NOT RUN | PLACEHOLDER |

### CI Status

| Workflow | Status | Notes |
|---|---|---|
| PLACEHOLDER | PASS / FAIL / PENDING / UNKNOWN | PLACEHOLDER |

### Diff Self-Inspection

- Unrelated refactors: None / Present
- Forbidden files changed: No / Yes
- Tests weakened: No / Yes
- Security boundary weakened: No / Yes
- Docs consistent: Yes / No / Not applicable

### Remaining Risks

- PLACEHOLDER_RISK_1
- PLACEHOLDER_RISK_2

### Final Status

Choose exactly one:

- COMPLETE
- COMPLETE WITH RISKS
- BLOCKED
- FAILED
```

---

## 3. Compact Request Changes Prompt

Use this for simple review repairs.

```markdown
# Request Changes Repair Task

Fix only the blocking review findings in:

- Repository:
- PR:
- Base:
- Head:

Findings to fix:
1. PLACEHOLDER
2. PLACEHOLDER

Rules:
- No unrelated refactors.
- No forbidden files.
- No test deletion.
- No security weakening.
- No broad cleanup.
- No unsupported docs.

Allowed files:
- PLACEHOLDER

Forbidden files:
- PLACEHOLDER

Required:
- Confirm each finding still applies.
- Fix each finding narrowly.
- Add/update tests.
- Run targeted tests.
- Run git diff --check.
- Check CI if available.
- Report changed files, commands, results, CI, and remaining risks.

Stop if:
- Fix requires forbidden files.
- PR state changed materially.
- Required validation cannot be run.
- Security boundary is unclear.
```

---

## 4. Request Changes Review Comment Template

Use this when writing a concise GitHub review comment.

```markdown
REQUEST CHANGES

This PR should not be merged until the following issues are fixed.

### Blocking findings

1. **PLACEHOLDER_FINDING_TITLE**
   - Severity:
   - Evidence:
   - Problem:
   - Required fix:
   - Required verification:

2. **PLACEHOLDER_FINDING_TITLE**
   - Severity:
   - Evidence:
   - Problem:
   - Required fix:
   - Required verification:

### Required repair constraints

- Fix only the findings above.
- Do not make unrelated refactors.
- Do not weaken tests or security checks.
- Add regression/negative tests where applicable.
- Re-run targeted tests and CI.
- Provide a final report mapping each finding to its fix and verification.
```

---

## 5. Notes for Task Prompt Architect GPT

When generating Request Changes prompts:

- Be narrow.
- Do not let the repair task become a redesign.
- Tie each change to an audit finding.
- Require tests for each finding.
- Require CI status.
- Require diff self-inspection.
- Include Stop Conditions.
- Include final status taxonomy.
