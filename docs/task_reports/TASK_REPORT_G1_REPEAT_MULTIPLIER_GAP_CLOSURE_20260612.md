# タスク完了報告 — G1 Repeat-Multiplier Gap Closure

**Date:** 2026-06-12
**Branch:** `claude/s4-artifact-analysis-7571321383-l8kedi`

---

## 概要

S4 run #47 (artifact 7571321383) で特定された G1 ギャップ（repeat multiplier is non-constant）を閉じた。
`scripts/propose_mutation.py` の `_validate_replacement_code()` に check 6.5 を追加し、
Gemini が生成した `replacement_code` に非定数の乗算式が含まれる場合を apply 前に検出・拒否する。
プロンプト rule 17 の追加でモデルへの制約も明示した。
5 件の新テストが追加され、既存 1924 テストすべて引き続きパス。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `scripts/propose_mutation.py` | 編集 | check 6.5 (G1 repeat-multiplier check) 追加、docstring 更新、LLM system prompt rule 17 追加 |
| `tests/test_propose_output_contract.py` | 編集 | `TestRuntimeAllocationRiskGap` クラス（5テスト）追加 |
| `docs/task_reports/TASK_REPORT_G1_REPEAT_MULTIPLIER_GAP_CLOSURE_20260612.md` | 新規 | 本報告ファイル |

---

## 主な変更内容

### `scripts/propose_mutation.py`

1. **check 6.5 — BinOp(Mult) non-constant repeat-multiplier check** (`else:` ブロック内、check 6 parse 成功後・check 7 semantic validation 前):
   - `ast.walk(tree)` で `BinOp(Mult)` ノードをスキャン
   - 一方のオペランドが非 int 定数（float / string Constant）かつ他方が `ast.Name` の場合に拒否
   - 違反文字列は `core/policy.py _check_repeat_mult()` と同一: `"runtime allocation risk: repeat multiplier is non-constant (cannot bound statically) — fail-closed"`
   - 除外: `Call × float_const`（例: `0.12 * len(matched)`）はこのチェックでは検出しない — apply 側で検出される

2. **docstring 更新**: check 6.5 を checks リストに追加

3. **`_LLM_SYSTEM_PROMPT` rule 17 追加** (8326 chars 以下に収まるよう compact 1 行):
   ```
   17. Avoid runtime allocation risk: non-constant repeat multiplier is rejected (e.g. 0.3 * count; use constant float 0.7).
   ```
   - "runtime allocation risk", "repeat multiplier", "non-constant" の 3 フレーズを含む（テスト検証済み）
   - prompt 長を 8326 chars に抑え、既存の budget gate テストがパスするよう設計

### `tests/test_propose_output_contract.py`

`TestRuntimeAllocationRiskGap` クラス（5テスト）を追加:

| テスト名 | 検証内容 |
|---|---|
| `test_non_constant_repeat_multiplier_rejected` | `0.3 * indicator_count` が `_validate_replacement_code` で拒否される |
| `test_non_constant_repeat_multiplier_rejected_through_full_contract_path` | 同パターンが `_parse_and_validate_response` でも拒否される (patch=None) |
| `test_prompt_states_runtime_allocation_obligation` | プロンプトに 3 フレーズが存在する |
| `test_valid_fixture_still_passes_validator` | `_VALID_BODY` が引き続き合格する |
| `test_offline_sample_still_passes_full_contract_path` | オフラインサンプル (`per_signal_boost * len(matched)`) が引き続き合格する |

---

## 設計上の判断

**なぜ `check_runtime_allocation_risks()` を直接使わないか**:
`check_runtime_allocation_risks()` は list/set/dict comprehension・generator・range() も拒否する。
既存テストフィクスチャ（`test_gemini_integration.py`）が list comprehension を使用しており、
propose 段階での検出スコープは repeat-multiplier のみとした（apply 側で残りをカバー）。

**タスク scope**: `scripts/propose_mutation.py` と `tests/test_propose_output_contract.py` のみ編集。
`core/policy.py` / `core/detector.py` / `data/**` / `.github/**` は無変更。

---

## テスト検証結果

```
pytest tests/test_propose_output_contract.py -q
→ 32 passed in 0.05s

pytest -q
→ 1924 passed, 1 failed (pre-existing: test_project_state_matches_ledger_success_count)
```

pre-existing failure: `data/project_state.json` が 3 primary-model success と宣言しているが、
`data/api_usage_ledger.json` には S4 run (2026-06-11) を含む 4 件がある。
このギャップは本タスクのスコープ外であり、変更前から存在していた。

---

## 後検証

```
git grep "check_runtime_allocation_risks" scripts/propose_mutation.py
→ (no output — import not used; custom BinOp walker used instead)

git grep "repeat multiplier" scripts/propose_mutation.py
→ scripts/propose_mutation.py:  6.5 Runtime allocation risk check — repeat-multiplier sub-case only
→ scripts/propose_mutation.py:  runtime allocation risk: repeat multiplier is non-constant
→ scripts/propose_mutation.py:  non-constant repeat multiplier is rejected

git diff --name-only HEAD
→ scripts/propose_mutation.py
→ tests/test_propose_output_contract.py
→ docs/task_reports/TASK_REPORT_G1_REPEAT_MULTIPLIER_GAP_CLOSURE_20260612.md
```

---

## 残存事項・注意点

1. **Call 型オペランドの repeat multiplier**（例: `0.12 * len(matched)`）は propose 側ではスキャンしない。
   apply 側 `core/policy.py` で検出される。次の paid-credit run で Gemini がこのパターンを生成した場合、
   apply 失敗となる。必要であれば将来のタスクで propose 側カバレッジを拡張できる。

2. **`data/project_state.json` の success count** が ledger と不一致のまま。
   本タスクのスコープ外だが、次の Owner レビュー時に更新が必要。

3. **次の paid-credit run** に向けて: propose/apply 両側でルールが一致したため、
   Gemini が `0.3 * variable` 型の confidence 式を生成した場合は propose 段階で失敗し、
   不要な artifact アップロードを防ぐ。

---

## Definition of Done 確認

- [x] `_validate_replacement_code()` が `0.3 * indicator_count` を拒否する
- [x] `_validate_replacement_code()` が `_VALID_BODY` / offline sample を合格させる
- [x] `_LLM_SYSTEM_PROMPT` に rule 17 が追加されている
- [x] `tests/test_propose_output_contract.py::TestRuntimeAllocationRiskGap` 5 テスト全通過
- [x] `pytest tests/test_propose_output_contract.py -q`: 32 passed
- [x] `pytest -q`: 1924 passed (pre-existing 1 failure のみ)
- [x] `scripts/propose_mutation.py` 以外の runtime コードは無変更
- [x] `core/policy.py` / `core/detector.py` / `data/**` 無変更
