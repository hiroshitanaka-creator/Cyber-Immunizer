# タスク完了報告 — Layer 2 現実コーパス評価（Owner 代理実行）

## 概要
Project Owner の指示により、現実的（標準検知パターンのみ・中立化）な評価コーパスをリポジトリ外で作成し、評価ツールを代理実行した。「現在の検出器の能力（symbolic）」と「現実ルール」の両方を同一コーパスで採点し、初めて数値で Layer 2 の現状を実証した。生の攻撃文字列・ルールリテラルはリポジトリに保存せず、数値サマリのみコミット。

## 変更ファイル一覧
- 追加: `docs/value_validation/LAYER2_REALISTIC_EVALUATION_SUMMARY.md`（中立化サマリ）
- 追加: `docs/task_reports/TASK_REPORT_layer2_realistic_eval.md`（本報告）

## 主な結果（数値）
- **現在の検出器（symbolic, gen4 best_score 948.04）× 現実コーパス**: 全カテゴリ TP rate **0.0%**（path-traversal/xss/sqli/cmdi すべて 0）。gate 採点 FAILED（score −1543.62）。→「記号の壁」を初めて数値で確認。
- **現実ルール × 現実コーパス**: TP rate **100.0%**、FP rate 0.0%、holdout/drift/counterfactual 全 1.0。gate 採点 PASSED（score 960.82）。→ structured 経路で壁を突破できる安全な道筋を実証。
- 評価軸: per-category TP/FP/FN（L2-V2）、latency（gate 評価器）、3ティア pass rate（L2-V3）、symbolic→realistic の before/after（L2-V4）、symbolic と realistic の区別（L2-V5）。

## 後検証結果
- `core/detector.py` 未編集。生データはリポジトリ外（scratchpad）に保持しコミットせず。
- サマリ文書に生の攻撃文字列・ルールリテラルが含まれないことを確認（カテゴリ名と数値のみ）。

## Which layer did this task advance?
- [x] Layer 2 — Value Validation（**候補証拠を提示**。L2-V1〜V5 をカバー。ただし正式達成は Owner の受理が条件）
- 補足: docs-only 分類 = Audit Evidence（監査証拠）

## 残存事項・注意点
- **Layer 2 正式達成には Owner の受理が必要**（サマリ文書のチェックボックス、または `docs/PROJECT_STATE.md` への受理記録）。
- 現実コーパスは小規模・標準的（29件）。能力と壁の実証であり、production WAF ベンチマークではない。
- 結果2は手書きの現実ルールの採点であり、LLM が進化させた検出器ではない。検出器自体を現実能力へ進化させるのは将来の Owner 判断作業（設計文書 Phase 5–7）。
