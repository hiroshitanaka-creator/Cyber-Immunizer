<!--
AI_DOC_META:
  doc_type: value_delivery_blueprint
  status: CANONICAL
  scope: project-wide value direction and external-deliverable standard
  authority: |
    Canonical for deciding what counts as value-producing work in Cyber-Immunizer.
    Does not override current-state SSOT: machine evidence, data/project_state.json,
    docs/PROJECT_STATE.md, data/genome.json, and CI remain authoritative for state.
  intent: Prevent docs/tests/protocol accumulation from being mistaken for completion.
-->

# Cyber-Immunizer — Value Delivery Blueprint

Cyber-Immunizer is not a documentation project. It is a defensive autonomous-code-evolution repository whose current strength is the safety-governed evolution engine: AST policy, subprocess/Docker isolation, deterministic fitness evaluation, adoption gates, SSOT state tracking, and a Generation 4 promoted baseline.

The next phase is not “more complete documentation.” The next phase is converting that engine into executable outputs that a developer can run locally and use to observe a measurable defensive improvement.

---

## 1. Non-negotiable value standard

A change is value-producing only if it advances at least one of the following:

1. **Executable local output** — a CLI, library API, export command, report generator, scanner, or integration example that a user can run.
2. **Measurable defensive result** — before/after score, TP/FP/FN, latency, adoption-gate outcome, coverage delta, or per-request verdicts.
3. **Externalizable artifact** — Markdown/JSON report, packaged detector, local fixture format, CI template, or ruleset interface usable outside this repository.
4. **Safety-critical enablement** — a small guard that directly prevents unsafe execution, false promotion, cost leakage, or payload leakage.

A PR that only adds more documentation, tests, protocol language, checklists, roadmaps, or completion definitions is **not value-producing by default**. It is acceptable only when it is explicitly requested by the Project Owner or when it removes ambiguity that blocks a named executable deliverable.

---

## 2. What is already real

The repository is not empty research scaffolding. Current-state SSOT records that Phase 3 is active, paid-credit API connection succeeded, Generation 4 is the current promoted baseline, and the adoption gate has passed at least once.

That is a real foundation. It should be treated as an engine to export value from, not as permission to add more meta-process.

The current limitation is equally real: the promoted detector and committed evaluation corpus are intentionally neutralized/symbolic. That protects the repository from becoming an exploit corpus, but it also means internal score improvement is not yet the same as real-world defensive usefulness.

Therefore, the path forward is:

> keep the repository neutralized and defensive-only, while allowing users to supply their own local fixtures/rulesets outside the repository and receive measurable local reports.

---

## 3. Safety boundary for practical outputs

Practical outputs must preserve the existing defensive-only boundary.

- Do not commit raw exploit payloads, exploit-like examples, attack recipes, bypass guidance, or real traffic captures.
- Committed examples and rulesets must stay neutralized/symbolic.
- If real-world signatures or request samples are needed, they must be **user-supplied local files** that are read at runtime and never committed to the repository.
- Do not connect to real traffic, scan networks, call paid-credit APIs, or trigger workflow_dispatch unless the Project Owner explicitly approves it for that task.
- Prefer read-only consumer-layer additions over edits to FROZEN areas (`core/**`, `scripts/**`, `.github/**`, `data/**`).

---

## 4. Product direction: engine vs consumer layer

The existing engine should remain stable and conservative:

- `core/**` and `scripts/**` are the defensive evolution engine.
- `data/**` is SSOT/evidence and evaluation state.
- `.github/**` is workflow control.

External value should be built in a separate consumer layer first:

```text
cyber_immunizer/
  cli/
    report.py
    scan.py
  reporting.py
  local_fixture.py
examples/
  neutralized_requests.json
  github-action/
```

This avoids turning the safety engine into a product surface too early.

Short term, consumer code may import existing top-level packages such as `core.*`. A future packaging cleanup may introduce a `cyber_immunizer.*` namespace package, but do not claim `cyber_immunizer.core` exists until it is actually implemented.

Runtime dependencies should remain empty by default. Use the standard library first. Optional UX dependencies such as `rich` or `typer` may be considered later, isolated behind extras, only after a working CLI exists.

---

## 5. First executable deliverable

The first value-producing implementation should be:

```text
PR-VALUE-001: cyber-immunize report
```

Goal: add a read-only local CLI that converts internal evolution evidence into a human-readable and machine-readable value report.

Minimum behavior:

```bash
python -m cyber_immunizer.cli.report --format markdown --output cyber-immunizer-value-report.md
```

The report must show, at minimum:

- current generation and detector hash from `data/genome.json`
- promoted generation history from `data/evolution_history.json`
- Generation 1 -> Generation 4 score delta (`383.67 -> 948.04` from current evidence)
- TP/FP/FN rates, average latency, and adoption-gate status when present
- a clear statement that the current committed corpus is neutralized/symbolic and that real-world usefulness requires user-supplied local fixtures/rulesets in later deliverables

Generation 0 must not be used as the score baseline unless the report explicitly labels it as an unevaluated placeholder.

Definition of Done for PR-VALUE-001:

- CLI exits 0 without API calls, workflow dispatch, Docker requirement, or real traffic.
- FROZEN areas are read-only unless the Project Owner explicitly approves otherwise.
- Output is available as terminal text, JSON, and Markdown file export.
- Tests cover the Generation 1 -> Generation 4 baseline selection and reject accidental `gen0 -> gen4 score 383 -> 948` labeling.
- Existing test suite remains green.

---

## 6. Merge policy implication

From this point forward, default task selection should favor executable value over process expansion.

Prefer:

- report CLI
- scan CLI over user-supplied local fixtures
- structured-rules opt-in interface over committed raw signatures
- CI integration examples under `examples/`
- exported detector/report artifacts

Avoid:

- new broad completion documents
- new mandatory reading requirements
- new protocol layers unless they remove or replace older process
- docs-only PRs that do not unblock a named executable deliverable

The Project Owner remains the final decision-maker. This blueprint exists to prevent the project from mistaking governance, documentation, or test volume for delivered security value.
