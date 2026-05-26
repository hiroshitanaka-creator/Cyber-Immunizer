# GPT Audit Gate 憲章 — Project Cyber-Immunizer

> **目的**: このプロジェクトへのすべての変更は、マージ前に GPT Audit Gate を通過しなければならない。  
> Audit Gate は「安全性の保証」ではなく「防衛的レビューの一層」である。  
> 最終的な判断は常に **Human Owner（プロジェクト所有者）** が行う。

---

## 1. 役割と責任

| 役割 | 担当 | 責任範囲 |
|---|---|---|
| **Human Owner** | hiroshitanaka-creator | 最終マージ判断・安全方針の決定・BLOCK/APPROVE の覆し権限 |
| **GPT Audit Gate** | GPT-4o（または同等モデル） | 6カテゴリの構造的レビュー・APPROVE/REQUEST CHANGES/BLOCK の推薦 |
| **Claude Code** | claude-sonnet-4-6 | 実装・テスト作成・コミット・PR準備・Audit Gateへの情報提供 |

> ⚠️ **Claude Code は自ら APPROVE/BLOCK を宣言しない。** それは GPT Audit Gate および Human Owner の権限である。  
> Claude Code は実装の事実と根拠を正確に提供し、レビューを支援する。

---

## 2. 監査カテゴリ

GPT Audit Gate は以下の 6 カテゴリを評価する。

### カテゴリ A: アーキテクチャ整合性

- MAPE-K ループ（Monitor → Propose → Evaluate → Promote）の構造が維持されているか
- propose / evaluate / promote の3ジョブ分離が崩れていないか
- 変異境界マーカー（`MUTATION_START` / `MUTATION_END`）の不変性が保たれているか
- `core/types.py` のイミュータブルデータクラス設計が損なわれていないか

### カテゴリ B: セキュリティ境界

- シークレット（`GEMINI_API_KEY`, `GITHUB_TOKEN` 等）が propose ジョブ外に漏れていないか
- 生成コードが evaluate ジョブ外で実行されていないか
- `_BLOCKED_CODE_TOKENS` および `_BLOCKED_PROMPT_TOKENS` の禁止リストが弱められていないか
- ASTポリシー（`core/policy.py`）の禁止パターン（`import`, `eval`, `exec`, `os.`, dunder属性 等）が削除・緩和されていないか
- プリフライトシークレットスキャンが削除・バイパスされていないか
- 候補コードの `_validate_replacement_code` 検証が弱められていないか
- symbolic indicator（`path_traversal_indicator` 等）に実際のエクスプロイト文字列が混入していないか

### カテゴリ C: フィットネス・リグレッション品質

- フィットネス計算式が変更・弱化されていないか（係数: tp_rate×1000, fp_rate×-2000, fn_rate×-1500）
- リグレッション通過率の要件（`min_regression_pass_rate == 1.0`）が緩和されていないか
- `candidate_hash` による SHA-256 検証が maintain されているか
- テストケースが削除・弱化されていないか

### カテゴリ D: コスト・API ガバナンス

- `monthly_api_budget_usd` / `daily_api_budget_usd` の上限チェックが削除・バイパスされていないか
- `api_budget.assert_budget_available` の fail-closed 動作（不正 ledger → 拒否）が維持されているか
- スケジュール実行が `noop` 以外のモードで呼び出される設定になっていないか
- `max_model_requests_per_run <= 1` の制約が守られているか
- `send_repository_full_text`, `send_raw_payloads`, `send_secrets` が false に保たれているか

### カテゴリ E: ドキュメント整合性

- README の安全方針・テスト数・ステータスブロックが実態と一致しているか
- `AUDIT_CHARTER.md` (本文書) の内容が変更・弱化されていないか
- PR テンプレートのチェックリストが適切に維持されているか

### カテゴリ F: 法的・デュアルユース境界

- 攻撃コード・スキャナ・資格情報窃取ロジック・マルウェア持続化が混入していないか
- 実際のエクスプロイトペイロード・CVE詳細・シェルコードが含まれていないか
- 実トラフィックの傍受・外部ホストへのネットワーク接続が追加されていないか

---

## 3. 監査決定

### APPROVE（承認）

以下をすべて満たす場合に APPROVE を推薦する：

- カテゴリ A〜F のすべてで重大な問題がない
- 新規テストが追加変更をカバーしている
- 既存テストが削除・弱化されていない
- コミットメッセージが変更内容を正確に説明している

### REQUEST CHANGES（修正要求）

以下のいずれかを満たす場合に REQUEST CHANGES を推薦する：

- テストカバレッジが不十分（変更に対応するテストがない）
- ドキュメントと実装が不一致
- コストガバナンスの設定が実態と乖離している
- 軽微なセキュリティ境界の弱化（悪意のある意図なし、修正可能）
- ガバナンス上の懸念はあるが、ブロック基準には達しない

### BLOCK（ブロック）

以下のいずれかを検出した場合、即座に BLOCK を推薦する：

- **攻撃コードの混入**: 実際のエクスプロイト、スキャナ、マルウェア、資格情報窃取ロジック
- **シークレットの漏洩**: API キーや認証情報が evaluate / promote ジョブに漏れる変更
- **AST ポリシーの重大な弱化**: `import`, `eval`, `exec`, `os.`, dunder 属性の禁止が削除される変更
- **生成コードの無隔離実行**: 候補コードが subprocess 以外のパスで実行される変更
- **プリフライトスキャンの削除**: `_preflight_secret_scan` または同等の保護の除去
- **ハッシュ検証の削除**: `candidate_hash` による SHA-256 チェックの除去
- **予算キャップの削除**: `assert_budget_available` の呼び出し除去またはバイパス
- **スケジュール実行の API 呼び出し**: cron ジョブが noop 以外のモードで API を呼び出す変更

> ⚠️ BLOCK は Human Owner が明示的に覆さない限り、マージ禁止を意味する。

---

## 4. GPT Audit Gate の出力フォーマット（必須）

GPT Audit Gate は以下のフォーマットで出力を提供しなければならない。

```
## GPT Audit Gate レポート

**PR / ブランチ**: <PR番号またはブランチ名>
**審査日時**: <ISO 8601形式>
**審査モデル**: <使用したGPTモデル>

### カテゴリ別評価

| カテゴリ | 評価 | 所見 |
|---|---|---|
| A: アーキテクチャ整合性 | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |
| B: セキュリティ境界 | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |
| C: フィットネス・リグレッション | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |
| D: コスト・API ガバナンス | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |
| E: ドキュメント整合性 | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |
| F: 法的・デュアルユース | ✅ OK / ⚠️ 要確認 / ❌ 問題あり | <所見> |

### 重要所見

<BLOCK に至る発見、または REQUEST CHANGES の具体的な修正要求>

### 決定

**[ APPROVE / REQUEST CHANGES / BLOCK ]**

理由: <決定の根拠を1〜3文で>
```

---

## 5. 本憲章の変更手続き

- 本文書の変更は、それ自体が Audit Gate レビューの対象となる
- BLOCK 基準の削除・緩和は Human Owner の明示的な書面上の承認が必要
- GPT Audit Gate のモデルを変更する場合は、新モデルでテスト審査を実施する

---

*このドキュメントは Project Cyber-Immunizer のセキュリティガバナンス文書です。*  
*最終更新: 2026-05-26*
