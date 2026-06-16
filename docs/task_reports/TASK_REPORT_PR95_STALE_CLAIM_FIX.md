# タスク完了報告 — PR #95 Stale Claim Fix & Drift-Prevention Tests

## 1. 概要

PR #95 の残存 stale current-state claim を除去し、同種の drift を将来検出できるテストを追加した。
invalid UTF-8 artifact に対するクラッシュ防止も合わせて実装。

commit: `0e61d9f`

---

## 2. 修正内容

### 2-1. README.md — roadmap v0.3 行の stale claim 除去

| Before | After |
|---|---|
| `初回 paid-credit run 待機中` | `paid-credit API success records 5件（2026-06-03〜2026-06-15）、run 5 artifact triage pending` |

### 2-2. docs/PROJECT_STATE.md — Section 4 の stale claim 除去

| Before | After |
|---|---|
| `The 3 primary-model paid-credit API calls **were executed** and are recorded in the ledger. The promotion gate was never reached because no valid candidate patch was produced.` | `The primary-model paid-credit API calls **have been executed** and are recorded in the ledger (5 success records). The promotion gate was never reached in verified runs 1–4 because no valid candidate patch was produced; run 5 (2026-06-15) outcome is pending artifact triage.` |

### 2-3. tests/test_project_state_sync.py — 強化

**_FORBIDDEN_STALE に追加:**
- `初回 paid-credit run 待機中`
- `The 3 primary-model paid-credit API calls`

**test_evaluate_and_promote_not_reached メッセージ修正:**
- `"evaluate was not reached in any paid-credit run"` → `"evaluate was not reached in verified runs 1–4; run 5 is pending artifact triage"`

**新規テスト 6 件（#17〜#22）:**

| # | テスト名 | 内容 |
|---|---|---|
| 17 | `test_readme_roadmap_no_stale_first_run_pending` | README 全文に `初回 paid-credit run 待機中` がないこと |
| 18 | `test_project_state_doc_no_stale_3_calls_claim` | PROJECT_STATE.md に `The 3 primary-model paid-credit API calls` がないこと |
| 19 | `test_project_state_doc_shows_5_success_records` | PROJECT_STATE.md に `**5**` が含まれること |
| 20 | `test_project_state_doc_mentions_run5_triage_pending` | PROJECT_STATE.md に `run 5` と `artifact triage` が含まれること |
| 21 | `test_state_id_is_record_5_pending_triage` | `state_id == "phase3_paid_credit_record_5_recorded_pending_artifact_triage"` |
| 22 | `test_next_action_is_triage_artifacts` | `next_action == "triage_latest_paid_credit_run_artifacts_and_update_apply_evaluate_promote_state"` |

### 2-4. scripts/triage_s4_rerun.py — UnicodeDecodeError 堅牢性

- `_load_json_safe()`: `UnicodeDecodeError` を `OSError` の前に catch → `"contains invalid UTF-8 encoding"` エラーを返す
- `_scan_for_secrets()`: `except (OSError, UnicodeDecodeError)` に拡張 → silent skip（クラッシュ禁止）

| artifact | invalid UTF-8 時の挙動 |
|---|---|
| `fitness_report.json` | `tool_failure`（fail-closed） |
| `mutation_patch.json` | `propose_failed` + warning |
| `candidate_detector.py` | silent skip（クラッシュせず処理継続） |

### 2-5. tests/test_s4_rerun_triage.py — invalid UTF-8 テスト 3 件（#38〜#40）

| # | テスト名 | 内容 |
|---|---|---|
| 38 | `test_invalid_utf8_fitness_report_is_tool_failure` | fitness_report.json が invalid UTF-8 → `tool_failure` |
| 39 | `test_invalid_utf8_mutation_patch_is_propose_failed` | mutation_patch.json が invalid UTF-8 → `propose_failed` + warning |
| 40 | `test_invalid_utf8_candidate_detector_no_crash` | candidate_detector.py が invalid UTF-8 → クラッシュしない |

---

## 3. 変更ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `README.md` | v0.3 roadmap 行の stale claim 除去 |
| `docs/PROJECT_STATE.md` | Section 4 の "3 calls" stale claim 修正 |
| `tests/test_project_state_sync.py` | _FORBIDDEN_STALE 追加 / test message 修正 / 新規テスト #17–22 |
| `scripts/triage_s4_rerun.py` | UnicodeDecodeError catch 追加 |
| `tests/test_s4_rerun_triage.py` | 新規テスト #38–40 |

変更禁止ファイル（変更なし）:
`data/api_usage_ledger.json` / `data/genome.json` / `core/policy.py` /
`core/detector.py` / `data/evolution_history.json` / `.github/workflows/**`

---

## 4. テスト結果

```
pytest tests/test_project_state_sync.py -q
→ 22 passed in 0.06s

pytest tests/test_s4_rerun_triage.py -q
→ 40 passed in 0.20s

pytest -q
→ 1999 passed in 3.38s
```

---

## 5. セキュリティ制約確認

| 制約 | 遵守状況 |
|---|---|
| Gemini API 呼び出し禁止 | ✅ 不使用 |
| workflow_dispatch 禁止 | ✅ 不使用 |
| data/api_usage_ledger.json 編集禁止 | ✅ 変更なし |
| core/** / data/genome.json 等 FROZEN | ✅ 変更なし |
| run 5 apply/evaluate/promote 推測禁止 | ✅ "pending artifact triage" として扱った |

---

## 6. 残存事項

- run 5 の apply/evaluate/promote 到達状況は Project Owner による artifact triage 後に確定する
- `scripts/triage_s4_rerun.py --artifacts-dir <DIR>` で実アーティファクトを用いた検証が必要
