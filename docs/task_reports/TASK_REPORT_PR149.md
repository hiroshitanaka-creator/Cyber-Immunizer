# タスク完了報告 — PR #149

## 概要

PR #149（`codex/add-structured-rule-output-path`）の "Request Changes" レビューに基づき、
structured-rules 出力パスの安全実装修正を `claude/pr-151-review-changes-8922ts` ブランチに追加した。

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `scripts/propose_mutation.py` | 修正（PR #149 追加機能 + stale-patch 除去修正） |
| `tests/test_structured_rules_proposal_output.py` | 新規作成（PR #149 テスト5件 + 回帰テスト1件） |
| `docs/task_reports/TASK_REPORT_PR149.md` | 新規作成（本ファイル） |

コミットしないもの: `.cyber_immunizer/structured_rules.json`（`.gitignore` 対象の生成成果物）

## 主な変更内容

### レビュー指摘 2 項目の対応状況

| # | 指摘 | 対応 |
|---|---|---|
| 1 | `--structured-rules` 実行後に stale `mutation_patch.json` が残る（raw patch hazard） | ✅ `_OUT_PATCH.exists()` チェック → `unlink()` → 失敗時は fail-closed（`success: false`、非ゼロ終了） |
| 2 | `.cyber_immunizer/structured_rules.json` がコミットされている | ✅ `.gitignore` が `.cyber_immunizer/` をすでに対象にしているため未コミット。本 PR ではステージングしない |

### `scripts/propose_mutation.py` 追加内容

**PR #149 から適用した変更（PR #149 の diff をローカルへ適用）:**
- `from core.structured_validator import validate_rules_schema` import 追加
- `_OUT_STRUCTURED_RULES = _OUT_DIR / "structured_rules.json"` 定数追加
- `build_offline_sample_structured_rules()` 関数追加（offline サンプル構造化ルール文書を生成）
- `propose_structured_rules()` 関数追加（offline_sample のみ対応、ライブモデルはガード済み）
- `--structured-rules` CLI 引数追加（`--offline-sample` の後に配置）
- `if args.structured_rules:` 分岐追加（preflight 後、raw patch パスの前に配置）

**本タスクで追加した stale-patch 除去修正:**
- `_OUT_STRUCTURED_RULES.write_text(...)` 成功後、`_OUT_PATCH.exists()` をチェック
- 存在する場合は `_OUT_PATCH.unlink()` で削除
- `OSError` 発生時: `success: false`、エラーメッセージ出力、`return 1`（fail-closed）
- `patch_path: null` をレスポンスに含め、mutation_patch との混同を防止

### `tests/test_structured_rules_proposal_output.py` 内容

PR #149 のテスト 5 件（そのまま収録）:
1. `test_offline_structured_rules_document_is_valid_and_safe_shape`
2. `test_structured_rules_cli_writes_rules_not_mutation_patch`
3. `test_structured_rules_output_is_cli_validator_compatible`
4. `test_generated_rules_evaluate_through_evaluator_and_adapter`
5. `test_structured_rules_without_offline_sample_fails_closed`

新規回帰テスト:
6. `test_structured_rules_cli_removes_stale_mutation_patch` — stale な `mutation_patch.json` を事前配置して `pm.main(["--structured-rules", "--offline-sample", "--json"])` を呼び出し、完了後にファイルが消えることを確認

## 後検証結果

```
python3 -m pytest tests/test_structured_rules_proposal_output.py -x -q
6 passed in 0.60s

python3 -m pytest tests/ -x -q
2676 passed, 5 warnings in 11.51s

python3 scripts/propose_mutation.py --structured-rules --offline-sample --json
{"success": true, "rules_path": ".../.cyber_immunizer/structured_rules.json", "patch_path": null, "mode": "structured-rules-offline-sample", "rule_count": 5}
```

- stale `mutation_patch.json` が `--structured-rules` 実行後に削除されることを確認: ✅
- `patch_path: null` がレスポンスに含まれることを確認: ✅
- `.cyber_immunizer/structured_rules.json` がコミット対象外であることを確認: ✅（`.gitignore` 適用済み）
- raw Python mutation path（`--offline-sample` 単体）に影響がないことを確認: ✅（全スイート通過）

## 残存事項・注意点

- `--structured-rules` のライブモデル対応は本 PR のスコープ外。`propose_structured_rules()` は `offline_sample=False` 時に fail-closed でエラーを返す。
- raw Python mutation path の削除・弱体化は行っていない。両パスは独立して機能する。

## 完了レイヤー宣言

`[ ] None`（本タスク報告ファイル自体はドキュメント整備）

structured-rules 出力パスの安全実装は Layer 2 validation support tooling の一部として機能するが、
Layer 2 完了単独では宣言しない。Owner の判断を要する。
