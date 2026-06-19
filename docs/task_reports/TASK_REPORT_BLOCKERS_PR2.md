# タスク完了報告 — PR-2: コーパス/状態ファイルのポイズニング耐性

## 概要

コーパスおよびプロジェクト状態ファイルの厳密なスキーマ検証を実装し、JSONファイルの改ざん（`expected_blocked` の文字列強制、型不正、重複ID等）が評価セマンティクスにサイレントに影響することを防止した。

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `core/test_attacker.py` | `_validate_request_dict`, `_validate_corpus_record`, `_load_corpus_file` を追加。`load_test_cases` を厳密検証に更新 |
| `intelligence/threat_feeds.py` | `load_active_threats(strict=True/False)` 追加、strict/lenient 2モード |
| `scripts/validate_state.py` | 新規作成（genome/evolution_history/project_state/active_threats/corpus の全バリデーションCLI） |
| `tests/test_corpus_schema.py` | 新規テスト（expected_blockedのbool強制、型チェック、欠損フィールド、重複ID等） |
| `tests/test_threat_feed_validation.py` | 新規テスト（strict/lenientモード、defensive_focus検証等） |

## 主な変更内容

- `expected_blocked` の `bool()` による文字列強制を廃止。`type(x) is bool` でJSON `true`/`false` のみ受け付ける
- `query`・`headers` の値が `dict[str, str]` であることを検証（`int` 値等をリジェクト）
- 重複IDを検出してValueErrorを発生させる
- `load_active_threats(strict=True)` はdefaultになり、既知の `defensive_focus` 値のみ受け付ける
- `scripts/validate_state.py --json` が7ファイルを検証してexit 0を返す

## 後検証結果

```
python scripts/validate_state.py --json
→ {"success": true, "checked_files": [...7 files...], "violations": []}

pytest tests/test_corpus_schema.py tests/test_threat_feed_validation.py -q
→ 全テスト PASSED
```

## 残存事項・注意点

- `scripts/validate_state.py` はPR-3で追加される holdout/counterfactual/drift ファイルを明示的に検証しない（`load_test_cases` 内での検証に委ねる）
- lenientモード（`strict=False`）は後方互換性のため維持
