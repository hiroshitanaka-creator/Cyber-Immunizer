# タスク完了報告 — PR #156 Final Correctness Pass

**日付**: 2026-06-21
**ブランチ**: claude/repository-progress-ni8lko

---

## 概要

"Request Changes Task Prompt — PR #156 final correctness pass" の全要件を実装した。
scalar null 拒否修正・`_make_request()` body 修正・`_TIER_TAGS` / `per_tier` 集計追加・
`scripts/propose_mutation.py` GOOD example `.items()` 修正・新テスト追加・stale task report 更新を含む。

---

## 変更ファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `cli/structured_eval.py` | 変更 | scalar null 修正・body 修正・`_TIER_TAGS`・`per_tier` 集計・Markdown/JSON 出力追加 |
| `scripts/propose_mutation.py` | 変更 | GOOD example `.values()` → `.items()` でキー+値を両方包含 |
| `tests/test_structured_eval_cli.py` | 変更 | 63 → 77 テスト（null rejection・source_ip null 受容・per_tier・L2-V3 Tier セクション） |
| `docs/task_reports/TASK_REPORT_structured_eval_layer2_framework.md` | 変更 | 39テスト→77テスト / 2709→2747 に更新 |
| `docs/task_reports/TASK_REPORT_PR156.md` | 変更 | 2727 → 2747 に更新 |

---

## 主な変更内容

### 1. `load_corpus()` scalar null 拒否修正（`cli/structured_eval.py`）

- 旧: `method`/`path`/`body`/`source_ip` を同一ループで `if _v is not None` 判定 → null を誤って通過させていた
- 新: `method`/`path`/`body` は `if _sf in _req` で明示 null を検出して EvalError → `source_ip` は `_validate_optional_str` (null 許容)

### 2. `_make_request()` body 修正

- `req.get("body") or ""` → `req.get("body", "")` (明示 null が coerce されなくなる; load_corpus で事前拒否済みのため実質的防御強化)

### 3. `_TIER_TAGS` + `per_tier` 集計追加

- `_TIER_TAGS = frozenset({"holdout", "drift", "counterfactual"})` を `_KIND_TAGS` 直後に追加
- `run_evaluation()` に `per_tier: dict[str, dict[str, int]] = {}` を追加
- エントリのタグを走査して tier ごとに TP/FP/TN/FN/exceptions を集計（1エントリが複数 tier に計上可能）
- `build_markdown()` に `## L2-V3 Tier Results` セクション追加
- `build_json_report()` に `per_tier`（pass_rate 付き）を追加

### 4. `scripts/propose_mutation.py` GOOD example 修正

- `.values()` → `.items()` で `k, v` ペアを展開し、クエリ/ヘッダーのキーも surface に含める
- プロンプトヘッドルーム: +54 chars 増加で約 216 chars 残存（最小 200 chars 要件 ✅）

### 5. テスト追加（63 → 77 テスト）

- `test_load_corpus_rejects_malformed` 17 → 20 ケース（`method=null`・`path=null`・`body=null` の 3 件追加）
- `TestLoadCorpus.test_source_ip_null_is_accepted` — source_ip=null が受容されることを確認
- `TestLoadCorpus.test_build_json_report_null_path_raises_eval_error` — エンドツーエンド EvalError 確認
- `TestMainCLI.test_main_exits_2_on_null_body_corpus` — CLI exit-code-2 確認
- `TestRunEvaluation`: 5 件追加（per_tier キー存在・holdout/drift/counterfactual 集計・複数 tier・空・exception only）
- `TestBuildMarkdown.test_markdown_has_l2v3_tier_section` — `## L2-V3 Tier Results` セクション存在確認
- `TestBuildJsonReport.test_json_has_per_tier`, `test_json_per_tier_has_pass_rate` — JSON per_tier 確認

---

## 後検証結果

```
pytest tests/ -q
2747 passed, 5 warnings in 11.67s
```

```bash
# CLI smoke test — Markdown
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json
# → TP=5, FP=0, TN=5, FN=0 / ## L2-V3 Tier Results 出力あり (none)

# CLI smoke test — JSON
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json --json
# → overall.TP=5 / per_tier={} (symbolic corpus に tier tags なし) / per_kind.attack.TP=5
```

---

## 残存事項・注意点

- **Layer 2 は未達成**。per_tier 集計はフレームワーク完成を意味するが、Owner 提供の現実コーパスによる評価・承認が必要
- `fixtures/` はシンボリックプレースホルダのみ（tier tags なし）— per_tier が空になるのは正常動作
- `scripts/propose_mutation.py` 修正は `main` にマージ後の次回 Evolution Loop から有効

---

## タスクレイヤー宣言

```
[x] None（フレームワーク完成・品質向上のみ。Layer 2 は Owner による現実コーパス評価・承認が必要）
```
