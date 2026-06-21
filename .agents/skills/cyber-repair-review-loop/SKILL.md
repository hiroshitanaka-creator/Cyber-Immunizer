---
name: cyber-repair-review-loop
description: Use this for Cyber-Immunizer repair tasks after a task prompt or PR review finding, when the agent must implement a minimal fix, self-audit the diff, handle CI/test failures up to 3 times, classify Codex Review threads without resolving them, and return a final owner-ready report. Do not use for casual explanation or broad roadmap work.
---

# Cyber Repair Review Loop

## Purpose

Use this repository-scoped Codex skill to run a disciplined repair -> self-review -> repair-loop workflow before handing work back to the Project Owner. The workflow is designed for scoped Cyber-Immunizer implementation tasks, PR review findings, and CI/test failures that need minimal safe repair and owner-ready reporting.

This skill does not authorize merge, approval, review-thread resolution, paid-credit execution, promotion, or high-risk repository state changes. Final merge remains blocked unless the Project Owner obtains a separate GPT final audit approval.

## When to use

Use this skill when all of the following are true:

- The Project Owner provided a scoped implementation, repair, or PR-review-finding task.
- The task has clear target files, allowed changes, forbidden changes, validation commands, and Definition of Done.
- The agent must implement a minimal fix, self-audit its diff, run relevant validation, and report owner-ready evidence.
- Codex Review threads or CI/test failures may need classification and bounded repair.

## When not to use

Do not use this skill for:

- Casual explanation, roadmap brainstorming, or broad architecture discussion.
- Broad refactors or opportunistic cleanup.
- Tasks that require automatic merge, automatic approval, or review-thread resolution.
- Paid-credit runs, Gemini API calls, workflow_dispatch, promotion, ledger/genome changes, dependency upgrades, or workflow edits unless explicitly owner-approved and scoped.
- Any task missing the Task Prompt Gate items below.

## Phase 0 — Preflight checklist

Run or request equivalent evidence before editing:

```bash
git status --short
git branch --show-current
git remote -v
git fetch origin
git rev-parse HEAD
git diff --name-only origin/main...HEAD
```

If `origin` is missing, run:

```bash
git remote add origin https://github.com/hiroshitanaka-creator/Cyber-Immunizer.git
git fetch origin
```

Before destructive repair commands, stop if there are uncommitted unrelated changes. Record branch, start HEAD, remote, and baseline diff evidence for the final report.

## Phase 1 — Task Prompt Gate checklist

Before editing, verify that the task prompt states:

1. Mission / objective
2. Target PR / branch / files
3. Allowed changes
4. Forbidden changes
5. Whole-PR review requirement
6. Validation commands
7. Definition of Done
8. Stop conditions
9. Final report format
10. Owner-only actions

If any item is missing, stop and ask for a corrected task prompt or produce a gate-failure report. Do not infer permission for high-risk work from ambiguity.

## Phase 2 — Minimal scoped implementation

The agent must:

- Make one logical change at a time.
- Stay inside allowed files.
- Avoid unrelated refactors and formatting churn.
- Preserve public APIs unless explicitly scoped.
- Preserve default runtime behavior unless explicitly scoped.
- Preserve tests unless adding or strengthening them.
- Document any necessary risk.

## Phase 3 — Self-audit workflow

After editing, inspect the full diff before final reporting. Classify self-found findings:

- `P0 BLOCKER` — unsafe, forbidden, or corrupts project state.
- `P1 REQUIRED FIX` — correctness or security issue.
- `P2 SHOULD FIX BEFORE MERGE` — evidence, tests, edge cases, or reliability issue.
- `P3 NICE TO HAVE` — non-blocking improvement.

The self-audit must check:

- Changed files and forbidden files.
- Task scope and unrelated changes.
- Security boundaries.
- Input validation and output escaping where relevant.
- Exception handling.
- Test coverage and CI/test relevance.
- PR body / docs consistency.
- No paid-credit, Gemini API, workflow_dispatch, promotion, ledger, or genome side effects.

## Phase 4 — Repair workflow

Fix all self-found P0, P1, and P2 issues that are within scope. If a required fix exceeds scope, stop and report the issue, affected files, risk, and requested owner decision. Do not broaden scope to make the task appear complete.

## Phase 5 — CI/test repair loop, max 3

CI/test repair loop maximum: 3 attempts. Each attempt must:

- Identify the failing command or CI job.
- Classify the cause.
- Make the smallest safe fix.
- Rerun the relevant focused test locally if available.
- Report what changed.

Use these failure categories: `lint`, `type-check`, `unit-test`, `integration-test`, `security-check`, `build`, `docs/state-sync`, `unknown`.

For each attempt, record:

```text
Attempt number:
Failing command/job:
Failure category:
Root cause:
Files changed:
Focused validation rerun:
Result:
```

After 3 unsuccessful attempts, stop and ask the Project Owner. Do not continue indefinitely. Do not broaden scope, delete tests, weaken tests, hide exceptions, or convert security failures into non-blocking success to make CI pass.

## Phase 6 — Codex Review thread handling

The agent may inspect Codex Review threads and classify them as:

- `addressed by code`
- `still open`
- `outdated`
- `requires owner decision`
- `owner resolve pending`

The agent must not resolve Codex Review threads, GitHub review threads, or any review conversation. Resolve is reserved for the Project Owner.

Produce this table when threads are available:

| Thread / comment | Path | Finding | Status | Evidence |
|---|---|---|---|---|

The final report must say: `Review thread resolve is reserved for the Project Owner.`

## Forbidden operations

The skill explicitly prohibits:

- Automatic merge.
- Automatic PR approval.
- Automatic Codex Review thread resolve.
- Automatic GitHub review-thread resolve.
- Paid-credit runs.
- Gemini API calls.
- `workflow_dispatch`.
- Promotion state changes.
- Ledger changes unless explicitly scoped and owner-approved.
- Genome changes unless explicitly scoped and owner-approved.
- `core/detector.py` default runtime behavior changes unless explicitly scoped and owner-approved.
- `.github/workflows/**` changes unless explicitly scoped and owner-approved.
- Dependency upgrades unless explicitly scoped and owner-approved.
- Broad refactors.
- Unrelated formatting churn.
- Deleting tests to pass CI.
- Weakening tests.
- Hiding exceptions.
- Converting security failures into non-blocking success.

## Owner-permission-only operations

High-risk changes are owner-permission-only and are basically forbidden by default. If an agent believes such a change is necessary, it must stop, explain the reason, list exact files and risks, and ask for explicit Project Owner permission before editing.

High-risk changes include at minimum:

- paid-credit
- workflow_dispatch
- Gemini API
- promotion state
- ledger
- genome
- `core/detector.py` default behavior
- `.github/workflows/**`
- secrets
- authentication / authorization behavior
- dependency lockfiles

## Final report format

```markdown
## Summary
- What changed:
- Why it changed:
- Layer advanced:
## Preflight
- Branch:
- Start HEAD:
- End HEAD:
- Remote:
- Changed files:
## Scope Control
- Allowed files changed:
- Forbidden files changed: yes/no
- Unrelated changes: yes/no
## Self-Audit Result
| Severity | Finding | Status | Evidence |
|---|---|---|---|
## CI/Test Repair Loop
| Attempt | Failure category | Fix | Result |
|---:|---|---|---|
## Validation
- Commands run:
- Results:
- Not run:
## Codex Review Threads
| Thread | Path | Status | Evidence |
|---|---|---|---|
## Safety Confirmation
- Auto-merge performed: no
- Review threads resolved: no
- paid-credit run: no
- workflow_dispatch: no
- Gemini API call: no
- promotion state change: no
- ledger/genome change: no, unless explicitly scoped and owner-approved
- detector default behavior change: no, unless explicitly scoped and owner-approved
## Owner Actions Remaining
- CI green re-check, if not already verified:
- Codex Review thread resolve:
- Final GPT audit:
- Merge decision:
```

## Stop conditions

Stop and report if:

- Canonical skill paths cannot be created.
- The branch is not based on latest `main` or latest-main evidence cannot be obtained.
- Unrelated uncommitted changes exist.
- The task requires modifying forbidden paths without explicit owner approval.
- A tool or user asks for auto-merge, auto-approval, or review-thread resolution.
- A tool or user asks to run paid-credit, Gemini API, or workflow_dispatch.
- The task requires promotion, ledger/genome changes, detector default behavior changes, workflow edits, secrets, authentication/authorization changes, or dependency lockfile edits without explicit owner approval.
- Conflicting existing skill definitions with the same name are found.
- A malformed path under `Cyber-Immunizer/` would be created.
- Three CI/test repair attempts fail.
