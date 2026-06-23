<!--
AI_DOC_META
status: HISTORICAL
scope: API activation readiness checklist, GEMINI_API_KEY terminology, Phase 3 Go/No-Go boundaries, and Phase 3 paid-credit current state as of PR #60–#62 (first controlled run pending at time of writing).
use_for:
  - checking API activation readiness
  - understanding raw GEMINI_API_KEY vs GEMINI_API_KEY_PRESENT
  - verifying secret-scoping terminology
  - confirming Phase 3 activation PR status and paid-credit current state
do_not_use_for:
  - performing API activation by itself
  - bypassing Project Owner approval
  - changing workflow execution logic without a dedicated activation PR
  - asserting GitHub Secrets state (Project Owner verifies out-of-band)
related:
  - docs/AI_ENTRYPOINT.md
  - docs/API_ACTIVATION_RUNBOOK.md
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
last_reviewed: 2026-06-03
AI_DOC_META_END
-->
# Cyber-Immunizer API Activation Checklist

> **[HISTORICAL — 2026-06-03 更新 / PR #60–#62 merge 直後の記録]** このヘッダーは controlled paid-credit run 実行前の状態の歴史的記録です。現在の状態は `docs/PROJECT_STATE.md` を参照してください（paid-credit success 14 件、generation 4 昇格済み、promote_approved=true）。

> **⚠️ 2026-06-03 更新: Phase 3 activation PR #58–#62 が main に merge 済み。**  
> **paid-credit path は準備完了。gemini-3-flash-preview での controlled run は未実行（次のステップ）。**  
> **過去の paid-credit API call 記録は存在する（gemini-3.1-flash-lite での成功記録あり）。promote_approved=true はまだ禁止。**  
> 詳細は下記「Phase 3 Paid-Credit 現在地」セクションを参照。

---

> **旧状態（Phase 2.5 closeout 時点）:** Phase 3 で実 Gemini API 接続を開始する前に、Project Owner が確認すべき条件を固定します。  
> **このチェックリストは Phase 3 活性化を承認しません。API 接続は行われていません。live_model_enabled は false のままです。GitHub Secrets は変更されません。**

---

## Purpose

- Phase 3 で実 Gemini API 接続を開始する前に、Project Owner が確認すべき条件を固定する
- このチェックリストは Phase 3 活性化を承認しない
- GitHub Secrets の状態はリポジトリファイルによって主張されない。Project Owner が帯域外で GEMINI_API_KEY 設定を検証する
- Project Owner は GEMINI_API_KEY が GitHub Secrets に設定済みであると報告しているが、シークレット値はリポジトリファイル・PR・Issue・ログ・チャットに記録してはならない
- Project Owner の明示的判断なしに Phase 3 以降の paid-credit run を追加実行・promote しない

> **Historical note (Phase 2.5 closeout 時点):** Phase 2.5 closeout 文書はマージ済み。Phase 3 は開始していない（当時）。現在の作業は Phase 3 Go/No-Go 準備。Gemini API はリポジトリ作業から呼ばれていない（当時）。live_model_enabled は false のまま維持する（当時の制約。現在は Phase 3 activation により true）。Gemini API call は行わない（当時）。

---

## Canonical GEMINI_API_KEY terminology

The following terms are used consistently throughout this repository to
describe secret scoping.  Use these definitions when reviewing or writing
workflow changes to verify that minimum-privilege is preserved.

| Term | Definition |
|---|---|
| `GEMINI_API_KEY` | The GitHub Secret name.  Also the environment variable name when the secret is injected into a step's `env:` block. |
| raw `GEMINI_API_KEY` | The actual secret value — `${{ secrets.GEMINI_API_KEY }}` — injected as `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}` at **step-level** env.  Must never appear at job-level or workflow-level env. |
| `GEMINI_API_KEY_PRESENT` | A non-secret boolean existence signal derived as `${{ secrets.GEMINI_API_KEY != '' && 'true' \|\| 'false' }}`.  The preflight step receives this signal instead of raw `GEMINI_API_KEY`. |
| step-level env | The `env:` block inside an individual workflow step (`- name: …`).  The **only** permitted scope for raw `GEMINI_API_KEY`. |
| job-level env | The `env:` block under a job definition, before `steps:`.  Raw `GEMINI_API_KEY` must **never** appear here. |
| workflow-level env | The top-level `env:` block of the workflow file.  Raw `GEMINI_API_KEY` must **never** appear here. |
| GitHub Secret configuration for GEMINI_API_KEY | Storing the key value in the repository's GitHub Secrets settings.  This is a Project Owner-managed action verified out-of-band.  Repository files do not assert GitHub Secrets registration state.  The secret value must never appear in repository files, PRs, issues, logs, or chat. |

**Preflight rule**: the `gemini-paid-credit-preflight` step does not receive raw
`GEMINI_API_KEY`.  It receives only `GEMINI_API_KEY_PRESENT` (boolean signal) to
confirm the key is configured in GitHub Secrets without exposing the actual value.

**Minimum-privilege rule**: raw `GEMINI_API_KEY` must only be injected at
step-level env, in mode-specific steps (`live-model`, `gemini-paid-credit`) that
are gated by a mode-matching `if:` condition.

---

## Current phase status

> **⚠️ Historical / Superseded:** このセクションは Phase 2.5 closeout 完了時点の状態を記録しています。Phase 3 activation PR #58–#62 は main に merge 済みです。現在の状態は「Phase 3 Paid-Credit 現在地」セクションを参照してください。

| Field | Value |
|---|---|
| Current phase | Phase 3 Go/No-Go preparation (Phase 2.5 closeout merged) — **Historical** |
| API connection | Not connected — **Historical** |
| GEMINI_API_KEY | GitHub Secrets state not asserted by repository files. Project Owner verifies configuration out-of-band. Project Owner reports GEMINI_API_KEY is configured; secret value must never appear in repository files, PRs, issues, logs, or chat. |
| GEMINI_API_KEY registration | Not performed by repository files; Project Owner-managed and verified out-of-band |
| live_model_enabled | false |
| Gemini API calls | Not executed |
| Phase 3 | Not started |
| Schedule mode | noop only |
| This checklist | Does not authorize Phase 3 activation. No API call. No live_model_enabled change. No GitHub Secrets change. |
| Quota / billing / free-tier | Project Owner verifies quota, billing, budget caps, and free-tier constraints out-of-band. Not asserted as repository fact. |

---

## Project Owner approval gate

Phase 3 へ進む前に、Project Owner が明示的に以下を宣言する必要があります。

- [ ] I approve starting Phase 3
- [ ] I understand Gemini API may incur cost
- [ ] I confirm billing budget caps are configured
- [ ] I confirm GEMINI_API_KEY will be stored only in GitHub Secrets
- [ ] I confirm live_model_enabled=true will be changed only in a dedicated Phase 3 PR
- [ ] I confirm GPT Audit Gate must review the activation PR before merge

Project Owner による上記の明示的宣言なしに、AI エージェント（Claude Code）は Phase 3 移行を自律的に実施しません。

---

## Required pre-activation checks

以下のすべての条件を満たした場合にのみ、Phase 3（実 Gemini API 接続）への移行を検討します。

### Repository safety

- [ ] No API key in repository files
- [ ] No raw secrets in README / docs / tests
- [ ] No GEMINI_API_KEY printed in logs
- [ ] No workflow passes raw GEMINI_API_KEY outside approved live-model/gemini-paid-credit propose steps
- [ ] CI workflow remains read-only
- [ ] No `contents: write` in normal CI
- [ ] No `promote_candidate.py` execution in CI
- [ ] No `live_model_enabled=true` in Phase 2

### Billing / budget

- [ ] Google Cloud billing account verified by Project Owner
- [ ] Monthly budget cap configured
- [ ] Daily budget cap configured
- [ ] Alerting configured
- [ ] Budget cap remains $10/month or lower unless Project Owner explicitly changes it
- [ ] Daily budget cap remains conservative, e.g. $0.25/day, unless Project Owner explicitly changes it

### Ledger / cost governance

- [ ] `data/api_usage_ledger.json` exists
- [x] ledger corruption fails closed — **enforced**: `strict_load_ledger()` raises ValueError for malformed JSON; live API/budget enforcement paths use `strict_load_ledger()` (PR-C #3 fix)
- [x] ledger missing fails closed — **enforced**: `strict_load_ledger()` raises ValueError for missing file ("budget state unknown"); live paid path and preflight use `strict_load_ledger()` (PR-C #3 fix)
- [ ] ledger write failure fails workflow
- [ ] ledger is append-only for API calls
- [ ] ledger is not reset, overwritten, or rolled back
- [ ] API call must persist ledger regardless of patch success/failure
- [ ] `ledger_changed=true` requires persist-ledger success

**ledger fail-closed semantics (enforced as of PR-C)**:

- `api_usage_ledger.json` が存在しない場合: **fail-closed** — "budget state unknown" エラーで API call を拒否
- `api_usage_ledger.json` が malformed JSON の場合: **fail-closed** — "budget state unknown" エラーで API call を拒否
- `api_usage_ledger.json` の top-level が list でない場合（dict / null / string / number 等）: **fail-closed**
- ledger が読み取り不能な場合: **fail-closed**
- missing ledger を [] として扱い、過去使用量ゼロ扱いにすることは禁止
- ledger reset / overwrite / rollback は禁止
- live API call 経路 (`_propose_via_gemini_paid_credit`) および preflight (`run_gemini_paid_credit_preflight`) では `strict_load_ledger()` を使用すること

### Runtime / workflow

- [ ] schedule must remain noop unless Project Owner explicitly changes it
- [ ] `workflow_dispatch` for paid-credit path must be explicit
- [ ] live-model / gemini-paid-credit path must be opt-in
- [ ] normal CI must never call Gemini
- [ ] API activation must happen in a dedicated PR
- [ ] Phase 3 activation PR must be audited by GPT Audit Gate
- [ ] Codex review should be run before merge
- [x] GEMINI_API_KEY is step-level scoped (minimum privilege) — **enforced**: noop / offline-sample steps receive no API key; gemini-paid-credit-preflight receives only `GEMINI_API_KEY_PRESENT` boolean signal; live-model / gemini-paid-credit steps receive raw `GEMINI_API_KEY` (PR-D fix)

### Privacy / data minimization

- [ ] `send_repository_full_text=false`
- [ ] `send_raw_payloads=false`
- [ ] `send_secrets=false`
- [ ] prompt context is minimal
- [ ] no secrets, billing data, or credentials are sent to Gemini
- [ ] no raw exploit payloads are sent

### Promotion / generated code safety

- [ ] generated code is not executed in write-permission jobs
- [ ] dry-run artifacts are non-promotable by default
- [x] promote requires Project Owner approval — **enforced**: `promote_approved` workflow_dispatch input (default: `"false"`) gates the promote job; Project Owner must explicitly select `"true"` (Critical #1 fix, pre-Phase-3 hardening PR)
- [x] `promote_approved` defaults to `"false"` — promote job skipped unless Project Owner explicitly approves (Critical #1 fix)
- [x] schedule runs cannot trigger promote job — `github.event_name == 'workflow_dispatch'` required in promote if condition (Critical #1 fix)
- [x] offline-sample success alone is not promote approval — `promote_approved=false` (default) blocks promote even if adoption gate passed (Critical #1 fix)
- [ ] promote requires GPT Audit Gate APPROVE (manual process gate — not automated workflow condition)
- [ ] CI smoke artifacts cannot be promoted
- [ ] offline-sample success is not promote approval
- [x] promote gate rejects bool-as-number in fitness fields — **enforced** (backlog #12, PR-E): `_validate_fitness_schema()` uses `type(v) is T` (not `isinstance`) so `score: true`, `tp_rate: true`, `fp_rate: false`, `fn_rate: true`, `exception_count: true/false` are rejected; NaN/±Infinity rejected; rate fields bounded [0.0, 1.0]; `exception_count` requires strict non-negative `int` (not `float`, not `bool`); genuine boolean fields (`passed_adoption_gate`, etc.) unaffected

---

## Phase 3 activation procedure preview

> ⚠️ **Phase 3 は開始していません。以下の手順はまだ実行されていません。**  
> これは Phase 3 での手順案の事前記録です。実際の実行は Phase 3 で Project Owner の明示的判断後に行います。  
> **このチェックリストはこれらの手順を承認しません。No API call is performed by this checklist. No live_model_enabled change is performed by this checklist. No GitHub Secrets are modified by this checklist.**

Preview steps (Phase 2-E does not execute these):

1. Project Owner explicitly decides to start Phase 3
2. Create a dedicated Phase 3 activation PR
3. Confirm billing and budget caps
4. Perform GitHub Secret configuration for GEMINI_API_KEY (add the key value to GitHub Secrets manually)
5. Keep key out of repository files
6. Run paid-credit preflight
7. Confirm preflight behavior
8. Change `live_model_enabled=true` only in the dedicated activation PR
9. Run limited workflow_dispatch test
10. Verify ledger persisted
11. Verify cost stayed within budget
12. GPT Audit Gate reviews results
13. Project Owner decides whether to merge

---

## Fail-closed conditions

以下の状態が確認された場合、Phase 3 への移行を進めることはできません。

- GEMINI_API_KEY appears in repository files
- `live_model_enabled=true` appears before dedicated Phase 3 PR
- budget cap is missing
- daily budget cap is missing
- ledger is missing, corrupted, or reset
- normal CI attempts to call the Gemini API
- schedule is able to call the Gemini API
- workflow grants `contents: write` to normal CI
- generated code is able to run in write-permission job
- Project Owner approval is missing
- GPT Audit Gate approval is missing
- Codex review has unresolved valid findings
- API call succeeds but ledger persistence fails
- `ledger_changed=true` but persist-ledger is not success

---

## Non-goals

Phase 3 Go/No-Go 準備中は以下を実施しません。これらは Phase 3 で Project Owner の明示的判断のもと専用 PR を経由して実施します。

- GitHub Secret configuration for GEMINI_API_KEY
- live_model_enabled=true
- Gemini API call
- workflow 変更
- schedule API execution
- paid-credit live execution
- `promote_candidate.py` 変更
- `propose_mutation.py` 変更
- `apply_mutation.py` 変更
- `evaluate_candidate.py` 変更
- `data/genome.json` 変更
- `data/api_usage_ledger.json` 変更
- `data/evolution_history.json` 変更
- GitHub Secrets 操作
- Google Cloud Billing 設定変更
- Phase 3 開始

---

## Phase 3 Paid-Credit 現在地（PR #60–#62 反映）

> **[HISTORICAL — PR #60–#62 merge 直後の記録]** このセクションは gemini-3-flash-preview の初回 paid-credit run 実行前の状態を記録した歴史的証拠です。現在の paid-credit 件数・promote 状態は `docs/PROJECT_STATE.md` / `data/project_state.json` を参照してください（success 14 件、generation 4 昇格済み、promote_approved=true）。

> **このセクションは Phase 3 activation PR merge 後の正確な現在地を記録する。**  
> 過去の paid-credit API call 記録は存在する（`data/api_usage_ledger.json` 参照）。gemini-3-flash-preview での controlled paid-credit run は未実行。paid-credit path の準備は完了。

### Phase 3 Activation PR サマリー

| PR | 内容 |
|---|---|
| **PR #58** | `live_model_enabled=true` を main に merge。`--live-model` path を Phase 3 でブロック。`gemini-paid-credit` のみ許可 |
| **PR #59** | Gemini ClientError の安全な診断情報を許可リストベースで記録。payload redaction 強化 |
| **PR #60** | 停止 Gemini 2.0 Flash 系から移行。`model_name = gemini-3.1-flash-lite`、`fallback = gemini-2.5-flash-lite` に更新 |
| **PR #61** | `replacement_code` の Python 構文検証を Propose 段階に追加（`ast.parse()` のみ、実行なし） |
| **PR #62** | Primary model を `gemini-3-flash-preview` に変更。`ThinkingConfig(thinking_level="low")`、actual thinking tokens の ledger 反映 |

### 現在の Phase 3 状態

| 項目 | 状態 |
|---|---|
| Phase 3 activation PR | ✅ PR #58–#62 merge 済み |
| `live_model_enabled` | `true` |
| Primary model | `gemini-3-flash-preview` |
| Fallback model | `gemini-3.1-flash-lite` |
| 過去の paid-credit API call 記録 | 存在する（gemini-3.1-flash-lite 成功 × 1 など — `data/api_usage_ledger.json` 参照） |
| Gemini 3 Flash Preview controlled run | **未実行** — gemini-3-flash-preview 構成での初回確認 run が次ステップ |
| `promote_approved` | `false` — 最初の run 結果確認前は禁止 |
| Apply / Evaluate / Promote 自動昇格 | **禁止** — run 結果確認後に判断 |

### 次の Project Owner 手順

1. PR #62 が main に merge 済みであることを確認（`data/genome.json` が `gemini-3-flash-preview`）
2. この docs PR を merge する
3. `workflow_dispatch` → mode: `gemini-paid-credit`、`promote_approved=false` で 1 回だけ実行
4. ledger artifact / candidate patch / apply / evaluate 結果を確認
5. 結果に基づいて次 PR を判断（promote / fix / halt）

### 禁止事項（Phase 3 paid-credit 実行前）

- `promote_approved=true` にしない（最初の run 結果確認前）
- paid-credit run を連続実行しない
- workflow / scripts / data / ledger を docs PR で変更しない
- GEMINI_API_KEY をドキュメントに書かない
- `Phase 3 成功済み` と書かない（「準備完了」と「実行成功」を混同しない）

---

## 関連ドキュメント

- [`docs/API_ACTIVATION_RUNBOOK.md`](./API_ACTIVATION_RUNBOOK.md) — API 有効化手順書（Gemini 3 runbook 含む）
- [`docs/PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) — Phase 2 計画文書
- [`docs/AUDIT_CHARTER.md`](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章
- [`data/genome.json`](../data/genome.json) — ゲノム設定（`live_model_enabled=true`、`model_name=gemini-3-flash-preview`）
- [`data/api_usage_ledger.json`](../data/api_usage_ledger.json) — API 使用量台帳

---

*このドキュメントは Project Cyber-Immunizer の Phase 2-E で作成されました。*  
*Phase 2.5 closeout 完了 / Phase 3 Go/No-Go 準備中に current-state alignment を実施（docs-only）。*  
*Phase 3 activation PR #60–#62 反映のため 2026-06-03 に更新。*  
*作成日: 2026-05-26 / 最終更新: 2026-06-03*
