# PR Audit Protocol — Cyber-Immunizer

Use this protocol for every PR audit and merge decision.
Read `docs/AUDIT_CHARTER.md` for the governing roles and six audit categories.

---

## Mandatory fields

Verify and report every field below for each PR audit.

| Field | Notes |
|---|---|
| repo | Full repository path |
| PR number | Explicit; do not assume |
| title | As shown on GitHub |
| state | open / closed |
| merged | true / false |
| mergeable | Current GitHub value |
| draft | true / false |
| base branch | Target branch |
| base SHA | Current tip of base |
| head branch | Source branch |
| head SHA | **Current** head — mandatory |
| changed files | Full list |
| diff | Full diff at current head SHA |
| CI run | Workflow name |
| CI run id | Exact run id |
| failed step | Name, if any |
| skipped step | Names, if any |
| comments | All PR comments |
| Codex review | Review submissions |
| inline threads | All inline review threads |
| unresolved / outdated status | Per thread |
| scope-in | Changes within stated scope |
| scope-out | Changes outside stated scope |

If the head SHA is unchanged from a previous audit, state explicitly:
"headが変わっていないため、前回指摘は未対応です。"

If the head SHA changed, state explicitly:
"headが更新されたため、最新差分で再監査します。"

---

## CI classification

Classify the CI result as exactly one of:

| Classification | Meaning |
|---|---|
| NOT TRIGGERED | No workflow run exists for this head SHA |
| WORKFLOW PARSE FAILURE | Workflow YAML is invalid |
| RUNNER START FAILURE | Runner could not start |
| CHECKOUT FAILURE | Checkout step failed |
| SETUP FAILURE | Environment/tool setup failed |
| INSTALL FAILURE | Dependency install failed |
| TEST FAILURE | pytest (or equivalent) ran and failed |
| DOMAIN FAILURE | Domain-specific check failed (not pytest) |
| SUCCESS | All steps completed successfully |

Rules:
- If pytest failed, classify TEST FAILURE.
- If pytest did not run, do not call it TEST FAILURE.
- Do not treat post-step success as job success.
- Do not treat "Complete job" success as job success.
- CI green alone is not security approval.
- CI run must be for the **current head SHA**, not an older commit.

---

## Codex handling

Always check all of: PR comments, Codex review comments, review submissions,
inline review threads, unresolved state, outdated state, finding validity, and
whether the latest head fixes each finding.

| Situation | Classification |
|---|---|
| No Codex review, no comments, no reaction | NOT VERIFIED |
| +1 reaction only, no threads | VERIFIED BY REACTION ONLY |
| Unresolved + not outdated + valid finding | UNRESOLVED THREAD PRESENT (blocking) |
| Unresolved + outdated + latest diff fixes issue | VERIFIED |
| Resolved or outdated + latest diff fixes issue | VERIFIED |

Critical distinctions:
- A +1 reaction is **not** the same as a thread review.
- A review comment is **not** the same as the absence of inline threads.
- A generic "No major issues" comment does not override unresolved valid inline
  findings.
- Never approve while ignoring unresolved valid non-outdated threads.

---

## Self-report rule

PR bodies and Claude Code reports are self-reports. They must be verified
against GitHub state, current head SHA, diff, CI logs, and real files.
If the PR body contradicts the current diff, trust the diff.

---

## Scope control

For every PR, identify scope-in and scope-out changes. The following are always
suspicious unless explicitly part of the PR scope:

- `.github/workflows/*` execution logic changes
- `core/*` changes
- `scripts/*` logic changes
- `data/*.json` changes
- API activation
- GitHub Secret configuration
- Gemini API call
- `live_model_enabled=true`
- "Phase 3 started" or "API connected" wording

---

## Merge decision template

Report all four lines for every merge decision:

```
Code Audit:        APPROVE / REQUEST CHANGES / BLOCK
CI Verification:   VERIFIED / FAILED / NOT VERIFIED
Codex Verification: VERIFIED / FAILED / NOT VERIFIED / VERIFIED BY REACTION ONLY / UNRESOLVED THREAD PRESENT
Merge Recommendation: APPROVE / HOLD / BLOCK
```

Before final decision, check `docs/audit_gate/CHANGELOG.md` for relevant regression lessons, especially when a PR touches schemas, workflows, secret handling, generated-code boundaries, CI behavior, or audit protocol documents.

Do not give APPROVE unless all are true:
- Current PR state checked
- Current head SHA checked and stated
- Current diff checked
- Current CI for current head SHA checked
- Failed/skipped steps checked
- All Codex comments, reactions, and threads checked
- Unresolved thread status checked
- Scope drift checked
- Secret/API/Phase-3 wording checked
- Real file content checked where needed
- Stale PR body discarded where contradicted by diff

---

## Output structure

```
1. Scope reviewed
   repo:
   PR番号:
   title:
   state:
   merged:
   mergeable:
   draft:
   branch:
   base:
   head SHA:
   changed files:
   CI run:
   Codex comments / threads:

2. Evidence summary
   確認した一次証拠:
   CI状態:
   Codex状態:
   scope内 / scope外:

3. Findings
   [Finding format below]

4. Merge decision
   Code Audit:
   CI Verification:
   Codex Verification:
   Merge Recommendation:
```

Finding format:

```
### [Severity: Critical / High / Medium / Low]: Title
- 該当箇所:
- 脅威・リスク:
- 根本原因:
- Before / After:
- 必要な修正:
```

Include a required fix prompt only when the decision is REQUEST CHANGES, HOLD
for a fixable defect, or BLOCK.
