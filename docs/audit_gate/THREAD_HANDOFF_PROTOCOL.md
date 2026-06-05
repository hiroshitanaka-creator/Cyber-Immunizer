<!--
AI_DOC_META
status: CANONICAL
scope: Mandatory thread handoff prompt construction rules for continuing Cyber-Immunizer work in a new session/thread.
use_for:
  - writing a handoff prompt when a thread is ending or context is about to be lost
  - capturing verifiable state (branch, head SHA, PR, constraints) for the next session
  - preventing context-loss errors when work continues in a fresh thread
do_not_use_for:
  - PR audit field verification (see PR_AUDIT_PROTOCOL.md)
  - implementation task prompt construction (see TASK_PROMPT_PROTOCOL.md)
  - GPT drift recovery (see PULLBACK_PROMPT.md)
related:
  - docs/AI_ENTRYPOINT.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - CLAUDE.md
last_reviewed: 2026-06-05
AI_DOC_META_END
-->
# Thread Handoff Protocol — Cyber-Immunizer

When a thread is ending, running low on context, or work must continue in a new
session, the **outgoing** session must produce a handoff prompt using this protocol.
The **incoming** session must verify that handoff before acting on it.

A handoff prompt that omits any mandatory field, or that states facts the incoming
session cannot verify against the repository, is invalid.

---

## Why this protocol exists

Context-loss between threads is a recurring failure mode. A new session that trusts
an unverified handoff can:

- act on a stale head SHA and overwrite newer work,
- re-implement something already done,
- violate a constraint the previous session was operating under,
- claim something is complete when it was only described as planned.

This protocol forces the handoff to carry **verifiable state**, not narrative.

---

## Core rule — Verifiable state, not narrative

Every fact in a handoff prompt must be either:

1. **Verifiable** against the repository (branch, head SHA, PR number, file path,
   test count, CI run id), or
2. **Explicitly labeled** as an assumption, plan, or unverified claim.

Narrative summaries ("we fixed the spec, then improved the runbook") are allowed
only as supporting context, never as the source of truth. The incoming session
verifies state from the repository first, and treats the narrative as a hint.

---

## Mandatory handoff prompt template

```markdown
# Thread Handoff — Cyber-Immunizer

## 1. Verifiable state (incoming session must re-verify all of these)
- repo: hiroshitanaka-creator/Cyber-Immunizer
- branch:
- head SHA:               ← 必須・verbatim。incoming session が git log で照合する
- PR number / state:      ← open / closed / merged / なし
- CI status for head SHA: ← SUCCESS / FAILED / NOT TRIGGERED / 未確認
- test status:            ← 例: pytest tests/ -x -q → 1756 passed（実行して確認した値）

## 2. Current task in one sentence
<今やっている1タスク。複数あるなら最優先の1つ>

## 3. Done (verifiable — each item cites a commit or file)
- [x] <完了した変更> — commit <sha> / <file_path>
- [x] ...

## 4. Not done / next step
- [ ] <次にやるべき具体的アクション1>
- [ ] <次にやるべき具体的アクション2>

## 5. Hard constraints still in effect (絶対遵守)
- <このスレッドで守っていた禁止事項を全て列挙>
- 例: scripts/** core/** .github/** data/** を編集しない
- 例: PR を APPROVE / マージしない
- 例: Gemini API / paid-credit を実行しない

## 6. Assumptions / unverified (incoming session must confirm before relying)
- <未確認のまま引き継ぐ事項。なければ「なし」と書く>

## 7. Where to read next
- CLAUDE.md
- docs/AI_ENTRYPOINT.md
- <このタスク固有のファイル: 例 docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md>
```

---

## Mandatory construction rules (outgoing session)

1. `head SHA` must be stated verbatim. A handoff without a head SHA is invalid.
2. Every `Done` item must cite a commit SHA or a file path. Assertion-only
   ("specを直した") without a commit/file reference is invalid.
3. `Hard constraints still in effect` must never be blank. If the previous
   session operated under any scope/action restriction, list all of them.
4. `Assumptions / unverified` must never be blank. If there are none, write
   `なし`. Do not silently omit it.
5. Do not state a task is complete unless it is committed. "完了" means a commit
   exists; a described-but-uncommitted change is `Not done`, not `Done`.

---

## Mandatory intake rules (incoming session)

Before acting on a handoff prompt, the incoming session must:

1. Verify `branch` and `head SHA` against the repository (`git log`, `git branch
   --show-current`). If the actual head SHA differs from the handoff, **stop** and
   report the discrepancy before doing any work.
2. Re-run the stated test command and confirm the test status matches. If it does
   not match, report the mismatch.
3. Re-read `Hard constraints still in effect` and treat them as binding for this
   session unless the Project Owner explicitly lifts them.
4. Treat every item in `Assumptions / unverified` as unconfirmed until checked.
5. Trust the repository over the handoff narrative. If the handoff contradicts the
   actual diff/state, trust the repository and report the contradiction.

---

## Failure rule

If the outgoing session cannot fill the mandatory fields without guessing — for
example it does not know the current head SHA — it must say so explicitly in the
handoff rather than inventing a value. An honest "head SHA: 未確認（git log で要確認）"
is valid; a fabricated SHA is a protocol violation.
