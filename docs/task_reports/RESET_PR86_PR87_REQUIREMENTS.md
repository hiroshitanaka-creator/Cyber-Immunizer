# Reset Note — PR #86 and PR #87 Abandoned

**Date:** 2026-06-10  
**Branch:** claude/cyber-immunizer-minimal-os-reset-lto21f  
**Risk Class:** S1 — Protocol / docs reset

---

## Decision

PR #86 and PR #87 are abandoned as implementation branches by Project Owner decision.
Their code changes must not be merged. This document preserves only the requirements that informed them.

---

## Requirements Preserved from PR #86

These requirements remain valid and must be honoured in future task prompts:

1. **Bounded task prompt** — Every task prompt must define a clear, single-sentence purpose and an explicit allowed-file scope before implementation begins.
2. **Allowed / Reference / Frozen path declarations** — Each task prompt must list files under one of three classifications: editable (`ALLOWED`), read-only context (`REFERENCE_ONLY`), or immutable (`FROZEN`).
3. **Source evidence** — Any claim about current code must cite a concrete file path, line range, and verbatim excerpt. Assertion-only evidence is invalid.
4. **Verification commands** — The task prompt must specify at least one shell command that proves the change is complete (e.g., `pytest`, `python -m json.tool`).
5. **Stop instead of guessing** — When the task is ambiguous or a required piece of information is missing, the AI must stop and report rather than proceed with a guess.
6. **Weak-model safety** — The task prompt must not rely on the AI discovering constraints through inference; all invariants must be stated explicitly so a less-capable model can follow them.

---

## Requirements Preserved from PR #87

These audit principles remain valid and must be applied in all future PR reviews:

1. **Diff-only audit is invalid** — Reviewing only the changed lines is insufficient. A valid audit must examine the full context of each changed file.
2. **Assertion-only evidence is invalid** — Claims like "reviewed", "checked", "seems fine", or "no issue found" are not acceptable as audit evidence. Each finding must cite file, line, content, and result.
3. **AI self-report is not machine evidence** — An AI's statement that tests passed is not equivalent to a CI log showing tests passed. Machine evidence is a recorded output from an automated system.
4. **Changed files must be known** — An audit is invalid if the list of changed files is incomplete or unverified against the actual diff.
5. **High-risk paths must be detected** — Any PR touching `.github/**`, `data/**`, `core/**`, `scripts/**`, `tests/**`, or `CLAUDE.md` must be explicitly flagged as elevated risk.
6. **CI gate should be read-only and secret-free** — CI scripts invoked from PRs must not read secrets, trigger paid-credit API calls, or write to production data paths.

---

## Intentionally NOT Carried Forward

The following patterns from PR #86 and PR #87 are dropped without replacement:

- Large multi-layer audit PR structure — too much complexity for current project scale.
- Complex initial policy engine — premature abstraction before `project_guard` exists.
- Complex handoff protocols with 10-item gates across multiple AI sessions — added overhead without proportionate safety gain at this scale.
- Multiple AI entrypoints routing to different protocol documents — consolidate to one entrypoint.
- GPT self-score requirements (e.g., "98/100") — scores are not machine evidence and must not gate decisions.

---

## New Direction

The project moves to a minimal **Project Operating System** with these properties:

1. **One AI entrypoint** — All AI sessions read a single, short entry document before acting.
2. **PR risk class** — Every PR is classified S0–S4 before work begins; the class determines merge rules.
3. **`project_guard` first** — No `.github` workflow changes, no branch protection rules, and no paid-credit reruns until a `project_guard` script exists and passes locally.
4. **Branch protection after guard is stable** — Branch protection is enabled only after `project_guard` has been verified in at least one successful PR cycle.
5. **Return to Phase 3 paid-credit controlled rerun only after the guard exists** — The `data/project_state.json` field `promote_approved` remains `false` until a separate, Owner-approved promotion PR is merged.
