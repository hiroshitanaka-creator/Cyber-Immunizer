# Reset Note — PR #86 and PR #87 Abandoned

**Risk Class:** S1 — Protocol / documentation reset  
**Date:** 2026-06-11  
**Author:** Project Owner (hiroshitanaka-creator)

---

## 1. Reset Decision

- **PR #86 is abandoned.** Its implementation branch will not be merged.
- **PR #87 is abandoned.** Its implementation branch will not be merged.
- The code changes from both PRs must not be merged into `main`.
- The useful requirements from both PRs are preserved in this document as input for future smaller PRs.
- **This reset does not change the current project phase.** The project remains in Phase 3, state `phase3_propose_output_contract_hardened_pending_owner_review`.
- **This reset does not authorize** API usage, paid-credit reruns, promotion, release, `workflow_dispatch`, or any change to `promote_approved`.

---

## 2. Why the Reset Is Necessary

The previous audit and rule-hardening direction became too large and too difficult for the Project Owner to control:

- PR #86 expanded the task-prompt protocol into a multi-requirement, multi-section system that is hard to operate without deep familiarity with every rule.
- PR #87 introduced a three-layer audit gate (Evidence Ledger + Audit Packet + Policy Engine + CI required check) that adds significant complexity and has open design issues (e.g., stale CI classification in full-mode evaluation).
- Stronger rules are **not automatically safer** when they create complexity, edge cases, and loopholes that the Project Owner cannot easily inspect or override.
- A large expert-only audit system creates a dependency on AI to interpret AI, rather than giving the Owner direct control.

The new direction is to:

- Reduce the number of active rules to what the Owner can confidently operate.
- Use one clear AI entrypoint instead of multiple layered protocols.
- Add deterministic guardrails in small, testable PRs rather than large, complex PRs.
- Build an Owner-controllable system first, then layer complexity only where it is proven necessary.

---

## 3. Requirements Preserved from PR #86

These task-prompt and scope-control requirements are valid and must be carried forward into the Project Operating System and future task contracts.

- **Bounded task prompt before editing.** Every implementation task must have a bounded task prompt before any file is edited.
- **One task = one PR = one purpose.** Do not mix multiple concerns in a single PR.
- **Explicit Goal.** Every task must state its goal in one sentence.
- **Explicit Risk Class.** Every task must state its risk level.
- **Explicit Allowed Paths.** Every task must list exactly which files may be created or edited.
- **Explicit Reference Only files.** Files that may be read but not edited must be listed separately.
- **Explicit Frozen Paths.** Files that must not be touched must be listed explicitly.
- **Explicit Impact section.** Expected runtime, state, and side-effect impact must be stated. "None" with a reason is acceptable.
- **Source Evidence requirement.** Claims about existing code must be supported by file citations, not assertions.
- **Verification commands requirement.** Every task must specify what to run and what result to expect.
- **Stop instead of guessing.** When the task is unclear, contradictory, or the scope is ambiguous, stop and report instead of editing.
- **Weak-model safety.** If an AI model cannot confidently verify the task boundaries, it must stop and report rather than proceed.
- **Duplicate-doc prevention.** Do not create a new protocol document if an existing canonical document should be updated instead. Check for overlap before creating new docs.
- **No API, no `workflow_dispatch`, no promotion, no release unless explicitly authorized** by the Project Owner in the task prompt.

---

## 4. Requirements Preserved from PR #87

These audit evidence and anti-laundering requirements are valid and must be carried forward. They define what counts as legitimate audit evidence in this project.

- **Diff-only audit is invalid for non-trivial PRs.** Reviewing only the diff without reading existing code context is not a complete audit.
- **Assertion-only audit evidence is invalid.** Saying "checked", "reviewed", "safe", "looks good", or "no issue found" without supporting evidence is not acceptable.
- **AI self-report is not machine evidence.** An AI's claim that it verified something is not the same as a machine-collected fact.
- **"Checked", "reviewed", "safe", "looks good", and "no issue found" are not sufficient evidence** on their own.
- **Evidence must be tied to files, line ranges, quotes, commands, and results.** Claims must reference specific locations in the codebase.
- **Changed files must be known.** An audit without a complete list of changed files is incomplete.
- **High-risk paths must be detected.** Changes to `scripts/**`, `.github/**`, `core/**`, `data/**`, and `tests/**` must be explicitly identified.
- **Base/diff context must exist for audit claims about changed files.** An auditor cannot make claims about what changed without the diff.
- **Missing diff context must fail closed.** If the diff is unavailable, the audit result must be HOLD, not APPROVE.
- **Machine facts and AI judgment must be separated.** Facts collected by script (head SHA, CI status, changed files) must not be mixed with AI-generated claims.
- **CI/audit gates must be read-only and secret-free.** Audit workflows must not have write permissions, API keys, or secrets.
- **CI success alone must not mean "approved".** A green CI run is a necessary but not sufficient condition for merge approval.
- **Owner approval is still required for high-risk operations.** CI and AI cannot substitute for explicit Project Owner sign-off on high-risk changes.
- **API, secret, paid-credit, promotion, and release operations must remain isolated.** These must not be triggered by audit workflows or AI agents without explicit Owner authorization.

---

## 5. Explicitly Not Carried Forward

The following are intentionally **not** carried forward as immediate implementation targets:

- A large multi-layer audit PR (the PR #87 approach).
- A complex initial policy engine.
- A complex Audit Packet system in the first reset step.
- A new CI required check in this reset.
- A new GitHub Actions workflow in this reset.
- A new `project_guard.py` script in this reset.
- Multiple AI entrypoints or protocol layers.
- Large protocol stacks that the Project Owner cannot easily operate without expert help.
- Any automatic approval mechanism.
- Any paid-credit rerun authorization.
- Any promotion or release authorization.

These may be reintroduced later, one at a time, as small and testable additions after the minimal foundation is stable.

---

## 6. New Direction After Reset

The project will build a minimal, Owner-controllable Project Operating System:

- **One AI entrypoint.** A single document that tells any AI agent how to work in this repository, without branching into multiple protocol documents.
- **PR risk classes.** A simple classification (S1 / S2 / S3 or equivalent) so the Owner can calibrate oversight proportionally.
- **WIP limit = 1.** Only one PR in flight at a time. The Project Owner reviews and closes each PR before the next begins.
- **One PR = one purpose.** No combining concerns.
- **Small deterministic `project_guard.py` first.** Before any complex audit tooling, add a lightweight guard script with clear, testable rules. This script runs in CI and fails deterministically on detectable violations.
- **Read-only CI only after the guard exists and has tests.** Do not add a CI workflow until the underlying script is stable and test-covered.
- **Branch protection only after the guard workflow is stable.** Enable required checks only after the workflow has been running without false positives.
- **Return to Phase 3 paid-credit readiness review only after the minimal guard and branch protection are in place.**

---

## 7. Future PR Roadmap

The following PRs are planned in order. Each is one purpose, one PR.

| # | PR | Purpose |
|---|---|---|
| 1 | Create minimal Project Operating System document | `docs/PROJECT_OPERATING_SYSTEM.md` — single AI entrypoint with risk classes and WIP limit |
| 2 | Create Owner Runbook | `docs/OWNER_RUNBOOK.md` — step-by-step Owner-facing guide for each risk class |
| 3 | Simplify AI entrypoint | Update `CLAUDE.md` and/or `AGENTS.md` to point to the new minimal OS; remove redundant protocol layers |
| 4 | Replace PR template with minimal Task Contract | Add a lean Task Contract template; deprecate the complex task prompt protocol |
| 5 | Add `project_guard.py` | A small, deterministic script that checks the most important invariants |
| 6 | Add tests for `project_guard.py` | Test coverage for the guard before adding CI |
| 7 | Add read-only `project-guard` workflow | CI job that runs `project_guard.py`; read-only, no secrets |
| 8 | Enable branch protection manually | Project Owner enables required checks in GitHub Settings |
| 9 | Review Phase 3 propose/output-contract readiness | Confirm that PR #84 hardening is sufficient before any paid-credit rerun |
| 10 | Authorize exactly one paid-credit rerun | Only if readiness review (step 9) confirms the fix is sufficient |
| 11 | Record rerun result | Document outcome in ledger and state files per existing protocol |
| 12 | Release v0.3 controlled-run state | Tag only if rerun produces a valid mutation patch and adoption gate passes |

---

## 8. Safety Confirmation

- [ ] No `.github/**` files changed.
- [ ] No `scripts/**` files changed.
- [ ] No `core/**` files changed.
- [ ] No `tests/**` files changed.
- [ ] No `data/**` files changed.
- [ ] No `README.md` changed.
- [ ] No `CLAUDE.md` changed.
- [ ] No `AGENTS.md` changed.
- [ ] No API call performed.
- [ ] No `workflow_dispatch` performed.
- [ ] No paid-credit run performed.
- [ ] No promotion performed.
- [ ] No release or tag created.
- [ ] `promote_approved` was not changed.
