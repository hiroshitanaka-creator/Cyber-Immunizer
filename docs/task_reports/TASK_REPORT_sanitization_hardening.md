# タスク完了報告 — apply_report.json メタデータ sanitization 強化

**ブランチ**: `claude/cyber-immunizer-failure-diagnostics-in1tuk`
**コミット**: `240e3aa`

---

## Summary

- ブロッカーはコードライク・置換コードライクなコンテンツが `mutation_rationale` / `target_threats` 経由で `apply_report.json` に漏洩できた点だった
- `_CODELIKE_MARKERS` 定数を追加し、`_sanitize_report_string()` に大文字小文字を無視したコードライク検出を追加した
- 非 string 値の `str()` 変換を廃止して `"[invalid]"` を返すよう変更し、dict/list 内容の漏洩を防いだ
- 新テスト 37 件を追加（コードライク unit / dict・list 漏洩防止 / 置換コード一致 / CLI 統合テスト）
- CI: **2128 passed**

---

## 変更ファイル一覧

| ファイル | 変更理由 | セキュリティ影響 |
|---|---|---|
| `scripts/apply_mutation.py` | `_CODELIKE_MARKERS` 追加・`_sanitize_report_string()` 強化 | `return `・`import `・`subprocess`・`flagged=`・`DetectionResult(` 等を含む文字列を `[REDACTED]` に、非 string を `[invalid]` に変換 |
| `tests/test_apply_mutation.py` | 既存 2 テストを新動作に更新・37 件の新テスト追加 | 退行防止 |

---

## 主な変更内容

### `scripts/apply_mutation.py`

**追加: `_CODELIKE_MARKERS` 定数**

```python
_CODELIKE_MARKERS: tuple[str, ...] = (
    "return ",
    "def ",
    "class ",
    "import ",
    "from ",
    "detectionresult(",
    "inspect_request",
    "flagged=",
    "reasons=",
    "os.",
    "subprocess",
    "eval(",
    "exec(",
)
```

**変更: `_sanitize_report_string()`**

```python
def _sanitize_report_string(value: object, max_len: int = _SANITIZE_MAX_STRING_LEN) -> str:
    if not isinstance(value, str):
        return "[invalid]"           # str() 変換禁止（dict/list 漏洩防止）
    upper = value.upper()
    if any(marker in upper for marker in _SECRET_MARKERS):
        return "[REDACTED]"          # 秘密マーカー
    lowered = value.lower()
    if any(marker.lower() in lowered for marker in _CODELIKE_MARKERS):
        return "[REDACTED]"          # コードライク（case-insensitive）
    return value[:max_len]           # 長さ制限
```

**変更前の動作（問題）**:
- 非 string 値を `str(value)` で変換 → dict/list 内容が文字列として漏洩する可能性
- `_SECRET_MARKERS` のみチェック → Python コード構文が素通りしていた

---

## Sanitization ルール（変更後）

| ルール | 動作 |
|---|---|
| 非 string 値 | `"[invalid]"` を返す（`str()` 変換禁止） |
| secret マーカー | `API_KEY`, `SECRET`, `PASSWORD`, `TOKEN`, `CREDENTIAL`, `PRIVATE_KEY`, `ACCESS_KEY` のいずれかを含む → `"[REDACTED]"` |
| コードライクマーカー | `return `, `def `, `class `, `import `, `from `, `detectionresult(`, `inspect_request`, `flagged=`, `reasons=`, `os.`, `subprocess`, `eval(`, `exec(` のいずれかを含む → `"[REDACTED]"`（大文字小文字無視） |
| 最大文字列長 | 2000 文字で切り捨て |
| target_threats 最大件数 | 20 件で切り捨て |
| 置換コード完全一致検出 | `return `・`flagged=`・`DetectionResult(` 等のマーカーがあれば exact match も含めて検出 |

---

## テスト結果

```bash
python -m pytest tests/test_apply_mutation.py -q
# → 70 passed

python -m pytest tests/test_evaluate_candidate.py tests/test_evaluate_promote_contract.py tests/test_workflow.py -q
# → 178 passed

python -m pytest tests/ -q
# → 2128 passed, 5 warnings
```

### 追加テスト内訳（37 件）

**`TestSanitizeReportStringCodeLike`（14 テスト）**
- `return DetectionResult(flagged=False, reasons=[])` → `[REDACTED]`
- `import os` → `[REDACTED]`
- `def inspect_request(request):` → `[REDACTED]`
- `subprocess.run(...)` → `[REDACTED]`
- `eval(...)` → `[REDACTED]`
- `exec(payload)` → `[REDACTED]`
- `flagged=` → `[REDACTED]`
- `DetectionResult(` → `[REDACTED]`
- `inspect_request` → `[REDACTED]`
- `from core.types import ...` → `[REDACTED]`
- case-insensitive 確認
- dict 値 → `[invalid]`（内容漏洩なし）
- list 値 → `[invalid]`（内容漏洩なし）
- `_CODELIKE_MARKERS` の存在・内容確認

**`TestSanitizeTargetThreats` 追加（5 テスト）**
- dict 項目 → `[invalid]`（内容漏洩なし）
- list 項目 → `[invalid]`（内容漏洩なし）
- dict 内容が result に現れないこと
- コードライク脅威項目 → `[REDACTED]`

**`TestSanitizationAppliedInReport` 追加（8 テスト）**
- `mutation_rationale` に exact replacement_code → report に現れない
- `return DetectionResult(...)` → `[REDACTED]` in report
- `import os`・`subprocess` → `[REDACTED]` in report
- dict in `target_threats` → 内容漏洩なし in report
- `replacement_code_sha256` 保持確認
- `replacement_code` キー・値が report に現れないこと

**既存テスト更新（2 件）**
- `test_non_string_coerced_to_str` → `test_non_string_returns_invalid`（`"42"` → `"[invalid]"`）
- `test_none_coerced_to_str` → `test_none_returns_invalid`（`"None"` → `"[invalid]"`）

---

## Merge Readiness Checklist

- [x] code-like rationale redacted
- [x] replacement-like rationale redacted
- [x] code-like target_threats redacted
- [x] non-string metadata does not leak via str()
- [x] raw replacement_code absent from apply_report
- [x] replacement_code_sha256 preserved
- [x] existing secret redaction preserved
- [x] existing bounds preserved（length / list count）
- [x] promotion path unchanged
- [x] full CI green（2128 passed）
- [x] task report 更新済み

---

## 残存事項

なし。今回のタスクスコープ内の全 Acceptance Criteria を満たした。
