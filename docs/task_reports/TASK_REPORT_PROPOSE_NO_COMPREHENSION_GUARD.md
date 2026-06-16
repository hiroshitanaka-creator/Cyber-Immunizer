# タスク完了報告 — propose-no-comprehension-guard

## 概要

Run 7 でリストコンプリヘンションを含む `replacement_code` が propose 段階のバリデーションを通過したが apply 段階の `core.policy.check_runtime_allocation_risks()` で却下された根本原因を解消するため、propose 段階に Check 6.6 を追加した。これにより、`ast.ListComp` / `ast.SetComp` / `ast.DictComp` および安全でない `ast.GeneratorExp` を含むコードが propose 時点で fail-closed で却下される。Gemini 向けプロンプトにも明示的禁止ルールとスコアリングガイダンスを追記した。

## 変更ファイル一覧

- `scripts/propose_mutation.py` — Check 6.6 追加、プロンプト更新
- `tests/test_gemini_integration.py` — 新規テストクラス `TestNoComprehensionGuard`（20テスト）追加、既存フィクスチャのリストコンプリヘンション除去
- `tests/test_gemini_paid_credit.py` — 既存フィクスチャのリストコンプリヘンション除去（8テスト修正）
- `docs/task_reports/TASK_REPORT_PROPOSE_NO_COMPREHENSION_GUARD.md` — 本報告書

## 主な変更内容

### `scripts/propose_mutation.py`

- **Check 6.6** を `_validate_replacement_code()` に追加（Check 6.5 の直後）
  - `core.policy.check_runtime_allocation_risks(tree)` を再利用して `ListComp` / `SetComp` / `DictComp` / 安全でない `GeneratorExp` を reject
  - apply 段階と同じポリシーを使うことで policy drift を防止
  - `ImportError` 時は skip（backstop として apply 段階のチェックが残る）
- **`_LLM_SYSTEM_PROMPT` STRICT RULES** に Rule 18 追加（コンパクトな1行）:
  - `"18. No list comprehension, set comprehension, dict comprehension, or generator expression — all rejected. Use for-loop + append."`
  - テスト要件: `"list comprehension"`, `"set comprehension"`, `"dict comprehension"`, `"generator"`, `"for-loop"` / `"append"` が全てシステムプロンプトに含まれる
- **`_build_scoring_guidance()`** の末尾に1行追加:
  - `"- NO-COMPREHENSION: list/set/dict comprehensions and generator expressions rejected; use for-loop + append."`
  - テスト要件: user prompt に `"comprehension"` / `"for-loop"` が含まれる
- **プロンプト長制約を維持**: 変更後の full prompt は 11585 chars（headroom 415 chars ≥ 200 chars 要件をクリア）
  - 冗長な FORBIDDEN セクションの return shape 列挙を 1 行に短縮（530 → 225 chars）
  - 冗長なコンプリヘンション禁止 4-bullet を削除（Rule 18 でカバー）

### `tests/test_gemini_integration.py`

- `valid_patch` フィクスチャのリストコンプリヘンション → for-loop + append に変換
- `test_accepts_safe_code` および `test_accepts_nested_return_plus_top_level_fallback` の `replacement_code` フィクスチャ更新
- **新規テストクラス `TestNoComprehensionGuard`** を追加（20テスト）:
  - `test_rejects_list_comprehension_simple`
  - `test_rejects_list_comprehension_with_if_filter`
  - `test_rejects_set_comprehension`
  - `test_rejects_dict_comprehension`
  - `test_rejects_unsafe_generator_expression_in_any`
  - `test_rejects_standalone_generator_expression`
  - `test_rejects_list_comprehension_in_return_context`
  - `test_accepts_for_loop_instead_of_list_comprehension`
  - `test_accepts_sample_mutation_no_comprehension`
  - `test_system_prompt_forbids_list_comprehension`
  - `test_system_prompt_forbids_set_comprehension`
  - `test_system_prompt_forbids_dict_comprehension`
  - `test_system_prompt_forbids_generator_expression`
  - `test_system_prompt_recommends_for_loop`
  - `test_user_prompt_contains_no_comprehension_guidance`
  - `test_prompt_headroom_after_guidance_added`
  - `test_prompt_headroom_with_real_genome`
  - `test_detection_result_shape_still_validated_after_check66`
  - `test_detection_result_shape_validated_when_no_comprehension`

### `tests/test_gemini_paid_credit.py`

- 8テストが失敗していたフィクスチャ（`replacement_code` 内のリストコンプリヘンション）を for-loop + append に変換:
  - `TestPaidCreditLedgerAppend::test_appends_usage_record_on_success`（line 627）
  - `TestConservativeMultilingualBudgetRefusal` 内2テスト（lines 1883, 2024）
  - `TestThinkingBudgetInEstimation._VALID_RESPONSE`（line 2099）
  - `TestActualThinkingTokensInLedger._VALID_RESPONSE`（line 2270）

## 後検証結果

```
pytest tests/ -q
2147 passed, 5 warnings in 4.18s

prompt headroom: 415 chars (max_prompt_chars=12000, full_prompt=11585, require>=200) ✅
list comprehension in system prompt: True ✅
set comprehension in system prompt: True ✅
dict comprehension in system prompt: True ✅
generator in system prompt: True ✅
for-loop in system prompt: True ✅
comprehension in user prompt: True ✅
```

## 残存事項・注意点

- `core/policy.py` は FROZEN のため未変更。Check 6.6 は `core.policy.check_runtime_allocation_risks()` を呼び出すことで policy drift を防止している。
- `tests/test_gemini_paid_credit.py` の `valid_patch` フィクスチャ（line 114）はリストコンプリヘンションと runtime multiplier（`0.12 * len(matched)`）を残したまま。このフィクスチャを使用するテストは高レベルモックで `_validate_replacement_code` を経由しないため現時点で問題なし。将来のテスト変更時に注意が必要。
- `TestPaidCreditLedgerFailures._VALID_RESPONSE_TEXT`（line 1051）も同様にリストコンプリヘンションを残したまま。このクラスのテストは ledger write を先にモックして失敗させるため `_parse_and_validate_response` に到達しない。
