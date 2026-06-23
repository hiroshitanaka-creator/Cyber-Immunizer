# Generalization to Unknown Threats — Report (M3)

The mission requires detecting **不特定の脅威** — threats the system was not built
around. This report makes that **measurable** and states the honest current
position: how well the active detector generalizes to threats it was never shown.

## Method

Two committed corpora are graded with the same ruleset
(`fixtures/structured_rules/realistic_baseline.json`):

- **In-distribution** (`fixtures/realistic_corpus/all_cases.json`): the threat
  classes/variants the detector is built for.
- **Held-out** (`fixtures/generalization_corpus/heldout_threats.json`): threats
  the proposer was **never shown** — evasive variants of known classes
  (double-encoded / backslash traversal, comment-obfuscated SQLi, spaceless
  command chaining) **and new threat classes** (SSRF, XXE, SSTI, NoSQL, LDAP).
  All are canonical, neutralized defensive detection targets (no weaponized
  exploits), plus held-out benign near-misses.

Reproduce:

```bash
python scripts/generalization_report.py --json
# or per-category:
python -m cli.structured_eval \
  --rules fixtures/structured_rules/realistic_baseline.json \
  --corpus fixtures/generalization_corpus/heldout_threats.json
```

## Result (current static baseline)

| Corpus | Attack detection (TP rate) | False-positive rate |
|---|---:|---:|
| In-distribution | **100%** | 0% |
| Held-out (unknown) | **11%** (1/9) | **0%** |
| **Generalization gap** | **89 points** | — |

## Honest interpretation

- The hand-written static ruleset is **strong on what it was built for and
  catches almost none of the unknown** (11%): it has no signatures for the new
  classes and misses evasive variants of known ones. False positives on held-out
  benign are **0%** (it does not over-block).
- This is **not a failure — it is the metric the mission needs.** "不特定の脅威"
  detection is now quantified, and the 89-point gap is exactly what the
  autonomous loop must close.
- A static, human-authored detector cannot keep up with evolving/unknown threats
  — which is the README's premise. Closing this gap is the job of **autonomous
  self-evolution**: when new threats surface (held-out / live feeds), the LLM
  proposes detection, the gate evaluates it (incl. held-out generalization), and
  promotion + self-healing (M2) keep production safe.

## What "improving generalization" will look like

As the autonomous loop runs, the held-out detection rate should climb while the
held-out false-positive rate stays ~0. This report is the tracked baseline; each
generation that raises held-out detection (without raising held-out FP) is real
progress toward detecting the unspecified. The number is bounded honesty — we
report measured generalization, and we keep pushing it up; we do not claim to
detect all unknowns.

## Bounds

- The held-out corpus is curated and moderate; it measures generalization
  direction, not an absolute guarantee of zero-day coverage.
- `contains_literal` signatures are a basic model; richer matching is future work.
