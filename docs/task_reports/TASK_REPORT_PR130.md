# タスク完了報告 — PR #130 (PR-A final merge-grade fix)

## 概要

PR #130 (branch `claude/pr-a-detection-result-x007`) の final merge-grade 対応。
ラッパー式経由の DetectionResult エイリアスバイパスを封鎖し、全 Acceptance Criteria を充足した。

## 変更ファイル一覧

- `core/policy.py` — `_expr_contains_detectionresult_reference()` で再帰的 RHS スキャンに強化
- `tests/test_ast_policy.py` — `TestDetectionResultLocalAliases` クラスにラッパー式テスト5件追加

## 主な変更内容

### Fix 1 — import alias bypass 封鎖 (`core/policy.py:127-159`)

`from core.types import DetectionResult as DR` — `alias.asname is not None` で拒否。（前回実装済み）

### Fix 2 — `confidence=(0.5,)` tuple literal bypass 封鎖 (`core/policy.py:967-971`)

`_check_dr_confidence()` に `ast.Tuple` を追加。（前回実装済み）

### Fix 3 — direct local alias bypass 封鎖 (`core/policy.py:1042-1077`)

`check_detection_result_aliases()` が `DR = DetectionResult` 等を検出。（前回実装済み）

### Fix 4 — wrapper-expression alias bypass 封鎖 (`core/policy.py:1010-1077`)

`_is_detectionresult_name()` + `_check_value()` を廃棄し、再帰スキャナー
`_expr_contains_detectionresult_reference()` に置き換え。

カバー範囲（`ast.iter_child_nodes` による再帰走査）:
- `(DetectionResult,)[0]` → `ast.Subscript` → `ast.Tuple` → `ast.Name`
- `[DetectionResult][0]` → `ast.Subscript` → `ast.List` → `ast.Name`
- `DetectionResult if cond else DetectionResult` → `ast.IfExp` → `ast.Name`
- `{"ctor": DetectionResult}["ctor"]` → `ast.Subscript` → `ast.Dict` → `ast.Name`
- `(DetectionResult or DetectionResult)` → `ast.BoolOp` → `ast.Name`

**カノニカルコンストラクタ呼び出しの例外**: `result = DetectionResult(blocked=..., ...)` のように
RHS が DetectionResult(...) コールそのものである場合は、callee の `Name` を skip して
args/keywords のみを再帰検査する。これにより canonical result-assignment は引き続き許容される。

### テスト追加 (`tests/test_ast_policy.py:263-313`)

`TestDetectionResultLocalAliases` クラスに5件追加（既存7件に追加）:
- `test_rejects_tuple_subscript_detectionresult_alias` — `(DetectionResult,)[0]`
- `test_rejects_list_subscript_detectionresult_alias` — `[DetectionResult][0]`
- `test_rejects_ifexp_detectionresult_alias` — `DetectionResult if True else DetectionResult`
- `test_rejects_dict_subscript_detectionresult_alias` — `{"ctor": DetectionResult}["ctor"]`
- `test_canonical_detectionresult_result_assignment_allowed` — canonical result-assignment は許容（regression）

## 後検証結果

```
python -m pytest tests/test_ast_policy.py tests/test_detection_result_contract.py -q
→ 153 passed

python scripts/validate_mutation.py --candidate core/detector.py --json
→ {"valid": true, "violations": []}

python -m core.fitness --candidate core/detector.py --baseline --json
→ {"ast_policy_ok": true, "score": 948.04, "passed_adoption_gate": true}

python -m pytest tests/ -q
→ 2464 passed, 5 warnings
```

Verification head: 03f0ce6 (pre-this-fix) → commit 後は同一ブランチの次 SHA  
Latest PR head at report time: 本 commit の SHA（下記 commit 後に確定）

## Codex alias thread

Import alias、direct local alias、wrapper-expression alias のすべてを封鎖済み。
Resolved: import aliases rejected by `check_imports()`; local and wrapper-expression aliases
rejected by `check_detection_result_aliases()` + `_expr_contains_detectionresult_reference()`.
Added regression tests for `DR = (DetectionResult,)[0]`, `DR = [DetectionResult][0]`,
and conditional alias creation.

## 残存事項・注意点

なし。Acceptance Criteria の全15条件を充足。
