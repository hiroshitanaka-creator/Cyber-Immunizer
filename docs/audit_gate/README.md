# Audit Gate — Protocol Index

This directory contains operational protocols for the Cyber-Immunizer Audit Gate.

---

## Relationship to AUDIT_CHARTER.md

`docs/AUDIT_CHARTER.md` is the existing Audit Gate constitution: it defines
roles, responsibilities, the six audit categories, and the governance model.
It is **not** replaced by this directory.

The files here are **operational protocols** — step-by-step procedures that
implement the charter in practice. For audit decisions, read both:
`docs/AUDIT_CHARTER.md` for the governing rules, and the relevant protocol
below for the procedure.

---

## Files in this directory

### PULLBACK_PROMPT.md

A short prompt to paste into a new GPT session when the Audit Gate drifts from
its target. Covers the key orientation rules: current-request identification,
screenshot-first, current-head SHA verification, Codex thread distinction, and
scope control. Intentionally short; links to PR_AUDIT_PROTOCOL.md for the full
procedure.

### PR_AUDIT_PROTOCOL.md

Detailed protocol for auditing a pull request. Defines all mandatory fields to
verify, CI classification categories, Codex thread handling rules, and the
merge decision template. Use this for every PR audit and merge decision.

### TASK_PROMPT_PROTOCOL.md

Mandatory construction protocol for every implementation task prompt written by
GPT Audit Gate / Task Prompt Engineer. Defines the required task prompt
template, ALLOWED / REFERENCE_ONLY / FROZEN / IMPACT file boundaries, Change
Request fields, ambiguity handling, and the PR completion documentation gate.
Use this before writing any Claude Code, Codex, or other implementation-agent
prompt. It also defines Task Prompt Gate v2: mandatory pre-prompt
investigation, adversarial validation matrix, Codex issue pre-emption, and a
98/100 self-score threshold before GPT may output an implementation task
prompt.

### TOOL_EXECUTION_ANOMALY_PROTOCOL.md

Reporting rules for when a tool operation fails, is blocked, falls back, or
uses a low-level GitHub API path during work. Defines the mandatory anomaly log
template. Any such event must appear in the final response or PR body — not
only in internal thinking.

### CHANGELOG.md

Records why each protocol rule was added, keyed to the PR lesson that motivated
it. Not a project status document. Use it to understand the reasoning behind
specific rules in the other files.
