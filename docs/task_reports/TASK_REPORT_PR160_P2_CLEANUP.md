# タスク完了報告 — PR #160 P2 Cleanup

## 概要

PR #160 の Codex P2 レビュー指摘 2 件を latest main (PR #161 merge 済み) に対して修正した。
runtime integration (PR-E) は意図的にこの PR に含めない。

## なぜ PR-E 前にこの cleanup が必要だったか

1. **シグナル名の不整合**: `build_offline_sample_structured_rules()` が生成するルールの `signal` フィールドが `"symbolic_path_traversal"` 等の独自シンボル名になっており、`core.detector.inspect_request()` が返す `matched_signals` の値 (`"path_traversal_indicator"` 等) と一致しなかった。PR-E で構造化ルールをランタイムに統合した場合、`matched_signals` が legacy detector と異なる値になり等価性が崩れる。
2. **preflight フラグの漏れ**: `--structured-rules` ブランチが `--gemini-paid-credit-preflight` を拒否していなかった。このフラグと組み合わせた場合、ルールファイルが書き込まれてしまう (preflight は「API 呼び出しなしの検証」であり構造化ルール出力とは相容れない)。

## 変更ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `scripts/propose_mutation.py` | Fix 1: `build_offline_sample_structured_rules()` の各ルールの `signal` を `literal` と同じ値に変更。Fix 2: `main()` の構造化ルールブランチで `args.gemini_paid_credit_preflight` も拒否するよう追加 |
| `tests/test_structured_rules_proposal_output.py` | 4 クラス 9 テストを追加 (Test 1〜4) |
| `docs/task_reports/TASK_REPORT_PR160_P2_CLEANUP.md` | 本ファイル |

## 主な変更内容

### Fix 1 — シグナル名を detector リテラルと一致させる

**Before:**
```python
{"id": "symbolic_path_traversal", "literal": "path_traversal_indicator", "signal": "symbolic_path_traversal", ...}
```

**After:**
```python
{"id": "symbolic_path_traversal", "literal": "path_traversal_indicator", "signal": "path_traversal_indicator", ...}
```

5 ルール全て同様に修正:
- `path_traversal_indicator`
- `script_injection_indicator`
- `sqli_indicator`
- `command_delimiter_indicator`
- `encoded_traversal_indicator`

### Fix 2 — preflight フラグを拒否

**Before:**
```python
if args.live_model or args.gemini_paid_credit:
    err = "--structured-rules does not support live model or paid-credit modes. ..."
```

**After:**
```python
if args.live_model or args.gemini_paid_credit or args.gemini_paid_credit_preflight:
    err = "--structured-rules does not support live model, paid-credit, or paid-credit-preflight modes. ..."
```

実際の動作:
```
$ python scripts/propose_mutation.py --structured-rules --offline-sample --gemini-paid-credit-preflight --json
{"success": false, "error": "--structured-rules does not support ... Use --structured-rules --offline-sample only.", "patch_path": null}
exit code: 1
```

## 追加テスト

| クラス | テスト数 | 内容 |
|---|---|---|
| `TestRuleSignalsEqualDetectorLiterals` | 2 | `signal == literal` の確認、期待されるシグナルセットの確認 |
| `TestMatchedSignalsEquivalenceWithLegacyDetector` | 3 | single/multi/benign の各リクエストで `blocked`, `confidence`, `matched_signals`, `reason` が legacy detector と一致 |
| `TestStructuredRulesRejectsPaidCreditPreflight` | 4 | rc==1 確認、JSON success=False 確認、エラーメッセージ確認、artifacts 非生成確認 |

## テスト結果

```
# フォーカステスト (34 tests = 元の 25 + 新規 9)
tests/test_structured_rules_proposal_output.py: 34 passed

# 構造化ルール行列テスト (151 tests)
tests/test_structured_rules_proposal_output.py ......... [34]
tests/test_structured_validator.py ..................... [58]
tests/test_structured_evaluator.py ..................... [29]
tests/test_structured_detector_integration.py .......... [12]
tests/test_structured_detector_equivalence.py .......... [16]
151 passed

# 全スイート
1817 passed, 1 pre-existing failure (test_project_state_matches_ledger_success_count: data sync mismatch in data/ files — not caused by this PR)
```

## 後検証結果

```bash
# シグナル == リテラル の確認
symbolic_path_traversal: signal='path_traversal_indicator' literal='path_traversal_indicator' -> OK
symbolic_script_injection: signal='script_injection_indicator' literal='script_injection_indicator' -> OK
symbolic_sqli: signal='sqli_indicator' literal='sqli_indicator' -> OK
symbolic_cmdi: signal='command_delimiter_indicator' literal='command_delimiter_indicator' -> OK
symbolic_encoded_traversal: signal='encoded_traversal_indicator' literal='encoded_traversal_indicator' -> OK

# preflight 拒否確認
$ python scripts/propose_mutation.py --structured-rules --offline-sample --gemini-paid-credit-preflight --json
{"success": false, ...}
exit code: 1

# アーティファクト確認
$ find .cyber_immunizer -maxdepth 1 -type f  # ディレクトリ不在 → 生成なし
```

## 残存事項・注意点

- PR-E (runtime integration) はこの PR に含めない。これは意図的スコープ除外。
- `test_project_state_sync.py::test_project_state_matches_ledger_success_count` の失敗は pre-existing (main ブランチ上で確認済み、`data/` ファイルのカウント不一致)。この PR の変更とは無関係。
- `core/detector.py`, `core/structured_detector.py`, `core/structured_evaluator.py`, `data/**`, `.github/**` はいずれも変更していない。

## 安全確認

- Gemini API 呼び出し: なし
- paid-credit 実行: なし
- workflow_dispatch: なし
- promotion state 変更: なし
- 生成アーティファクトのコミット: なし
- デフォルトランタイム動作の変更: なし
- `core/detector.py` の変更: なし

## Layer 宣言

- [x] Layer 1 — Research Foundation (detector signal 等価性の前提条件を回復)
- [ ] Layer 2 — Value Validation (未主張)
- [x] Layer 3 — AI Operation Control (PR-E runtime integration 前の review hygiene 解消)
