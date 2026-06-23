# タスク完了報告 — R4-LLM 自律提案の計画・preflight・予算整理（API 不使用）

## 概要
Gemini に「現実的な構造化検知ルール」を自律提案させ、R3 経路で昇格する R4-LLM の実行計画を作成した。**paid-credit API は一切呼んでいない**。API を呼ばない既存の readiness / preflight / budget を実行して現状を記録し、最大の前提ギャップ（live 構造化提案モードの不在）を特定した。

## 変更ファイル一覧
- 追加: `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md`（計画・preflight・予算・安全制約・ゲート）
- 追加: `docs/task_reports/TASK_REPORT_R4_llm_plan.md`（本報告）

## 主な内容
- **前提ギャップ**: `--structured-rules` は `--offline-sample` 専用で、live（paid）構造化提案モードが無い。R4 にはこのモードの新設（scripts FROZEN・Owner 承認・API 不要で実装可）が必要。
- **意図するパイプライン**: propose（live structured・PAID）→ evaluate（外部現実コーパス・API不要）→ promote（R3・API不要）。evaluate/promote は実装済み。
- **必要な Owner ゲート**: (1) 提案モード実装承認、(2) paid-credit 実行承認、(3) 外部現実コーパス供給、(4) 昇格承認。
- **readiness/preflight（API不使用）**: readiness=ready:true（gen-4 整合）。preflight はこのサンドボックスに `GEMINI_API_KEY` が無く停止（鍵は CI Secrets 側、正常）。
- **予算**: 月$10/日$0.25、1回 ≈ $0.034（過大見積）、約7回/日の余裕。budget gate は fail-closed。

## 後検証結果
- `scripts/pre_paid_credit_readiness.py` → ready:true。
- `scripts/api_budget.py` 関数でコスト見積を算出（≈$0.034/run）。
- API 呼び出し・live 設定変更・workflow_dispatch は一切行っていない。

## Which layer did this task advance?
- [ ] Layer 2（計画のみ。実行は Owner ゲート後）
- docs-only 分類: Owner Intent / 計画記録 + Safety Boundary（ゲート定義）

## 残存事項・注意点
- 実際の R4 実行には live 構造化提案モードの実装（ゲート1）が先決。これは API 不要・テスト可能。
- 本計画書はいかなる paid-credit 実行・live 設定変更も承認しない。
