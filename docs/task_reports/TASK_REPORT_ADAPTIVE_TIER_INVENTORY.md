# Task Report — Adaptive Tier Inventory

## Summary

This report inventories the existing Cyber-Immunizer evaluation fixtures into the T0/T1/T2 tiers defined by `docs/ADAPTIVE_SECURITY_GAME_MODEL.md`. It is analysis-only and does not change runtime behavior, data files, promotion behavior, model settings, or workflow behavior.

The current fixture set is sufficient to identify an initial safety/regression floor and a small known-threat tier, but it does not yet provide true T3 synthetic neutralized variants, T4 adaptive counterfactuals, or T5 holdout/future-drift evaluation.

## Canonical state checked

- `data/project_state.json`
  - `state_id`: `phase3_propose_side_baseline_preservation_hardened_await_owner_approved_rerun`
  - `next_action`: `propose_side_baseline_preservation_hardened_await_owner_approved_rerun_review`
  - Fresh verification policy: no paid-credit run, no `workflow_dispatch`, no Gemini API call.
- `docs/PROJECT_STATE.md`
- `docs/ADAPTIVE_SECURITY_GAME_MODEL.md`
- Reference-only fixture/evaluation files:
  - `data/attack_requests.json`
  - `data/benign_requests.json`
  - `data/regression_cases.json`
  - `data/active_threats.json`
  - `core/fitness.py`
  - `core/test_attacker.py`

## Scope and non-changes

Allowed file changed:

- `docs/task_reports/TASK_REPORT_ADAPTIVE_TIER_INVENTORY.md`

Frozen/reference-only files not changed:

- `core/**`
- `scripts/**`
- `data/**`
- `.github/**`

No new attack payloads were added. No data files were edited. No Gemini API call was made. No `workflow_dispatch` was run. Promotion behavior was not changed.

## Evaluation pipeline observed

The current evaluator loads three fixture files through `core.test_attacker.load_test_cases()`:

- benign fixtures from `data/benign_requests.json`, defaulting to `kind="benign"` and `expected_blocked=false`;
- attack fixtures from `data/attack_requests.json`, defaulting to `kind="attack"` and `expected_blocked=true`;
- regression fixtures from `data/regression_cases.json`, using each record's explicit `kind` and `expected_blocked` fields.

`core.fitness.evaluate()` then runs the candidate detector against those cases, computes true/false positive and negative counts, computes a regression pass rate over `kind="regression"` cases, and applies the adoption gate over syntax, AST policy, contract, timeout/exception, regression pass rate, false-positive rate, latency, and score-vs-previous-best checks.

The current T0/T1/T2 inventory should therefore be interpreted as a classification of existing fixture and gate roles, not as a new evaluator implementation.

## T0 Safety / policy inventory

T0 is the hard safety and policy floor. Existing T0 coverage is mostly implemented as evaluator and policy behavior rather than as standalone JSON request fixtures.

| Existing source | Current role | Adaptive tier classification | Notes |
|---|---|---|---|
| `core/fitness.py` syntax and module-load handling | Rejects candidates that cannot be parsed, loaded, or evaluated safely enough to produce a valid report. | T0 Safety / policy | Runtime behavior unchanged. |
| `core/fitness.py` AST policy invocation | Runs the strict policy check before importing the candidate module. | T0 Safety / policy | This is the strongest existing T0 guard because it evaluates candidate code before execution. |
| `core/fitness.py` contract check | Requires the candidate to expose the expected detector interface and return a valid detection result on a smoke request. | T0 Safety / policy | Prevents malformed detector interfaces from entering scoring. |
| `core/test_attacker.py` in-process simulator | Constructs static request objects and calls the detector in process; it performs no network activity, socket use, or external command execution. | T0 Safety / policy | Provides safety evidence for fixture evaluation mechanics. |
| `data/benign_requests.json` | Provides benign requests expected not to be blocked. | T0/T1 boundary | T0 relevance is indirect: these fixtures help expose unsafe overblocking when combined with false-positive gates. |
| `data/regression_cases.json` benign regression rows | Preserve known benign behavior that must not be blocked. | T0/T1 boundary | These are T1 fixtures with T0 safety-floor impact because blocking known-good benign traffic is an unacceptable regression. |

### T0 gaps

- There is no dedicated T0 fixture manifest that explicitly labels each safety rule from the adaptive model, such as no raw exploit payloads, no offensive tooling, no network scanning, and no credential logic.
- Current safety coverage is distributed across policy code, evaluator checks, and simulator behavior rather than summarized in tier metadata.
- There is no separate adaptive-game report field that says, "T0 passed," apart from the existing adoption-gate fields.

## T1 Regression / known-good preservation inventory

T1 is the hard regression floor. Existing regression coverage is explicit in `data/regression_cases.json` and is enforced by `core.fitness.evaluate()` through `regression_pass_rate`.

| Fixture group | Fixture IDs | Expected behavior | Adaptive tier classification | Notes |
|---|---|---|---|---|
| Regression threat-preservation cases | `regression-001`, `regression-002`, `regression-003` | Must continue to block known symbolic suspicious categories. | T1 Regression / known-good preservation | These protect prior defensive behavior from being removed by a candidate. |
| Regression benign-preservation cases | `regression-004`, `regression-005` | Must continue not to block known benign behavior. | T1 Regression / known-good preservation | These protect the non-blocking baseline and false-positive floor. |
| Benign request corpus | `benign-001` through `benign-005` | Expected not to be blocked. | T1 Regression / known-good preservation | These serve as benign known-good preservation and false-positive checks. |
| Adoption gate regression pass rate | All `kind="regression"` results | Must meet the configured minimum regression pass rate. | T1 Regression / hard gate | This is the current implementation of the regression floor. |
| Adoption gate false-positive rate | Benign and regression-benign outcomes | Must stay within the configured maximum false-positive rate. | T1 Regression / hard gate | This connects benign preservation to adoption eligibility. |

### T1 gaps

- Regression fixtures are not yet annotated with adaptive tier metadata in the data files.
- Regression preservation is currently measured as a single pass-rate value; it does not yet separately report threat-regression preservation vs. benign-regression preservation.
- The current regression floor does not yet distinguish between static-gate correction work and adaptive tournament performance beyond the planning distinction in `docs/ADAPTIVE_SECURITY_GAME_MODEL.md`.

## T2 Known neutralized threats inventory

T2 represents known neutralized threat concepts. Existing T2 coverage comes from the symbolic attack fixture corpus and the active threat stub records. This report intentionally lists only IDs, tags, and defensive categories; it does not reproduce request bodies or raw indicators.

| Fixture source | Fixture IDs / records | Defensive category represented | Adaptive tier classification | Notes |
|---|---|---|---|---|
| `data/attack_requests.json` | `attack-001` | Path traversal category, symbolic indicator only. | T2 Known neutralized threats | Known threat concept from the current static corpus. |
| `data/attack_requests.json` | `attack-002` | Script-injection category, symbolic indicator only. | T2 Known neutralized threats | Known threat concept from the current static corpus. |
| `data/attack_requests.json` | `attack-003` | SQL-like suspicious-token category, symbolic indicator only. | T2 Known neutralized threats | Known threat concept from the current static corpus. |
| `data/attack_requests.json` | `attack-004` | Command-delimiter category, symbolic indicator only. | T2 Known neutralized threats | Known threat concept from the current static corpus. |
| `data/attack_requests.json` | `attack-005` | Encoded traversal category, symbolic indicator only. | T2 Known neutralized threats | Known threat concept from the current static corpus. |
| `data/active_threats.json` | `THREAT-2024-001` through `THREAT-2024-005` | Active threat stubs mirroring path traversal, SQL-like, script-injection, command-delimiter, and encoded traversal focus areas. | T2 Known neutralized threats / observe-stage signal | These records describe known defensive focus areas, but they are not currently loaded by `core.test_attacker.load_test_cases()` as evaluation cases. |

### T2 gaps

- T2 is small: five attack fixtures and five active-threat stubs.
- Active threat records are observation inputs, not currently evaluator fixtures.
- T2 currently checks known symbolic categories but not concept generalization across broader neutralized transformations.
- There is no T2-specific score separate from the existing true-positive rate and deterministic fitness score.

## Future tier gaps

### T3 synthetic neutralized variants

Current status: not implemented in the existing fixture set.

Needed future work:

- Generate inert symbolic variants from safe labels and abstract request features only.
- Keep variants neutralized and non-operational.
- Version generated fixtures separately from hand-authored T1/T2 fixtures.
- Report T3 performance separately after T0/T1 pass.

### T4 adaptive counterfactuals

Current status: not implemented in the existing fixture set.

Needed future work:

- Add benign lookalikes that should remain unblocked.
- Add safe near-miss examples that test whether the detector is overfitting to fixed strings.
- Keep all counterfactuals neutralized and defensive-only.
- Report false-positive cost and no-op rejection effects separately.

### T5 holdout/future drift

Current status: not implemented in the existing fixture set.

Needed future work:

- Create holdout fixtures unavailable to proposal-time context.
- Add future-drift scenarios as neutralized, non-operational examples.
- Prevent prompt-time leakage of holdout contents.
- Use T5 only as an adaptive-performance score component after T0/T1 pass; never use it to bypass the safety floor.

## Recommended next migration steps

1. Keep the existing adoption gate as the current T0/T1 floor.
2. Add tier labels in documentation or generated reports before editing data schemas.
3. Split future evaluator reporting into `t0_safety`, `t1_regression`, and `t2_known_threats` sections without changing promotion behavior.
4. Introduce T3/T4/T5 only as neutralized, defensive-only fixtures in later scoped PRs.
5. Keep competitive adaptive scoring separate from the regression gate: a candidate must pass T0/T1 before any T2+ adaptive score matters.

## Verification commands and results

- `pytest tests/test_ai_docs_navigation.py -q` — passed (21 passed).
- `pytest tests/test_audit_docs.py -q` — passed (49 passed).
- `pytest tests/ -q` — passed (2148 passed, 103 warnings).
- `git diff --name-only | grep -E '^(\.github|core|scripts|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true` — passed (no frozen paths reported).

## No-API confirmation

No Gemini API call was made. No paid-credit workflow was run. No `workflow_dispatch` was triggered. No promotion was attempted, and `promote_approved` was not changed.
