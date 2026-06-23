# Realistic Detection Results (committed, reproducible)

This records the committed realistic defensive ruleset evaluated against the
committed realistic corpus. Unlike the earlier sandbox demonstration, **both the
ruleset and the corpus now live in the repository** and the results are
reproducible from a clean checkout. A regression test
(`tests/test_realistic_ruleset.py`) locks these outcomes in.

Per the Owner policy (see `docs/VALUE_DELIVERY_BLUEPRINT.md` → "Owner ポリシー明確化"),
committing defensive detection signatures and standard attack test patterns is
permitted for this public defensive-research repository; weaponized exploits,
multi-stage attack chains, bypass/evasion guidance, and live-traffic capture are
not.

## Inputs

- Ruleset: `fixtures/structured_rules/realistic_baseline.json` — 21 defensive
  detection signatures across path-traversal, XSS, SQLi, and command injection
  (canonical WAF/IDS-style `contains_literal` signatures).
- Corpus: `fixtures/realistic_corpus/` — 34 realistic requests across the four
  categories plus benign and the holdout / drift / counterfactual tiers.

## Results

`cli/structured_eval` (per-category / per-tier):

| Metric | Value |
|---|---|
| Overall TP / FP / TN / FN | 18 / 0 / 16 / 0 |
| Overall detection rate | **100.0%** |
| Overall false-positive rate | **0.0%** |
| path-traversal TP rate | 100.0% (4/4) |
| xss TP rate | 100.0% (5/5) |
| sqli TP rate | 100.0% (5/5) |
| cmdi TP rate | 100.0% (4/4) |
| holdout / drift / counterfactual pass rate | 1.0 / 1.0 / 1.0 |

`scripts/evaluate_structured_rules_candidate.py --corpus-dir fixtures/realistic_corpus --baseline`:
adoption gate **PASSED** — tp_rate 1.000, fp_rate 0.000, score 902.06,
avg_latency_ms ≈ 0.18, all adaptive floors 1.0.

## What this means

This is the project's first **committed, reproducible** evidence that the
structured detector path detects realistic threats (not symbolic tokens) with
zero false positives on this corpus, including the counterfactual near-miss
benign cases. It is verified end-to-end through the real structured detector
(`core/runtime_selector` → `core/structured_evaluator`).

## Bounds (honest)

- The corpus is curated and moderate (34 cases); it demonstrates real detection
  capability and is a regression baseline — it is not a production WAF benchmark.
- `contains_literal` signatures are a basic detection model (no regex); a
  production deployment would extend the signature set and tune for the live
  traffic profile.
- This evaluates the **structured ruleset**. Making it the **default committed
  runtime** (`genome.detector_mode = "structured_rules"`) is a separate
  re-baselining step (it changes the audited-baseline invariants and the
  `current_detector_hash` semantics) and is tracked as the next focused change.

## Activation (today)

The realistic ruleset can be activated through the existing promotion path:

```bash
python scripts/promote_structured_candidate.py \
  --rules fixtures/structured_rules/realistic_baseline.json \
  --corpus-dir fixtures/realistic_corpus \
  --baseline --owner-approved
```

This writes `data/active_structured_rules.json` and sets
`genome.detector_mode = "structured_rules"` so `core.active_detector` dispatches
to the realistic ruleset.
