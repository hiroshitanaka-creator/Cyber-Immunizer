# タスク完了報告 — PR #80

## 概要

README generator（`scripts/update_readme.py`）と関連テスト（`tests/test_update_readme.py`、`tests/test_phase2_progress_docs.py`）を更新し、`data/api_usage_ledger.json` の primary evidence（gemini-3-flash-preview paid-credit API call success 記録が既に存在）に合わせた状態を README に反映させた。README は手動パッチではなく generator 再実行（`python scripts/update_readme.py`）で更新した。

## 変更ファイル一覧

| ファイル | 区分 | 内容 |
|---|---|---|
| `scripts/update_readme.py` | 変更 | `current_phase` を ledger 状態ベースに動的化。"Phase 3 First Paid-Credit Run" → "Phase 3 Paid-Credit API Calls" に改名。`next_focus`・`promote_note` を状態別に追加 |
| `README.md` | 変更（generator 再実行） | ステータスブロックを generator で再生成。ledger 証拠に基づく Phase 3 状態を反映 |
| `tests/test_update_readme.py` | 変更 | `test_real_readme_block_shows_first_run_pending` → `test_real_readme_block_shows_paid_credit_run_state`（ledger ベースの動的チェック）に置換 |
| `tests/test_phase2_progress_docs.py` | 変更 | `TestPhase3NotStartedAndApiNotConnected` の3テストをstatus blockスコープに再設定（stale Phase 2 wording を README current status に強制しない） |
| `docs/task_reports/TASK_REPORT_PR80.md` | 新規 | 本報告書 |

## 主な変更内容

### scripts/update_readme.py
- `current_phase` を static 文字列から ledger 状態ベースの動的値に変更:
  - primary success 記録あり → "Phase 3 — paid-credit API call success records exist; post-run result review pending"
  - primary 試行なし → "Phase 3 — paid-credit path ready; first paid-credit run not yet executed"
  - primary 試行あり・全失敗 → "Phase 3 — paid-credit run attempted (no successful calls); inspect ledger"
- `phase_rows` に `Next Focus` 行と ledger 状態別 `promote_note` を追加
- "Phase 3 First Paid-Credit Run" → "Phase 3 Paid-Credit API Calls" に改名

### README.md（generator 再実行結果）
新しいステータスブロック:
```
| Current Phase | Phase 3 — paid-credit API call success records exist; post-run result review pending |
| Phase 3 Activation | Complete (PR #58-#62) |
| Phase 3 Paid-Credit API Calls | Executed (3 successful / 3 attempt(s)) |
| promote_approved | false (promotion not approved — API call already executed; post-run review pending) |
| Next Focus | Review existing paid-credit run results: ledger / candidate / apply / evaluate / promotion decision |
| live_model_enabled | true |
```

### tests/test_update_readme.py
- `test_real_readme_block_shows_first_run_pending` を削除
- `test_real_readme_block_shows_paid_credit_run_state` を追加:
  - 実際の ledger を読み、success 記録があれば "Executed" を要求、なければ pending/failed state を要求
  - ledger が更新されても追従する

### tests/test_phase2_progress_docs.py
`TestPhase3NotStartedAndApiNotConnected` の3テストを再スコープ:
- `test_readme_states_phase3_not_started` → `test_readme_status_block_shows_phase3_activation`: 全 README ではなく status block のみを検査
- `test_readme_states_api_not_connected` → `test_readme_status_block_shows_paid_credit_api_mode`: status block が paid-credit API mode を示すことを確認
- `test_readme_live_model_enabled_remains_false` → `test_readme_status_block_shows_live_model_enabled_true`: status block に `live_model_enabled | true` があることを確認

PHASE_2_PLAN.md 向けアサーション（`test_phase2_plan_states_phase3_not_started` 等）は変更なし（歴史的記録として正確）。

## Source Evidence

- **Evidence A**: HEAD = `d3ed3f23ab03cf1b03f4ba3b2ec1ee12981f00f6` = PR #79 merge commit = origin/main ✅。working tree clean（作業開始時）。
- **Evidence B**: `data/api_usage_ledger.json` に `gemini-3-flash-preview` / `gemini_paid_credit` / `success=true` × 3 件（`2026-06-03T23:36`、`2026-06-04T00:34`、`2026-06-04T01:33`）✅
- **Evidence C**: `scripts/update_readme.py:121` の `current_phase` が static "run pending" 文字列だったことを確認 → 修正済み ✅
- **Evidence D**: `tests/test_update_readme.py:603-607` が "Not yet executed" / "first run pending" を要求していたことを確認 → 修正済み ✅；`tests/test_phase2_progress_docs.py:531-623` が README 全体をスキャンして stale Phase 2 wording を要求していたことを確認 → status block スコープに再設定済み ✅
- **Evidence E**: `README.md:882-884` に "Gemini 3 Flash Preview run pending" / "Not yet executed" が残っていたことを確認 → generator 再実行で修正済み ✅

## README generator/test maintenance

**Generator 更新**: README を手動編集せず generator を修正してから再実行した。今後 generator を呼ぶたびに ledger 状態が正しく反映される。

**テスト再スコープの理由**: 旧テストが全 README を対象にすると、歴史的 Phase 1/2 セクション（lines 695, 712, 733 等）に残る "Phase 3 not started" / "API not connected" テキストで pass していた。これでは将来そのセクションを削除したとき stale wording の復元を強制されるため、status block のみをスキャンするよう再スコープした。PHASE_2_PLAN.md アサーションは歴史的記録として正確なため変更せず。

**README 歴史的セクションの扱い**: lines 695, 712, 733 等の Phase 1/2 記述（"API is intentionally not connected yet" / "Phase 3 is not started" / "live_model_enabled remains false"）は当時の状態を正確に記録した歴史的テキストとして保持（今回の scope 外）。

## 後検証結果

```
# 変更ファイル（4 ファイル + 1 新規）
$ git diff --name-only
README.md
docs/task_reports/TASK_REPORT_PR80.md   ← 新規
scripts/update_readme.py
tests/test_phase2_progress_docs.py
tests/test_update_readme.py

# 禁止パス確認 → 未接触
$ git diff --name-only | grep -E '^(core|\.github|data)/|ledger'
（出力なし）

# .grok 確認
$ find .grok -type f
（ファイルなし）

# テスト（対象テスト）
$ pytest tests/test_update_readme.py tests/test_phase2_progress_docs.py -q
143 passed

# フルスイート
$ pytest tests/ -q
1882 passed
```

**stale wording 残存箇所（active current-state assertion ではない）:**
- README lines 695, 712, 733: 歴史的 Phase 1/2 セクション（当時の状態の正確な記録）
- `scripts/update_readme.py:135`: primary_attempts なしの場合の "Not yet executed"（そのシナリオでは正しい）
- テストのフィクスチャとコメント: synthetic ledger を使うシナリオの正当な記述

## 残存事項・注意点

- **data/ledger は変更していない**。
- **paid-credit workflow は実行していない**。
- **core / .github は変更していない**。
- **promote_approved=false は変更していない**（昇格引き続き未承認）。
- **README 歴史的セクション（lines 695-733 等）**は今回 scope 外。将来の docs cleanup タスクで整理可能。
- generator は `python scripts/update_readme.py` で常に最新 ledger 状態を反映する。

## Definition of Done

- [x] ledger evidence を編集前に確認した。
- [x] generator を修正し、README を generator 再実行で更新した（手動パッチではない）。
- [x] 対象テストを更新し、stale state を強制しないよう再スコープした。
- [x] 歴史的 Phase 2 docs（PHASE_2_PLAN.md アサーション）は有効性を維持した。
- [x] data / ledger を編集していない。
- [x] workflow を実行していない。
- [x] core / .github を編集していない。
- [x] `promote_approved=false` を「promotion 未承認」として維持した。
- [x] 実際の PR 番号で報告書を作成した（実 PR 番号確認後に filename 更新）。
- [x] `pytest tests/ -q` → 1882 passed（green）。
