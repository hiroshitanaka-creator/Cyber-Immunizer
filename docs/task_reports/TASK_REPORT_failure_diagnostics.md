# タスク完了報告 — Failure Diagnostics (PR branch: claude/cyber-immunizer-failure-diagnostics-in1tuk)

## 概要

Apply/Evaluate のどの段階で失敗しても、失敗理由を machine-readable な JSON artifact として必ず残す仕組みを実装した。fail-closed の安全性・既存の adoption gate・promotion 条件・budget/ledger 制約はすべて維持した上で、診断情報の永続化と CI artifacts の観測可能性を向上させた。

## 変更ファイル一覧

| ファイル | 種別 | 変更理由 |
|---|---|---|
| `scripts/apply_mutation.py` | 変更 | `--report` CLI オプション追加・`_write_apply_report_atomic()` 追加・全失敗経路に `replacement_code_sha256` / `mutation_rationale` / `target_threats` を含むスキーマ追加 |
| `scripts/evaluate_candidate.py` | 変更 | `--report` CLI オプション追加・candidate-not-found ガード追加・AST validation 失敗経路に `_write_report()` 呼び出し追加・report に `stage` フィールド追加 |
| `.github/workflows/immunization_loop.yml` | 変更 | apply ステップに `--report` フラグ・apply-report artifact upload 追加 (`if: always()`)・evaluate ステップに `if: steps.apply.outcome == 'success'` 条件追加・artifact upload に `if-no-files-found: warn` 追加 |
| `tests/test_apply_mutation.py` | 新規 | apply_mutation の --report 動作・失敗経路のレポート生成・セキュリティ制約のテスト |
| `tests/test_evaluate_candidate.py` | 変更 | stage フィールド・candidate-not-found・AST failure report・no-secrets テスト追加 |
| `tests/test_workflow.py` | 変更 | apply-report artifact upload・--report フラグ・evaluate スキップ条件・promotion 条件不変のテスト追加 |

## 主な変更内容

### apply_mutation.py
- `import hashlib` 追加
- `_write_apply_report_atomic(report_path, payload)` — tempfile + fsync + os.replace による atomic write
- `apply_mutation()` の全返り値に `replacement_code_sha256`（sha256 ハッシュのみ、本文なし）、`mutation_rationale`、`target_threats` を追加
- `main()` に `--report PATH` オプション追加。report write 失敗は fail-closed（exit 1）

### evaluate_candidate.py
- candidate hash をバリデーション前に事前計算（候補ファイル不在でも null で返す）
- `candidate_path.exists()` ガードを Step 1 前に追加、report を書いて fail-closed 返却
- AST validation 失敗経路に `_write_report()` 呼び出し追加（以前は report を書かなかった）
- `_write_report()` を改修し `stage: "evaluate_candidate"` と正規スキーマ（`metrics` キー）を出力
- `main()` に `--report PATH` オプション追加

### immunization_loop.yml
- apply ステップに `id: apply` と `--report .cyber_immunizer/apply_report.json` 追加
- `Upload apply report artifact` ステップ追加（`if: always()`）
- evaluate ステップに `if: steps.apply.outcome == 'success'` 追加
- evaluate ステップに `--report .cyber_immunizer/fitness_report.json` 追加
- candidate-detector / fitness-report upload に `if-no-files-found: warn` 追加

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
  "mutation_rationale": "string|null",
  "target_threats": ["string"],
  "replacement_code_sha256": "string|null"
}
```

### fitness_report.json (failure schema)
```json
{
  "stage": "evaluate_candidate",
  "success": false,
  "passed_adoption_gate": false,
  "is_tool_failure": true,
  "timed_out": false,
  "candidate_hash": "string|null",
  "violations": ["string"],
  "error": "string",
  "metrics": null,
  "return_code": null
}
```

## テスト結果

```
python -m pytest tests/test_apply_mutation.py tests/test_evaluate_candidate.py tests/test_workflow.py -q
197 passed in 0.46s

python -m pytest tests/ -q --ignore=tests/test_project_state_sync.py
2055 passed, 5 warnings in 3.53s
```

（`test_project_state_sync.py` の 1 失敗は本変更以前から存在するデータ不整合のため除外）

## 追加テストケース要約

**test_apply_mutation.py（新規、28テスト）**
- malformed JSON / 必須フィールド欠落 / ファイル不在 → report 生成
- policy violation → report に `replacement_code` 全文不在・sha256 のみ存在
- 成功時 → `success=true` / `exit_code=0` / `candidate_path` あり
- report 書き込み失敗 → fail-closed (非ゼロ終了)
- `_write_apply_report_atomic()` 単体テスト

**test_evaluate_candidate.py（追加、23テスト）**
- fitness_report.json に `stage: "evaluate_candidate"` が常に含まれること
- candidate ファイル不在 → report 生成・`candidate_hash=null`
- AST validation 失敗 → report 生成・violations 一覧あり
- secret 系 env var が report に漏洩しないこと

**test_workflow.py（追加、12テスト）**
- `apply-report` artifact upload が存在し `if: always()` を使用していること
- apply ステップに `--report` フラグがあること
- evaluate ステップが apply 失敗時にスキップされる条件を持つこと
- promotion 条件が緩和されていないこと（regression guard）

## セキュリティノート

- **fail-closed 維持**: report write 自体に失敗した場合は非ゼロ終了
- **secret 漏洩防止**: `_safe_env()` による環境変数ストリップは変更なし。report に `GEMINI_API_KEY` 等は含まれない
- **replacement_code 全文除外**: apply_report.json には `replacement_code_sha256`（SHA-256 のみ）を含め、本文は含めない
- **invalid candidate 実行禁止**: candidate-not-found ガードと AST validation はいずれも validate 前に fail-closed で返却し、subprocess は起動しない
- **promotion gate 不変**: `passed_adoption_gate`・`promote_approved`・`workflow_dispatch` 条件はすべて維持

## 残存事項・注意点

- `test_project_state_sync.py::test_project_state_matches_ledger_success_count` は本変更前から失敗しているデータ不整合（ledger=7件 vs project_state宣言=6件）。本タスクスコープ外。
- `_write_report()` の write 失敗（OSError）は現在 silently drop される。fail-closed にするには evaluate_candidate の report write も atomic にする必要があるが、既存の `report_path.write_text()` の変更はスコープ外とした。
