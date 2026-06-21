# AI Entrypoint — Cyber-Immunizer

This is the first file an AI should read before working in this repository.

Do not move or rename this file. Do not replace existing docs with this file.
This file only points to existing documents; it does not duplicate their content.

---

## Purpose

This file provides a task-oriented reference table so that an AI can locate the
correct protocol or background document immediately, without scanning the whole
`docs/` tree.

Existing docs are not moved or restructured by this file. All paths below are
relative to the repository root.

---

## Status label definitions

These labels describe how a document should be used. They appear in document
headers as AI_DOC_META comment blocks.

| Label | Meaning |
|---|---|
| CURRENT | Use for current decision-making. |
| CANONICAL | Rule or definition source of truth. |
| PLANNING | Proposed or future architecture guidance; use for planning only and do not treat as implemented current state. |
| PROTOCOL | Procedure to follow. |
| RUNBOOK | Execution guide. |
| HISTORICAL | Background or completed-phase record. |
| SUPERSEDED | Replaced by later work; do not use as current truth. |

Note: core existing docs now carry AI_DOC_META blocks with these labels.
When auditing or planning work, use those metadata blocks together with this
entrypoint to distinguish current sources of truth, canonical rules, runbooks,
and historical background.

---

## Terminology rule

The canonical term for the final decision-maker is **Project Owner** (hiroshitanaka-creator).
Do not use `Human Owner`, `人間オーナー`, or a vague `人` to mean the final decision-maker.
See `docs/audit_gate/PR_AUDIT_PROTOCOL.md` (Terminology rule section) for the full rule.

---

## Mandatory orientation (read before any task)

Before selecting a row below, read **`docs/VALUE_DELIVERY_BLUEPRINT.md`**. It is the
CANONICAL definition of what counts as a high-level deliverable and "value" in this
project, and it is required reading for all task participants (Claude / GPT / Codex /
Project Owner). It does not override current-state SSOT (`data/project_state.json`,
`docs/PROJECT_STATE.md`, `data/genome.json`, machine evidence).

---

## Task reference table

| User request / task | Read first | Then read |
|---|---|---|
| Value / deliverable / "is this worth building" / 価値判断 / roadmap of outputs | docs/VALUE_DELIVERY_BLUEPRINT.md | docs/PROJECT_STATE.md, data/project_state.json |
| PR audit / merge decision | docs/audit_gate/PR_AUDIT_PROTOCOL.md | docs/AUDIT_CHARTER.md, docs/audit_gate/CHANGELOG.md |
| Implementation task prompt / Claude Code prompt / Codex task prompt | docs/audit_gate/TASK_PROMPT_PROTOCOL.md | docs/audit_gate/PR_AUDIT_PROTOCOL.md, docs/audit_gate/CHANGELOG.md, relevant canonical implementation/tests/docs for the target scope |
| GPT drift / pullback prompt | docs/audit_gate/PULLBACK_PROMPT.md | docs/audit_gate/CHANGELOG.md |
| Thread handoff / 新スレッド引き継ぎ / session continuation | docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md | CLAUDE.md, docs/audit_gate/CHANGELOG.md |
| Tool blocked / fallback / low-level GitHub operation | docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md | docs/audit_gate/PR_AUDIT_PROTOCOL.md |
| Phase status check | docs/PHASE_2_5_CLOSEOUT_AUDIT.md | docs/PHASE_2_COMPLETION_CHECKPOINT.md, docs/PHASE_2_PLAN.md |
| Phase 2.5 closeout / post-hardening audit | docs/PHASE_2_5_CLOSEOUT_AUDIT.md | docs/PHASE_3_GO_NO_GO_CHECKLIST.md |
| Project Owner roadmap / Phase 3–7 planning | docs/human用roadmap/phase3_to_phase7_roadmap.md | docs/PHASE_3_GO_NO_GO_CHECKLIST.md |
| Phase 3 readiness / Go-No-Go decision / activation decision | docs/PHASE_3_GO_NO_GO_CHECKLIST.md | docs/PHASE_2_5_CLOSEOUT_AUDIT.md, docs/API_ACTIVATION_CHECKLIST.md |
| Phase 3 paid-credit 現在地 / Gemini 3 runbook | docs/API_ACTIVATION_CHECKLIST.md | docs/API_ACTIVATION_RUNBOOK.md |
| Phase 3 paid-credit run 実行手順 / 初回 run 前確認 | docs/API_ACTIVATION_RUNBOOK.md | docs/API_ACTIVATION_CHECKLIST.md |
| Phase 3 activation PR #60–#62 内容確認 | docs/PHASE_3_GO_NO_GO_CHECKLIST.md | docs/API_ACTIVATION_RUNBOOK.md |
| API activation (only after Go/No-Go checklist approved) | docs/API_ACTIVATION_CHECKLIST.md | docs/API_ACTIVATION_RUNBOOK.md |
| Secret boundary / GEMINI_API_KEY wording | docs/API_ACTIVATION_CHECKLIST.md | docs/audit_gate/PR_AUDIT_PROTOCOL.md |
| Rollback/backtrack design | docs/ROLLBACK_BACKTRACK_DESIGN.md | docs/EVOLUTION_HISTORY_AUDIT.md |
| Offline sample / promote separation | docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md | docs/AUDIT_CHARTER.md |
| Autonomous Immune Loop architecture / lifecycle progress axis | docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md | docs/PROJECT_STATE.md, data/project_state.json |
| Adaptive Security Game / static-to-adaptive paradigm / future adaptive evaluation model | docs/ADAPTIVE_SECURITY_GAME_MODEL.md | README.md, docs/human用roadmap/phase3_to_phase7_roadmap.md, docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md |

---

## Mandatory before starting any task

1. Identify the user's current request in one sentence.
2. Select the matching row in the table above and read those documents.
3. For implementation task prompts, apply `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` before writing the prompt.
4. Before writing any implementation task prompt, complete the Task Prompt Gate v2 in `docs/audit_gate/TASK_PROMPT_PROTOCOL.md`.
   - Do not write a task prompt from diff-only inspection.
   - Do not rely on Codex Review to discover predictable edge cases.
   - If the self-score is below 98/100, stop and report the missing investigation instead of writing the prompt.
5. When receiving any task prompt, thread handoff prompt, or PR audit report from GPT
   or another agent, apply the corresponding reception gate in `CLAUDE.md` before
   starting work. Each gate requires a scoring receipt and, for task prompts, an intent
   confirmation before proceeding.
6. Do not propose work outside the stated scope.
7. If a tool operation is blocked or falls back, follow
   `docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md` and log it in the
   audit trail.
8. Claude Code reports and PR bodies are self-reports. Verify against GitHub
   state, current head SHA, diff, CI, and real files.
9. **Source Evidence intake check**: If the task prompt contains a `Source Evidence` block,
   verify each `file_path:start_line-end_line` citation against the actual file before
   starting any implementation. If a citation does not match — wrong lines, wrong content,
   or file does not exist — stop immediately, report the specific mismatch, and ask GPT to
   correct the task prompt. Do not proceed with implementation on an unchecked or
   mismatched citation.
