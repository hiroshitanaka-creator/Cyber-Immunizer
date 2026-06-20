# Cyber-Immunizer Long-Run Playbook

This file is a compact continuation checklist for repository maintenance work.

## Start checklist

1. Read `AGENTS.md`.
2. Read `data/project_state.json`.
3. Read `docs/PROJECT_STATE.md`.
4. Read files named by the user.
5. Select one route label from `routing-matrix.md`.
6. Define one atomic objective.

## Work loop

1. Confirm allowed paths and frozen paths.
2. Make the smallest useful change.
3. Record what changed.
4. Run available checks or state why checks were not run.
5. Open or update one PR.
6. Record unresolved items.
7. Write a handoff when another session or agent must continue.

## PR checklist

A useful PR report includes:

- Summary
- State sources checked
- Changed files
- Checks and results
- No live API confirmation
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
