# Layer 2 Realistic Evaluation — Neutralized Summary

> **Owner-directed run.** The Project Owner directed this evaluation and an
> assistant executed it on the Owner's behalf. The realistic request corpus and
> rule literals were generated and kept **outside the repository** (local
> scratch only). This file contains **numeric results and category labels only**
> — no raw attack strings, payloads, or rule literals are stored in the
> repository. This is candidate Layer 2 evidence presented for Owner review and
> acceptance; it does not by itself declare Layer 2 complete.

## What was evaluated

Two detector configurations were graded against the **same realistic corpus**:

1. **Current detector capability** — the symbolic-token rules equivalent to the
   promoted generation-4 `core/detector.py` (`fixtures/structured_rules/symbolic_equivalent.json`).
2. **Realistic ruleset** — a structured ruleset whose literals are canonical,
   safely neutralized signature tokens for each threat category (held outside
   the repository).

Each configuration was run through both evaluation paths:

- `cli/structured_eval` — per-category / per-tier TP/FP/FN report.
- `scripts/evaluate_structured_rules_candidate.py --corpus-dir` — gate-grade
  score / adoption gate / adaptive floor / latency.

### Corpus composition (realistic, neutralized, outside repo)

| Tier / kind | Cases |
|---|---|
| attack (path-traversal ×5*, xss ×4, sqli ×4, cmdi ×3 across tiers) | — |
| attack (main tier) | 9 |
| benign (main tier) | 6 |
| regression | 4 |
| holdout | 3 |
| counterfactual | 4 |
| drift | 3 |
| **Total cases (all tiers)** | **29** |

\* category totals are counted across main + adaptive tiers.

## Result 1 — Current detector capability vs realistic corpus

`cli/structured_eval`, overall and per category:

| Metric | Value |
|---|---|
| Overall TP / FP / TN / FN | 0 / 0 / 13 / 16 |
| Overall detection rate (TP rate) | **0.0%** |
| path-traversal TP rate | 0.0% (0 of 5) |
| xss TP rate | 0.0% (0 of 4) |
| sqli TP rate | 0.0% (0 of 4) |
| cmdi TP rate | 0.0% (0 of 3) |
| holdout pass rate | 33.3% |
| drift pass rate | 33.3% |
| counterfactual pass rate | 75.0% |

Gate-grade (`--corpus-dir`, baseline mode): **adoption gate FAILED**,
tp_rate = 0.000, score = −1543.62, avg_latency_ms ≈ 0.078.

**Interpretation:** the promoted generation-4 detector (symbolic best_score
948.04) detects **none** of the realistic threats in any category. This is the
first numeric confirmation of the "symbolic wall": the high symbolic-corpus
score does not transfer to realistic threat coverage.

## Result 2 — Realistic ruleset vs realistic corpus

`cli/structured_eval`, overall and per category:

| Metric | Value |
|---|---|
| Overall TP / FP / TN / FN | 16 / 0 / 13 / 0 |
| Overall detection rate (TP rate) | **100.0%** |
| Overall false-positive rate | **0.0%** |
| path-traversal TP rate | 100.0% (5 of 5) |
| xss TP rate | 100.0% (4 of 4) |
| sqli TP rate | 100.0% (4 of 4) |
| cmdi TP rate | 100.0% (3 of 3) |
| holdout pass rate | 100.0% |
| drift pass rate | 100.0% |
| counterfactual pass rate | 100.0% |

Gate-grade (`--corpus-dir`, baseline mode): **adoption gate PASSED**,
tp_rate = 1.000, fp_rate = 0.000, score = 960.82, avg_latency_ms ≈ 0.086,
holdout / counterfactual / drift floors all 1.0.

**Interpretation:** the structured-rules path can detect the realistic threats
across all four categories with zero false positives, including the
counterfactual near-miss benign requests (no overfitting on this corpus). This
demonstrates a concrete, safe route through the structured detector to close the
symbolic wall — without editing `core/detector.py` or committing exploit data.

## Layer 2 criteria coverage (DEFINITION_OF_DONE L2-V1..V5)

| ID | Requirement | This evaluation |
|---|---|---|
| L2-V1 | Realistic threat coverage (path-traversal, xss, sqli, cmdi) | Covered — all four categories evaluated against realistic (non-symbolic) requests |
| L2-V2 | Per-category TP/FP/FN + latency | Reported above (latency from gate-grade evaluator) |
| L2-V3 | Holdout / drift / counterfactual pass rates | Reported above for both configurations |
| L2-V4 | Improvement explanation | symbolic capability 0.0% → realistic ruleset 100.0% on the same corpus; gap and path quantified |
| L2-V5 | No overfitting / bounded claims | Symbolic vs realistic explicitly distinguished; counterfactual tier passes; claims bounded to this small canonical corpus |

## Honest bounds

- The realistic corpus is **small and canonical** (29 cases). It demonstrates
  capability and the symbolic-wall gap; it is **not** a production WAF benchmark
  and does not prove real-world deployment readiness.
- Result 2 grades a **hand-written realistic ruleset**, not an LLM-evolved
  detector. It shows the evaluation path and the achievable target; evolving the
  promoted detector to this capability remains future, Owner-gated work
  (see the L1-F14 decision record and design-doc phases 5–7).
- Raw corpus and rule literals are intentionally **not** in the repository.

## Owner acceptance

- [x] Project Owner has reviewed this evidence and accepts it toward Layer 2.
      **Accepted 2026-06-23** by the Project Owner (tanakantyo0229@gmail.com),
      recorded on behalf of the Owner at the Owner's explicit direction.

### Scope of this acceptance (bounded)

The Owner accepts that this evaluation has demonstrated, with reproducible
numeric evidence on a small canonical neutralized corpus:

1. The evaluation path (per-category TP/FP/FN, latency, and holdout / drift /
   counterfactual tiers) functions end-to-end against realistic, non-symbolic
   requests — satisfying the structure of DEFINITION_OF_DONE L2-V1..V5.
2. The promoted generation-4 detector's symbolic capability detects **0.0%** of
   realistic threats (the symbolic wall, now quantified).
3. A structured ruleset detects the same realistic threats at **100.0%** TP /
   **0.0%** FP, including counterfactual near-miss benign requests — a concrete,
   safe route to close the wall.

This acceptance does **not** claim that the **promoted runtime detector**
(`core/detector.py`) detects realistic threats, nor that the system is
production-WAF ready. Evolving the promoted detector to realistic capability
remains future, Owner-gated work (design-doc phases 5–7).
