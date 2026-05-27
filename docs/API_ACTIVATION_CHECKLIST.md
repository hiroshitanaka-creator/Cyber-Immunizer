# Cyber-Immunizer API Activation Checklist

> **このドキュメントは Phase 2-E で作成されました。**  
> Phase 3 で実 Gemini API 接続を開始する前に、Human Owner が確認すべき条件を固定します。  
> **Phase 2-E では API 接続を行いません。**

---

## Purpose

- Phase 3 で実 Gemini API 接続を開始する前に、Human Owner が確認すべき条件を固定する
- Phase 2-E では API 接続を行わない
- Phase 2-E では GEMINI_API_KEY 登録を行わない
- Phase 2-E では live_model_enabled=true にしない
- Phase 2-E では Gemini API call を行わない
- Human Owner の明示的判断なしに Phase 3 へ進まない

---

## Current phase status

| Field | Value |
|---|---|
| Current phase | Phase 2-E — API activation checklist hardening |
| API connection | Not connected |
| GEMINI_API_KEY | Not registered in repository |
| live_model_enabled | false |
| Gemini API calls | Not executed |
| Phase 3 | Not started |
| Schedule mode | noop only |

---

## Human Owner approval gate

Phase 3 へ進む前に、Human Owner が明示的に以下を宣言する必要があります。

- [ ] I approve starting Phase 3
- [ ] I understand Gemini API may incur cost
- [ ] I confirm billing budget caps are configured
- [ ] I confirm GEMINI_API_KEY will be stored only in GitHub Secrets
- [ ] I confirm live_model_enabled=true will be changed only in a dedicated Phase 3 PR
- [ ] I confirm GPT Audit Gate must review the activation PR before merge

Human Owner による上記の明示的宣言なしに、AI エージェント（Claude Code）は Phase 3 移行を自律的に実施しません。

---

## Required pre-activation checks

以下のすべての条件を満たした場合にのみ、Phase 3（実 Gemini API 接続）への移行を検討します。

### Repository safety

- [ ] No API key in repository files
- [ ] No raw secrets in README / docs / tests
- [ ] No GEMINI_API_KEY printed in logs
- [ ] No workflow passes GEMINI_API_KEY outside approved propose/preflight context
- [ ] CI workflow remains read-only
- [ ] No `contents: write` in normal CI
- [ ] No `promote_candidate.py` execution in CI
- [ ] No `live_model_enabled=true` in Phase 2

### Billing / budget

- [ ] Google Cloud billing account verified by Human Owner
- [ ] Monthly budget cap configured
- [ ] Daily budget cap configured
- [ ] Alerting configured
- [ ] Budget cap remains $10/month or lower unless Human Owner explicitly changes it
- [ ] Daily budget cap remains conservative, e.g. $0.25/day, unless Human Owner explicitly changes it

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

- [ ] schedule must remain noop unless Human Owner explicitly changes it
- [ ] `workflow_dispatch` for paid-credit path must be explicit
- [ ] live-model / gemini-paid-credit path must be opt-in
- [ ] normal CI must never call Gemini
- [ ] API activation must happen in a dedicated PR
- [ ] Phase 3 activation PR must be audited by GPT Audit Gate
- [ ] Codex review should be run before merge

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
- [x] promote requires Human Owner approval — **enforced**: `promote_approved` workflow_dispatch input (default: `"false"`) gates the promote job; Human Owner must explicitly select `"true"` (Critical #1 fix, pre-Phase-3 hardening PR)
- [x] `promote_approved` defaults to `"false"` — promote job skipped unless Human Owner explicitly approves (Critical #1 fix)
- [x] schedule runs cannot trigger promote job — `github.event_name == 'workflow_dispatch'` required in promote if condition (Critical #1 fix)
- [x] offline-sample success alone is not promote approval — `promote_approved=false` (default) blocks promote even if adoption gate passed (Critical #1 fix)
- [ ] promote requires GPT Audit Gate APPROVE (manual process gate — not automated workflow condition)
- [ ] CI smoke artifacts cannot be promoted
- [ ] offline-sample success is not promote approval

---

## Phase 3 activation procedure preview

> ⚠️ **Phase 2-E では以下の手順を実行しません。**  
> これは Phase 3 での手順案の事前記録です。実際の実行は Phase 3 で Human Owner の明示的判断後に行います。

Preview steps (Phase 2-E does not execute these):

1. Human Owner explicitly decides to start Phase 3
2. Create a dedicated Phase 3 activation PR
3. Confirm billing and budget caps
4. Add GEMINI_API_KEY to GitHub Secrets manually
5. Keep key out of repository files
6. Run paid-credit preflight
7. Confirm preflight behavior
8. Change `live_model_enabled=true` only in the dedicated activation PR
9. Run limited workflow_dispatch test
10. Verify ledger persisted
11. Verify cost stayed within budget
12. GPT Audit Gate reviews results
13. Human Owner decides whether to merge

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
- Human Owner approval is missing
- GPT Audit Gate approval is missing
- Codex review has unresolved valid findings
- API call succeeds but ledger persistence fails
- `ledger_changed=true` but persist-ledger is not success

---

## Non-goals

Phase 2-E では以下を実施しません。これらは Phase 3 以降で Human Owner の判断のもと実施します。

- GEMINI_API_KEY registration
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

## 関連ドキュメント

- [`docs/API_ACTIVATION_RUNBOOK.md`](./API_ACTIVATION_RUNBOOK.md) — API 有効化手順書（Phase 3 で実施）
- [`docs/PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) — Phase 2 計画文書
- [`docs/AUDIT_CHARTER.md`](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章
- [`data/genome.json`](../data/genome.json) — ゲノム設定（`live_model_enabled=false` を維持）
- [`data/api_usage_ledger.json`](../data/api_usage_ledger.json) — API 使用量台帳

---

*このドキュメントは Project Cyber-Immunizer の Phase 2-E で作成されました。*  
*Phase 2-E: API activation checklist hardening（docs/tests only）*  
*作成日: 2026-05-26*
