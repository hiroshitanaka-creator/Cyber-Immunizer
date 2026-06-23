# タスク完了報告 — Layer 2 tiered demonstration corpus

## 概要
`cli/structured_eval` は L2-V3 の per-tier（holdout / drift / counterfactual）集計を実装済みだが、それを実走させるコーパスが1つもコミットされていなかった。全4必須カテゴリ（path-traversal / xss / sqli / cmdi）＋3ティアを中立化プレースホルダで網羅したデモコーパスを追加し、ツールを実走させて per-category / per-tier 証拠を生成・コミットした。FROZEN（`core/**` `scripts/**` `.github/**` `data/**` 既存 `tests/**`）は一切編集していない。

## 変更ファイル一覧
- 追加: `fixtures/evaluation_corpus/tiered_demo_corpus.json`（17件の中立化ケース）
- 追加: `docs/value_validation/STRUCTURED_EVAL_TIERED_DEMO_REPORT.md`（実走 Markdown 証拠）
- 追加: `docs/value_validation/STRUCTURED_EVAL_TIERED_DEMO_REPORT.json`（実走 JSON 証拠）
- 追加: `docs/task_reports/TASK_REPORT_layer2_tiered_demo.md`（本報告）
- 変更: `fixtures/README.md`（新コーパスの説明・使用法・正直な限界を追記）

## 主な変更内容
- 全4必須カテゴリの attack ケース＋benign ケース（base tier）。
- holdout ティア: base に無いリクエスト形状で indicator を運ぶ attack/benign。
- drift ティア: indicator を header / path など別サーフェスで運ぶ attack/benign。
- counterfactual ティア: 攻撃に酷似するが indicator トークンを含まない benign（過学習プローブ）＋ 真の indicator を含む attack。
- すべてのリテラルは中立化プレースホルダ（`PATH_TRAVERSAL_INDICATOR` 等）のみ。raw exploit payload・bypass guidance・実トラフィックは一切含まない。

## 後検証結果
- `python -m cli.structured_eval --rules fixtures/structured_rules/symbolic_equivalent.json --corpus fixtures/evaluation_corpus/tiered_demo_corpus.json` → exit 0。
- 集計結果: overall TP=10 FP=0 TN=7 FN=0 exceptions=0（total_cases=17）。
- per-tier: holdout pass=1.0 / drift pass=1.0 / counterfactual pass=1.0（counterfactual は near-miss benign を正しく非ブロック=TN、真の indicator を正しくブロック=TP）。
- `python -m pytest tests/ -q` → **2953 passed**（FROZEN 未編集）。

## 正直な限界（重要）
- 本コーパスのリテラルはルール文書が照合する中立化プレースホルダそのものであるため、`tp_rate=1.0 / fp_rate=0.0` は **symbolic coverage** を示すにすぎず、**現実脅威カバレッジ（Layer 2 価値検証）の証拠ではない**。
- 本成果物は「評価パイプラインが per-category / per-tier の完全な出力を生成すること」を実証し、Owner が現実データを流し込むための **構造テンプレート** を提供するもの。
- L2-V2 のレイテンシ要件は本 CLI 単体では満たさない（ツール自身が明記）。
- Layer 2 達成には、Owner がリポジトリ外から「現実的だが安全に中立化された」rules / corpus を供給し、その証拠を Owner がレビュー・受理する必要がある。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（評価基盤の実走可能な実証カバレッジを拡張: L2-V3 ティア経路の初の実行可能デモ）
- [ ] Layer 2 — Value Validation（**未達**。本タスクは Layer 2 達成のための実行可能なオンランプであり、現実コーパス未供給のため Layer 2 はカウントしない）
- [ ] Layer 3 — AI Operation Control
- [ ] None

## 残存事項・注意点
- 真の Layer 2 達成は Owner 供給の現実コーパス待ち（リポジトリ外・read-only・防御専用）。
- 別途確認した衛生上の不備（DoD supporting criteria 違反）は本タスクのスコープ外として未対応:
  - ネストした空ディレクトリ `Cyber-Immunizer/`
  - スペース入りディレクトリ名 `text task-prompt-architect-gpt/`
  - 拡張子なしファイル `引き戻しプロンプト`（`docs/audit_gate/PULLBACK_PROMPT.md` と重複の疑い）
  これらは Owner 判断後に別タスクで対応する。
