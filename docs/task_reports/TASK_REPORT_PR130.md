# タスク完了報告 — PR #130 (PR-A merge-grade fix)

## 概要

PR #130 (branch `claude/pr-a-detection-result-x007`) の merge-grade 対応。
DetectionResult 型コントラクトに存在した3つのバイパス経路をすべて封鎖した。

## 変更ファイル一覧

- `core/policy.py` — Fix 1 (import alias bypass) + Fix 2 (tuple literal) + Fix 3 (local alias bypass)
- `tests/test_ast_policy.py` — 計11件のテスト追加 (import alias 4件 + local alias 7件)
- `tests/test_detection_result_contract.py` — tuple literal rejection テスト1件追加

## 主な変更内容

### Fix 1 — `check_imports()` import alias bypass 封鎖 (`core/policy.py:127-159`)

`from core.types import DetectionResult as DR` のようなエイリアス付きインポートを検出して拒否。
`alias.asname is not None` チェックを `ast.ImportFrom` ハンドラの `else` ブランチに追加。

### Fix 2 — `_check_dr_confidence()` tuple literal bypass 封鎖 (`core/policy.py:967-971`)

`confidence=(0.5,)` のようなタプルリテラルを拒否。
`isinstance(val, (ast.List, ast.Tuple, ast.Set, ast.Dict))` に `ast.Tuple` を追加。

### Fix 3 — `check_detection_result_aliases()` local alias bypass 封鎖 (`core/policy.py:1010-1054`)

`DR = DetectionResult` のようなローカルエイリアス作成を検出して拒否する新チェッカーを追加。
カバー範囲:
- `ast.Assign` (単純代入・チェーン代入)
- `ast.AnnAssign` (`DR: object = DetectionResult`)
- `ast.NamedExpr` (walrus operator)
- タプルアンパック: `DR, x = DetectionResult, None`
- チェーン代入: `a = b = DetectionResult`

`run_full_policy()` のステップ10として `check_detection_result_static_values()` の前に組み込み済み。

### テスト追加

`tests/test_ast_policy.py` — `TestForbiddenImports` クラスに4件:
- `test_rejects_aliased_detectionresult_import`
- `test_rejects_aliased_request_import`
- `test_rejects_aliased_detectionresult_positional_args_bypass`
- `test_canonical_import_still_accepted`

`tests/test_ast_policy.py` — `TestDetectionResultLocalAliases` クラス（新規）7件:
- `test_rejects_local_detectionresult_alias_assignment`
- `test_rejects_local_detectionresult_alias_positional_bypass`
- `test_rejects_annotated_detectionresult_alias_assignment`
- `test_rejects_chained_alias_assignment`
- `test_rejects_tuple_unpacking_alias`
- `test_canonical_detectionresult_call_not_rejected`
- `test_dynamic_canonical_call_not_rejected`

`tests/test_detection_result_contract.py` — `TestDetectionResultASTValidation` クラスに1件:
- `test_rejects_confidence_tuple_literal`

## 後検証結果

```
python -m pytest tests/test_ast_policy.py tests/test_detection_result_contract.py -q
→ 148 passed

python scripts/validate_mutation.py --candidate core/detector.py --json
→ {"valid": true, "violations": []}

python -m core.fitness --candidate core/detector.py --baseline --json
→ {"ast_policy_ok": true, "score": 948.04, "passed_adoption_gate": true}

python -m pytest tests/ -q
→ 2459 passed, 5 warnings
```

HEAD SHA: `e881987` (pre-fix) → 最終 HEAD は commit 後に更新

## 残存事項・注意点

なし。Acceptance Criteria の全条件を満たす。
`docs/task_reports/TASK_REPORT_PR130.md` は本ファイル自体（owner が docs-in-PR-A を許容する前提で保持）。
