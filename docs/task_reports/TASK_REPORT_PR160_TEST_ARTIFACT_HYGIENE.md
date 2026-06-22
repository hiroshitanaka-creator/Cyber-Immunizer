# タスク完了報告 — PR #160 テスト アーティファクトハイジーン修正

## 概要

PR #160 がマージされた後、テストファイル `tests/test_structured_rules_proposal_output.py` のアーティファクトハイジーンの問題を修正しました。

テストが実リポジトリのルート配下に生成されたファイルを書き込むことを防ぎ、stale patch cleanup を実際の CLI 経路で検証するよう改善しました。

## 背景

PR #160 の構造化ルール提案機能実装後、テストに以下の課題がありました：

1. **リポジトリルート書き込み**: `test_structured_rules_offline_sample_json_output` が subprocess で CLI を実行し、`cwd=_PROJECT_ROOT` で `.cyber_immunizer/structured_rules.json` を実リポジトリに書き込んでいた。

2. **不十分な stale patch テスト**: `test_stale_mutation_patch_removed` が `propose_structured_rules()` 低レベル関数を呼び出した後、テスト内で手動でファイル削除（`stale_patch.unlink()`）を実行していた。実際の CLI クリーンアップパス（`main()` 内で実装）を検証していなかった。

## 変更ファイル一覧

- `tests/test_structured_rules_proposal_output.py` — テスト修正

## 主な変更内容

### 1. 不要な import 削除
- `subprocess` import を削除（subprocess テストは in-process 呼び出しに変更）

### 2. `main` 関数のインポート追加
- `scripts.propose_mutation` から `main` を import

### 3. CLI テストのリファクタリング

#### `test_structured_rules_requires_offline_sample`
- **before**: `subprocess.run(cwd=_PROJECT_ROOT)` でリポジトリルート汚染の可能性
- **after**: 直接 `main(["--structured-rules", "--json"])` を in-process で呼び出し

#### `test_structured_rules_offline_sample_json_output`
- **before**: subprocess + `cwd=_PROJECT_ROOT` → リポジトリルートに `.cyber_immunizer/structured_rules.json` 生成
- **after**: monkeypatch で `_OUT_DIR`, `_OUT_STRUCTURED_RULES`, `_OUT_PATCH` を `tmp_path` に置き換え
- **追加**: in-process `main()` 呼び出し
- **結果**: 生成アーティファクトは `tmp_path` のみ

#### `test_structured_rules_rejects_live_model` / `test_structured_rules_rejects_gemini_paid_credit`
- **before**: subprocess
- **after**: in-process `main()` 呼び出し + `capsys` で stdout キャプチャ

### 4. Stale patch cleanup テストの改善

#### `test_stale_mutation_patch_removed_via_main`（新規）
- **after**: `main()` CLI 経路を実際に検証
- **実装**:
  1. `tmp_path` に stale patch ファイルを作成
  2. monkeypatch で出力パスを `tmp_path` に設定
  3. **実際の `main(["--structured-rules", "--offline-sample", "--json"])` を呼び出し**
  4. stale patch が削除されたこと、rules が作成されたことを検証
- **改善**: 手動削除ロジック（`stale_patch.unlink()`）を削除、実際の CLI cleanup 動作を検証

### 5. テスト出力キャプチャ方式

- **before**: subprocess の stdout を直接キャプチャ
- **after**: pytest の `capsys` fixture で in-process 出力をキャプチャ

## テスト改善のメリット

1. **アーティファクト隔離**: 生成ファイルは `tmp_path` に限定、実リポジトリ非汚染
2. **CLI 動作検証**: 実際の `main()` 経路で cleanup を検証（不完全なテストの除去）
3. **テスト速度**: subprocess 呼び出し廃止で実行時間短縮
4. **手動ロジック廃止**: テスト内での `unlink()` 削除、実装側に検証責任委譲
5. **保守性**: in-process テストは更新も容易

## 完了条件チェック

- [x] リポジトリルートアーティファクト書き込み廃止
- [x] Stale patch cleanup を `main()` CLI 経由で検証
- [x] テスト内の手動クリーンアップロジック削除
- [x] 本番コード変更なし
- [x] 生成アーティファクトはコミットされていない
- [x] Gemini / 有料クレジット / workflow_dispatch 呼び出しなし
- [x] タスク報告書で Layer 3 のみ宣言
- [x] CI パス確認

## 検証結果

### テスト実行
```bash
python -m pytest tests/test_structured_rules_proposal_output.py -q
# 結果：25 passed
```

### 構造化ルール統合テスト
```bash
python -m pytest \
  tests/test_structured_rules_proposal_output.py \
  tests/test_structured_validator.py \
  tests/test_structured_evaluator.py \
  tests/test_structured_detector_integration.py \
  tests/test_structured_detector_equivalence.py \
  -q
# 結果：142 passed
```

### リポジトリ清潔性チェック
```bash
git status --short
# 結果：M tests/test_structured_rules_proposal_output.py のみ

find .cyber_immunizer -maxdepth 1 -type f -print
# 結果：生成ファイルなし

git diff --check
# 結果：空白エラーなし
```

## 安全性確認

- [x] **Gemini API**: 呼び出しなし
- [x] **有料クレジット**: 使用なし
- [x] **workflow_dispatch**: トリガーなし
- [x] **本番動作変更**: なし
- [x] **core/data/.github 変更**: なし
- [x] **生成アーティファクトコミット**: なし

## レイヤー宣言

このタスクが進めたレイヤー：

- [ ] **Layer 1 — Research Foundation**
- [ ] **Layer 2 — Value Validation**
- [x] **Layer 3 — AI Operation Control**
- [ ] **None**

**理由**: このタスクはテスト品質と AI オペレーション・アーティファクトハイジーンを改善。デテクタ機能を進めるものではない。

## PR #160 との関係

- PR #160: 構造化ルール提案出力パスの実装（Layer 1）
- このタスク: PR #160 マージ後の test hygiene フォローアップ（Layer 3）
- 本番動作: **変更なし** — テストのみ改善

## 改善サマリ

| 観点 | 以前 | 以後 | メリット |
|---|---|---|---|
| アーティファクト出力先 | repo root | tmp_path | 実リポジトリ非汚染 |
| CLI テスト方式 | subprocess | in-process | 速度向上、隔離強化 |
| cleanup 検証 | 低レベル関数 + 手動削除 | main() CLI 経由 | 実動作検証 |
| テスト手動ロジック | `stale_patch.unlink()` 含む | 実装側に委譲 | 保守性向上 |
