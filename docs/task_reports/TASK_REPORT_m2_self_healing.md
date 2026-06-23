# タスク完了報告 — M2：自己修復（昇格後ヘルスチェック＋自動ロールバック）

## 概要
自律ループを「安全に回し続ける」ための M2 中核＝**自己修復**を実装した。構造化昇格の直後に、
**本番の active 検出器が runtime で実際に効いているか**を検証し、回帰（サイレントな legacy フォール
バック等）を検知したら**即座に `detector_mode=legacy` へ自動ロールバック**してコミットする。
scheduled は noop 据え置き（自動 paid 起動なし）。本タスクで API・live 実行・workflow_dispatch なし。

## 追加スクリプト
- `scripts/post_promote_healthcheck.py`（読取専用）
  - `core.active_detector.inspect_active`（runtime 入口）で、committed の active 検出器を
    `fixtures/realistic_corpus/all_cases.json` に対して実行。
  - 健全条件：`fp_rate <= genome.max_fp_rate` かつ `tp_rate >= --min-tp-rate`(既定0.5)。
  - `detector_mode!=structured_rules` なら skip(exit0)。回帰時 exit1。
  - **サイレント fallback 検知**：昇格を記録したのに active rules が読めず legacy に落ちると
    realistic 検知=0 → 不健全 → ロールバック誘発。
- `scripts/rollback_to_legacy_detector.py`
  - `detector_mode=legacy` に戻し `active_structured_rules_*` を除去（レガシー系統 generation/
    best_score/hash は不変＝即時・無損失）。idempotent。

## ワークフロー（structured-promote）
昇格コミット後に「Post-promote health check」ステップを追加：
- healthcheck 合格 → 構造化検出器を本番継続。
- 不合格 → `rollback_to_legacy_detector.py` 実行 → genome を legacy に戻して commit/push →
  ジョブを fail（production が自己修復）。

## 安全性
- healthcheck は読取専用・鍵なし。rollback は genome のみ変更（レガシー系統不変）。
- 「自走で自分を昇格する」ループに、**昇格が実際に効いていなければ自動で安全側へ戻す**装置を付与。
- scheduled=noop 不変（自動 paid 起動なし）。継続運用の周期は Owner 制御（手動 ≤10回/時）。

## 変更ファイル
- 追加: `scripts/post_promote_healthcheck.py` / `scripts/rollback_to_legacy_detector.py`
- 変更: `.github/workflows/immunization_loop.yml`（structured-promote に自己修復ステップ）
- 追加: `tests/test_self_healing.py`（rollback 3＋healthcheck 4＋workflow 1）
- 本報告

## 後検証
- スモーク：legacy→skip健全 / 有効ルール→tp1.0健全 / active 消失→不健全(fallback検知) / rollback→legacy化・フィールド除去。
- `pytest tests/ -q` → **3031 passed**。`validate_state.py` → PASS。YAML 妥当。

## Which layer did this task advance?
- [x] Layer 1（自律ループの自己修復＝継続自走の安全装置）

## 残存（M2 続き・Owner ゲート）
- サーキットブレーカー（連続失敗/予算超過での停止）— 予算は既存 api_budget が担保。連続失敗カウンタは将来増分。
- 周期自走の cadence は Owner 制御（scheduled の自動 paid 化は安全境界として行わない）。
- 実点火（structured-gemini-paid-credit＋promote_approved）で自己進化→評価→昇格→自己修復まで一気通貫。
