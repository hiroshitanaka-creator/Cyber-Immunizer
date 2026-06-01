<!--
AI_DOC_META
status: RUNBOOK
scope: Phase 3 API activation procedure and operational checklist. Current state: Phase 2.5 closeout complete, Phase 3 not started.
use_for:
  - planning a dedicated Phase 3 activation PR
  - understanding the order of API activation steps
  - Human Owner guided activation procedure
  - confirming current state is Phase 3 Go/No-Go preparation
do_not_use_for:
  - executing API activation without explicit Human Owner approval and a dedicated activation PR
  - registering GEMINI_API_KEY without explicit Human Owner approval
  - setting live_model_enabled=true outside a dedicated Phase 3 activation PR
  - asserting GitHub Secrets state (Human Owner verifies out-of-band)
related:
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
last_reviewed: 2026-06-01
AI_DOC_META_END
-->
# Cyber-Immunizer API Activation Runbook

> **目的**: GEMINI_API_KEY を登録し、実際の Gemini API 呼び出しを有効化する前に迷わないよう、手順と安全チェックリストをまとめたドキュメントです。  
> このドキュメントはAPIキーを含みません。APIキーをリポジトリにコミットしてはいけません。

---

## ⚠️ 現在の状態: Phase 2.5 closeout 完了 / Phase 3 Go/No-Go 準備中

> **このランブックは Human Owner 主導の Phase 3 活性化のためのものです。Phase 3 はまだ開始していません。**

このドキュメントに記載された API Activation 手順（GEMINI_API_KEY 設定確認・`live_model_enabled=true` への変更・実 API 実行）は、**Phase 3 で Human Owner の明示的判断後、専用 activation PR を経由して実施します。**

- Phase 2.5 closeout は完了済み。
- Phase 3 は開始していない。
- 現在の作業は Phase 3 Go/No-Go 準備。
- GitHub Secret 設定は Human Owner が管理し、帯域外で検証する。
- Human Owner は GEMINI_API_KEY が設定済みであると報告しているが、リポジトリファイルはシークレット値を含まないし、含めてはならない。

### Phase 3 開始前の確認事項

**Phase 3 開始前に、API Activation Checklist の全項目を Human Owner が確認・承認する必要があります。**

詳細は **[`docs/API_ACTIVATION_CHECKLIST.md`](./API_ACTIVATION_CHECKLIST.md)** を参照してください。

| 確認事項 | 内容 |
|---|---|
| GEMINI_API_KEY 設定 | Human Owner が帯域外で検証。リポジトリファイルはシークレット値を含まない |
| `live_model_enabled=true` 変更 | 専用の Phase 3 activation PR でのみ実施する |
| Gemini API call | preflight 成功・Human Owner 最終確認・activation PR マージ後のみ |
| API activation PR | 専用 PR で実施する |
| GPT Audit Gate レビュー | API activation PR では必須 |
| Codex review | API activation PR では必須 |

### paid-credit preflight について

paid-credit preflight は、API 呼び出し前の安全確認として使用します。  
preflight 成功は API 呼び出しを承認しません。`live_model_enabled=true` への変更は専用 activation PR でのみ実施します。

preflight では以下を検証します:
- `GEMINI_API_KEY_PRESENT=true`
- `api_call_performed=false`
- `ledger_written=false`
- `patch_path=null`
- `live_model_enabled=false`
- `budget_available=true`

### 現在の制約

| 制約 | 内容 |
|---|---|
| **`live_model_enabled`** | `false` のまま維持する（trueにしない）。変更は専用 activation PR のみ |
| **実 Gemini API call** | Phase 3 Go/No-Go 準備中は実行しない |
| **paid-credit live 実行** | preflight 成功・Human Owner 最終確認・activation PR マージ後のみ |
| **quota / billing / free-tier** | Human Owner が帯域外で検証。リポジトリファクトとして主張しない |

Phase 2.5 closeout の詳細は **[`docs/PHASE_2_5_CLOSEOUT_AUDIT.md`](./PHASE_2_5_CLOSEOUT_AUDIT.md)** を参照してください。

Phase 3 への移行は Human Owner の明示的な判断が必要です。以下の手順はその際に参照してください。

---

## 現在の状態

- Phase 2.5 closeout 完了済み
- 通常CI成功済み
- noop workflow成功済み
- offline-sample workflow成功済み
- gemini-paid-credit-preflight 実装済み
- `live_model_enabled=false` を維持中
- 実Gemini API call は未実行
- Phase 3 は開始していない
- GitHub Secret 設定は Human Owner が帯域外で管理。リポジトリファイルはシークレット値を含まない

---

## APIキー登録前チェック

API キーを GitHub Secrets に登録する前に、以下をすべて確認してください。

- [ ] Google Cloud Billing linked project を確認（Human Owner が帯域外で検証）
- [ ] Gemini API key が billing-linked paid project のものか確認（Human Owner が帯域外で検証）
- [ ] quota / billing / budget caps / free-tier 制約を Human Owner が帯域外で検証（リポジトリファクトとして主張しない）
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

preflight が成功した後、以下を**人間オーナーが順序どおりに**確認・実施してください。

> ⚠️ **preflight 成功は API 呼び出しを承認しません。** paid-credit live 実行は以下の全条件が満たされた後にのみ実施します:
> - preflight 成功
> - Human Owner 最終確認
> - 専用 activation PR レビュー・マージ済み
> - workflow_dispatch 手動実行
> - `max_model_requests_per_run <= 1`
> - `promote_approved=false`（最初の live run 時。Human Owner が監査後に別途承認した場合を除く）

1. **GPT Audit Gate で preflight 成功を確認**
   - preflight の JSON 出力を Audit Gate に提示する
   - `api_call_performed=false` / `live_model_enabled=false` / `budget_available=true` を確認

2. **人間オーナーが Billing / Secret / Budget を最終確認**
   - Cloud Billing リンク済みプロジェクトへのアクセスを確認（帯域外で検証）
   - GitHub Secrets に `GEMINI_API_KEY` が正しく登録されていることを確認（帯域外で検証。シークレット値はリポジトリに記録しない）
   - 月次・日次予算が実際の利用計画と一致していることを確認（Human Owner が帯域外で検証）

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
   - `promote_approved=true` は Human Owner が監査結果を確認した後に別途承認する

> ⚠️ preflight が成功しても、自動的にAPIを呼び出すことはありません。ステップ3〜5は人間オーナーの明示的な判断と操作が必要です。

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
*最終更新: 2026-06-01*
