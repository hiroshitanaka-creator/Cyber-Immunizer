# 実装完了レポート — Apply/Evaluate 失敗診断アーティファクト

---

## Summary

Apply/Evaluate のどの段階で失敗しても、失敗理由を machine-readable な JSON artifact として必ず残す仕組みを実装しました。fail-closed の安全性・既存の adoption gate・promotion 条件・budget/ledger 制約はすべて維持しています。

---

## Files Changed

| ファイル | 変更内容 |
|---|---|
| `scripts/apply_mutation.py` | `--report PATH` CLI オプション追加、`_write_apply_report_atomic()` 実装、全エラー経路に `replacement_code_sha256` / `mutation_rationale` / `target_threats` を含むスキーマ追加 |
| `scripts/evaluate_candidate.py` | `--report PATH` CLI オプション追加、candidate-not-found ガード追加、AST validation 失敗経路への `_write_report()` 呼び出し追加、`stage: "evaluate_candidate"` フィールド追加 |
| `.github/workflows/immunization_loop.yml` | apply ステップに `--report` フラグ追加、`Upload apply report artifact`（`if: always()`）追加、evaluate ステップに `if: steps.apply.outcome == 'success'` 条件追加、artifact upload に `if-no-files-found: warn` 追加 |
| `tests/test_apply_mutation.py` | **新規** — 28 テスト（malformed patch, policy violation, success path, スキーマ検証, fail-closed write） |
| `tests/test_evaluate_candidate.py` | 追加 — 23 テスト（stage フィールド, candidate-not-found, AST failure, secrets 漏洩なし） |
| `tests/test_workflow.py` | 追加 — 12 テスト（apply-report artifact, evaluate スキップ条件, promotion gate 不変） |

---

## JSON Report Schemas

### apply_report.json

```json
{
  "stage": "apply_mutation",
  "success": false,
  "exit_code": 1,
  "candidate_path": null,
  "violations": ["string"],
  "error": "string",
  "mutation_rationale": "string | null",
  "target_threats": ["string"],
  "replacement_code_sha256": "string | null"
}
```

### fitness_report.json（失敗スキーマ）

```json
{
  "stage": "evaluate_candidate",
  "success": false,
  "passed_adoption_gate": false,
  "is_tool_failure": true,
  "timed_out": false,
  "candidate_hash": "string | null",
  "violations": ["string"],
  "error": "string",
  "metrics": null,
  "return_code": null
}
```

---

## Tests

```bash
# 対象テストのみ
python -m pytest tests/test_apply_mutation.py tests/test_evaluate_candidate.py tests/test_workflow.py -q
# → 197 passed

# フルスイート（既存の data 不整合テストを除外）
python -m pytest tests/ -q --ignore=tests/test_project_state_sync.py
# → 2055 passed
```

> `test_project_state_sync.py` の 1 失敗は本変更前から存在する既存データ不整合（ledger 7 件 vs 宣言 6 件）であり、本タスクスコープ外。

---

## Security Notes

| 項目 | 対応内容 |
|---|---|
| `replacement_code` 全文除外 | apply_report.json には sha256 ハッシュのみ含める。本文は含めない |
| Secrets 漏洩防止 | `_safe_env()` による subprocess 環境変数ストリップは変更なし。`GEMINI_API_KEY` 等は report に含まれない |
| Invalid candidate 実行禁止 | candidate-not-found ガードと AST validation 失敗は subprocess 起動前に fail-closed で返却 |
| fail-closed 維持 | `--report` の write 失敗は非ゼロ終了（隠さない） |
| Promotion gate 不変 | `passed_adoption_gate` / `promote_approved` / `workflow_dispatch` 条件は変更なし |

---

## Residual Risks

- `evaluate_candidate.py` の `_write_report()` 内の OSError は現在 silently drop される（atomic write 化はスコープ外）
- `test_project_state_sync.py` の既存データ不整合（ledger 7 件 vs 宣言 6 件）は未解決（本タスクスコープ外）
