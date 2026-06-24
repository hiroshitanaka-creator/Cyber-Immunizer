<!--
AI_DOC_META
status: TASK_REPORT
scope: Run #78 SSOT reconciliation (ledger 21->22). Split out from proposer hardening per Codex PR #184 #3 / AGENTS.md scope rule.
last_reviewed: 2026-06-24
AI_DOC_META_END
-->
# タスク完了報告 — run #78 SSOT 整合（ledger 21→22）

## 概要
Evolution Loop run #78（id 28095623368）が main 上で paid call を1件実行し ledger が
21→22 になったが、SSOT（`data/project_state.json` / `docs/PROJECT_STATE.md` / sync テスト）が
21 のままで `test_project_state_matches_ledger_success_count` が **main で red** だった。
これを 22 に整合し green を復旧する。**proposer 強化（PR #184）とは分離**した独立変更
（Codex PR #184 #3 / AGENTS.md スコープ規則に準拠）。

## Layer 宣言
- [x] None（Current-State SSOT 更新のみ。ドキュメント規律の許可範囲）

## 変更ファイル一覧
- `data/project_state.json` — `gemini_3_flash_preview_success_records` 21→22、note 冒頭文を 22 に、
  note 末尾に run #78 のトリアージ追記（compact 修正 live 実証・gate 不合格 regression のみ・promote skip・breaker 1/3）
- `docs/PROJECT_STATE.md` — count 21→22（全箇所）、run #78 行追加
- `tests/test_project_state_sync.py` — `_EXPECTED…SUCCESS_RECORDS` 21→22

## run #78 の事実（機械的証拠）
- PR #183 マージ後の main で structured-gemini-paid-credit を実行
- **compact 修正を live 実証**: propose 成功・truncation なし（`schema_valid=true`, `code_chars=6253` > 5596）
- 候補は adoption gate で**唯一の理由** `regression_pass_rate=0.750 < 1.000` で不合格
  （`fp_rate=0.0` / holdout / drift / counterfactual はすべて 1.0）
- Promote Structured Rules は **skipped**（`promote_approved` 未指定）→ promotion なし＝generation 4 baseline 不変
- ledger +1 = 22、circuit breaker 1/3（未 trip）

## 後検証結果
- `pytest tests/ -x -q` → 全 green
- `python scripts/validate_state.py` → PASS
- ledger 実数 22 == project_state declared 22 == test EXPECTED 22
- note 内 count 整合: 冒頭 current-state 文 = 22（残る「+2 = 21」は #75/#76 時点の履歴記述で正確）

## 残存事項・注意点
- マージ順序: 本 PR を **先に** main へマージ → main green → proposer PR #184 を main 同期後に green 化。
- promotion・budget・model 設定は一切変更なし。
