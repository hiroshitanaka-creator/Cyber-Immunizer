# Defensive MITRE report template

Use this template for Cyber-Immunizer security audit reports. Keep all attack content abstract and defense-oriented.

## Canonical State checked
- `state_id`:
- `next_action`:
- Machine evidence checked:
- Allowed files:
- Forbidden files:
- Required tests:

## Attack Surface Map
| Surface | Defensive observation | Existing control | Priority |
|---|---|---|---|
| External input |  |  |  |
| API / model call |  |  |  |
| File access |  |  |  |
| Logging / exception handling |  |  |  |
| Dependencies |  |  |  |

## Attack Path + MITRE Mapping
### Scenario: <title>
- Entry point:
- Attacker objective (abstract):
- Attack path (abstract, no payloads or steps):
- MITRE ATT&CK:
  - Tactic(s):
  - Technique(s): Txxxx: <name>
- Defense priority: High | Medium | Low

## Defense Plan
- Priority controls:
- Checks/tests to add:
- Logging/audit/detection notes:
- Follow-up task prompt:

## Verification
- Commands and results:
- No-API confirmation:
- Forbidden-path confirmation:
