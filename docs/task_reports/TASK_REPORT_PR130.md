# タスク完了報告 — PR #130 (PR-A review fix)

## 概要

PR #130 (branch `claude/pr-a-detection-result-x007`) の REQUEST CHANGES 対応。
DetectionResult 型コントラクトに存在した2つのバイパス経路を封鎖した。

## 変更ファイル一覧

- `core/policy.py` — Fix 1 (alias bypass) + Fix 2 (tuple literal bypass)
- `tests/test_ast_policy.py` — alias rejection の新規テスト4件追加
- `tests/test_detection_result_contract.py` — tuple literal rejection の新規テスト1件追加

## 主な変更内容

### Fix 1 — `check_imports()` alias bypass 封鎖 (`core/policy.py`)

`from core.types import DetectionResult as DR` のようなエイリアス付きインポートを検出して拒否。
`ast.ImportFrom` の `alias.asname is not None` をチェックして violation を生成する `else` ブランチを追加。
これにより `DR(False, "ok", 0.0, ())` のようなエイリアス経由の positional-args バイパスも封鎖される。

### Fix 2 — `_check_dr_confidence()` tuple literal bypass 封鎖 (`core/policy.py`)

`confidence=(0.5,)` のようなタプルリテラルを拒否。
collection literal チェックの isinstance 判定に `ast.Tuple` を追加
（変更前: `ast.List, ast.Set, ast.Dict` → 変更後: `ast.List, ast.Tuple, ast.Set, ast.Dict`）。

### テスト追加

`tests/test_ast_policy.py` — `TestForbiddenImports` クラスに4件追加:
- `test_rejects_aliased_detectionresult_import`
- `test_rejects_aliased_request_import`
- `test_rejects_aliased_detectionresult_positional_args_bypass`
- `test_canonical_import_still_accepted`

`tests/test_detection_result_contract.py` — `TestDetectionResultASTValidation` クラスに1件追加:
- `test_rejects_confidence_tuple_literal`

## 後検証結果

```
pytest tests/test_detection_result_contract.py tests/test_ast_policy.py -q
→ 141 passed

python scripts/validate_mutation.py --candidate core/detector.py --json
→ {"valid": true, "violations": []}

pytest tests/ -q
→ 2452 passed, 5 warnings
```

HEAD SHA: `14eeb50`

## 残存事項・注意点

なし。Definition of Done の全条件を満たす。
