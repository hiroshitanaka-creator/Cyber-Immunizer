# タスク完了報告 — propose-no-comprehension-guard（監査修正版）

## 概要

Run 7 でリストコンプリヘンションを含む `replacement_code` が propose 段階のバリデーションを通過したが apply 段階の `core.policy.check_runtime_allocation_risks()` で却下された根本原因を解消するため、propose 段階に Check 6.6 を追加した（PR #104 初版）。

その後の監査指摘（P1〜P3）に対応し、以下の修正を実施した:

- **P1**: Check 6.6 の ImportError ハンドリングを fail-closed に変更（skip → reject）
- **P2**: System prompt の Rule 18 文言を短縮・整合（`"all rejected"` → `join()` 例外を LLM に教えない表現へ）
- **P3**: `valid_patch` フィクスチャと `_VALID_RESPONSE_TEXT` の無効なコードを修正

## 変更ファイル一覧

- `scripts/propose_mutation.py` — Check 6.6 ImportError fail-closed 化、Rule 18 文言更新
- `tests/test_gemini_integration.py` — ImportError fail-closed テスト追加、prompt assertion 更新
- `tests/test_gemini_paid_credit.py` — フィクスチャ整理（リストコンプリヘンション除去・runtime multiplier 除去）
- `docs/task_reports/TASK_REPORT_PROPOSE_NO_COMPREHENSION_GUARD.md` — 本報告書

## 主な変更内容

### `scripts/propose_mutation.py`

**PR #104 初版（Check 6.6 本体）:**
- `_validate_replacement_code()` に Check 6.6 を追加（Check 6.5 の直後）
  - `core.policy.check_runtime_allocation_risks(tree)` を再利用して `ListComp` / `SetComp` / `DictComp` / 安全でない `GeneratorExp` を reject
  - apply 段階と同じポリシーを使うことで policy drift を防止
- `_LLM_SYSTEM_PROMPT` STRICT RULES に Rule 18 追加
- `_build_scoring_guidance()` の末尾に NO-COMPREHENSION ガイダンス追加
- 冗長な FORBIDDEN セクションの return shape 列挙を短縮してプロンプト長を予算内に維持

**監査修正 P1（ImportError fail-closed）:**
- `except ImportError: pass` → `except ImportError as exc: return (error message)` に変更
  - error message: `"core.policy unavailable for check 6.6 ({exc.__class__.__name__}) — fail-closed"`
- コメントの「apply-stage backstop に任せる」という記述を削除

**監査修正 P2（Rule 18 文言整合）:**
- 旧: `"18. No list comprehension, set comprehension, dict comprehension, or generator expression — all rejected. Use for-loop + append."`
- 新: `"18. Do not use list/set/dict comprehensions or generator expressions in replacement_code. Use explicit for-loop + append."`
- `"all rejected"` という誤解を招く文言を削除（core.policy は join(generator) を許容するが LLM に例外条件を教えない）

**プロンプト長**: 11578 chars（headroom 422 chars ≥ 200 chars 要件をクリア）

### `tests/test_gemini_integration.py`

**PR #104 初版:**
- 既存フィクスチャのリストコンプリヘンション → for-loop + append に変換
- `TestNoComprehensionGuard` クラス追加（20テスト）

**監査修正 P1 テスト:**
- `test_check66_import_error_fails_closed` を `TestNoComprehensionGuard` に追加
  - 有効な（コンプリヘンションなし）コードで `core.policy` import を monkeypatch で封鎖
  - `_validate_replacement_code()` が空文字でないエラーを返すことを assert
  - エラーに `"core.policy"` / `"check 6.6"` / `"fail-closed"` のいずれかが含まれることを assert

**監査修正 P2 テスト:**
- `test_system_prompt_forbids_list_comprehension`: `"list/set/dict"` を許容する assert に更新
- `test_system_prompt_forbids_set_comprehension`: 同様に `"list/set/dict"` を許容する assert に更新

### `tests/test_gemini_paid_credit.py`

**PR #104 初版:**
- 8テストのフィクスチャのリストコンプリヘンション → for-loop + append に変換

**監査修正 P3（invalid fixture 整理）:**
- `valid_patch` フィクスチャ（line 104）:
  - `[ind for ind in indicators if ind in surface]` → for-loop + append に変換
  - `min(1.0, 0.5 + 0.12 * len(matched))` runtime multiplier → branch-constant `confidence = 0.7 / 0.9` に変換
  - docstring から `(no '__' in code)` の限定表現を削除
- `TestPaidCreditLedgerFailures._VALID_RESPONSE_TEXT`:
  - `[ind for ind in indicators if ind in surface]` → for-loop + append に変換

## 後検証結果

```
pytest tests/test_gemini_integration.py -q  → 307 passed
pytest tests/test_gemini_paid_credit.py -q  → 74 passed
pytest tests/ -q                            → 2148 passed, 5 warnings

python scripts/propose_mutation.py --noop --json         → success: true
python scripts/propose_mutation.py --offline-sample --json → success: true

prompt headroom: 422 chars (max_prompt_chars=12000, full_prompt=11578, require>=200) ✅
```

## 残存事項・注意点

- `core/policy.py` は FROZEN のため未変更。Check 6.6 は `core.policy.check_runtime_allocation_risks()` を呼び出すことで policy drift を防止している。

## Safety Invariants

- No Gemini API call ✅
- No OpenAI API call ✅
- No workflow_dispatch ✅
- No paid-credit run ✅
- No preflight run ✅
- No promotion ✅
- No ledger/genome/detector/workflow changes ✅
- No weakening of core.policy ✅
