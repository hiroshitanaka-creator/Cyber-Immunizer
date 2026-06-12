# タスク完了報告 — G1 Repeat-Multiplier Gap Closure (PR #91)

**Date:** 2026-06-12
**Branch:** `claude/s4-artifact-analysis-7571321383-l8kedi`

---

## 概要

S4 run #47 (artifact 7571321383) で特定された G1 ギャップ（repeat multiplier is non-constant）を閉じた。
`scripts/propose_mutation.py` の `_validate_replacement_code()` に check 6.5 を追加・拡張し、
Codex Review P2 指摘を受けて Name/Call/Attribute オペランドと int/float 定数の両方をカバーする
12 パターンすべてを apply 前に検出・拒否する実装に更新した。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `scripts/propose_mutation.py` | 編集 | check 6.5 拡張（G1 Codex P2 対応）、G1 helper 関数追加、`_SAMPLE_MUTATION` をブランチベース confidence に更新、docstring 更新 |
| `tests/test_propose_output_contract.py` | 編集 | `TestRuntimeAllocationRiskGap` クラスを 17 テストに拡張（12 rejection + 5 regression） |
| `docs/task_reports/TASK_REPORT_G1_REPEAT_MULTIPLIER_GAP_CLOSURE_20260612.md` | 更新 | Codex P2 解決状況・後検証結果を追記 |

---

## 主な変更内容

### `scripts/propose_mutation.py`

1. **G1 helper 関数追加**（`_validate_replacement_code` より前に配置）:
   - `_g1_is_numeric_const(node)` — `ast.Constant` かつ value が int または float の場合 True
   - `_g1_is_runtime_derived(node)` — `ast.Name` / `ast.Attribute` / `ast.Call` の場合 True

2. **check 6.5 拡張** (`else:` ブロック内):
   - **旧（Codex P2 指摘）**: `non-int Constant × bare Name` のみ対象（float×Name のみ）
   - **新（拡張後）**: `_g1_is_numeric_const × _g1_is_runtime_derived`（両方向）= 12 パターン全カバー
     - float×Name, float×Call, float×Attribute（および各逆順）
     - int×Name, int×Call, int×Attribute（および各逆順）
   - 違反文字列は `core/policy.py _check_repeat_mult()` と同一を維持

3. **docstring 更新**: check 6.5 説明を拡張後の 12 パターン対応に合わせた

4. **`_SAMPLE_MUTATION` 更新** — `per_signal_boost * len(matched)` 乗算式をブランチベース confidence に変更:
   ```python
   # 変更前（G1 違反: float 定数 × Call）:
   per_signal_boost = 0.12
   confidence = min(1.0, base_confidence + per_signal_boost * len(matched))
   
   # 変更後（安全なブランチベース）:
   confidence = 0.5
   if len(matched) > 1:
       confidence = 0.7
   if len(matched) > 2:
       confidence = 0.9
   ```

5. **`_LLM_SYSTEM_PROMPT` rule 17**（変更なし — 前コミットで追加済み）:
   ```
   17. Avoid runtime allocation risk: non-constant repeat multiplier is rejected (e.g. 0.3 * count; use constant float 0.7).
   ```

### `tests/test_propose_output_contract.py`

`TestRuntimeAllocationRiskGap` クラスを 5 テスト → 17 テストに拡張:

**12 rejection テスト（新規）:**

| テスト名 | 検証パターン |
|---|---|
| `test_float_times_name_rejected` | `0.3 * indicator_count` (float × Name) |
| `test_name_times_float_rejected` | `indicator_count * 0.3` (Name × float) |
| `test_float_times_call_rejected` | `0.12 * len(matched)` (float × Call) |
| `test_call_times_float_rejected` | `len(matched) * 0.12` (Call × float) |
| `test_float_times_attribute_rejected` | `0.2 * request.score` (float × Attribute) |
| `test_attribute_times_float_rejected` | `request.score * 0.2` (Attribute × float) |
| `test_int_times_name_rejected` | `2 * indicator_count` (int × Name) |
| `test_name_times_int_rejected` | `indicator_count * 2` (Name × int) |
| `test_int_times_call_rejected` | `2 * len(matched)` (int × Call) |
| `test_call_times_int_rejected` | `len(matched) * 2` (Call × int) |
| `test_int_times_attribute_rejected` | `2 * request.score` (int × Attribute) |
| `test_attribute_times_int_rejected` | `request.score * 2` (Attribute × int) |

**5 regression テスト（旧 5 テストを更新・置換）:**

| テスト名 | 検証内容 |
|---|---|
| `test_branch_based_confidence_still_passes` | ブランチベース confidence が拒否されない |
| `test_valid_fixture_still_passes` | `_VALID_BODY` が引き続き合格する |
| `test_offline_sample_still_passes` | `_SAMPLE_MUTATION`（ブランチベース更新後）が引き続き合格する |
| `test_full_contract_path_rejects_unsafe_multiplier` | `_parse_and_validate_response` でも拒否される |
| `test_prompt_states_runtime_allocation_obligation` | プロンプトに 3 フレーズが存在する |

---

## Codex Review P2 解決状況

| Codex 指摘 | 内容 | 対応 |
|---|---|---|
| P2: check too narrow | check 6.5 が `non-int Constant × Name` のみ対象 | `_g1_is_numeric_const × _g1_is_runtime_derived` に拡張、12 パターン全対応 |
| P2: Call オペランド未対応 | `0.12 * len(matched)` が通過してしまう | `_g1_is_runtime_derived` に `ast.Call` を含める |
| P2: Attribute オペランド未対応 | `0.2 * request.score` が通過してしまう | `_g1_is_runtime_derived` に `ast.Attribute` を含める |
| P2: int 定数未対応 | `2 * indicator_count` が通過してしまう | `_g1_is_numeric_const` で `int` も対象にする |
| P2: 逆順オペランド不完全 | `indicator_count * 0.3` 等が通過してしまう | `or` の両方向で両 helper を呼び出す |
| P2: offline sample が G1 違反 | `per_signal_boost * len(matched)` がテスト通過していたが G1 違反 | `_SAMPLE_MUTATION` をブランチベース confidence に変更 |

---

## スコープ外分類

`tests/test_gemini_integration.py` の 3 テスト（`test_accepts_safe_code`, `test_accepts_valid_multiline_replacement_code`, `test_accepts_nested_return_plus_top_level_fallback`）は `0.12 * len(matched)` を含む fixture を使用しており、拡張後の G1 check で拒否される。

これらのテストは FROZEN ファイル（本タスクの ALLOWED FILES 外）に存在する。
対応ステータス: **OUT_OF_SCOPE — 別タスクで fixture 更新が必要**。

本タスクの required verification コマンド（`pytest tests/test_propose_output_contract.py -q` および `pytest tests/test_gemini_paid_credit.py tests/test_workflow.py -q`）はいずれも通過している。

---

## テスト検証結果

```
pytest tests/test_propose_output_contract.py -q
→ 44 passed in 0.10s

pytest tests/test_gemini_paid_credit.py tests/test_workflow.py -q
→ 195 passed in 0.33s
```

---

## 後検証

```
git grep "_g1_is_numeric_const\|_g1_is_runtime_derived" scripts/propose_mutation.py
→ scripts/propose_mutation.py:def _g1_is_numeric_const(node: ast.expr) -> bool:
→ scripts/propose_mutation.py:def _g1_is_runtime_derived(node: ast.expr) -> bool:
→ scripts/propose_mutation.py:    (_g1_is_numeric_const(_g1_l) and _g1_is_runtime_derived(_g1_r))
→ scripts/propose_mutation.py:    or (_g1_is_numeric_const(_g1_r) and _g1_is_runtime_derived(_g1_l))

git grep "per_signal_boost" scripts/propose_mutation.py
→ (no output — multiplier expression removed from _SAMPLE_MUTATION)

git grep "repeat multiplier" scripts/propose_mutation.py
→ (violation string present in check 6.5 and rule 17)
```

---

## 残存事項・注意点

1. **`tests/test_gemini_integration.py` fixture 更新**: `0.12 * len(matched)` を含む 3 テスト fixture が G1 違反となる。FROZEN ファイルのため別タスクで対応が必要。

2. **`data/project_state.json` success count 不一致**: 前タスクから残存。本タスクのスコープ外。

3. **次の paid-credit run**: propose/apply 両側でルールが完全に一致した（12 パターン全対応）。Gemini が repeat multiplier を使用した場合は propose 段階で失敗し、不要な artifact アップロードを防ぐ。

---

## Definition of Done 確認

- [x] check 6.5 が 12 パターンすべてを拒否する（float/int × Name/Call/Attribute、両方向）
- [x] `_validate_replacement_code()` が `_VALID_BODY` / `_G1_BRANCH_BODY` を合格させる
- [x] `_SAMPLE_MUTATION` がブランチベース confidence に更新され G1 check を通過する
- [x] `TestRuntimeAllocationRiskGap` 17 テスト全通過
- [x] `pytest tests/test_propose_output_contract.py -q`: 44 passed
- [x] `pytest tests/test_gemini_paid_credit.py tests/test_workflow.py -q`: 195 passed
- [x] `scripts/propose_mutation.py` 以外の runtime コードは無変更
- [x] `core/policy.py` / `core/detector.py` / `data/**` 無変更
- [x] Codex P2 コメントの全指摘が解決された
