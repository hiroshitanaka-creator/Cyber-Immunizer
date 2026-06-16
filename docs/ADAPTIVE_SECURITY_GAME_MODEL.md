# Adaptive Security Game Model

<!--
AI_DOC_META
document_id: adaptive_security_game_model
status: PLANNING
authority_scope: next_architecture_layer
scope: Defines the proposed next architecture layer for Cyber-Immunizer as a defensive adaptive security game layered above the current fitness/adoption gate.
current_state_authority: data/project_state.json and docs/PROJECT_STATE.md remain authoritative for runtime/current-state interpretation.
use_for:
  - planning migration from fixed-corpus fitness scoring toward adaptive defensive tournaments
  - distinguishing regression gates from competitive adaptive-performance scores
  - defining defensive-only evaluation tiers and metrics for future implementation tasks
do_not_use_for:
  - claiming the adaptive tournament is implemented
  - executing paid-credit API runs
  - changing model names, budget settings, promotion behavior, workflow behavior, or ledger state
  - adding raw exploit payloads, offensive tooling, scanning logic, or credential logic
related:
  - docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md
  - docs/PROJECT_STATE.md
  - data/project_state.json
AI_DOC_META_END
-->

---

## 1. Purpose and status

This document defines Cyber-Immunizer's next architecture layer as an **adaptive, adversarial, defensive security game** rather than a static fitness optimizer over a fixed corpus.

This is a planning document only. It does **not** claim that the adaptive tournament, new metrics, new gates, or new memory model are implemented. The current machine state remains governed by `data/project_state.json`, `docs/PROJECT_STATE.md`, and the existing Autonomous Immune Loop architecture.

PR #105 should be interpreted as a **static-gate correction**: it improved the current fixed fitness/adoption-gate behavior and helped prevent regressions in the existing evaluation path. It is not the final adaptive security game model and should not be treated as completion of this architecture layer.

---

## 2. Why fixed corpus score maximization is insufficient

The current fitness gate is necessary, but it is not sufficient as the final measure of defensive capability.

A fixed corpus can prove that a candidate preserves known behavior against known examples. It cannot prove that the candidate will remain effective as the threat distribution changes, as benign traffic shifts, or as an adversary adapts to the detector's visible behavior. If the system optimizes only for a static score, it can overfit to the current examples, maximize narrow symbolic matches, or trade away future adaptability while still appearing to improve.

Static score maximization is insufficient because:

- **Threats are non-stationary.** Defensive behavior must be evaluated against changing patterns, not only against examples already present in the corpus.
- **Adversaries adapt.** A detector that blocks a known symbolic indicator may still fail when the same defensive concept appears in a neutralized variant or new context.
- **Benign environments drift.** False-positive cost changes when normal request shapes, headers, paths, or bodies evolve.
- **Regression tests are floors, not objectives.** Passing historical safety and regression tests is a minimum requirement, not evidence of adaptive strength.
- **No-op or cosmetic mutations can score well locally.** A candidate may preserve the old score without adding meaningful defensive capability.
- **Memory must be evaluated.** A system that records prior failures but cannot use them to improve the next cycle is not genuinely adaptive.

The next architecture layer therefore separates two concepts:

| Concept | Role | Promotion meaning |
|---|---|---|
| Regression gate | Safety floor that prevents known-bad regressions and unsafe behavior. | Candidate is eligible for further evaluation only if the floor passes. |
| Competitive score | Adaptive-performance measure in a defensive tournament. | Candidate demonstrates stronger adaptation under drift, counterfactuals, and memory-aware evaluation. |

---

## 3. Adaptive security game model

Cyber-Immunizer should model each evaluation cycle as a defensive game over time step `t`:

```text
(D_t, A_t, E_t, M_t) --candidate action--> D_{t+1}
                 \--gate G_t evaluates safety and eligibility
```

The model is defensive-only. `A_t` represents neutralized, symbolic adversary pressure used for evaluation; it is not an offensive agent and must not contain raw exploit payloads or executable attack instructions.

### 3.1 Defender state `D_t`

`D_t` is the defender's current state at time `t`.

It includes:

- the current detector behavior;
- the current genome/configuration relevant to defensive evaluation;
- known symbolic indicators and policy boundaries;
- current regression expectations;
- the candidate mutation under evaluation, when evaluating `D_t -> D_{t+1}`.

`D_t` answers: **what defensive capability does the system currently have, and what change is being proposed?**

### 3.2 Threat/adversary state `A_t`

`A_t` is the neutralized adversarial pressure set at time `t`.

It includes:

- known threat classes represented by symbolic, non-actionable indicators;
- neutralized variants that preserve defensive concepts without exposing raw payloads;
- counterfactual examples that test whether the detector learned a concept rather than memorizing a string;
- drift scenarios that simulate future or holdout pressure.

`A_t` must remain defensive and inert. It must not include working exploit strings, offensive tooling, scanning behavior, credential acquisition logic, or instructions that enable misuse.

### 3.3 Environment `E_t`

`E_t` is the benign and operational context at time `t`.

It includes:

- representative benign request shapes;
- expected protocol and application variation;
- false-positive cost assumptions;
- runtime/resource constraints;
- sandbox and policy constraints for evaluation.

`E_t` answers: **what normal-world conditions must the defender preserve while adapting?**

### 3.4 Memory `M_t`

`M_t` is the system's accumulated, safety-bounded memory.

It includes:

- prior candidate outcomes;
- prior rejection reasons;
- known regression-preservation lessons;
- neutralized summaries of past threat drift;
- evidence about which memories improved or harmed future evaluations.

Memory is useful only if it improves later defensive decisions without causing unsafe scope expansion, overfitting, or stale-state contradictions. The tournament should measure whether `M_t` changes outcomes, not merely whether memory exists.

### 3.5 Gate `G_t`

`G_t` is the combined gate at time `t`.

It has two distinct responsibilities:

1. **Regression gate / safety floor.** Reject candidates that violate T0 safety, regress known behavior, increase unacceptable false positives, modify forbidden surfaces, or fail policy checks.
2. **Competitive adaptive score.** Rank candidates that pass the floor according to adaptive performance across higher tiers.

`G_t` must never allow a high competitive score to override the safety floor. A candidate that fails the regression gate is rejected even if it appears strong on adaptive scenarios.

---

## 4. Evaluation tiers

The adaptive tournament should evaluate candidates through increasingly demanding defensive tiers. Lower tiers are eligibility gates; higher tiers measure adaptive strength.

| Tier | Name | Purpose | Gate role |
|---|---|---|---|
| T0 | Safety | Enforce defensive-only boundaries, syntax validity, sandbox constraints, forbidden-path constraints, no raw exploit payloads, no offensive tooling, no scanning, and no credential logic. | Hard gate; any failure rejects. |
| T1 | Regression | Preserve current known-good behavior, including existing symbolic detections, benign non-blocking cases, and current fixed-corpus expectations. | Hard gate; any unacceptable regression rejects. |
| T2 | Known threats | Evaluate against known neutralized threat classes and symbolic indicators that represent already-understood defensive concepts. | Eligibility plus score component. |
| T3 | Synthetic neutralized variants | Evaluate concept preservation under generated inert variants that avoid raw payloads and offensive instructions. | Adaptive score component after T0/T1 pass. |
| T4 | Adaptive counterfactuals | Evaluate whether the candidate handles safe counterfactual pressure, including near misses, benign lookalikes, and concept shifts that expose overfitting. | Adaptive score component after T0/T1 pass. |
| T5 | Holdout/future drift | Evaluate against held-out or future-drift scenarios that were not used to propose the candidate. | Highest-confidence adaptive score component; never bypasses T0/T1. |

The tier ordering is intentional: T0 and T1 prevent unsafe or regressive candidates from entering the tournament, while T2 through T5 measure increasingly robust adaptive defensive performance.

---

## 5. Metrics

The adaptive security game should track metrics that cannot be reduced to one fixed-corpus score.

### 5.1 Adaptation latency

Measures how many cycles, proposals, or evaluation attempts are required before the system improves against a new neutralized threat class or drift scenario without violating T0/T1.

Lower latency is better only when safety and regression preservation remain intact.

### 5.2 Robustness under drift

Measures how much defensive performance is preserved as `A_t` and `E_t` shift across neutralized variants, counterfactuals, and holdouts.

A robust candidate should not depend on a single string, fixture, or narrow corpus artifact.

### 5.3 False-positive cost

Measures the cost of blocking benign behavior in `E_t`.

False-positive cost should be explicit because an aggressive detector can appear strong against threats while harming normal traffic. The cost model should distinguish minor benign friction from severe benign blocking.

### 5.4 Regression preservation

Measures preservation of known-good behavior from T1 and current project expectations.

This remains a floor metric: adaptive gains do not compensate for unacceptable regression in required known behavior.

### 5.5 No-op rejection

Measures whether the tournament rejects candidates that are cosmetic, behavior-preserving without meaningful adaptive gain, or merely tuned to pass the old fixed score.

A no-op candidate may pass T0/T1 but should not receive a competitive score high enough to be adopted as adaptive progress.

### 5.6 Memory usefulness

Measures whether `M_t` improves future outcomes.

Useful memory reduces repeated failure modes, improves adaptation latency, preserves regression lessons, or improves drift robustness. Memory that only accumulates stale summaries, contradicts canonical state, or causes unsafe behavior should score poorly or be pruned.

---

## 6. Safety constraints

The adaptive security game must remain defensive-only.

Hard constraints:

- Do not include raw exploit payloads.
- Do not add offensive tooling.
- Use neutralized symbolic indicators only.
- Do not add network scanning.
- Do not add credential logic.
- Do not provide operational attack instructions.
- Do not allow adaptive scoring to override safety checks.
- Do not change promotion, model, ledger, workflow, or paid-credit behavior as part of this planning layer.

Safe scenario examples should be abstract and inert, such as `symbolic_traversal_indicator`, `neutralized_script_marker`, or `benign_lookalike_header`. They should test defensive concepts without becoming executable attack content.

---

## 7. Migration plan from current fitness gate to adaptive tournament

The migration should be incremental and should preserve the current gate as a safety floor while adding adaptive scoring around it.

### Step 1 — Document the split between floor and score

Keep the current fixed fitness/adoption gate as the initial regression gate. Explicitly rename its architectural role in future work: it is the T0/T1 safety and regression floor, not the final objective function.

### Step 2 — Inventory existing fixtures by tier

Classify current evaluation cases into T0, T1, and T2. Do not add new raw exploit strings. Where current fixtures need broader representation, use neutralized symbolic indicators rather than operational payloads.

### Step 3 — Add inert variant generation as data, not offensive logic

Introduce future T3 fixtures as neutralized symbolic transformations. The variant generator, if implemented later, should operate only on safe labels and abstract features, not on raw exploit payloads or executable attack material.

### Step 4 — Add counterfactual evaluation

Introduce T4 safe counterfactuals that test overfitting and benign lookalikes. These should be designed to increase confidence that the detector learned defensive concepts while controlling false positives.

### Step 5 — Add holdout/future-drift sets

Introduce T5 holdouts that are unavailable to the proposal step. Holdouts should be versioned and protected from prompt-time leakage so that competitive score measures generalization rather than memorization.

### Step 6 — Add adaptive metrics beside the existing score

Report adaptation latency, drift robustness, false-positive cost, regression preservation, no-op rejection, and memory usefulness as separate fields before combining them into a tournament score.

### Step 7 — Introduce tournament ranking only after floor pass

Rank only candidates that pass T0 and T1. A candidate that fails the regression gate remains rejected regardless of its T2-T5 performance.

### Step 8 — Connect memory to the next cycle

Allow future cycles to consume safety-bounded memory summaries of prior outcomes. Evaluate whether that memory improves future proposal quality and adaptive score without contradicting canonical state.

### Step 9 — Keep promotion owner-gated

Even after adaptive tournament scoring exists, promotion must remain subject to the existing project safety model, including owner approval where required. Adaptive score is evidence for adoption; it is not independent permission to promote.

---

## 8. Required distinction: regression gate vs. competitive score

Cyber-Immunizer must preserve this distinction in future implementation and documentation:

```text
Regression gate = safety floor.
Competitive score = adaptive performance.
```

The regression gate answers: **is this candidate safe enough and non-regressive enough to consider?**

The competitive score answers: **among safe, non-regressive candidates, which one adapts best under known threats, neutralized variants, counterfactuals, future drift, false-positive costs, and memory-aware evaluation?**

A candidate can pass the regression gate and still fail to represent adaptive progress. A candidate can appear strong competitively and still be rejected if it violates the safety floor. This separation is the core architectural change from static fitness optimization to an adaptive security game.
