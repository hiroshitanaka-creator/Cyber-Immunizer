# Propose Output Contract Root Cause

<!--
AI_DOC_META
status: CURRENT
scope: Root-cause analysis of the propose/output-contract failure behind the three
  gemini-3-flash-preview paid-credit API success records that produced no valid
  mutation patch (2026-06-03 / 2026-06-04), and the accepted no-API remediation.
use_for:
  - understanding why API success did not produce a candidate patch
  - auditing the propose output-contract remediation before the next
    Project-Owner-approved paid-credit run
do_not_use_for:
  - executing paid-credit runs or workflow_dispatch
  - changing model names, budgets, or promotion behavior
related:
  - data/project_state.json
  - docs/PROJECT_STATE.md
  - docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md
  - scripts/propose_mutation.py
  - tests/test_propose_output_contract.py
AI_DOC_META_END
-->

## Canonical state

Current canonical state per `data/project_state.json` and `docs/PROJECT_STATE.md`
(minimally updated within PR #84, Owner-directed):

- `state_id=phase3_propose_output_contract_hardened_pending_owner_review`
- `next_action=review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun`

Pre-PR84 canonical state (**historical state before this remediation** — recorded
here because it is what triggered this analysis; NOT the current canonical state):

- `state_id=phase3_paid_credit_api_success_patch_not_produced`
- `next_action=fix_propose_output_contract_before_new_paid_credit_run`

Historical facts, unchanged by this remediation:

| Fact | Value |
|---|---|
| paid-credit API success records (`gemini-3-flash-preview`) | 3 |
| `valid_mutation_patch_produced` | false |
| `apply_reached` / `evaluate_reached` / `promote_reached` | false / false / false |
| `promote_approved` | false (promotion not approved; does NOT mean the API call was unexecuted) |

This document and its remediation are **no-API and no-promotion**: no Gemini call,
no `workflow_dispatch`, no ledger edit, no candidate promotion.

## Evidence from paid-credit runs

Source: `data/api_usage_ledger.json` (records 5–7) and
`docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md` (Sections 4–6).

| Ledger record | Workflow run | main SHA at run time | propose result |
|---|---|---|---|
| 2026-06-03T23:36:37Z | 26919888348 | `90d39c86f6f1` | patch_exists=false |
| 2026-06-04T00:34:12Z | 26922191264 | `4482b416d168` | patch_exists=false |
| 2026-06-04T01:33:29Z | 26924388218 | `6b428f147ac5` | patch_exists=false |

All three propose job logs recorded the identical error:

```
Gemini replacement_code validation failed: replacement_code is not valid Python
syntax: expected an indented block after function definition on line 1 (<unknown>, line 3)
```

All three runs consumed real output tokens (590 / 562 / 561), so the model returned
substantive JSON content — the failure was in the `replacement_code` field's format,
not an empty or truncated response.

## What API success means

`success=true` in `data/api_usage_ledger.json` records **HTTP 200 + token usage
recorded** — nothing more. It is the budget-integrity record for the call itself.
It does **not** mean the model output was usable, that a patch was produced, or that
any later pipeline stage ran.

## What failed

The pipeline stages must be kept distinct:

| Stage | Result in all 3 runs |
|---|---|
| 1. API success (HTTP 200 + tokens) | ✅ succeeded — recorded `success=true` in ledger |
| 2. Model content validity (JSON parse + schema) | ✅ passed — JSON parsed, all 5 schema fields present |
| 3. `replacement_code` syntax validity | ❌ **failed — `ast.parse()` SyntaxError** |
| 4. `mutation_patch.json` creation | ❌ never written (`patch_path=null`, `patch_exists=false`) |
| 5. apply reached | ❌ no — evaluate job skipped on `patch_exists=false` |
| 6. evaluate reached | ❌ no — no `fitness_report.json`, no adoption-gate result |
| 7. promote reached | ❌ no — promote job skipped; `promote_approved` moot |

The failure boundary is stage 3: the propose output contract.

## Where the output contract is enforced

All enforcement lives in `scripts/propose_mutation.py` (fail-closed; generated code
is never executed):

- `_parse_and_validate_response()` — JSON parse → `_validate_patch_schema()` →
  `_validate_replacement_code()`. Any error returns `(None, error)`; `main()` then
  exits non-zero without writing `.cyber_immunizer/mutation_patch.json`.
- `_validate_patch_schema()` — required/extra fields, types, length caps.
- `_validate_replacement_code()` — checks 1–11: mutation markers, markdown fences,
  `def` statements, forbidden tokens, indentation contract (4-space top level,
  multiples of 4, no tabs), AST syntax via an anchored wrapper, non-empty /
  non-pass-only body with at least one return, `return DetectionResult(...)` shape,
  top-level fallthrough guard, keyword-only argument shape, and static value checks.
- The workflow (`.github/workflows/immunization_loop.yml`, read-only here) gates the
  evaluate job on `patch_exists == 'true'`, so a rejected response can never reach
  apply/evaluate/promote.

## Current prompt / schema / validation path

- System prompt: `_LLM_SYSTEM_PROMPT` — 16 STRICT RULES plus a
  `REPLACEMENT_CODE FORMAT CONTRACT` block (REQUIRED / FORBIDDEN lists and one GOOD /
  four BAD worked examples).
- User prompt: `_LLM_USER_PROMPT_TEMPLATE` — mutation region, detector interface
  summary, neutralized threat IDs only.
- Response schema: `_PATCH_SCHEMA_FOR_GEMINI` sent as `response_schema` with
  `response_mime_type="application/json"`; the schema constrains key names and
  types only — it cannot express "syntactically valid Python", so post-response
  validation is the authoritative gate.
- Expected `replacement_code` shape: a 4-space-indented function-body fragment for
  `inspect_request()` — no `def`, no markers, no markdown fences, ending in a
  top-level `return DetectionResult(...)` fallback.
- Failure artifact behavior: on rejection, status JSON is
  `{"success": false, "error": ..., "patch_path": null}` and no patch file exists.

## Existing tests

`tests/test_gemini_integration.py` already covers the validator extensively
(indentation contract, empty/comment-only/pass-only bodies, markdown fences,
`def` rejection, return-shape checks 8–9, argument-shape check 10, X-007 static
value checks). `tests/test_gemini_paid_credit.py` covers budget/ledger gates and
the no-patch-artifact boundary. `tests/test_propose_output_contract.py` (added with
this remediation) pins the historical failure shape and the prompt obligations —
see "Accepted remediation strategy".

## Root-cause hypotheses

The validator wrapper at run time (sha `90d39c86`) was:

```python
wrapped = (
    "def _candidate_body(request):\n"
    "    " + _MUTATION_START_MARKER + "\n"
    + code
    + "\n" + _MUTATION_END_MARKER + "\n"
)
```

Line 1 is the wrapper's own `def`; line 2 is an indented comment (comments do not
form a block); line 3 is the **first line of the model's replacement_code**.

Local reproduction against that exact wrapper (no API call):

| Hypothesis | Reproduced error |
|---|---|
| H1: model returned the body starting at **column 0** (unindented) | `expected an indented block after function definition on line 1 (<unknown>, line 3)` — **exact match** |
| H2: model returned an empty / comment-only `replacement_code` | same message but `line 4` — does not match |
| H3: model returned its own `def inspect_request(...):` at column 0 with an empty body | `(<unknown>, line 3)` — **exact match** |

So the verbatim run error is consistent with H1 or H3 (indistinguishable without the
raw response text, which is intentionally never logged): the model emitted
`replacement_code` whose first line sat at column 0 instead of the required 4-space
body indentation. **Root cause: at run time the output contract was under-specified
on the model side.** The system prompt then described `replacement_code` only as
*"Python code string for the function body only (no def statement)"* — it contained
**no indentation requirement, no body-fragment examples, no empty-body prohibition,
and no markdown prohibition**. The validator side worked exactly as designed
(fail-closed, no patch written); the contract communication side did not.

Contributing factor: the run-time error message did not state the failure stage, so
ledger `success=true` plus a propose failure was repeatedly misread as
promotion/API state confusion (see `docs/PROJECT_STATE.md` §3–4).

Timeline note: the bulk of the contract hardening (indentation contract, semantic
body checks, return-shape checks, FORMAT CONTRACT prompt block with GOOD/BAD
examples) was merged to `main` between 2026-06-04 and 2026-06-07 (commits
`94a6561`…`7b28eb6`), **after** the three failed runs. No paid-credit run has been
executed since, so that hardening — and this remediation — is unverified against a
live call by design until the Project Owner approves a rerun.

## Accepted remediation strategy

Smallest robust fix, local-only, preserving the fail-closed validator boundary:

1. **Prompt obligations made explicit** (`_LLM_SYSTEM_PROMPT`): syntactic validity
   is now a stated REQUIRED obligation ("checked with ast.parse(); ANY SyntaxError
   is rejected fail-closed"), and placeholder-ellipsis-only bodies are explicitly
   FORBIDDEN alongside the existing empty-body / pass-only / markdown prohibitions.
2. **Stage-marked diagnostics** (`_parse_and_validate_response`): every model-output
   rejection now carries `propose/output-contract failure — the Gemini API call
   succeeded; the model output was rejected before any patch was written`, so run
   logs and the ledger error field can no longer be misread as API failures.
3. **Dedicated no-API contract tests** (`tests/test_propose_output_contract.py`):
   pin the exact historical failure shape (column-0 body and model-emitted `def`
   reproduce the run-log error against the historical wrapper and are rejected by
   the current validator), reject empty-body / pass-only / ellipsis-only /
   markdown-wrapped output, prove a valid fixture passes end-to-end to a written
   patch dict, and assert the prompt states each obligation.

No schema change: the current schema has no no-patch/abstain field, and inventing
one is out of scope (see rejected strategies).

## Rejected remediation strategies

- **Do not auto-insert `pass` into empty functions.** An empty body is a meaningless
  candidate; silently making it parseable would convert a model failure into a
  fake candidate and waste an evaluate cycle.
- **Do not silently repair invalid model code into a candidate.** Re-indenting,
  stripping fences, or otherwise rewriting arbitrary LLM output blurs the provenance
  boundary the AST policy depends on; the validator must judge what the model
  actually produced.
- **Do not bypass validation.** The validator is the safety boundary between
  unreviewed LLM output and `apply_mutation.py`.
- **Do not lower validator strictness.** All checks 1–11 are retained unchanged.
- **Do not run another paid-credit attempt before remediation.** A rerun without a
  contract fix would most likely re-fail at the same boundary and consume budget;
  any rerun is a separate Project-Owner-approved decision.
- **Do not invent a new response schema (e.g. an abstain/no-patch field).** The
  existing parser and workflow have no such path; a schema migration without a
  proven need would expand scope and risk for no evidence-backed benefit.

## No-API / no-promotion guarantees

This remediation, including its tests:

- makes **no Gemini API call** (all tests are local; mocks/fixtures only);
- triggers **no `workflow_dispatch`** and changes nothing under `.github/**`;
- does **not edit** `data/api_usage_ledger.json` or `data/genome.json`;
- does **not promote** any candidate and leaves `promote_approved=false`;
- does **not weaken** any validator check — every change is prompt text,
  diagnostic wording, documentation, or added tests.
