# タスク完了報告 — PR #124 AST Alias Bypass Hardening

## 概要

`core/policy.py` に `check_forbidden_name_references()` を追加し、エイリアス経由で禁止 builtin を呼び出す bypass クラスを閉鎖した。`tests/test_ast_policy.py` に `TestAliasAndDunderNameBypassClosure` クラス（**9 件の負テスト + 1 件の正テスト、計 10 件**）を追加した。

PR #124 は最新 main（PR #123 — generation 4 SSOT 修正）へ rebase 済み。state-sync 差分（README / project_state / readiness / tests）は PR 差分から除去し、AST hardening 本体と task reports のみ残した。

- **ブランチ**: `claude/ast-alias-bypass-fix-7957x4`
- **PR**: #124
- **実装コミット SHA**: `eeb717c`（`security(policy): close alias-bypass class via forbidden Name reference check`）
- **Rebase base**: `origin/main`（PR #123 merge 後 — SHA `487d340`）

---

## 最終 PR 差分ファイル一覧（rebase 後）

| ファイル | 変更種別 | 理由 |
|---|---|---|
| `core/policy.py` | 変更 | `check_forbidden_name_references()` 関数追加、`run_full_policy()` に組み込み |
| `tests/test_ast_policy.py` | 変更 | `TestAliasAndDunderNameBypassClosure` クラス（10 テスト: 9 負 + 1 正）追加 |
| `docs/task_reports/TASK_REPORT_ast_alias_bypass_hardening.md` | 新規 | 実装時点での詳細調査記録 |
| `docs/task_reports/TASK_REPORT_PR124.md` | 新規 | 本報告ファイル |

**PR 差分から除外したファイル（最新 main が generation 4 SSOT を保持するため）**:
`README.md` / `data/project_state.json` / `docs/PROJECT_STATE.md` / `scripts/pre_paid_credit_readiness.py` / `tests/test_project_state_sync.py` / `tests/test_update_readme.py`

---

## 主な変更内容

### core/policy.py

新関数 `check_forbidden_name_references(tree)` を追加（`check_dunder_access` の直後に定義）:

- `ast.walk` で全 `ast.Name` ノードを走査
- `id in FORBIDDEN_BUILTINS` → `"forbidden name reference: {name!r}"` 違反
- `id.startswith("__") and id.endswith("__") and len(id) >= 5` → `"forbidden dunder name reference: {name!r}"` 違反

`run_full_policy()` 内のステップ 6b として挿入（`check_forbidden_calls` の直後、`check_dunder_access` の前）:

```python
# 6b. Forbidden name references — alias-bypass closure
violations.extend(check_forbidden_name_references(tree))
```

**なぜこれが alias bypass クラスを閉鎖するか**:
従来の `check_forbidden_calls` は `ast.Call.func` が `ast.Name` かつ `id in FORBIDDEN_BUILTINS` の場合のみ違反を検出した（直接呼び出しのみ）。新しい `check_forbidden_name_references` は呼び出し位置にあるかどうかに関わらず、コード中に forbidden name が `ast.Name` として出現した時点で違反とするため:

- `f = open` → `open` が `ast.Name` として出現 → 即座に違反
- `a = __import__; b = a; b("os")` → `__import__` が `ast.Name` → 即座に違反
- `b = __builtins__` → dunder name pattern → 即座に違反

### tests/test_ast_policy.py

`TestAliasAndDunderNameBypassClosure` クラスを追加（9 件の負テスト + 1 件の正テスト）:

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
| `test_baseline_detector_still_valid_after_alias_hardening` | `core/detector.py` 正テスト（リグレッション確認） |

---

## ローカル後検証結果（rebase 後）

```
python3 -m pytest tests/test_ast_policy.py -q
→ 100 passed in 0.51s

python3 -m pytest tests/test_mutation_boundaries.py -q
→ 40 passed in 0.37s

python3 scripts/validate_mutation.py --candidate core/detector.py --json
→ {"valid": true, "violations": []}

python3 -m pytest -q
→ 2374 passed in 9.42s（5 warnings）
```

---

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
- generation 4 SSOT preserved: state-sync 差分を PR から除外; main の generation 4 修正（PR #123）を採用 ✅

---

## 残存事項・注意点

- `check_forbidden_name_references` は `check_forbidden_calls` と一部重複する（直接呼び出しは両方が検出）。重複は fail-closed の観点から許容。
- Runtime injection パターン（外部から callable を注入するケース）は AST 静的解析では捕捉できない。これは既知の制限であり sandbox / 隔離実行の責務。
