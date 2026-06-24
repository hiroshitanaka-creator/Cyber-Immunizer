<!--
AI_DOC_META
status: TASK_REPORT
scope: Task completion report — proposer canonical regression-signature hardening (proposer-only; run #78 SSOT reconciliation split to PR #185).
last_reviewed: 2026-06-24
AI_DOC_META_END
-->
# タスク完了報告 — proposer 正典シグネチャ強化

## 概要
Evolution Loop run #78 で structured 候補が adoption gate により唯一の理由
`regression_pass_rate=0.750 < 1.000`（既知攻撃1件取りこぼし）で不合格となった。
proposer プロンプトに「正典的な必須シグネチャ」（破壊的/stacked SQLi・コア path-traversal）を
明示し、生成ルールセットが regression を100%カバーできるようにした。

> **スコープ分離**: 当初この PR には run #78 の SSOT 整合（ledger 21→22）も含めていたが、
> Codex PR #184 #3（AGENTS.md「実装 fix と SSOT 整合を混ぜるな」）に従い、SSOT 整合は
> **PR #185 に分離**し、本 PR では `git revert` で打ち消した。本 PR の net 差分は proposer のみ。

## Layer 宣言
- [x] **Layer 3 — AI Operation Control**（自律ループが既知攻撃を確実に検出できるよう proposer の
  生成品質を是正。安全境界・予算・スキーマは不変）

## 変更ファイル一覧（net 差分）
- `scripts/propose_mutation.py` — `_build_structured_rules_prompt` のプロンプト文字列のみ強化
- `tests/test_structured_rules_live.py` — 正典シグネチャ必須化のアサーション追加（新規テスト1件）
- `docs/task_reports/TASK_REPORT_proposer_regression_coverage.md` — 本報告

## 主な変更内容（commit 042c5de）
- SQLi カテゴリに破壊的/stacked 文を追記: `drop table`, `delete from`, `insert into`,
  `update set`, 文区切り `'; `（従来は read 系 `union select`/`or 1=1`/コメントのみ）。
- path-traversal に `/etc/shadow` を `/etc/passwd` と並記。
- 「MANDATORY canonical coverage」指示を追加: `../` ＋ 機微システムファイル、SQLi は
  read 系 AND 破壊系の両方を必ず含めること（単一 SQLi シグネチャに依存しない）。
- compact/minified・bound（24-40・max 64）・precision 指示は不変。
- **コーパス実ケースはプロンプトに埋め込まない（overfitting 回避）**。一般に既知の canonical 語のみ。

## 後検証結果
- `pytest tests/test_structured_rules_live.py -q` → 18 passed（新規アサーション含む）
- プロンプト内容確認:
  `python -c "import scripts.propose_mutation as pm; p=pm._build_structured_rules_prompt({}).lower(); print('drop table' in p, '../' in p, '/etc/shadow' in p, 'mandatory' in p)"`
  → `True True True True`

## マージ順序の注意（重要）
- 本 PR は SSOT 整合（PR #185）を含まないため、**本ブランチ単体では `main` の既存 red
  （run #78 で ledger=22 だが SSOT=21）を引き継ぎ `test_project_state_matches_ledger_success_count`
  が red**。
- 正しい順序: **PR #185 を先に main へマージ → main green 化 → 本 PR を main に同期（update branch）→ green → マージ**。
  PR #185 と本 PR の SSOT 行は 3-way merge で衝突しない（本 PR は SSOT を net で変更しないため）。

## ドキュメント/履歴ゲート
1. `README.md` 更新: 不要（ユーザー向け挙動・コマンドの変更なし）
2. `docs/**` 更新: 不要（current-state 正典は本 PR では変更しない。SSOT は PR #185）
3. `docs/audit_gate/CHANGELOG.md`: 不要（運用教訓の新規分類ではなくプロンプト品質改善）
4. generator 整合: 該当なし
5. `data/**`（ledger/history）更新: 本 PR では行わない（SSOT は PR #185）

## 残存事項・注意点
- 本 PR は **proposer の生成品質を是正するのみ**。実証は次回 paid ignition が必要
  （Owner 判断。`promote_approved=false` 推奨で regression_pass_rate=1.0 到達を確認）。
- 取りこぼしが r-3（sqli `drop table`）か r-1（path-traversal）か機械的に100%確定できないため、
  両カテゴリを強化して吸収する設計とした。
- paid/model/budget 設定は一切変更していない（`max_output_tokens=2048` 据え置き、daily 0.25 不変）。
