# タスク完了報告 — PR #160 P2 Cleanup

## 概要

PR #160 の Codex P2 レビュー指摘 2 件を latest main (PR #163 merge 済み) に対して修正した。
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

## 安全確認

- Gemini API 呼び出し: なし
- paid-credit 実行: なし
- workflow_dispatch: なし
- promotion state 変更: なし
- 生成アーティファクトのコミット: なし
- デフォルトランタイム動作の変更: なし
- `core/detector.py` の変更: なし
