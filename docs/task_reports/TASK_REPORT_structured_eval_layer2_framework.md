# タスク完了報告 — 構造化評価フレームワーク（Layer 2 価値検証ツール）

**日付**: 2026-06-21
**ブランチ**: claude/repository-progress-ni8lko

---

## 概要

Layer 2 価値検証（DEFINITION_OF_DONE.md L2-V1〜V5）への道筋として、
`cli/structured_eval.py`（per-category TP/FP/FN 評価 CLI）と
`fixtures/`（中立化サンプルルール・コーパス）を新規実装した。

また `cli/report.py` にスコア解釈セクションと Layer 2 ギャップ分析セクションを追加し、
evolution_history.json のスコア改善が「コードサイズ削減」に起因することを明示した。

---

## 変更ファイル一覧

**新規作成:**
- `cli/structured_eval.py` — per-category 構造化ルール評価 CLI
- `fixtures/README.md` — フィクスチャ利用方法とスキーマ説明
- `fixtures/structured_rules/symbolic_equivalent.json` — gen-4 相当の中立化ルール
- `fixtures/structured_rules/path_traversal_only.json` — path-traversal カテゴリ専用ルール
- `fixtures/structured_rules/xss_only.json` — XSS カテゴリ専用ルール
- `fixtures/structured_rules/sqli_only.json` — SQLi カテゴリ専用ルール
- `fixtures/structured_rules/cmdi_only.json` — CMDi カテゴリ専用ルール
- `fixtures/evaluation_corpus/symbolic_corpus.json` — 中立化テストコーパス（10件）
- `tests/test_structured_eval_cli.py` — 77テスト（PR #156 最終修正後の確定値）

**変更:**
- `cli/report.py` — Score Interpretation + Layer 2 Gap セクション追加

---

## 主な変更内容

### `cli/structured_eval.py`

- `load_rules(path)` — `core.structured_validator` でスキーマ検証後にロード
- `load_corpus(path)` — テストコーパス JSON をロード・検証
- `run_evaluation(rules_doc, corpus)` — per-case TP/FP/TN/FN 集計と per-category 集計
- `build_markdown(rules_path, corpus_path)` — Markdown レポート生成
- `build_json_report(rules_path, corpus_path)` — JSON レポート生成
- `main(argv)` — CLI エントリポイント（`--rules`, `--corpus`, `--json`）

**利用方法:**
```bash
# 付属フィクスチャ（シンボリック、Layer 2 証拠ではない）
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json

# Owner 提供のリアルデータ（リポジトリ外、Layer 2 評価用）
python -m cli.structured_eval \
  --rules /path/to/owner/realistic_rules.json \
  --corpus /path/to/owner/realistic_corpus.json
```

### `cli/report.py` の追加セクション

**Score Interpretation**:
- 全世代で tp_rate=1.0/fp_rate=0.0 が当然の理由（シンボリックコーパス）を説明
- スコア改善（383→948）が「コードサイズ削減」によるものであり防御改善ではないことを明示
- 公式: `score = 1000*tp_rate − 0.02*code_chars` でコードサイズ減少がスコアを上げる

**Layer 2 Gap**:
- L2-V1〜V5 の現在未充足状態を明示
- `cli/structured_eval` を Layer 2 評価ツールとして案内
- Owner がリポジトリ外で提供する現実コーパスが必要であることを記載

---

## テスト結果

```
pytest tests/ -q
2747 passed, 5 warnings in 11.67s
```

- 追加テスト: 77件（test_structured_eval_cli.py — PR #156 最終修正後の確定値）
- 既存テスト: 2670件（全通過）
- 合計: 2747件

---

## 後検証結果

```bash
# CLI 動作確認
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json
# → TP=5, FP=0, TN=5, FN=0（4カテゴリすべて 100% 検知）

# 全フィクスチャのスキーマ検証（テストで確認済み）
# path_traversal_only.json, xss_only.json, sqli_only.json, cmdi_only.json — 全合格
```

---

## 残存事項・注意点

- **Layer 2 は未達成**。このタスクは Layer 2 評価フレームワークを構築したが、
  Layer 2 達成には Owner による現実（非シンボリック）コーパスの提供と評価承認が必要。
- フィクスチャ（`fixtures/`）はシンボリックプレースホルダのみ。
  Layer 2 証拠として使用不可。
- `data/project_state.json` は Owner 承認のもと変更済み（ledger カウント同期）。`data/**` のその他のファイルは変更なし。
- `scripts/propose_mutation.py` は Owner 承認のもと変更済み（GOOD example 更新・プロンプト強化）。`scripts/**` のその他のファイルは変更なし。
- `core/**`, `.github/**` は FROZEN のため変更なし。

---

## タスクレイヤー宣言

```
Which layer did this task advance?
[ ] Layer 1 — Research Foundation
[ ] Layer 2 — Value Validation
[ ] Layer 3 — AI Operation Control
[x] None（ドキュメント整備・ツール実装のみ。Layer 2 は Owner による現実コーパス評価・承認が必要）
```

**注**: Layer 2 完了条件（L2-V1〜V5 全充足 + Owner 承認）は未達。
`docs/DEFINITION_OF_DONE.md` に明示のとおり、ドキュメント・テスト・プロトコルの追加のみでは
Layer 2 の進捗としてカウントしない。
L2-V1〜V5 の達成には Owner 提供の現実（非シンボリック）コーパスでの評価と Owner 承認が必要。
