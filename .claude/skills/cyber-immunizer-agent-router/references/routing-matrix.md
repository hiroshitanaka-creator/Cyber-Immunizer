# Cyber-Immunizer Agent Routing Matrix

This reference defines which track should handle each repository maintenance task.

## Tracks

- `ROUTE_TASK_PROMPT`: create a bounded implementation prompt.
- `ROUTE_CODEX_IMPLEMENT`: make a small test-backed repository change.
- `ROUTE_CLAUDE_DESIGN`: analyze broad scope and reduce it to an atomic task.
- `ROUTE_PR_REVIEW`: review an existing pull request.
- `ROUTE_TRIAGE`: classify failing checks and decide the next repair.
- `ROUTE_STRUCTURED_RULES`: work on structured detector rule schema, evaluator, adapter, or equivalence tests.
- `ROUTE_OWNER_GATE`: stop for exact owner approval before owner-only actions.
- `ROUTE_HANDOFF`: create a copyable continuation prompt.
- `ROUTE_SKILL_GOVERNANCE`: maintain skill files and routing policy.

## Owner-gate triggers

Use `ROUTE_OWNER_GATE` for any request that changes live API usage, workflow dispatch, promotion state, ledger files, model names, model budgets, or repository safety boundaries.

## Pairing pattern

1. Claude or GPT reduces broad work into a single bounded task.
2. Codex performs the minimal repository edit.
3. Claude or GPT reviews the resulting PR.
4. Codex repairs concrete findings.
5. The owner makes merge and owner-only operation decisions.

## Stop conditions

Stop instead of continuing when current-state evidence cannot be checked, branch or head SHA is unclear, allowed files are ambiguous, required checks cannot be identified, or the requested action needs owner approval that is not present in the current task.
