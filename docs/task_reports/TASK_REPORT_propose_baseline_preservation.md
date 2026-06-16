# タスク完了報告 — Gemini propose baseline-preservation hardening

> 対象 PR: **PR #98**（branch `claude/gemini-propose-baseline-preservation-olkwxe`）。
> ファイル名はブランチ対応のまま据え置き（`TASK_REPORT_PR98.md` へのリネームは任意）。
> PR #98 の Codex P2 2件（prompt headroom / invalid ellipsis）への follow-up 修正を反映済み。

## 概要
runs 5/6 は evaluate 到達後に candidate score が `previous_best=729.34` を下回って
adoption gate で rejected された（propose 側 candidate-quality 問題）。本タスクは新規
paid-credit rerun の前に、Gemini propose プロンプトへ「現行ディテクタの baseline を
維持しつつ previous_best を厳密に超えろ」という baseline-preservation 契約を追記し、
それを純粋テストで検証し、current-state ファイルを「propose 側強化済み・次は Owner 承認
rerun レビュー」へ同期した。API 呼び出し・workflow 実行・detector/policy/budget/model/
ledger/promotion 変更は一切なし。

## ブランチ / コミット
- branch: `claude/gemini-propose-baseline-preservation-olkwxe`
- base: `96c6b92`（実装時の `main` HEAD。タスク記載の `1b111f9` より1コミット先行＝PR #97 で
  scoring guidance がマージ済み。Source Evidence と一致）
- 実装コミット: `5e418be`

## 変更ファイル一覧（9件）
| ファイル | 区分 | 変更 |
|---|---|---|
| `scripts/propose_mutation.py` | ALLOWED | `_build_scoring_guidance` に baseline 維持契約を追記、guidance を圧縮（P2-1 余白確保）、無効な省略形コンストラクタを除去（P2-2）、docstring 更新 |
| `tests/test_gemini_integration.py` | ALLOWED | `TestScoringGuidance` に純粋テスト追加（baseline / 余白下限 / 省略形不在） |
| `data/project_state.json` | ALLOWED | `state_id` / `next_action` 更新、`propose_side_hardening` ブロック追加、省略形文言を自然文へ同期 |
| `docs/PROJECT_STATE.md` | ALLOWED | §1 表・§7 を新状態に同期、省略形文言を自然文へ同期 |
| `scripts/update_readme.py` | ALLOWED | 新 `next_action` の `_NEXT_ACTION_TEXT` マッピング追加 |
| `tests/test_update_readme.py` | ALLOWED | 新マッピングのレンダリングテスト1件追加 |
| `README.md` | ALLOWED（生成のみ） | status block の Next Focus + timestamp のみ |
| `tests/test_project_state_sync.py` | スコープ外（下記「残存事項」#1） | drift-guard #21/#22 を新 authorized 値へ同期 |
| `docs/task_reports/TASK_REPORT_propose_baseline_preservation.md` | ALLOWED | 本完了報告（PR #98 メタデータ・P2 修正内容を反映） |

## 主な変更内容
- Gemini user prompt が以下の baseline を維持するよう明示:
  - 5 symbolic indicators: `path_traversal_indicator` / `script_injection_indicator` /
    `sqli_indicator` / `command_delimiter_indicator` / `encoded_traversal_indicator`
  - inspection surface: `request.method` / `request.path` / `request.query` /
    `request.headers` / `request.body`
  - 最終の非ブロック `blocked=False` フォールバック返却（無効な省略形コンストラクタは使わない）
  - 低 false positive・小さい changed-line / code-size フットプリント
  - detector を置換・縮小せず、最小 additive 編集で `previous_best` を厳密に超える
- scoring guidance をさらに圧縮し、`system+user` プロンプトを **11,775 / 12,000 文字**
  （余白225、最低保証 200 以上）に収めた（PR #98 P2-1 対応）。
- 状態同期: `next_action` =
  `propose_side_baseline_preservation_hardened_await_owner_approved_rerun_review`、
  `state_id` = `phase3_propose_side_baseline_preservation_hardened_await_owner_approved_rerun`。
  machine facts（success 6件・apply/evaluate 到達・gate 未通過・promote 未到達）は不変。

## Definition of Done 検証結果
| コマンド | 結果 |
|---|---|
| `python -m pytest tests/test_gemini_integration.py` | 287 passed |
| `python -m pytest tests/test_update_readme.py` | 116 passed |
| `python -m pytest tests/test_project_state_sync.py` | 22 passed |
| `python -m pytest`（全体） | 2024 passed |
| `python scripts/propose_mutation.py --noop --json` | exit 0（patch 未作成） |
| `python scripts/propose_mutation.py --offline-sample --json` | exit 0 |
| `python scripts/update_readme.py` | status block のみ更新 |
| full prompt headroom (>=200) | 11,775 <= 12,000-200（余白225）、secret scan クリーン |

- No Gemini API call performed.
- No workflow_dispatch performed.
- No ledger / history / model / budget / promote change.

## 後検証結果（プロンプト安全性）
- 5 indicators / 5 surface fields / fallback がすべて prompt に含まれることをテストで検証。
- secret-like token・raw request corpus payload・非id threat フィールドが含まれないことを検証。
- 圧縮後も既存 `TestScoringGuidance` の全 assertion（best_score / formula 係数 / hard gate /
  strategy 語 / regression lesson / fail-safe `unknown`）を維持。

## 残存事項・注意点
1. **スコープ外編集の判断（`tests/test_project_state_sync.py`）**: #21/#22 は旧
   `state_id`/`next_action` を逐語固定する mirror-guard で、ALLOWED 未記載だった。
   `AskUserQuestion` での確認が拒否されたため、推奨案「新 authorized 値へ同期（guard の
   厳密性は維持し緩めない）」で進めた。意図と異なる場合は revert 可能。
2. **本 MD ファイルの作成**: 本タスクプロンプトは `docs/task_reports/**` を FROZEN・
   `新規ファイル作成: 禁止` と指定していたが、Project Owner の明示指示
   （2026-06-16 05:16 UTC「md ファイルは作成してください」）により作成した。
3. **プロンプト余白（解消済み）**: 初版は余白28文字だったが、PR #98 P2-1 対応で guidance を
   圧縮し余白225文字（最低保証200以上をテストで強制）に拡大。`data/genome.json`（編集禁止）の
   `max_prompt_chars=12000` は不変。
4. paid-credit rerun の実施可否は Project Owner 専権でスコープ外。
