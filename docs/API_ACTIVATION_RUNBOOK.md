# Cyber-Immunizer API Activation Runbook

> **目的**: GEMINI_API_KEY を登録し、実際の Gemini API 呼び出しを有効化する前に迷わないよう、手順と安全チェックリストをまとめたドキュメントです。  
> このドキュメントはAPIキーを含みません。APIキーをリポジトリにコミットしてはいけません。

---

## 現在の状態

- 通常CI成功済み
- noop workflow成功済み
- offline-sample workflow成功済み
- gemini-paid-credit-preflight 実装済み
- GEMINI_API_KEY 未登録の場合、preflight は fail-closed する
- `live_model_enabled=false` を維持中
- 実Gemini API call は未実行

---

## APIキー登録前チェック

API キーを GitHub Secrets に登録する前に、以下をすべて確認してください。

- [ ] Google AI Pro / Google Developer Program の $10 GenAI & Cloud credit を確認
- [ ] Google Cloud Billing linked project を確認
- [ ] Gemini API key が billing-linked paid project のものか確認
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

1. **GPT Audit Gate で preflight 成功を確認**
   - preflight の JSON 出力を Audit Gate に提示する
   - `api_call_performed=false` / `live_model_enabled=false` を確認

2. **人間オーナーが Billing / Secret / Budget を最終確認**
   - Cloud Billing リンク済みプロジェクトへのアクセスを確認
   - GitHub Secrets に `GEMINI_API_KEY` が正しく登録されていることを確認
   - 月次・日次予算が実際の利用計画と一致していることを確認

3. **別PRで `data/genome.json` の `live_model_enabled` を `true` に変更**
   - 直接 main へコミットしない
   - レビュー済みPRを経由する
   - このPR自体が GPT Audit Gate のレビュー対象になる

4. **通常CIを確認**
   - PRが CI を通過していることを確認してからマージする

5. **workflow_dispatch で `mode=gemini-paid-credit` を1回だけ手動実行**
   - スケジュール実行（cron）では絶対に実行しない
   - `max_model_requests_per_run <= 1` を守る

6. **API usage ledger に記録されたことを確認**
   - `data/api_usage_ledger.json` に新しいエントリが追記されていることを確認

7. **evaluate / promote の結果を GPT Audit Gate で監査**
   - 候補が採用ゲートを通過した場合、昇格前に Audit Gate レビューを実施する

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

- [AUDIT_CHARTER.md](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章
- [`data/genome.json`](../data/genome.json) — ゲノム設定（`live_model_enabled` はここで管理）
- [`data/api_usage_ledger.json`](../data/api_usage_ledger.json) — API 使用量台帳

---

*このドキュメントは Project Cyber-Immunizer の API 有効化手順書です。*  
*APIキーは含まれておらず、含めてはいけません。*  
*最終更新: 2026-05-26*
