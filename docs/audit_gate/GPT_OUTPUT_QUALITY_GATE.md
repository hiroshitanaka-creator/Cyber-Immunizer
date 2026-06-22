# GPT Output Quality Gate

The GPT Output Quality Gate is the deterministic, offline validation layer for Cyber-Immunizer task prompts, PR audit reports, and PR-body audit receipts.

Natural-language protocols remain authoritative, but GPT narrative is not trusted as proof of compliance. A self-score can be gamed, a checklist can be copied without evidence, and an audit can assert `APPROVE` while omitting required verification. This gate requires a machine-readable JSON receipt plus minimum Markdown structure before GPT output can be treated as merge-ready evidence.

## Receipt block format

Every validated output must contain exactly one receipt block:

````markdown
<!-- AUDIT_GATE_RECEIPT_START -->
```json
{
  "kind": "pr_audit",
  "protocol_version": 1,
  "repo": "hiroshitanaka-creator/Cyber-Immunizer",
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ci_classification": "SUCCESS",
  "codex_verification": "VERIFIED",
  "docs_history_gate_checked": true,
  "scope_checked": true,
  "changed_files_checked": true,
  "current_diff_checked": true,
  "current_head_checked": true,
  "codex_threads_checked": true,
  "merge_recommendation": "APPROVE",
  "validator_expectation": "PASS"
}
```
<!-- AUDIT_GATE_RECEIPT_END -->
````

Shared required keys:

- `kind`: `task_prompt`, `pr_audit`, or `pr_body`
- `protocol_version`: integer `1`
- `repo`: exactly `hiroshitanaka-creator/Cyber-Immunizer`
- `head_sha`: 40-character hexadecimal SHA
- `validator_expectation`: exactly `PASS`

## Task prompt receipt requirements

For `kind: "task_prompt"`, the receipt must include:

- `self_score`: integer `>= 98`
- `source_evidence_present: true`
- `pre_prompt_investigation_complete: true`
- `allowed_files_declared: true`
- `impact_declared: true`
- `change_request_complete: true`
- `docs_history_gate_checked: true`
- `adversarial_matrix_present: true`

The Markdown body must include the required task prompt sections from `TASK_PROMPT_PROTOCOL.md`, including `ALLOWED`, `REFERENCE_ONLY`, `FROZEN`, `IMPACT`, `Change Request`, `Pre-Prompt Investigation Gate`, `Source Evidence`, and `Self Score`.

`Source Evidence` must include at least one `path:start-end` style header and one fenced excerpt. Assertion-only evidence such as `確認済み`, `reviewed`, `checked`, `読了`, or `確認した` is invalid without quoted source content.

## PR audit receipt requirements

For `kind: "pr_audit"`, the receipt must include:

- `ci_classification`: one of the CI classifications in `PR_AUDIT_PROTOCOL.md`
- `codex_verification`: one of the Codex verification classifications in `PR_AUDIT_PROTOCOL.md`
- `docs_history_gate_checked: true`
- `scope_checked: true`
- `changed_files_checked: true`
- `current_diff_checked: true`
- `current_head_checked: true`
- `codex_threads_checked: true`
- `merge_recommendation`: `APPROVE`, `HOLD`, or `BLOCK`

The Markdown body must include the four-line merge decision format:

```text
Code Audit:
CI Verification:
Codex Verification:
Merge Recommendation:
```

`APPROVE` is valid only when CI is `SUCCESS`, Codex verification is `VERIFIED`, and every required verification boolean is true.

## PR body receipt requirements

PR bodies must include the same wrapped JSON receipt in the GPT Audit Gate section. `kind` may be `pr_body` or `pr_audit` when validating a PR body context.

Placeholder text inside the receipt area is invalid, including `<40-hex-sha>`, `ここに`, `TODO`, `TBD`, `未記入`, or `paste`. If the GPT Audit Gate decision checkbox is checked as APPROVE, the receipt must also satisfy the APPROVE conditions.

## Validator command

Run the stdlib-only validator locally:

```bash
python scripts/validate_gpt_gate_output.py path/to/file.md
python scripts/validate_gpt_gate_output.py --kind task_prompt path/to/file.md
python scripts/validate_gpt_gate_output.py --kind pr_audit path/to/file.md
python scripts/validate_gpt_gate_output.py --kind pr_body path/to/file.md
```

The command exits `0` on PASS and non-zero on FAIL.

## CI workflow role

`.github/workflows/gpt-gate-quality.yml` runs the focused validator test suite and validates committed valid fixtures. It is static/offline only: it uses no secrets, does not call Gemini, and does not run paid-credit workflows.

## What this gate does not do

- It does not prove that an audit is true.
- It does not query live GitHub PR state.
- It does not replace the Project Owner's final merge decision.
- It does not configure branch protection or rulesets.
