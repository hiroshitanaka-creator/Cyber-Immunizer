# タスク完了報告 — R4：現実能力検出器への昇格を end-to-end 実証（Owner 代理・サンドボックス）

## 概要
R3 で実装した構造化ルール昇格経路を使い、**現実能力の検出器への昇格を end-to-end で実際に実行**した。リポジトリの `data/` を丸ごとコピーしたサンドボックス上で、監査済み generation-4 baseline（best_score 948.04）に対して現実ルールを昇格させ、昇格後の active detector が現実攻撃を検知することを before/after で実証した。**本物の `data/genome.json` は legacy のまま不変**。生の検知署名はリポジトリに保存せず、中立化サマリのみコミット。

## 変更ファイル一覧
- 追加: `docs/value_validation/R4_PROMOTION_DEMONSTRATION_SUMMARY.md`（中立化サマリ）
- 追加: `docs/task_reports/TASK_REPORT_R4_promotion_demo.md`（本報告）

## 主な結果（数値）
- 昇格（サンドボックス、実 gen-4 baseline に対して）: detector_mode legacy→structured_rules、generation 4→5、best_score 948.04→**960.82**。現実ルールが live adoption gate（score 改善＋parity guard＋adaptive floor 全1.0）を通過し `--owner-approved` で昇格。
- active detector の現実攻撃検知（before/after）:
  - BEFORE（legacy gen-4）: **0/13（0%）**
  - AFTER（promoted gen-5）: **13/13（100%）**、benign 誤検知 0/9

## 後検証結果
- 昇格・評価はすべてサンドボックス（リポジトリ外コピー）で実行。本物の `data/genome.json` は `detector_mode="legacy"`（gen-4）のまま。
- サマリ文書に生の検知署名・攻撃文字列が含まれないことを確認（数値のみ）。
- `core/` `scripts/` `data/`（実体）は本タスクで未編集（docs 追加のみ）。

## Which layer did this task advance?
- [x] Layer 2 — Value Validation（プロジェクト中核の問い「検出器を現実能力へ進化できるか」に end-to-end で Yes と実証）
- docs-only 分類: Audit Evidence（監査証拠）

## 残存事項・注意点
- **本番ベースラインは未変更**。実 `data/` を structured_rules に切り替えるかは Owner の明示判断。その際は「現実署名をどこに保存するか」（ブループリント：コミットは中立化のみ／現実署名は外部）を決める必要がある。
- 現実コーパスは小規模・標準的（29件）。昇格機構と能力の実証であり production WAF ベンチマークではない。
- 昇格したルールは手書き。LLM に現実ルールを自律提案させるのは別途 paid-credit・Owner 承認のステップ。
