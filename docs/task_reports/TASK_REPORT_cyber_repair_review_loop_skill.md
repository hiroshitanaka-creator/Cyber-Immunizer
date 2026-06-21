# Task Report — cyber-repair-review-loop skill

## Purpose

Add repository-scoped repair/review-loop skill definitions for Codex and Claude so implementation agents follow a disciplined preflight, prompt-gate, minimal implementation, self-audit, bounded CI/test repair, review-thread classification, and final owner-report workflow.

## Files added

- `.agents/skills/cyber-repair-review-loop/SKILL.md`
- `.claude/skills/cyber-repair-review-loop/SKILL.md`
- `docs/task_reports/TASK_REPORT_cyber_repair_review_loop_skill.md`

## Why this skill exists

Cyber-Immunizer implementation work often involves safety-sensitive project state, paid-credit controls, promotion state, review findings, and CI evidence. This skill creates a shared operating policy for Codex and Claude so repair work remains scoped, auditable, and owner-controlled.

The workflow requires agents to verify repository state before editing, gate the task prompt for missing instructions, make minimal changes, audit their own diffs at GPT audit standard, run a maximum of three CI/test repair attempts, classify Codex Review threads without resolving them, and return a final Project Owner-ready report.

## Final GPT audit remains required

This skill does not replace final GPT audit. Final merge remains blocked unless the Project Owner obtains a separate GPT final audit approval.

## Auto-merge and review-thread resolve are forbidden

The skill explicitly forbids automatic merge, automatic PR approval, automatic Codex Review thread resolve, and automatic GitHub review-thread resolve. Review-thread resolution and merge decisions remain reserved for the Project Owner.

## Validation performed

Planned validation for this docs/skill-only task:

- Confirm both canonical skill files exist.
- Confirm no noncanonical nested `Cyber-Immunizer/.../cyber-repair-review-loop` path was created.
- Confirm changed files are limited to allowed paths.
- Confirm no paid-credit, workflow_dispatch, Gemini API, promotion, ledger, genome, detector runtime, workflow, dependency, test, fixture, or core changes were made.

Python tests are unnecessary for this docs/skill-only change because no executable product code, tests, state files, workflows, or dependencies were modified.

## Layer declaration

Which layer did this task advance?

[ ] Layer 1 — Research Foundation
[ ] Layer 2 — Value Validation
[x] Layer 3 — AI Operation Control
[ ] None
