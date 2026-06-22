<!--
AI_DOC_META
status: PROTOCOL
scope: Mandatory workflow for keeping long-running Codex / Claude tasks restartable, auditable, and bounded in Cyber-Immunizer.
use_for:
  - planning multi-step Codex or Claude implementation tasks
  - checkpointing long-running work before context loss
  - handing off a branch or PR between Codex and Claude without stale-state drift
  - preventing GPT-generated ambiguity from turning into unbounded implementation work
do_not_use_for:
  - authorizing paid-credit runs
  - authorizing workflow_dispatch
  - authorizing edits to .github/**, core/**, scripts/**, or data/** without explicit task scope
  - approving or merging a pull request
related:
  - docs/AI_ENTRYPOINT.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
  - docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - AGENTS.md
last_reviewed: 2026-06-22
AI_DOC_META_END
-->
# Long-Running Agent Workflow — Cyber-Immunizer

This protocol defines how Codex and Claude should execute long-running work in
Cyber-Immunizer without depending on chat memory, vague GPT summaries, or
unverified self-reports.

Long-running does **not** mean "let the agent keep going indefinitely." It means
"split the task into bounded work packets, verify state at every boundary, and
leave a restartable checkpoint before context is lost."

---

## 1. When this workflow is mandatory

Use this workflow when any condition below is true:

- The task is expected to need more than one implementation pass.
- The task may span multiple commits, multiple files, or multiple agents.
- Codex and Claude may both touch the work at different times.
- A PR may receive review comments that require follow-up implementation.
- The work involves protocol, audit, task-prompt, handoff, or PR-completion rules.
- The agent may hit context limits, tool instability, or session timeout before completion.

If none of these are true, use the normal task prompt / PR audit protocols instead.

---

## 2. Non-goals and hard prohibitions

This workflow does not authorize any normally prohibited action.

Unless the Project Owner explicitly approves the specific task, do not:

- run paid-credit workflows or paid-credit API calls,
- run `workflow_dispatch`,
- call the Gemini API,
- edit `data/**` or ledger files,
- edit `.github/**`, `core/**`, or `scripts/**`,
- set `promote_approved=true`,
- promote a candidate,
- approve or merge a PR,
- push forcefully or rewrite branch history.

Do not let Codex and Claude write to the same branch at the same time. Use a
serial baton. If parallel work is unavoidable, use separate branches and separate
PRs for separate work packets.

---

## 3. Roles

| Role | Responsibility |
|---|---|
| Project Owner | Final decision-maker. Approves scope expansion, paid-credit actions, merge, and any override of frozen paths. |
| GPT / Orchestrator | Creates bounded task prompts, audits current state, and prevents vague or scope-leaking instructions. |
| Codex / Claude implementation agent | Executes exactly one approved work packet at a time, verifies repository state, commits changes, and emits checkpoints. |
| Audit agent | Reviews the exact PR head SHA, changed files, CI, Codex comments, and protocol compliance before merge recommendation. |

A single agent may perform more than one role only if the output explicitly says
which role it is performing for that response.

---

## 4. Workflow overview

### Phase 0 — Intake and orientation

Before editing, the agent must read the applicable entrypoint and state files:

- `AGENTS.md` when operating as Codex.
- `CLAUDE.md` when operating as Claude.
- `docs/AI_ENTRYPOINT.md`.
- `data/project_state.json` and `docs/PROJECT_STATE.md` for current-state claims.
- This file, when the task is long-running.
- The task-specific protocol selected by `docs/AI_ENTRYPOINT.md`.

The agent must identify:

- current branch and head SHA,
- current task in one sentence,
- allowed files,
- reference-only files,
- frozen files,
- impact files,
- required verification commands,
- stop conditions.

If any required field is unknown, the agent must stop and report what is missing.

### Phase 1 — Work-packet plan

Before implementation, split the task into work packets.

Each packet must have:

- an ID (`P0`, `P1`, `P2`, ...),
- one objective,
- exact files allowed for that packet,
- files explicitly frozen for that packet,
- expected verification,
- completion evidence.

A work packet must be small enough that it can be completed, verified, and
checkpointed before the agent loses context.

### Phase 2 — Serial baton execution

Only one implementation agent owns the branch at a time.

For each baton handoff:

1. The outgoing agent emits a checkpoint block using the template in this file.
2. The incoming agent verifies branch, head SHA, PR state, changed files, and tests.
3. The incoming agent either continues exactly the next packet or stops with a mismatch report.

The incoming agent must trust repository state over the outgoing agent narrative.

### Phase 3 — Work quantum loop

For each work quantum, the implementation agent must:

1. Re-verify branch and head SHA.
2. Re-read the active checkpoint.
3. Select exactly one work packet.
4. Implement only that packet.
5. Run the packet's verification commands or state why they could not be run.
6. Check forbidden paths.
7. Emit a fresh checkpoint block.
8. Stop if any stop condition is reached.

Do not continue into the next packet silently. A new packet requires either an
explicit task prompt or a fresh checkpoint that shows the previous packet is done.

---

## 5. Mandatory checkpoint block

Emit this block after every work quantum, before stopping, before handing off to
another agent, and before asking the Project Owner for a decision.

```markdown
# Long-Running Agent Checkpoint — Cyber-Immunizer

## 1. Verifiable repository state
- repo: hiroshitanaka-creator/Cyber-Immunizer
- branch:
- head SHA:
- base branch:
- PR number / state:
- CI status for head SHA: SUCCESS / FAILED / NOT TRIGGERED / 未確認

## 2. Active role and packet
- acting role: GPT_ORCHESTRATOR / CODEX_IMPLEMENTATION / CLAUDE_IMPLEMENTATION / AUDIT
- current packet ID:
- current packet objective:

## 3. Completed in this quantum
- [x] <completed item> — commit <sha> / file <path>

## 4. Files touched
- <path> — <why it was touched>

## 5. Verification performed
- command: <command or NOT RUN>
- result: <actual result or reason not run>
- forbidden-path check: <actual result>

## 6. Next exact action
- [ ] <one concrete next action only>

## 7. Hard constraints still in effect
- <all constraints that remain binding>

## 8. Blockers / decisions needed
- <blocker, or `なし`>

## 9. Assumptions / unverified
- <unverified claim, or `なし`>

## 10. Continuation prompt for the next agent
Paste this into the next Codex / Claude session:

```text
You are continuing Cyber-Immunizer work from a long-running checkpoint.
First read AGENTS.md or CLAUDE.md as applicable, then docs/AI_ENTRYPOINT.md,
then docs/audit_gate/LONG_RUNNING_AGENT_WORKFLOW.md.
Verify the branch, head SHA, PR state, changed files, and test status below
against the repository before editing. If anything differs, stop and report the
mismatch. Continue only the next exact action listed below.

<copy sections 1, 2, 6, 7, 8, and 9 from this checkpoint>
```
```

A checkpoint without branch, head SHA, PR state, constraints, and next exact
action is invalid.

---

## 6. Stop conditions

Stop immediately and report instead of continuing if any of these occur:

- The task would require touching a frozen path not explicitly allowed.
- The branch or head SHA differs from the checkpoint or task prompt.
- The current-state sources disagree and the conflict affects the task.
- Verification fails and the failure is not clearly caused by the current packet.
- The agent needs paid-credit execution, Gemini API access, or `workflow_dispatch`.
- The agent wants to broaden the task scope.
- The agent cannot fill the checkpoint without guessing.
- Codex and Claude both appear to have changed the same branch concurrently.
- The next action is not a single concrete action.

A stop is not a failure. Continuing past an unverified boundary is the failure.

---

## 7. Codex / Claude prompt skeleton for long work

Use this skeleton when assigning a long-running packet to Codex or Claude:

```markdown
# Task: Execute one bounded long-running work packet for Cyber-Immunizer.

## Required protocol
Read and follow:
- AGENTS.md or CLAUDE.md, depending on your agent runtime
- docs/AI_ENTRYPOINT.md
- docs/audit_gate/LONG_RUNNING_AGENT_WORKFLOW.md
- docs/audit_gate/TASK_PROMPT_PROTOCOL.md, if implementation is required
- docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md, if handing off or continuing from a handoff

## Current packet
- Packet ID:
- Objective:
- ALLOWED:
- REFERENCE_ONLY:
- FROZEN:
- IMPACT:

## Constraints
- Execute only this packet.
- Do not begin the next packet silently.
- Do not touch frozen paths.
- Do not run paid-credit, Gemini API, or workflow_dispatch.
- Do not approve or merge PRs.
- Stop on ambiguity, state mismatch, or scope expansion.

## Definition of Done
- Required verification:
- Forbidden-path check:
- Fresh checkpoint block emitted using docs/audit_gate/LONG_RUNNING_AGENT_WORKFLOW.md.
```

---

## 8. PR requirements for long-running work

A PR created under this workflow must include:

- summary,
- current-state sources checked,
- work packets completed,
- changed files,
- verification commands and results,
- latest checkpoint block or a link to the task report,
- No-API / no-paid-credit confirmation,
- explicit next recommended action.

The PR body is still a self-report. Audit must verify it against the actual diff,
current head SHA, CI, and files.

---

## 9. Completion rule

A long-running task is complete only when all are true:

- every in-scope packet is committed,
- the PR diff contains no out-of-scope files,
- required verification is green or the reason for not running is documented,
- a task report exists when required by repository rules,
- the final checkpoint says `Next exact action: audit PR` or `Next exact action: Project Owner merge decision`,
- no blocker remains unlabeled.

If these are not all true, the task is not complete. It is merely checkpointed.
