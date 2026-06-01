<!--
AI_DOC_META
status: CURRENT
scope: Phase 2.5 hardening closeout audit. Records all Phase 2.5 PRs (#46–#53) and current non-activation state.
use_for:
  - checking Phase 2.5 hardening completion status
  - confirming Phase 3 has not started
  - verifying API is not connected
  - reviewing Phase 2.5 PR ledger for audit evidence
do_not_use_for:
  - executing Phase 3 activation steps
  - setting live_model_enabled=true
  - connecting Gemini API
  - registering or modifying GitHub Secrets
  - treating audit inputs as Phase 3 activation approval
related:
  - docs/AI_ENTRYPOINT.md
  - docs/PHASE_3_GO_NO_GO_CHECKLIST.md
  - docs/human用roadmap/phase3_to_phase7_roadmap.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
last_reviewed: 2026-05-31
AI_DOC_META_END
-->

# Phase 2.5 Closeout Audit

> **This document records Phase 2.5 hardening completion through PR #53.**
> Phase 3 is not started.
> Gemini API is not connected.
> live_model_enabled remains false.
> This document does not authorize Phase 3 activation.
> This PR is docs/progress/navigation/test-only.

---

## 1. Purpose

This document records the completion of Phase 2.5 hardening and serves as an auditable closeout for the work completed through PR #53.

- This is a progress record, not an execution runbook.
- Grok, Claude Code, and GPT audit inputs referenced here are supporting evidence only.
- Audit outputs from external tools are not treated as Phase 3 activation approval.
- This document prepares documentation for a future Human Owner Phase 3 Go/No-Go review.

---

## 2. Explicit Non-Activation State

| Field | Value |
|---|---|
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 | Not started |
| Gemini API connection | Not connected |
| live_model_enabled | false |
| Gemini API real calls | Not executed by repository work |
| GitHub Secrets | Human Owner controlled; state not asserted by repository files |
| Human Owner Phase 3 GO | Not given |

> **This document does not authorize Phase 3 activation.**
> GitHub Secrets are Human Owner controlled.
> live_model_enabled remains false.
> No real Gemini API calls have been made by repository work.

---

## 3. Phase 2.5 Hardening Ledger

The following PRs constitute the Phase 2.5 hardening series. All are merged into `main`.

| PR | Title / Scope |
|---|---|
| #46 | Conservative token estimation / output token cap accounting |
| #47 | `evaluate_candidate` resource limits |
| #48 | Persist-ledger rebase retry / paid-credit main-only guard |
| #49 | AST structural guard / whitelist roadmap |
| #50 | `apply_mutation` atomic write |
| #51 | Detector large-payload regression |
| #52 | Indicator case normalization |
| #53 | Ledger write failure after API success behavior tests |

All Phase 2.5 PRs are docs/tests/hardening-only where stated. No PR in this series connects the Gemini API, sets `live_model_enabled=true`, or schedules paid runs.

---

## 4. Hardening Summary

### PR #46 — Conservative token estimation / output token cap accounting

Added conservative token estimation logic using ceiling division (`ceil(chars / 4)`) and enforced output token cap accounting in the API budget module. Ensures that cost estimates are never under-counted.

### PR #47 — `evaluate_candidate` resource limits

Added resource limit enforcement in `evaluate_candidate` (via `resource.setrlimit`) to bound memory, CPU time, and file descriptor usage during candidate evaluation. Candidates that exceed limits are rejected at the evaluation gate.

### PR #48 — Persist-ledger rebase retry / paid-credit main-only guard

Added retry logic for ledger persistence on rebase conflicts, and added a guard that prevents `gemini-paid-credit` mode from running on non-main branches. Prevents accidental paid API use in feature branches.

### PR #49 — AST structural guard / whitelist roadmap

Added structural AST guards including source size, node count, depth, literal, and collection limits. Added a whitelist roadmap document (`docs/AST_POLICY_WHITELIST_ROADMAP.md`) for future safe-node expansion. Parser `MemoryError`, `RecursionError`, and syntax-path failures now return structured validation failures.

### PR #50 — `apply_mutation` atomic write

Made `apply_mutation` candidate writes atomic using a temp-file-then-rename pattern. Prevents partial writes from leaving the repository in a corrupted state if the process is interrupted.

### PR #51 — Detector large-payload regression

Added regression tests for detector behavior under large payload inputs. Confirms that the detector does not time out, crash, or produce incorrect results when processing payloads at or near the size boundary.

### PR #52 — Indicator case normalization

Added contract tests that enforce consistent case normalization for threat indicators. Ensures that indicator matching is not bypassed by mixed-case or uppercase variants of known threat strings.

### PR #53 — Ledger write failure after API success behavior tests

Added behavior tests covering the scenario where the Gemini API call succeeds but the subsequent ledger write fails. Confirmed that in this scenario no patch is returned and the failure is reported without hiding the API usage attempt.

---

## 5. Audit Input Classification

The following audit tools contributed review inputs during Phase 2.5. Their outputs are supporting evidence only.

| Source | Role |
|---|---|
| Grok | External audit review input — supporting evidence only |
| Claude Code | Implementation and test authorship |
| GPT (Codex / Audit Gate) | Structural review feedback — supporting evidence only |

**None of the above inputs constitute a Human Owner Phase 3 GO decision.**
**Audit outputs do not authorize Phase 3 activation.**

---

## 6. What Is Not Done

The following items are explicitly not part of this closeout:

- Phase 3 activation has not started.
- Gemini API has not been connected.
- `live_model_enabled` has not been set to `true`.
- `GEMINI_API_KEY` has not been registered in GitHub Secrets by repository work.
- No real Gemini API calls have been executed by repository workflows.
- No paid runs have been scheduled.
- This PR does not contain workflow permission changes.
- This PR does not contain production code changes.
- This PR does not contain `data/*.json` changes.

---

## 7. Preparation for Phase 3 Go/No-Go Review

This document prepares the documentation baseline for a future Human Owner Phase 3 Go/No-Go review.

Before Phase 3 may begin, the Human Owner must review:

- [docs/PHASE_3_GO_NO_GO_CHECKLIST.md](./PHASE_3_GO_NO_GO_CHECKLIST.md) — Go/No-Go readiness checklist
- [docs/human用roadmap/phase3_to_phase7_roadmap.md](./human用roadmap/phase3_to_phase7_roadmap.md) — Human Owner roadmap for Phase 3–7
- [docs/API_ACTIVATION_CHECKLIST.md](./API_ACTIVATION_CHECKLIST.md) — Detailed API activation checklist
- [docs/API_ACTIVATION_RUNBOOK.md](./API_ACTIVATION_RUNBOOK.md) — API activation runbook

No Phase 3 work may begin without explicit Human Owner GO.

---

## Related Documents

- [docs/AI_ENTRYPOINT.md](./AI_ENTRYPOINT.md) — Task routing entrypoint for AI
- [docs/PHASE_3_GO_NO_GO_CHECKLIST.md](./PHASE_3_GO_NO_GO_CHECKLIST.md) — Phase 3 Go/No-Go readiness audit
- [docs/human用roadmap/phase3_to_phase7_roadmap.md](./human用roadmap/phase3_to_phase7_roadmap.md) — Human Owner roadmap for Phase 3–7
- [docs/PHASE_2_COMPLETION_CHECKPOINT.md](./PHASE_2_COMPLETION_CHECKPOINT.md) — Phase 2 completion checkpoint

---

*This document records Phase 2.5 hardening completion for Project Cyber-Immunizer.*
*Phase 2.5 complete through PR #53.*
*Phase 3 not started / API not connected / live_model_enabled false.*
*This document does not authorize Phase 3 activation.*
