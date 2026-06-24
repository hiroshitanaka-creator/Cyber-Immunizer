<!--
AI_DOC_META
status: TASK_REPORT
scope: Task completion report — proposer canonical regression-signature hardening + run #78 SSOT reconciliation.
last_reviewed: 2026-06-24
AI_DOC_META_END
-->
# タスク完了報告 — proposer 正典シグネチャ強化 ＋ run #78 SSOT 整合

## 概要
Evolution Loop run #78 で structured 候補が adoption gate により唯一の理由
`regression_pass_rate=0.750 < 1.000`（既知攻撃1件取りこぼし）で不合格となった。
proposer プロンプトに「正典的な必須シグネチャ」（破壊的/stacked SQLi・コア path-traversal）を
明示し、生成ルールセットが regression を100%カバーできるようにした。あわせて run #78 で
ledger が 21→22 に増えたのに SSOT が 21 のままで red だった drift を整合した。

## Layer 宣言
- [x] **Layer 3 — AI Operation Control**（自律ループが既知攻撃を確実に検出できるよう proposer の
  生成品質を是正。安全境界・予算・スキーマは不変）
- 付随作業（run #78 SSOT 整合）は Current-State SSOT 更新（ドキュメント規律の許可範囲）

## 変更ファイル一覧
- `scripts/propose_mutation.py` — `_build_structured_rules_prompt` のプロンプト文字列のみ強化
- `tests/test_structured_rules_live.py` — 正典シグネチャ必須化のアサーション追加（新規テスト1件）
- `data/project_state.json` — success 記録 21→22、note に run #78 追記
- `docs/PROJECT_STATE.md` — count 21→22（全箇所）、run #78 行追加
- `tests/test_project_state_sync.py` — `_EXPECTED…SUCCESS_RECORDS` 21→22

## 主な変更内容
### 1. proposer プロンプト強化（commit 042c5de）
- SQLi カテゴリに破壊的/stacked 文を追記: `drop table`, `delete from`, `insert into`,
  `update set`, 文区切り `'; `（従来は read 系 `union select`/`or 1=1`/コメントのみ）。
- path-traversal に `/etc/shadow` を `/etc/passwd` と並記。
- 「MANDATORY canonical coverage」指示を追加: `../` ＋ 機微システムファイル、SQLi は
  read 系 AND 破壊系の両方を必ず含めること（単一 SQLi シグネチャに依存しない）。
- compact/minified・bound（24-40・max 64）・precision 指示は不変。
- **コーパス実ケースはプロンプトに埋め込まない（overfitting 回避）**。一般に既知の canonical 語のみ。

### 2. run #78 SSOT 整合（commit 2d6ce67）
- #78 は PR #183 マージ後の main で実行 → **compact 修正が live で実証**（propose 成功・
  truncation なし・`code_chars=6253` > 5596）。候補は gate で regression floor のみ不合格。
- promote は skipped（`promote_approved` 未指定＝安全）。breaker 1/3。promotion なし＝generation 4 baseline 不変。

## 後検証結果
- `pytest tests/test_structured_rules_live.py -q` → 18 passed
- `pytest tests/ -x -q` → **3077 passed**
- `python scripts/validate_state.py` → **PASS**
- プロンプト内容確認:
  `python -c "import scripts.propose_mutation as pm; p=pm._build_structured_rules_prompt({}).lower(); print('drop table' in p, '../' in p, '/etc/shadow' in p, 'mandatory' in p)"`
  → `True True True True`
- ledger 実数 22 == project_state declared 22 == test EXPECTED 22

## ドキュメント/履歴ゲート
1. `README.md` 更新: 不要（ユーザー向け挙動・コマンドの変更なし）
2. `docs/**` 更新: PROJECT_STATE.md を current-state 整合のため更新済み
3. `docs/audit_gate/CHANGELOG.md`: 不要（運用教訓の新規分類ではなくプロンプト品質改善）
4. generator 整合: 該当なし
5. `data/**`（ledger/history）更新: ledger は #78 が自動追記済み。project_state.json を整合済み。
   genome/budget/circuit_breaker のロジック値は不変

## 残存事項・注意点
- 本 PR は **proposer の生成品質を是正するのみ**。実証は次回 paid ignition が必要
  （Owner 判断。`promote_approved=false` 推奨で regression_pass_rate=1.0 到達を確認）。
- 取りこぼしが r-3（sqli `drop table`）か r-1（path-traversal）か機械的に100%確定できないため、
  両カテゴリを強化して吸収する設計とした。
- paid/model/budget 設定は一切変更していない（`max_output_tokens=2048` 据え置き、daily 0.25 不変）。
- `CLAUDE.md` の要約表（success 件数）は派生サマリのため未変更（正典は project_state.json / PROJECT_STATE.md）。
