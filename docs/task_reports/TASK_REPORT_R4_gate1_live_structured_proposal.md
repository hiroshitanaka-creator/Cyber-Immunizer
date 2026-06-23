# タスク完了報告 — R4 ゲート1：Gemini に構造化ルールを提案させる live モード

## 概要
R4-LLM の前提だった「live（paid-credit）で構造化検知ルールを提案するモードの不在」を解消した。`scripts/propose_mutation.py` に `--structured-rules --gemini-paid-credit --allow-live-model` 経路を追加。**API は呼ばず、モック Gemini でテスト**。生Python paid 経路と同一の genome 安全ゲート・予算・台帳・秘密スキャンを適用し、モデル出力は strict 構造化スキーマ検証を通過した場合のみ書き出す。Owner 承認済みの FROZEN 改修。

## 変更ファイル一覧
- 変更: `scripts/propose_mutation.py`
  - `_call_gemini_api` を `response_schema` / `system_instruction` でパラメータ化（既定は現状維持）
  - 共有ヘルパー `_check_paid_credit_genome_gates` を抽出（生Python paid 経路と構造化 paid 経路で同一ゲート）
  - `_STRUCTURED_SYSTEM_PROMPT` / `_build_structured_rules_prompt`（防御的・ペイロード非生成）
  - `_propose_structured_rules_via_gemini_paid_credit`（予算/台帳/秘密スキャン＋スキーマ検証）
  - `propose_structured_rules(..., gemini_paid_credit, allow_live_model)` 拡張
  - `main()` 構造化ハンドラを offline / paid 分岐に拡張（曖昧な併用は拒否）
- 追加: `tests/test_structured_rules_live.py`（12件、モック Gemini）
- 変更: `tests/test_structured_rules_proposal_output.py`（旧 PR-D の「paid 未統合」前提の2件を新挙動へ更新）
- 追加: `docs/task_reports/TASK_REPORT_R4_gate1_live_structured_proposal.md`（本報告）

## 安全設計
- モデル出力（ルール JSON）は `core.structured_validator.validate_rules_schema` を通過しないと破棄（output-contract failure）。ルールは「検知署名（データ）」であり実行コードではない。
- プロンプトは防御専用（WAF ルール作者）。exploit コード・ペイロード・bypass を求めない/生成しない方針を system prompt に明記。
- paid 安全ゲート（live_model_enabled / require_paid_tier / free_tier_only / 予算 / max_requests / grounding 等）を生Python 経路と共有（メッセージ不変）。
- 予算 fail-closed（strict_load_ledger + assert_budget_available）、台帳記録失敗時はルールを返さない。
- **このタスクで API 呼び出し・live 設定変更・workflow_dispatch は一切なし。**

## 後検証結果
- 新規: `pytest tests/test_structured_rules_live.py -q` → **12 passed**。
- 関連: `pytest tests/test_structured_rules_proposal_output.py -q` → 更新後 green。
- 既存 propose 系（`test_propose_mutation` / `test_propose_output_contract` / `test_gemini_paid_credit` / `test_gemini_integration`）→ 回帰なし。
- 全体: `pytest tests/ -q` → **2992 passed**。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（自律ループに live 構造化提案経路を追加。R4 実行の前提を充足）

## 残存事項・注意点
- 実際の R4 実行（API 呼び出し）には GEMINI_API_KEY が必要で、CLAUDE.md により手動 CI 起動は Owner の操作。**注意**: 現行の `.github/workflows/immunization_loop.yml` の `gemini-paid-credit` ステップは `--structured-rules` を渡しておらず、そのまま `workflow_dispatch` で起動すると**生 Python mutation を生成し、paid credit を別の実験に消費してしまう**。構造化提案を回すには、(a) `--structured-rules` を渡す workflow モードの追加（別途・Owner 承認）か、(b) 直接コマンド実行 `python scripts/propose_mutation.py --structured-rules --gemini-paid-credit --allow-live-model` のいずれかが必要。
- 無料枠で回す場合は genome の `free_tier_only=false` / `require_paid_tier=true` 等が paid 前提のため設定整理が必要（別タスク・Owner 判断）。
- 提案された現実ルールの評価・昇格は既存 `evaluate_structured_rules_candidate.py --corpus-dir`（外部現実コーパス）＋ `promote_structured_candidate.py --owner-approved`（R3）で実施。
