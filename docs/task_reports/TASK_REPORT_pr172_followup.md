# タスク完了報告 — PR #172 follow-up（新規 P2 4件是正＋実用防御コミット取り込み）

## 概要
マージ済 PR #172 に Codex が残した**新規の有効 P2 指摘4件**を是正し、#172 マージ後にブランチへ積まれて main に未統合だった**実用的防御コミット（realistic ruleset + corpus + 回帰テスト + ガバナンス是正）**を取り込んだ follow-up。Owner が本タスクを明示承認（public リポジトリ）。全テスト **3009 passed**。

## 取り込んだ未統合コミット（cherry-pick）
- 実用的防御能力：`fixtures/structured_rules/realistic_baseline.json`（21署名）、`fixtures/realistic_corpus/`（34件）、`tests/test_realistic_ruleset.py`、`docs/value_validation/REALISTIC_DETECTION_RESULTS.md`、ブループリントの Owner 方針是正。

## Codex 新規 P2 の是正（4件）
| # | 指摘 | 対応 |
|---|---|---|
| 1 | live 構造化提案で validator 例外(OverflowError)未捕捉→paid 後に traceback | `_propose_structured_rules_via_gemini_paid_credit` の検証を try/except で output-contract failure 化 |
| 2 | R4 gate1 報告の CI 手順が `--structured-rules` 未付与→paid credit 誤用リスク | 報告に「現行 workflow は --structured-rules を渡さない」警告と直接コマンドを明記 |
| 3 | empty-main-tier ガードが outcome ベースで kind 不一致を見逃す（false green） | ガードを **kind ベース**集計に変更＋全 per-tier ファイルに kind 一致を強制 |
| 4 | コーパス precheck が RecursionError 未捕捉 | precheck の except に RecursionError 追加 |

## 変更ファイル
- `scripts/propose_mutation.py`（#1）
- `scripts/evaluate_structured_rules_candidate.py`（#3/#4）
- `docs/task_reports/TASK_REPORT_R4_gate1_live_structured_proposal.md`（#2）
- tests: `test_structured_rules_live.py`（validator 例外）/ `test_evaluate_structured_rules_candidate.py`（kind ベース false-green ガード）
- 取り込み: realistic ruleset/corpus/test/evidence/blueprint（cherry-pick）

## 後検証
- `pytest tests/ -q` → **3009 passed**。
- `validate_state.py` → PASS。
- API 呼び出し・live 設定変更・workflow_dispatch なし。本番 detector_mode は legacy のまま。

## Which layer did this task advance?
- [x] Layer 1（堅牢化）
- [x] Layer 2（実用防御の取り込み）

## 残存事項
- 本番既定 runtime の structured 切替（再ベースライン化）は引き続き別 PR。
