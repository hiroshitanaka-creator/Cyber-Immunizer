<!--
AI_DOC_META
status: PLANNING
scope: L3-A4 (Future automation path) proposal — a lightweight post-task classifier for docs-only / task-layer classification. Proposal only; not implemented.
use_for:
  - satisfying DEFINITION_OF_DONE.md L3-A4 ("proposed or implemented") at the "proposed" level
  - designing a future Skill / Codex / CI post-task classifier before any code is written
do_not_use_for:
  - claiming the classifier is implemented (it is not)
  - editing .claude/** / .codex/** / .github/** / scripts/** / tests/** without separate Owner approval
  - adding a heavy new protocol or ceremony (DEFINITION_OF_DONE.md:160 forbids this)
related:
  - docs/DEFINITION_OF_DONE.md
  - CLAUDE.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - docs/COMPLETION_TASKLIST.md
AI_DOC_META_END
-->

# L3-A4 — Post-task Docs-only / Layer Classifier (Proposal)

## What this document is

`docs/DEFINITION_OF_DONE.md:131` defines **L3-A4**:

> | L3-A4 | Future automation path | A Skill / Custom GPT / Codex post-task classifier is **proposed or implemented**. |

`docs/DEFINITION_OF_DONE.md:133`: *"Layer 3 is complete when L3-A1 through L3-A3 hold and L3-A4 has been **at minimum proposed**."*

**This document is that proposal.** It proposes a lightweight, owner-invoked post-task classifier.
It does **not** implement it. Implementation touches FROZEN paths
(`.claude/**`, `.codex/**`, `.github/**`, `scripts/**`, `tests/**`) and is a separate, Owner-approved task.

> ⚠️ Per `docs/DEFINITION_OF_DONE.md:160`: **"Do not make this a large new protocol. It is a checklist, not a ceremony."**
> This proposal deliberately stays minimal and adds **no** new protocol layer.

## What the classifier decides (no new rules — reuse the canonical ones)

The classifier does not invent criteria. It mechanically applies the existing rules in
`docs/DEFINITION_OF_DONE.md`:

1. **Task layer** — one of `Layer 1 / Layer 2 / Layer 3 / None` (DoD:137-147).
2. **If docs-only**, the allowed category — one of the six (DoD:96-108):
   Owner Intent / Claim Record · Safety Boundary · Current-State SSOT · Audit Evidence ·
   User-facing Manual (for an existing executable feature) · Minimal Task Report.
3. **Disallowed / redundant flag** — raised when the change matches a suspect pattern (DoD:110-117):
   broad roadmap/DoD expansion, a new protocol layer with no defensive value, duplicate explanation,
   over-long task report, or "looks complete" docs with no executable/validated link.

Output is a 3-line verdict: `layer=…`, `docs_category=… (or n/a)`, `flag=ok|review:<reason>`.
It classifies and flags only — it never edits code, data, genome, ledger, or PR state.

## Proposed mechanism (lightweight, owner-gated implementation)

### (Primary) Claude Code Skill `cyber-docs-classifier`
A manual-invocation skill under `.claude/skills/`, following the existing
`.claude/skills/cyber-repair-review-loop/SKILL.md` convention
(`disable-model-invocation: true`, Owner-invoked, read-only, no merge/approve/resolve).

- **Input**: the PR's changed file list + the task report (`docs/task_reports/TASK_REPORT_*.md`).
- **Output**: the 3-line verdict above, with a one-line rationale citing the DoD category.
- **Boundaries**: read-only; produces text only; does not run paid-credit / `workflow_dispatch` /
  promotion / ledger / genome / detector changes (same forbidden-ops posture as the existing skill).

### (Complementary) Minimal CI / test check
A small `scripts/` helper + one `tests/` case that assert, per PR:
- the task report contains a valid **Layer declaration line** (one of the four), and
- a docs-only PR names **exactly one** allowed docs category.

This is a presence/format check (a checklist), not a semantic judge — it cannot, by itself,
decide "redundant"; that judgement stays with the Skill/Codex/Owner.

### (Optional) Codex post-task check
The same verdict surfaced as a Codex Review comment, co-located with the existing Codex Review
practice referenced in `docs/audit_gate/PR_AUDIT_PROTOCOL.md`. No new protocol; it reuses the
PR-audit docs/classification gate (`PR_AUDIT_PROTOCOL.md` "PR completion documentation / history gate").

## Non-goals

- No automatic merge, approval, or review-thread resolution.
- No new protocol document, checklist ceremony, or required manual doc-writing step.
- No change to the canonical classification rules — `docs/DEFINITION_OF_DONE.md` remains the source.

## Relationship to Layer 3 completion

With this proposal, **L3-A4 is satisfied at the "proposed" level**. L3-A1 (CLAUDE.md value/docs
discipline), L3-A2 (task layer declaration, used across `docs/task_reports/`), and L3-A3 (PR-audit
docs classification gate in `PR_AUDIT_PROTOCOL.md`) were already established. Whether Layer 3 is
therefore **complete** (DoD:133) is for the Project Owner / audit to confirm; this document does not
assert that in the current-state SSOT.

## Implementation status

**Proposed only.** Building the Skill / CI check / Codex check is future, Owner-approved work
(it edits FROZEN `.claude/**`, `.github/**`, `scripts/**`, `tests/**`).
