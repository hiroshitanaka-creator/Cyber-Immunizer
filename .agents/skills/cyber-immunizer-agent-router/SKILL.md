---
name: cyber-immunizer-agent-router
description: Route Cyber-Immunizer long-running agent work across Codex implementation, Claude reasoning/refactor, PR audit, CI triage, task-prompt generation, structured-detector-rule migration, and paid-credit owner-decision gates. Use when asked to operate Codex or Claude skills, plan long agent runs, create task prompts, audit PRs, triage CI, or continue Cyber-Immunizer development without violating repository guardrails.
---

# Cyber-Immunizer Agent Router

## Purpose

Use this skill as the first routing layer for Cyber-Immunizer work that may involve multiple agents, long-running execution, PR loops, or safety-sensitive repository decisions. This skill does not replace `AGENTS.md`, `CLAUDE.md`, or the audit-gate protocols. It forces the agent to select the correct operating track before editing.

## Hard boundary

Cyber-Immunizer is defensive-only. Do not generate exploit procedures, offensive payloads, credential-theft logic, persistence logic, scanner logic for real targets, or real-world abuse instructions. Keep attack reasoning abstract and only use it to improve defensive controls.

Never perform any of the following unless the Project Owner explicitly approved that exact action in the current task:

- Gemini API call or live-model call
- paid-credit workflow or paid-credit run
- `workflow_dispatch`
- candidate promotion or `promote_approved=true`
- ledger edits, especially `data/api_usage_ledger.json`
- model name, model budget, or API budget changes
- `.github/**`, `core/**`, `scripts/**`, `data/**`, or `tests/**` changes outside the task's explicit scope

If the task requires a forbidden action and approval is not explicit, stop and report the required owner decision instead of implementing.

## Required state gate

Before editing or giving a routing decision, inspect and use this authority order:

1. Machine evidence: latest branch/HEAD, CI, `data/api_usage_ledger.json`, `data/genome.json` when relevant.
2. `data/project_state.json`.
3. `docs/PROJECT_STATE.md`.
4. Derived summaries: `README.md`, `CLAUDE.md`, old PR bodies, old task reports, old roadmap documents.

Minimum files to read for any routed task:

- `AGENTS.md`
- `data/project_state.json`
- `docs/PROJECT_STATE.md`
- files explicitly named by the user

Also read:

- `CLAUDE.md` for Claude Code or Claude skill work
- `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` for task-prompt generation
- `docs/audit_gate/PR_AUDIT_PROTOCOL.md` for PR audit or merge recommendation
- `docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md` for handoff work
- `docs/STRUCTURED_DETECTOR_RULES_DESIGN.md` for structured detector rules work, if present on the current branch
- `.agents/skills/cyber-immunizer-meta-devsecops-mitre-ultra/SKILL.md` or `.codex/skills/cyber-immunizer-meta-devsecops-mitre-ultra/SKILL.md` for defensive MITRE/security-audit work, if present

## First response after activation

Output this block before substantial work:

```text
ROUTE_DECISION
- task_type: <implementation | task_prompt | pr_audit | request_changes | ci_triage | structured_rules | skill_governance | security_audit | handoff | owner_decision>
- selected_track: <Codex | Claude | GPT audit | owner gate | mixed>
- current_state_sources_checked: <files/evidence>
- state_id: <value or unknown after attempted read>
- next_action: <value or unknown after attempted read>
- owner_approval_needed: <yes/no + reason>
- allowed_paths: <paths>
- forbidden_paths: <paths>
- verification_plan: <commands or no-run reason>
- next_atomic_action: <single next action>
```

If information cannot be read, state that as evidence failure and continue only if the task can be safely scoped without it.

## Routing rules

### 1. Owner-decision gate

Route here when the task involves live Gemini/API execution, paid-credit, workflow dispatch, promotion, ledger mutation, model/budget settings, or changing the safety boundary. Do not implement. Produce the exact approval needed, risk, and proposed command/file scope.

### 2. Task Prompt Architect track

Use for requests such as “タスクプロンプトを作成”, “REQUEST CHANGESプロンプト”, “次のCodex/Claudeタスク”. Do not edit code. Produce a single high-quality prompt with purpose, source evidence, allowed/forbidden files, invariants, tests, DoD, and stop conditions. Follow `docs/audit_gate/TASK_PROMPT_PROTOCOL.md`.

### 3. Codex implementation track

Use Codex for scoped, deterministic repository edits, test-backed fixes, CI repair, small refactors, and structured-rule implementation tasks. Keep one branch/PR to one purpose. Run the required tests and forbidden-path check. Create or update a PR with Summary, Canonical State checked, Changed files, Verification, No-API confirmation, residual risk, and next action.

### 4. Claude reasoning/refactor track

Use Claude first when the task requires broad design synthesis, large-context analysis, prompt validation, spec reconciliation, or refactor planning before implementation. Claude should produce a validated implementation prompt or audit report. Codex should execute only the atomic implementation slice.

### 5. PR audit track

Use for PR URLs, “監査”, “mergeしてよいか”, “Codex Review確認”. Do not rely on diff-only review. Inspect PR metadata, changed files, CI, review threads, Codex Review state, repository current-state sources, and relevant docs. Follow `docs/audit_gate/PR_AUDIT_PROTOCOL.md`.

### 6. CI triage track

Use when CI is red or uncertain. Classify failure source before patching: test regression, workflow/config, environment/tooling, stale branch, forbidden-path breach, or external service. Patch only within the task scope. After three scoped fix attempts, stop and propose rollback or owner decision.

### 7. Structured detector rules track

Use when the task mentions structured rules, schema validator, runtime evaluator, adapter, equivalence tests, or detector migration. Read the current branch state before assuming which PRs are merged. Preserve default `core.detector.inspect_request()` behavior unless explicit integration is approved. Require negative tests and equivalence/behavioral checks before any integration path.

### 8. Security/MITRE audit track

Use for defensive attack-surface mapping, MITRE tagging, dependency risk, DevSecOps hardening, or abuse-path reports. Keep content defensive and abstract. Do not include payloads, exploitation steps, scanner commands, or offensive automation. Convert findings into bounded remediation prompts.

### 9. Handoff track

Use when changing thread, delegating from Claude to Codex, or pausing a long run. Produce a copyable handoff containing branch, head SHA, PR state, current task in one sentence, done evidence, tests, CI, constraints, unresolved items, and next atomic action.

## Long-running agent loop

For long-running operation, use this loop:

1. Intake and state gate.
2. Route to the correct track.
3. Define a single atomic objective.
4. Create or reuse one branch for one PR purpose.
5. Implement the minimum diff.
6. Run verification and forbidden-path checks.
7. Open or update PR.
8. Request Codex Review when appropriate.
9. Fix P1/P2 findings before merge recommendation.
10. Write a task report when repository rules require it.
11. Produce a handoff if the work is not complete.

Detailed routing and long-run procedures are in:

- `references/routing-matrix.md`
- `references/long-run-playbook.md`

## Default verification

For typical implementation changes:

```bash
python -m pytest tests/ -q
git diff --name-only | grep -E '^(\.github|core|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true
```

For docs/skill-only changes, at minimum run a forbidden-path check and `git diff --check` if shell access is available. If tests are not run, state exactly why and classify the residual risk.

## Output discipline

Do not claim success without evidence. Every final report must separate:

- what was changed
- what was verified
- what was not verified
- what was intentionally not touched
- what needs owner approval
- next recommended atomic action
