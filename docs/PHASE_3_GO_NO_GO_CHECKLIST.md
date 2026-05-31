<!--
AI_DOC_META
status: CANONICAL
scope: Phase 3 Go/No-Go readiness audit before any activation PR.
use_for:
  - deciding whether a Phase 3 activation PR may be opened
  - separating repository-verifiable checks from Human Owner external checks
  - identifying No-Go conditions before API activation
  - recording a Human Owner Go/No-Go decision
do_not_use_for:
  - executing Phase 3 activation
  - setting live_model_enabled=true
  - registering or modifying GitHub Secrets
  - calling Gemini API
related:
  - docs/AI_ENTRYPOINT.md
  - docs/PHASE_2_5_CLOSEOUT_AUDIT.md
  - docs/human用roadmap/phase3_to_phase7_roadmap.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/API_ACTIVATION_RUNBOOK.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
last_reviewed: 2026-05-31
AI_DOC_META_END
-->

# Phase 3 Go/No-Go Readiness Audit

> **This document is not Phase 3 activation.**
> Phase 3 is not started.
> API is not connected.
> live_model_enabled must remain false until a dedicated Phase 3 activation PR is approved.
> Human Owner explicit approval is required before any Phase 3 activation PR.

---

## 1. Purpose

This document is a Go/No-Go readiness checklist that must be reviewed before any Phase 3 activation PR is opened.

- This is not an execution runbook. Do not use it to perform Phase 3 activation steps.
- This checklist separates repository-verifiable checks from Human Owner external checks.
- This document does not record API keys or secret values. Secret values must not appear in any repository file, PR body, chat, or log.
- Before creating a Phase 3 activation PR, GPT Audit Gate and Human Owner must confirm all Go conditions and confirm there are no No-Go conditions.

---

## 2. Current Non-Activation State

| Field | Value |
|---|---|
| Phase 2 | Complete |
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 | Not started |
| API connection | Not connected |
| live_model_enabled | false |
| Gemini API real calls | Not executed by repository work |
| GitHub Secrets state | Not asserted by repository files; Human Owner controlled |
| Human Owner Phase 3 GO | Not given |
| Human Owner external verification | Human Owner controls external secret and billing verification |

> Phase 3 is not started. API is not connected. live_model_enabled remains false.
> GitHub Secrets state is not asserted by repository files.
> Human Owner verifies GitHub Secrets state out-of-band before Phase 3.
>
> See [docs/PHASE_2_5_CLOSEOUT_AUDIT.md](./PHASE_2_5_CLOSEOUT_AUDIT.md) for the Phase 2.5 hardening ledger.
> See [docs/human用roadmap/phase3_to_phase7_roadmap.md](./human用roadmap/phase3_to_phase7_roadmap.md) for Human Owner roadmap guidance.

---

## 3. Repository-Verifiable Readiness Checks

The following items can be verified from repository files without external access.

- [ ] Phase 2.5 hardening PRs #46–#53 completed and reflected in current docs
- [ ] docs/PHASE_2_5_CLOSEOUT_AUDIT.md exists and records Phase 2.5 completion
- [ ] docs/human用roadmap/phase3_to_phase7_roadmap.md exists and contains thread handoff guidance
- [ ] docs/AI_ENTRYPOINT.md routes Phase 3 readiness work to this checklist
- [ ] docs/AI_ENTRYPOINT.md routes Phase 2.5 closeout queries to docs/PHASE_2_5_CLOSEOUT_AUDIT.md
- [ ] README docs map includes this checklist (docs/PHASE_3_GO_NO_GO_CHECKLIST.md)
- [ ] docs/audit_gate/PR_AUDIT_PROTOCOL.md exists and is referenced
- [ ] docs/audit_gate/CHANGELOG.md exists and is referenced
- [ ] docs/PHASE_2_COMPLETION_CHECKPOINT.md states Phase 3 not started
- [ ] docs/API_ACTIVATION_CHECKLIST.md exists
- [ ] docs/API_ACTIVATION_RUNBOOK.md exists
- [ ] normal CI (ci.yml) is read-only (contents: read only)
- [ ] normal CI does not call Gemini API
- [ ] workflow permissions must be re-checked in the Phase 3 activation PR before any activation
- [ ] promote Human Owner approval gate (promote_approved=true) is enforced in immunization_loop.yml
- [ ] GEMINI_API_KEY step-level secret separation is in place (noop/offline-sample steps receive no API key)
- [ ] ledger missing or corrupt or write failure fails closed (strict_load_ledger enforced)
- [ ] Gemini paid-credit path has explicit timeout, bounded transient retry, and max_model_requests_per_run alignment
- [ ] AST source size, node count, depth, literal, and collection limits are enforced fail-closed
- [ ] parser MemoryError and RecursionError and syntax-path failures return structured validation failures
- [ ] runtime allocation risks (computed repeat multipliers, unbounded join generators) are rejected before evaluation and promote
- [ ] apply_mutation safe output path guard is in place (output_root symlink rejection, traversal rejection)
- [ ] apply_mutation atomic write in place (PR #50)
- [ ] API success followed by ledger write failure returns no patch (PR #53 behavior tests pass)
- [ ] evaluate_candidate resource limits enforced (PR #47)
- [ ] detector large payload regression tests pass (PR #51)
- [ ] indicator case normalization tests pass (PR #52)
- [ ] docs tests cover current state (python -m pytest passes on current head SHA)

---

## 4. Human Owner External Readiness Checks

The following items cannot be verified from repository files. Human Owner must verify these out-of-band before any Phase 3 activation PR is opened.

- [ ] GitHub Secrets — GEMINI_API_KEY is registered in GitHub Secrets (verified out-of-band by Human Owner)
- [ ] GitHub Secrets — GEMINI_API_KEY value is valid and current (verified out-of-band by Human Owner)
- [ ] GitHub Secrets — GEMINI_API_KEY value has not been pasted into chat, PR body, logs, or repository files
- [ ] Google Cloud Billing — billing is active and linked to the correct project
- [ ] Budget caps — monthly budget cap is set (monthly_api_budget_usd > 0 in genome.json)
- [ ] Budget caps — daily budget cap is set (daily_api_budget_usd > 0 in genome.json)
- [ ] Budget alerts — Google Cloud billing alerts are configured
- [ ] Google AI / Gemini API quota and paid tier status verified
- [ ] Initial live-run maximum cost accepted by Human Owner
- [ ] Initial live-run maximum request count accepted by Human Owner
- [ ] Failure stop criteria — Human Owner has defined when to stop the first live run
- [ ] Human Owner can monitor the first live run in real time

---

## 5. No-Go Conditions

**If any one of the following conditions is true, Phase 3 activation must not proceed.**

- Human Owner explicit approval to open a Phase 3 activation PR is missing
- GitHub Secrets state has not been verified out-of-band by Human Owner
- GEMINI_API_KEY value was pasted into chat, PR body, logs, or repository files
- Google Cloud billing, budget caps, or billing alerts have not been verified by Human Owner
- Workflow permission state is unclear or has not been re-checked for the activation PR
- live_model_enabled=true appears outside a dedicated Phase 3 activation PR
- API activation steps are mixed with unrelated code changes in the same PR
- A Codex unresolved non-outdated inline thread remains on the activation PR
- GPT Audit Gate has not reviewed the current head SHA before the activation PR is opened
- CI is not green on current head SHA (python -m pytest must pass)
- Budget or ledger fail-closed behavior has been weakened
- Normal CI (ci.yml) would call Gemini API
- Generated candidate code would execute in a write-permission job
- Human Owner cannot monitor the first live run
- Rollback and stop procedure is unclear or undocumented

---

## 6. Required Activation PR Boundary

When all Go conditions are met and no No-Go conditions exist, a Phase 3 activation PR may be opened. That PR must satisfy all of the following:

- Must be a dedicated PR — Phase 3 activation must not be bundled with unrelated changes
- Must be explicitly approved by Human Owner before merge
- Must be reviewed by GPT Audit Gate
- Must check all Codex inline threads (resolve or explicitly defer non-outdated threads)
- Must re-check workflow permissions (the permissions audit must be re-performed for the activation PR diff)
- Must not include unrelated refactors
- Must not include broad docs cleanup not required for activation
- Must not include detector behavior changes not required for activation
- Must not include data/*.json mutations unless explicitly justified for activation
- Must preserve budget and ledger fail-closed behavior
- Must not set live_model_enabled=true outside this dedicated activation PR

---

## 7. Go / No-Go Decision Record Template

Human Owner fills this table before opening a Phase 3 activation PR.

| Item | Decision |
|---|---|
| Human Owner approval to open Phase 3 activation PR | GO / NO-GO |
| GitHub Secrets verified out-of-band | GO / NO-GO |
| Google billing and budget verified | GO / NO-GO |
| Initial live-run max cost accepted | GO / NO-GO |
| Initial live-run max request count accepted | GO / NO-GO |
| GPT Audit Gate reviewed readiness checklist | GO / NO-GO |
| Codex review required for activation PR | GO / NO-GO |
| Final decision | GO / NO-GO |

**If any item is NO-GO, Phase 3 activation must not proceed.**

---

## 8. Explicit Next-Step Gate

Before creating a Phase 3 activation PR, GPT Audit Gate must ask the Human Owner:

> "ここからは Phase 3 activation PR です。
> Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
> 進めてよいですか？"

Without an explicit Human Owner "GO", Phase 3 activation must not proceed.

---

## Related Documents

- [docs/AI_ENTRYPOINT.md](./AI_ENTRYPOINT.md) — Task routing entrypoint for AI
- [docs/PHASE_2_5_CLOSEOUT_AUDIT.md](./PHASE_2_5_CLOSEOUT_AUDIT.md) — Phase 2.5 closeout audit (PR #46–#53 ledger)
- [docs/human用roadmap/phase3_to_phase7_roadmap.md](./human用roadmap/phase3_to_phase7_roadmap.md) — Human Owner roadmap for Phase 3–7
- [docs/PHASE_2_COMPLETION_CHECKPOINT.md](./PHASE_2_COMPLETION_CHECKPOINT.md) — Phase 2 completion checkpoint and current state
- [docs/API_ACTIVATION_CHECKLIST.md](./API_ACTIVATION_CHECKLIST.md) — Detailed API activation checklist
- [docs/API_ACTIVATION_RUNBOOK.md](./API_ACTIVATION_RUNBOOK.md) — API activation runbook (Phase 3 execution guide)
- [docs/audit_gate/PR_AUDIT_PROTOCOL.md](./audit_gate/PR_AUDIT_PROTOCOL.md) — PR audit protocol
- [tests/test_phase3_go_no_go_checklist_docs.py](../tests/test_phase3_go_no_go_checklist_docs.py) — Tests for this document

---

*This document is the Phase 3 Go/No-Go readiness audit for Project Cyber-Immunizer.*
*Created: 2026-05-31*
*Phase 3 not started / API not connected / live_model_enabled false*
