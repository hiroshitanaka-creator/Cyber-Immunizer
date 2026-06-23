# R4 — Realistic-Capability Promotion Demonstration (Neutralized Summary)

> **Owner-directed sandbox run.** Executed on the Owner's behalf. The realistic
> ruleset and corpus were generated and kept **outside the repository**. The
> promotion was run against a **sandbox copy** of the repository's `data/` state
> (a faithful copy of the audited generation-4 baseline, `best_score=948.04`).
> The repository's real `data/genome.json` was **not** changed — it remains
> `detector_mode="legacy"`. This file contains **numeric results only**; no raw
> detection signatures or attack strings are stored in the repository.

## What was demonstrated

The R3 structured-rules promotion path (`scripts/promote_structured_candidate.py`)
was used end-to-end to promote a realistic-capability ruleset over the audited
generation-4 baseline, and the resulting **active detector** was then measured
against realistic threats.

### Promotion result (sandbox, vs the real gen-4 baseline)

| Field | Before | After |
|---|---|---|
| detector_mode | legacy | structured_rules |
| generation | 4 | 5 |
| best_score | 948.04 | 960.82 |

The realistic ruleset (score 960.82) passed the live adoption gate — beating the
audited gen-4 baseline (948.04), differing from the legacy detector (parity
guard satisfied), with all adaptive floors at 1.0 — and was promoted to
generation 5 with explicit `--owner-approved`.

### Active-detector capability (before vs after)

Measured with `core.active_detector.inspect_active` against the realistic
external corpus:

| Metric | Before (legacy gen-4) | After (promoted gen-5) |
|---|---|---|
| Realistic attacks detected | **0 / 13 (0%)** | **13 / 13 (100%)** |
| Benign false-positives | 0 / 9 | 0 / 9 |

## Interpretation

This is the project's central question answered end-to-end: the promoted runtime
detector **can** be evolved to detect realistic threats. The audited gen-4
detector detects 0% of realistic threats (the symbolic wall); after promoting a
realistic ruleset through the R3 path, the active detector detects 100% with
zero false positives on this corpus — and the promotion passed the same
fail-closed gate the autonomous loop uses.

## Honest bounds

- **The real repository baseline is unchanged.** This ran in a sandbox; the
  committed `data/genome.json` is still `detector_mode="legacy"` (gen-4). Flipping
  the real active baseline to a structured ruleset is a deliberate Owner decision
  and would require deciding how realistic detection signatures are stored (the
  Value Delivery Blueprint requires committed rulesets to be neutralized and
  realistic signatures to live outside the repository).
- The realistic corpus is **small and canonical** (29 cases). This demonstrates
  capability and the promotion mechanism; it is not a production WAF benchmark.
- The promoted ruleset is **hand-written**, not LLM-evolved. Having the live
  model propose realistic rules is a separate, paid-credit, Owner-gated step.
- Raw detection signatures and request samples are intentionally **not** in the
  repository.
