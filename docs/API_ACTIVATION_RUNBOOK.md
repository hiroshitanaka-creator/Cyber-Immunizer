<!--
AI_DOC_META
status: RUNBOOK
scope: Phase 3 API activation procedure, Gemini 3 Flash Preview operational runbook, and paid-credit current state (PR #60-#62).
use_for:
  - planning and executing the first Phase 3 paid-credit run
  - understanding the Gemini 3 Flash Preview configuration and safe operation
  - Project Owner guided activation procedure and next steps
  - confirming Phase 3 activation PRs are merged and first run is pending
do_not_use_for:
  - executing multiple paid-credit runs without reviewing each result
  - setting promote_approved=true before reviewing first run results
  - asserting GitHub Secrets state (Project Owner verifies out-of-band)
  - calling Gemini API directly from this document
related:
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
last_reviewed: 2026-06-04
AI_DOC_META_END
-->
# Cyber-Immunizer API Activation Runbook

> **目的**: GEMINI_API_KEY を登録し、実際の Gemini API 呼び出しを有効化する前に迷わないよう、手順と安全チェックリストをまとめたドキュメントです。  
> このドキュメントはAPIキーを含みません。APIキーをリポジトリにコミットしてはいけません。

---

## ⚠️ 現在の状態: Phase 3 activation 完了 / 初回 paid-credit run 待機中

> **Phase 3 activation PR (#58–#62) は main に merge 済み。**  
> **paid-credit path は準備完了。過去の paid-credit API call 記録は存在する（gemini-3.1-flash-lite 成功記録あり — `data/api_usage_ledger.json` 参照）。**  
> **gemini-3-flash-preview での controlled paid-credit run は未実行。次のステップ: Project Owner が 1 回だけ手動実行する。**

| 項目 | 状態 |
|---|---|
| Phase 3 activation PR | ✅ #58–#62 merge 済み |
| `live_model_enabled` | `true` |
| Primary model | `gemini-3-flash-preview` |
| Fallback model | `gemini-3.1-flash-lite` |
| 過去の paid-credit API call 記録 | 存在する（gemini-3.1-flash-lite 成功 × 1 など） |
| Gemini 3 Flash Preview controlled run | **未実行** — gemini-3-flash-preview 構成での確認 run が次ステップ |
| `promote_approved` | `false` — 初回 run 結果確認前は禁止 |

### 現在の制約

| 制約 | 内容 |
|---|---|
| **paid-credit run** | 1 回のみ実行し、結果を確認してから次のアクションを判断する |
| **`promote_approved`** | `false` のまま維持する。初回 run 結果確認前に `true` にしない |
| **連続 run 禁止** | 1 run ごとに ledger/candidate/evaluate 結果を確認してから次を実行 |
| **quota / billing** | Project Owner が帯域外で検証。リポジトリファクトとして主張しない |

詳細は **[`docs/API_ACTIVATION_CHECKLIST.md`](./API_ACTIVATION_CHECKLIST.md)** の「Phase 3 Paid-Credit 現在地」セクションを参照してください。

---

## 旧状態（Phase 2.5 closeout 完了時点）

> ※ 以下は Phase 2.5 closeout 完了時点の記録です。Phase 3 activation PR #58–#62 の merge により状態が変わっています。

### Phase 3 開始前の確認事項（完了済み）

Phase 3 開始前に、API Activation Checklist の全項目を Project Owner が確認・承認しました。

| 確認事項 | 状態 |
|---|---|
| GEMINI_API_KEY 設定 | ✅ Project Owner が帯域外で検証済み |
| `live_model_enabled=true` 変更 | ✅ PR #58 で実施済み |
| Gemini API call | 待機中（初回 paid-credit run が次のステップ） |
| GPT Audit Gate レビュー | ✅ 各 PR でレビュー済み |

### paid-credit preflight（完了済み）

Preflight run #26733824493 が成功しました:
- `GEMINI_API_KEY_PRESENT=true`
- `api_call_performed=false`
- `ledger_written=false`
- `patch_path=null`
- `live_model_enabled=false`（preflight 時点）
- `budget_available=true`

---

## 現在の状態

- Phase 2.5 closeout 完了済み
- 通常CI成功済み
- noop workflow成功済み
- offline-sample workflow成功済み
- gemini-paid-credit-preflight 実施済み（run #26733824493）
- Phase 3 activation PR #58–#62 merge 済み
- `live_model_enabled=true` — 実 Gemini API call は未実行（初回 paid-credit run 待機中）
- GitHub Secret 設定は Project Owner が帯域外で管理。リポジトリファイルはシークレット値を含まない

---

## Gemini 3 Flash Preview 運用ランブック（PR #62）

> **このセクションは Gemini 3 系モデル (`gemini-3-flash-preview` / `gemini-3.1-flash-lite`) を使用する paid-credit run の運用上の注意事項を記録する。**

### モデル設定

| 項目 | 値 | 出典 |
|---|---|---|
| Primary model | `gemini-3-flash-preview` | PR #62 / `data/genome.json` |
| Fallback model | `gemini-3.1-flash-lite` | PR #62 / `data/genome.json` |
| Thinking config (Gemini 3 のみ) | `ThinkingConfig(thinking_level="low")` | PR #62 |
| `thinking_budget` | 使用しない | PR #62（`thinking_level` で代替） |

### Thinking Token 予算管理

| 項目 | 内容 |
|---|---|
| `_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS` | `1024` — pre-call budget gate 専用の保守的上限。API に送信しない |
| Actual thinking tokens | `response.usage_metadata.thoughts_token_count` から取得 |
| `actual_billable_response_tokens` | `actual_output_tokens + actual_thinking_tokens`（片方 None なら fallback） |
| Cost 計算 | `max(pre-call estimate, actual billable response tokens)` で過小記録を防止 |
| 超過時の動作 | actual > estimate の場合、usage 記録後に patch 返却を拒否（fail-closed） |

### SDK 互換 Guard（PR #62）

- `ThinkingConfig(thinking_level="low")` の構築は `except Exception as exc` で broad guard
- `type(exc).__name__` をエラーメッセージに含め、SDK validation 例外（`ValueError` 等）も fail-closed
- ThinkingConfig 構築失敗 → 即時 `(None, None, None, None, error_str)` 返却

### Syntax Validation Guard（PR #61 / PR #65）

- `replacement_code` は Propose 段階で `ast.parse()` のみで検証（実行しない）
- 以下のラッパーに splice して `ast.parse()` を実行:
  ```
  def _candidate_body(request):
      # === MUTATION_START ===
  {replacement_code（as-is、インデント維持）}
  # === MUTATION_END ===
  ```
  - ラッパーの先頭行は `def _candidate_body(request):` — `request` パラメータあり
  - `MUTATION_START` は 4 スペースインデント、`MUTATION_END` はカラム 0（`core/detector.py` に合わせる）
  - `replacement_code` はインデント必須: top-level 文は 4 スペース、if/for/while/try ブロック内の nested 文は 8/12/16 スペース等の通常 block depth に従う
  - top-level `return DetectionResult(...)` は 4 スペース; ブロック内の nested `return DetectionResult(...)` は 8 スペース以上
- `SyntaxError` / `IndentationError` → patch 返却拒否（`mutation_patch.json` に書き込まない）
- `UnicodeError` → fail-closed（エラー文字列は `replacement_code` 本文をエコーしない）
- 対象: 不正 Python 構文、無インデント、lone surrogate / Unicode 系 parser failure

### Model Migration 履歴（PR #60）

| 変更前 | 変更後 | 理由 |
|---|---|---|
| `model_name: gemini-2.0-flash` | `gemini-3.1-flash-lite` (PR #60) → `gemini-3-flash-preview` (PR #62) | 停止済みモデル ID の 404 NOT_FOUND を解消 |
| `fallback: gemini-2.0-flash-lite` | `gemini-2.5-flash-lite` (PR #60) → `gemini-3.1-flash-lite` (PR #62) | 同上 |

---

## APIキー登録前チェック

API キーを GitHub Secrets に登録する前に、以下をすべて確認してください。

- [ ] Google Cloud Billing linked project を確認（Project Owner が帯域外で検証）
- [ ] Gemini API key が billing-linked paid project のものか確認（Project Owner が帯域外で検証）
- [ ] quota / billing / budget caps / free-tier 制約を Project Owner が帯域外で検証（リポジトリファクトとして主張しない）
- [ ] GitHub Secrets に登録する前に、キーをファイル・README・Issue・PRコメントへ貼らない
- [ ] GitHub Secrets の名前は `GEMINI_API_KEY` にする
- [ ] `data/genome.json` の `live_model_enabled` は `false` のままにする

---

## GitHub Secrets 登録手順

1. **Repository Settings** を開く
2. 左メニューから **Secrets and variables** → **Actions** を選択
3. **New repository secret** をクリック
4. **Name**: `GEMINI_API_KEY`
5. **Value**: `<API key>`（キーの値を貼り付ける）
6. **Add secret** をクリックして保存

> ⚠️ 保存後、値は再表示されません。登録直後に別タブで貼り付けないでください。

---

## preflight 実行手順

**workflow_dispatch で実行（推奨）:**

```
GitHub Actions → Cyber-Immunizer Evolution Loop
→ Run workflow → mode: gemini-paid-credit-preflight
```

### 期待結果（ジョブ）

| ジョブ | 期待結果 |
|---|---|
| Propose Mutation | ✅ success |
| Persist API Usage Ledger | ⏭ skipped（ledger未変更） |
| Finalize Propose Status | ✅ success |
| Apply and Evaluate Candidate | ⏭ skipped（patch未生成） |
| Promote Candidate | ⏭ skipped（candidate未評価） |

### 期待 JSON（propose ジョブの出力）

preflight 成功時の期待出力（以下の全フィールドを検証する）:

```json
{
  "success": true,
  "mode": "gemini-paid-credit-preflight",
  "api_call_performed": false,
  "ledger_written": false,
  "patch_path": null,
  "live_model_enabled": false,
  "gemini_api_key_present": true,
  "budget_available": true
}
```

> ⚠️ preflight 成功は API 呼び出しを承認しません。`live_model_enabled=true` への変更は専用 Phase 3 activation PR でのみ実施します。

---

## preflight 失敗時の分類

### GEMINI_API_KEY missing

**意味**: GitHub Secrets に `GEMINI_API_KEY` が未登録

**対応**:
- Repository Settings → Secrets and variables → Actions を確認
- APIキーをログやファイルに貼らない
- Secrets 登録後、再度 preflight を実行

---

### live_model_enabled=true

**意味**: API有効化前に `live_model_enabled` が `true` になっている

**対応**:
- `data/genome.json` で `live_model_enabled` を `false` に戻す
- `live_model_enabled=true` への変更はレビュー済みPRでのみ実施する
- このドキュメントの「preflight成功後の手順」に従って順序どおりに進める

---

### malformed ledger

**意味**: `data/api_usage_ledger.json` が破損またはスキーマ不正

**対応**:
- ファイルを手動で確認する
- 勝手に上書きしない（fail-closed 設計のため、上書きは budget cap を無効化する可能性がある）
- 破損原因を特定してから修正する

---

### budget unavailable

**意味**: monthly / daily budget cap 超過または設定不正

**対応**:
- `data/genome.json` の `monthly_api_budget_usd` / `daily_api_budget_usd` を確認する
- 予算設定を見直す（`> 0` でなければ preflight は失敗する）
- `data/api_usage_ledger.json` で当月・当日の累計支出を確認する

---

## preflight 成功後の手順

preflight が成功した後、以下を**Project Ownerが順序どおりに**確認・実施してください。

> ⚠️ **preflight 成功は API 呼び出しを承認しません。** paid-credit live 実行は以下の全条件が満たされた後にのみ実施します:
> - preflight 成功
> - Project Owner 最終確認
> - 専用 activation PR レビュー・マージ済み
> - workflow_dispatch 手動実行
> - `max_model_requests_per_run <= 1`
> - `promote_approved=false`（最初の live run 時。Project Owner が監査後に別途承認した場合を除く）

1. **GPT Audit Gate で preflight 成功を確認**
   - preflight の JSON 出力を Audit Gate に提示する
   - `api_call_performed=false` / `live_model_enabled=false` / `budget_available=true` を確認

2. **Project Ownerが Billing / Secret / Budget を最終確認**
   - Cloud Billing リンク済みプロジェクトへのアクセスを確認（帯域外で検証）
   - GitHub Secrets に `GEMINI_API_KEY` が正しく登録されていることを確認（帯域外で検証。シークレット値はリポジトリに記録しない）
   - 月次・日次予算が実際の利用計画と一致していることを確認（Project Owner が帯域外で検証）

3. **別PRで `data/genome.json` の `live_model_enabled` を `true` に変更**
   - 直接 main へコミットしない
   - レビュー済みPRを経由する（専用 Phase 3 activation PR）
   - このPR自体が GPT Audit Gate のレビュー対象になる

4. **通常CIを確認**
   - PRが CI を通過していることを確認してからマージする

5. **workflow_dispatch で `mode=gemini-paid-credit` を1回だけ手動実行**
   - スケジュール実行（cron）では絶対に実行しない
   - `max_model_requests_per_run <= 1` を守る
   - 最初の live run では `promote_approved=false` のまま実行する

6. **API usage ledger に記録されたことを確認**
   - `data/api_usage_ledger.json` に新しいエントリが追記されていることを確認

7. **evaluate / promote の結果を GPT Audit Gate で監査**
   - 候補が採用ゲートを通過した場合、昇格前に Audit Gate レビューを実施する
   - `promote_approved=true` は Project Owner が監査結果を確認した後に別途承認する

> ⚠️ preflight が成功しても、自動的にAPIを呼び出すことはありません。ステップ3〜5はProject Ownerの明示的な判断と操作が必要です。

---

## 禁止事項

以下は**絶対に行ってはいけません**。

| 禁止事項 | 理由 |
|---|---|
| APIキーをリポジトリにコミットしない | キーが公開される・履歴に残る |
| APIキーを README / Issue / PR comment に貼らない | 第三者に露出する |
| `live_model_enabled=true` を雑にmainへ直接commitしない | レビューなしの実行防止 |
| `gemini-paid-credit` をcronで実行しない | 意図しない課金・budget cap バイパス |
| `max_model_requests_per_run > 1` にしない | 制御不能な連続API呼び出し防止 |
| raw payload / secrets / full repo text を Gemini に送らない | プライバシー・機密情報保護 |
| malformed ledger を確認なしに上書きしない | budget fail-closed の破壊防止 |

---

## 関連ドキュメント

- [`docs/API_ACTIVATION_CHECKLIST.md`](./API_ACTIVATION_CHECKLIST.md) — API 有効化チェックリスト
- [AUDIT_CHARTER.md](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章
- [`data/genome.json`](../data/genome.json) — ゲノム設定（`live_model_enabled` はここで管理）
- [`data/api_usage_ledger.json`](../data/api_usage_ledger.json) — API 使用量台帳

---

*このドキュメントは Project Cyber-Immunizer の API 有効化手順書です。*  
*APIキーは含まれておらず、含めてはいけません。*  
*Phase 2.5 closeout 完了 / Phase 3 Go/No-Go 準備中に current-state alignment を実施（docs-only）。*  
*最終更新: 2026-06-04*
