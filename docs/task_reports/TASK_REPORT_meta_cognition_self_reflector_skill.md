# Task Report — meta-cognition-self-reflector Skill

## Purpose

Add repository-scoped `meta-cognition-self-reflector` skills for Codex and Claude so high-risk Cyber-Immunizer decisions use a bounded reasoning audit before recommendations are made.

## Files added

- `.agents/skills/meta-cognition-self-reflector/SKILL.md`
- `.agents/skills/meta-cognition-self-reflector/references/reflection_report_template.md`
- `.claude/skills/meta-cognition-self-reflector/SKILL.md`
- `.claude/skills/meta-cognition-self-reflector/references/reflection_report_template.md`
- `docs/task_reports/TASK_REPORT_meta_cognition_self_reflector_skill.md`

## Why this skill exists

The skill exists to reduce overconfidence, premise drift, hallucinated project state, unverified causal claims, and confusion between CI success, score improvement, tooling/docs additions, merge readiness, and real defensive value.

## When it should be invoked

Invoke it for high-risk decisions involving phase transitions, architecture changes, mutation boundary changes, fitness function changes, structured-rules runtime integration, Layer 2 / Layer 3 progress interpretation, experiment interpretation, paid-credit run decision-making, roadmap or completion definition changes, defensive-value claims, or deciding which layer a PR/task advances.

## When it should not be invoked

Do not invoke it for typo fixes, local test failures, straightforward PR review, routine CI triage, small validation fixes, task-report wording only, formatting-only changes, dependency updates, or implementation-focused work better handled by repair or PR-audit skills.

## Non-replacement statements

- This skill does not replace final GPT audit.
- This skill does not decide merge readiness.
- This skill does not prove Layer 2 value.

## Validation performed

- `git status --short`
- `git diff --name-only origin/main...HEAD` attempted, but `origin/main` was unavailable because fetching `origin` failed in this environment with HTTP 403.
- `git diff --check`
- `test -f .agents/skills/meta-cognition-self-reflector/SKILL.md`
- `test -f .claude/skills/meta-cognition-self-reflector/SKILL.md`
- `find . -path '*meta-cognition-self-reflector*' -print`

No Python tests were required because this was a docs/skill-only change and no Python code changed.

## Layer declaration

Which layer did this task advance?

[ ] Layer 1 — Research Foundation
[ ] Layer 2 — Value Validation
[x] Layer 3 — AI Operation Control
[ ] None
