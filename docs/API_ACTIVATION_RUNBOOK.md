<!--
AI_DOC_META
status: HISTORICAL
scope: Phase 3 API activation procedure, Gemini 3 Flash Preview operational runbook, and paid-credit current state as of PR #60-#62 (first controlled run pending at time of writing).
use_for:
  - reviewing the historical Phase 3 activation procedure (PR #60–#62 era, first run pending)
  - audit evidence for the safety boundaries applied during initial Phase 3 activation
  - understanding Gemini 3 Flash Preview configuration as documented before first paid-credit run
do_not_use_for:
  - determining current paid-credit run count (use docs/PROJECT_STATE.md or data/project_state.json — success records: 14, generation 4 active)
  - determining current promote_approved status (use data/project_state.json — promote_approved=true as of run #59)
  - planning next paid-credit experiments (Project Owner decision required per next_action field)
  - asserting GitHub Secrets state (Project Owner verifies out-of-band)
  - calling Gemini API directly from this document
related:
  - docs/API_ACTIVATION_CHECKLIST.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
last_reviewed: 2026-06-05
pr_66_fallthrough_guard: check 9 added — last top-level node must be ast.Return
pr_67_dr_arg_shape: check 10 added — DetectionResult keyword-only, exactly blocked/reason/confidence/matched_signals
pr_69_x007_spec_freeze: X-007 static value-check policy frozen in docs — check 11 NOT implemented in PR #69; see docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md
AI_DOC_META_END
-->
# Cyber-Immunizer API Activation Runbook

> **目的**: GEMINI_API_KEY を登録し、実際の Gemini API 呼び出しを有効化する前に迷わないよう、手順と安全チェックリストをまとめたドキュメントです。  
> このドキュメントはAPIキーを含みません。APIキーをリポジトリにコミットしてはいけません。

---

## ⚠️ 現在の状態: Phase 3 activation 完了 / 初回 paid-credit run 待機中

> **[HISTORICAL — PR #60–#62 merge 直後の記録]** このセクションは gemini-3-flash-preview の初回 paid-credit run 実行前の状態を記録した歴史的証拠です。現在の状態は `docs/PROJECT_STATE.md` / `data/project_state.json` を参照してください（paid-credit success 14 件、generation 4 昇格済み、promote_approved=true）。

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
- 以下のラッパーに splice して `ast.parse()` を実行（コードは**絶対に実行しない**）:
  ```
  def _candidate_body(request):
      _mutation_anchor = None
      # === MUTATION_START ===
  {replacement_code（as-is、インデント維持）}
  # === MUTATION_END ===
  ```
  - 先頭行: `def _candidate_body(request):` — `request` パラメータあり
  - `_mutation_anchor = None` — AST 意味検証用のアンカー文（body[0]）; `body[1:]` が replacement region
  - `MUTATION_START` は 4 スペースインデント、`MUTATION_END` はカラム 0（`core/detector.py` に合わせる）
- `SyntaxError` / `IndentationError` → patch 返却拒否（`mutation_patch.json` に書き込まない）
- `UnicodeError` → fail-closed（エラー文字列は `replacement_code` 本文をエコーしない）
- 対象: 不正 Python 構文、無インデント、lone surrogate / Unicode 系 parser failure

#### replacement_code インデント契約（PR #65）

| 項目 | 内容 |
|---|---|
| **契約** | `replacement_code` は `inspect_request()` 関数内部に **そのまま挿入** される 4 スペースインデント済み function body fragment |
| **必須** | トップレベル実行行・コメント行は **正確に 4 スペース**でインデントする。トップレベルの `return DetectionResult(...)` は 4 スペース。**ただし** if/for/while ブロック内の nested `return DetectionResult(...)` は **8 スペース**（さらにネストは 12, 16, …）で正しい — これは valid な Python であり拒否されない。ネストブロック（if/for/while 内）は **8 スペース**（さらにネストは 12, 16, …）。**すべてのインデントは 4 の倍数**でなければならない（1, 2, 3, 5, 6 スペース等は拒否）。**leading tab は禁止**（スペースのみ） |
| **禁止** | `def` / `async def` 文を含めない（任意のインデントレベルで禁止）/ mutation marker を含めない / Markdown code fence (` ``` `) を含めない / 列 0 のコードを含めない / 4 の倍数でないインデントを使わない |
| **検証失敗分類** | tab あり → `tab indentation is forbidden` / min indent < 4 → `indentation contract violation` / min indent > 4 → `top-level statements must start with exactly 4 spaces` / 4の倍数違反 → `all indentation must be a multiple of 4 spaces` / function definition → function definition エラー / code fence → markdown code fence エラー / 空・コメントのみ → `replacement_code body is empty` / return 文なし → `must contain at least one return statement` |
| **意味検証** | AST parse 成功後、replacement body が空・コメントのみ・pass のみ・return 文なしの場合も拒否される（Propose 段階で fail-closed）。空や comments-only の Gemini 応答も `mutation_patch.json` には書き込まれない。さらに、すべての return 文は `return DetectionResult(...)` の形式でなければならない（`return None` / `return result` / `return True` 等は拒否） |

#### fallthrough/default return guard（PR #66）

**PR #66 で追加された check 9**: `replacement_code` の最後のトップレベル文は `return DetectionResult(...)` でなければならない。

| 項目 | 内容 |
|---|---|
| **問題** | `return` 文が存在しても、すべての `return` が if/for/while ブロック内の nested return だけの場合、いずれの分岐も取られなければ関数は暗黙の `None` を返す（Python の fallthrough 動作）。check 7 の「少なくとも 1 つの return が存在すること」チェックはこの問題を検出できない |
| **check 9 の要件** | `replacement_nodes` の最後のトップレベルノード（`_mutation_anchor` 後の function body 直下の最終 AST ノード）が `ast.Return` でなければならない。check 8 がすべての `return` の形式を `DetectionResult(...)` に検証済みなので、check 9 はノード型が `ast.Return` かを確認するだけでよい |
| **拒否されるパターン** | ① nested return のみで最後のトップレベル文が if/for/while ブロック ② nested return の後に代入・式文が続いて最後が return でない |
| **受理されるパターン** | nested return + 最後に 4 スペースインデントのトップレベル `return DetectionResult(...)` fallback |
| **エラーメッセージ** | `replacement_code fallthrough guard violation: the last top-level statement must be a direct return DetectionResult(...) fallback; nested-only return paths can fall through to implicit None` |
| **Protocol lesson** | return 文の存在確認（check 7）は fallthrough 安全性を保証しない。「safe fallback return path exists」の保証には別途トップレベル fallback return チェック（check 9）が必要 |

#### _validate_replacement_code チェック順（PR #65 / PR #66 / PR #67）

| # | チェック | 失敗時エラーキーワード |
|---|---|---|
| 1 | mutation marker 禁止 | `mutation marker` |
| 2 | markdown code fence 禁止 | `markdown code fence` |
| 3 | function definition 禁止 | `function definition` |
| 4 | forbidden token 禁止 (import/eval/exec/os. 等) | `forbidden token` |
| 5 | indentation contract (tab/min-4/multiple-of-4) | `indentation contract violation` |
| 6 | Python syntax (ast.parse のみ、実行しない) | `not valid Python syntax` |
| 7 | semantic body (空・pass のみ・return なし を拒否) | `body is empty` / `pass-only` / `must contain at least one return` |
| 8 | return shape (全 return が `DetectionResult(...)` 形式) | `return contract violation` |
| 9 | fallthrough guard (最後のトップレベルノードが `ast.Return`) | `fallthrough guard violation` |
| 10 | DetectionResult 引数形式 (keyword-only、正確に 4 フィールド) | `argument shape violation` |

#### DetectionResult 引数形式チェック（PR #67）

**PR #67 で追加された check 10**: `DetectionResult(...)` のすべての呼び出しは keyword-only 引数で、正確に 4 フィールド `blocked`, `reason`, `confidence`, `matched_signals` を指定しなければならない。

| 項目 | 内容 |
|---|---|
| **問題** | check 8 は `return DetectionResult(...)` の形式を検証するが、コンストラクタの引数形式は検証しない。`DetectionResult(True, "x", 0.5, ())` のような positional 引数や、`DetectionResult(blocked=True, reason="x")` のような不完全な keyword 引数が通過してしまう |
| **check 10 の要件** | `replacement_nodes` 配下の **すべての bare `DetectionResult(...)` `ast.Call`** について（returned / 式文 / 代入 / nested branch 問わず）: ① positional 引数なし（`call.args` が空）② `**kwargs` 展開なし（`keyword.arg is None` の keyword なし）③ keyword 名の重複なし（`ast.parse` は重複を通すが Python 実行時は `TypeError` になるため）④ keyword 名が正確に `{blocked, reason, confidence, matched_signals}` の 4 つ。非 return 呼び出しも検証する（Codex P2 対応） |
| **拒否されるパターン** | positional 引数 / **kwargs 展開 / duplicate keyword 名 / keyword 名不足 / keyword 名過剰 / keyword 名誤り / mixed positional+keyword（return 文内外問わず） |
| **受理されるパターン** | `DetectionResult(blocked=..., reason=..., confidence=..., matched_signals=...)` のみ（呼び出し場所問わず） |
| **エラーメッセージ prefix** | `replacement_code DetectionResult argument shape violation:` |
| **適用範囲** | nested return（if/for/while 内）とトップレベル fallback return の両方に適用される |
| **型・値レンジの検証** | check 11（X-007）が Category A obvious invalid literal を静的に拒否する。動的式は defer（Category B）。 |

#### X-007 型・値レンジ静的チェック（PR #69 frozen / PR #73 実装済み）

> **✅ check 11 は実装済み（PR #73）。現在の validator は check 1–11 を実装する。**

X-007 は `DetectionResult(...)` の各フィールドの型・値レンジを静的に検証するポリシー拡張項目です。
PR #69 でポリシーを凍結（docs-only）し、PR #73で Category A safe-subset を実装しました。

| 状態 | 内容 |
|---|---|
| **現在の実装** | check 1–11（check 11 = X-007 Category A 実装済み） |
| **PR #69** | X-007 ポリシー凍結（docs-only）— validator 変更なし |
| **PR #73** | X-007 安全サブセット実装（check 11 実装済み） |

凍結されたポリシーの詳細は **[`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md`](REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md)** を参照してください。

このドキュメントが定義する4つのカテゴリ:
- **Category A**: check 11 が静的に拒否する obvious invalid literal のケース（実装済み）
- **Category B**: check 11 が必ず許可またはデファーする動的式（実装済み）
- **Category C**: 静的検証は AST のみ（eval/compile/実行禁止）— 実装済み
- **Category D**: fitness/evaluate はランタイム責任を**部分的にのみ**担う — `_contract_ok` は DetectionResult インスタンスと `confidence` 範囲のみ検証する。`blocked`/`reason`/`matched_signals` の型誤りは runtime で検出されない（詳細は spec の Category D を参照）

**オペレーターへの注意**: X-007 静的チェック（Category A）が拒否できるのは obvious invalid literal のみです。`confidence=min(1.0, score)` や `matched_signals=tuple(matched)` のような動的式は check 11 でも拒否されません（Category B）。

#### paid-credit run で replacement_code 検証が失敗した場合

> **すぐに paid-credit を再実行しない。**

1. Propose ジョブのログを確認し、`validation error` の分類を特定する。
2. `data/api_usage_ledger.json` を確認する — **API call と ledger 保存は成功している場合がある**（mutation patch 生成が失敗しても）。
3. 同種エラー（`indentation contract violation` 等）が再発し得る場合は、prompt/validation 契約を修正してから再実行する。
4. 修正 PR をレビュー・マージしてから次の paid-credit run を実施する。

```
Gemini 応答は構文検証で失敗する場合がある。
replacement_code は inspect_request() 関数内部にそのまま挿入される
4 スペースインデント済み function body でなければならない。
replacement_code の構文・インデント検証で失敗した場合、すぐに paid-credit を再実行しない。
まず Propose ログ、ledger 記録、validation error を確認する。
同種エラーが再発し得る場合は、再実行前に prompt/validation 契約を修正する。
mutation patch 生成が失敗しても、API call と ledger 保存は成功している場合がある。
```

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
*最終更新: 2026-06-01*
