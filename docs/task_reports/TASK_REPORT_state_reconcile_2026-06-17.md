# タスク完了報告 — state reconcile 2026-06-17

## 概要

2026-06-17 の paid-credit run (GitHub Actions run id 27683267711) が `data/api_usage_ledger.json`
に新たな API 成功レコードを追記した結果、ledger の primary-model 成功件数が 8 件になった。
一方 `data/project_state.json` の宣言値は 7 件のままだったため CI が失敗した。
本 PR は project state / docs を ledger の正典に合わせて整合させる。

---

## CI 失敗の根本原因

- **テスト**: `tests/test_project_state_sync.py::test_project_state_matches_ledger_success_count`
- **原因**: `data/project_state.json` の `paid_credit_api_calls.gemini_3_flash_preview_success_records` が `7` を宣言していたが、ledger には 8 件の `provider=gemini`, `api_mode=gemini_paid_credit`, `model=gemini-3-flash-preview`, `success=true` レコードが存在した。

---

## 変更ファイル一覧

| ファイル | 変更区分 |
|---|---|
| `data/project_state.json` | 更新（state reconcile + evidence attribution 修正） |
| `docs/PROJECT_STATE.md` | 更新（human-readable SSOT + machine evidence 分離） |
| `tests/test_project_state_sync.py` | 更新（stale 期待値を修正） |
| `scripts/update_readme.py` | 更新（run 8 recovery state の README 生成ロジック追加） |
| `tests/test_update_readme.py` | 更新（run 8 recovery state のテスト追加） |
| `README.md` | 更新（`scripts/update_readme.py` による status block 再生成） |
| `docs/task_reports/TASK_REPORT_state_reconcile_2026-06-17.md` | 新規 / 更新（本ファイル） |

---

## 主な変更内容

### data/project_state.json

| フィールド | 変更前 | 変更後 | 理由 |
|---|---|---|---|
| `state_id` | `phase3_generation_invariant_score_migrated_await_owner_approved_rerun` | `phase3_run8_adoption_gate_passed_promote_push_failed_await_owner_recovery` | run 8 の状態を正確に反映 |
| `paid_credit_api_calls.gemini_3_flash_preview_success_records` | `7` | `8` | ledger の正典に合わせる |
| `paid_credit_api_calls.adoption_gate_ever_passed` | `false` | `true` | run 8 が adoption gate を初めて通過 |
| `paid_credit_api_calls.promote_reached` | `false` | `true` | run 8 が promote ステージに到達 |
| `paid_credit_api_calls.run_7_triage` | 存在せず | 追加（`api_token_success_only`, untriaged） | 7 件目レコード (2026-06-16T06:20) の未トリアージ状態を明記 |
| `paid_credit_api_calls.run_8_triage` | 存在せず | 追加（`promote_push_failed`） | run 8 の分類を記録 |
| `next_action` | `generation_invariant_score_migrated_await_owner_approved_rerun_review` | `owner_audited_candidate_recovery_after_run8_promote_push_failure` | 次アクションを正確に反映 |
| `note` | 7 件・promote 未到達を記述 | 8 件・run 8 push 失敗・candidate 未昇格を記述 | 実態に合わせる |

### run_8_triage 分類詳細

- GitHub Actions run id: `27683267711`
- 失敗箇所: Promote Candidate / Commit promoted changes
- apply: 到達・成功
- evaluate: 到達・成功
- adoption gate: **通過（初回）**
- promote: 到達。`promote_candidate.py` はローカルで成功、README 更新も成功
- 最終 push 失敗: `persist-ledger` が API usage ledger をコミットした後に `main` が進んでいたため non-fast-forward エラー（push-race 条件）
- candidate は `main` に昇格しなかった
- push-race ハードニングは PR #115 で別途対応済み
- `is_tool_failure: true`（evaluate rejection ではない）

### docs/PROJECT_STATE.md

- success records カウントを **7 → 8** に更新
- adoption gate / promote reached の状態を更新
- run 7（untriaged）と run 8（`promote_push_failed`）の行を追加
- machine evidence テーブルを 8 件に更新
- セクション 3 に run 7・run 8 の説明を追加
- セクション 6 に run 8 の apply/evaluate/adoption gate/promote 状態を追加
- セクション 7 の Next action を「Owner-audited candidate recovery after run 8 promote push failure」に更新

### tests/test_project_state_sync.py（stale 期待値のみ修正）

| テスト | 変更内容 |
|---|---|
| `test_project_state_matches_ledger_success_count` | `actual == 7` → `actual == 8` |
| `test_evaluate_reached_and_promote_not_reached` | `adoption_gate_ever_passed is False` → `is True`; `promote_reached is False` → `is True` |
| `test_project_state_doc_shows_6_success_records` | `"**7**"` → `"**8**"` |
| `test_state_id_is_generation_invariant_score_migrated` | state_id を新しい値に更新 |
| `test_next_action_is_generation_invariant_score_migrated_review` | next_action を新しい値に更新 |

---

## Codex Review P2 対応（コミット 2 — fix(state): handle run8 recovery state in generated docs）

### P2-1: README generator への run 8 recovery state 対応

**問題**: `scripts/update_readme.py` の `_apply_project_state` が `adoption_gate_ever_passed=True`
のブランチを持っておらず、`_NEXT_ACTION_TEXT` に
`owner_audited_candidate_recovery_after_run8_promote_push_failure` のエントリもなかった。
結果として README が汎用的な「post-run result review pending」に落ちた。

**修正内容** (`scripts/update_readme.py`):
- `_NEXT_ACTION_TEXT` に新エントリを追加:
  「Owner-audited candidate recovery after run 8 promote push failure — run 8 passed adoption gate;
  promote was reached; final push failed (push-race; PR #115 hardened); candidate not promoted to main;
  no new paid-credit rerun required as immediate next step」
- `_apply_project_state` に `promote_reached` 変数を追加
- `current_phase` の `elif` に `adoption_gate_ever_passed=True` ブランチを追加:
  「Phase 3 — run 8 passed adoption gate; promote reached; promote push failed (push-race — PR #115 hardened);
  candidate not promoted; owner-audited recovery pending」
- `promote_note` の `elif` に `adoption_gate_ever_passed=True` ブランチを追加:
  「false (promotion not approved — promote push failed; candidate was not promoted; owner-audited recovery pending)」

**新規テスト** (`tests/test_update_readme.py` — `TestPhase3Run8RecoveryState` クラス、9 件):
- `test_next_focus_says_owner_recovery` — next_focus に「Owner-audited candidate recovery」が含まれる
- `test_next_focus_mentions_promote_push_failure` — 「push failed」が含まれる
- `test_next_focus_says_candidate_not_promoted` — 「not promoted」が含まれる
- `test_next_focus_no_new_paid_credit_rerun_required` — 「no new paid-credit rerun required as immediate next step」が含まれる
- `test_current_phase_reflects_adoption_gate_passed` — 「adoption gate」と「promote」が含まれる
- `test_no_generic_post_run_review_wording` — 汎用的な fallback 文言が現れない
- `test_promote_note_does_not_say_gate_never_passed` — 誤った「no candidate has passed the adoption gate」が現れない
- `test_promote_note_says_push_failed_and_not_promoted` — push failure と not promoted が含まれる
- `test_promote_approved_is_false` — promote_approved=false が正しく表示される

**README.md の更新**: `scripts/update_readme.py` を実行し status block を再生成。変更は status block
内のみ（Current Phase / Next Focus / promote_approved 文言の更新、Executed count 8 反映、
Best Score / Last Updated の genome.json 由来の更新）。

---

### P2-2: machine evidence attribution の修正

**問題**: `docs/PROJECT_STATE.md` の ledger 行が run 8 の adoption gate / promote / push failure
をまとめて記述しており、ledger がステージ結果を証明しているかのように見えた。

**修正内容** (`docs/PROJECT_STATE.md`):
- ledger 行を API/token 成功件数・タイムスタンプ・コストフィールドのみを証明するように書き直し
- 明示的な注記を追加: 「Proves API/token success count and timestamp/cost fields only. Does not prove
  apply, evaluate, adoption-gate, or promote stage outcomes — do not infer stage results from ledger
  success alone.」
- GitHub Actions (run 8, id 27683267711, 2026-06-17) の新行を追加: apply/evaluate/adoption-gate/
  promote/push-race の各ステージ結果を GHA ジョブログ / run context に帰属
- `data/project_state.json` ミラー注記を更新: 「Stage outcomes (apply/evaluate/adoption-gate/promote)
  are derived from GitHub Actions job logs and artifact triage, not from the ledger alone.」

**data/project_state.json** の `run_8_triage.evidence_source` を更新:
- 変更前: `"task description / PR context (run id 27683267711)"`
- 変更後: `"GitHub Actions run 27683267711 job/artifact triage; ledger proves API/token success count only"`

---

## 後検証結果（P2 対応後）

```
pytest tests/test_project_state_sync.py -q  →  22 passed
pytest tests/test_update_readme.py -q       →  125 passed (9 新規テスト含む)
pytest tests/test_workflow.py -q            →  145 passed
pytest tests/ -q                            →  2179 passed, 5 warnings
git diff --name-only                        →  README.md
                                               data/project_state.json
                                               docs/PROJECT_STATE.md
                                               scripts/update_readme.py
                                               tests/test_update_readme.py
```

---

## ledger を正典として扱ったことの確認

- `data/api_usage_ledger.json` は一切編集していない
- ledger のカウント（8 件）を正典とし、`project_state.json` の宣言値をそれに合わせた
- ledger はAPI/token 成功カウントのみを証明するものとして扱い、ステージ結果（apply/evaluate/
  adoption gate/promote）は GHA ジョブログ / artifact triage に帰属させた
- genome (`data/genome.json`) は編集していない
- evolution_history (`data/evolution_history.json`) は編集していない

---

## 実施しなかったことの確認

- Gemini API 呼び出しなし
- workflow_dispatch なし
- paid-credit run なし
- candidate の復元・昇格なし
- detector / genome / evolution_history の変更なし
- `data/api_usage_ledger.json` の編集なし
- force push なし
- マージなし

---

## 残存事項・注意点

- run 7 (2026-06-16T06:20:37, untriaged) は本 PR でトリアージしていない。API/token 成功のみ。別途トリアージが必要な場合は別 PR で対応する。
- run 8 の candidate 復元は本 PR のスコープ外。候補の回復は別の将来 PR で Owner 判断のもと実施する。
- `promote_approved` は `false` のまま。候補が `main` に昇格するためには adoption gate 通過後に Project Owner の明示承認が必要。
