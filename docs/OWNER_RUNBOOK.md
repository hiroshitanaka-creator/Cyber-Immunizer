# Owner Runbook — Cyber-Immunizer

**Version:** 0.1  
**Date:** 2026-06-10  
**Audience:** Project Owner (hiroshitanaka-creator)

Use this document when deciding whether to merge, hold, or reject a PR.

---

## 1. Five Questions Before Merging

Ask these five questions for every PR, in order. If any answer is missing or unsatisfying, HOLD.

| # | Question | What to check |
|---|---|---|
| 1 | **What is the risk class?** | PR body must state S0–S4. If missing, ask the AI to add it before merging. |
| 2 | **What files changed?** | Open the Files tab. Compare against the PR body's stated changed-files list. Any file not listed in the PR body is a discrepancy — hold until explained. |
| 3 | **Did the PR touch frozen paths?** | Frozen paths: `.github/**`, `core/**`, `scripts/**`, `tests/**`, `data/**`, `CLAUDE.md`. If a frozen path changed, verify the PR has explicit S2/S3/S4 authorization. |
| 4 | **What commands passed?** | The PR body must include at least one shell command and its verbatim output. "Tests passed" without output is not acceptable. |
| 5 | **Does this advance `project_state` or use API/promotion/release?** | If yes, this is S3 or S4. Verify you authorized this action explicitly, in this PR. A prior authorization does not carry over. |

---

## 2. Owner Merge Decision Rules

| Condition | Action |
|---|---|
| Any of the five questions above is unanswered | **HOLD** — ask the AI to update the PR body |
| Risk class S4 appears without a separately-planned Owner decision | **HOLD** — do not merge until you have explicitly decided to run S4 |
| AI uses unsupported claims ("I verified", "looks correct", "should be fine") without file+line+command+result evidence | **HOLD** — ask for machine evidence |
| Tests are missing for S2 or higher risk class | **HOLD** — require `pytest tests/ -x -q` output with zero failures |
| PR body is incomplete (purpose missing, changed files not listed, no verification output) | **HOLD** — require complete PR body |

**Default rule: if unsure, HOLD.** The cost of a delayed merge is lower than the cost of an incorrect merge to `main`.

---

## 3. AI-Output Screening

When reading AI-produced PR descriptions, audit reports, or completion reports, apply this screen.

### Valid evidence (accept)

- File path + line number + verbatim quoted content
- Shell command + verbatim stdout/stderr output
- CI status label (`SUCCESS` / `FAILED` / `NOT TRIGGERED`) with a link or log excerpt
- `git log` or `git show` output identifying a specific commit SHA

### Invalid evidence (reject — ask for valid form)

The following phrases are not evidence:

| Phrase | Why invalid |
|---|---|
| "I checked the file" | Does not show what was found |
| "I reviewed the changes" | Does not show what was verified |
| "Seems fine" / "looks correct" | Opinion, not observation |
| "Safe" / "no issue found" | Negative claim without search record |
| "Tests passed" (no output) | AI self-report is not machine evidence |
| "CI is green" (no link/log) | Cannot be verified without evidence |

If an AI report contains only invalid evidence, treat the entire finding as unverified.

---

## 4. Paid-Credit Rule

Paid-credit Gemini API calls are strictly controlled.

**Do not authorize a paid-credit rerun until ALL of the following are true:**

1. `project_guard` script exists in the repository and passes locally with zero errors.
2. GitHub branch protection is enabled on `main` (requires passing `project_guard` check).
3. The propose/output-contract root cause from Phase 3 has been reviewed and a fix is merged.
4. You have explicitly approved a dedicated S4 PR whose sole purpose is the paid-credit rerun.

**`promote_approved` remains `false`** in `data/project_state.json` until a separate promotion PR — describing exactly which mutation to promote and why — is approved by you.

Changing `promote_approved` to `true` is an S4 action. It requires a dedicated PR, your explicit approval comment, and passing `project_guard`.

---

## 5. Quick Reference — Risk Class Cheat Sheet

```
S0  cosmetic only          → merge with passing tests
S1  docs/protocol          → merge with passing tests
S2  scripts/tests/schemas  → merge with passing tests + review
S3  .github/data/state     → Owner approval + project_guard required
S4  API/secret/promote     → Owner approval + env approval + project_guard required
```
