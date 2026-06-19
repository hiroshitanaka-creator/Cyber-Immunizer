# タスク完了報告 — PR-3: 最小限ホールドアウト/ドリフト/反事実評価フロア

## 概要

固定コーパスへの過学習を軽減するため、最小限の適応的評価フロアを導入した。holdout・counterfactual・drift の3層を新たに追加し、採用ゲートに各層のパスレートしきい値チェックを追加した。完全な適応的トーナメントは実装せず、スコア計算の決定論性・世代不変性を維持する。

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `data/holdout_requests.json` | 新規作成（5件のinert symbolic indicatorフィクスチャ） |
| `data/counterfactual_requests.json` | 新規作成（5件のbenign-lookalike フィクスチャ） |
| `data/drift_requests.json` | 新規作成（5件のdrift symbolic indicatorフィクスチャ） |
| `core/types.py` | `TestCase.kind` Literalに3種追加。`FitnessReport` に5フィールド追加（デフォルト付き） |
| `core/test_attacker.py` | `_VALID_CORPUS_KINDS` を拡張。`load_test_cases` にオプショナル層ローディングを追加 |
| `core/fitness.py` | `_compute_tier_pass_rate`, `_adaptive_floor_gate` を追加。`evaluate` に適応フロアを組み込み |
| `tests/test_adaptive_floor.py` | 新規テスト（パスレート計算・フロアゲート・種別ローディング・FitnessReportデフォルト） |

## 主な変更内容

### データフィクスチャ（inert symbolic only）

- **holdout**: `PATH_TRAVERSAL_INDICATOR`, `SQLI_INDICATOR`, `ENCODED_TRAVERSAL_INDICATOR` + benign 2件
- **counterfactual**: 5件のbenignリクエスト（SQLキーワードを含むが正当なURL/クエリ）
- **drift**: 5件のattackリクエスト（`DRIFT_PATH_TRAVERSAL_INDICATOR` 等、ベースライン検出器のトークンを部分文字列として含む命名）

### アーキテクチャ上の設計判断

- **スコア計算分離**: holdout/counterfactual/drift の結果は `_MAIN_EVAL_KINDS` (benign/attack/regression) のtp/fp/fn計算に含めない。スコアの世代不変性・決定論性を維持するため
- **オプショナルロード**: 新層のファイルが存在しない場合は空リストとして扱い、フロアはパスとみなす（後方互換性）
- **`expected_blocked=None` デフォルト**: 適応層レコードは各自 `expected_blocked` を持つことを強制（`_validate_corpus_record` で検証済み）

### FitnessReport 新フィールド（デフォルト付き）

```python
holdout_pass_rate: float = 1.0
counterfactual_pass_rate: float = 1.0
drift_pass_rate: float = 1.0
adaptive_floor_passed: bool = True
adaptive_floor_rejection_reasons: tuple[str, ...] = ()
```

### 適応フロアゲート

- genome.json から `min_holdout_pass_rate` (デフォルト0.5), `min_counterfactual_pass_rate` (0.5), `min_drift_pass_rate` (0.5) を読む
- 各層のファイルがない（Noneレート）場合はその層のチェックをスキップ
- フロア失敗理由は `rejection_reasons` に追記し、`passed_adoption_gate` を False にする

## 後検証結果

```
pytest tests/ -x -q
→ 2511 passed, 5 warnings

python scripts/validate_state.py
→ PASS: 7 files validated successfully
```

## 残存事項・注意点

- genome.json に `min_holdout_pass_rate` 等が未設定のため、デフォルト0.5が使われる
- drift指標のプレフィックス命名（`DRIFT_PATH_TRAVERSAL_INDICATOR` 等）はベースライン検出器の部分文字列マッチで検出可能。これは「同カテゴリの微妙な変形」を想定した意図的設計
- 完全な適応的トーナメント（候補ごとに動的にフィクスチャを生成）は実装していない
