# タスク完了報告 — PR #103 Failure Diagnostics Hardening

**ブランチ**: `claude/cyber-immunizer-failure-diagnostics-in1tuk`
**コミット**: `15da5e8`

---

## 概要

PR #103（Apply/Evaluate 失敗診断 artifact 追加）のブロッキング問題 4 件＋推奨 1 件をすべて解決した。
fail-closed 安全性・adoption gate・promotion 条件・budget/ledger 制約はすべて維持。

---

## 変更ファイル一覧

| ファイル | 種別 | 変更理由 |
|---|---|---|
| `scripts/evaluate_candidate.py` | 変更 | `_write_report()` に `fitness_report` 正規キー追加・atomic write 化 |
| `scripts/promote_candidate.py` | 変更 | `candidate_hash` 検索・`fitness` 取得に `metrics` フォールバック追加 |
| `scripts/apply_mutation.py` | 変更 | `_sanitize_report_string()` / `_sanitize_target_threats()` 追加・`main()` で適用 |
| `data/project_state.json` | 変更 | `gemini_3_flash_preview_success_records`: 6 → 7（ledger 実数と一致） |
| `tests/test_project_state_sync.py` | 変更 | `assert actual == 6` → `assert actual == 7` |
| `tests/test_evaluate_promote_contract.py` | 新規 | evaluate → promote 契約の統合回帰テスト（9 テスト） |
| `tests/test_apply_mutation.py` | 変更 | sanitization ユニットテスト 15 件追加 |

---

## 主な変更内容

### Task 1 — fitness_report 後方互換性の復元

**`scripts/evaluate_candidate.py::_write_report()`**

- `"fitness_report": result.get("fitness_report")` キーを payload に追加（promote_candidate.py が読む正規キー）
- `"metrics"` は CI ツーリング向けエイリアスとして残す
- atomic write 化（`NamedTemporaryFile` + `fsync` + `os.replace`）。OSError は raise（fail-closed）

**`scripts/promote_candidate.py`**

```python
# candidate_hash 検索（Step 3）
inner = report.get("fitness_report") or report.get("metrics") or {}

# fitness schema 検証（Step 4）
fitness = report.get("fitness_report") or report.get("metrics") or report
```

---

### Task 2 — evaluate → promote 統合回帰テスト

**新規ファイル**: `tests/test_evaluate_promote_contract.py`（9 テスト）

| テストクラス | 内容 |
|---|---|
| `TestFitnessReportKeyContract` | `fitness_report` キーで promote 成功・`metrics` のみでフォールバック成功・両キー共存時 `fitness_report` 優先・どちらも無いときスキーマエラー |
| `TestPromoteGatesUnchanged` | `passed_adoption_gate=false` 拒否・`candidate_hash` 欠損拒否・ハッシュ不一致拒否・policy 再バリデーション実行確認・metrics フォールバックでも gate 維持 |

---

### Task 3 — SSOT 不整合の修正

| ファイル | 変更 |
|---|---|
| `data/project_state.json` | `"gemini_3_flash_preview_success_records": 6` → `7` |
| `tests/test_project_state_sync.py` | `assert actual == 6` → `assert actual == 7` |

以前から失敗していた `test_project_state_matches_ledger_success_count` が通過するようになった。

---

### Task 4 — LLM 由来メタデータのサニタイズ

**`scripts/apply_mutation.py`** に追加:

```python
_SECRET_MARKERS = (
    "API_KEY", "SECRET", "PASSWORD", "TOKEN",
    "CREDENTIAL", "PRIVATE_KEY", "ACCESS_KEY",
)
_SANITIZE_MAX_STRING_LEN = 2000
_SANITIZE_MAX_THREATS = 20

def _sanitize_report_string(value, max_len=_SANITIZE_MAX_STRING_LEN) -> str:
    """秘密マーカーを含む場合は [REDACTED]、超長文字列は切り捨て"""

def _sanitize_target_threats(threats) -> list[str]:
    """リストでない場合は []、各要素を sanitize、最大件数を制限"""
```

`main()` の report_payload 構築前に適用:

```python
san_rationale = _sanitize_report_string(result.get("mutation_rationale") or "")
san_threats   = _sanitize_target_threats(result.get("target_threats") or [])
```

**`tests/test_apply_mutation.py`** に 15 テスト追加:
- `TestSanitizeReportString` — 8 テスト（クリーン文字列・切り捨て・型変換・秘密マーカー・大文字小文字・カスタム長）
- `TestSanitizeTargetThreats` — 5 テスト
- `TestSanitizationAppliedInReport` — 5 テスト（report ファイル上で検証）

---

### Task 5（推奨）— evaluate report の atomic write / fail-closed

`_write_report()` の `report_path.write_text(...)` を:
```python
with tempfile.NamedTemporaryFile(...) as tmp:
    json.dump(payload, tmp, indent=2)
    tmp.flush()
    os.fsync(tmp.fileno())
os.replace(tmp_path, report_path)
```
に置換。OSError は catch せず raise（呼び出し元に伝播、CI は非ゼロ終了）。

---

## テスト結果

```bash
# 対象テストのみ
python -m pytest tests/test_apply_mutation.py tests/test_evaluate_candidate.py \
    tests/test_evaluate_promote_contract.py tests/test_workflow.py \
    tests/test_project_state_sync.py -q
# → 246 passed

# フルスイート
python -m pytest tests/ -q
# → 2104 passed, 5 warnings
```

（`test_project_state_sync.py` の失敗は本変更で解消済み）

---

## セキュリティ確認

| 項目 | 状態 |
|---|---|
| fail-closed 維持 | `_write_report()` atomic write 失敗は raise（非ゼロ終了） |
| secret 漏洩防止 | `_safe_env()` 変更なし。sanitization で `API_KEY` 等を `[REDACTED]` に置換 |
| replacement_code 全文除外 | `replacement_code_sha256`（SHA-256 のみ）。本文は含めない |
| invalid candidate 実行禁止 | candidate-not-found ガード・AST validation は変更なし |
| promotion gate 不変 | `passed_adoption_gate` / `promote_approved` / `workflow_dispatch` 条件はすべて維持 |
| metrics フォールバックは gate を緩めない | `metrics` 経由でも全 gate（hash 検証・schema・adoption gate・policy 再バリデーション）を通過必須 |

---

## 残存事項

なし（4 blocking tasks + 1 recommended task をすべて解決）。
