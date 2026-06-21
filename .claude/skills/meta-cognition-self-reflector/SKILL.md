---
name: meta-cognition-self-reflector
description: Run a bounded meta-cognition reflection protocol for Cyber-Immunizer high-risk design, roadmap, experiment-interpretation, phase-transition, fitness-function, mutation-boundary, structured-rules integration, or value-claim decisions. Use only when explicitly invoked by the Project Owner.
disable-model-invocation: true
---

## Claude-specific invocation rules

This skill is manual-invocation only. It must not self-trigger for routine coding tasks. It may not edit files unless the Project Owner explicitly asks for a follow-up implementation task. It must produce a Reflection Report, not code changes.

## Purpose

This skill is a bounded reflection protocol for Cyber-Immunizer decisions. It audits reasoning, not code. It forces the agent to identify premises, evidence quality, counterarguments, alternative hypotheses, uncertainty, weakest links, and next verification steps before recommending a decision.

Use it as a meta-cognitive gate before high-risk interpretation or direction-setting. It does not replace final GPT audit, does not decide merge readiness, and does not prove Layer 2 defensive value.

## When to use

Use this skill for:

- new phase design
- architecture direction
- mutation boundary changes
- fitness function changes
- structured detector rules runtime integration decisions
- raw Python mutation path retirement decisions
- Layer 2 / Layer 3 progress classification
- experiment result interpretation
- paid-credit run decision-making
- roadmap / completion definition changes
- claims that score, tests, or tooling prove defensive value
- deciding whether a PR or task advances Layer 1 / Layer 2 / Layer 3

## When not to use

Do not use this skill for:

- simple typo fixes
- local test failures
- straightforward PR review
- routine CI triage
- small validation bug fixes
- task report wording only
- formatting-only changes
- dependency updates
- code implementation

If the task is implementation-focused, use a repair or PR audit skill instead.

## Hard boundaries

- Do not edit files by default.
- Do not write code by default.
- Do not open or modify a PR by default.
- Do not resolve review threads.
- Do not merge.
- Do not approve PRs.
- Do not run paid-credit.
- Do not call Gemini API.
- Do not trigger workflow_dispatch.
- Do not modify promotion state.
- Do not modify ledger/genome/state files.
- Do not claim Layer 2 progress from tooling, docs, or tests alone.
- Do not replace final GPT audit.

## Reflection workflow

Run the workflow in this exact sequence:

1. Decision Question
   - What exactly is being decided?
   - What is explicitly out of scope?
2. Pre-flight Premise Inventory
   - List explicit premises.
   - List hidden assumptions.
   - Mark unverified assumptions as red flags.
3. Inspect & Challenge
   - Grade evidence for each premise.
   - Identify where the reasoning depends on weak evidence.
4. Refute & Explore
   - Generate at least two counterarguments.
   - Generate at least two alternative approaches.
   - State what evidence would disprove the favored interpretation.
5. Synthesize & Converge
   - Separate known facts from inference.
   - State most defensible interpretation.
   - State uncertainty and confidence.
6. Weakest Link
   - Identify the weakest part of the reasoning.
7. Next Verification
   - List what to check now.
   - List what to check later.
   - List what not to check because it is not worth it.
8. Decision
   - Choose exactly one:
     - Proceed now
     - Create small implementation PR
     - Request more evidence
     - Defer
     - Reject

## Evidence grading

Grade every important claim or premise with one of these levels:

- E0 — unsupported assertion
- E1 — plausible but unverified
- E2 — supported by provided text or local observation
- E3 — supported by repo file / test / CI evidence
- E4 — supported by multiple independent sources or direct execution evidence

Every important premise must list:

- evidence level
- source or basis
- risk if false
- verification needed

## Refutation requirements

- Generate at least two serious counterarguments against the favored interpretation.
- Include the strongest version of each counterargument, not a strawman.
- State what specific evidence would disprove the favored interpretation.
- Explicitly flag any causal claim that is not directly supported by evidence.

## Alternative-hypothesis requirements

- Generate at least two alternative approaches or hypotheses.
- For each alternative, list pros, cons, and evidence needed.
- Do not collapse alternatives into the favored decision until after the evidence grading and refutation pass.

## Convergence / anti-overthinking rule

Reflection must be bounded. Maximum two reflection passes unless the Project Owner explicitly requests deeper analysis. If uncertainty remains after two passes, stop and produce the best available decision with uncertainty clearly marked.

The output must end with a concrete decision. Do not end with only more questions.

## Reflection Report template

```markdown
## Reflection Report
### 1. Decision Question
- Decision:
- Out of scope:
### 2. Explicit Premises
| Premise | Evidence level | Source / basis | Risk if false | Verification needed |
|---|---|---|---|---|
### 3. Hidden Assumptions / Red Flags
- Unverified assumptions:
- Ambiguous terms:
- Scope drift risks:
- Safety / repo-state risks:
### 4. Refutation Pass
| Claim | Strongest counterargument | What would disprove it |
|---|---|---|
### 5. Alternative Hypotheses
| Option | Pros | Cons | Evidence needed |
|---|---|---|---|
### 6. Synthesis
- Known facts:
- Inferences:
- Unknowns:
- Most defensible interpretation:
- Confidence:
### 7. Weakest Link
- Weakest link:
### 8. Next Verification
- Check now:
- Check later:
- Not worth checking:
### 9. Decision
Choose exactly one:
- [ ] Proceed now
- [ ] Create small implementation PR
- [ ] Request more evidence
- [ ] Defer
- [ ] Reject
### 10. Non-Replacement Statement
- This reflection does not replace final GPT audit.
- This reflection does not by itself authorize merge.
- This reflection does not prove Layer 2 value.
```

## Stop conditions

Stop and report instead of continuing if:

- required repository state evidence is unavailable for the decision being made
- the task turns into broad documentation expansion rather than bounded reflection
- the decision appears to require paid-credit, Gemini API, workflow_dispatch, promotion, merge, approval, or review-thread resolution
- the decision requires changing ledger, genome, state, detector runtime, CI, or protected files without explicit Project Owner authorization
- an existing canonical decision source already answers the question and no new decision is needed

## Final output requirements

- Produce a Reflection Report, not code changes, unless the Project Owner explicitly requested a follow-up implementation task.
- Separate facts from inferences.
- Include evidence levels for important premises.
- Include counterarguments and alternatives.
- State uncertainty and confidence.
- End with exactly one concrete decision from the allowed decision list.
- Include the non-replacement statement that the reflection does not replace final GPT audit, authorize merge, or prove Layer 2 value.
