# タスク完了報告 — PR #128 REQUEST CHANGES 対応 (PR-A / PR-B / PR-C 分割)

## 概要

PR #128 の REQUEST CHANGES に対し、Preferred Split Path（3分割）を採用。
PR-A / PR-B / PR-C の3ブランチを新規作成し、レビュー指摘を全件解消した。
その後 PR #129（PR-C）への REQUEST CHANGES も対応済み（空ファイル fail-closed、end-to-end テスト追加）。

## 対象ブランチ・PR

| ブランチ | PR | 内容 | Head SHA |
|---|---|---|---|
| `claude/pr-a-detection-result-x007` | #130 | DetectionResult 型保証（PR-1 + PR-A 修正） | `33afadc` |
| `claude/pr-b-corpus-state-validation` | #131 | コーパス/状態スキーマ検証（PR-2）| `fa26980` |
| `claude/pr-c-adaptive-floor` | #129 | 適応フロア（PR-3 + PR-C 修正 2ラウンド） | `1e1f034` |

各ブランチは `b901a6e` を merge-base とし、PR-A → PR-B → PR-C の順に積み上がっている。

## レビュー指摘と対応

### P1: AST チェックが位置引数を拒否しない / 必須フィールド欠落を拒否しない

**対応ファイル（PR-A）：** `core/policy.py`, `tests/test_ast_policy.py`, `tests/test_detection_result_contract.py`, `tests/test_fitness.py`, `tests/test_mutation_boundaries.py`

変更内容：
- `check_detection_result_static_values` に2ステップ追加:
  1. `node.args` が存在 → "positional arguments are not allowed" violation + `continue`
  2. `_DR_VALID_FIELDS - kw_field_names` が非空 → "missing required keyword field(s)" violation
- `tests/test_ast_policy.py` の7つの `_assert_accepted` テストを keyword 形式に更新（位置引数禁止の波及）
- `tests/test_ast_policy.py` に `test_rejects_detectionresult_positional_args` / `test_rejects_detectionresult_missing_required_field` を追加
- `tests/test_detection_result_contract.py` に `test_rejects_positional_args` / `test_rejects_missing_required_field` を追加
- `tests/test_fitness.py` / `tests/test_mutation_boundaries.py` の有効候補コード文字列を keyword 形式に更新（波及）

### P1: 適応フロアがファイル不在でサイレントにパスする（fail-open）

**対応ファイル（PR-C 第1ラウンド）：** `core/test_attacker.py`

変更内容：
- `load_test_cases` に `require_adaptive_tiers: bool = True` を追加
- デフォルト True の場合、tier ファイルが存在しないと `ValueError` を送出（fail-closed）
- `tests/test_adaptive_floor.py` の既存テストに `require_adaptive_tiers=False` を追加
- `tests/test_adaptive_floor.py` に `test_missing_tier_raises_by_default` を追加

### P1: 適応フロアが空ファイル（`[]`）でサイレントにパスする（fail-open）

**対応ファイル（PR-C 第2ラウンド）：** `core/test_attacker.py`, `scripts/validate_state.py`, `tests/test_adaptive_floor.py`

変更内容：
- `_load_corpus_file` に `require_non_empty: bool = False`（keyword-only）を追加
- 空ファイルが存在する場合 `ValueError("Corpus file {path} must contain at least one record")` を送出
- `load_test_cases` はすべての適応層ファイルを `require_non_empty=True` で呼び出す
- `validate_state.py` の `_check_corpus_file` も `require_non_empty` を受け取り、holdout/cf/drift で `True` を指定
- `TestEmptyAdaptiveTierFile` クラス（4テスト）を追加

### P1: end-to-end `evaluate()` テストが不足

**対応ファイル（PR-C 第2ラウンド）：** `tests/test_adaptive_floor.py`

変更内容：
- `TestAdaptiveFloorEndToEnd` クラス（2テスト）を追加:
  - `test_never_blocking_fails_adaptive_floor`: never-blocking 候補 → `holdout_pass_rate < 1.0` → `adaptive_floor_passed=False` → `passed_adoption_gate=False`
  - `test_always_blocking_fails_adaptive_floor`: always-blocking 候補 → `counterfactual_pass_rate < 1.0` → `adaptive_floor_passed=False` → `passed_adoption_gate=False`

### P1: `validate_state.py` が holdout/counterfactual/drift を検証しない

**対応ファイル（PR-C 第1ラウンド）：** `scripts/validate_state.py`

変更内容：
- `validate_all()` のコーパスループに `holdout_requests.json`, `counterfactual_requests.json`, `drift_requests.json` を追加
- 検証ファイル数: 7 → 10
- 第2ラウンドで holdout/cf/drift に `require_non_empty=True` を追加

### P2: 適応フロアのデフォルト閾値が 0.5（ゆるすぎる）

**対応ファイル（PR-C 第1ラウンド）：** `core/fitness.py`

変更内容：
- `min_holdout_pass_rate` / `min_counterfactual_pass_rate` / `min_drift_pass_rate` のデフォルトを 0.5 → **1.0** に変更

### P2: PR タイトル/本文のスコープ違反（3スコープを1PRに混在）

**対応：** 3ブランチに分割（PR-A #130 / PR-B #131 / PR-C #129）

### P2: PR-C の diff に PR1/PR2 レポートが混在

**対応（PR-C 第2ラウンド）：**
- `docs/task_reports/TASK_REPORT_BLOCKERS_PR1.md` を PR-C ブランチから削除（`git rm`）
- `docs/task_reports/TASK_REPORT_BLOCKERS_PR2.md` を PR-C ブランチから削除（`git rm`）

## セキュリティ不変条件の確認

| 不変条件 | 状態 |
|---|---|
| Gemini API / workflow_dispatch / paid-credit 未呼び出し | ✅ 変更なし |
| `data/api_usage_ledger.json` 未編集 | ✅ 変更なし |
| `promote_approved` 未変更 | ✅ 変更なし |
| `.github/**` 未編集 | ✅ 変更なし |
| スコア決定論性（holdout/cf/drift は main eval から分離） | ✅ 維持 |
| AST fail-closed（例外時は violations に追記） | ✅ 維持 |
| 適応フロア fail-closed（ファイル不在 → ValueError） | ✅ 維持 |
| 適応フロア fail-closed（空ファイル → ValueError） | ✅ 新規追加 |

## 後検証結果

```
# claude/pr-a-detection-result-x007 (HEAD: 33afadc) にて
pytest tests/ -x -q
→ 2447 passed, 5 warnings

# claude/pr-c-adaptive-floor (HEAD: 1e1f034) にて
pytest tests/test_adaptive_floor.py -q
→ 37 passed in 0.13s

pytest tests/ -x -q
→ 2522 passed, 5 warnings in 12.87s

python scripts/validate_state.py --json
→ {"success": true, "checked_files": [...10 files...], "violations": []}
```

## 変更ファイル一覧

### PR-A (claude/pr-a-detection-result-x007 / PR #130)

| ファイル | 操作 |
|---|---|
| `core/policy.py` | EDIT — 位置引数拒否・必須フィールド欠落拒否を追加 |
| `core/types.py` | EDIT (PR-1 original) — `__post_init__` 追加 |
| `core/fitness.py` | EDIT (PR-1 original) — `_contract_ok` 強化 |
| `tests/test_detection_result_contract.py` | EDIT — AST レベルの rejection テスト追加 |
| `tests/test_ast_policy.py` | EDIT — keyword 形式に更新 + 新 rejection テスト |
| `tests/test_fitness.py` | EDIT — keyword 形式に更新（波及） |
| `tests/test_mutation_boundaries.py` | EDIT — keyword 形式に更新（波及） |

### PR-B (claude/pr-b-corpus-state-validation / PR #131)

| ファイル | 操作 |
|---|---|
| `core/test_attacker.py` | EDIT (PR-2 original) — スキーマ厳密検証 |
| `intelligence/threat_feeds.py` | EDIT (PR-2 original) — strict/lenient モード |
| `scripts/validate_state.py` | CREATE (PR-2 original) — 基本7ファイル検証 |
| `tests/test_corpus_schema.py` | CREATE (PR-2 original) |
| `tests/test_threat_feed_validation.py` | CREATE (PR-2 original) |

### PR-C (claude/pr-c-adaptive-floor / PR #129)

| ファイル | 操作 |
|---|---|
| `data/holdout_requests.json` | CREATE (PR-3 original) |
| `data/counterfactual_requests.json` | CREATE (PR-3 original) |
| `data/drift_requests.json` | CREATE (PR-3 original) |
| `core/types.py` | EDIT (PR-3 original) — TestCase.kind / FitnessReport adaptive fields |
| `core/test_attacker.py` | EDIT — `require_adaptive_tiers=True` + `require_non_empty=True` 追加 |
| `core/fitness.py` | EDIT — 1.0 デフォルト閾値、adaptive floor gate |
| `scripts/validate_state.py` | EDIT — 10ファイル検証に拡張 + `require_non_empty=True` |
| `tests/test_adaptive_floor.py` | EDIT — 37テスト（fail-closed・空ファイル拒否・end-to-end） |
| `docs/task_reports/TASK_REPORT_BLOCKERS_PR3.md` | EDIT — 現行実装に合わせて更新 |
| `docs/task_reports/TASK_REPORT_BLOCKERS_REVIEW_FIXES.md` | EDIT — 本ファイル（最新 HEAD / PR番号 / 空ファイル fix を反映） |
| `docs/task_reports/TASK_REPORT_BLOCKERS_PR1.md` | DELETE — PR-C の diff から除外 |
| `docs/task_reports/TASK_REPORT_BLOCKERS_PR2.md` | DELETE — PR-C の diff から除外 |

## 残存事項

- genome.json の `min_holdout_pass_rate` 等は未設定のため 1.0 デフォルトが適用される
- PR #129 のマージは Project Owner が PR #130 → PR #131 のマージ完了後に判断する
- 3ブランチの PR 作成済み：PR #130（PR-A）/ PR #131（PR-B）/ PR #129（PR-C）
