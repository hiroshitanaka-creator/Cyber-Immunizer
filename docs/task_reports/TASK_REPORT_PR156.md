# タスク完了報告 — PR #156

## 概要

PR #156「fix(propose) + feat(structured-eval): indicator-preservation prompt hardening & Layer 2 evaluation framework」に対するCodexレビュー指摘 C1〜C8 の全対応、CI 修正（ledger カウント 10→13）、および corpus validation 強化（Request Changes Task Prompt 対応）を完了した。

## 変更ファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `cli/structured_eval.py` | 変更 | corpus バリデーション強化・例外処理修正・型検証ヘルパー追加 |
| `cli/report.py` | 変更 | Score Interpretation 動的化・Layer 2 全5要件列挙 |
| `scripts/propose_mutation.py` | 変更 | GOOD example を全5インジケーター含む for ループ実装に更新 |
| `data/project_state.json` | 変更 | success records 10→13・run_11/12/13 triage エントリ追加 |
| `docs/PROJECT_STATE.md` | 変更 | SSOT 同期（13件・run 11/12/13 triage 記録） |
| `tests/test_project_state_sync.py` | 変更 | `assert actual == 13`・test_19 更新 |
| `tests/test_structured_eval_cli.py` | 変更 | 17ケース parametrized テスト + CLI exit-code-2 テスト追加（39→57テスト） |

## 主な変更内容

### C1 — expected_blocked 型検証
- `load_corpus()` と `run_evaluation()` の両方に `isinstance(_, bool)` チェックを追加
- `"true"`・`1`・`null` などを EvalError で即時拒否

### C2 — Score Interpretation 動的化
- `cli/report.py`: 全世代の `tp_rate`/`fp_rate` を確認し、完全一致なら symbolic 旨を、varying なら varying 旨を動的に出力

### C3 — GOOD example 全5インジケーター化（scripts/propose_mutation.py）
- 旧: path_traversal_indicator のみの単純例
- 新: 5インジケーターを for ループで列挙するコード例に更新
- プロンプトヘッドルーム: 433 chars（最小 200 chars 要件 ✅）

### C4 — Layer 2 全5要件列挙
- `cli/report.py`: L2-V1〜V5（realistic coverage / per-category / holdout-drift / improvement explanation / no-overfitting）を全列挙

### C5 — 例外ケース TN 汚染バグ修正
- 例外発生時 `outcome = None` として TP/FP/TN/FN 加算をスキップ
- `exceptions` カウンタのみ加算し、`per_case` には `"exception"` として記録

### C6 — request フィールド型検証
- `method`/`path`/`body`/`source_ip`: str or absent を検証
- `query`/`headers`: dict or absent を検証（値の str 型は C8 強化で対応）

### C7 — ゼロ除算 n/a 表示
- `_tp_rate()`・`_fp_rate()`・`_fn_rate()` が分母0のとき `None` を返す
- `_pct(None)` → `"n/a"` を表示（偽の `0.0%` を排除）

### C8 — Markdown インジェクション対策
- `_md_cell()` 関数追加: パイプ文字(`|`)・CR/LF をエスケープ
- per-category・per-case の全 Owner 提供値に適用

### corpus validation 強化（Request Changes Task Prompt 対応）
- `_validate_optional_str()` / `_validate_optional_str_list()` / `_validate_request_mapping()` ヘルパー追加
- `load_corpus()`: `id`/`kind`（string or absent）・`source_ip`（string or absent）・`tags`（list of strings）・`query`/`headers` 値（全 string）を検証
- `_make_request()`: 不要な `str()` ラッパーを除去（`body=req.get("body") or ""`）

### CI 修正（ledger カウント 10→13）
- Runs #64/#65/#66 が CI で auto-commit されたが `project_state.json` は未更新だった
- `data/project_state.json`: 10→13、run_11/12/13 triage（`evaluate_rejected` / `missing_baseline_symbolic_indicator_runtime`）追加
- `docs/PROJECT_STATE.md`: SSOT 同期
- `tests/test_project_state_sync.py`: `assert actual == 13` に更新

## 後検証結果

```
pytest tests/ -q
2747 passed, 5 warnings in 11.67s
```

## 残存事項・注意点

- Layer 2 は未達成（Owner 提供の現実コーパスが必要）
- `fixtures/` はシンボリックプレースホルダのみ — Layer 2 証拠として使用不可
- プロンプト修正は `main` にマージ後、次の Evolution Loop 実行から有効

## Layer 分類

- [x] Layer 1 — Research Foundation（corpus validation・eval framework 品質向上）
- [ ] Layer 2 — Value Validation（未達成）
- [ ] Layer 3 — AI Operation Control
