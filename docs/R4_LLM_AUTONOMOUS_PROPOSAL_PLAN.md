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

## The gap that must be built first (Owner-gated code change)

The proposer has **no live structured-rules mode**. Today:

- `propose_mutation.py --structured-rules --offline-sample` → emits a structured
  rules JSON **offline** (symbolic indicators only, no API).
- `propose_mutation.py --gemini-paid-credit --allow-live-model` → calls Gemini
  but emits a **raw-Python** mutation for `core/detector.py`, scored against the
  **symbolic** `data/` corpus.

There is no `--structured-rules --gemini-paid-credit` path. **R4 requires adding
a live structured-rules proposal mode** that asks Gemini to return a structured
rules JSON (validated by `core.structured_validator`), so the proposal can be
evaluated against a realistic corpus and promoted via R3.

This is a `scripts/**` (FROZEN) change and must be approved separately before
implementation. It does not itself call the API; the API call happens only when
the Owner later runs the paid-credit step.

## Intended pipeline (once the live structured mode exists)

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

Steps [2] and [3] already exist and were validated in R1/R3/R4-demo. Only step
[1]'s live structured mode is missing.

## Required Owner gates (each is a separate explicit approval)

1. **Build approval** — add the live structured-rules proposal mode to
   `propose_mutation.py` (FROZEN scripts change). Includes tests; no API call.
2. **Paid-credit run approval** — run step [1]: requires `GEMINI_API_KEY` in CI
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

Approve **gate 1 (build the live structured-rules proposal mode)** first — it is
paid-credit-free and testable with mocked model output, and it is the only
missing piece between today and a real autonomous R4 run. Gates 2–4 follow when
the Owner is ready to spend paid credit.
