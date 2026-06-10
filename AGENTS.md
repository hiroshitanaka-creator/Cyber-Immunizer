# Cyber-Immunizer Codex Workflow Rules

This repository uses Codex as an implementation agent. Keep changes minimal,
test-backed, and limited to one purpose per PR.

## Canonical current-state sources

For current project state, use only these canonical sources:

1. `data/project_state.json`
2. `docs/PROJECT_STATE.md`

`README.md`, `CLAUDE.md`, old task reports, old PR bodies, roadmap documents,
and historical phase documents are not canonical current-state sources. If they
conflict with the canonical sources, the canonical sources win. Historical
files preserve past state and must not be treated as current-state
contradictions.

## Required pre-edit checks

Before editing, inspect:

- `data/project_state.json`
- `docs/PROJECT_STATE.md`
- Any files explicitly named in the task prompt

Identify the current `state_id`, current `next_action`, allowed files,
forbidden files, and task-required test commands before making changes.

## Hard prohibitions

Unless the Project Owner explicitly approves the specific task, do not:

- Run paid-credit workflows or paid-credit runs.
- Run `workflow_dispatch`.
- Call the Gemini API.
- Edit ledger files.
- Edit `data/api_usage_ledger.json`.
- Set `promote_approved=true`.
- Promote any candidate.
- Change `.github/**`.
- Change `core/**`.
- Change model names or budget settings.
- Reintroduce `.grok/**`.

If a task appears to require any prohibited action, stop and report instead of
implementing.

## PR scope rule

One PR must have one purpose. Do not mix implementation fixes, broad docs
cleanup, workflow changes, paid-credit execution, promotion logic, or SSOT
rewrites in the same PR. If a needed fix is outside scope, document it as a
follow-up instead of adding it.

## Verification rule

After changes, run the tests required by the task and a forbidden-path check.
For typical implementation changes, run:

```bash
pytest tests/ -q
```

If `data/project_state.json` changes, also run:

```bash
python -m json.tool data/project_state.json
```

Run a forbidden-path check appropriate to the task, for example:

```bash
git diff --name-only | grep -E '^(\.github|core|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true
```

If the task explicitly allows otherwise-forbidden paths, adjust the check and
explain why.

## PR body requirements

Every Codex PR must include:

- Summary
- Canonical State checked
- Changed files
- Verification commands and results
- No-API confirmation

When relevant, also include forbidden files not changed, residual risk, and the
next recommended action.

## Codex Review

After opening or updating a PR, request:

```text
@codex Review
```

If Codex Review reports P1 or P2 issues, do not merge until resolved. If it
reports P3 issues, either fix them or explicitly explain why they are
non-blocking.
