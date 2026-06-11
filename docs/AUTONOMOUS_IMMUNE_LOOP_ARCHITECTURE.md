# Autonomous Immune Loop Architecture

<!--
AI_DOC_META
document_id: autonomous_immune_loop_architecture
status: CANONICAL
authority_scope: autonomous_immune_loop_architecture
scope: Canonical architecture and lifecycle-state model for the Autonomous Immune Loop. Defines the primary loop, lifecycle stages, progress axis, and the subordinate role of audit mechanisms.
current_state_authority: data/project_state.json and docs/PROJECT_STATE.md remain authoritative for runtime/current-state interpretation.
use_for:
  - defining the Autonomous Immune Loop primary architecture
  - evaluating project progress by loop-stage reachability
  - distinguishing primary autonomous pipeline work from subordinate audit safety mechanisms
  - planning future docs/tasks/PRs around the main immune loop
do_not_use_for:
  - overriding data/project_state.json
  - overriding docs/PROJECT_STATE.md
  - executing paid-credit API runs
  - changing model names, budget settings, promotion behavior, or workflow behavior
  - treating historical docs as current-state contradictions
related:
  - docs/PROJECT_STATE.md
  - data/project_state.json
  - docs/AI_ENTRYPOINT.md
  - README.md
  - CLAUDE.md
  - AGENTS.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
AI_DOC_META_END
-->

---

## 1. Architecture Principle

Cyber-Immunizer's primary architecture is the **Autonomous Immune Loop**.

The project goal is not "completion of audit gates."

The project goal is a defensive code system that can observe, diagnose, propose, validate, materialize, apply, evaluate, adopt, promote, remember, and begin the next cycle — autonomously and safely.

Audit is a safety mechanism subordinate to the loop. It detects problems, blocks unsafe transitions, and triggers rollbacks. It does not own the main pipeline and cannot substitute for loop-stage progress.

**監査は主導権を持たない。**

---

## 2. Primary Loop Definition

The primary pipeline of the Autonomous Immune Loop is:

```
Observe → Diagnose → Propose → Validate → Materialize → Apply → Evaluate → Adopt → Promote → Memory → Next Cycle
```

Each stage is described below.

### Observe

- **Purpose**: Ingest threat records, detect changes in the attack surface, and supply raw signal to the diagnostic stage.
- **Input**: `data/active_threats.json`, system logs, or simulated threat feeds.
- **Output**: Normalized threat observations ready for diagnosis.
- **Success evidence**: At least one valid threat record present in the observation set.
- **Failure return path**: Observation fails → loop does not advance; retry or re-ingest at next scheduled cycle.
- **Current reachability (Phase 3)**: Reached — threat feed data exists; `data/active_threats.json` is present.

### Diagnose

- **Purpose**: Identify the root cause or improvement target from observations; determine which part of the defensive code should change.
- **Input**: Normalized threat observations from Observe.
- **Output**: Diagnosis artifact or improvement target specification.
- **Success evidence**: A named improvement target exists and is used as input to Propose.
- **Failure return path**: Cannot identify improvement target → return to Observe with broadened inputs.
- **Current reachability (Phase 3)**: Implicitly reached in so far as the scripts select a target, but no machine-evidence artifact is separately recorded.

### Propose

- **Purpose**: Request a mutation proposal from the configured proposal path (LLM or local fallback).
- **Input**: Diagnosis / improvement target.
- **Output**: A structured JSON proposal response that passes the output-contract check.
- **Success evidence**: Proposal response received AND passes output-contract validation (not merely HTTP 200 / token success).
- **Failure return path**: API error → retry within budget; output-contract failure → discard response, optionally log failure, return to Propose start.
- **Current reachability (Phase 3)**: API/token success recorded (3 records in `data/api_usage_ledger.json`). A valid output-contract-passing proposal has NOT been produced. Propose/output-contract hardening was implemented in PR #84.

### Validate

- **Purpose**: Verify that the proposal response meets schema, syntax, and output-contract requirements.
- **Input**: Proposal response from Propose.
- **Output**: Validated proposal artifact or rejection with reason.
- **Success evidence**: Validation passes all checks: schema, syntax, static value checks, AST policy pre-check.
- **Failure return path**: Validation fails → discard; return to Propose.
- **Current reachability (Phase 3)**: Not reached — no valid proposal has passed output-contract validation as of the current state.

### Materialize

- **Purpose**: Convert the validated proposal into a concrete candidate artifact (`mutation_patch.json` or equivalent).
- **Input**: Validated proposal from Validate.
- **Output**: `mutation_patch.json` (or equivalent candidate artifact) written to the designated output path.
- **Success evidence**: `mutation_patch.json` exists at the expected path and is non-empty with valid structure.
- **Failure return path**: Cannot materialize → return to Validate or Propose depending on root cause.
- **Current reachability (Phase 3)**: Not reached — `valid_mutation_patch_produced: false` per `data/project_state.json`.

### Apply

- **Purpose**: Generate a candidate file from the patch artifact under safe, isolated conditions.
- **Input**: `mutation_patch.json` from Materialize.
- **Output**: Candidate file written to the designated candidate path.
- **Success evidence**: Candidate file exists, is syntactically valid Python, and passes AST policy.
- **Failure return path**: Apply fails → return to Materialize or Propose depending on cause.
- **Current reachability (Phase 3)**: Not reached — `apply_reached: false` per `data/project_state.json`.

### Evaluate

- **Purpose**: Run the candidate file in a sandboxed subprocess and measure fitness/adoption-gate metrics.
- **Input**: Candidate file from Apply.
- **Output**: Fitness report with regression pass rate, FP rate, and score delta.
- **Success evidence**: Fitness report exists, adoption gate threshold met.
- **Failure return path**: Fails adoption gate → candidate rejected; return to Propose with context.
- **Current reachability (Phase 3)**: Not reached — `evaluate_reached: false` per `data/project_state.json`.

### Adopt

- **Purpose**: Mark the candidate as accepted into a staged adoption state, pending Promote.
- **Input**: Fitness report from Evaluate with adoption gate passed.
- **Output**: Adoption decision record.
- **Success evidence**: Adoption decision record exists and is positive.
- **Failure return path**: Adoption withheld → document reason; return to Evaluate or Propose.
- **Current reachability (Phase 3)**: Not reached.

### Promote

- **Purpose**: Update the detector, genome, and evolution history under configured promotion rules and with Project Owner approval.
- **Input**: Adoption decision record from Adopt.
- **Output**: Updated `core/detector.py`, `data/genome.json`, `data/evolution_history.json`.
- **Success evidence**: All three targets updated sequentially (`core/detector.py` → `data/genome.json` → `data/evolution_history.json`); README status block refreshed by generator. Note: no transaction or rollback exists — partial-promotion failure is possible if a later write fails.
- **Failure return path**: Promotion blocked (missing approval, failing checks) → hold at Adopt; do not promote.
- **Current reachability (Phase 3)**: Not reached — `promote_reached: false`, `promote_approved: false` per `data/project_state.json`.

### Memory

- **Purpose**: Record the completed cycle's outcome in evolution history and update working memory for the next cycle.
- **Input**: Promotion outcome from Promote.
- **Output**: Updated evolution history; next-cycle context prepared.
- **Success evidence**: Evolution history entry appended; system ready for next Observe.
- **Failure return path**: Memory write fails → log; retry or treat as partial cycle.
- **Current reachability (Phase 3)**: Not reached — no cycle has completed through Promote.

### Next Cycle

- **Purpose**: Begin the next iteration of the Autonomous Immune Loop using the updated genome and fresh threat observations.
- **Input**: Updated genome and evolution history from Memory.
- **Output**: Restart of Observe with improved baseline.
- **Success evidence**: A new Observe phase begins with the promoted genome as baseline.
- **Failure return path**: N/A — this stage marks completion of one full loop cycle.
- **Current reachability (Phase 3)**: Not reached.

---

## 3. State Transition Table

The current lifecycle position is determined by `data/project_state.json` and `docs/PROJECT_STATE.md`. The table below uses conservative Phase 3 values consistent with those sources.

| Stage | Role in loop | Input | Output | Success evidence | Failure return path | Current reachability |
|---|---|---|---|---|---|---|
| Observe | Ingest threat signals | Threat feeds / logs | Normalized threat observations | ≥1 valid threat record | Retry / re-ingest | **Reached** (threat data exists) |
| Diagnose | Identify improvement target | Threat observations | Improvement target specification | Named target used in Propose | Broaden inputs, re-Observe | Implicitly reached (no separate artifact) |
| Propose | Request mutation from proposal path | Improvement target | Output-contract-passing proposal | Valid proposal response (not just API success) | Retry within budget; discard on contract failure | **Partially reached** — API/token success only; output contract NOT passed |
| Validate | Verify proposal meets schema / AST policy | Proposal response | Validated proposal or rejection | All checks pass | Discard; re-Propose | **Not reached** — no valid proposal has passed |
| Materialize | Convert proposal to patch artifact | Validated proposal | `mutation_patch.json` | File exists with valid structure | Re-Validate or re-Propose | **Not reached** (`valid_mutation_patch_produced: false`) |
| Apply | Generate candidate file from patch | `mutation_patch.json` | Candidate file | Syntactically valid, passes AST policy | Re-Materialize or re-Propose | **Not reached** (`apply_reached: false`) |
| Evaluate | Measure candidate fitness in sandbox | Candidate file | Fitness report | Adoption gate threshold met | Reject; re-Propose | **Not reached** (`evaluate_reached: false`) |
| Adopt | Stage candidate for promotion | Fitness report | Adoption decision record | Positive adoption record | Hold; re-Evaluate or re-Propose | **Not reached** |
| Promote | Update detector / genome / history | Adoption record | Updated core/detector.py, genome, history | Sequential update (no transaction); README refreshed | Block; hold at Adopt | **Not reached** (`promote_approved: false`) |
| Memory | Record cycle outcome; prep next cycle | Promotion outcome | Updated evolution history | History entry appended | Retry / partial-cycle log | **Not reached** |
| Next Cycle | Restart loop with improved genome | Updated genome + history | New Observe phase | Loop iterates with promoted genome | N/A | **Not reached** |

---

## 4. Audit as Subordinate Safety Infrastructure

Audit mechanisms exist to protect the loop from unsafe transitions. They do not own the pipeline, do not define project progress, and cannot substitute for loop-stage reachability.

| Audit mechanism | What it does | What it must not do |
|---|---|---|
| Safety Net | Detects missing evidence, unsafe scope, protocol violations, and stale claims. | Must not redefine project progress as audit completion. |
| Circuit Breaker | Stops unsafe API runs, promotions, scope expansion, or state mutation. | Must not become the main pipeline. |
| Rollback Trigger | Provides evidence that a candidate or PR should be reverted, held, or rejected. | Must not promote or adopt code by itself. |

Additional rules:

- Audit can block unsafe transitions.
- Audit can require evidence before transitions.
- Audit cannot count as autonomous progress unless the main loop advances.
- **Example**: Ten audit PRs that do not produce a valid mutation patch leave the lifecycle at the same loop stage (Propose/output-contract boundary as of Phase 3).

---

## 5. Progress Evaluation Axis

Progress is measured by the furthest Autonomous Immune Loop stage reached with machine evidence, not by the number of audit PRs merged.

```
Progress is measured by the furthest Autonomous Immune Loop stage reached with machine evidence,
not by the number of audit PRs merged.
```

| Progress axis | Counts as progress | Does not count as progress |
|---|---|---|
| Observe | New valid observations/threat records ingested or simulated. | Audit-only wording changes. |
| Diagnose | Root cause or improvement target identified. | Generic review comments. |
| Propose | Valid proposal response received from configured proposal path. | API success without valid output contract. |
| Validate | Proposal passes schema/syntax/output-contract validation. | LLM self-claim that code is valid. |
| Materialize | `mutation_patch.json` or equivalent candidate artifact produced. | A text suggestion not materialized into the expected artifact. |
| Apply | Candidate file generated safely from the patch. | Patch exists but cannot be applied. |
| Evaluate | Fitness/adoption-gate result exists. | CI-only green unrelated to candidate evaluation. |
| Adopt | Candidate accepted into a staged adoption state. | Audit approval alone. |
| Promote | Detector/genome/history updated only under configured promotion rules and Project Owner approval. | Any promotion without owner-approved gate. |
| Memory | Evolution history/current memory updated for the next cycle. | Historical docs rewritten as current state. |

---

## 6. Document Responsibility Map

| File / area | Role | Authority boundary |
|---|---|---|
| `docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md` | Canonical architecture and lifecycle-stage definition. | Does not define current runtime state. |
| `data/project_state.json` | Machine-readable current-state SSOT. | Frozen in this PR. |
| `docs/PROJECT_STATE.md` | Human-readable current-state SSOT. | Frozen in this PR. |
| `README.md` | Public overview and derived status summary. | Do not treat as higher authority than project_state. |
| `scripts/update_readme.py` | README generated status-block updater. | Reference only; do not modify. |
| `docs/human用roadmap/phase3_to_phase7_roadmap.md` | Project Owner roadmap / handoff context. | Historical or planning context must not override current-state SSOT. |
| `CLAUDE.md` | Claude operational instructions and receiving gate. | Derived operational summary; cross-reference link to this document added in this PR. |
| `AGENTS.md` | Codex workflow rules. | Derived operational summary; cross-reference link to this document added in this PR. |
| `docs/audit_gate/**` | Audit protocols and task/PR gates. | Subordinate safety infrastructure, not the main immune loop. |

### Current-state authority order (preserved from docs/PROJECT_STATE.md)

When interpreting the current state of the project, use this authority order:

1. **Machine evidence** — latest `main` HEAD, `data/api_usage_ledger.json`, `data/genome.json`, GitHub Actions / CI results.
2. `data/project_state.json` — machine-readable current-state source.
3. `docs/PROJECT_STATE.md` — human-readable current-state source.
4. **Derived summaries** — `README.md` status block, `CLAUDE.md`.

This architecture document does not override or supersede this authority order.

---

## 7. Historical Docs Policy

Historical docs preserve past state and must not be rewritten merely because current state changed.

- Historical docs (old task reports, roadmap snapshots, old PR bodies, old phase docs) are **past-state evidence only**.
- They do not independently define current state.
- If a historical doc conflicts with `data/project_state.json` or `docs/PROJECT_STATE.md`, the current-state SSOT wins.
- Do not use this architecture PR to "clean up" old phase docs, old task reports, old PR bodies, or roadmap snapshots.
- Do not treat historical docs as contradictions requiring resolution; they simply describe a different point in time.

---

## 8. Non-Goals for This Document

This document defines architecture only. The following remain out of scope regardless of PR activity:

- No paid-credit run.
- No API call.
- No workflow dispatch.
- No promotion.
- No data-state update (`data/**` frozen).
- No historical-doc synchronization.
- No audit protocol expansion.
- No runtime code change.
- No changes to `.github/**`, `core/**`, `scripts/**`.

Note: `README.md`, `CLAUDE.md`, and `AGENTS.md` may receive cross-reference links pointing to this document as a separate, Project Owner-approved step. Such cross-reference additions do not change the architecture defined here and do not affect runtime behavior.
