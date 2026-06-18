# タスク完了報告 — offline candidate evaluation hardening (2026-06-18)

## 概要

Generation 3 アクティブ（best_score=947.66）の状態で、次の paid-credit run が rejected になるリスクを
減らすために、evaluate_candidate.py の上流に静的・決定論的なオフライン契約チェックを追加した。
ネットワーク・Gemini API・subprocess を一切使わずに候補コードを事前スクリーニングし、
5 つの要件が満たされない候補を早期拒否（soft rejection, is_tool_failure=False）する。

## 変更ファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `scripts/candidate_contract.py` | 新規作成 | オフライン契約チェック本体 |
| `scripts/evaluate_candidate.py` | 修正 | Step 2 として contract チェックを挿入 |
| `tests/test_candidate_contract.py` | 新規作成 | candidate_contract の包括的テスト |
| `tests/test_evaluate_candidate.py` | 修正 | `_MINIMAL_CANDIDATE` を core/detector.py 実コンテンツに変更 |

変更していないファイル（FROZEN 確認済み）:
- `core/detector.py` — 未変更
- `data/genome.json` — 未変更
- `data/api_usage_ledger.json` — 未変更
- `data/evolution_history.json` — 未変更
- `.github/workflows/**` — 未変更
- `core/fitness.py` — 未変更

## 主な変更内容

### 1. `scripts/candidate_contract.py`（新規）

以下の 5 つのチェックと統合ランナーを実装:

| チェック | 関数 | 内容 |
|---|---|---|
| ベースライン symbolic 指標保全 | `check_baseline_symbolic_indicators` | 5 つの指標文字列がソース内に全て存在するか（大文字小文字無視） |
| リクエストサーフェスカバレッジ（静的） | `check_request_surface_coverage` | AST walk で `request.X` 属性と `.items()/.keys()/.values()` チェーンを解析 |
| リクエストサーフェスカバレッジ（行動） | `check_request_surface_coverage_behavioral` | 合成 Request を渡して各フィールドで検出が起きるか確認（テスト用） |
| ミューテーション境界整合性 | `check_mutation_region_integrity` | `# === MUTATION_START ===` / `# === MUTATION_END ===` の存在・一意性・順序を確認 |
| 候補ファイルハッシュ整合性 | `check_candidate_hash_consistency` | SHA-256 実測値と reported_hash の一致確認 |

統合ランナー `run_candidate_contract_checks(candidate_path, reported_hash, base_source)` は
4 チェックを実行し `{passed, rejection_reasons, contract_checks, candidate_hash}` を返す。

`base_source` は明示提供の場合のみ境界外変更チェックを有効化（自動ロードなし）。

### 2. `scripts/evaluate_candidate.py`（修正）

AST バリデーション（Step 1）とリソース制限設定（Step 3）の間に Step 2 を追加:

```
Step 1: AST validate
Step 2: Offline contract checks (新規追加)
Step 3: POSIX resource limits
Step 4: Subprocess evaluation
```

- `core/detector.py` を明示的に読み込み `base_source` として渡す
- 契約チェック失敗時: `is_tool_failure=False` で早期 return（soft rejection）
- 全 result dict と `_write_report` に `contract_checks`, `rejection_reasons` キーを追加

### 3. `tests/test_candidate_contract.py`（新規）

8 テストクラス・計 ~30 テストケース:

- `TestBaselineSymbolicIndicators` — 全存在・1 欠如・2 欠如・大文字小文字
- `TestRequestSurfaceCoverageStatic` — full coverage・method 欠如・query/header keys/values 片側のみ・構文エラー
- `TestRequestSurfaceCoverageBehavioral` — full detection・body 未検出
- `TestMutationRegionIntegrity` — marker 欠如・重複・順序逆・境界外変更あり/なし
- `TestCandidateHashConsistency` — 一致・不一致・reported_hash=None・ファイル不存在
- `TestRunCandidateContractChecks` — 統合チェック（合格・失敗・ファイル不存在）
- `TestAdoptionGateScore` — score == previous_best は拒否、score > は通過
- `TestEvaluateCandidateContractIntegration` — evaluate_candidate 経由で contract_checks フィールドが report に含まれること

### 4. `tests/test_evaluate_candidate.py`（修正）

`_MINIMAL_CANDIDATE` を `core/detector.py` の実コンテンツに変更:

```python
_MINIMAL_CANDIDATE = (_PROJECT_ROOT / "core" / "detector.py").read_text(encoding="utf-8")
```

理由: 旧スタブ（`class Detector(_Base): pass`）は mutation marker・symbolic 指標・
リクエストサーフェスをすべて欠いており、Step 2 のオフライン契約チェックで拒否されるため、
既存テスト 10 件が失敗していた。実コンテンツに変更することで全チェックを通過する。

## 後検証結果

```
pytest tests/ -q
2253 passed, 5 warnings in 7.02s
```

全テスト通過確認済み。

## API・外部リソース使用状況

- Gemini API 呼び出し: **なし**
- 外部モデル API 呼び出し: **なし**
- workflow_dispatch トリガー: **なし**
- GitHub Actions 手動 rerun: **なし**
- paid-credit run 開始: **なし**
- data/api_usage_ledger.json 編集: **なし**
- data/genome.json 編集: **なし**（generation=3, best_score=947.66, hash 不変）
- data/evolution_history.json 編集: **なし**
- core/detector.py 編集: **なし**
- .github/workflows/** 編集: **なし**

## 事後監査対応（2026-06-18）

監査で指摘された merge-blocking weakness に対応し、以下を追加修正した。

### 静的リクエストサーフェスチェックの強化

`check_request_surface_coverage()` を強化し、以下のパターンは query/header coverage を
**満たさない**ように変更した:

- 裸属性アクセス (`request.query`, `request.headers`)
- `.get(...)` 呼び出し (`request.query.get(...)`, `request.headers.get(...)`)
- `str()` 変換 (`str(request.query)`, `str(request.headers)`)
- f-string 補間 (`f"{request.query}"`, `f"{request.headers}"`)
- 辞書インデクシング (`request.query["x"]`, `request.headers["x"]`)

coverage として認める唯一のパターン:
- `.items()` → keys + values 両方を満たす
- `.keys()` → keys のみ、`.values()` → values のみ
- `.keys()` と `.values()` の両方 → keys + values 両方を満たす

Generation 3 の `core/detector.py`（`request.query.items()` / `request.headers.items()` 使用）は
引き続き全チェックを通過することを確認済み。

### missing-candidate result dict の修正

candidate ファイルが存在しない場合の早期 return dict に
`contract_checks: []` と `rejection_reasons: [...]` を追加し、
全 result dict への記載という PR の主張と一致させた。

### 追加テスト

`tests/test_candidate_contract.py` に `TestRequestSurfaceCoverageTightened` クラス（19 件）を追加。
`pytest tests/ -q`: 2272 passed（追加前 2253 から増加）。

## 残存事項・注意点

- `check_request_surface_coverage_behavioral` は evaluate_candidate.py の通常フロー（Step 2）では
  **呼ばれない**。静的 AST チェック（`check_request_surface_coverage`）のみが通常フローに組み込まれている。
  行動チェックはテストコードから直接呼ぶ用途を想定。
- `base_source` の自動ロードは意図的に削除済み。evaluate_candidate.py 側で明示提供する設計。
- 採点ゲート（adoption gate）: `score > previous_best_score` の厳格な不等号は変更していない
  （`core/fitness.py` 未変更）。

---

### Audit P1 follow-up — 行動的リクエストサーフェスチェック（2026-06-18）

Codex P1「Verify request surface coverage at runtime」に対応した。

**問題**: 静的 AST チェックは `if False:` ブロック内の unreachable code を通過させる。
`request.headers.items()` が unreachable block にあれば static check は pass するが、
runtime では headers を検査しない candidate が fitness まで到達できた。

**対応**:

- `scripts/candidate_contract.py` に `run_behavioral_surface_check_subprocess()` を追加
  - isolated subprocess (POSIX resource limits + stripped env + no API keys) で candidate を実行
  - 7 つの synthetic `Request`（field ごと 1 件）を使って全 surface field を個別検証
  - candidate code は親プロセスで import しない
- `scripts/evaluate_candidate.py` に Step 2b を追加
  - Step 2a（static）通過後、Step 3（resource limits）前に実行
  - harness error → `is_tool_failure=True`、coverage miss → soft reject（`is_tool_failure=False`）
  - `contract_checks` に `request_surface_coverage_behavioral` エントリを追加

**確認**:

- `core/detector.py`（generation 3）は静的・行動的両チェックを通過することを確認
- `if False:` unreachable code を持つ candidate は behavioral check で拒否されることを確認
- `is_tool_failure=False` で soft reject されることを確認
- `pytest tests/ -q`: `2294 passed`
- frozen files 未変更
- Gemini / 外部 API / workflow_dispatch / paid-credit run なし
