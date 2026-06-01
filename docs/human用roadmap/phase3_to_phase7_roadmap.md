<!--
AI_DOC_META
status: CURRENT
scope: Human Owner roadmap for Phase 3 through Phase 7. Thread handoff guidance for future AI instances.
use_for:
  - Human Owner planning for Phase 3 through Phase 7
  - thread handoff: what to paste at the start of a new AI thread
  - identifying which docs to read first in a new thread
  - understanding phase objectives, prohibitions, stop conditions, and completion conditions
do_not_use_for:
  - executing Phase 3 activation
  - connecting Gemini API
  - setting live_model_enabled=true
  - registering or modifying GitHub Secrets
  - replacing docs/PHASE_3_GO_NO_GO_CHECKLIST.md
related:
  - docs/AI_ENTRYPOINT.md
  - docs/PHASE_3_GO_NO_GO_CHECKLIST.md
  - docs/PHASE_2_5_CLOSEOUT_AUDIT.md
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/API_ACTIVATION_RUNBOOK.md
last_reviewed: 2026-05-31
AI_DOC_META_END
-->

# Human Owner Roadmap: Phase 3 through Phase 7

> **This is a Human Owner roadmap and thread handoff document.**
> This is not Phase 3 activation.
> This does not permit API connection.
> This does not permit GitHub Secrets setup.
> This does not permit `live_model_enabled=true`.
> This does not replace `docs/PHASE_3_GO_NO_GO_CHECKLIST.md`.

---

## 1. Purpose

This document provides the Human Owner with a roadmap for Phase 3 through Phase 7 of Project Cyber-Immunizer.

It also serves as a thread handoff document so that later AI instances (GPT, Claude, Codex) do not drift from the established project boundaries and safety constraints.

**Reading this document does not authorize any Phase 3 activation work.**

---

## 2. Thread Handoff Instructions

### What to paste at the start of a new AI thread

When starting a new AI work thread, paste the following context block at the beginning of the conversation:

```
Project: Cyber-Immunizer
Current state as of PR #53 (merged):
- Phase 2.5 hardening is complete.
- Phase 3 has NOT started.
- Gemini API is NOT connected.
- live_model_enabled=false.
- GitHub Secrets are Human Owner managed (not set by AI).
- No real Gemini API calls have been made by repository work.

Before doing any work, read these documents in order:
1. docs/AI_ENTRYPOINT.md
2. docs/PHASE_2_5_CLOSEOUT_AUDIT.md
3. docs/PHASE_3_GO_NO_GO_CHECKLIST.md
4. docs/human用roadmap/phase3_to_phase7_roadmap.md (this file)

Do not begin Phase 3 activation work without an explicit Human Owner GO to the Phase 3 gate question below.

Phase 3 gate question (must be asked and answered GO before activation work):
"ここからは Phase 3 activation PR です。
Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
進めてよいですか？"
```

### Which docs to read first in a new thread

| Order | Document | Purpose |
|---|---|---|
| 1 | docs/AI_ENTRYPOINT.md | Task routing — identifies correct doc for each task type |
| 2 | docs/PHASE_2_5_CLOSEOUT_AUDIT.md | Phase 2.5 completion record and current state |
| 3 | docs/PHASE_3_GO_NO_GO_CHECKLIST.md | Go/No-Go checklist before any Phase 3 activation PR |
| 4 | docs/human用roadmap/phase3_to_phase7_roadmap.md | This roadmap |
| 5 | docs/API_ACTIVATION_CHECKLIST.md | Detailed API activation requirements |
| 6 | docs/API_ACTIVATION_RUNBOOK.md | Phase 3 execution guide |

---

## 3. Current State (as of PR #53)

| Field | Value |
|---|---|
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 | Not started |
| Gemini API | Not connected |
| live_model_enabled | false |
| GitHub Secrets | Human Owner managed |
| Human Owner Phase 3 GO | Not given |

---

## 4. Phase 3 Activation Gate

Before any Phase 3 activation work begins, the following gate question **must be asked by the AI and answered GO by the Human Owner**:

> "ここからは Phase 3 activation PR です。
> Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
> 進めてよいですか？"

**Without explicit Human Owner GO to this exact question, Phase 3 activation work is prohibited.**

This gate applies to any work involving:
- Connecting the Gemini API
- Setting `live_model_enabled=true`
- Registering or modifying `GEMINI_API_KEY` in GitHub Secrets
- Scheduling paid API runs
- Any PR that includes Phase 3 activation steps

---

## 5. Phase Roadmap

### Phase 2.5 Closeout (Complete)

**Objective:** Harden the system after Phase 2, improve test coverage, and close out the pre-Phase-3 baseline.

**Completed PRs:** #46 through #53

**Completion conditions:**
- All Phase 2.5 PRs merged into main.
- All tests passing on current head.
- Phase 2.5 closeout audit document created (`docs/PHASE_2_5_CLOSEOUT_AUDIT.md`).
- Human Owner roadmap document created (this file).

**Status:** Complete as of PR #53.

---

### Phase 3 Go/No-Go Review (Next step — requires Human Owner)

**Objective:** Human Owner reviews all Go/No-Go conditions and decides whether to authorize Phase 3 activation.

**Key documents:**
- `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` — Repository-verifiable and Human Owner external checks
- `docs/API_ACTIVATION_CHECKLIST.md` — Detailed API activation requirements
- `docs/PHASE_2_5_CLOSEOUT_AUDIT.md` — Phase 2.5 completion evidence

**Prohibitions during this phase:**
- No Phase 3 activation work.
- No API connection.
- No `live_model_enabled=true`.
- No GitHub Secrets registration.
- No paid run scheduling.

**Stop conditions (No-Go):**
- Any No-Go condition in `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` section 5 is present.
- Human Owner has not given explicit GO to the Phase 3 gate question.
- CI is not green on current head SHA.

**Completion conditions:**
- Human Owner has reviewed all checklist items.
- Human Owner gives explicit GO to the Phase 3 gate question.
- All No-Go conditions are clear.
- A dedicated Phase 3 activation PR is opened (separate from this roadmap PR).

---

### Phase 3 Controlled API Activation (Future — requires Human Owner GO)

**Objective:** Connect the Gemini API under controlled, monitored conditions. First real API calls under budget caps.

**Prerequisites:**
- Explicit Human Owner GO to the Phase 3 gate question.
- All Go/No-Go checklist items resolved.
- GitHub Secrets registered by Human Owner out-of-band.
- Billing and budget verified by Human Owner out-of-band.
- CI green on activation PR head SHA.

**Prohibitions:**
- Phase 3 activation must be a dedicated PR — not bundled with unrelated changes.
- Activation PR must be reviewed by GPT Audit Gate.
- `live_model_enabled=true` must appear only in this dedicated activation PR.
- No broad docs cleanup mixed in with the activation PR.
- No detector behavior changes mixed in unless explicitly required.

**Stop conditions:**
- API call fails after multiple retries.
- Budget cap is exceeded or approaching.
- Ledger write fails after API success (expected behavior: return no patch; stop and investigate).
- Any unexpected system behavior during first live run.
- Human Owner decides to stop.

**Completion conditions:**
- First real Gemini API call succeeds in a controlled `workflow_dispatch` run.
- Ledger records the API usage correctly.
- Budget caps are respected.
- No patch is promoted unless all adoption gates pass.
- Human Owner reviews and accepts the first live run result.

---

### Phase 4 Controlled Evolution (Future)

**Objective:** Run repeated Gemini API-driven mutation cycles under monitoring. Evaluate candidate quality and adoption gate behavior with real model outputs.

**Prerequisites:** Phase 3 complete and stable.

**Key activities:**
- Multiple `workflow_dispatch` runs with `gemini-paid-credit` or `live-model` mode.
- Review of fitness scores, adoption gate pass/fail rates, and ledger entries.
- Human Owner monitors each run.
- Adjustment of genome parameters (budget caps, resource limits) as needed.

**Prohibitions:**
- No cron/scheduled live API runs until Human Owner explicitly authorizes.
- No promotion of candidates without Human Owner review (if adoption gate is not yet trusted).
- No weakening of AST policy or evaluation gates.
- No removal of resource limits.

**Stop conditions:**
- Repeated adoption gate failures without understood root cause.
- Budget unexpectedly consumed faster than expected.
- Ledger integrity issues.
- Human Owner decides to pause.

**Completion conditions:**
- Multiple successful mutation cycles with understood outcomes.
- Human Owner trusts the adoption gate behavior.
- Budget management is proven stable.

---

### Phase 5 Promotion Governance (Future)

**Objective:** Establish a repeatable, audited promotion process. Define when promoted detectors require Human Owner review vs. automated approval.

**Prerequisites:** Phase 4 complete and stable.

**Key activities:**
- Define promotion tiers: automated vs. Human Owner reviewed.
- Establish promotion audit log requirements.
- Add tests for promotion governance rules.
- Document rollback procedures for promoted detectors.

**Prohibitions:**
- No fully automated promotion without defined governance policy.
- No promotion of candidates with known policy gaps.

**Stop conditions:**
- Promotion audit log is incomplete or corrupted.
- Rollback procedure cannot be tested.

**Completion conditions:**
- Promotion governance policy documented and tested.
- Rollback procedure tested end-to-end (dry run acceptable).
- Human Owner approves governance policy.

---

### Phase 6 Observability / Audit Ledger (Future)

**Objective:** Improve observability of the evolution system. Enhance the audit ledger with richer metadata, dashboards, and alerting.

**Prerequisites:** Phase 5 complete.

**Key activities:**
- Extend `data/evolution_history.json` schema with richer audit fields.
- Add dashboard or summary report generation (read-only, no API).
- Add alerting conditions for budget approaching limit.
- Add ledger integrity checks that run in CI.

**Prohibitions:**
- No live API calls from the observability layer.
- No external data transmission.

**Completion conditions:**
- Enhanced evolution history schema documented and tested.
- Dashboard/report generation works offline.
- Ledger integrity CI check passes.

---

### Phase 7 Scaled Autonomous Operation (Future)

**Objective:** Enable more frequent, partially automated evolution cycles with strong governance and monitoring.

**Prerequisites:** Phases 4–6 complete. Human Owner explicitly authorizes increased automation.

**Key activities:**
- Enable cron-scheduled `gemini-paid-credit` runs (requires explicit Human Owner authorization).
- Increase `max_model_requests_per_run` carefully (requires genome PR review).
- Expand AST policy whitelist as needed (requires dedicated whitelist PR).
- Extend regression test suite to match expanded mutation space.

**Prohibitions:**
- No cron activation without explicit Human Owner authorization.
- No `max_model_requests_per_run` increase without genome PR review.
- No AST policy relaxation without documented justification.
- No weakening of adoption gates.

**Stop conditions:**
- Budget consumed faster than modeled.
- Adoption gate failures spike.
- Unexpected candidate promotions.
- Human Owner decides to scale back.

**Completion conditions:**
- Cron runs stable across multiple weeks.
- Budget under control.
- Human Owner satisfied with automation level.

---

## 6. Persistent Prohibitions (All Phases)

The following prohibitions apply across all phases, regardless of phase:

| Prohibition | Reason |
|---|---|
| Never paste `GEMINI_API_KEY` value into chat, PR body, logs, or repository files | Secret boundary — keys in repository files are a security violation |
| Never set `live_model_enabled=true` outside a dedicated activation PR | Prevents accidental live API calls |
| Never weaken AST policy without a dedicated whitelist PR | AST policy is a safety boundary |
| Never weaken adoption gate conditions | Adoption gate prevents unsafe promotions |
| Never run paid API calls from non-main branches | Prevents accidental cost from feature branches |
| Never use external AI audit outputs as Phase 3 activation approval | Audit outputs are supporting evidence only |

---

## Related Documents

- [docs/AI_ENTRYPOINT.md](../AI_ENTRYPOINT.md) — Task routing entrypoint for AI
- [docs/PHASE_3_GO_NO_GO_CHECKLIST.md](../PHASE_3_GO_NO_GO_CHECKLIST.md) — Phase 3 Go/No-Go readiness checklist
- [docs/PHASE_2_5_CLOSEOUT_AUDIT.md](../PHASE_2_5_CLOSEOUT_AUDIT.md) — Phase 2.5 closeout audit
- [docs/API_ACTIVATION_CHECKLIST.md](../API_ACTIVATION_CHECKLIST.md) — Detailed API activation requirements
- [docs/API_ACTIVATION_RUNBOOK.md](../API_ACTIVATION_RUNBOOK.md) — API activation runbook

---

*This is a Human Owner roadmap for Project Cyber-Immunizer.*
*Phase 3 not started / API not connected / live_model_enabled false.*
*This document does not authorize Phase 3 activation.*
*Created: 2026-05-31*
