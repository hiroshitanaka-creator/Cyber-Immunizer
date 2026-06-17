# タスク完了報告 — Owner-approved paid-credit rerun readiness check (2026-06-17)

## 概要

PR #112 マージ後（generation-invariant score migration 完了）の状態で、
次の Owner 承認済み paid-credit rerun を実行する前の readiness audit を実施した。
API 呼び出し・ワークフロー実行・プロモーション・runtime/state ファイル編集は一切行っていない。
本 PR の差分は、この readiness audit report の新規追加のみである。
結論: **GO — Project Owner は paid-credit rerun を承認可能**。

---

## 変更ファイル一覧

*本 PR で追加したのは、この readiness audit report のみ。runtime/state files は編集していない。*

---

## 検証結果

### 1. Current main SHA

```
bbd11f163988665fcf2761753437b75ee0c1c692
```

最新コミット: `Merge pull request #112 from hiroshitanaka-creator/claude/adoption-gate-generation-invariant-in87ii`

PR #112 が main に含まれていることを確認。 ✅

---

### 2. Current state_id

`data/project_state.json` より:

```
phase3_generation_invariant_score_migrated_await_owner_approved_rerun
```

✅ 期待値と一致。

---

### 3. Current best_score

`data/genome.json` より:

```
"best_score": 939.34
```

`data/project_state.json` の `score_schema_migration.new_best_score = 939.34` と一致。 ✅

---

### 4. no-op 候補が adoption gate で fail すること

コマンド: `python -m core.fitness --candidate core/detector.py --json`

```json
{
  "score": 939.34,
  "passed_adoption_gate": false,
  "rejection_reasons": ["score=939.3400 <= previous_best=939.3400"],
  "score_components": {
    "tp_contribution": 1000.0,
    "fp_penalty": 0.0,
    "fn_penalty": 0.0,
    "exception_penalty": 0.0,
    "code_size_penalty": 60.66,
    "changed_lines_diagnostic": 0.0,
    "gate_score": 939.34
  }
}
```

exit code: 1 (gate reject) ✅

`score=939.3400 <= previous_best=939.3400` により正しく reject される。

---

### 5. changed_lines が diagnostic-only であること

**core/fitness.py `_compute_score` 関数 (line 52-74):**

```python
def _compute_score(tp_rate, fp_rate, fn_rate, exception_count, code_chars) -> float:
    return (
        1000.0 * tp_rate
        - 2000.0 * fp_rate
        - 1500.0 * fn_rate
        - 50.0  * exception_count
        - 0.02  * code_chars
    )
```

`changed_lines` は引数に含まれない。 ✅

`changed_lines_diagnostic` フィールドは `10.0 * changed_lines` として報告のみ (line 353)。
ただし `gate_score` の計算には使用されない。 ✅

---

### 6. stale `- 10*changed_lines` formula の不在確認

コマンド: `grep -R "10\*changed_lines\|- 10\.0 \* changed_lines\|- 10\*changed" -n core scripts tests data docs`

マッチ箇所: `tests/test_gemini_integration.py` の 2 件のみ。
両方とも **negative assertion** (guidance/prompt に `10*changed_lines` が存在しないことを assert するテスト)。
active runtime / prompt path には stale formula なし。 ✅

---

### 7. propose guidance が generation-invariant formula と一致すること

`scripts/propose_mutation.py::_build_scoring_guidance` (line 1099-1149) が emit する内容:

```
SCORING-AWARE GUIDANCE:
- previous_best (current best detector score): {best_score}. A valid patch is NOT
  enough; it must score STRICTLY GREATER THAN previous_best or the gate rejects.
- score = 1000*tp_rate - 2000*fp_rate - 1500*fn_rate - 50*exception_count
  - 0.02*code_chars (avg_latency and changed_lines excluded from score).
- changed_lines is diagnostic-only and is NOT part of the adoption gate score.
...
BASELINE CONTRACT (do NOT regress coverage):
- Keep five indicators: path_traversal_indicator, script_injection_indicator,
  sqli_indicator, command_delimiter_indicator, encoded_traversal_indicator.
- Keep the full surface: request.method, request.path, request.query, request.headers,
  request.body.
- Keep a blocked=False fallback so false positives stay low.
- Make a minimal additive edit; ...
```

確認項目:
- `avg_latency and changed_lines excluded from score` ✅
- `changed_lines is diagnostic-only` ✅
- 5 つの symbolic indicator すべて記載 ✅
- full request inspection surface (method/path/query/headers/body) ✅
- `blocked=False` fallback ✅
- `previous_best` を strictly 上回ること ✅

---

### 8. run 7 が untriaged のままであること

`data/project_state.json` より:

```json
"run_7_note": "The 7th primary-model success record remains API/token success only and untriaged.
This migration does not infer apply, evaluate, adoption, or promote from run 7."
```

run 7 (2026-06-16T06:20:37 UTC) は API/token success のみで triage 未実施。 ✅

---

### 9. promote_approved=false であること

`data/project_state.json::promotion.promote_approved = false` ✅
`data/genome.json` に `promote_approved` フィールドなし（default false）。

adoption gate をこれまで一度も通過した候補なし (`adoption_gate_ever_passed: false`)。 ✅

---

### 10. paid-credit API ledger 件数

`data/api_usage_ledger.json`:

| model | success records |
|---|---|
| gemini-3-flash-preview (primary) | **7** |
| gemini-3.1-flash-lite (fallback) | 1 |
| **Total paid-credit success** | **8** |

`data/project_state.json::gemini_3_flash_preview_success_records = 7` は primary model のみカウント。整合している。 ✅

run triage 状態:
- runs 1–3: propose output-contract failure (valid patch なし)
- run 4 (S4 run #47): apply 到達・G1 で fail、evaluate 未到達
- run 5 (2026-06-15): evaluate_rejected (score=494.48 ≤ previous_best=729.34)
- run 6 (2026-06-16): evaluate_rejected (score=478.12 ≤ previous_best=729.34)
- run 7 (2026-06-16T06:20): **API/token success のみ、untriaged**

---

### 11. テスト結果

| suite | result |
|---|---|
| `pytest tests/test_fitness.py -q` | **30 passed** ✅ |
| `pytest tests/test_gemini_integration.py -q` | **308 passed** ✅ |
| `pytest tests/test_project_state_sync.py -q` | **22 passed** ✅ |
| `pytest tests/ -q` | **2157 passed** ✅ |

---

### 12. 禁止ファイル・設定の変更確認

本 PR の差分: **本 readiness audit report の新規作成のみ**。
runtime/state files edited: **なし**。

- `.github/**`: 変更なし ✅
- `data/api_usage_ledger.json`: 変更なし ✅
- `data/genome.json`: 変更なし ✅
- `data/project_state.json`: 変更なし ✅
- `core/**`: 変更なし ✅
- `scripts/**`: 変更なし ✅
- Gemini API 呼び出し: なし ✅
- workflow_dispatch: なし ✅
- promotion state 変更: なし ✅

---

## ブロッカー

**なし。**

---

## 最終勧告

### GO ✅ — Project Owner は paid-credit rerun を承認可能

GO 条件の全確認:

| 条件 | 結果 |
|---|---|
| main に PR #112 が含まれる | ✅ SHA `bbd11f1` |
| best_score=939.34 | ✅ genome.json + project_state.json 一致 |
| no-op 候補が adoption gate で fail | ✅ `score=939.3400 <= previous_best=939.3400` |
| propose guidance に changed_lines が score に含まれない | ✅ `avg_latency and changed_lines excluded from score` |
| stale `- 10*changed_lines` が active runtime/prompt path に不在 | ✅ test assertion のみ（negative assertion） |
| promote_approved=false | ✅ |
| run 7 が untriaged のまま | ✅ |
| テスト全通過 | ✅ 2157 passed |
| 禁止ファイル・設定の変更なし | ✅ |

NO-GO 条件: **すべて false（該当なし）**

---

## 残存事項・注意点

- run 7 (2026-06-16T06:20) は API/token success のみで未 triage。次の Owner 承認 rerun 後に別途 triage が必要。
- 次の rerun では `previous_best=939.34` を超える候補が必要。
  runs 5 & 6 が 729.34 未満で rejected だったことを踏まえ、propose 側の baseline-preservation contract（5 indicator + full surface + blocked=False fallback）が機能することに期待。
- run 7 を approve/triage/promote することは本タスクのスコープ外であり実施していない。
