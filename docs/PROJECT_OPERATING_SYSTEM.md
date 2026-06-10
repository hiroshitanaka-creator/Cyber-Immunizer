# Project Operating System — Cyber-Immunizer

**Version:** 0.1  
**Date:** 2026-06-10  
**Status:** Active — minimal bootstrap

This document defines the roles, authority model, PR risk classes, and state machine for the Cyber-Immunizer project.
It replaces the multi-document protocol stack that was being built in PR #86 and PR #87.

---

## 1. Roles

| Role | Who | Responsibilities |
|---|---|---|
| **Project Owner** | Human (hiroshitanaka-creator) | Final approve, merge, paid-credit authorization, promotion decisions |
| **Implementation AI** | Claude Code (this session) | Propose, implement, verify locally, commit, push — within allowed scope |
| **Audit AI** | Claude or GPT invoked by Owner | Review PRs, produce audit reports — read-only, no merge authority |
| **Machine Gate** | `project_guard` script (future) | Enforce forbidden-operation checks before each commit or push |
| **GitHub Branch Protection** | GitHub settings (future) | Require passing status checks and Owner review before merge |

---

## 2. Authority Model

| Actor | May do | May not do |
|---|---|---|
| Implementation AI | Propose, implement, commit, push to feature branch | Approve PRs, merge PRs, run Gemini/paid-credit API, promote mutations, cut releases |
| Audit AI | Read code, produce reports, post comments | Approve PRs, merge PRs, modify code |
| Machine Gate | Block commits that violate policy | Approve or merge anything |
| Project Owner | Everything the above actors may not do | Nothing prohibited (Owner has full authority) |

**S3/S4 actions require explicit Owner approval each time.** A prior approval for one PR does not authorize the same action in another PR.

---

## 3. PR Risk Classes

Every PR must be assigned one risk class before work begins.

| Class | Scope | Examples |
|---|---|---|
| **S0** | Cosmetic only | Typo fixes, whitespace, comment wording |
| **S1** | Docs / protocol | `docs/**`, `CLAUDE.md`, `AGENTS.md`, `README.md` |
| **S2** | Scripts / tests / schemas | `scripts/**`, `tests/**`, JSON schema files |
| **S3** | CI / data / project state / workflows | `.github/**`, `data/**`, `data/project_state.json` |
| **S4** | API / secret / paid-credit / promote / release | Gemini API calls, secret references, `promote_approved=true`, version tags |

A PR that touches files in multiple classes is assigned the highest applicable class.

---

## 4. WIP Rule

- **WIP limit = 1.** Only one feature branch may be open for active development at any time.
- **One PR = one purpose.** A PR may not combine unrelated concerns (e.g., docs reset + CI fix).
- If a second PR is needed before the first merges, the first must be merged, closed, or explicitly parked by the Owner.

---

## 5. Project State Machine

The project advances through the following states in order.
Skipping a state requires explicit Owner authorization.

| State ID | Description | Entry condition |
|---|---|---|
| `RESET_RULES` | Abandon PR #86/#87 direction; write minimal OS docs | Owner decision |
| `MINIMAL_OS` | This document and OWNER_RUNBOOK.md merged | `RESET_RULES` complete |
| `PROJECT_GUARD` | `project_guard` script written and passing locally | `MINIMAL_OS` complete |
| `BRANCH_PROTECTION` | GitHub branch protection enabled | `PROJECT_GUARD` stable for ≥1 PR cycle |
| `PHASE3_FIX_REVIEW` | Owner reviews propose/output-contract root cause | `BRANCH_PROTECTION` complete |
| `PAID_CREDIT_RERUN` | One paid-credit run with Owner approval | `PHASE3_FIX_REVIEW` approved |
| `APPLY_EVALUATE` | Apply + evaluate mutation pipeline | Valid patch from `PAID_CREDIT_RERUN` |
| `RELEASE_V0_3` | Tag v0.3, update README | `APPLY_EVALUATE` produces stable genome |

**Current state as of this PR:** `RESET_RULES` → `MINIMAL_OS`

---

## 6. Merge Rules

| Risk class | Required to merge |
|---|---|
| S0 | Passing `pytest tests/ -x -q`; complete PR body |
| S1 | Passing `pytest tests/ -x -q`; complete PR body |
| S2 | Passing `pytest tests/ -x -q`; changed scripts/tests reviewed |
| S3 | Owner explicit approval; `project_guard` must exist and pass |
| S4 | Owner explicit approval; environment approval (separate issue or comment); `project_guard` must exist and pass |

"Complete PR body" means: purpose stated, risk class stated, changed files listed, verification commands and their output present.

---

## 7. Invariants (never change without Owner decision)

- `data/project_state.json` `promote_approved` remains `false` until a dedicated promotion PR is approved.
- `live_model_enabled` and `api_mode` in `data/project_state.json` are not changed by docs-only PRs.
- No paid-credit Gemini API calls are made by AI without Owner authorization in a separate S4 PR.
