# タスク完了報告 — S4 Rerun Triage Tool

## 概要

次回 S4 paid-credit rerun 後のアーティファクトをローカルで決定論的に分類する
トリアージツール (`scripts/triage_s4_rerun.py`) を実装した。
18テスト全通過。既存テスト (`test_project_state_sync.py`) 16件も全通過。

---

## 変更ファイル一覧

| ファイル | 区分 | 内容 |
|---|---|---|
| `scripts/triage_s4_rerun.py` | 新規追加 | トリアージツール本体 |
| `tests/test_s4_rerun_triage.py` | 新規追加 | 18テストケース |
| `docs/S4_RERUN_CHECKLIST.md` | 追記 | Local Triage Tool セクション追加 |

---

## 主な変更内容

### `scripts/triage_s4_rerun.py`

- CLI: `python scripts/triage_s4_rerun.py --artifacts-dir <DIR> [--json] [--markdown <PATH>]`
- Python 3.11 標準ライブラリのみ使用（外部依存なし）
- アーティファクト5種を読み取り:
  - `mutation_patch.json`、`api_usage_ledger.json`、`candidate_detector.py`、
    `fitness_report.json`、`promote_result.json`
- **6段階の決定論的分類:**
  | Classification | 条件 |
  |---|---|
  | `propose_failed` | mutation_patch.json が存在しないまたは malformed |
  | `apply_failed_or_not_reached` | patch あり、candidate_detector.py なし |
  | `evaluate_rejected` | fitness_report.json あり、`passed_adoption_gate=false` |
  | `promote_eligible` | `passed_adoption_gate=true`、promote_result.json なし |
  | `promoted` | promote_result.json 存在 |
  | `tool_failure` | fitness_report.json が malformed / 型異常 / 予期しないフィールド値 |
- **Fail-closed:** malformed JSON は即座に `tool_failure` に分類（gate 値不明のまま続行しない）
- **Secret 検出:** Google API key、bearer token、password 風文字列をパターンマッチで検出し
  値を出力せず警告のみ返す
- **Promise:** `promote_eligible` でも promotion を実行しない。`requires_owner_approval=true` を返すのみ
- **ledger 編集禁止:** `api_usage_ledger.json` は read-only で参照するのみ

### `tests/test_s4_rerun_triage.py`

18テスト:
1. アーティファクトなし → `propose_failed`
2. patch + ledger のみ → `apply_failed_or_not_reached`
3. candidate_detector あり、fitness_report なし → `apply_failed_or_not_reached`
4. `passed_adoption_gate=false` → `evaluate_rejected`
5. `passed_adoption_gate=true` → `promote_eligible` + `requires_owner_approval=true`
6. malformed fitness_report (invalid JSON) → `tool_failure`
7. fitness_report のルートが配列 → `tool_failure`
8. `passed_adoption_gate` フィールド欠落 → `tool_failure` (fail-closed)
9. mutation_patch にシークレット風文字列 → 値が出力に漏れない
10. promote_result.json あり → `promoted`
11. malformed mutation_patch → `propose_failed` + 警告
12. 空の fitness_report.json → `tool_failure`
13. 出力スキーマに必須キー全存在
14. CLI `--json` フラグで有効な JSON 出力
15. CLI `--markdown` フラグで Markdown ファイル生成
16. 存在しない artifacts_dir → exit code 2
17. candidate_detector にシークレット風文字列 → 値が出力に漏れない
18. rejection_reasons にシークレット風文字列 → 値が出力に漏れない

### `docs/S4_RERUN_CHECKLIST.md`

「Local Triage Tool」セクションを Ledger Verification セクションの前に追記。
CLI 使用例、期待アーティファクト表、分類表、promotion 実行禁止注意書きを含む。

---

## 後検証結果

```
pytest tests/test_s4_rerun_triage.py -q
→ 18 passed in 0.08s

pytest tests/test_project_state_sync.py -q
→ 16 passed in 0.05s
```

---

## セキュリティ制約の確認

| 制約 | 対応 |
|---|---|
| ネットワークアクセス禁止 | 標準ライブラリのみ使用、urllib/requests 不使用 |
| ledger 編集禁止 | `api_usage_ledger.json` は read-only で参照 |
| シークレット出力禁止 | 正規表現パターンで検出し値を suppress |
| promotion 実行禁止 | `promote_eligible` は `requires_owner_approval=true` を返すのみ |
| workflow_dispatch 禁止 | ツール内に一切の CI トリガーコードなし |
| core/policy.py 等 FROZEN ファイル不変 | 変更なし |

---

## 残存事項・注意点

1. **実アーティファクトでの検証未実施:** 次回 Owner-approved S4 rerun 後に
   実アーティファクトで `--artifacts-dir` を指定して動作確認すること。
2. **`fitness_report.json` のフィールド追加への対応:** 将来 evaluate_candidate.py が
   新フィールドを追加した場合も、このツールは `passed_adoption_gate` 以外を
   evidence として参照するだけなので影響は最小限。
3. **promote_result.json の実フォーマット:** promote_candidate.py が実際に書き出す
   フォーマットは未確認。ツールはファイルの存在のみを判定基準とするため互換性はある。
