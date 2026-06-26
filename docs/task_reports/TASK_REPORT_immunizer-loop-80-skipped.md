# タスク完了報告 — 完成に向けた実行タスクリスト作成

branch: `claude/immunizer-loop-80-skipped-25i9h5`

## 概要
Project Owner の依頼「このリポジトリを完成に向けて進める為のタスクリストを作成」に対し、
全ミッション M1〜M5 と Layer 1/2/3 完成条件を、実ファイル・スクリプト・DoD条件に紐づけた
実行タスク分解 `docs/COMPLETION_TASKLIST.md` を新規作成した。既存ロードマップの重複ではなく、
従属する execution checklist として位置づけた。

## 変更ファイル一覧
- 追加: `docs/COMPLETION_TASKLIST.md`
- 追加: `docs/task_reports/TASK_REPORT_immunizer-loop-80-skipped.md`（本ファイル）
- 変更なし: `core/**` `scripts/**` `.github/**` `data/**` `tests/**`（FROZEN 無編集）

## 主な変更内容
- M0（DONE）〜M5、横断タスク（Layer 2/Layer 3/衛生）、Owner ゲート一覧を表形式で分解。
- 各タスクに ID / 紐づく DoD / Owner-gate・FROZEN フラグ / 主担当ファイル / Done-when を付与。
- AI_DOC_META ブロックを付与し、従属関係（MISSION_ROADMAP.md・DEFINITION_OF_DONE.md・current-state SSOT）を明記。
- 調査で判明した docs/code 不整合を M1-T0 としてタスク化（下記「残存事項」参照）。

## 後検証結果
- スコープ: `git diff --name-only` で FROZEN 配下の変更なしを確認（追加は docs/ のみ）。
- AI_DOC_META: 新規 docs に存在。
- 引用照合（実ファイルと一致を確認）:
  - `scripts/propose_mutation.py:2111-2154` — `--structured-rules --gemini-paid-credit` 実装済み（`propose_structured_rules`）。
  - `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md:30-43` — 「未実装」記述（コードと矛盾）。
  - `docs/DEFINITION_OF_DONE.md:64-70`（外部化禁止リスト）/ `:80-87`（L2-V1〜V5）。
  - `docs/MISSION_ROADMAP.md:107-113`（Owner ゲート表）。
  - `data/project_state.json`（state_id / next_action / promotion / layer_2_value_validation / live_model_enabled）。
  - `data/genome.json`（detector_mode=structured_rules / generation 4）。
- README 更新: 不要（ステータスブロックに影響しない実行 checklist の追加のため）。

## テスト結果
- 実行: `pip install -e ".[dev]" -q && python -m pytest tests/ -x -q`
- 結果: `tests/test_active_detector.py::test_default_genome_is_legacy_and_matches_inspect_request` で **1 failed**。
- **重要**: この失敗は本タスクの変更（docs 1ファイル追加、未追跡）とは無関係。`git stash -u` で
  作業ツリーをクリーン HEAD に戻しても同一の失敗が再現することを確認済み（HEAD 既存の不整合）。
  原因は run #80 の structured promotion で `data/genome.json` の `detector_mode` が `structured_rules`
  になっている一方、当該テストは「default genome は legacy」と assert しているため。
  `data/**`・`tests/**` は FROZEN のため本タスクでは修正せず、Owner へ報告のみ行う。

## 残存事項・注意点
1. **[要 Owner 判断] HEAD 既存のテスト不整合**: `test_default_genome_is_legacy_and_matches_inspect_request`
   が main HEAD で失敗している。run #80 の structured promotion 後の genome 状態とテスト前提のズレ。
   `data/**`/`tests/**` の修正は別タスク・Owner 承認が必要。
2. **[M1-T0] docs/code 不整合**: live structured proposal は実装済み（`propose_mutation.py:2111-2154`）だが
   `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md:30-43` は未実装と記述。SSOT 整合の解消が必要（本書 M1-T0）。
3. 本タスクは docs-only。実行（M1〜M5 の着手・paid-credit run）は行っていない。

## Which layer did this task advance?
- [x] None（docs-only）
- docs 分類: **Owner Intent / Claim Record**（Owner の明示依頼による実行計画の記録）
- Layer 2（価値検証）進捗にはカウントしない。
