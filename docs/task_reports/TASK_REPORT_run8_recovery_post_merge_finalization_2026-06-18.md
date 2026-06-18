# タスク完了報告 — run 8 recovery post-merge finalization (2026-06-18)

## 概要

PR #117 (`recover(run8): promote verified candidate after push failure`) がマージされた後の
後処理タスク。`state_id` / `next_action` / README / `docs/PROJECT_STATE.md` に残っていた
"pending owner merge" 系の記述を全て除去し、generation 3 が main でアクティブな状態を正確に反映した。

## PR / マージ情報

| 項目 | 値 |
|---|---|
| Recovery PR | #117 — `recover(run8): promote verified candidate after push failure` |
| マージコミット | `21947b4b00c6516afcb1174da0655b808fc9c5d0` |
| Generation | 3 |
| best_score | 947.66 |
| Detector hash | `c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6` |

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `data/project_state.json` | 更新 | `state_id` / `next_action` / `note` を post-merge active 状態に変更 |
| `README.md` | 更新 | `scripts/update_readme.py` で status block を再生成 |
| `docs/PROJECT_STATE.md` | 更新 | セクション 1 / 4 / 7 の pending-merge 記述を除去 |
| `scripts/update_readme.py` | 更新 | 新 next_action キーの追加・`_apply_project_state` 分岐追加 |
| `tests/test_project_state_sync.py` | 更新 | テスト #21/#22 更新・新テスト #23/#24 追加・`_FORBIDDEN_STALE` 拡張 |
| `tests/test_update_readme.py` | 更新 | `TestPhase3Run8CandidateRecoveredState` を post-merge state に更新 |
| `docs/task_reports/TASK_REPORT_run8_recovery_post_merge_finalization_2026-06-18.md` | 新規 | 本ファイル |

## 主な変更内容

### data/project_state.json
- `state_id`: `phase3_run8_candidate_recovered_generation3_pending_owner_merge` → `phase3_run8_candidate_recovered_generation3_active`
- `next_action`: `run8_candidate_recovered_generation3_pending_owner_merge` → `post_recovery_monitor_generation3_and_owner_decide_next_phase3_step`
- `note`: "This PR is the recovery PR pending owner merge." を "Run 8 candidate recovered via owner-audited PR #117 and is now active on main as generation 3." に更新
- `candidate_promoted=true` / `promote_approved=true` / generation 3 / score 947.66 / detector hash は変更なし

### README.md (status block)
- `Current Phase`: "owner merge review pending" → "recovery complete / generation 3 active on main"
- `promote_approved`: "pending owner merge" → "via PR #117; active on main"
- `Next Focus`: "Owner merge review of the run 8 candidate recovery PR" → "Post-recovery monitoring of generation 3 and owner decision for the next Phase 3 experiment; no automatic paid-credit run"
- Generation 3 / 947.66 / c488855e / N/A fitness metrics は変更なし

### docs/PROJECT_STATE.md
- セクション 1: `promote_approved` 行・`state_id` 行・Next action 行を更新
- セクション 4: "recovery PR has been merged to main" のエントリを ❌ Incorrect → ✅ Correct に変更、末尾段落を更新
- セクション 7: "Owner merge review of the run 8 candidate recovery PR" → post-recovery monitoring に更新、"PR is pending owner merge" → "PR #117 merged; generation 3 active on main" に更新

### scripts/update_readme.py
- `_NEXT_ACTION_TEXT` に `post_recovery_monitor_generation3_and_owner_decide_next_phase3_step` を追加
- `_apply_project_state`: `candidate_promoted=True` ブランチで `next_action` を確認し、post-merge 状態では "generation 3 active on main … recovery complete" を出力するよう分岐追加
- `promote_note`: post-merge 状態では "via PR #117; active on main" を使用

### tests
- `test_project_state_sync.py`:
  - `_FORBIDDEN_STALE` に "owner merge review pending" / "pending owner merge" 等を追加
  - テスト #21: expected state_id を `phase3_run8_candidate_recovered_generation3_active` に更新
  - テスト #22: expected next_action を `post_recovery_monitor_generation3_and_owner_decide_next_phase3_step` に更新
  - テスト #23 (新規): README status block に pending-merge 語句がないことを確認
  - テスト #24 (新規): docs/PROJECT_STATE.md に pending-merge 語句がないことを確認
- `test_update_readme.py`:
  - `TestPhase3Run8CandidateRecoveredState._ps()`: `next_action` を新 post-merge キーに更新
  - `test_current_phase_shows_generation_3_active`: "active on main" / "recovery complete" を検証
  - `test_next_focus_says_post_recovery_monitoring`: post-recovery monitoring 語句を検証
  - `test_next_focus_no_owner_merge_review_pending`: "owner merge review pending" / "pending owner merge" が含まれないことを検証

## 後検証結果

```
pytest tests/test_project_state_sync.py tests/test_update_readme.py -q
→ 161 passed in 0.51s

pytest tests/test_workflow.py -q
→ 145 passed in 0.25s

pytest tests/ -q
→ 2193 passed, 5 warnings in 6.90s
```

## 禁止事項の遵守確認

| 禁止事項 | 確認 |
|---|---|
| Gemini API 呼び出し | 実施していない |
| 外部モデル API 呼び出し | 実施していない |
| workflow_dispatch | 実施していない |
| GitHub Actions 手動再実行 | 実施していない |
| paid-credit run | 実施していない |
| `data/api_usage_ledger.json` 編集 | 実施していない (git diff で確認) |
| `core/detector.py` 編集 | 実施していない |
| `data/genome.json` 編集 | 実施していない |
| `data/evolution_history.json` 編集 | 実施していない |
| `.github/workflows/**` 編集 | 実施していない |
| generation / best_score / detector hash の変更 | 実施していない (全て 3 / 947.66 / c488855e… で不変) |
| ledger レコードの作成・複製 | 実施していない |
| force-push | 実施していない |

## 変更ファイル確認 (git diff --name-only)

```
README.md
data/project_state.json
docs/PROJECT_STATE.md
scripts/update_readme.py
tests/test_project_state_sync.py
tests/test_update_readme.py
```

禁止ファイル (`core/detector.py`, `data/genome.json`, `data/evolution_history.json`,
`data/api_usage_ledger.json`, `.github/workflows/**`) は diff に含まれていない。

## 残存事項・注意点

- run 7 は API/token success only / untriaged のまま（このタスクのスコープ外）
- 次の paid-credit run は owner が承認するまで開始しない
- `fresh_verification_policy` フィールド（PR 中の制約を記録したもの）は歴史的記録として保持
