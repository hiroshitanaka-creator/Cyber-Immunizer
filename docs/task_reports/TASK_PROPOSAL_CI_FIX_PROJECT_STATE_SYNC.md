# 作業提案書 — CI 修正: project_state / ledger 不一致解消

**Date:** 2026-06-12
**Branch:** `claude/s4-artifact-analysis-7571321383-l8kedi`
**PR:** #91

---

## 現状

PR #91 の CI が以下の 1 テストで失敗中：

```
FAILED tests/test_project_state_sync.py::test_project_state_matches_ledger_success_count
AssertionError: project_state declares 3 primary-model success records but ledger has 4
assert 4 == 3
```

---

## 根本原因

`tests/test_project_state_sync.py` は 2 つのアサーションを持つ：

```python
# アサーション①: project_state と ledger の数値が一致すること
assert actual == declared   # 現在: 4 != 3 → FAIL

# アサーション②: ledger の成功件数がちょうど 3 件であること（ハードコード）
assert actual == 3          # 現在: 4 != 3 → FAIL
```

`data/api_usage_ledger.json` に存在する `gemini-3-flash-preview` × `gemini_paid_credit` × `success=True` のエントリ：

| # | timestamp | model |
|---|---|---|
| 1 | 2026-06-03 | gemini-3-flash-preview |
| 2 | 2026-06-04 | gemini-3-flash-preview |
| 3 | 2026-06-04 | gemini-3-flash-preview |
| 4 | 2026-06-11 | gemini-3-flash-preview |（S4 run #47 — 新規追加分）

`data/project_state.json` は `"gemini_3_flash_preview_success_records": 3` のまま更新されていない。

---

## 必要な変更

### 変更① `data/project_state.json`

```json
// 変更前
"gemini_3_flash_preview_success_records": 3,

// 変更後
"gemini_3_flash_preview_success_records": 4,
```

### 変更② `tests/test_project_state_sync.py`

```python
# 変更前
assert actual == 3, "ledger must contain exactly 3 primary-model paid-credit success records"

# 変更後
assert actual == 4, "ledger must contain exactly 4 primary-model paid-credit success records"
```

---

## リスク評価

| 項目 | 評価 |
|---|---|
| runtime コード変更 | なし |
| validator 変更 | なし |
| policy 変更 | なし |
| detector 変更 | なし |
| workflow 変更 | なし |
| 昇格・promote | なし |
| Gemini API 呼び出し | なし |
| SSOT 変更 | あり（`data/project_state.json` の数値を実態に合わせる） |
| テスト変更 | あり（ハードコード値を実態に合わせる） |

**本質**: どちらの変更も「事実を記録している値を実態に合わせる」だけで、ロジックや振る舞いの変更ではない。

---

## 変更後の期待テスト結果

```
pytest tests/test_project_state_sync.py -q   → passed
pytest -q（full）                             → 1937 passed, 0 failed
```

---

## 確認事項（監査 GPT 向け）

1. `data/api_usage_ledger.json` の 4 件目（2026-06-11, S4 run #47）は正規の paid-credit run として記録されたものか？
2. `gemini_3_flash_preview_success_records` を `3 → 4` に更新することは SSOT としての正確性を高める変更として許容されるか？
3. テストのハードコード `assert actual == 3 → 4` は実態追従としてスコープ内か？
