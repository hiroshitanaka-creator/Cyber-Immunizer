<!--
AI_DOC_META
status: DESIGN (approved approach: Option 1 — decoupled activation)
scope: Design for switching the production runtime detector to structured_rules.
authority: Design / Owner-intent record. Does NOT itself change runtime state.
  Current state remains governed by data/project_state.json, docs/PROJECT_STATE.md,
  data/genome.json, machine evidence.
do_not_use_for:
  - executing the flip before PR #173 (realistic ruleset/corpus) is merged
  - changing audited legacy lineage fields (generation / best_score / current_detector_hash)
AI_DOC_META_END
-->

# Production Detector Flip — Design (structured_rules as the runtime default)

## Context & goal

Today the production runtime detector is the legacy Python detector
(`genome.detector_mode = "legacy"` → `core/detector.py`), which matches only
symbolic tokens and detects **0%** of realistic threats. The structured detector
path is implemented and a committed realistic ruleset
(`fixtures/structured_rules/realistic_baseline.json`) detects realistic attacks
at **100% / 0% FP** (`docs/value_validation/REALISTIC_DETECTION_RESULTS.md`).

Goal: make the **realistic structured ruleset the active runtime detector** so
`core.active_detector.inspect_active` actually blocks real attack patterns —
delivering the README mission (useful defense) on `main`.

## The constraint that shapes the design

Several invariants encode "audited baseline = generation 4 legacy":

- `scripts/pre_paid_credit_readiness.py`: `EXPECTED_GENERATION=4`,
  `EXPECTED_BEST_SCORE=948.04`, `EXPECTED_DETECTOR_HASH=ebb8799…`, and
  `hash_ok = sha256(core/detector.py) == genome.current_detector_hash == EXPECTED_DETECTOR_HASH`.
- `tests/test_project_state_sync.py` (~30 tests): pins `generation` 4,
  `best_score` 948.04, `current_detector_hash`, `state_id`, `next_action`, and
  README status-block wording.
- `scripts/offline_validation.py::hash_consistency_issues`: treats
  `current_detector_hash` as the hash of the Python detector of record.

The current `scripts/promote_structured_candidate.py` overwrites
`generation` (+1), `current_detector_hash` (= rules hash), and `best_score`
(= structured score). That collides with every invariant above.

## Decision: Option 1 — decouple structured activation from the legacy lineage

Treat the genome's generation lineage (`generation` / `best_score` /
`current_detector_hash`) as the record of the **legacy evolved detector**, and
record the structured runtime activation in **separate fields**. This is both
lower-risk (no pinned invariant changes) and more correct: the structured score
(902.06, realistic-corpus basis) and the legacy best_score (948.04,
symbolic-corpus basis) are different scoring bases and must not be merged into
one `best_score`/generation counter.

### Genome shape after the flip

```jsonc
{
  "generation": 4,                       // UNCHANGED (legacy lineage)
  "best_score": 948.04,                  // UNCHANGED (symbolic basis, legacy lineage)
  "current_detector_hash": "ebb8799…",   // UNCHANGED (= sha256 of core/detector.py)
  "detector_mode": "structured_rules",   // FLIPPED — selects the runtime detector
  "active_structured_rules_path": "data/active_structured_rules.json",
  "active_structured_rules_hash": "<sha256 of active rules>",
  "active_structured_rules_score": 902.06,        // realistic-corpus basis
  "active_structured_rules_promoted_at": "<ts>"
}
```

`core.active_detector.inspect_active` already dispatches on `detector_mode` and
reads `active_structured_rules_path` — **no change needed there**.

## Changes required (small, bounded)

1. **`scripts/promote_structured_candidate.py`** — change the genome update so it
   does NOT touch `generation` / `best_score` / `current_detector_hash`. Instead
   set `detector_mode`, `active_structured_rules_path`, `active_structured_rules_hash`,
   `active_structured_rules_score`, `active_structured_rules_promoted_at`. Stop
   appending a generation entry to `data/evolution_history.json` (that ledger is
   the legacy generation lineage); structured activations are recorded in genome.
   Update `tests/test_promote_structured_candidate.py` accordingly (assert the new
   fields; assert legacy lineage fields unchanged).

2. **`data/genome.json`** — flip to `detector_mode="structured_rules"` by running
   the modified promote against the committed realistic inputs:
   ```bash
   python scripts/promote_structured_candidate.py \
     --rules fixtures/structured_rules/realistic_baseline.json \
     --corpus-dir fixtures/realistic_corpus --baseline --owner-approved
   ```
   This also writes `data/active_structured_rules.json`.

3. **`tests/test_active_detector.py`** — update the "default genome is legacy"
   test: the committed default genome is now `structured_rules`; assert
   `inspect_active` dispatches to the active rules and that an explicit
   `detector_mode="legacy"` genome still routes to `inspect_request`.

4. **State / docs (current-state SSOT)**:
   - `data/project_state.json` + `docs/PROJECT_STATE.md`: record
     `active_runtime = "structured_rules (realistic_baseline)"` while keeping the
     legacy lineage row at generation 4. Keep `state_id` / `next_action` /
     pinned legacy values unchanged (sync tests stay green).
   - `README.md` status block (and `scripts/update_readme.py` if it generates it):
     add one line that the active runtime detector is the realistic structured
     ruleset. Verify `tests/test_project_state_sync.py` README assertions still
     hold (they require "generation 4" / "audit complete" wording — keep it).

5. **`scripts/pre_paid_credit_readiness.py`** — no change to EXPECTED_* (legacy
   lineage unchanged, so `hash_ok`/`state_ok` still pass). Optionally surface
   `detector_mode` in the readiness output for visibility (non-gating).

## What stays green automatically

Because the legacy lineage fields are untouched: `pre_paid_credit_readiness`
EXPECTED_* checks, `offline_validation.hash_consistency_issues`, and the ~30
`test_project_state_sync` assertions all continue to pass without edits.

## Rollback

Reverting is one field change: set `detector_mode="legacy"` (and optionally drop
`active_structured_rules_*`). `core.active_detector` then routes to
`core/detector.py` again. The legacy detector is never modified by this flip, so
rollback is immediate and lossless. A legacy Python promotion already resets
`detector_mode` to `legacy` (added in PR #172).

## Verification plan

- `python -m pytest tests/ -q` → all green (expect ~3009+; only the active_detector
  default test and promote_structured tests change).
- `python scripts/validate_state.py` → PASS.
- `python scripts/pre_paid_credit_readiness.py` → ready: true (gen-4 lineage intact).
- Runtime check: `core.active_detector.inspect_active` blocks the realistic
  attack corpus and allows benign/counterfactual (covered by
  `tests/test_realistic_ruleset.py` + a new active_detector end-to-end test).

## Safety

No Gemini API call, no `live_model` change, no `workflow_dispatch`, no
paid-credit run. Only defensive detection content is committed. The flip is a
configuration change (`detector_mode`) plus the committed active rules document.

## Dependency / sequencing

Implement **after PR #173 is merged** (it lands the realistic ruleset/corpus and
the latest evaluator/promote hardening). Then this flip is a focused, low-risk PR.
