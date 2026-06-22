# Task: Add a deterministic example gate.

## Context
- Repo: hiroshitanaka-creator/Cyber-Immunizer
- Goal: validate structure.

## Scope
- [ ] Add one validator fixture.

## Files
### ALLOWED
- scripts/validate_gpt_gate_output.py — validator behavior.

### REFERENCE_ONLY
- docs/audit_gate/TASK_PROMPT_PROTOCOL.md

### FROZEN
- core/**

### IMPACT
- tests/fixtures/gpt_gate/** — validator fixtures.

## Constraints
- No dependencies.

## Definition of Done
- python scripts/validate_gpt_gate_output.py tests/fixtures/gpt_gate/valid/valid_task_prompt.md

## On Ambiguity
Stop and report.

## Change Request
- WHAT: Add validator fixture.
- WHY: Current examples need machine coverage.
- INVARIANT: Offline validation only.
- DO_NOT: Do not call APIs.

## Pre-Prompt Investigation Gate
- main / PR / head SHA: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Canonical source of truth: docs/audit_gate/TASK_PROMPT_PROTOCOL.md
- Current implementation: See Source Evidence block below.
- Downstream effects: CI fixture validation.
- Existing tests: validator tests.
- Missing/adversarial tests: invalid receipt cases.
- README / docs / changelog / history impact: changelog entry required.
- Likely Codex findings pre-empted: missing evidence.
- Scope-out / PO-overridable items: branch protection.

## Source Evidence
### scripts/validate_gpt_gate_output.py:1-3
```python
#!/usr/bin/env python3
print("example")
```
根拠: Demonstrates a real path header and fenced excerpt.

## Self Score
- Score: 99 / 100
- Pass threshold: 98

<!-- AUDIT_GATE_RECEIPT_START -->
```json
{
  "kind": "task_prompt",
  "protocol_version": 1,
  "repo": "hiroshitanaka-creator/Cyber-Immunizer",
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "validator_expectation": "PASS",
  "self_score": 99,
  "source_evidence_present": true,
  "pre_prompt_investigation_complete": true,
  "allowed_files_declared": true,
  "impact_declared": true,
  "change_request_complete": true,
  "docs_history_gate_checked": true,
  "adversarial_matrix_present": true
}
```
<!-- AUDIT_GATE_RECEIPT_END -->
