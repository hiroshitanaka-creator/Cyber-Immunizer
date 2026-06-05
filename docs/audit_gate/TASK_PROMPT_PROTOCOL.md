<!--
AI_DOC_META
status: CANONICAL
scope: Mandatory task prompt construction rules for GPT Audit Gate / Task Prompt Engineer work.
use_for:
  - writing task prompts for Claude Code, Codex, or any implementation agent
  - defining allowed / reference-only / frozen / impact file boundaries
  - preventing scope drift, vague instructions, and opportunistic refactors
do_not_use_for:
  - PR audit field verification
  - CI classification
  - Codex inline thread handling
related:
  - docs/AI_ENTRYPOINT.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - docs/audit_gate/PULLBACK_PROMPT.md
last_reviewed: 2026-06-04
AI_DOC_META_END
-->
# Task Prompt Protocol — Cyber-Immunizer

This protocol is the repository-level commitment for every task prompt produced by GPT Audit Gate / Task Prompt Engineer.

Before writing any task prompt, GPT must apply this file as a mandatory construction rule. A task prompt that violates this protocol is invalid, even if the requested code change is small.

---

## Non-negotiable commitment

GPT must not produce vague, scope-leaking, or under-specified task prompts.

Every implementation task prompt must:

1. State the task purpose in one complete sentence.
2. Define the current context and the exact goal.
3. Separate editable files, reference-only files, frozen files, and impact files.
4. Explain why every ALLOWED file may be edited.
5. Use broad FROZEN globs when in doubt.
6. Fill every Change Request field, even for a one-line change.
7. Explain what is wrong with the current behavior in WHY.
8. Preserve invariants explicitly.
9. Move opportunistic cleanup, refactors, or nice-to-have improvements into DO_NOT.
10. Stop instead of guessing when ambiguity, contradiction, or scope expansion appears.

---

## Task Prompt Gate v2 — mandatory pre-prompt investigation

GPT must not output an implementation task prompt until it has completed the following gate.
A task prompt is invalid if this gate is omitted, incomplete, or self-scored below 98/100.

### Pre-Prompt Investigation Gate

Before writing any implementation prompt, GPT must verify and summarize:

1. `main` / PR / branch / head SHA / merge-base SHA.
2. The canonical source of truth for the target behavior.
3. The current implementation, not only the diff.
4. Downstream consumers and runtime/evaluation effects.
5. Existing tests and missing tests.
6. README / docs / changelog / generator / data-history implications.
7. Likely Codex Review findings and how the prompt prevents them.
8. Scope-in, scope-out, and Project Owner-overridable items.

### Adversarial validation matrix

For validator, schema, policy, parser, prompt, generated-code, API, workflow, or security-boundary tasks, GPT must include a task-specific adversarial matrix.

At minimum, include applicable cases from:

- valid direct case
- missing required field
- extra field
- wrong field name
- duplicate field name
- positional args
- mixed positional + keyword
- `*args` / `**kwargs`
- return context
- non-return expression context
- assignment context
- nested branch context
- parse succeeds but compile/runtime fails
- stale metadata / generated docs mismatch
- scope-out but Project Owner-overridable item

### Self-score threshold

GPT must self-score the task prompt before output.

Passing threshold: **98/100**.

Rubric:

| Area | Points |
|---|---:|
| Primary-source verification | 15 |
| Scope boundary clarity | 15 |
| Adversarial matrix coverage | 20 |
| Existing implementation and downstream understanding | 15 |
| README / docs / changelog / history gate | 10 |
| ALLOWED / REFERENCE_ONLY / FROZEN / IMPACT precision | 10 |
| Codex Review issue pre-emption | 10 |
| Executability and minimality | 5 |
| Total | 100 |

If score is below 98, GPT must not output the task prompt. It must instead report:

```markdown
Self-score: <score>/100 — output prohibited
Missing evidence:
- ...
Unresolved risk:
- ...
Required next investigation:
- ...
```

### Codex Review is not the auditor

Codex Review is a supplemental signal, not the audit authority.

If Codex finds a valid PR-scope issue that GPT should have caught through this gate, treat it as a GPT pre-prompt design failure unless:

- the issue depends on information unavailable before implementation,
- the issue is explicitly out of scope,
- or the Project Owner intentionally accepted the risk beforehand.

---

## Required task prompt template

Use the following template for every task prompt.

```markdown
# Task: <一文で完結する目的>

## Context
- リポジトリ: <repo名>
- 現状: <今どうなっているか。前提知識を2-3行>
- このタスクのゴール: <完了の定義を1行>

## Scope (これだけやる)
- [ ] <具体的アクション1>
- [ ] <具体的アクション2>

## Files
### ALLOWED (編集可)
- path/to/a.py  — <なぜ編集が必要かを1行で書く>
- path/to/b.py  — <なぜ編集が必要かを1行で書く>

### REFERENCE_ONLY (読んでよいが編集禁止)
- path/to/config.yaml
- path/to/interface.py

### FROZEN (絶対に触るな・読む必要もない)
- migrations/**
- path/to/legacy/**

### IMPACT (影響が波及しうる。変更時は要確認)
- path/to/caller.py  ← b.py のシグネチャ変更が伝播する
- なし（<波及が無いと判断した具体的理由>）

## Constraints
- 新規ファイル作成: 禁止 / ALLOWED内のみ可 <どちらか明記>
- 依存追加: 禁止（必要なら停止して確認）
- 公開APIのシグネチャ変更: 禁止
- スコープ外を触りたくなったら → 実行せず理由を報告して停止

## Definition of Done
- <検証コマンド1>  例: pytest tests/test_b.py
- <検証コマンド2>  例: ruff check path/to/
- 全て green であること

## On Ambiguity
不明点・前提の矛盾・スコープ外への波及を見つけたら、
**推測で進めず、選択肢を提示して停止する。**

## Change Request
- WHAT: <変更する1行/箇所。before→after を明示>
- WHY: <なぜ変えるか。元の挙動の何が問題か>
- INVARIANT: <変えてはいけない振る舞い。これは維持しろ>
- DO_NOT: <この修正のついでに触りがちだが触るな、という範囲>
- VERIFY: <この変更が正しいと確認できるコマンド/観測>

## Pre-Prompt Investigation Gate
- main / PR / head SHA:
- Canonical source of truth:
- Current implementation: → See Source Evidence block below (assertion alone is invalid)
- Downstream effects:
- Existing tests:
- Missing/adversarial tests:
- README / docs / changelog / history impact:
- Likely Codex findings pre-empted:
- Scope-out / PO-overridable items:

## Source Evidence (必須 — assertion禁止)
<!--
ALLOWED ファイルのうち、変更ロジックに関係する箇所を1件以上、以下の形式で貼ること。
「確認済み」「reviewed」「checked」などの assertion だけを書いた場合はこのプロンプトは無効。
-->

### <file_path>:<start_line>-<end_line>
```
<ここに実際のコードをそのまま貼る>
```
根拠: <この引用がなぜこのタスクに関係するか1行>

## Self Score
- Score: ___ / 100
- Pass threshold: 98
- If below 98: do not output this prompt.
```

---

## Mandatory construction rules

1. `IMPACT` must never be blank. If there is no impact, write `なし（理由）` and explain why.
2. Every file listed under `ALLOWED` must include a one-line reason explaining why editing is necessary.
3. `FROZEN` must use broad globs. When unsure, freeze the path instead of allowing it.
4. The five `Change Request` fields are mandatory even for one-line changes: `WHAT`, `WHY`, `INVARIANT`, `DO_NOT`, and `VERIFY`.
5. `WHY` must describe what is wrong with the current code or current documentation. `変えたいから` or equivalent preference-only wording is forbidden.
6. Do not mix opportunistic improvements, refactors, wording cleanup, or adjacent fixes into the task. Put them in `DO_NOT` unless they are required for the stated goal.
7. The `Source Evidence` block is mandatory in every task prompt. For each ALLOWED file that affects the change logic, paste at least one verbatim code excerpt with a `file_path:start_line-end_line` header.
8. Assertion-only evidence is invalid. Writing `「確認済み」`, `「reviewed」`, `「checked」`, or similar claims without accompanying verbatim code excerpts does not satisfy the Source Evidence requirement. The task prompt is invalid if Source Evidence is missing or assertion-only.

---

## PR completion documentation gate

When a task prompt is for completing any PR, its `Definition of Done` or explicit scope must include a documentation / history verification gate.

The gate must check all of the following before the PR is considered complete:

1. `README.md` update needed? If not, state the reason.
2. `docs/**` update needed? If not, state the reason.
3. `docs/audit_gate/CHANGELOG.md` or another changelog/history file update needed? If not, state the reason.
4. Generator script consistency needed? If `README.md` or another generated section is affected, identify the generator path and whether it must be updated.
5. `data/evolution_history.json`, `data/api_usage_ledger.json`, or another history / ledger file update needed? If not, state the reason.

A PR completion task prompt that omits this gate is invalid.

---

## Failure rule

If GPT cannot fill this protocol without guessing, it must not produce an implementation prompt. It must instead report:

- the missing information,
- the conflicting assumption,
- the smallest set of options for Project Owner decision,
- and the files or evidence required to continue.
