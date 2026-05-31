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
| PROTOCOL | Procedure to follow. |
| RUNBOOK | Execution guide. |
| HISTORICAL | Background or completed-phase record. |
| SUPERSEDED | Replaced by later work; do not use as current truth. |

Note: core existing docs now carry AI_DOC_META blocks with these labels.
When auditing or planning work, use those metadata blocks together with this
entrypoint to distinguish current sources of truth, canonical rules, runbooks,
and historical background.

---

## Task reference table

| User request / task | Read first | Then read |
|---|---|---|
| PR audit / merge decision | docs/audit_gate/PR_AUDIT_PROTOCOL.md | docs/AUDIT_CHARTER.md, docs/audit_gate/CHANGELOG.md |
| GPT drift / pullback prompt | docs/audit_gate/PULLBACK_PROMPT.md | docs/audit_gate/CHANGELOG.md |
| Tool blocked / fallback / low-level GitHub operation | docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md | docs/audit_gate/PR_AUDIT_PROTOCOL.md |
| Phase status check | docs/PHASE_2_COMPLETION_CHECKPOINT.md | docs/PHASE_2_PLAN.md |
| API activation | docs/API_ACTIVATION_CHECKLIST.md | docs/API_ACTIVATION_RUNBOOK.md |
| Secret boundary / GEMINI_API_KEY wording | docs/API_ACTIVATION_CHECKLIST.md | docs/audit_gate/PR_AUDIT_PROTOCOL.md |
| Rollback/backtrack design | docs/ROLLBACK_BACKTRACK_DESIGN.md | docs/EVOLUTION_HISTORY_AUDIT.md |
| Offline sample / promote separation | docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md | docs/AUDIT_CHARTER.md |

---

## Mandatory before starting any task

1. Identify the user's current request in one sentence.
2. Select the matching row in the table above and read those documents.
3. Do not propose work outside the stated scope.
4. If a tool operation is blocked or falls back, follow
   `docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md` and log it in the
   audit trail.
5. Claude Code reports and PR bodies are self-reports. Verify against GitHub
   state, current head SHA, diff, CI, and real files.
