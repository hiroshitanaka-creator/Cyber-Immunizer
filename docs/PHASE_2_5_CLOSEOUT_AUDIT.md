# Phase 2.5 Closeout Audit

> This document is not Phase 3 activation.
> Phase 3 is not started.
> API is not connected.
> `live_model_enabled` must remain false until a dedicated Phase 3 activation PR is approved by the Human Owner.

## 1. Purpose

This document records the completion state of Phase 2.5 hardening for Project Cyber-Immunizer and prepares the repository for a later Human Owner Go/No-Go decision about Phase 3.

This document does not:

- enable Gemini API
- set `live_model_enabled=true`
- add or expose GitHub Secrets
- execute a real Gemini API call
- approve Phase 3 activation

## 2. Closeout basis

| Item | Status |
|---|---|
| Phase 2 | Complete |
| Phase 2.5 hardening | Complete through PR #53 |
| Phase 3 | Not started |
| Gemini API connection | Not connected |
| `live_model_enabled` | false |
| Real Gemini API calls | Not executed by repository work |
| GitHub Secrets | Human Owner controlled, not asserted by repository files |
| Human Owner Phase 3 GO | Not given in this document |

## 3. Phase 2.5 hardening PR ledger

| PR | Area | Closeout status |
|---|---|---|
| #46 | Conservative multilingual/code token estimation and paid-credit output cap accounting | Complete |
| #47 | Candidate evaluation subprocess physical resource limits | Complete |
| #48 | `persist-ledger` rebase retry, main-only paid-credit guard, safe main checkout | Complete |
| #49 | AST structural guard and whitelist roadmap | Complete |
| #50 | `apply_mutation.py` atomic candidate writes | Complete |
| #51 | Detector large-payload regression tests | Complete |
| #52 | Threat indicator case-normalization contract tests | Complete |
| #53 | Paid-credit API-success / ledger-write-failure behavior tests | Complete |

## 4. External audit inputs

### 4.1 Grok external red-team audit

Grok's full-scope audit returned `READY_WITH_WARNINGS`.

GPT Audit Gate classification:

| Item | GPT classification | Closeout impact | Phase 3 impact |
|---|---|---|---|
| Indirect dunder residual risk | Known residual / future allowlist backlog | Does not block closeout | Track for later Stage C/D hardening |
| Documentation drift concern | Not accepted as a blocker; insufficient concrete contradiction after Claude audit | Does not block closeout | Continue normal doc review |
| Ledger write failure behavioral coverage | Accepted as useful hardening | Addressed by PR #53 | Strengthens Phase 3 readiness |

### 4.2 Claude Code full-scope read-only audit

Claude Code's full-scope read-only audit returned `READY_FOR_GPT_CLOSEOUT_AUDIT`.

Key outcomes:

- full test suite passed in the audited checkout
- `live_model_enabled=false` remained in repository data
- scheduled workflow behavior remained `noop`
- paid-credit mode outside main was refused
- `persist-ledger` was main-only with rebase retry and fail-closed finalize behavior
- candidate evaluation had timeout, stripped environment, and POSIX resource limits
- mutation output used temp write, validation, and atomic replace
- AST policy rejected disallowed constructs including `Assert` and `AsyncFor`
- detector corpus used neutralized indicators and case-normalization tests

Non-blocking notes from Claude:

| Item | GPT classification | Action |
|---|---|---|
| `docs/AI_workflow` has no `.md` extension | Reject / ignore for readiness | No action required |
| `apply_mutation.py` notes parent directory symlink residual for custom output roots | Post-Phase3 backlog | Revisit only if untrusted custom `output_root` is introduced |

## 5. Repository-verifiable hardening summary

| Boundary | Status | Evidence category |
|---|---|---|
| Token and cost estimation | Conservative 2.0x char-to-token fallback; chars/4 forbidden | PR #46, tests |
| Output token cap accounting | `max_output_tokens` treated as token cap, not char estimate | PR #46, tests |
| Ledger write after API call | Patch not returned if usage cannot be recorded | PR #53, tests |
| Candidate evaluation | subprocess, timeout, safe env, POSIX rlimits | PR #47, tests |
| Workflow paid-credit boundary | non-main paid-credit refused before API call | PR #48, workflow/tests |
| Ledger persistence | main-only, checkout `ref: main`, bounded rebase retry | PR #48, workflow/tests |
| Mutation output | same-directory temp write, validate before atomic replace | PR #50, tests |
| AST structural policy | high-risk unnecessary constructs rejected | PR #49, tests |
| Detector payload regressions | large benign payload and tail indicator covered | PR #51, tests |
| Detector case normalization | uppercase/mixed-case indicators covered | PR #52, tests |

## 6. Known residual risks and classification

| Residual item | Classification | Blocks closeout? | Blocks Phase 3 activation? | Handling |
|---|---|---|---|---|
| Indirect dunder access is not mathematically proven impossible | Known residual / POST_PHASE3_BACKLOG | No | No | Already documented in `docs/AST_POLICY_WHITELIST_ROADMAP.md`; revisit during later allowlist stages |
| Custom untrusted `output_root` parent symlink chain | POST_PHASE3_BACKLOG | No | No | Current default root is repo-controlled; revisit if external output roots are introduced |
| Exact real Gemini token/billing behavior | Human Owner external / runtime verification | No | Requires Go/No-Go review before activation | Verify in Phase 3 Go/No-Go and first controlled activation |
| GitHub Secrets existence and validity | Human Owner external verification | No | Yes, before activation | Must be verified out-of-band by Human Owner |

## 7. No-Go boundaries preserved

The following remain No-Go conditions for Phase 3 activation:

- Human Owner has not explicitly approved a Phase 3 activation PR
- GitHub Secrets state has not been verified out-of-band
- billing / budget alert state has not been verified out-of-band
- `live_model_enabled=true` appears outside a dedicated activation PR
- API activation is mixed with unrelated changes
- generated candidate code executes in a write-permission job
- budget / ledger fail-closed behavior is weakened
- CI is not green on the activation PR head SHA
- unresolved non-outdated review threads remain on the activation PR

## 8. Next decision point

The next step after this closeout document is **Phase 3 Go/No-Go Review**, not automatic activation.

Before any Phase 3 activation PR, GPT Audit Gate must ask the Human Owner:

```text
ここからは Phase 3 activation PR です。
Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
進めてよいですか？
```

Without explicit Human Owner GO, Phase 3 activation must not proceed.

## 9. Related documents

- `docs/PHASE_3_GO_NO_GO_CHECKLIST.md`
- `docs/API_ACTIVATION_CHECKLIST.md`
- `docs/API_ACTIVATION_RUNBOOK.md`
- `docs/AST_POLICY_WHITELIST_ROADMAP.md`
- `docs/human用roadmap/phase3_to_phase7_roadmap.md`

## 10. Closeout recommendation

Phase 2.5 hardening can be closed after this document and the related roadmap/checklist updates are reviewed and merged.

This closeout does not authorize Phase 3 activation.
