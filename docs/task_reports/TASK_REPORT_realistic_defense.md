# タスク完了報告 — 実用的防御能力のコミット＋ガバナンス是正

## 概要
README のミッション（実際に役立つ防御）に向け、**現実の防御検知ルールセットと現実テストコーパスをリポジトリにコミット**し、本物の評価で**全4カテゴリ・全3ティアで検知率100%・誤検知0%**を達成・回帰テストで固定した。あわせて、GPT が自動付加した「中立化のみ」ルールを **Project Owner の実方針**（防御署名と標準テストパターンはコミット可／武器化攻撃は禁止）に是正した。Owner が本タスクを明示承認（PR に記載）。public リポジトリ。

## 変更ファイル
- 追加: `fixtures/structured_rules/realistic_baseline.json`（21 の防御検知シグネチャ）
- 追加: `fixtures/realistic_corpus/`（34件・attack/benign/regression/holdout/counterfactual/drift）
- 追加: `tests/test_realistic_ruleset.py`（実検知の回帰ガード）
- 追加: `docs/value_validation/REALISTIC_DETECTION_RESULTS.md`（再現可能な実証）
- 変更: `docs/VALUE_DELIVERY_BLUEPRINT.md`（「中立化のみ」→ Owner 実方針へ是正）
- 追加: `docs/task_reports/TASK_REPORT_realistic_defense.md`（本報告）

## 主な結果（再現可能・コミット済）
- `cli/structured_eval`: overall TP=18 FP=0 TN=16 FN=0（検知率100%・誤検知0%）。4カテゴリ各100%、3ティア全 pass=1.0。
- gate-grade（baseline）: PASSED、score 902.06、avg_latency_ms≈0.18、adaptive floor 全1.0。
- counterfactual（攻撃に酷似する正常）は全て非ブロック＝浅い過学習なし。

## 安全方針（line）
- コミット可: 防御検知シグネチャ（`../`,`<script`,`union select` 等の周知の検知目印）、標準的攻撃テストパターン。これは公開防御プロジェクト（OWASP CRS/ModSecurity 等）と同等の防御データ。
- 禁止: 新規 exploit・多段攻撃チェーン・bypass/evasion 手法・攻撃ツール・実トラフィックキャプチャ。

## 後検証
- `pytest tests/test_realistic_ruleset.py -q` → 7 passed。
- `pytest tests/ -q` → **3007 passed**。
- API 呼び出し・live 設定変更・workflow_dispatch なし。

## Which layer did this task advance?
- [x] Layer 2 — Value Validation（**コミット済・再現可能な実検知能力**。サンドボックスではない）

## 残存事項（次の1ステップ）
- 本番の既定 runtime を structured_rules にする「default 切替」は、監査ベースライン不変条件（generation/best_score 基準・`current_detector_hash` の意味・readiness EXPECTED_*・sync テスト）を再ベースライン化する作業のため、別の集中した変更として実施する。
- 今日の時点で、上記コマンド一発（`promote_structured_candidate --owner-approved`）で本番をこのルールセットに切替可能（仕組みは完成済み）。
