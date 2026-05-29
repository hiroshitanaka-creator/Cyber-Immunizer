# Tool Execution Anomaly Protocol — Cyber-Immunizer

Use this protocol when any tool operation fails, is blocked, falls back, or
takes an unusual path during AI-assisted work on this repository.

---

## Scope

This protocol covers:

- Tool failure (API error, timeout, unexpected response)
- Blocked operation (permission denied, rate limit, safety/filter refusal)
- Connector limitation (MCP server unavailable, capability gap)
- Safety or filter refusal (platform-level block)
- Unknown block reason (operation failed without a clear error)
- Fallback path (alternative used because primary path failed)
- Low-level GitHub operation (blob/tree/commit/ref API used instead of normal
  file-level operations)
- Manual workaround (human-readable steps substituted for an automated path)

---

## Mandatory reporting rule

Do not keep anomalies only in internal thinking or temporary display.

Every anomaly covered by this protocol must appear in **at least one** of:
- The final response to the user
- The PR body (if a PR is being created or updated)

The anomaly log must be present as an audit trail, not only described in prose.

---

## Cause classification rules

- If the cause is unknown, write `Unknown` — do not guess.
- Do not write "safety filter" unless the tool or platform explicitly stated
  that reason. If uncertain, write `Unknown (possible filter — not confirmed)`.
- If a low-level GitHub blob/tree/commit/ref operation was used, the PR or
  change requires additional verification in the audit.

---

## Anomaly log template

Include this block verbatim (with fields filled in) in the final response or
PR body whenever an anomaly occurs.

```
## Tool / execution anomaly log
- Attempted action:
- Failed or blocked path:
- Fallback path used:
- Evidence level:
- Confirmed cause:
- Unknowns:
- User-visible risk:
- Verification required:
```

Field guidance:

| Field | What to write |
|---|---|
| Attempted action | What operation was attempted and why |
| Failed or blocked path | The exact tool call or path that failed |
| Fallback path used | What was used instead; "none" if no fallback |
| Evidence level | Confirmed / Strong hypothesis / Weak hypothesis / Unknown |
| Confirmed cause | The known reason; "Unknown" if not determinable |
| Unknowns | What is still unclear about the failure |
| User-visible risk | What the user may not be able to see or verify as a result |
| Verification required | What a human reviewer should check manually |

---

## Low-level GitHub operation flag

If any of the following were used during a session:
- Git blob API
- Git tree API
- Git commit API
- Git ref update API

Then the PR body must include a note that low-level Git operations were used,
and the audit must treat the resulting changes as requiring additional
verification (file-level diff, CI, and real-file content check).
