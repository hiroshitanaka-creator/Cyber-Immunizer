# 03_PR_AUDIT_TEMPLATE.md

# Pull Request Audit Prompt Template

## 0. Purpose

このテンプレートは、GitHub Pull Requestを厳格に監査するための標準プロンプトです。

目的は、PRを機械的に承認することではありません。  
目的は、PRの主張、実装、テスト、CI、ドキュメント、セキュリティ境界、プロジェクトゴールとの整合性を一次証拠で検証し、mergeしてよいかを判断することです。

---

## 1. Audit Principles

PR監査では、以下を絶対に守ります。

- PR diffだけで判断しない。
- PR descriptionの主張を鵜呑みにしない。
- Bot reviewやCodex Reviewを無視しない。
- CI statusを確認する。
- Relevant source filesを読む。
- Relevant testsを読む。
- Relevant docsを読む。
- Workflowやpermissionに影響する場合は `.github/workflows/**` を確認する。
- 各技術的主張に証拠を付ける。
- 不明なことは不明と書く。
- 最終判定は `APPROVE` / `REQUEST CHANGES` / `BLOCKED` のいずれかにする。

---

## 2. PR Audit Prompt

```markdown
# PR Audit: PLACEHOLDER_PR_TITLE_OR_NUMBER

## 0. Mission

You are performing a strict, evidence-based audit of this pull request.

Your job is not to approve the PR quickly.  
Your job is to determine whether this PR safely and correctly advances the project toward its stated goal.

You must verify the PR claims against actual repository evidence.

Final verdict must be exactly one of:

- APPROVE
- REQUEST CHANGES
- BLOCKED

---

## 1. Target

- Repository: PLACEHOLDER_REPOSITORY_URL
- Pull Request: PLACEHOLDER_PR_URL
- PR number: PLACEHOLDER_PR_NUMBER
- Base branch: PLACEHOLDER_BASE_BRANCH
- Head branch: PLACEHOLDER_HEAD_BRANCH
- Claimed purpose: PLACEHOLDER_CLAIMED_PURPOSE
- Project goal: PLACEHOLDER_PROJECT_GOAL

If any field is unknown, verify it before making a final judgment.

---

## 2. Mandatory Audit Scope

You must inspect all applicable sources.

### Pull Request Metadata

- PR title
- PR description
- PR changed files
- PR commits
- PR discussion
- Inline review comments
- Review submissions
- Bot review comments
- Codex Review comments, if present
- CI/check status

### Repository Context

Read and use evidence from:

- README.md
- Relevant docs under docs/
- Relevant source files
- Relevant tests
- Relevant workflows, if CI or automation is affected
- Relevant task reports, if present
- Configuration files affected by the PR

Do not audit the diff only.

---

## 3. Required Audit Questions

Answer each question with evidence.

### A. Scope and Intent

- What does the PR claim to do?
- What files does it actually change?
- Are the changed files consistent with the stated purpose?
- Are there unrelated changes?
- Is the PR too broad for safe review?

### B. Architecture

- Does the PR preserve the intended architecture?
- Does it introduce hidden coupling?
- Does it bypass an existing abstraction or contract?
- Does it create a new source of truth conflict?
- Does it align with the project’s stated goal?

### C. Security Boundary

- Does the PR weaken any security checks?
- Does it change fail-closed behavior?
- Does it broaden permissions?
- Does it introduce new network, filesystem, subprocess, sandbox, or credential behavior?
- Does it leak sensitive information into logs, reports, artifacts, or docs?
- Does it introduce unsafe defaults?

### D. Fitness and Regression

- Are tests sufficient for the claimed behavior?
- Are there negative tests?
- Are there regression tests?
- Do tests prove the bug cannot recur?
- Could existing behavior regress silently?
- Are tests deterministic?
- Do tests depend on external services unnecessarily?

### E. CI and Workflow Safety

- Are CI changes necessary?
- Are workflow permissions minimal?
- Are artifacts handled safely?
- Are promotion/deployment/write steps protected?
- Are jobs ordered correctly?
- Are skipped jobs safe and intentional?
- Are matrix or environment changes justified?

### F. Cost and API Governance

- Does the PR increase paid API usage?
- Are cost controls preserved?
- Are external model calls gated?
- Are secrets handled safely?
- Are dry-run or no-API paths preserved?

### G. Audit Evidence and Documentation

- Does the PR update docs where necessary?
- Are docs consistent with implementation?
- Does the PR description overclaim?
- Is there a task report?
- Are limitations and remaining risks documented?

### H. Merge Readiness

- Is CI passing?
- Are required reviews resolved?
- Are blocking review comments addressed?
- Are there unresolved risks?
- Would merging this PR make future work safer or harder?

---

## 4. Severity Definitions

Use the following severity levels.

### P0 — Critical Blocker

Must not merge.

Examples:

- Security boundary weakened
- CI/promotion bypass
- Secret exposure
- Data loss risk
- Dangerous behavior enabled
- Tests removed to hide failure
- PR cannot be validated

### P1 — Blocking Defect

Must be fixed before merge.

Examples:

- Claimed behavior not implemented
- Missing negative tests for security-sensitive behavior
- Regression risk with no test coverage
- Docs contradict implementation
- CI failure related to PR
- Incorrect artifact or workflow handling

### P2 — Important Non-Blocking or Context-Dependent

Should be fixed before merge unless explicitly accepted.

Examples:

- Incomplete docs
- Weak test coverage for edge cases
- Ambiguous error message
- Minor architecture debt
- Missing task report detail

### P3 — Minor

Can be follow-up.

Examples:

- Typo
- Formatting issue
- Small naming inconsistency
- Minor comment improvement

---

## 5. Required Finding Format

Every finding must use this exact structure.

```markdown
### Finding P1: PLACEHOLDER_TITLE

- Severity: P0 / P1 / P2 / P3
- Status: Blocking / Non-blocking
- Category: Architecture / Security Boundary / Fitness & Regression / Cost & API Governance / Audit Evidence / Workflow Safety / Documentation
- Evidence:
  - File:
  - Line or diff hunk:
  - Quote:
- Problem:
- Impact:
- Required fix:
- Verification required:
```

Rules:

- Do not create findings without evidence.
- Do not cite broad impressions.
- Do not claim a file says something unless verified.
- If line numbers are unavailable, cite exact file path and exact snippet.
- If evidence cannot be obtained, mark the audit BLOCKED.

---

## 6. Required Output Format

Use this final audit format.

### 1. Executive Verdict

State exactly one:

- APPROVE
- REQUEST CHANGES
- BLOCKED

Then give a concise reason.

### 2. PR Summary

| Item | Value |
|---|---|
| Repository | PLACEHOLDER |
| PR | PLACEHOLDER |
| Base | PLACEHOLDER |
| Head | PLACEHOLDER |
| Changed files | PLACEHOLDER |
| CI status | PASS / FAIL / PENDING / UNKNOWN |
| Review status | PLACEHOLDER |

### 3. Evidence Inspected

List what was inspected.

| Source | Status | Notes |
|---|---|---|
| PR description | Inspected / Not available | PLACEHOLDER |
| PR diff | Inspected / Not available | PLACEHOLDER |
| Changed files | Inspected / Not available | PLACEHOLDER |
| README | Inspected / Not relevant | PLACEHOLDER |
| docs | Inspected / Not relevant | PLACEHOLDER |
| tests | Inspected / Not relevant | PLACEHOLDER |
| workflows | Inspected / Not relevant | PLACEHOLDER |
| CI | PASS / FAIL / PENDING / UNKNOWN | PLACEHOLDER |
| reviews/comments | Inspected / None / Unknown | PLACEHOLDER |

### 4. Findings

If no findings:

```markdown
No blocking findings were identified.
```

If findings exist, use the required finding format.

### 5. Positive Confirmations

List what was verified as correct.

Examples:

- Scope is limited to expected files.
- Tests cover the new behavior.
- CI is passing.
- No workflow permissions were broadened.
- Security boundary remains fail-closed.

### 6. Remaining Risks

List risks that remain even if the PR is mergeable.

- PLACEHOLDER_RISK_1
- PLACEHOLDER_RISK_2

### 7. Merge Recommendation

Choose exactly one:

- Merge recommended
- Do not merge until findings are fixed
- Cannot determine merge readiness

### 8. Request Changes Task Prompt

If verdict is REQUEST CHANGES, provide a copy-ready task prompt that fixes only the blocking issues.

If verdict is APPROVE, do not generate a large follow-up task unless useful.

If verdict is BLOCKED, state exactly what evidence is missing.

---

## 7. Required CI Review

The audit must determine CI status.

Required CI fields:

- Workflow name
- Run status
- Conclusion
- Commit SHA
- Failed job name, if any
- Failed step name, if any
- Whether failure is related to the PR

If CI cannot be checked, write:

```text
CI status could not be verified. This audit cannot claim merge readiness.
```

A PR with unknown CI may be APPROVE only if the user explicitly requested code-only review and merge readiness is not being judged. Otherwise, use BLOCKED or REQUEST CHANGES depending on context.

---

## 8. Required Review Comment Review

The audit must inspect review comments where available.

Check:

- Human review comments
- Bot review comments
- Codex Review comments
- Unresolved review threads
- Requested changes
- Dismissed reviews, if relevant

If review comments cannot be checked, state that explicitly.

Do not claim "all comments resolved" without evidence.

---

## 9. Request Changes Conversion Rules

If the audit result is REQUEST CHANGES, create a task prompt that:

- Targets only the identified findings
- Does not broaden scope
- Lists allowed files
- Lists forbidden files
- Requires tests
- Requires CI confirmation
- Requires final evidence
- Includes Stop Conditions
- Does not permit unrelated refactors

Use `04_REQUEST_CHANGES_TEMPLATE.md` as the preferred structure.

---

## 10. Approve Criteria

A PR may be APPROVED only if:

- PR purpose is clear.
- Changed files match the purpose.
- No blocking security issue exists.
- Required tests are present and meaningful.
- CI is passing or CI is explicitly out of scope and that limitation is stated.
- Docs are consistent with implementation where relevant.
- Review comments are resolved or non-blocking.
- Remaining risks are acceptable and documented.

---

## 11. Request Changes Criteria

Use REQUEST CHANGES if:

- Claimed behavior is not implemented.
- Tests are missing for critical behavior.
- Negative tests are missing for security-sensitive behavior.
- CI fails due to the PR.
- Docs contradict implementation.
- Security boundary is weakened.
- Workflow permissions are too broad.
- Promotion/deployment/evaluation gates can be bypassed.
- PR introduces unresolved regression risk.

---

## 12. Blocked Criteria

Use BLOCKED if:

- PR cannot be accessed.
- Diff cannot be inspected.
- Relevant files cannot be read.
- CI status is required but unavailable.
- Review comments are required but unavailable.
- Repository state is ambiguous.
- Evidence is insufficient to make a responsible judgment.

BLOCKED is not a failure of the PR.  
BLOCKED means the audit cannot responsibly conclude.

---

## 13. Self-Audit Checklist

Before finalizing the audit, verify:

- [ ] I did not rely on PR diff only.
- [ ] I checked PR claims against implementation.
- [ ] I checked tests.
- [ ] I checked docs where relevant.
- [ ] I checked CI or documented inability.
- [ ] I checked review comments or documented inability.
- [ ] I assigned severity to findings.
- [ ] I included evidence for every finding.
- [ ] I avoided unsupported claims.
- [ ] I used exactly one final verdict.
```

---

## 3. Minimal PR Audit Prompt

Use only for low-risk PRs.

```markdown
# PR Audit

Audit this PR using evidence, not assumptions.

- Repository:
- PR:
- Base:
- Head:

Required:
- Inspect PR description.
- Inspect changed files.
- Inspect relevant source/tests/docs.
- Check CI status.
- Check review comments if available.
- Do not rely on diff only.
- Do not approve if evidence is missing.

Output:
- Verdict: APPROVE / REQUEST CHANGES / BLOCKED
- Changed files summary
- CI status
- Findings with severity and evidence
- Remaining risks
- Merge recommendation
```

---

## 4. Notes for Task Prompt Architect GPT

When generating a PR audit prompt:

- Make the final verdict mandatory.
- Force CI verification.
- Force review comment verification.
- Force source/test/doc inspection.
- Require evidence for each finding.
- Require Request Changes task prompt if blocking issues exist.
- For security-sensitive repos, bias toward REQUEST CHANGES or BLOCKED when evidence is missing.
