# PR #65 Minimal Completion Report

**Branch**: `claude/pr-65-minimal-completion-Qf2I9`  
**Date**: 2026-06-04  
**Commit**: `32e789a`

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `scripts/propose_mutation.py` | `_LLM_SYSTEM_PROMPT` に rule 16（インデント契約）を追加 (65-MIN-01) |
| `docs/API_ACTIVATION_RUNBOOK.md` | Syntax Validation Guard のラッパー記述を実装に合わせて修正 (65-MIN-02) |
| `tests/test_gemini_integration.py` | `TestReplacementCodeSyntaxValidation` に 2 テスト追加 (CR-65-MIN-01 evidence) |
| `tests/test_gemini_paid_credit.py` | `TestInvalidResponseNoPatchArtifact` (2 テスト) 追加 (CR-65-MIN-03) |
| `tests/test_api_activation_docs.py` | `TestApiActivationRunbookContent` に 2 テスト追加 (CR-65-MIN-02 regression guard) |
| `docs/audit_gate/CHANGELOG.md` | PR #65 のレッスンエントリを追加 (65-MIN-05) |

---

## 実施した変更の詳細

### 65-MIN-01 — `_LLM_SYSTEM_PROMPT` インデント表現の修正

`scripts/propose_mutation.py` の `_LLM_SYSTEM_PROMPT` に rule 16 を追加:

```
16. Use correct Python indentation. replacement_code is inserted into
    the body of inspect_request() — all lines must be indented.
    Top-level statements (including a top-level return DetectionResult(...))
    must start at exactly 4 spaces. Nested statements inside if/for/while/try
    blocks follow normal 4-space block depth: 8, 12, 16 spaces, etc.
    A return DetectionResult(...) inside a conditional block must be at
    8 or more spaces, not 4. Never use tabs; use spaces only.
```

**修正の理由**: `if`/`for`/`while` ブロック内の nested return は 8/12/16 スペースが正しい Python。
「すべての `return DetectionResult(...)` が 4 スペース」という表現は論理的に誤りであり、
valid な nested return を model が誤って生成しないよう、top-level と nested を明示的に区別する必要があった。

---

### 65-MIN-02 — ランブック ラッパー記述の同期

`docs/API_ACTIVATION_RUNBOOK.md` の Syntax Validation Guard セクションを修正:

**変更前:**
```
- `def _candidate_body():\n...` にラップして parse
```

**変更後 (実装に合わせた正確な形):**
```
- 以下のラッパーに splice して ast.parse() を実行:

  def _candidate_body(request):
      # === MUTATION_START ===
  {replacement_code（as-is、インデント維持）}
  # === MUTATION_END ===

  - ラッパーの先頭行は `def _candidate_body(request):` — `request` パラメータあり
  - top-level 文は 4 スペース、nested 文は 8/12/16 スペース等の block depth に従う
```

> **不一致の注記**: CR-65-MIN-02 の「After」記述に `_mutation_anchor = None` が含まれていたが、
> 実際の `_validate_replacement_code` の実装にはこの変数は存在しない。
> ランブックは実際のコードに合わせて更新した（`_mutation_anchor = None` は含めていない）。
> もしこれが H-1/H-2 の将来設計要素であれば、PR #66+ のスコープに属する。

---

### 65-MIN-04 / CR-65-MIN-03 — no-patch artifact テスト

`tests/test_gemini_paid_credit.py` に `TestInvalidResponseNoPatchArtifact` クラスを追加:

| テスト名 | 何を証明するか |
|---|---|
| `test_forbidden_token_response_no_patch_file` | `_propose_via_gemini_paid_credit` が `(None, error)` を返した場合、`mutation_patch.json` がディスクに作成されない |
| `test_invalid_replacement_code_via_call_boundary_no_patch` | `_call_gemini_api` が `import os` を含む raw JSON を返した場合、`_parse_and_validate_response` が reject し、`patch_path.exists()` が False |

両テストとも monkeypatch のみ使用。Gemini API 呼び出しなし。

---

### 追加テスト一覧

| テスト | ファイル | 対応 CR |
|---|---|---|
| `test_accepts_nested_return_at_8_spaces` | `test_gemini_integration.py` | CR-65-MIN-01 |
| `test_system_prompt_indentation_wording_distinguishes_nested_returns` | `test_gemini_integration.py` | CR-65-MIN-01 |
| `test_forbidden_token_response_no_patch_file` | `test_gemini_paid_credit.py` | CR-65-MIN-03 |
| `test_invalid_replacement_code_via_call_boundary_no_patch` | `test_gemini_paid_credit.py` | CR-65-MIN-03 |
| `test_runbook_syntax_validation_wrapper_has_request_param` | `test_api_activation_docs.py` | CR-65-MIN-02 |
| `test_runbook_indentation_contract_mentions_nested_returns` | `test_api_activation_docs.py` | CR-65-MIN-01/02 |

---

## テスト実行結果

```
tests/test_gemini_integration.py      101 passed  (変更前: 99)
tests/test_gemini_paid_credit.py       74 passed  (変更前: 72)
tests/test_api_activation_docs.py      21 passed  (変更前: 19)
tests/test_ai_docs_navigation.py       21 passed  (変更なし)
------------------------------------------------------------
Full suite:                          1698 passed  in 4.02s  — zero failures
```

---

## PR ボディ差し替えドラフト

> 65-MIN-03 per: このテキストを PR #65 のボディとしてコピー&ペーストしてください。
> `gh pr edit` による PR ボディ直接編集は行っていません（明示的な指示がないため）。

---

```markdown
## Summary

Minimal completion PR for PR #65 (`claude/replacement-code-indentation-lyscz`).
Fixes a logical contradiction in the `_LLM_SYSTEM_PROMPT` indentation contract,
synchronizes the runbook wrapper description with the actual implementation, and
adds evidence tests proving invalid `replacement_code` does not create
`mutation_patch.json`. H-1/H-2/H-3 and design-boundary tasks are deferred to PR #66+.

## Minimal PR #65 Scope

| ID | Description | Status |
|---|---|---|
| 65-MIN-01 | Fix `_LLM_SYSTEM_PROMPT` indentation wording: top-level returns at 4 spaces, nested returns at 8/12/16 spaces | ✅ Done |
| 65-MIN-02 | Sync `docs/API_ACTIVATION_RUNBOOK.md` Syntax Validation Guard: `def _candidate_body(request):` + indentation contract | ✅ Done |
| 65-MIN-03 | Draft updated PR body (this document) | ✅ Done |
| 65-MIN-04 | Add evidence tests: invalid response → no `mutation_patch.json` (monkeypatch only) | ✅ Done |
| 65-MIN-05 | Document deferred follow-up scope in PR body and `docs/audit_gate/CHANGELOG.md` | ✅ Done |

## Changed Files

| File | Purpose |
|---|---|
| `scripts/propose_mutation.py` | Added rule 16 to `_LLM_SYSTEM_PROMPT` about indentation contract |
| `docs/API_ACTIVATION_RUNBOOK.md` | Fixed Syntax Validation Guard wrapper description + indentation contract wording |
| `tests/test_gemini_integration.py` | Added nested-return-at-8-spaces acceptance test + system prompt wording assertion |
| `tests/test_gemini_paid_credit.py` | Added `TestInvalidResponseNoPatchArtifact` (two tests) |
| `tests/test_api_activation_docs.py` | Added `_candidate_body(request)` regression guard + nested-indentation assertion |
| `docs/audit_gate/CHANGELOG.md` | Added PR #65 lesson entry |

## Validator Check Order (unchanged)

`_validate_replacement_code` check order (not changed in this PR):
1. Mutation marker rejection (`# === MUTATION_START/END ===` in code)
2. Forbidden token rejection (`import`, `eval`, `exec`, `open(`, `subprocess`, `socket`, `os.`, `pathlib`, `shutil`, `urllib`, `requests`, `__`)
3. AST parse-only validation (`def _candidate_body(request):\n    # === MUTATION_START ===\n{code}\n# === MUTATION_END ===`)
   - `SyntaxError` / `IndentationError` → rejected
   - `UnicodeError` → rejected fail-closed (error string does not echo code)

## Test Coverage

### New tests (this PR)

| Test | File | Proves |
|---|---|---|
| `test_accepts_nested_return_at_8_spaces` | `test_gemini_integration.py` | Nested return at 8 spaces accepted by validator |
| `test_system_prompt_indentation_wording_distinguishes_nested_returns` | `test_gemini_integration.py` | `_LLM_SYSTEM_PROMPT` contains "nested" and block depth description |
| `test_forbidden_token_response_no_patch_file` | `test_gemini_paid_credit.py` | `mutation_patch.json` not written when validation returns error |
| `test_invalid_replacement_code_via_call_boundary_no_patch` | `test_gemini_paid_credit.py` | Forbidden token from `_call_gemini_api` → no patch file |
| `test_runbook_syntax_validation_wrapper_has_request_param` | `test_api_activation_docs.py` | Runbook contains `_candidate_body(request)` |
| `test_runbook_indentation_contract_mentions_nested_returns` | `test_api_activation_docs.py` | Runbook describes nested indentation |

## Deferred Follow-up PR #66+ Scope

| ID | Description | Note |
|---|---|---|
| H-1 | Require at least one `return DetectionResult(...)` in `replacement_code` body | Semantic body validation |
| H-2 | CFG reachability — every path returns `DetectionResult(...)` | Control-flow graph analysis |
| H-3 | Static argument validation for `DetectionResult(...)` (count + keyword names) | Excludes type/value-range (those are X-007) |
| M-1 | Reject non-multiple-of-4 indentation (e.g. 3 or 5 spaces) | Medium-priority |
| M-2 | Explicit tab character rejection | Medium-priority |
| X-002 | Function-definition fence (`def ` inside replacement_code) | Project Owner-overridable recommendation |
| X-006 | Additional semantic body checks | TBD design |
| X-007 | Static type/value-range checks on `DetectionResult(...)` args | Excludes H-3 scope |

## Documentation / History Gate

| Category | Updated? | Reason |
|---|---|---|
| `README.md` | No | No new documents, no changed project structure. Existing link present. |
| `docs/**` (other than runbook) | No | Only `API_ACTIVATION_RUNBOOK.md` required update. |
| `docs/audit_gate/CHANGELOG.md` | Yes | 3 protocol lessons added for PR #65. |
| `scripts/update_readme.py` | No | README unchanged; generator consistency not required. |
| `data/evolution_history.json` | No | No runtime mutations made. |
| `data/api_usage_ledger.json` | No | No paid-credit run. Frozen (`data/**`). |

## Test Results

```
tests/test_gemini_integration.py      101 passed
tests/test_gemini_paid_credit.py       74 passed
tests/test_api_activation_docs.py      21 passed
tests/test_ai_docs_navigation.py       21 passed
Full suite:                          1698 passed  — zero failures
```

## Safety Confirmation

- ✅ No Gemini API call was made
- ✅ No paid-credit run was made
- ✅ No `workflow_dispatch` was triggered
- ✅ No file under `.github/**`, `core/**`, or `data/**` was modified
- ✅ No new dependencies added
- ✅ No public API signatures changed
- ✅ Validator logic not changed (text-only prompt wording + test additions only)
- ✅ H-1/H-2/H-3 not implemented
```

---

## ドキュメント / 履歴ゲート結果

| カテゴリ | 更新要否 | 理由 |
|---|---|---|
| `README.md` | **不要** | 新規ドキュメントなし・プロジェクト構造変更なし。`API_ACTIVATION_RUNBOOK.md` へのリンクは既存で `test_readme_links_to_api_activation_runbook` も通過 |
| `docs/**`（ランブック以外） | **不要** | CR-65-MIN-02 に必要な更新は `API_ACTIVATION_RUNBOOK.md` のみ |
| `docs/audit_gate/CHANGELOG.md` | **要・実施済み** | PR #65 のプロトコルレッスン 3 件を記録（prompt wording・runbook wrapper・artifact boundary） |
| `scripts/update_readme.py` | **不要** | README を変更しないため、ジェネレータ整合性チェック不要 |
| `data/evolution_history.json` | **不要** | 実行時のミューテーション変更なし |
| `data/api_usage_ledger.json` | **不要** | paid-credit run なし。`data/**` は frozen |

---

## 注記・不一致点

1. **`_mutation_anchor = None` の不在**: CR-65-MIN-02 の「After」記述に `_mutation_anchor = None` が含まれていたが、実際の `_validate_replacement_code` 実装にこの変数は存在しない。ランブックは実装に合わせて更新した。この変数が将来の H-1/H-2 設計要素であれば PR #66+ のスコープ。

2. **`test_ai_docs_navigation.py` の更新不要**: 新規ファイルを `docs/audit_gate/` に追加していない（`CHANGELOG.md` はすでに存在）。navigation テストはすべて通過。

3. **H-1/H-2/H-3 未実装の確認**: Validator logic は一切変更していない。Rule 16 の追加は `_LLM_SYSTEM_PROMPT` のテキスト変更のみ。

---

*このレポートは PR #65 minimal completion の最終報告書です。*
