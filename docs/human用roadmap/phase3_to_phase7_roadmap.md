<!--
AI_DOC_META
status: CURRENT
scope: Project Owner roadmap for Phase 3 through Phase 7. Thread handoff guidance for future AI instances. Updated to reflect Phase 3 activation (PR #58-#62 merged, first paid-credit run pending).
use_for:
  - Project Owner planning for Phase 3 paid-credit execution and Phase 4–7
  - thread handoff: what to paste at the start of a new AI thread
  - identifying which docs to read first in a new thread
  - understanding Phase 3 current state (activation complete, first run pending)
  - aligning Phase 4+ planning with the Adaptive Security Game vision defined in docs/ADAPTIVE_SECURITY_GAME_MODEL.md
do_not_use_for:
  - executing paid-credit runs (Project Owner triggers manually)
  - setting promote_approved=true before reviewing first run results
  - registering or modifying GitHub Secrets
  - replacing docs/PHASE_3_GO_NO_GO_CHECKLIST.md
  - claiming the adaptive tournament or adaptive metrics are implemented
related:
  - docs/AI_ENTRYPOINT.md
  - docs/PHASE_3_GO_NO_GO_CHECKLIST.md
  - docs/PHASE_2_5_CLOSEOUT_AUDIT.md
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/API_ACTIVATION_RUNBOOK.md
  - docs/ADAPTIVE_SECURITY_GAME_MODEL.md
  - README.md
last_reviewed: 2026-06-03
AI_DOC_META_END
-->

# Project Owner Roadmap: Phase 3 through Phase 7

> **This is a Project Owner roadmap and thread handoff document.**
> This is not Phase 3 activation.
> This does not permit API connection.
> This does not permit GitHub Secrets setup.
> This does not permit `live_model_enabled=true`.
> This does not replace `docs/PHASE_3_GO_NO_GO_CHECKLIST.md`.

---

## 1. Purpose

This document provides the Project Owner with a roadmap for Phase 3 through Phase 7 of Project Cyber-Immunizer.

It also serves as a thread handoff document so that later AI instances (GPT, Claude, Codex) do not drift from the established project boundaries and safety constraints.

**Reading this document does not authorize any Phase 3 activation work.**

---

## 2a. Adaptive Security Game planning layer

PR #106 added [`docs/ADAPTIVE_SECURITY_GAME_MODEL.md`](../ADAPTIVE_SECURITY_GAME_MODEL.md) as the detailed planning source for the static-to-adaptive paradigm shift. PR #109 surfaced this paradigm as a high-visibility declaration in `README.md`.

The current fitness score formula and adoption gate remain the safety floor for all phases. They define the minimum correctness requirement (regression-free, low FP) and must not be weakened. This is unchanged.

Future Phase 4+ planning should treat `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` as the guiding architecture layer for dynamic adaptive evaluation — covering evaluation tiers, adversarial non-stationarity, memory model concepts, and adaptive tournament scoring that goes beyond static corpus fitness. The roadmap phases below should be read with that planning layer in mind.

**This is planning guidance only.** The adaptive tournament, new evaluation metrics, new gates, and memory model described in `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` are not implemented. No runtime state, promotion rules, genome, ledger, or workflow behavior has changed.

---

## 2. Thread Handoff Instructions

### What to paste at the start of a new AI thread

When starting a new AI work thread, paste the following context block at the beginning of the conversation:

```
Project: Cyber-Immunizer
Current state as of PR #62 (merged into main on 2026-06-03):
- Phase 3 activation PRs #58–#62 are ALL merged into main.
- live_model_enabled=true (PR #58).
- Primary model: gemini-3-flash-preview (PR #62).
- Fallback model: gemini-3.1-flash-lite (PR #62).
- Gemini API FIRST LIVE CALL: NOT YET EXECUTED.
- paid-credit run: NOT YET EXECUTED — Project Owner triggers 1 run manually.
- promote_approved: false — prohibited until first run result reviewed.
- GitHub Secrets are Project Owner managed (not set by AI).

Before doing any work, read these documents in order:
1. docs/AI_ENTRYPOINT.md
2. docs/PHASE_3_GO_NO_GO_CHECKLIST.md (Section 2a: Phase 3 Activation Record)
3. docs/API_ACTIVATION_CHECKLIST.md (Section: Phase 3 Paid-Credit 現在地)
4. docs/API_ACTIVATION_RUNBOOK.md (Section: Gemini 3 Flash Preview 運用ランブック)
5. docs/human用roadmap/phase3_to_phase7_roadmap.md (this file)

IMPORTANT: Do NOT set promote_approved=true before reviewing first run results.
IMPORTANT: Do NOT execute multiple paid-credit runs without reviewing each result.
IMPORTANT: Do NOT call Gemini API directly from docs or scripts work.
```

### Historical thread handoff (Phase 2.5 era — for reference only)

```
Project: Cyber-Immunizer
Current state as of PR #53 (merged):
- Phase 2.5 hardening is complete.
- Phase 3 has NOT started.
- Gemini API is NOT connected.
- live_model_enabled=false.
- GitHub Secrets are Project Owner managed (not set by AI).
- No real Gemini API calls have been made by repository work.

(This block is now HISTORICAL. See the current state block above for PR #62 state.)
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
| 7 | docs/ADAPTIVE_SECURITY_GAME_MODEL.md | Adaptive Security Game planning model — static-to-adaptive paradigm, evaluation tiers, safety constraints, and future adaptive metrics (planning only; not implemented) |

---

## 3. Current State (as of PR #62 / 2026-06-03)

| Field | Value |
|---|---|
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 activation PRs | ✅ Complete (#58–#62 merged) |
| Past paid-credit API call records | Exist (see `data/api_usage_ledger.json`) |
| Gemini 3 Flash Preview controlled run | **Not yet executed** — gemini-3-flash-preview 構成での確認 run が次ステップ |
| Gemini API | live_model_enabled=true; past API calls recorded; gemini-3-flash-preview run pending |
| live_model_enabled | true (PR #58) |
| Primary model | gemini-3-flash-preview (PR #62) |
| Fallback model | gemini-3.1-flash-lite (PR #62) |
| promote_approved | false (prohibited until first run result reviewed) |
| GitHub Secrets | Project Owner managed |
| Project Owner Phase 3 GO | Given (PR #58 merged with Project Owner approval) |

### Phase 3 Activation PR Summary

| PR | Status | Key Change |
|---|---|---|
| PR #58 | ✅ Merged | live_model_enabled=true, --live-model blocked, gemini-paid-credit path active |
| PR #59 | ✅ Merged | Gemini ClientError safe diagnostics (allowlist-based) |
| PR #60 | ✅ Merged | model_name: gemini-3.1-flash-lite (404 fix) |
| PR #61 | ✅ Merged | replacement_code Python syntax validation at Propose stage |
| PR #62 | ✅ Merged | Primary model: gemini-3-flash-preview, ThinkingConfig, thinking tokens in ledger |

## 3a. Historical State (as of PR #53)

| Field | Value |
|---|---|
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 | Not started |
| Gemini API | Not connected |
| live_model_enabled | false |
| GitHub Secrets | Project Owner managed |
| Project Owner Phase 3 GO | Not given |

---

## 4. Phase 3 Activation Gate

Before any Phase 3 activation work begins, the following gate question **must be asked by the AI and answered GO by the Project Owner**:

> "ここからは Phase 3 activation PR です。
> Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
> 進めてよいですか？"

**Without explicit Project Owner GO to this exact question, Phase 3 activation work is prohibited.**

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
- Project Owner roadmap document created (this file).

**Status:** Complete as of PR #53.

---

### Phase 3 Go/No-Go Review (Complete ✅)

**Status: Complete.** Project Owner reviewed all Go/No-Go conditions and authorized Phase 3 activation.

**Key documents:**
- `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` — Section 2a: Phase 3 Activation Record
- `docs/API_ACTIVATION_CHECKLIST.md` — Section: Phase 3 Paid-Credit 現在地
- `docs/PHASE_2_5_CLOSEOUT_AUDIT.md` — Phase 2.5 completion evidence

---

### Phase 3 Controlled API Activation (In Progress — first run pending)

**Objective:** Run first Gemini API paid-credit call under controlled, monitored conditions.

**Current status:**
- All activation PRs (#58–#62) merged.
- `live_model_enabled=true`, primary model `gemini-3-flash-preview`.
- **First paid-credit run NOT YET EXECUTED.**
- `promote_approved=false` — auto-promote prohibited.

**Next step for Project Owner:**
1. Confirm PR #62 merged into main (`data/genome.json` → `gemini-3-flash-preview`)
2. Merge this docs PR
3. Run `workflow_dispatch` → mode: `gemini-paid-credit`, `promote_approved=false` — **1 run only**
4. Review: ledger artifact, candidate patch, apply/evaluate result
5. Decide next action based on result (promote / fix / halt)

**Prohibitions:**
- Do not set `promote_approved=true` before reviewing first run results.
- Do not execute multiple paid-credit runs without reviewing each result.
- Do not call Gemini API outside of `workflow_dispatch` manual trigger.

**Stop conditions:**
- API call fails after multiple retries.
- Budget cap is exceeded or approaching.
- Ledger write fails after API success (expected behavior: return no patch; stop and investigate).
- Any unexpected system behavior during first live run.
- Project Owner decides to stop.

**Completion conditions:**
- First real Gemini API call succeeds in a controlled `workflow_dispatch` run.
- Ledger records the API usage correctly (including thinking tokens).
- Budget caps are respected.
- No patch is promoted unless all adoption gates pass AND Project Owner reviews.
- Project Owner reviews and accepts the first live run result.

---

### Phase 4 Controlled Evolution (Future)

**Objective:** Run repeated Gemini API-driven mutation cycles under monitoring. Evaluate candidate quality and adoption gate behavior with real model outputs.

**Prerequisites:** Phase 3 complete and stable.

**Key activities:**
- Multiple `workflow_dispatch` runs with `gemini-paid-credit` or `live-model` mode.
- Review of fitness scores, adoption gate pass/fail rates, and ledger entries.
- Project Owner monitors each run.
- Adjustment of genome parameters (budget caps, resource limits) as needed.
- Use `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` as planning guidance for separating the current fitness/adoption gate safety floor from future adaptive tournament scoring. This does not mean adaptive scoring is implemented in Phase 4.

**Prohibitions:**
- No cron/scheduled live API runs until Project Owner explicitly authorizes.
- No promotion of candidates without Project Owner review (if adoption gate is not yet trusted).
- No weakening of AST policy or evaluation gates.
- No removal of resource limits.

**Stop conditions:**
- Repeated adoption gate failures without understood root cause.
- Budget unexpectedly consumed faster than expected.
- Ledger integrity issues.
- Project Owner decides to pause.

**Completion conditions:**
- Multiple successful mutation cycles with understood outcomes.
- Project Owner trusts the adoption gate behavior.
- Budget management is proven stable.

---

### Phase 5 Promotion Governance (Future)

**Objective:** Establish a repeatable, audited promotion process. Define when promoted detectors require Project Owner review vs. automated approval.

**Prerequisites:** Phase 4 complete and stable.

**Key activities:**
- Define promotion tiers: automated vs. Project Owner reviewed.
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
- Project Owner approves governance policy.

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

**Prerequisites:** Phases 4–6 complete. Project Owner explicitly authorizes increased automation.

**Key activities:**
- Enable cron-scheduled `gemini-paid-credit` runs (requires explicit Project Owner authorization).
- Increase `max_model_requests_per_run` carefully (requires genome PR review).
- Expand AST policy whitelist as needed (requires dedicated whitelist PR).
- Extend regression test suite to match expanded mutation space.

**Prohibitions:**
- No cron activation without explicit Project Owner authorization.
- No `max_model_requests_per_run` increase without genome PR review.
- No AST policy relaxation without documented justification.
- No weakening of adoption gates.

**Stop conditions:**
- Budget consumed faster than modeled.
- Adoption gate failures spike.
- Unexpected candidate promotions.
- Project Owner decides to scale back.

**Completion conditions:**
- Cron runs stable across multiple weeks.
- Budget under control.
- Project Owner satisfied with automation level.

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

*This is a Project Owner roadmap for Project Cyber-Immunizer.*
*Phase 3 activation complete (PR #58–#62) / first paid-credit run pending / live_model_enabled=true.*
*This document does not authorize running paid-credit or setting promote_approved=true.*
*Created: 2026-05-31 / Updated: 2026-06-03*
