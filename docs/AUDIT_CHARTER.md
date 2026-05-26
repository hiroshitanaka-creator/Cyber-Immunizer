# GPT Audit Gate 憲章 — Project Cyber-Immunizer

> **目的**: このプロジェクトへのすべての変更は、マージ前に GPT Audit Gate を通過しなければならない。  
> Audit Gate は「安全性の保証」ではなく「防衛的レビューの一層」である。  
> 最終的な判断は常に **Human Owner（プロジェクト所有者）** が行う。

---

## 1. 役割と責任

| 役割 | 担当 | 責任範囲 |
|---|---|---|
| **Human Owner** | hiroshitanaka-creator | 最終マージ判断・安全方針の決定・BLOCK/APPROVE の覆し権限 |
| **GPT Audit Gate** | GPT 系監査モデル（モデルバージョンに依存しない） | 6カテゴリの構造的レビュー・APPROVE/REQUEST CHANGES/BLOCK の推薦 |
| **Claude Code** | Claude Code 実装環境（モデルバージョンに依存しない） | 実装・テスト作成・コミット・PR準備・Audit Gateへの情報提供 |

> ⚠️ **Claude Code は自ら APPROVE/BLOCK を宣言しない。** それは GPT Audit Gate および Human Owner の権限である。  
> Claude Code は実装の事実と根拠を正確に提供し、レビューを支援する。  
> 特定モデルバージョン名（例: GPT-4o, claude-sonnet-x-y）はコミット・PR・コメントに記載しない。

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

## 5. API Activation 監査条件（Phase 1-D）

API キー登録・`live_model_enabled=true` への変更・実 API 実行を含む PR は、以下の追加条件でレビューする。

### BLOCK（即座にブロック）

以下のいずれかを検出した場合、即座に BLOCK を推薦する：

- **GEMINI_API_KEY の露出**: キーがファイル・README・PRコメント・Issue に含まれている
- **preflight 未確認の live_model_enabled=true**: `gemini-paid-credit-preflight` の成功確認前に `live_model_enabled` が `true` に変更されている
- **cron による gemini-paid-credit 実行**: スケジュール実行が `gemini-paid-credit` または `live-model` モードで呼び出される設定になっている
- **ledger 未記録**: 実 API 呼び出しにもかかわらず `api_usage_ledger.json` が更新されていない
- **budget cap の fail-open**: `assert_budget_available` がバイパスされるか、budget が 0 以下のまま API が呼び出されている

### REQUEST CHANGES（修正要求）

以下のいずれかを満たす場合に REQUEST CHANGES を推薦する：

- API activation 手順が README / `docs/API_ACTIVATION_RUNBOOK.md` の記載と一致していない
- preflight 結果の JSON（`api_call_performed`, `live_model_enabled`, `budget_available` 等）が PR に添付されていない
- Billing / Secret 確認が人間オーナーの判断として明示的に記録されていない

### APPROVE（承認）

以下をすべて満たす場合のみ APPROVE を推薦する：

- `gemini-paid-credit-preflight` が成功し、その JSON 出力が PR に添付されている
- `live_model_enabled=true` への変更がレビュー済みPRを経由している（直接 main コミットでない）
- `GEMINI_API_KEY` が GitHub Secrets にのみ存在し、リポジトリ内のいかなるファイルにも含まれていない
- `gemini-paid-credit` が `workflow_dispatch` による1回のみの手動実行であることが確認されている
- 実行後に `api_usage_ledger.json` への記録が確認されている

---

## 6. 本憲章の変更手続き

- 本文書の変更は、それ自体が Audit Gate レビューの対象となる
- BLOCK 基準の削除・緩和は Human Owner の明示的な書面上の承認が必要
- GPT Audit Gate のモデルを変更する場合は、新モデルでテスト審査を実施する

---

## 7. Phase transition rule（Phase 1 → Phase 2）

### Phase 1 → Phase 2 への移行条件

**Phase 2（API未接続運用強化）への移行は、Human Owner の明示的な決定によってのみ開始されます。**

> ⚠️ **Phase 2 は API 接続を含みません。**  
> GEMINI_API_KEY 登録・`live_model_enabled=true` への変更・実 Gemini API call は **Phase 3 以降**で実施します。  
> Phase 1 → Phase 2 の移行はコスト発生を伴わず、`live_model_enabled=false` を維持したまま進行します。

#### Phase 2 移行の内容

Phase 2（API未接続運用強化）への移行は、以下の運用強化を含みます。API 接続は含みません。

- README dashboard 精度向上
- rollback / backtrack 設計の文書化
- evolution_history の監査強化
- offline-sample の dry-run / promote 分離検討
- API 接続前の運用チェックリスト整備

Phase 2 中は以下を実施しません：

- GEMINI_API_KEY 登録（Phase 3 以降）
- `live_model_enabled=true` への変更（Phase 3 以降）
- 実 Gemini API call（Phase 3 以降）

#### GPT Audit Gate による確認事項

Phase 2 移行を含む PR を審査する際、GPT Audit Gate は以下をすべて確認しなければならない：

1. **CI success** — `python -m pytest` が全件 pass していること
2. **API 未接続の維持** — `data/genome.json` の `live_model_enabled` が `false` であること
3. **GEMINI_API_KEY 未コミット** — `GEMINI_API_KEY` がリポジトリ内のいかなるファイルにも含まれていないこと
4. **Phase 2 計画との整合** — `docs/PHASE_2_PLAN.md` の内容と矛盾していないこと
5. **preflight fail-closed 確認** — `GEMINI_API_KEY` 未登録時に preflight が fail-closed で失敗すること

#### BLOCK 条件（Phase 1 → Phase 2 transition に関する追加ルール）

以下のいずれかを検出した場合、即座に **BLOCK** を推薦する：

- **Phase 2 移行に GEMINI_API_KEY 登録を含める変更** — Phase 1 → Phase 2 移行の範囲として GEMINI_API_KEY 登録を前提とする変更は即座に BLOCK する（GEMINI_API_KEY 登録は Phase 3 の範囲）
- **Phase 2 移行に live_model_enabled=true を含める変更** — Phase 1 → Phase 2 移行の範囲として `live_model_enabled=true` を含む変更は即座に BLOCK する（`live_model_enabled=true` への変更は Phase 3 の範囲）
- **Human Owner decision なしの live_model_enabled=true** — Human Owner の明示的な決定を経ずに `live_model_enabled` が `true` に変更されている PR は即座に BLOCK する
- **Phase 1 baseline 破壊** — `docs/PHASE_1_BASELINE.md` に記載された Safety invariants が変更・削除されている PR は BLOCK する

Phase 1 完了状態の詳細は `docs/PHASE_1_BASELINE.md` を参照してください。  
Phase 3（実 Gemini API 接続）への移行条件は「セクション 8. Phase 2 transition rule」を参照してください。

---

## 8. Phase 2 transition rule（Phase 2 中の制約 / Phase 2 → Phase 3）

> **現在は Phase 2（API未接続運用強化）フェーズです。**  
> Phase 2 中は API を接続しません。API 接続は Phase 3 以降です。

### Phase 2 中の BLOCK 条件

以下のいずれかを含む PR を検出した場合、GPT Audit Gate は即座に **BLOCK** を推薦する：

- **Phase 2 中の `live_model_enabled=true` への変更** — Phase 2 中に `data/genome.json` の `live_model_enabled` を `true` に変更する PR は即座に BLOCK する
- **GEMINI_API_KEY 登録を前提とするコード変更** — API キーが存在する前提で動作するコード・ワークフロー変更（`live_model_enabled=true` を前提とする変更を含む）は BLOCK する
- **Phase 2 中の cron API 実行設定** — スケジュール実行が `noop` 以外のモードで API を呼び出す設定変更は BLOCK する

### Phase 2 中の REQUEST CHANGES 条件

以下のいずれかを含む PR を検出した場合、GPT Audit Gate は **REQUEST CHANGES** を推薦する：

- **GEMINI_API_KEY 登録を前提とするドキュメント変更** — Phase 2 中に API キー登録を必須ステップとして記述するドキュメント変更（Phase 3 以降として明示すれば許容）
- **Phase 2 計画との不整合** — `docs/PHASE_2_PLAN.md` に記載された Phase 2 の実施内容・禁止事項と矛盾する変更

### Phase 3 への移行条件

**Phase 3（実 Gemini API 接続）の開始は、Human Owner（hiroshitanaka-creator）の明示的な判断が必要です。**

以下をすべて満たした場合にのみ、Phase 3 への移行を検討します：

1. **Phase 2 完了** — `docs/PHASE_2_PLAN.md` に記載された全実施項目が完了している
2. **CI success** — `python -m pytest` が全件 pass していること
3. **API 接続前チェックリスト完了** — Human Owner が `docs/API_ACTIVATION_RUNBOOK.md` のチェックリストを完了している
4. **`live_model_enabled=false` の維持** — Phase 3 開始前の時点で `live_model_enabled` が `false` であること
5. **Human Owner の明示的決定** — Human Owner が「Phase 3 へ移行する」と明示的に決定し、その記録がある

> ⚠️ **Phase 3 移行は不可逆的なコスト発生を伴う可能性があります。**  
> AI エージェント（Claude Code）は Phase 3 移行を自律的に判断・実施しません。  
> Human Owner の明示的な判断と操作（GEMINI_API_KEY 登録・`live_model_enabled=true` への変更）が必要です。

Phase 2 の計画・実施内容・禁止事項の詳細は `docs/PHASE_2_PLAN.md` を参照してください。

---

*このドキュメントは Project Cyber-Immunizer のセキュリティガバナンス文書です。*  
*最終更新: 2026-05-26*
