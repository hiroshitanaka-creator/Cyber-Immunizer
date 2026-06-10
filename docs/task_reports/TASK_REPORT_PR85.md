# Task Report — PR #85

## Summary

Added root-level Codex workflow guardrails for Cyber-Immunizer as a small,
documentation-only PR. The new rules make `data/project_state.json` and
`docs/PROJECT_STATE.md` the canonical current-state sources, record the key
no-API/no-promotion prohibitions, require one purpose per PR, and require tests,
forbidden-path checks, PR body sections, and `@codex Review` after PR creation.

## Canonical State checked

| Source | Checked result |
|---|---|
| `data/project_state.json` | `state_id=phase3_propose_output_contract_hardened_pending_owner_review`; `next_action=review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun`; no-API tests required; paid-credit run, `workflow_dispatch`, and Gemini API call forbidden in this PR. |
| `docs/PROJECT_STATE.md` | Confirms Phase 3 state, PR #84 hardening pending Owner review, no new paid-credit run executed, and `promote_approved=false`. |

## Changed files

| File | Change |
|---|---|
| `AGENTS.md` | New root-level Codex workflow rules. |
| `docs/task_reports/TASK_REPORT_PR85.md` | New task report for this PR. |

## Not changed / forbidden files

- Did not change `core/**`.
- Did not change `.github/**`.
- Did not change `data/**`, including `data/project_state.json`, `data/api_usage_ledger.json`, and `data/genome.json`.
- Did not change ledger files.
- Did not change model names or budget settings.

## Verification commands and results

```text
pytest tests/ -q
python -m json.tool data/project_state.json
git diff --name-only | grep -E '^(\.github|core|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true
```

`pytest tests/ -q` passed: 1920 passed, 95 warnings.
`python -m json.tool data/project_state.json` passed.
Forbidden-path check passed with no forbidden paths reported.

## No-API / no-promotion confirmation

- No paid-credit run was executed.
- No `workflow_dispatch` was executed.
- No Gemini API call was made.
- No ledger file was edited.
- No candidate was promoted.
- `promote_approved` was not changed.

## Residual risk

This PR adds workflow documentation only. It does not enforce the guardrails in
code or CI; future agents and reviewers must follow the documented process.

## Next recommended action

Review and merge this guardrail PR, then continue with the canonical next action:
Project Owner review of the PR #84 propose/output-contract fix before any
owner-approved paid-credit rerun.

## Codex Review request

After opening the PR, request:

```text
@codex Review
```
