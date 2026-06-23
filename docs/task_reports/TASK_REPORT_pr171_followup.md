# タスク完了報告 — PR #171 follow-up（Codex P2 是正＋未統合コミット取り込み）

## 概要
マージ済 PR #171 に Codex が残した**有効な P2 指摘12件**を是正し、squash マージ後にブランチへ積まれて main に未統合だった**2コミット（R4 計画・ゲート1）**を取り込んだ follow-up。Project Owner が本 Claude タスクに対する許可を明示（PR 本文に記載）。全テスト **3000 passed**、リポジトリ内の個人メール（PII）を完全除去。

## 取り込んだ未統合コミット（cherry-pick from old branch）
- `R4-LLM 計画書`（`docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md` 他）
- `ゲート1：live 構造化提案モード`（`scripts/propose_mutation.py` + `tests/test_structured_rules_live.py` 他）

## Codex P2 指摘の是正（12件）
| # | 指摘 | 対応 | 種別 |
|---|---|---|---|
| 1 | adaptive tier の kind 未強制（false green 可能） | 外部 per-tier ファイルの kind 不一致を tool failure 化 | 実バグ |
| 2 | 外部コーパスの FIFO/サイズ未検査 | 全コーパスパスを stat（正規ファイル＋サイズ）検査 | 防御 |
| 3 | 空 main tier で baseline 合格 | 外部コーパスの空 main tier を tool failure 化 | 実バグ |
| 4 | SSOT 不整合（data/project_state.json） | `layer_2_value_validation` ブロックを追加（next_action は固定値維持） | 整合 |
| 5 | LAYER2 サマリの L2-V2/V4 過大表記 | 「Partial」と限界を明記 | 整合 |
| 6 | **個人メール（PII）コミット** | `hiroshitanaka-creator` に置換・全箇所除去 | 🔴PII |
| 7 | promote が非正規 rules ファイル未検査 | `stat.S_ISREG` 検査追加 | 防御 |
| 8 | promote の TOCTOU（評価後にファイル変化） | 評価後に再読込し raw_text と一致検証 | 実バグ |
| 9 | legacy promote が detector_mode 未リセット | `promote_candidate.py` で legacy にリセット＋active path 削除 | 実バグ |
| 10 | active_detector が検証時に例外送出し得る | validate を fail-safe try に内包（never raises 維持） | 実バグ |
| 11 | promote 前検証の例外で traceback | validator 例外を捕捉し fail-closed 拒否 | 防御 |
| 12 | リポジトリ外 active rules の相対パス記録 | repo 外は絶対パスを記録 | 実バグ |

## 変更ファイル
- `core/active_detector.py`（#10）
- `scripts/promote_candidate.py`（#9）
- `scripts/promote_structured_candidate.py`（#7/#8/#11/#12）
- `scripts/evaluate_structured_rules_candidate.py`（#1/#2/#3）
- `data/project_state.json`（#4）
- `docs/value_validation/LAYER2_REALISTIC_EVALUATION_SUMMARY.md`（#5/#6）
- tests: `test_active_detector.py` / `test_promote_structured_candidate.py` / `test_evaluate_structured_rules_candidate.py` / `test_promote_candidate.py`（回帰テスト追加）
- 取り込み: `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md` / `docs/task_reports/TASK_REPORT_R4_llm_plan.md` / `scripts/propose_mutation.py` / `tests/test_structured_rules_live.py` / 関連 task report

## 後検証結果
- `python -m pytest tests/ -q` → **3000 passed**。
- `python scripts/validate_state.py` → PASS（10ファイル）。
- `git grep tanakantyo0229` → 0件（PII 完全除去）。
- API 呼び出し・live 設定変更・workflow_dispatch・paid-credit 実行は一切なし。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（自律ループ部品の堅牢化＋未統合機能の取り込み）
- docs-only 分類（一部）: Audit Evidence / Current-State SSOT

## 残存事項・注意点
- 本番 `detector_mode` は legacy のまま（挙動不変）。
- 実 R4 実行（API）・本番ベースライン切替は引き続き Owner ゲート。
