# タスク完了報告 — M1 配線：ワークフローに structured 自己進化モードを追加

## 概要
理念（自律的に自己進化する免疫システム）の本線 M1 の配線として、`.github/workflows/immunization_loop.yml`
の propose ジョブに **structured モード2種**を追加した。これで自律ループの「**LLM が構造化防御ルールを
自分で書く**」入口が CI から起動可能になる。**自動起動の挙動は不変**（scheduled は noop のまま、
structured-paid は手動 workflow_dispatch のオプトインかつ main-only）。既存の最小権限・秘密スコープ・
ledger 永続・fail-closed を完全踏襲。本タスクで API 呼び出し・live 実行・workflow_dispatch 起動は行わない。

## 追加した dispatch モード
- `structured-offline-sample`：`propose_mutation.py --structured-rules --offline-sample`（**鍵なし**・書込なし）
- `structured-gemini-paid-credit`：`propose_mutation.py --structured-rules --gemini-paid-credit --allow-live-model`
  （propose ステップに **GEMINI_API_KEY をステップスコープ注入**、**main-only ガード適用**）

両モードは `.cyber_immunizer/structured_rules.json` を生成し、新規アーティファクト `structured-rules`
としてアップロード。**raw-Python の evaluate/promote ジョブは `patch_exists=false` で自然に skip**
（mutation_patch.json を生成しないため）。paid 構造化の ledger 変更は既存 persist-ledger が永続化。

## 安全性（既存ガード踏襲）
- GEMINI_API_KEY は propose ジョブの paid ステップのみ（promote/persist-ledger/finalize には無し）。
- structured-paid は main 以外で実行拒否（ledger 永続が main 正典のため）。
- scheduled は強制 noop（自動 paid 実行なし）。
- 構造化の評価/昇格は別経路（`evaluate_structured_rules_candidate.py` / `promote_structured_candidate.py`）。
  本 PR ではワークフロー内の structured evaluate/promote ジョブ化は行わない（次増分）。

## 変更ファイル
- `.github/workflows/immunization_loop.yml`（dispatch options＋propose 2ステップ＋deps install 条件＋
  main-only ガード＋structured-rules アーティファクト）
- `tests/test_workflow.py`（structured モードの存在・鍵スコープ・main-only・アーティファクトを検証する回帰テスト5件）
- 本報告

## 後検証
- `python -c "import yaml; yaml.safe_load(...)"` → YAML 妥当。
- `pytest tests/test_workflow.py tests/test_ci_workflow.py tests/test_preflight_workflow.py tests/test_preflight_mode.py` → green。
- `pytest tests/ -q` → **3019 passed**。`validate_state.py` → PASS。

## Which layer did this task advance?
- [x] Layer 1（自律ループの live 配線。LLM が構造化防御を CI から提案できる入口を整備）

## 残存（次増分・Owner ゲート）
- ワークフロー内の **structured evaluate ジョブ＋structured promote ジョブ**（現状はアーティファクト出力まで。
  評価/昇格は CLI または次の配線で）。
- Owner による live paid 起動（≤10回/時・無料枠）で実際の自己進化を点火。
- 本番 `detector_mode` の structured 切替（`docs/PRODUCTION_DETECTOR_FLIP_DESIGN.md` 案1）。
