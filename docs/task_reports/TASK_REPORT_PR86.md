# Task Report PR86 — Task Prompt Protocol hardening

## Summary

Strengthened the existing canonical task prompt protocol and root Codex guardrails so future implementation tasks must be design-audited, bounded, evidence-backed, and stop-oriented before Codex edits files.

## Canonical State checked

- `AGENTS.md` was checked as the root Codex workflow guardrail source.
- `data/project_state.json` was checked for current `state_id`, `next_action`, and no-API policy:
  - `state_id`: `phase3_propose_output_contract_hardened_pending_owner_review`
  - `next_action`: `review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun`
  - no-API policy: paid-credit runs, `workflow_dispatch`, and Gemini API calls are forbidden in this PR.
- `docs/PROJECT_STATE.md` was checked for current authority order and next-action context.
- `docs/AI_ENTRYPOINT.md` was checked to avoid duplicating its routing role; no contradiction requiring an edit was found.
- `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` was checked as the existing canonical task prompt construction protocol.

## Changed files

- `AGENTS.md` — added a concise Task prompt reception gate pointing Codex to `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` and requiring stop-and-report behavior when required task prompt fields are missing.
- `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` — strengthened the existing protocol with explicit completion target, duplicate-doc prevention, Codex weak-model safety, receiving-agent stop requirements, and Codex Review pre-emption language.
- `tests/test_task_prompt_protocol_docs.py` — added text regression tests for design audit, 100-point completion target, duplicate-doc prevention, Codex weak-model stop language, and AGENTS.md protocol linkage.
- `docs/task_reports/TASK_REPORT_PR86.md` — added this task report.

## Design audit performed

- Confirmed the task updates the existing canonical `TASK_PROMPT_PROTOCOL.md` instead of creating a duplicate design-gate document.
- Confirmed the AGENTS.md change is a short receiving-task stop rule and does not duplicate the full protocol.
- Confirmed tests remain simple text-presence checks with no new dependencies.
- Confirmed runtime logic, workflow behavior, model settings, paid-credit state, promotion state, ledger records, and SSOT files are out of scope and unchanged.

## Existing-doc overlap decision

`docs/AI_ENTRYPOINT.md` already routes implementation task prompt work to `docs/audit_gate/TASK_PROMPT_PROTOCOL.md`. No contradiction was found, so this PR updates only the canonical protocol and root reception guardrail rather than creating a new protocol, runbook, or current-state document.

## Verification commands and results

- `pytest tests/test_task_prompt_protocol_docs.py -q` — passed (`14 passed`).
- `pytest tests/ -q` — passed (`1926 passed`, `95 warnings`).
- `python -m json.tool data/project_state.json` — passed.
- `git diff --name-only | grep -E '^(\.github|core|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true` — passed; no forbidden paths were reported.

## No-API / no-promotion confirmation

No paid-credit workflows were run. No `workflow_dispatch` was run. No Gemini API call was made. No ledger files were edited. No candidate was promoted, and `promote_approved` was not changed.

## Residual risk

The new protection is documentation/test-based. It does not add runtime or CI enforcement beyond the repository's existing test execution expectations.

## Next recommended action

Open the PR and request `@codex Review`.
