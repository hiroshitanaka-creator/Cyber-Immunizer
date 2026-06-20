---
name: cyber-immunizer-meta-devsecops-mitre-ultra
description: Defensive Cyber-Immunizer DevSecOps workflow for repository audits, attack-surface analysis, MITRE ATT&CK tagging, remediation planning, testing, PR preparation, CI failure triage, and safe auto-fix loops. Use when asked to security-audit Cyber-Immunizer, map findings to MITRE ATT&CK, generate attack-surface/impact/priority reports, convert audit results into tasks, or harden code without running attacks or paid-credit workflows.
---

# Cyber-Immunizer Defensive MITRE DevSecOps

## Safety boundary

Use offensive knowledge only to strengthen defenses. Do not output exploit code, payloads, procedural abuse steps, scanner logic, credential-theft logic, or instructions that enable real-world attack execution. Use MITRE ATT&CK only for tactic/technique tagging, prioritization, and defensive explanation.

For Cyber-Immunizer tasks, obey repository instructions first, especially `AGENTS.md` and canonical project-state files. Never run paid-credit workflows, `workflow_dispatch`, Gemini API calls, promotion actions, or ledger edits unless the Project Owner explicitly approves that exact task.

## Required pre-edit workflow

1. Read `AGENTS.md`.
2. Read `data/project_state.json` and `docs/PROJECT_STATE.md`.
3. Identify and state:
   - current `state_id`
   - current `next_action`
   - allowed files
   - forbidden files
   - required verification commands
4. For tasks involving paid-credit state, model settings, promotion state, CI state, or branch/merge state, inspect relevant machine evidence before editing:
   - `data/api_usage_ledger.json`
   - `data/genome.json`
   - GitHub Actions / CI evidence when available
   - latest main/HEAD evidence
5. Keep the PR to one purpose. If a needed fix is out of scope, record it as a follow-up instead of implementing it.

## Defensive audit workflow

Use this sequence for security-audit or hardening requests:

1. `repository_audit`: identify relevant files and trust boundaries.
2. `security_audit_advanced`: inspect external input, parsing, file I/O, subprocess, network, secrets, logging, exception handling, and dependency risk.
3. `attack_scenario_analysis`: describe abuse paths abstractly and defensively only.
4. `MITRE_mapping`: map each scenario to ATT&CK tactics and technique IDs/names only.
5. `attack_visual_report_generation`: produce Attack Surface, Entry Point, Attack Path, Impact, and Defense Priority sections.
6. `audit_to_task_prompt`: turn findings into a focused remediation task with allowed/forbidden files and tests.
7. `refactor_code`: implement the smallest safe fix if the user requested implementation.
8. `test_and_debug`: run required tests and a forbidden-path check.
9. `audit_to_pr`: summarize defensive improvement, state checked, changed files, verification, no-API confirmation, residual risk, and next action.
10. CI failure loop: if CI results are available and fail, fix up to three scoped iterations; reassess whether the fix expands attack surface; after three failures, propose rollback or owner decision.

## Report format

When generating a report, use this structure:

```markdown
## Attack Surface Map
- External input:
- API / model calls:
- File access:
- Crypto / hashing:
- Logging and exception handling:
- Dependencies:

## Entry Points
- Entry point:
- Validation concern:
- Existing control:
- Residual risk:

## Attack Path + MITRE Mapping
### Scenario: <defensive title>
- Entry point:
- Attacker objective (abstract):
- Attack path (abstract, no payloads or steps):
- MITRE ATT&CK:
  - Tactic(s):
  - Technique(s): Txxxx: <name>
- Defense priority: High | Medium | Low

## Impact Map
- Information leakage:
- Integrity / tampering:
- Availability / DoS:
- Authentication / authorization:
- Governance / CI risk:

## Defense Plan
- Priority controls:
- Tests to add or run:
- Logging / audit / detection notes:
- Follow-up task prompt:

## Verification
- Commands run and results:
- No-API confirmation:
- Forbidden-path confirmation:
```

Keep attack paths abstract. Prefer phrases such as “could attempt to broaden execution surface” over concrete commands or payload strings.

## MITRE tagging guidance

Use common tactic labels and technique IDs/names only. Do not include exploitation procedures.

- Initial Access: T1190 Exploit Public-Facing Application
- Execution: T1059 Command and Scripting Interpreter
- Persistence: use only when repository changes could create durable unauthorized behavior
- Privilege Escalation: use only for privilege-boundary changes
- Defense Evasion: T1027 Obfuscated Files or Information, T1562 Impair Defenses
- Credential Access: T1552 Unsecured Credentials
- Discovery: T1082 System Information Discovery
- Collection: T1005 Data from Local System
- Exfiltration: T1041 Exfiltration Over C2 Channel
- Impact: T1499 Endpoint Denial of Service, T1565 Data Manipulation

## Dependency vulnerability audit

When dependency scanning evidence is available, classify each vulnerable dependency defensively:

```markdown
### Vulnerable Dependency
- Library:
- Current version:
- CVE-ID:
- Severity:
- Defensive scenario:
- MITRE ATT&CK:
  - Tactic(s):
  - Technique(s): Txxxx: <name>
- Recommended version or action:
- Tests / compatibility checks:
```

Do not speculate beyond evidence. If no scanner output exists, recommend a follow-up scan instead of inventing CVEs.

## Cyber-Immunizer guardrails

Default forbidden actions unless explicitly approved for the specific task:

- paid-credit workflows or paid-credit runs
- `workflow_dispatch`
- Gemini API calls
- ledger edits, especially `data/api_usage_ledger.json`
- setting `promote_approved=true`
- candidate promotion
- `.github/**` changes
- `core/**` changes
- model-name or budget-setting changes
- reintroducing `.grok/**`

Default verification for typical implementation changes:

```bash
pytest tests/ -q
git diff --name-only | grep -E '^(\.github|core|data)/|ledger' && echo "FORBIDDEN PATH TOUCHED" && exit 1 || true
```

If only documentation or skill files changed, still run the forbidden-path check and run the repo-required tests unless the task explicitly narrows verification.
