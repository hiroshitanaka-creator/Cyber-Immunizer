---
name: cyber-immunizer-agent-router
description: Route Cyber-Immunizer Claude and Codex work across prompt creation, implementation, PR review, check triage, structured detector rule work, handoff, and owner-decision gates while preserving repository rules.
when_to_use: Use when coordinating Claude, Codex, GPT review, task prompts, PR review, long-running repository work, or thread handoff for Cyber-Immunizer.
argument-hint: "[task | PR URL | issue | handoff]"
---

# Cyber-Immunizer Agent Router for Claude

## Mandatory read order

Before substantive work, read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `data/project_state.json`
4. `docs/PROJECT_STATE.md`
5. files named by the user

For prompt, PR review, or handoff tasks, also read the matching protocol under `docs/audit_gate/`.

## Route decision

Before work, output:

```text
ROUTE_DECISION
- task_type: <implementation | task_prompt | pr_review | request_changes | triage | structured_rules | skill_governance | handoff | owner_decision>
- selected_track: <Claude | Codex | GPT review | owner gate | mixed>
- sources_checked: <files/evidence>
- state_id: <value or unknown>
- next_action: <value or unknown>
- owner_approval_needed: <yes/no + reason>
- allowed_paths: <paths>
- frozen_paths: <paths>
- check_plan: <commands or no-run reason>
- next_atomic_action: <single next action>
```

## Routing tracks

- `ROUTE_TASK_PROMPT`: create or validate a bounded Codex/Claude task prompt.
- `ROUTE_CODEX_IMPLEMENT`: send Codex one small repository patch.
- `ROUTE_CLAUDE_DESIGN`: use Claude for broad analysis, scope reduction, and migration planning.
- `ROUTE_PR_REVIEW`: review a PR using the repository protocol, not only the diff.
- `ROUTE_TRIAGE`: classify failing checks before patching.
- `ROUTE_STRUCTURED_RULES`: handle structured detector rule schema, evaluator, adapter, or equivalence-test work.
- `ROUTE_OWNER_GATE`: stop for exact owner approval before owner-only actions.
- `ROUTE_HANDOFF`: produce a copyable continuation prompt.
- `ROUTE_SKILL_GOVERNANCE`: maintain skill files and routing policy.

## References

- `references/routing-matrix.md`
- `references/long-run-playbook.md`

## Finish rule

Separate confirmed changes, verified checks, unverified checks, intentionally unchanged files, owner decisions needed, and the next atomic action.
