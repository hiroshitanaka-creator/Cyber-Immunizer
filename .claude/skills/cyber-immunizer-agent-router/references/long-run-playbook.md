# Cyber-Immunizer Long-Run Playbook

This file is a compact continuation checklist for repository maintenance work.

## Start checklist

1. Read `CLAUDE.md`.
2. Read `AGENTS.md`.
3. Read `data/project_state.json`.
4. Read `docs/PROJECT_STATE.md`.
5. Read files named by the user.
6. Select one route label from `routing-matrix.md`.
7. Define one atomic objective.

## Work loop

1. Confirm allowed paths and frozen paths.
2. Make the smallest useful change or produce the smallest useful prompt.
3. Record what changed or what was proposed.
4. Run available checks or state why checks were not run.
5. Open, update, or review one PR.
6. Record unresolved items.
7. Write a handoff when another session or agent must continue.

## PR or review checklist

A useful report includes:

- Summary
- State sources checked
- Changed files or reviewed files
- Checks and results
- No live API confirmation when applicable
- Files intentionally not changed
- Residual risk
- Next action

## Handoff template

```text
CYBER_IMMUNIZER_HANDOFF
- repository: hiroshitanaka-creator/Cyber-Immunizer
- branch: <branch>
- head SHA: <sha or unknown>
- PR number / state: <number and state if known>
- current task: <one sentence>
- done evidence: <commits, files, checks>
- not yet verified: <items>
- active constraints: <items>
- next atomic action: <one action>
```

## Finish rule

Do not describe an item as verified unless it was actually checked. If something was not checked, say so directly.
