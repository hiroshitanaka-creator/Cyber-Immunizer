# タスク完了報告 — PR-D' Structured Rule Proposal Output Path

## 概要

PR #149 の陳腐化した実装に代わり、最新 main を基に、明示的なオプトイン・オフライン限定の構造化ルール提案出力パスを `scripts/propose_mutation.py` に実装しました。

`--structured-rules --offline-sample` モードを追加し、API 呼び出しなしに `.cyber_immunizer/structured_rules.json` を生成します。
ランタイムデータベース動作に統合されず、レジャーや進化履歴も変更されません。

## 変更ファイル一覧

- `scripts/propose_mutation.py` — 構造化ルール提案出力パスを実装
- `tests/test_structured_rules_proposal_output.py` — 25 個の新規テスト

## 主な変更内容

### 1. CLI オプション追加
```
--structured-rules: 構造化ルール生成モードを有効化（--offline-sample 必須）
```

### 2. 構造化ルール生成機能
- **`build_offline_sample_structured_rules()`**
  - スキーマバージョン 1 に準拠した有効な構造化ルール文書を生成
  - 5 つの標準化された記号表示インジケータを含む：
    - `path_traversal_indicator`
    - `script_injection_indicator`
    - `sqli_indicator`
    - `command_delimiter_indicator`
    - `encoded_traversal_indicator`
  - すべてのリクエストサーフェス（method, path, query, headers, body）をカバー
  - 安全なフォールバック：`blocked: false, confidence: 0.0, matched_signals: []`

- **`propose_structured_rules(offline_sample=bool)`**
  - オフラインモード専用の提案関数
  - `validate_rules_schema()` で即座にバリデーション
  - バリデーション失敗時はフェイルクローズ
  - Gemini / ライブモデル / 有料クレジット呼び出しなし

### 3. CLI ハンドラ
```
--structured-rules --offline-sample --json
```
動作：
- `.cyber_immunizer/structured_rules.json` に構造化ルールを書き込み
- 既存の `.cyber_immunizer/mutation_patch.json` を削除
- JSON 出力：`patch_path: null`, `rules_path: <path>`, `rule_count: 5`

### 4. ライブモデル/有料クレジット拒否
```
--structured-rules --live-model --allow-live-model
→ エラー：モードは一致していません
```

### 5. 陳腐なパッチのクリーンアップ
構造化ルール成功時に実行：
- `mutation_patch.json` が存在すれば削除
- `patch_path: null` として報告

## 安全性プロパティ

| プロパティ | 状態 |
|---|---|
| Gemini API 呼び出し | なし |
| 有料クレジット呼び出し | なし |
| ライブモデル呼び出し | なし |
| workflow_dispatch トリガー | なし |
| ゲノム変更 | なし |
| レジャー変更 | なし |
| ランタイムデテクタ統合 | なし |
| core/detector.py 変更 | なし |
| inspect_request() デフォルト動作変更 | なし |

## 明示的オプトイン動作

`--structured-rules` 使用には以下が **必須** ：
1. `--offline-sample` フラグ
2. ライブモデル/有料クレジット フラグは **拒否**

## オフライン専用制限

- Gemini / LLM / 外部 API 呼び出しなし
- ローカルのみで実行
- `.cyber_immunizer/` の隔離アーティファクト出力

## 生成アーティファクトの非コミット

`.cyber_immunizer/` はすでに `.gitignore` に指定されているため：
```
.cyber_immunizer/
```
生成されたファイルは自動的に無視されます。

## テスト実行結果

### テスト追加
`tests/test_structured_rules_proposal_output.py` — 25 個のテスト

カテゴリ：
1. **ビルダー関数テスト**（12 個）
   - スキーマバージョン、ルール数、インジケータ、オペレータ、フィールド
   - 信度範囲、バリデーション、サーフェスフィールド、フォールバック

2. **提案関数テスト**（4 個）
   - オフラインモード成功、失敗ケース、バリデーション互換性

3. **CLI テスト**（4 個）
   - `--offline-sample` 必須チェック
   - JSON 出力形式
   - ライブモデル/有料クレジット拒否

4. **クリーンアップテスト**（2 個）
   - 陳腐なパッチ削除
   - パッチ非生成確認

5. **互換性テスト**（3 個）
   - バリデータ互換性
   - 構造化評価器互換性
   - 構造化デテクタ互換性

### テスト実行コマンド
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

### CLI スモークテスト
```bash
# 成功テスト
python scripts/propose_mutation.py --structured-rules --offline-sample --json
# 出力：mode="structured-rules-offline-sample", rule_count=5, patch_path=null

# バリデーション
python scripts/validate_structured_rules.py .cyber_immunizer/structured_rules.json
# 結果：PASSED

# 陳腐パッチクリーンアップ確認
rm -f .cyber_immunizer/structured_rules.json .cyber_immunizer/mutation_patch.json
```

## レイヤー宣言

このタスクが進めたレイヤー：

- [x] **Layer 1 — Research Foundation**
  - 提案出力パスの実装完了
  - オフラインサンプル生成の検証
  - スキーマ互換性の確認

- [ ] **Layer 2 — Value Validation**
  - 実装理由：このPRは提案出力パスのみを追加。
    実際の脅威検証、Owner 受け入れ、ランタイム統合は含まれていません。

- [ ] **Layer 3 — AI Operation Control**

- [ ] **None**

## 完了条件チェック

- [x] 新 PR ブランチは PR #159 後の latest main に基づいている
- [x] `--structured-rules --offline-sample` が機能する
- [x] 構造化ルール出力はスキーマ有効
- [x] ライブ/有料クレジット構造化ルールモードはフェイルクローズ
- [x] ランタイム統合なし
- [x] core/detector.py が変更されていない
- [x] inspect_request() デフォルト動作が変更されていない
- [x] `.cyber_immunizer/structured_rules.json` はローカル生成だがコミットされない
- [x] `.cyber_immunizer/mutation_patch.json` が構造化ルール成功後に残らない
- [x] 陳腐なパッチクリーンアップをテストでカバー
- [x] `--offline-sample` なしフェイルクローズをテストでカバー
- [x] バリデータ/評価器互換性をテストでカバー
- [x] Gemini / 有料クレジット / workflow_dispatch を使用していない
- [x] タスク報告書が Layer 1 のみと明記している（Layer 2 ではない）
- [x] 最終的な `git status --short` に生成アーティファクトなし
