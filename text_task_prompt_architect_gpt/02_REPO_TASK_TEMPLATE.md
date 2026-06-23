# 02_REPO_TASK_TEMPLATE.md

# Repository Task Prompt Template

## 0. Purpose

このテンプレートは、GitHubリポジトリに対する実装、修正、調査、ドキュメント更新、CI改善、セキュリティ境界強化タスクをAI実行者に依頼するための標準テンプレートです。

このテンプレートの目的は、実行者の自由度を必要十分に制御し、成果物の合否を第三者が判定できる状態にすることです。

---

## 1. Usage

以下のテンプレートをコピーし、`PLACEHOLDER` を具体値に置き換えて使用してください。

不明な値は推測せず、以下の形式で残してください。

```text
UNKNOWN — verify before editing.
```

---

## 2. Repository Task Prompt

```markdown
# Task: PLACEHOLDER_TASK_TITLE

## 0. Mission

Your mission is to PLACEHOLDER_MISSION.

This task exists because PLACEHOLDER_REASON.

The desired end state is:

- PLACEHOLDER_DESIRED_END_STATE_1
- PLACEHOLDER_DESIRED_END_STATE_2
- PLACEHOLDER_DESIRED_END_STATE_3

Do not optimize for appearing productive.  
Optimize for correctness, evidence, and a reviewable final state.

---

## 1. Target

- Repository: PLACEHOLDER_REPOSITORY_URL
- Base branch: PLACEHOLDER_BASE_BRANCH
- Working branch: PLACEHOLDER_WORKING_BRANCH
- Pull request: PLACEHOLDER_PR_URL_OR_NONE
- Related issue: PLACEHOLDER_ISSUE_URL_OR_NONE
- Current known commit SHA: PLACEHOLDER_COMMIT_SHA_OR_UNKNOWN
- Primary task type:
  - [ ] Implementation
  - [ ] Bug fix
  - [ ] Security hardening
  - [ ] CI/workflow update
  - [ ] Documentation update
  - [ ] Test improvement
  - [ ] Audit / investigation
  - [ ] Refactor with explicit scope
- Relevant files:
  - PLACEHOLDER_FILE_1
  - PLACEHOLDER_FILE_2
- Out-of-scope files:
  - PLACEHOLDER_FORBIDDEN_FILE_OR_DIR_1
  - PLACEHOLDER_FORBIDDEN_FILE_OR_DIR_2

If any target field is unknown, verify it before editing.  
If it cannot be verified, stop and report BLOCKED.

---

## 2. Current Facts and Assumptions

### Verified Facts

- PLACEHOLDER_VERIFIED_FACT_1
- PLACEHOLDER_VERIFIED_FACT_2
- PLACEHOLDER_VERIFIED_FACT_3

### Assumptions

The following assumptions are allowed only until contradicted by repository evidence:

- PLACEHOLDER_ASSUMPTION_1
- PLACEHOLDER_ASSUMPTION_2

If an assumption is contradicted by the repository, do not continue silently.  
Update the plan and report the contradiction.

---

## 3. Non-Negotiable Rules

You must obey all of the following rules.

### Scope Rules

- Do not make unrelated refactors.
- Do not reformat unrelated files.
- Do not modify files outside the allowed scope.
- Do not rename public APIs unless explicitly required.
- Do not change behavior outside the stated mission.
- Do not introduce broad cleanup commits.

### Security Rules

- Do not weaken existing security checks.
- Do not bypass fail-closed behavior.
- Do not introduce unsafe defaults.
- Do not log secrets, tokens, credentials, or private keys.
- Do not require production credentials.
- Do not add network access unless explicitly allowed.
- Do not implement real-world offensive behavior.

### Test and CI Rules

- Do not remove failing tests to make CI pass.
- Do not skip tests unless the reason is documented and justified.
- Do not claim success without command output.
- Do not treat local success as CI success unless CI was checked.
- Do not ignore failing CI if it is related to the task.

### Dependency Rules

- Do not add dependencies unless explicitly required.
- Do not upgrade dependencies silently.
- Do not change lock files unless dependency changes are explicitly in scope.

### Documentation Rules

- Do not claim a feature is implemented unless implementation and tests support it.
- Do not add unsupported roadmap promises.
- Do not use vague claims such as "fully secure", "complete protection", or "guaranteed safe".

---

## 4. Required Reconnaissance

Before editing, inspect the repository context.

You must read and use evidence from:

- README.md
- Relevant files under docs/
- Relevant implementation files
- Relevant test files
- Relevant CI/workflow files, if this task affects CI or automation
- Previous task report, if available
- PR comments or review comments, if this task is tied to a PR

Minimum reconnaissance checklist:

- [ ] Confirm repository and branch.
- [ ] Confirm the current implementation.
- [ ] Confirm existing tests.
- [ ] Confirm documentation impact.
- [ ] Confirm CI/workflow impact.
- [ ] Confirm allowed and forbidden files.
- [ ] Identify existing conventions before adding new patterns.

Final report must list the files inspected.

---

## 5. Required Work

Complete the following work in order.

### Step 1: Repository State Verification

- Confirm the current branch.
- Confirm the base branch.
- Confirm the working tree state.
- Confirm whether the target PR exists.
- Confirm whether CI status is relevant.

If the repository state cannot be verified, stop and report BLOCKED.

### Step 2: Problem Confirmation

Verify that the stated problem actually exists.

Evidence required:

- File path
- Relevant function, class, workflow, or document section
- Current behavior
- Why current behavior is insufficient

Do not implement a fix for an unverified problem unless the task is explicitly exploratory.

### Step 3: Implementation or Update

Perform only the required changes.

Required changes:

- PLACEHOLDER_REQUIRED_CHANGE_1
- PLACEHOLDER_REQUIRED_CHANGE_2
- PLACEHOLDER_REQUIRED_CHANGE_3

Preserve:

- PLACEHOLDER_BEHAVIOR_TO_PRESERVE_1
- PLACEHOLDER_BEHAVIOR_TO_PRESERVE_2

### Step 4: Tests

Add or update tests that prove the required behavior.

Required test coverage:

- Positive case: PLACEHOLDER_POSITIVE_CASE
- Negative case: PLACEHOLDER_NEGATIVE_CASE
- Regression case: PLACEHOLDER_REGRESSION_CASE
- Edge case: PLACEHOLDER_EDGE_CASE

Tests must fail on the old behavior and pass on the new behavior where practical.

### Step 5: Documentation

Update documentation only where necessary.

Required documentation updates:

- PLACEHOLDER_DOC_UPDATE_1
- PLACEHOLDER_DOC_UPDATE_2

Documentation must match implementation.  
Do not document future behavior as current behavior.

### Step 6: Task Report

Create or update a task report if the repository convention requires it.

Suggested path:

```text
docs/task_reports/PLACEHOLDER_DATE-PLACEHOLDER_TASK_SLUG.md
```

The task report must include:

- Summary
- Changed files
- Validation commands
- Test results
- Remaining risks
- CI status, if available

---

## 6. Allowed Changes

You may edit only the following files or directories:

- PLACEHOLDER_ALLOWED_PATH_1
- PLACEHOLDER_ALLOWED_PATH_2
- PLACEHOLDER_ALLOWED_PATH_3

You may create the following files if needed:

- PLACEHOLDER_ALLOWED_NEW_FILE_1
- PLACEHOLDER_ALLOWED_NEW_FILE_2

If the necessary fix requires editing outside this list, stop and report the required scope expansion.

---

## 7. Forbidden Changes

You must not edit:

- PLACEHOLDER_FORBIDDEN_PATH_1
- PLACEHOLDER_FORBIDDEN_PATH_2
- PLACEHOLDER_FORBIDDEN_PATH_3

Default forbidden changes unless explicitly allowed:

- `.github/workflows/**`
- Dependency lock files
- Generated files
- Secrets or credential files
- Unrelated documentation
- Unrelated formatting
- Public API surfaces outside the stated scope
- Security policy files outside the stated scope

---

## 8. Validation Requirements

Run all applicable validations.

### Required Commands

```bash
PLACEHOLDER_COMMAND_1
PLACEHOLDER_COMMAND_2
PLACEHOLDER_COMMAND_3
```

### Recommended Commands

```bash
git diff --check
PLACEHOLDER_RECOMMENDED_COMMAND_1
PLACEHOLDER_RECOMMENDED_COMMAND_2
```

### Validation Rules

- Each required command must pass.
- If a required command cannot be run, document the exact reason.
- If a command fails, determine whether the failure is related to this task.
- Do not claim COMPLETE if required validation failed.
- If CI exists, check CI status or document why CI could not be checked.

### Special Validation Cases

If this task touches JSON:

- Validate JSON syntax.
- Validate schema if schema exists.

If this task touches YAML:

- Validate YAML parse.
- Confirm indentation and keys.

If this task touches Docker:

- Confirm image references.
- Confirm deterministic or pinned behavior if required.
- Confirm sandbox assumptions are documented.

If this task touches CI:

- Confirm workflow syntax.
- Confirm permissions.
- Confirm triggers.
- Confirm artifact flow.
- Confirm no unnecessary write permissions were added.

If this task touches security boundary:

- Add negative tests.
- Confirm fail-closed behavior.
- Confirm bypass paths are rejected.
- Confirm logs do not leak sensitive data.

---

## 9. Evidence Requirements

The final report must include:

### Repository Evidence

- Current branch
- Base branch
- Commit SHA
- Changed file list
- Diff summary

### Implementation Evidence

- Files inspected
- Files changed
- Important functions or sections changed
- Before/after behavior

### Validation Evidence

- Exact commands run
- Command results
- Test summary
- CI status or reason CI was not checked

### Safety Evidence

- Confirmation that forbidden files were not changed
- Confirmation that security checks were not weakened
- Confirmation that no secrets or credentials were used
- Confirmation that no out-of-scope behavior was added

---

## 10. Definition of Done

The task is complete only if:

- [ ] Repository target was verified.
- [ ] Relevant files were inspected.
- [ ] The stated problem was confirmed or disproven with evidence.
- [ ] Changes stayed within allowed scope.
- [ ] No forbidden files were changed.
- [ ] Security boundary was not weakened.
- [ ] Required implementation changes were completed.
- [ ] Required tests were added or updated.
- [ ] Required validation commands passed.
- [ ] Documentation was updated where necessary.
- [ ] Task report was created or updated if required.
- [ ] Final report includes all required evidence.
- [ ] Remaining risks are documented.

---

## 11. Stop Conditions

Stop and report BLOCKED if any of the following occurs:

- Repository or branch cannot be verified.
- Required files are missing.
- Required artifacts are unavailable.
- The issue cannot be reproduced or confirmed.
- The required fix needs forbidden files.
- Security boundary is unclear.
- Required validation cannot be run.
- CI cannot be checked and CI status is required.
- The task would require secrets, credentials, or production access.
- The task would require unsafe or unauthorized behavior.
- The repository state differs materially from the prompt assumptions.

When stopped, report:

- What was checked
- What failed
- Why continuing would be unsafe or invalid
- What human decision is required

---

## 12. Final Report Format

Use this exact final report format.

### Summary

Briefly state what was done and why.

### Repository State

| Item | Value |
|---|---|
| Repository | PLACEHOLDER |
| Branch | PLACEHOLDER |
| Base | PLACEHOLDER |
| Commit | PLACEHOLDER |
| PR | PLACEHOLDER |

### Changed Files

| File | Purpose | Notes |
|---|---|---|
| PLACEHOLDER | PLACEHOLDER | PLACEHOLDER |

### Files Inspected

| File | Reason |
|---|---|
| PLACEHOLDER | PLACEHOLDER |

### Validation

| Command | Result | Notes |
|---|---|---|
| PLACEHOLDER | PASS / FAIL / NOT RUN | PLACEHOLDER |

### Evidence

- PLACEHOLDER_EVIDENCE_1
- PLACEHOLDER_EVIDENCE_2
- PLACEHOLDER_EVIDENCE_3

### Risk Assessment

- Remaining risk:
- Regression risk:
- Security impact:
- CI impact:
- Follow-up needed:

### Final Status

Choose exactly one:

- COMPLETE
- COMPLETE WITH RISKS
- BLOCKED
- FAILED

---

## 13. Self-Audit Before Final Answer

Before producing the final report, answer internally:

- Did I stay within scope?
- Did I avoid unrelated refactors?
- Did I preserve security boundaries?
- Did I avoid dependency churn?
- Did I add or update tests?
- Did I run required checks?
- Did I inspect the final diff?
- Did I document unresolved risks?
- Can an external reviewer verify my claims?
```

---

## 3. Minimal Variant

Use this shorter variant only for low-risk tasks.

```markdown
# Task: PLACEHOLDER

## Mission
PLACEHOLDER

## Target
- Repo:
- Branch:
- PR:
- Files:

## Rules
- No unrelated refactors.
- No forbidden files.
- No security weakening.
- No test deletion.
- No unsupported claims.

## Required Work
1. PLACEHOLDER
2. PLACEHOLDER
3. PLACEHOLDER

## Allowed Changes
- PLACEHOLDER

## Forbidden Changes
- PLACEHOLDER

## Validation
- PLACEHOLDER_COMMAND

## Evidence
Final report must include changed files, commands run, test results, CI status if available, and remaining risks.

## DoD
- [ ] Work complete
- [ ] Tests pass
- [ ] No forbidden changes
- [ ] Evidence provided

## Stop Conditions
Stop if target branch, required files, required tests, or security boundary cannot be verified.
```

---

## 4. Notes for Task Prompt Architect GPT

When generating a repo task prompt:

- Prefer explicit constraints over broad freedom.
- Prefer concrete validation over general confidence.
- Prefer narrow allowed paths over broad repository access.
- Prefer fail-closed behavior for security-sensitive tasks.
- Prefer documenting uncertainty over inventing missing facts.
- Always include Stop Conditions.
- Always include Final Report Format.
