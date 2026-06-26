# タスク完了報告 — L3-A4: docs-only タスク分類の Skill/Codex 自動化「提案」

branch: `claude/immunizer-loop-80-skipped-25i9h5` / PR #186

## 概要
`docs/DEFINITION_OF_DONE.md:131` の L3-A4（Future automation path）は「Skill / Custom GPT / Codex post-task classifier を **proposed または implemented**」で、提案だけで条件を満たす。本タスクで軽量な post-task 分類器の提案文書を作成し、L3-A4 を "proposed" として満たした。

## 変更ファイル一覧
- 追加: `docs/audit_gate/L3A4_POSTASK_CLASSIFIER_PROPOSAL.md`（AI_DOC_META status: PLANNING）
- 更新: `docs/COMPLETION_TASKLIST.md`（X-L3 行「提案段階」→「提案済み」＋リンク）
- 追加: `docs/task_reports/TASK_REPORT_L3A4_classifier_proposal.md`（本ファイル）
- 無変更: `.claude/** .codex/** .github/** scripts/** tests/** data/**`

## 主な変更内容
- 提案の中身（軽量・新プロトコル化しない）:
  - 分類対象は既存正典（DoD:96-117, 137-161）を再利用。Layer 判定＋docs-only 許可6カテゴリ＋disallowed/redundant フラグ。
  - 主機構: Claude Code Skill `cyber-docs-classifier`（`.claude/skills/`、`disable-model-invocation: true`、owner 手動起動、read-only、merge/approve/resolve しない）。既存 `cyber-repair-review-loop` の慣習に整合。
  - 補完: 各 task report の Layer 宣言行の存在と docs-only PR の許可カテゴリ名を検証する最小 CI/テスト check。
  - 任意: 同分類を Codex Review コメントで提示（既存 PR_AUDIT_PROTOCOL の docs gate に同居）。
  - 実装は FROZEN パス（`.claude/** .github/** scripts/** tests/**`）に触れるため別タスク・Owner 承認が前提。本書は提案のみ。
- DoD:160「大きな新プロトコルにするな。儀式ではなくチェックリスト」を明示遵守。

## 後検証結果
- `pytest tests/ -q` → 全 pass（下記テスト結果）。新規 docs 追加・X-L3 行更新は既存テストを壊さない。
- 引用照合: DoD:131/133/96-117/137-161、CLAUDE.md 価値・docs 規律、PR_AUDIT_PROTOCOL docs gate を実ファイルと整合確認。
- `git diff --name-only` は `docs/` 配下のみ。

## テスト結果
- 実行: `python -m pytest tests/ -q`
- 結果: **3077 passed**（docs-only のため挙動変更なし）。

## 残存事項・注意点
- 本提案は L3-A4 を "proposed" として満たす。L3-A1〜A3 は既存（CLAUDE.md 規律・task report の Layer 宣言・PR audit gate）。
  したがって Layer 3 の完成条件（DoD:133）が満たされる**見込み**だが、「Layer 3 complete」の SSOT 断定は本タスクでは行わず、Owner/audit の確認に委ねる。
- 提案機構の実装（Skill/CI/Codex check）は FROZEN パス編集を伴う別タスク・Owner 承認事項。

## Which layer did this task advance?
- [x] Layer 3 — AI Operation Control（L3-A4 を proposed として満たす）
- [ ] Layer 1 / [ ] Layer 2 / [ ] None

docs-only 分類:
- [x] Audit Evidence / Owner Intent（L3-A4 が要求する automation path の提案記録。証拠引用付き）
