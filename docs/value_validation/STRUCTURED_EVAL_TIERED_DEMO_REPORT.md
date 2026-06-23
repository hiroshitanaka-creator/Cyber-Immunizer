# Cyber-Immunizer Structured Rules Evaluation Report

**Owner/auditor use only.** This tool evaluates structured rules against a local test corpus.
It does not prove real-world defensive value or production WAF suitability.
Layer 2 value validation requires Owner review and acceptance of evidence from a realistic (non-symbolic) threat corpus.

Rules: `fixtures/structured_rules/symbolic_equivalent.json`
Rules SHA-256: `774b7f88fd269a4d9b420fe3704642ef7903812957bf0f471aaaf5d6fc03443f`
Corpus: `fixtures/evaluation_corpus/tiered_demo_corpus.json`
Corpus SHA-256: `f1ea441ad7f39873a65d4a0d033984b97fadc0909f8bd588deb117ea593175f9`
Total corpus entries: 17
Classified cases: 17 (exceptions excluded from classification counts)

## Overall Results

| Metric | Value |
|---|---|
| True Positive (TP) | 10 |
| False Positive (FP) | 0 |
| True Negative (TN) | 7 |
| False Negative (FN) | 0 |
| Exceptions | 0 |
| Detection rate (TP rate) | 100.0% (10/10) |
| False-positive rate | 0.0% (0/7) |
| False-negative rate | 0.0% (0/10) |

## Per-Category Results

| Category | TP | FP | TN | FN | Exc | TP rate | FP rate | FN rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| path-traversal | 3 | 0 | 1 | 0 | 0 | 100.0% | 0.0% | 0.0% |
| xss | 3 | 0 | 0 | 0 | 0 | 100.0% | n/a | 0.0% |
| sqli | 2 | 0 | 1 | 0 | 0 | 100.0% | 0.0% | 0.0% |
| cmdi | 2 | 0 | 0 | 0 | 0 | 100.0% | n/a | 0.0% |
| baseline | 0 | 0 | 2 | 0 | 0 | n/a | 0.0% | n/a |
| post | 0 | 0 | 1 | 0 | 0 | n/a | 0.0% | n/a |
| search | 0 | 0 | 2 | 0 | 0 | n/a | 0.0% | n/a |

## Per-Kind Results

Pass rate = (TP + TN) / (TP + FP + TN + FN). Holdout, drift, and counterfactual kind pass rates address L2-V3 overfitting-risk evaluation.

| Kind | TP | FP | TN | FN | Exc | Pass rate |
|---|---:|---:|---:|---:|---:|---:|
| attack | 10 | 0 | 0 | 0 | 0 | 100.0% |
| benign | 0 | 0 | 7 | 0 | 0 | 100.0% |

## L2-V3 Tier Results

Tag-based aggregation for holdout / drift / counterfactual corpus entries (L2-V3).
A corpus entry contributes to each tier whose tag it carries.

| Tier | TP | FP | TN | FN | Exc | Pass rate |
|---|---:|---:|---:|---:|---:|---:|
| holdout | 2 | 0 | 1 | 0 | 0 | 100.0% |
| drift | 2 | 0 | 1 | 0 | 0 | 100.0% |
| counterfactual | 1 | 0 | 2 | 0 | 0 | 100.0% |

## Per-Case Results

| ID | Kind | Category | Expected | Actual | Outcome | Matched signals |
|---|---|---|---|---|---|---|
| attack-base-path-traversal | attack | path-traversal | block | block | TP | symbolic_path_traversal |
| attack-base-xss | attack | xss | block | block | TP | symbolic_script_injection |
| attack-base-sqli | attack | sqli | block | block | TP | symbolic_sqli |
| attack-base-cmdi | attack | cmdi | block | block | TP | symbolic_cmdi |
| attack-base-encoded-traversal | attack | path-traversal | block | block | TP | symbolic_encoded_traversal |
| benign-base-root | benign | baseline | allow | allow | TN | — |
| benign-base-search | benign | search | allow | allow | TN | — |
| benign-base-post | benign | post | allow | allow | TN | — |
| holdout-attack-path-traversal | attack | path-traversal | block | block | TP | symbolic_path_traversal |
| holdout-attack-sqli | attack | sqli | block | block | TP | symbolic_sqli |
| holdout-benign-upload | benign | baseline | allow | allow | TN | — |
| drift-attack-xss | attack | xss | block | block | TP | symbolic_script_injection |
| drift-attack-cmdi | attack | cmdi | block | block | TP | symbolic_cmdi |
| drift-benign-locale | benign | search | allow | allow | TN | — |
| counterfactual-benign-near-traversal | benign | path-traversal | allow | allow | TN | — |
| counterfactual-benign-near-sqli | benign | sqli | allow | allow | TN | — |
| counterfactual-attack-true-positive | attack | xss | block | block | TP | symbolic_script_injection |

## Layer 2 Context

This evaluation used the rule literals for detection.
If the corpus uses **neutralized placeholder patterns** (e.g., `PATH_TRAVERSAL_SIGNATURE_PLACEHOLDER`), detection statistics reflect symbolic coverage only — not realistic threat coverage.

**Latency note**: This CLI does **not** capture per-request evaluation latency. L2-V2 requires per-category latency data alongside TP/FP/FN statistics. Latency evidence must be collected separately by the Owner during realistic-corpus evaluation and reported alongside this tool's output. This CLI alone does not satisfy the latency component of L2-V2.

For Layer 2 value validation (DEFINITION_OF_DONE.md L2-V1 through L2-V5), the Owner must supply:

1. A rules document with realistic but safely neutralized detection literals.
2. A test corpus with realistic but safely neutralized request samples.
3. Both files are provided **outside the repository** to avoid committing exploit-adjacent content.

Layer 2 is satisfied only when the Owner has reviewed and accepted value validation evidence from a realistic-corpus evaluation.

