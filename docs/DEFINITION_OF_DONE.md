<!--
AI_DOC_META:
  doc_type: definition_of_done
  status: CANONICAL
  scope: project-wide completion layers
  authority: |
    Defines what "done" means across three distinct layers.
    A task MUST declare which layer it advances.
    Subordinate to current-state SSOT:
      data/project_state.json / docs/PROJECT_STATE.md / data/genome.json / machine evidence.
  must_read_for:
    - value / deliverable / roadmap / completion tasks
    - PRs that claim practical defensive value
    - tasks that classify docs-only work
  read_alongside: docs/VALUE_DELIVERY_BLUEPRINT.md
-->

# Cyber-Immunizer — Completion Layers / Definition of Done

This document does not define a single universal "done."
Cyber-Immunizer has three distinct completion layers. **A task must declare which layer it advances.**
Docs-only tasks are allowed only when they clearly advance Layer 1 or Layer 3.
They do not by themselves satisfy Layer 2.

---

## Layer 1 — Research Foundation Completion

This layer proves that the repository is not "nothing happened."  
It does NOT prove real-world defensive usefulness by itself.

### Layer 1 criteria (all must hold)

| ID | Component | Completion condition |
|---|---|---|
| L1-F1 | AST safety policy | `core/policy.py::run_full_policy` blocks all forbidden builtins / modules / dunder / eval in 17 checks. `tests/test_ast_policy.py` fully green. Zero false-accepts. |
| L1-F2 | Mutation boundary | `MUTATION_START` / `MUTATION_END` markers enforced. Bytes outside the region are invariant after apply. |
| L1-F3 | Propose path | `scripts/propose_mutation.py` operates in all 5 modes (noop / offline-sample / live / paid-credit / preflight) with exit 0. Secret scan passes. Patch schema validates. |
| L1-F4 | Apply path | `scripts/apply_mutation.py` applies patch inside mutation region only. Post-apply F1 re-validation passes. |
| L1-F5 | Evaluate path | `scripts/evaluate_candidate.py` runs inside digest-pinned Docker. `--soft-reject` distinguishes tool failure (exit 1) from gate rejection (exit 0). |
| L1-F6 | Promote path | `scripts/promote_candidate.py` is fail-closed: attestation required, no promotion without it. `detector.py` / `genome.json` / `evolution_history.json` updated atomically. |
| L1-F7 | Deterministic fitness | Same candidate + same corpus → bitwise-identical score. `avg_latency_ms` and `changed_lines` excluded from ranking score. |
| L1-F8 | Adoption gate | `fp_rate ≤ max_fp_rate`, `score > previous_best`, regression / holdout / counterfactual / drift pass rates satisfied. |
| L1-F9 | API budget gate | `scripts/api_budget.py` blocks API calls when monthly or daily budget is exceeded. Estimates are always over-counted. |
| L1-F10 | State schema validation | `scripts/validate_state.py` validates 10 data files: `genome.json`, `evolution_history.json`, `project_state.json`, `active_threats.json`, `benign_requests.json`, `attack_requests.json`, `regression_cases.json`, `holdout_requests.json`, `counterfactual_requests.json`, `drift_requests.json`. Exit 0. **Note: `api_usage_ledger.json` is not validated by this script.** |
| L1-F11 | SSOT state tracking | `data/project_state.json` (machine-readable) and `docs/PROJECT_STATE.md` (human-readable) stay in sync. Authority order documented. |
| L1-F12 | Subprocess / Docker isolation | Candidate execution never runs on host. Docker digest pinned in `security/docker_digest_allowlist.json`. No write credentials passed. |
| L1-F13 | Paid-credit boundary | `live_model_enabled=true` and paid-credit API mode require explicit Project Owner approval. Scheduled runs default to noop. |
| L1-F14 | Structured detector decision | `core/structured_*` is either (a) integrated with a single call path and equivalence tests green, or (b) explicitly documented as experimental / non-integrated with tests asserting the separation. Decision is recorded. |
| L1-F15 | Rollback / Backtrack | Scope: future work. `ROLLBACK_BACKTRACK_DESIGN.md` exists as design record. Implementation is a separate future task. |
| L1-F16 | NVD / CVE live fetch | Scope: intentionally disabled or future Owner-approved scope only. The disabled stub in `intelligence/threat_feeds.py` must remain commented out with no exploit payloads stored. |

**Layer 1 is complete when all L1-F1 through L1-F13 hold, and L1-F14 is resolved (integrated or documented), and L1-F15 / L1-F16 are either deferred or resolved.**

---

## Layer 2 — Value Validation Completion

Layer 2 determines whether the system's outputs have meaningful defensive value
beyond symbolic corpus reporting.

**Layer 2 does NOT mean: create external-facing deliverables.**

The following are **explicitly blocked until Layer 2 is satisfied:**
- `cyber-immunize scan` or any scan CLI for external users
- Packaged / installable detector distributions
- GitHub Action templates for external projects
- Dashboards (Streamlit / Gradio / similar)
- Public demos or published benchmark results
- PyPI or other package registry publication

**`cyber-immunize report`, if built, is positioned as an Owner / auditor-facing
validation tool only, not as proof of external user value.**
A useless artifact exposed to external users is not a high-level deliverable.

### Layer 2 criteria (all must hold before externalization is permitted)

| ID | Requirement | Completion condition |
|---|---|---|
| L2-V1 | Realistic threat coverage | Detector evaluated against realistic but safe / neutralized threat categories (not symbolic-only corpus). Threat categories must cover at minimum: path traversal, XSS-class, SQLi-class, command delimiter. |
| L2-V2 | TP / FP / FN reporting | Clear per-category TP / FP / FN and latency reporting. Results are reproducible and deterministic. |
| L2-V3 | Holdout / drift / counterfactual | Adaptive floor tiers (holdout, drift, counterfactual) are evaluated and pass rates reported. Overfitting risk explicitly addressed. |
| L2-V4 | Improvement explanation | Document explains which threat classes improved generation-over-generation and why. Score increase from the first evaluated generation (gen1) to genN is not claimed as defensive value unless linked to threat-class coverage improvement. gen0 is an unevaluated placeholder and must not be used as a scored baseline. |
| L2-V5 | No overfitting claim | Results distinguish between symbolic corpus performance and realistic threat coverage. Claims are bounded to what the evaluation actually demonstrates. |

**Layer 2 is complete when L2-V1 through L2-V5 all hold and the Project Owner
has reviewed and accepted the value validation evidence.**

---

## Layer 3 — AI Operation Control Completion

Layer 3 captures why docs can be necessary while still preventing docs bloat.
It defines the boundary between useful documentation and process theater.

### Docs-only task classification

A docs-only task (no executable code changed) is **allowed** only when it falls
into one of these categories:

| Category | Examples |
|---|---|
| **Owner Intent / Claim Record** | This blueprint, Owner complaint preservation, failure-mode records |
| **Safety Boundary** | FROZEN rules, exploit exclusion policy, paid-credit gates |
| **Current-State SSOT** | `docs/PROJECT_STATE.md`, `data/project_state.json` updates |
| **Audit Evidence** | PR audit reports, task reports with commit SHA citations |
| **User-facing Manual** | Operation guide for an *existing* executable feature |
| **Minimal Task Report** | Required by repo policy; bounded to necessary evidence |

A docs-only task is **suspect or disallowed** when it is:

- Broad roadmap expansion with no executable counterpart
- Broad completion definition expansion (adding more criteria without advancing execution)
- New protocol or checklist layer that creates process burden without defensive value
- Duplicate explanation of existing docs
- Task report expanded beyond necessary evidence
- "Looks complete" documentation with no connection to actual executable or validated capability

**Saying "docs-only is always useless" is wrong.**
Saying "docs-only counts as Value Validation Completion" is also wrong.
Docs-only is allowed when it protects intent, safety, state, auditability, or user operation.
It must not be counted as progress toward Layer 2.

### Layer 3 criteria

| ID | Requirement | Completion condition |
|---|---|---|
| L3-A1 | Value / docs discipline active | CLAUDE.md contains a concise rule preventing task drift into docs-only theater. |
| L3-A2 | Task layer declaration | Tasks declare which layer they advance (see below). |
| L3-A3 | Docs classification enforced | PR audits check whether docs-only PRs fall into an allowed category. |
| L3-A4 | Future automation path | A Skill / Custom GPT / Codex post-task classifier is proposed or implemented (see below). |

**Layer 3 is complete when L3-A1 through L3-A3 hold and L3-A4 has been at minimum proposed.**

---

## Task layer declaration (required for all tasks)

Every task completion report must include:

```
Which layer did this task advance?
[ ] Layer 1 — Research Foundation
[ ] Layer 2 — Value Validation
[ ] Layer 3 — AI Operation Control
[ ] None

If docs-only, classify:
[ ] Owner Intent / Claim Record
[ ] Safety Boundary
[ ] Current-State SSOT
[ ] Audit Evidence
[ ] User-facing Manual for existing executable feature
[ ] Minimal Task Report
[ ] Redundant — should not have been added
```

This classification is intended for implementation via Skill / Custom GPT / Codex
post-task checks rather than as a manual doc-writing requirement.
**Do not make this a large new protocol. It is a checklist, not a ceremony.**

---

## Supporting quality criteria (Layer 1 supporting, not headline completion)

These are real quality requirements, but they are supporting criteria for Layer 1,
not the central definition of project completion.

- **Runtime dependency**: `pyproject.toml` `dependencies=[]` maintained. No new runtime deps without Owner approval.
- **Type annotations**: All public functions in `core/` and `scripts/` annotated (`from __future__ import annotations` consistent).
- **Determinism**: Same candidate + corpus → bitwise-identical score.
- **Secret hygiene**: No API keys, personal paths, or real environment config in repo. `config.backup.toml` removal is outstanding (as of HEAD `39d60d9`).
- **Test green**: `pytest tests/ -x -q` passes without modification to FROZEN files.
- **Naming**: No mojibake filenames, no space-in-path directories, no extension-less source/doc files.

---

## What this document does NOT define as completion

- Lint / type check / coverage threshold enforcement is useful but not the project's completion headline.
- Adding more docs, tests, or protocols is not progress toward Layer 2.
- Symbolic corpus score improvement (gen1→gen4: 383.67→948.04; gen0 is an unevaluated placeholder, not a scored baseline) is research foundation evidence, not defensive value evidence.
- Package export, scan CLI, CI templates, or dashboards are blocked until Layer 2 is satisfied.
- `cyber_immunizer.core` as a public importable package namespace does not exist yet; it is a future packaging decision and must not be claimed as implemented.

---

> Authority: This document is subordinate to `data/project_state.json`, `docs/PROJECT_STATE.md`,
> `data/genome.json`, and machine evidence (per CLAUDE.md authority order).
> Current state is determined by those sources; this document defines completion criteria only.
