# タスク完了報告 — PR-C: 適応的評価フロア (PR #129)

## 概要

固定コーパスへの過学習を軽減するため、最小限の適応的評価フロアを導入した。
holdout・counterfactual・drift の3層を新たに追加し、採用ゲートに各層のパスレートしきい値チェックを組み込んだ。
スコア計算の決定論性・世代不変性を維持しながら、フロアは `require_adaptive_tiers=True` / `require_non_empty=True` によりデフォルト fail-closed とした。

PR #129 は PR-B (`claude/pr-b-corpus-state-validation` / PR #131) にスタックしており、
PR-B は PR-A (`claude/pr-a-detection-result-x007` / PR #130) にスタックしている。

## ブランチ情報

| 項目 | 値 |
|---|---|
| ブランチ | `claude/pr-c-adaptive-floor` |
| Head SHA | `1e1f034` |
| PR | #129 |
| ベース | `claude/pr-b-corpus-state-validation` (PR #131) |

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `data/holdout_requests.json` | 新規作成（5件のinert symbolic indicatorフィクスチャ） |
| `data/counterfactual_requests.json` | 新規作成（5件のbenign-lookalike フィクスチャ） |
| `data/drift_requests.json` | 新規作成（5件のdrift symbolic indicatorフィクスチャ） |
| `core/types.py` | `TestCase.kind` Literalに3種追加。`FitnessReport` に5フィールド追加（デフォルト付き） |
| `core/test_attacker.py` | `_VALID_CORPUS_KINDS` 拡張。`load_test_cases` に `require_adaptive_tiers=True` / `_load_corpus_file` に `require_non_empty=True` 追加 |
| `core/fitness.py` | `_compute_tier_pass_rate`, `_adaptive_floor_gate` 追加。`evaluate` に適応フロア組み込み。デフォルト閾値 1.0 |
| `scripts/validate_state.py` | 10ファイル検証に拡張。holdout/cf/drift に `require_non_empty=True` |
| `tests/test_adaptive_floor.py` | 37テスト（パスレート計算・フロアゲート・層ローディング・FitnessReportデフォルト・空ファイル拒否・end-to-end evaluate() テスト） |
| `docs/task_reports/TASK_REPORT_BLOCKERS_PR3.md` | 本ファイル（PR-C完了報告） |
| `docs/task_reports/TASK_REPORT_BLOCKERS_REVIEW_FIXES.md` | PR #128 REQUEST CHANGES 対応報告 |

**PR-C の diff に含まれないファイル:** `TASK_REPORT_BLOCKERS_PR1.md` / `TASK_REPORT_BLOCKERS_PR2.md`（PR-A/PR-B に属するため削除済み）

## コミット履歴

| SHA | 内容 |
|---|---|
| `d785523` | PR-3: Minimal holdout/counterfactual/drift adaptive evaluation floor（オリジナル実装） |
| `128928e` | PR-C review fix: fail-closed adaptive floor and 1.0 default thresholds |
| `bd83a28` | Add resolution report for PR #128 REQUEST CHANGES |
| `1e1f034` | PR-C review fix: fail-closed on empty adaptive tier files + end-to-end floor tests |

## 主な変更内容

### データフィクスチャ（inert symbolic only）

- **holdout**: `PATH_TRAVERSAL_INDICATOR`, `SQLI_INDICATOR`, `ENCODED_TRAVERSAL_INDICATOR` 等 5件（expected_blocked=True 3件、False 2件）
- **counterfactual**: 5件のbenignリクエスト（SQLキーワードを含むが正当なURL）— 全件 expected_blocked=False
- **drift**: 5件のattackリクエスト（`DRIFT_PATH_TRAVERSAL_INDICATOR` 等、ベースライン検出器のトークンを部分文字列として含む命名）— 全件 expected_blocked=True

### フロア fail-closed 設計（2段階）

| 条件 | 動作 |
|---|---|
| 層ファイルが **存在しない** かつ `require_adaptive_tiers=True`（デフォルト） | `ValueError` を送出（fail-closed） |
| 層ファイルが **存在するが空**（`[]`）| `require_non_empty=True` により `ValueError` を送出（fail-closed） |
| 層ファイルが **存在しない** かつ `require_adaptive_tiers=False` | スキップ（テスト・後方互換用） |

### FitnessReport 新フィールド（デフォルト付き）

```python
holdout_pass_rate: float = 1.0
counterfactual_pass_rate: float = 1.0
drift_pass_rate: float = 1.0
adaptive_floor_passed: bool = True
adaptive_floor_rejection_reasons: tuple[str, ...] = ()
```

### 適応フロアゲート

- genome.json から `min_holdout_pass_rate`（デフォルト **1.0**）、`min_counterfactual_pass_rate`（1.0）、`min_drift_pass_rate`（1.0）を読む
- 各層のファイルがない（`None` レート）場合はその層のチェックをスキップ
- フロア失敗理由は `rejection_reasons` に追記し、`passed_adoption_gate` を False にする

### スコア計算分離

holdout/counterfactual/drift の結果は `_MAIN_EVAL_KINDS`（benign/attack/regression）の tp/fp/fn 計算に含めない。スコアの世代不変性・決定論性を維持するため。

### end-to-end evaluate() テスト（新規）

| テスト | 内容 |
|---|---|
| `test_never_blocking_fails_adaptive_floor` | never-blocking候補 → holdout_pass_rate=0.4 < 1.0 → adaptive_floor_passed=False |
| `test_always_blocking_fails_adaptive_floor` | always-blocking候補 → counterfactual_pass_rate=0.0 < 1.0 → adaptive_floor_passed=False |

## 後検証結果

```
# claude/pr-c-adaptive-floor (HEAD: 1e1f034) にて

pytest tests/test_adaptive_floor.py -q
→ 37 passed in 0.13s

pytest tests/ -x -q
→ 2522 passed, 5 warnings in 12.87s

python scripts/validate_state.py --json
→ {"success": true, "checked_files": [...10 files...], "violations": []}
```

## アーキテクチャ不変条件

| 不変条件 | 維持状況 |
|---|---|
| スコア決定論性（holdout/cf/drift は main eval から分離） | ✅ 維持 |
| fail-closed（ファイル不在 → ValueError） | ✅ 維持 |
| fail-closed（空ファイル → ValueError） | ✅ 新規追加 |
| Gemini API / workflow_dispatch / paid-credit 未呼び出し | ✅ 変更なし |
| `data/api_usage_ledger.json` 未編集 | ✅ 変更なし |
| `promote_approved` 未変更 | ✅ 変更なし |
| `.github/**` 未編集 | ✅ 変更なし |
| フィクスチャはすべて inert symbolic indicators のみ | ✅ 維持 |

## 残存事項・注意点

- genome.json に `min_holdout_pass_rate` 等が未設定のため、デフォルト 1.0 が適用される
- drift 指標のプレフィックス命名（`DRIFT_PATH_TRAVERSAL_INDICATOR` 等）はベースライン検出器の部分文字列マッチで検出可能。意図的設計
- 完全な適応的トーナメント（候補ごとに動的にフィクスチャを生成）は実装していない
- PR #129 のマージは Project Owner が PR-A (#130) → PR-B (#131) の順でマージ後に判断する
