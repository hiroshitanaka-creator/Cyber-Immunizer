# タスク完了報告 — PR-1: DetectionResult型保証の統一

## 概要

DetectionResult dataclassのランタイム型強制（`__post_init__`）、ASTレベルの静的値チェック（`check_detection_result_static_values`）、フィットネス評価のコントラクトチェック（`_contract_ok`）を統一し、誤った型がサイレントにスコアリングに流れ込むリスクを排除した。

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `core/types.py` | `DetectionResult.__post_init__` を追加（ランタイム型強制） |
| `core/policy.py` | `check_detection_result_static_values` を追加、`run_full_policy` に組み込み |
| `core/fitness.py` | `_contract_ok` を強化（bool/str/tuple 各フィールドの明示的型チェック） |
| `tests/test_detection_result_contract.py` | 新規テスト（ランタイム・AST・統合） |

## 主な変更内容

- `DetectionResult.__post_init__`: `type(x) is bool/str/tuple` を使った厳密型チェック。`isinstance` は `bool` が `int` のサブクラスである罠を回避するため使用しない
- `_check_dr_confidence`: `ast.UnaryOp(USub, Constant)` を検出して負数リテラル（`-0.1` 等）をリジェクト
- `check_detection_result_static_values`: キーワード引数のみチェック（位置引数は既存パターンを壊さないため）
- `_contract_ok` in fitness.py: スモークテスト後に全フィールドの型を明示的に確認

## 後検証結果

```
pytest tests/test_detection_result_contract.py -q
→ 全テスト PASSED
pytest tests/ -x -q
→ 2511 passed (PR-3完了後の最終確認)
```

## 残存事項・注意点

- 位置引数による `DetectionResult(False, '', 0.0, ())` はAST静的チェックの対象外（既存候補コードとの互換性維持）
- キーワード引数パターン（`DetectionResult(blocked=True, ...)` 等）が静的チェック対象
