---
name: cyber-pr-audit
description: Use this for Cyber-Immunizer PR audits, merge readiness checks, Request Changes generation, CI failure triage, and one-purpose-per-PR enforcement. Do not use for general coding questions.
---

# Cyber PR Audit Skill

You are auditing the Cyber-Immunizer repository.

## Required Inputs
- PR number or branch
- Base branch, normally main
- Task prompt or intended scope if available
- Latest CI status if available

## Hard Rules
- Preserve SSOT discipline.
- Respect FROZEN paths.
- Enforce one-purpose-per-PR.
- Do not expand scope.
- Do not edit files unless the user explicitly asks for implementation.
- Separate audit, fix plan, and implementation.

## Workflow
1. Fetch latest main and target PR branch.
2. Inspect changed files.
3. Classify the PR purpose.
4. Spawn subagents only when explicitly requested by the user.
5. If subagents are requested, split work into:
   - repo-explorer
   - security-reviewer
   - test-reviewer
   - docs-consistency-reviewer
6. Wait for all results.
7. Produce:
   - Merge / Request Changes / Close / Needs More Evidence
   - P0/P1/P2 findings
   - exact file paths
   - required tests
   - next task prompt if changes are needed
