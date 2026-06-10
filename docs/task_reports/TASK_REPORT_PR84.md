# タスク完了報告 — PR #84

## 概要

paid-credit 3 run（2026-06-03/04）が API success（HTTP 200＋トークン記録）にもかかわらず有効な mutation patch を生成できなかった propose/output-contract 失敗の根本原因を特定・文書化し、no-API / no-promotion の範囲で出力契約を強化した。Gemini 呼び出し・workflow_dispatch・ledger 編集・昇格は一切行っていない。

## Canonical Source Evidence

| 正本 | 確認結果 |
|---|---|
| `data/project_state.json` | `state_id=phase3_paid_credit_api_success_patch_not_produced` / success 3件 / `valid_mutation_patch_produced=false` / apply・evaluate・promote 全て false / `promote_approved=false` / `next_action=fix_propose_output_contract_before_new_paid_credit_run` — タスクプロンプトの期待状態と完全一致 |
| `docs/PROJECT_STATE.md` | §1–§7 が上記と一致。API success の意味（API/token success のみ）と `promote_approved=false` の意味（昇格未承認≠API未実行）を確認 |
| `data/api_usage_ledger.json` | 7レコード（読み取りのみ）。records 5–7 が `gemini-3-flash-preview` / `gemini_paid_credit` / `success=true`（出力 590/562/561 トークン） |
| `docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` | 3 run の propose ログエラー（全件同一）と patch_exists=false / 各 job skip 状況を確認 |

## Root Cause Summary

全3 run の propose ログエラーは同一：
`replacement_code is not valid Python syntax: expected an indented block after function definition on line 1 (<unknown>, line 3)`

- 失敗時点の main SHA（`90d39c86` 等）の検証ラッパーをローカル再現した結果、**モデルが返した `replacement_code` の1行目がカラム0（無インデント）の場合に行番号まで完全一致**するエラーが再現される（モデル自身が `def` を出力したケースも同一エラー）。
- 失敗時点のシステムプロンプトは `replacement_code` を「Python code string for the function body only (no def statement)」としか説明しておらず、**インデント要件・body-fragment 例・空 body 禁止・markdown 禁止が一切なかった**（出力契約のモデル側伝達が未整備）。検証側は設計どおり fail-closed に動作し、patch は書かれなかった。
- 契約ハードニングの大部分（FORMAT CONTRACT・GOOD/BAD例・チェック5/7–11）は失敗 run 後の 2026-06-04〜06-07 に main へマージ済み（commits `94a6561`…`7b28eb6`）。それ以降 paid-credit run は未実行。
- 詳細：`docs/audit_gate/PROPOSE_OUTPUT_CONTRACT_ROOT_CAUSE.md`

## Changed Files

| ファイル | 変更 |
|---|---|
| `scripts/propose_mutation.py` | プロンプト義務追記（構文妥当性・placeholder ellipsis 禁止）＋冗長2項目の同義圧縮＋`_parse_and_validate_response` の stage 診断追加。検証チェック1–11は無変更 |
| `tests/test_propose_output_contract.py` | 新規（27テスト、全てローカル・no-API） |
| `docs/audit_gate/PROPOSE_OUTPUT_CONTRACT_ROOT_CAUSE.md` | 新規（根本原因文書、AI_DOC_META 付き） |
| `data/project_state.json` | `state_id` / `next_action` のみ PR #84 後の状態へ最小更新（Owner 指示。historical facts は不変） |
| `docs/PROJECT_STATE.md` | Current state table と §7 Next action を同義に更新 |
| `scripts/update_readme.py` | `_NEXT_ACTION_TEXT` に新 `next_action` キーのマッピングを追加（Owner 指示。旧キーは保持） |
| `README.md` | `python scripts/update_readme.py` で再生成（手編集なし。Next Focus 行＋更新時刻のみ変化） |
| `docs/task_reports/TASK_REPORT_PR84.md` | 本報告 |

## Implementation Details

1. **プロンプト義務の明示化**（`_LLM_SYSTEM_PROMPT`）
   - REQUIRED に追加：「replacement_code must be syntactically valid Python as a function body — it is checked with ast.parse() and ANY SyntaxError is rejected fail-closed (no patch is written).」
   - FORBIDDEN に追加：「Do NOT use placeholder ellipsis: a body whose only statement is ... is rejected.」
   - 既存テスト `test_paid_credit_ledger_uses_output_token_cap_not_char_reestimate`（scope 外で編集不可）が実プロンプト長連動のコスト閾値 `< $0.005` を持ち、**変更前の余裕が約16文字しかなかった**ため、冗長な2項目（nested return の説明・fallthrough 禁止項目の重複説明）を意味を保って圧縮し、システムプロンプトを正味短縮（8318→8204文字）。コスト試算 0.0049936→0.004948 で余裕を拡大。
2. **Stage 診断**（`_parse_and_validate_response`）
   - JSON parse / schema / replacement_code の3拒否経路すべてに `propose/output-contract failure — the Gemini API call succeeded; the model output was rejected before any patch was written` を付加。ledger `success=true`＋propose 失敗が API 失敗と誤読される再発を防止。既存プレフィックス（`Gemini replacement_code validation failed` 等）は保持。
3. **スキーマ変更なし**：現行スキーマに no-patch/abstain フィールドはなく、新スキーマ発明はタスクの forbidden remediation のため見送り（根本原因文書の Rejected strategies に記録）。

## Tests Added / Updated

`tests/test_propose_output_contract.py`（新規・27テスト）：

1. 歴史的失敗形状の証拠ピン留め：カラム0 body／モデル出力 def が**失敗時点ラッパーで run ログと同一エラー（line 3）を再現**することを検証
2. 同形状が現行バリデータで明確な診断（indentation contract violation / function definition 禁止）により拒否されること
3. 空 body／コメントのみ／pass-only／**ellipsis-only**／markdown フェンス付き出力の拒否（修復・自動補完なし）
4. 有効な fixture と `_SAMPLE_MUTATION` が契約パスを通過すること
5. プロンプトが各義務（構文妥当性・空body禁止・pass-only禁止・ellipsis禁止・markdown禁止・4スペース契約・def禁止・JSON only）を明示し、実 genome/detector で `max_prompt_chars` ゲート内に収まること
6. 3拒否経路すべての診断が `propose/output-contract failure` と `API call succeeded` を含み、`API call failed` を含まないこと

## Verification Results

```
pytest tests/test_propose_output_contract.py -q          → 27 passed
pytest tests/test_gemini_integration.py tests/test_gemini_paid_credit.py \
       tests/test_gemini_error_diagnostics.py tests/test_mutation_boundaries.py -q
                                                          → 510 passed
pytest tests/ -q（SSOT 最小更新後に再実行）                → 1920 passed
python -m json.tool data/project_state.json               → VALID
python scripts/update_readme.py                           → README status block updated
                                                            （diff は Next Focus 行＋更新時刻のみ）
git diff --name-only | grep -E '^(\.github|core)/|data/api_usage_ledger.json|ledger'
                                                          → no match（CLEAN）
git grep（stale current-state 表現の回帰チェック）          → ヒットは PROJECT_STATE.md §4 の「❌ Incorrect」表
                                                            と過去 task report の歴史的引用のみ（current-state 主張なし）
```

## No-API / No-Promotion Confirmation

- `data/api_usage_ledger.json` は編集していない（読み取りのみ）。
- `workflow_dispatch` は実行していない。
- Gemini API call は行っていない（全テストはローカル・モック／fixture のみ）。
- paid-credit run は実行していない。
- いかなる candidate も昇格していない。
- `promote_approved` は false のまま。
- 既存 paid-credit 3 run において apply / evaluate / promote は到達していない（本PRはその事実を変更しない）。

## Canonical State Update

**PR #84 後の状態へ最小更新を実施**（当初は README ジェネレータ（FROZEN）との結合を理由に見送ったが、Project Owner が 2026-06-10 に `scripts/update_readme.py` の `_NEXT_ACTION_TEXT` 追加と README 再生成を含めて明示承認・指示したため実施）：

| 項目 | 変更前 | 変更後 |
|---|---|---|
| `state_id` | `phase3_paid_credit_api_success_patch_not_produced` | `phase3_propose_output_contract_hardened_pending_owner_review` |
| `next_action` | `fix_propose_output_contract_before_new_paid_credit_run` | `review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun` |

- `docs/PROJECT_STATE.md` の Current state table・§7 を同義に更新：PR #84 で no-API / no-promotion の propose/output-contract hardening が実装されたこと、**新規 paid-credit run は未実行**であること、次は **Project Owner が PR #84 の修正内容を確認**して owner-approved paid-credit rerun を判断すること、`promote_approved=false` 維持を明記。
- README は `python scripts/update_readme.py` で再生成（Next Focus 行が新 `next_action` の自然文に変化）。
- **historical facts は一切変更していない**：paid-credit API success records = 3 / `valid_mutation_patch_produced=false` / apply・evaluate・promote reached = false / `promote_approved=false`。
- 更新目的：旧 `next_action` のままだと、次スレッドで正本を読んだ AI が同じ root-cause 修正タスクを再提案してループするため。

## Residual Risk

1. **ライブ検証は未実施（設計どおり）**：本修正＋既存ハードニングが実際の Gemini 出力を改善するかは、Owner 承認の次回 paid-credit run まで検証できない。run-time の生レスポンスは意図的に保存されないため、根本原因はH1（カラム0 body）/H3（モデル出力 def）の区別までは確定できない（どちらも同一契約違反クラスで、現行バリデータ・プロンプトの両方で対処済み）。
2. **コスト閾値テストの脆弱性（既存・scope 外）**：`tests/test_gemini_paid_credit.py` の `< $0.005` 固定閾値はシステムプロンプト長に直結しており、本PR前の余裕は約16文字だった。本PRで余裕を約750文字相当に拡大したが、将来のプロンプト追記で再発し得る。閾値の余裕設計の見直しは別タスク（Owner 判断）を推奨。
3. **`docs/audit_gate/CHANGELOG.md` 未更新**：許可 scope 外のため未編集。本件の教訓（出力契約はモデル側への伝達とテストで固定する）の CHANGELOG 追記要否は Owner 判断。
4. **CLAUDE.md の派生サマリ**：CLAUDE.md の「現在の状態」表は旧 `state_id` を含む派生サマリのまま（Owner 指示の最小修正5項目に含まれないため未編集）。CLAUDE.md 自身が「矛盾があれば `docs/PROJECT_STATE.md` / `data/project_state.json` が優先」と定めており実害はないが、次回の CLAUDE.md 更新時に同期を推奨。

## Next Recommended Action

1. Project Owner が本PR（#84）と `docs/audit_gate/PROPOSE_OUTPUT_CONTRACT_ROOT_CAUSE.md` をレビュー・承認・マージする。
2. 承認後、次回 owner-approved paid-credit rerun の実行可否を Owner が判断する（本PRは run を実行しない。6月予算残 ≈ $9.89 はインベントリ §12 参照）。

## Definition of Done

- [x] `pytest tests/test_propose_output_contract.py -q` green（27 passed）
- [x] `pytest tests/ -q` green（1920 passed）
- [x] 禁止パス（`.github/**` / `core/**` / ledger / `data/genome.json`）に変更なし
- [x] 根本原因文書に必須11セクション＋Rejected strategies 5項目を記載
- [x] no-API / no-promotion 保証を本報告と PR 本文に明記
- [x] PR #84 作成・`@codex Review` 依頼
