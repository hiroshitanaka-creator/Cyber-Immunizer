# Cyber-Immunizer API Activation Checklist

> **このドキュメントは Phase 2-E で作成されました。**  
> Phase 3 で実 Gemini API 接続を開始する前に、Human Owner が確認すべき条件を固定します。  
> **Phase 2-E では API 接続を行いません。**

---

## Purpose

- Phase 3 で実 Gemini API 接続を開始する前に、Human Owner が確認すべき条件を固定する
- Phase 2-E では API 接続を行わない
- Phase 2-E では GEMINI_API_KEY を repository files に保存しない
- Phase 2-E では GEMINI_API_KEY を Phase 2 workflows で使用しない
- Phase 2-E では live_model_enabled=true にしない
- Phase 2-E では Gemini API call を行わない
- Human Owner の明示的判断なしに Phase 3 へ進まない
- このPRは GitHub Secrets の状態を検証しない（GitHub Secrets 状態は Human Owner が外部で確認する）
- Before Phase 3, Human Owner must confirm GEMINI_API_KEY is stored only in GitHub Secrets

---

## Current phase status

| Field | Value |
|---|---|
| Current phase | Phase 2-E — API activation checklist hardening |
| API connection | Not connected |
| GEMINI_API_KEY in repository files | Not present |
| GEMINI_API_KEY used by Phase 2 workflows | No |
| GitHub Secrets state | Not asserted by repository files; Human Owner controlled |
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
- [ ] ledger corruption fails closed
- [ ] ledger missing fails closed
- [ ] ledger write failure fails workflow
- [ ] ledger is append-only for API calls
- [ ] ledger is not reset, overwritten, or rolled back
- [ ] API call must persist ledger regardless of patch success/failure
- [ ] `ledger_changed=true` requires persist-ledger success

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
- [ ] promote requires Human Owner approval
- [ ] promote requires GPT Audit Gate APPROVE
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

## Verification limitations

以下の事項は、このPR / repository files からは検証できません。Human Owner が外部で確認する必要があります。

- PR diff can verify repository files, not GitHub Secrets contents
- GitHub Secrets state cannot be verified from repository files
- Google Cloud Billing settings cannot be verified from repository files
- Human Owner must verify GitHub Secrets and Billing before Phase 3
- GPT Audit Gate and Codex review reduce but do not eliminate review blind spots
- This PR does not inspect, modify, or rely on GitHub Secrets
- GitHub Secrets state is controlled and verified by the Human Owner outside repository files

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
