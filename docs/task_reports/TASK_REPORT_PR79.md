# タスク完了報告 — PR #79

## 概要

Phase 3 の state wording を `data/api_usage_ledger.json` の primary evidence に一致させる docs / control-plane 限定の修正。
`gemini-3-flash-preview` / `gemini_paid_credit` の paid-credit API call **success 記録は既に存在する**こと、`promote_approved=false` は「昇格未承認」であって「API call 未実行」ではないこと、次のアクションは新規 paid-credit run ではなく既存 run 結果のレビュー / inventory であることを反映した。実装・workflow・ledger・test・generator の変更は一切なし。

## 変更ファイル一覧

| ファイル | 区分 | 内容 |
|---|---|---|
| `CLAUDE.md` | 変更 | 「現在の状態」テーブルを ledger evidence に合わせて修正（Phase / Gemini API 行、`promote_approved` / `Next focus` 行を追加） |
| `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` | 変更 | stale な current-state 主張（controlled run 未実行 / Not yet executed / 「workflow_dispatch を 1 回だけ実行」）を success 記録ベースの記述に修正。次の Project Owner 手順を「既存 run 結果レビュー」に書き換え |
| `README.md` | **変更なし** | 後述の理由により意図的に未変更 |
| `docs/task_reports/TASK_REPORT_PR79.md` | 新規 | 本報告書 |

## 主な変更内容

### CLAUDE.md
- `Phase`: 「Phase 2.5 完了 / Phase 3 Go-No-Go 待ち」→「Phase 3 — paid-credit API call の success 記録が存在。post-run result review が未着手」
- `Gemini API`: 「未接続（Phase 3 activation 待ち）」→「paid-credit path で接続済み。`gemini-3-flash-preview` / `gemini_paid_credit` の success 記録が `data/api_usage_ledger.json` に存在」
- `promote_approved`（新規行）: 「`false` — 昇格は未承認。API call が未実行という意味ではない」
- `Next focus`（新規行）: 「既存 paid-credit run の結果レビュー：ledger / candidate / apply / evaluate / promotion decision」
- 日付を 2026-06-07 → 2026-06-08 に更新

### docs/PHASE_3_GO_NO_GO_CHECKLIST.md
- AI_DOC_META `scope` の "first paid-credit run pending" を success 記録存在＋post-run review pending に修正
- 冒頭バナー / 「2a. Phase 3 Activation Record」バナーの「controlled run は未実行」を success 記録存在に修正
- 表の `Gemini 3 Flash Preview controlled run | Not yet executed` を `Success records exist` に修正
- 「次の Project Owner 手順」を「paid-credit run を 1 回だけ実行」から **既存 run 結果のレビュー / inventory**（ledger 確認 → candidate/artifacts → apply/evaluate → promote/fix/halt 判断 → `promote_approved=false` 維持）に書き換え
- フッター署名を current state（activation merged / success 記録存在 / `promote_approved=false` / post-run review pending）に更新
- **保持**: 原文の Go/No-Go gate language ブロック（"This document is not Phase 3 activation." / "Phase 3 is not started…" / "API is not connected…" / "live_model_enabled must remain false…" / "Project Owner explicit approval is required…"）は historical pre-activation gate text として明示的にラベル付けした上で保持。`tests/test_phase3_go_no_go_checklist_docs.py` が要求する invariant phrase であり、削除すると test が失敗するため。

### README.md（意図的に未変更）
README の Phase 3 wording は **frozen test と generator により legacy wording が pin されている**ため、ledger 準拠の修正には scope 外の test / generator 変更が必要。よって本 PR では未変更とし、別途 Project Owner 承認のフォローアップ（generator + test メンテナンス）タスクとして報告する。根拠:
- `scripts/update_readme.py:121` — `Current Phase` 行に "…Gemini 3 Flash Preview run pending" がハードコードされている（generator-managed、`scripts/**` は FROZEN）。
- `scripts/update_readme.py:135-149` — generator は ledger を読み、`gemini-3-flash-preview` の paid-credit success 記録が存在する場合 `Phase 3 First Paid-Credit Run` 行を "Executed (3 successful / 3 attempt(s))" として生成する（= generated block 内の "Not yet executed" は再生成すると変化する状態）。
- ところが `tests/test_update_readme.py:603-607`（`test_real_readme_block_shows_first_run_pending`）が **live README** の status block に "Not yet executed" または "first run pending" を要求しているため、generated block を再生成すると frozen test が失敗する。
- さらに `tests/test_phase2_progress_docs.py:531-623` が README に「Phase 3 not started」「未接続 / not connected」「live_model_enabled … false」の保持を要求しており、README prose の legacy wording も同 frozen test 群に pin されている。
- 結論: README の Phase 3 wording 修正は `scripts/update_readme.py` と上記 frozen test 群の変更を要する。これは本タスクの ALLOWED scope 外であり、Evidence F / 4.3 の "generator maintenance must be a separate Project Owner-approved task" に該当する。

## Source Evidence

すべてローカル実ファイルで確認済み（プロンプトを信用せず一次ソース照合）。

- **Evidence A — main state**: `git rev-parse HEAD` = `bde92491299d500e792083a0cc06ec2ab22b21b4`（PR #78 merge commit）、`origin/main` と一致。working tree clean。branch = `claude/phase-3-state-wording-FdSx1`。
- **Evidence B — ledger primary evidence**: `data/api_usage_ledger.json` に `api_mode="gemini_paid_credit"` / `model="gemini-3-flash-preview"` / `success=true` の記録が 3 件存在（timestamp `2026-06-03T23:36:37`, `2026-06-04T00:34:12`, `2026-06-04T01:33:29`）。加えて `gemini-3.1-flash-lite` success × 1。→ 「gemini-3-flash-preview paid-credit API call は既に成功している」。
- **genome**: `data/genome.json` → `live_model_enabled=true`、`api_mode="gemini_paid_credit"`、`model_name="gemini-3-flash-preview"`。
- **Evidence C — audit protocol**: `docs/audit_gate/PR_AUDIT_PROTOCOL.md` が docs claim を `data/api_usage_ledger.json` 等の primary evidence と照合することを要求している（参照のみ・未編集）。
- **Evidence D — CLAUDE.md stale wording**: `CLAUDE.md:39`「Phase 3 Go-No-Go 待ち」、`:42`「Gemini API | 未接続」を確認 → 修正済み。
- **Evidence E — checklist stale wording**: `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` の冒頭バナー / 2a / 表 / 次手順の stale wording を確認 → 修正済み。
- **Evidence F — README generator gate**: 上記「README.md（意図的に未変更）」の通り、generator + frozen test pin を確認 → 未変更で follow-up 報告。
- **裏付け**: PR #78 本文および `docs/audit_gate/POST_PR77_UNRESOLVED_BACKLOG.md:219-228` が本タスク（docs-only Phase 3 state correction）を recommended next PR として明示している。

## 後検証結果

```
# 変更ファイル（2 ファイルのみ）
$ git diff --name-only
CLAUDE.md
docs/PHASE_3_GO_NO_GO_CHECKLIST.md

# stale active-claim grep（CLAUDE.md / checklist）→ 残存なし
$ git grep -n "Gemini API 未接続|Phase 3 activation 待ち|Phase 3 Go-No-Go 待ち|controlled run.*未実行|Not yet executed|first paid-credit run pending|workflow_dispatch.*once|paid-credit run を 1 回だけ実行" -- CLAUDE.md docs/PHASE_3_GO_NO_GO_CHECKLIST.md
（出力なし）

# forbidden path check → 触れていない
$ git diff --name-only | grep -E '^(core|scripts|tests|\.github|data)/|ledger'
（出力なし）

# .grok 再導入なし
$ find .grok -type f
（ファイルなし）

# テスト
$ pytest tests/ -q
1882 passed
```

## 残存事項・注意点

- **README.md は未変更**（理由は上記 Source Evidence / 4.3 参照）。README の Phase 3 wording を ledger 準拠にするには `scripts/update_readme.py:121` の "run pending" ハードコード修正と、`tests/test_update_readme.py:603-607` / `tests/test_phase2_progress_docs.py:531-623` の frozen test 更新が必要。**Project Owner 承認の別タスク**として切り出すことを推奨。
- checklist の歴史的 gate language ブロックは test invariant のため保持。stale wording ではなく "historical pre-activation gate text" として明示ラベル済み。
- **No data / ledger changes.**
- **No paid-credit workflow execution.**（workflow_dispatch / gemini-paid-credit call 一切なし）
- **No core / scripts / tests / .github changes.**
- **`promote_approved=false` は変更していない**（昇格は引き続き未承認）。

## Definition of Done

- [x] `data/api_usage_ledger.json` の primary evidence を編集前に確認した。
- [x] CLAUDE.md / checklist から active な「Gemini API 未接続」「controlled run 未実行」「workflow_dispatch を 1 回だけ実行」主張を除去した。
- [x] 昇格承認済み（promotion approved）とは主張していない。`promote_approved=false` を維持。
- [x] paid-credit workflow を実行していない。
- [x] data / ledger を編集していない。
- [x] core / scripts / tests / .github を編集していない。
- [x] README が generator-managed / frozen-test-pinned であることを確認し、未変更＋follow-up 報告とした。
- [x] 実際の PR 番号（#79）でタスク報告を作成した。
- [x] 次のアクションを「既存 run 結果のレビュー / inventory」に保った（新規 run ではない）。
- [x] `pytest tests/ -q` → 1882 passed（green）。
