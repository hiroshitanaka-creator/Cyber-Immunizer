<!--
AI_DOC_META
status: PLANNING
scope: Plan for live (paid-credit) LLM proposal of realistic structured detection rules (R4).
authority: Planning / Owner-intent record. Does NOT authorize any paid-credit run, live_model change, or workflow_dispatch. Current state remains governed by data/project_state.json, docs/PROJECT_STATE.md, data/genome.json.
use_for:
  - sequencing the R4 (LLM-autonomous realistic proposal) work
  - recording the required Owner gates and budget posture
do_not_use_for:
  - executing a paid-credit run
  - changing model/budget/promotion state
AI_DOC_META_END
-->

# R4 — LLM-Autonomous Realistic Rule Proposal (Plan / Preflight / Budget)

> **No paid-credit call was made to produce this document.** This is a plan and a
> record of offline preflight/readiness/budget state. Executing any step that
> calls the Gemini API, sets `live_model_enabled`, or triggers `workflow_dispatch`
> requires explicit Project Owner approval at the time of execution.

## Goal

Have the live model (Gemini, paid-credit) **autonomously propose realistic
structured detection rules**, evaluate them against a realistic (externally
supplied, neutralized) corpus, and promote a passing candidate to the active
detector via the R3 path. This is the "autonomous immune loop" applied to
realistic threat coverage rather than the symbolic corpus.

## Current implementation status (live structured mode exists)

The live structured-rules proposal mode has now been implemented and exercised
by the autonomous loop. Current code supports:

- `propose_mutation.py --structured-rules --offline-sample` → emits a structured
  rules JSON **offline** (symbolic indicators only, no API).
- `propose_mutation.py --gemini-paid-credit --allow-live-model` → calls Gemini
  and emits a **raw-Python** mutation for `core/detector.py`, scored against the
  legacy symbolic `data/` corpus.
- `propose_mutation.py --structured-rules --gemini-paid-credit --allow-live-model`
  → calls Gemini and asks for a structured-rules JSON document, then validates it
  with the strict structured-rules schema before writing the candidate.

Run #80 (2026-06-26, GitHub Actions id `28220768075`) used the structured
Gemini paid-credit path with `promote_approved=true`; the structured candidate
passed the adoption gate and was promoted, flipping the committed
`data/genome.json` runtime mode to `structured_rules`. This document is therefore
no longer a request to build live structured mode. It is a planning record for
the remaining R4/M1 work: one-trigger end-to-end operation, Owner-gated live
experiments, realistic-corpus evaluation, and any future auto-promotion wiring.

## Intended pipeline (current live structured path)

```
[1] propose   python scripts/propose_mutation.py --structured-rules \
                  --gemini-paid-credit --allow-live-model      (PAID, Owner-gated)
              -> .cyber_immunizer/structured_rules.json (schema-validated)

[2] evaluate  python scripts/evaluate_structured_rules_candidate.py \
                  --rules .cyber_immunizer/structured_rules.json \
                  --corpus-dir <OWNER EXTERNAL REALISTIC CORPUS> --json     (no API)
              -> passed_adoption_gate? (score + adaptive floor + parity guard)

[3] promote   python scripts/promote_structured_candidate.py \
                  --rules .cyber_immunizer/structured_rules.json \
                  --corpus-dir <OWNER EXTERNAL REALISTIC CORPUS> \
                  --owner-approved --json                                   (no API)
              -> flips genome detector_mode=structured_rules (R3)
```

Steps [1], [2], and [3] now exist. Step [1] was validated by paid-credit structured runs, culminating in run #80 promotion; further live execution remains Owner-gated.

## Required Owner gates (each is a separate explicit approval)

1. **Build approval** — already completed for the live structured-rules proposal mode; future changes to scripts/workflows remain separately Owner-gated.
2. **Paid-credit run approval** — run step [1] again: requires `GEMINI_API_KEY` in CI
   secrets, `live_model_enabled=true`, and the paid-credit run trigger. Per
   CLAUDE.md this is Owner-only.
3. **Realistic corpus** — Owner supplies the realistic (neutralized) corpus from
   outside the repository for steps [2]/[3].
4. **Promotion approval** — `--owner-approved` on step [3] to switch the active
   detector (and a decision on how/whether realistic rules are stored, given the
   blueprint's neutralization rule).

## Offline preflight / readiness (captured 2026-06-23, no API)

- `scripts/pre_paid_credit_readiness.py` → **ready: true**. Baseline consistent:
  phase 3, generation 4, best_score 948.04, detector_hash ebb8799d…; frozen
  index/worktree drift checks pass; proposal/apply validation pass.
- `scripts/propose_mutation.py --gemini-paid-credit-preflight` → fails locally
  because `GEMINI_API_KEY` is not set in this sandbox. **This is expected**: the
  key lives in CI secrets, not in this environment. The preflight makes no API
  call and never logs the key.

## Budget reconciliation

| Item | Value |
|---|---|
| Monthly cap (`monthly_api_budget_usd`) | $10.00 |
| Daily cap (`daily_api_budget_usd`) | $0.25 |
| `max_model_requests_per_run` | 1 |
| `max_prompt_chars` / `max_output_tokens` | 12000 / 2048 |
| Conservative est. cost per run | **≈ $0.034** (overcounted; unknown-model fallback pricing $1/1M in, $5/1M out) |
| Daily headroom at that estimate | ~7 runs/day |

The configured model `gemini-3-flash-preview` is not in `api_budget._COST_TABLE`,
so budgeting uses the deliberately high unknown-model fallback. A single R4
proposal run is far under the daily cap. The budget gate (`api_budget.py`) is
fail-closed: it refuses the call if the ledger is unreadable or the estimated
spend would exceed a cap.

## Safety constraints (apply to every R4 step)

- The proposal prompt must request **defensive detection rules only** — no
  exploit generation, payload synthesis, or bypass guidance. Output is data
  (a rules document), validated by the strict schema validator before use.
- Realistic corpus and realistic rules stay **outside the repository**; only
  neutralized numeric summaries are committed.
- No `live_model_enabled` change, no `workflow_dispatch`, no paid call without
  explicit Owner approval at execution time.

## Recommended next action

Do **not** rebuild the live structured-rules proposal mode; it already exists.
The next implementation breakthrough is an API-free one-trigger dry-run that
exercises structured proposal output, evaluation, and adoption-gate handling
without spending paid credit. Any further live paid-credit run, workflow trigger,
realistic external corpus use, or promotion remains Owner-gated at execution
time.
