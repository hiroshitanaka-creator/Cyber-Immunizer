# タスク完了報告 — PR #91 merge後 current-state sync

## 概要

PR #91 (`fix(propose): close S4 G1 repeat-multiplier gap`) merge後の current-state drift を解消した。
`data/project_state.json`・`docs/PROJECT_STATE.md`・README status block・テスト・S4 rerun チェックリストを
post-PR91 merged 状態に整合させた。paid-credit run・workflow_dispatch・Gemini API 呼び出しは一切実行していない。

## 変更ファイル一覧

| ファイル | 変更種別 |
|---|---|
| `data/project_state.json` | 更新 |
| `docs/PROJECT_STATE.md` | 更新 |
| `scripts/update_readme.py` | 更新 |
| `README.md` | 更新（`update_readme.py` 経由で再生成） |
| `tests/test_project_state_sync.py` | 更新（テスト追加・禁止文字列追加） |
| `docs/S4_RERUN_CHECKLIST.md` | 新規作成 |

## 主な変更内容

### `data/project_state.json`
- `state_id`: `phase3_s4_materialize_reached_apply_blocked_g1_gap_closing` →
  `phase3_s4_g1_gap_closed_pending_owner_approved_next_s4_rerun`
- `next_action`: 旧 `merge_g1_repeat_multiplier_gap_closure_then_...` →
  `prepare_owner_approved_next_s4_rerun_post_g1_gap_closure`
- `paid_credit_api_calls` に `"g1_gap_closure_pr91": "merged"` を追記

### `docs/PROJECT_STATE.md`
- Section 1 table: "pending merge" → "merged"、新 `state_id` を反映、`Next action` を post-PR91 文言に更新
- Section 7: "being closed in PR #91" → "PR #91 is merged" に書き換え、"The next step is for the Project Owner to merge PR #91" を削除

### `scripts/update_readme.py`
- `_NEXT_ACTION_TEXT` に `prepare_owner_approved_next_s4_rerun_post_g1_gap_closure` エントリを追加
- `_apply_project_state()` に apply-reached・evaluate未到達状態のハンドリング追加
  (`current_phase`, `promote_note` を正しく override)

### `README.md`（再生成）
- "3 successful / 3 attempt(s)" → "4 successful / 4 attempt(s)"
- Current Phase が apply-reached・G1 closed 状態の文言に更新
- Next Focus が Owner-approved next S4 rerun 文言に更新
- promote_note が "apply failed at G1; evaluate/promote not reached" に更新

### `tests/test_project_state_sync.py`
- `_FORBIDDEN_STALE` に `"PR #91 (pending merge)"` / `"to merge PR #91"` を追加
- テスト #11〜#16 を新規追加:
  - #11: Phase 3 active・live_model_enabled=true
  - #12: valid_mutation_patch_produced=true
  - #13: apply_reached=true
  - #14: evaluate_reached=false・promote_reached=false
  - #15: promote_approved=false
  - #16: next_action が post-PR91 rerun を参照し、旧 merge_g1 値でない

### `docs/S4_RERUN_CHECKLIST.md`（新規）
- Owner承認必須条件、trigger parameters、期待 artifact 一覧
- Evaluate未到達/Apply失敗/Adoption gate rejected/Promote eligible の各ケース別トリアージ
- Ledger 検証手順、post-run 状態更新手順、Hard constraints

## 後検証結果

```
pytest tests/test_project_state_sync.py -x -q
16 passed in 0.06s
```

ledger 確認:
- `gemini-3-flash-preview` + `gemini_paid_credit` + `success=true` のレコード: **4件**（変更なし）
- `data/api_usage_ledger.json` は手動編集していない

## 残存事項・注意点

- `data/api_usage_ledger.json` は変更していない（tasklist 通り）
- `core/detector.py` は変更していない（scope 外）
- `.github/workflows/**` は変更していない（scope 外）
- `promote_approved` は `false` のまま（Owner 承認前）
- `data/genome.json` は変更していない（API mode/model名は変更禁止）
- 次の paid-credit rerun は Project Owner の明示承認後に `docs/S4_RERUN_CHECKLIST.md` の手順に従うこと
