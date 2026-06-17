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
| `data/project_state.json` | 更新（state reconcile） |
| `docs/PROJECT_STATE.md` | 更新（human-readable SSOT） |
| `tests/test_project_state_sync.py` | 更新（stale 期待値を修正） |
| `docs/task_reports/TASK_REPORT_state_reconcile_2026-06-17.md` | 新規（本ファイル） |

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

## 後検証結果

```
pytest tests/test_project_state_sync.py -q  →  22 passed
pytest tests/test_workflow.py -q            →  145 passed
pytest tests/ -q                            →  2170 passed, 5 warnings
git diff --name-only                        →  data/project_state.json
                                               docs/PROJECT_STATE.md
                                               tests/test_project_state_sync.py
```

---

## ledger を正典として扱ったことの確認

- `data/api_usage_ledger.json` は一切編集していない
- ledger のカウント（8 件）を正典とし、`project_state.json` の宣言値をそれに合わせた
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
