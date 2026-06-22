# GPT Failure Registry

## Purpose

This registry records repeated GPT prompt and audit failures so they become protocol improvements, validator fixtures, or explicit scope decisions instead of recurring review noise.

A valid Codex finding inside the declared PR scope must be classified during audit. Repeated `GPT_PRE_PROMPT_FAILURE` entries must become either a validator invalid fixture or a protocol update.

## Classification enum

Use only the classifications defined in `docs/audit_gate/PR_AUDIT_PROTOCOL.md`:

- `GPT_PRE_PROMPT_FAILURE`
- `IMPLEMENTATION_AGENT_FAILURE`
- `INTENTIONAL_DEFERRED_SCOPE`
- `OUT_OF_SCOPE_NEW_FINDING`
- `UNAVAILABLE_INFORMATION`

## Required entry format

```markdown
### YYYY-MM-DD — <short finding title>
- PR / head SHA: <PR number or none> / <40-hex-sha>
- Classification: <one enum value>
- Finding: <what Codex or audit found>
- Scope status: <inside declared scope / outside declared scope / deferred by owner>
- Preventive action: <validator fixture / protocol update / no action with reason>
- Follow-up owner action: <if any>
```

## Registry entries

No production GPT failures have been recorded in this registry yet.

### Example only — Assertion-only source evidence accepted
- PR / head SHA: example / aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Classification: `GPT_PRE_PROMPT_FAILURE`
- Finding: A task prompt claimed files were checked but provided no quoted source evidence.
- Scope status: Inside declared scope.
- Preventive action: Add an invalid fixture for assertion-only evidence.
- Follow-up owner action: None.

This example is illustrative and is not a production incident.
