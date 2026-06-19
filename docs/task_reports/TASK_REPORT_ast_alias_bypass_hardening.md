# タスク完了報告 — AST Alias Bypass Hardening

## 概要

`core/policy.py` に `check_forbidden_name_references()` を追加し、エイリアス経由で禁止 builtin を呼び出す bypass クラスを閉鎖した。`tests/test_ast_policy.py` に **9 件の負テスト**と正テスト 1 件を追加し、全 AST policy テストが通過することを確認した。

## Pre-Prompt Investigation Gate Result

- HEAD SHA: `3a480ef934b1d4e25ec9f3a27af8f16c1373993a`（タスクプロンプト記載 SHA と一致）
- core/policy.py inspected: ✅（`check_forbidden_calls` は直接呼び出しのみ検査; `check_dunder_access` は `ast.Attribute` のみ対象で `ast.Name` dunder は未検査）
- scripts/validate_mutation.py inspected: ✅（`validate()` は `run_full_policy()` への thin wrapper のみ）
- core/fitness.py inspected: ✅（`run_full_policy()` をモジュール import 前に適用）
- core/detector.py baseline validation before change: `valid=true, violations=[]` ✅
- alias-chain negative test coverage before change: 0 件（既存テストは直接呼び出しのみ）

## 変更ファイル一覧

| ファイル | 変更種別 | 理由 |
|---|---|---|
| `core/policy.py` | 追加 | `check_forbidden_name_references()` 関数追加、`run_full_policy()` に組み込み |
| `tests/test_ast_policy.py` | 追加 | `TestAliasAndDunderNameBypassClosure` クラス（10 テスト: 9 負 + 1 正）追加 |
| `docs/task_reports/TASK_REPORT_ast_alias_bypass_hardening.md` | 新規 | 本報告ファイル |

## 主な変更内容

### core/policy.py

- `check_forbidden_name_references(tree)` を新規追加（`check_dunder_access` の直後に定義）
  - `ast.walk` で全 `ast.Name` ノードを走査
  - `id in FORBIDDEN_BUILTINS` → `"forbidden name reference: {name!r}"` violation
  - `id.startswith("__") and id.endswith("__") and len(id) >= 5` → `"forbidden dunder name reference: {name!r}"` violation
- `run_full_policy()` 内のステップ 6c として挿入（`check_forbidden_calls` の直後、`check_dunder_access` の前）

### tests/test_ast_policy.py

`TestAliasAndDunderNameBypassClosure` クラスを追加:

| テスト名 | 検証対象パターン |
|---|---|
| `test_rejects_alias_to_open_call` | `f = open; f("/tmp/x")` |
| `test_rejects_alias_to_eval_call` | `e = eval; e("1 + 1")` |
| `test_rejects_alias_to_exec_call` | `x = exec; x("pass")` |
| `test_rejects_alias_to_compile_call` | `c = compile; c(...)` |
| `test_rejects_alias_to_import_call` | `imp = __import__; m = imp("os")` |
| `test_rejects_alias_chain_to_import_call` | `a = __import__; b = a; m = b("os")` |
| `test_rejects_builtins_name_reference` | `b = __builtins__` |
| `test_rejects_dunder_name_reference` | `x = __import__` |
| `test_rejects_alias_import_then_attribute_call` | `imp = __import__; os_mod = imp("os"); os_mod.system("id")` |
| `test_baseline_detector_still_valid_after_alias_hardening` | `core/detector.py` 正テスト |

## なぜこれが alias bypass クラスを閉鎖するか

従来の `check_forbidden_calls` は `ast.Call.func` が `ast.Name` かつ `id in FORBIDDEN_BUILTINS` の場合のみ違反を検出した。これは直接呼び出し（`eval(x)`）は捕捉するが、右辺に forbidden name が現れる代入（`f = eval`）は捕捉しない。

新しい `check_forbidden_name_references` は **呼び出し位置にあるかどうかに関わらず**、コード中に forbidden name が `ast.Name` として出現した時点で違反とする。これにより:

- `f = open` → `open` が `ast.Name` として出現 → 即座に違反
- `a = __import__; b = a; b("os")` → `__import__` が `ast.Name` → 即座に違反
- `b = __builtins__` → dunder name pattern → 即座に違反

エイリアス呼び出し先（`f(...)` や `b("os")`）自体は forbidden name ではないが、その参照元（`open`, `__import__`）が必ず拒否されるため、alias chain 全体が拒否される。

## 残存リスク

| リスク | 評価 |
|---|---|
| タプル/リストアンパックによる alias（`f, g = open, eval`） | `open` / `eval` が `ast.Name` として出現するため拒否される ✅ |
| `getattr(__builtins__, "eval")` パターン | `__builtins__` が dunder Name として拒否される ✅ |
| 辞書ルックアップ経由 `d = {"x": open}; d["x"](...)` | `open` が `ast.Name` として出現するため拒否される ✅ |
| 完全に外部から tainted value を渡すパターン（runtime injection） | AST 静的解析では捕捉不能。これは sandboxing の責務であり policy の責務外 |
| 既存テストの false positive | 0 件（337 テスト全通過） |

## 後検証結果

```
python3 -m pytest tests/test_ast_policy.py -q
→ 100 passed in 0.18s

python3 -m pytest tests/test_mutation_boundaries.py tests/test_apply_mutation.py -q
→ 120 passed in 0.61s

python3 scripts/validate_mutation.py --candidate core/detector.py --json
→ {"valid": true, "violations": []}
```

## Security Invariants Preserved

- Single policy source: `core/policy.py` のみに policy ロジックを追加。`scripts/validate_mutation.py` は変更なし ✅
- Mutation marker checks preserved: `check_mutation_markers` に変更なし ✅
- Import restrictions preserved: `check_imports` に変更なし ✅
- Dunder attribute restrictions preserved: `check_dunder_access` に変更なし ✅
- Runtime allocation checks preserved: `check_runtime_allocation_risks` に変更なし ✅
- No generated code execution: テストは候補ファイルを作成して拒否判定するのみ。実行しない ✅
- No paid API call: なし ✅
- No ledger edit: `data/api_usage_ledger.json` 変更なし ✅
- No workflow dispatch: なし ✅

## 残存事項・注意点

- `check_forbidden_name_references` は `check_forbidden_calls` と一部重複する（直接呼び出しは両方が検出）。重複は fail-closed の観点から許容。
- Runtime injection パターン（外部から callable を注入するケース）は AST 静的解析では捕捉できない。これは既知の制限であり、sandbox / 隔離実行の責務。
