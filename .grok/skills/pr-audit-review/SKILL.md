# pr-audit-review

**Version**: 0.3.1  
**Author**: Grok + 飛べない豚  
**Last Updated**: 2026-06-07

## Overview

`pr-audit-review` is a **context-aware, purpose-driven PR audit and formal review skill**.

It goes far beyond simple diff inspection (like typical Codex reviews). It deeply analyzes:
- The **stated purpose/objective** of the PR (from title, body, linked issues)
- The **target files** changed in the PR (full content, not just diff)
- **Related/impacted files** (inferred from imports, architecture, tests, docs, config, and cross-references)
- **Scope drift** (scope-out changes outside the stated purpose)

The skill then generates a rigorous, evidence-based audit report and posts it as a **formal GitHub Review** (using `COMMENT` or `REQUEST_CHANGES`).

This skill is designed for high-quality projects that require strong audit trails, such as Po_core, Cyber-Immunizer, philosophy-driven AI systems, safety-critical components, and PR-Forge style workflows.

## When to Use

- A GitHub PR comment contains the trigger phrase: `@grok Review`
- Manual deep audit requested for any open PR before merge or major decision.
- Need to produce structured, merge-stable audit evidence that survives future commits (no mutable HEAD SHA in the review body).
- Want to combine automated analysis with human-level contextual understanding (purpose alignment, side-effect analysis, invariant checking, scope drift detection).

## Trigger Mechanism

**Trigger phrase is fixed to exactly one string**: `@grok Review`

Usage flow:
1. User (or teammate) posts a comment on the PR containing exactly `@grok Review`.
2. Agent detects the trigger via `pull_request_read` → `get_comments`.
3. Skill is invoked with `owner`, `repo`, `pull_number`, and optional `trigger_comment_id`.
4. Skill performs full audit and posts a formal Review (optionally replying to the trigger comment).

This design prioritizes simplicity and auditability over multiple trigger variations.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `owner` | string | Yes | Repository owner |
| `repo` | string | Yes | Repository name |
| `pull_number` | integer | Yes | PR number |
| `trigger_comment_id` | integer | No | ID of the comment that triggered the review (for reply threading) |
| `focus_areas` | array<string> | No | Specific areas to emphasize (e.g. `["safety", "architecture", "tests"]`) |
| `additional_related_files` | array<string> | No | Explicit list of extra file paths to analyze |
| `post_review` | boolean | No (default: true) | Whether to actually post the GitHub Review. Set false for dry-run/report-only. |
| `review_event` | string | No (default: "COMMENT") | `COMMENT` or `REQUEST_CHANGES` |
| `max_files_to_read` | integer | No (default: 15) | Safety limit on how many full files to read for context |

## Core Analysis Procedure (Strict Steps)

The skill **must** follow this sequence. Do not skip steps.

### 1. PR Metadata, Purpose & Head SHA Extraction
- Use `pull_request_read` (method=`get`) to fetch title, body, head/base, state, linked issues.
- Extract clear **PR objective/purpose** from title + body + any linked issue bodies.
- **Explicitly extract and record the `head.sha`** from the API response. This is the exact commit being audited.
- State it verbatim in the report header as `**Audited at head SHA**: <value>` (a frozen fact).
- **Never** write "Final HEAD SHA", "current HEAD SHA", or any mutable/live label. Only the fixed audit-time SHA is allowed.
- If purpose is ambiguous or missing, stop and report (do not guess).

### 2. Changed Files & Diff (Diff Is Source of Truth)
- Use `pull_request_read` (method=`get_files` + `get_diff`).
- Record all changed files with stats.
- **PR body is a self-report**. If the PR body contradicts the actual diff, **trust the diff** and explicitly note the contradiction in the report.

### 3. Related Files Discovery (Beyond Diff)
- Read full content of changed files using `get_file_contents` with `ref=refs/pull/{pull_number}/head`.
- Parse imports/dependencies.
- Infer high-impact related files (tests, docs, config, core modules, callers, etc.).
- Merge with `additional_related_files`.
- Limit to `max_files_to_read`.

### 4. Deep Contextual Reading
- Read full content of target + top related files.
- Fetch CI status (`get_check_runs`), existing reviews/comments, and secret scan if relevant.

### 5. Multi-Angle Audit (Purpose-Driven + Scope Drift Detection)
Evaluate against the extracted purpose:
- **Purpose Alignment**
- **Scope-in / Scope-out Identification** (mandatory)
  - `scope-in`: Changes within the stated purpose.
  - `scope-out`: Changes outside the stated purpose (scope drift). Flag every scope-out change explicitly.
- **Correctness, Completeness, Edge Cases, Error Handling**
- **Side Effects on Related Files**
- **Invariants & Safety** (especially safety gates, policy checks, FreedomPressure, etc.)
- **Test Quality & Coverage**
- **Architecture & Consistency**
- **Documentation & Traceability**
- **Security / Secrets / Performance**
- **Positive Findings** (explicitly preserve good work and previous audit notes)

### 6. CI Classification (Strict 9-Category Taxonomy)
Classify the CI result for the **audited head SHA** using exactly one of:
- `NOT TRIGGERED`
- `WORKFLOW PARSE FAILURE`
- `RUNNER START FAILURE`
- `CHECKOUT FAILURE`
- `SETUP FAILURE`
- `INSTALL FAILURE`
- `TEST FAILURE`
- `DOMAIN FAILURE`
- `SUCCESS`

**Important rules**:
- Only consider check runs for the audited `head_sha`. If no matching run exists → `NOT TRIGGERED`.
- If pytest failed → `TEST FAILURE`.
- If pytest did not run → do **not** call it `TEST FAILURE`; use the matching failure category.
- "Complete job" success does not automatically mean overall success.
- **CI green alone is never sufficient for merge approval.**

### 7. Report Generation
Produce a structured report containing:
- Header with `Audited at head SHA`
- PR Purpose Summary
- Scope of Analysis
- Scope-in / Scope-out breakdown
- Positive Observations
- Issues & Concerns (with file:line evidence)
- Documentation / History Gate (5 items)
- Recommendations
- CI Classification + Test Status
- Self-Audit Checklist Result
- Verdict in the strict 4-line merge decision format

### 8. Pre-Posting Self-Audit (Mandatory)
Run the **15-item** checklist. **Only post if all items PASS**.

### 9. Post Formal GitHub Review
- Use `pull_request_review_write` (`method=create`, `event=COMMENT` or `REQUEST_CHANGES`).
- Optionally add line-specific comments via `add_comment_to_pending_review`.
- If `trigger_comment_id` is provided, reply to it.
- Skip posting if `post_review=false` (dry-run mode).

### 10. Final Confirmation
Re-fetch reviews to confirm posting and report success.

## Output Format (Posted Review Body)

```
## PR Audit Review (by Grok pr-audit-review)

**Audited at head SHA**: abc1234...
**PR Purpose (extracted)**: ...
**Files Analyzed**: ...

### Scope-in
- ...

### Scope-out (scope drift)
- ... (or "None")

### Positive Findings
- ...

### Issues & Concerns
1. [file:line] ...
   Evidence: ...
   Risk: ...

### Documentation / History Gate
- README: <yes/no> — reason
- docs/**: <yes/no> — reason
- changelog/history: <yes/no> — reason
- generator scripts: <yes/no> — reason
- data ledger: <yes/no> — reason

### Recommendations
- ...

### CI / Test Status
- CI Classification: <one of 9 categories>
- Notes: ...

### Self-Audit Checklist
- [x] All items passed

### Verdict
Code Audit:           APPROVE / REQUEST CHANGES / BLOCK
CI Verification:      VERIFIED / FAILED / NOT VERIFIED
Codex Verification:   VERIFIED / VERIFIED BY REACTION ONLY / FAILED / NOT VERIFIED / UNRESOLVED THREAD PRESENT
Merge Recommendation: APPROVE / HOLD / BLOCK
```

**Important Verdict Rules**:
- `UNRESOLVED THREAD PRESENT` → `Merge Recommendation` must **not** be `APPROVE`.
- `Scope-out` contains any auto-BLOCK item → `Merge Recommendation` must be `BLOCK`.

## Cyber-Immunizer Scope-out Auto-BLOCK Conditions

The following scope-out items **automatically force `Merge Recommendation: BLOCK`** for the Cyber-Immunizer repository:

- Changes to `.github/workflows/**` execution logic
- Unauthorized changes to `core/**` or `data/**`
- Introduction or modification of `live_model_enabled=true`
- Any changes related to GitHub Secrets configuration

These conditions are **Cyber-Immunizer specific**. Other repositories may define their own auto-BLOCK lists.

## Mandatory Self-Audit Checklist (Before Posting)

All items must PASS:

- [ ] PR purpose clearly extracted and used as primary criterion
- [ ] `Audited at head SHA` stated verbatim (no mutable "current/Final HEAD SHA")
- [ ] PR body vs diff conflict resolved by trusting the diff + noted
- [ ] Related files analysis performed
- [ ] Scope-in and Scope-out both explicitly identified
- [ ] Scope-out auto-BLOCK conditions evaluated (Cyber-Immunizer)
- [ ] Documentation / History Gate completed for all 5 items
- [ ] CI classified using exactly one of the 9 categories with head SHA matching
- [ ] Positive aspects explicitly mentioned
- [ ] Previous good notes preserved where relevant
- [ ] Verdict in strict 4-line format with valid values
- [ ] `UNRESOLVED THREAD PRESENT` → Merge Recommendation is not APPROVE
- [ ] Language precise, evidence-based, no overconfidence
- [ ] Only allowed tools used (no local clones/commits/file edits)
- [ ] Analysis stayed within scope

## Implementation Notes

**Primary Tools**:
- `github___pull_request_read` (all methods)
- `github___get_file_contents` (with `ref=refs/pull/{pull_number}/head`)
- `github___pull_request_review_write`
- `github___add_comment_to_pending_review`
- `github___run_secret_scanning` (when relevant)

**Python Helper**:
See `analyzer.py` in the same directory. It provides structured dataclasses and helper functions (as specification/skeleton) to improve consistency of analysis and reporting.

**Extensibility**:
Repository-specific auto-BLOCK rules and analysis logic can be added (e.g., `rules/cyber_immunizer.py`).

## Examples

**Trigger Comment**:
```
@grok Review
```

**Invocation**:
```
pr-audit-review(
    owner="hiroshitanaka-creator",
    repo="Cyber-Immunizer",
    pull_number=73,
    trigger_comment_id=4641725401,
    post_review=true,
    review_event="COMMENT"
)
```

---

**Version 0.3.1 Changes**:
- Trigger unified to single phrase "@grok Review"
- Added mandatory Scope-in / Scope-out detection + Cyber-Immunizer auto-BLOCK conditions
- Added strict 9-category CI classification with head SHA matching rule
- Strengthened Documentation / History Gate (generator update rule)
- Clarified `UNRESOLVED THREAD PRESENT` handling in verdict
- Added reference to `analyzer.py` helper skeleton
- **Fixed checklist count from 16 to 15** (Codex P3 feedback)
- Improved overall precision and auditability

---

*This skill prioritizes evidence, traceability, and resistance to scope drift over speed.*