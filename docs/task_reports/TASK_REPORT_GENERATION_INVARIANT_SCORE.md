# タスク完了報告 — generation-invariant adoption gate score

## 概要

採用ゲートのスコア計算から `changed_lines` を除外し、スコアを世代間で比較可能な
生成不変スコアに移行した。これにより、現行 `core/detector.py` と同一の候補（no-op）が
`genome.json::best_score` を上回る不正なスコア優位を得て採用ゲートを通過できる脆弱性を修正した。
これは PR #105 から独立した新ブランチによる実装である（cherry-pick なし）。

## 変更ファイル一覧

- `core/fitness.py` — スコア式から `changed_lines` を除外、`score_components` 追加
- `core/types.py` — `FitnessReport` ドキュメント更新、`score_components` フィールド追加
- `tests/test_fitness.py` — no-op ゲートテスト追加、スコア式テスト更新
- `data/genome.json` — `best_score` を 729.34 → 939.34 に移行（スキーマ移行のみ）
- `data/project_state.json` — state_id / next_action 更新、移行ノート追加
- `docs/PROJECT_STATE.md` — 現在状態テーブル更新、移行内容を記述

## 主な変更内容

- `_compute_score()` から `changed_lines` パラメータを削除（`-10.0 * changed_lines` 項を除去）
- `changed_lines` は引き続き計算・`FitnessReport.changed_lines` に格納（診断専用）
- `FitnessReport.score_components` フィールドを追加（`dict | None = None`、early-exit では None）
  - `tp_contribution`, `fp_penalty`, `fn_penalty`, `exception_penalty`,
    `code_size_penalty`, `changed_lines_diagnostic`, `gate_score` を含む
- `data/genome.json::best_score` を 729.34 → 939.34 に移行
  - 現行 `core/detector.py` の生成不変スコア（`changed_lines=0` で両式は等価）
  - 昇格ではない。`generation` / `current_detector_hash` は変更なし
- `data/project_state.json` に `score_schema_migration` セクション追加
- `tests/test_project_state_sync.py` のテスト #21 / #22 を新 state_id / next_action に合わせて更新

## 後検証結果

```
python -m core.fitness --candidate core/detector.py --baseline --json
→ score: 939.34 (生成不変スコア確認)

python -m core.fitness --candidate core/detector.py --json
→ passed_adoption_gate: false
→ rejection_reasons: ["score=939.3400 <= previous_best=939.3400"]
(no-op 拒否を確認)

pytest tests/test_fitness.py -q   → 30 passed
pytest tests/test_project_state_sync.py -q → 22 passed
pytest tests/ -q → 2156 passed
```

## 脆弱性の説明

旧実装: `genome.json::best_score=729.34` は旧世代の変更行ペナルティ込みで計算された値。
現行 `core/detector.py` を no-op 候補として評価すると `changed_lines=0`（ペナルティなし）で
スコア 939.34 が得られ、729.34 を超えてゲートを通過できた。

修正後: スコアは世代不変（`tp_rate`, `fp_rate`, `fn_rate`, `exception_count`, `code_chars` のみ）。
`best_score=939.34` に移行したため no-op 候補は 939.34 ≤ 939.34 で拒否される。

## 残存事項・注意点

- `data/evolution_history.json` の過去スコアは旧式で記録されており、歴史記録として残存する。
  これは現在のゲートベースラインには影響しない（`genome.json::best_score` のみを参照するため）。
- ラン 5・6 の歴史的スコア（494.48 / 478.12）は旧式での記録であり、historical record として保持。
  新式での再計算・再分類は行っていない（タスクスコープ外）。
- ラン 7（第 7 次 API 成功記録）は untriaged のまま。本 PR は run 7 から apply / evaluate /
  promote を推論しない。
- PR #105 は設計証拠としてのみ参照した。cherry-pick・マージは行っていない。

## No-API / No-workflow / No-promotion 確認

- Gemini API 呼び出し: なし
- workflow_dispatch: なし
- paid-credit ワークフロー起動: なし
- 候補昇格: なし
- promote_approved: false のまま
- data/api_usage_ledger.json: 変更なし
- data/evolution_history.json: 変更なし
- .github/**: 変更なし
