<!--
AI_DOC_META
status: CANONICAL
scope: Mandatory PR audit and merge decision rules, including the Audit Evidence Ledger that every audit report must carry.
use_for:
  - auditing any PR before a merge decision
  - constructing the Audit Evidence Ledger (pre-diff spec recitation, call-site, negative evidence, read manifest)
  - classifying CI results, Codex findings, and audit-evidence failures
do_not_use_for:
  - implementation task prompt construction (see TASK_PROMPT_PROTOCOL.md)
  - thread handoff construction (see THREAD_HANDOFF_PROTOCOL.md)
related:
  - docs/AI_ENTRYPOINT.md
  - docs/AUDIT_CHARTER.md
  - docs/audit_gate/CHANGELOG.md
  - scripts/validate_audit_evidence.py
  - CLAUDE.md
last_reviewed: 2026-06-10
AI_DOC_META_END
-->
# PR Audit Protocol — Cyber-Immunizer

Use this protocol for every PR audit and merge decision.
Read `docs/AUDIT_CHARTER.md` for the governing roles and six audit categories.

---

## Terminology rule

| Term | Usage |
|---|---|
| **Project Owner** | Canonical term for the final decision-maker (hiroshitanaka-creator). Use for: repository direction, final merge decision, paid-credit approval, promote approval, external secret/billing verification. |
| ~~Human Owner~~ | Forbidden — use `Project Owner` instead. |
| ~~人間オーナー~~ | Forbidden — use `Project Owner` instead. |
| ~~人~~ (as final decision-maker) | Forbidden when referring to the final decision-maker — use `Project Owner` instead. |

Do not replace `Project Owner` with vague terms.

---

## Current-state authority

When an audit needs the project's **current state**, interpret it in this authority order. Do not
reconcile every historical document against every other document.

1. **Current-state authority**:
    * machine evidence (latest `main` HEAD, `data/api_usage_ledger.json`, `data/genome.json`, GitHub Actions / CI results)
    * `data/project_state.json`
    * `docs/PROJECT_STATE.md`
2. `README.md` and `CLAUDE.md` are derived / operational summaries, not independent current-state sources.
3. Historical documents are **not** current-state sources if labeled historical.
4. PR bodies and task reports are evidence for their own PR only. They are **not** current-state authorities after merge.
5. Future auditors **must not** request wording synchronization across historical documents unless a historical document falsely claims to be current.

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
| documentation / history gate | README / docs / changelog / generator / data-history update need checked before PR completion |

If the head SHA is unchanged from a previous audit, state explicitly:
"headが変わっていないため、前回指摘は未対応です。"

If the head SHA changed, state explicitly:
"headが更新されたため、最新差分で再監査します。"

---

## Audit Evidence Ledger (mandatory — proves the audit went beyond the diff)

An audit that only reads the diff is invalid. Assertions such as "checked",
"confirmed", or "no issues" carry zero evidential weight. Every audit report
must attach an **Audit Evidence Ledger**: verbatim, machine-verifiable proof
that the auditor read the repository beyond the diff. The receiving side
verifies the ledger mechanically with `scripts/validate_audit_evidence.py`;
a missing ledger or a single mismatched quote invalidates the entire audit.

### Rule 1 — Pre-diff spec recitation (read the file BEFORE the diff)

**Before reviewing the diff**, for every modified file, quote the file's core
processing that is **not** part of the diff — function/class name plus line
numbers plus verbatim lines — and explain the current specification in your
own words. This forces the reading order: current spec first, change second.

- The quoted range must lie entirely outside the diff hunks of that file.
- For `.py` files, `SYMBOL` (the function/class name) is mandatory and must
  appear in the quoted lines (quote the signature, not an arbitrary body slice).
- For prose/docs files with no functions, quote a section heading and its
  surrounding lines instead.
- Newly added files are exempt (the whole file is the diff) but must still
  appear in the Read Manifest as `FULL`.

### Rule 2 — Call-site evidence

For each changed function, constant, or schema key, list every line in the
repository that references it (`path:lineno:content`), with an explicit total
`COUNT`. "No callers" must be stated as `COUNT: 0`. The validator recounts and
rejects the audit if the count is incomplete or stale. Required whenever any
`.py` file is changed.

### Rule 3 — Negative evidence (minimum 2)

State at least two things you searched for and did **not** find (e.g. a
duplicate definition, a leftover `live_model_enabled=true`, an un-updated
generator output), each as a literal `PATTERN` with the expected `COUNT`
(usually 0) and a `NOTE` explaining what the absence proves. The validator
re-runs the search and rejects the audit if reality disagrees.

### Rule 4 — Read manifest

List every file you opened, split into `FULL:` (read in full) and
`DIFF_ONLY: <path> reason: <text>` (diff only, with a non-trivial reason).
Every changed file must appear in the manifest.

### Evidence block format

Each piece of evidence is a fenced markdown block with the info string
`audit-evidence`, a `KEY: value` header, a `---` separator, then the verbatim
body. Searches are literal substring matches (no regex) so the receiving side
can reproduce them deterministically.

````
```audit-evidence
TYPE: SPEC_RECITATION
FILE: core/detector.py
LINES: 40-44
SYMBOL: detect
SPEC: detect() normalizes the payload and runs each signature regex against it.
---
def detect(payload: str) -> DetectionResult:
    normalized = _normalize(payload)
    ...verbatim lines 40-44...
```

```audit-evidence
TYPE: CALLSITE
SYMBOL: detect
COUNT: 2
SCOPE: core/, scripts/
---
core/detector.py:40:def detect(payload: str) -> DetectionResult:
scripts/evaluate_candidate.py:88:    result = detect(sample)
```

```audit-evidence
TYPE: NEGATIVE
PATTERN: live_model_enabled=true
COUNT: 0
SCOPE: core/, scripts/
NOTE: no code path enables the live model flag outside the approved CLI gate.
---
```

```audit-evidence
TYPE: READ_MANIFEST
---
FULL: core/detector.py
FULL: scripts/evaluate_candidate.py
DIFF_ONLY: data/genome.json reason: generated artifact; integrity checked via ledger entry instead
```
````

### Mechanical verification (receiving side)

The receiving side (Claude or any other receiving AI) runs:

```
python scripts/validate_audit_evidence.py --report <audit_report.md> --base-ref origin/main
```

The validator confirms every quote matches the repository verbatim, every
count matches a fresh recount, every recitation lies outside the diff, and
every changed file is covered. Exit code 1 → the audit is rejected without
further review.

### Evidence failure classification

| Classification | Meaning | Consequence |
|---|---|---|
| DIFF_ONLY_AUDIT | Ledger missing or empty — the auditor reviewed only the diff | Audit rejected; resubmission required; record in `docs/audit_gate/CHANGELOG.md` |
| AUDIT_EVIDENCE_MISMATCH | A quote, count, or line number does not match repository reality (fabrication or stale read) | Audit rejected in full — one mismatch invalidates all other findings; record in `docs/audit_gate/CHANGELOG.md` |

Repeated `DIFF_ONLY_AUDIT` or `AUDIT_EVIDENCE_MISMATCH` from the same auditor
triggers `docs/audit_gate/PULLBACK_PROMPT.md`.

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

## Generated content verification

For any PR that changes README.md, docs, or status blocks, apply the following checks:

| Check | Required action |
|---|---|
| README status block or other doc section is generated by a script | Identify the generator script and its execution path |
| Generator script is outdated vs. current state | Treat as scope-out; REQUEST CHANGES unless the PR explicitly updates the generator |
| Hand-updated generated file without updating the generator | REQUEST CHANGES — generator must also be updated; hand edits will be overwritten on next run |
| docs-only PR updates a generated file | docs-only claim is valid only if the generator is also updated to produce the same output |
| "未実行" / "Not yet executed" / "success済み" / "準備済み" / "merge済み" / "禁止" / "許可" in docs | Verify against primary evidence: `data/api_usage_ledger.json`, `data/genome.json`, GitHub CI run logs |
| "Gemini API live call 未実行" / "paid-credit run 未実行" / "Gemini API first live call" in docs | Verify against `data/api_usage_ledger.json` — past call records may exist for earlier model IDs |
| PR body states "docs-only" | Verify changed files list; generator script (`scripts/update_readme.py`) changes are acceptable in generator maintenance PRs and do not violate a docs-only constraint |

---

## PR completion documentation / history gate

Before marking any PR complete or merge-ready, verify whether the PR requires updates to repository-facing documentation or history.

This gate is mandatory for every PR, including code-only, test-only, and docs-only PRs. If an item is not updated, the audit response or PR body must state why it is not required.

| Area | Required question |
|---|---|
| README | Does `README.md` need a status block, architecture, usage, or file-list update? If no, state why. |
| docs | Do any `docs/**` files need runbook, design, phase, or audit-gate updates? If no, state why. |
| changelog / history docs | Does `docs/audit_gate/CHANGELOG.md` or another changelog/history document need a lesson or status entry? If no, state why. |
| generator scripts | If README/status output is generated, does `scripts/update_readme.py` or another generator need updating? If no, state why. |
| data history / ledger | Does `data/evolution_history.json`, `data/api_usage_ledger.json`, or another data-history file need updating? If no, state why. |

A PR is not complete until this gate is explicitly checked.

---

## Self-report rule

PR bodies and Claude Code reports are self-reports. They must be verified
against GitHub state, current head SHA, diff, CI logs, and real files.
If the PR body contradicts the current diff, trust the diff.

---

## GPT pre-prompt failure rule

Codex Review is a supplemental signal, not the auditor.

When Codex finds a valid issue inside the declared PR scope, classify it during audit as one of:

| Classification | Meaning |
|---|---|
| GPT_PRE_PROMPT_FAILURE | GPT's task prompt should have included this edge case or invariant. |
| IMPLEMENTATION_AGENT_FAILURE | The prompt contained the requirement but the implementation agent failed to follow it. |
| INTENTIONAL_DEFERRED_SCOPE | The issue was explicitly deferred by the Project Owner before implementation. |
| OUT_OF_SCOPE_NEW_FINDING | The issue is valid but outside the declared PR scope. |
| UNAVAILABLE_INFORMATION | The issue depended on information not available before implementation. |

If the classification is `GPT_PRE_PROMPT_FAILURE`, the next task prompt must include a stronger adversarial matrix and must not be released unless it self-scores 98/100 or higher under `TASK_PROMPT_PROTOCOL.md`.

Do not treat repeated valid Codex P2 findings as normal workflow. They indicate a prompt-design or audit-design failure unless clearly classified otherwise.

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
- Audit Evidence Ledger attached (pre-diff spec recitation, call-site evidence, ≥2 negative evidence, read manifest)
- `scripts/validate_audit_evidence.py` passes for the report at the current head SHA
- Current PR state checked
- Current head SHA checked and stated
- Current diff checked
- Current CI for current head SHA checked
- Failed/skipped steps checked
- All Codex comments, reactions, and threads checked
- Unresolved thread status checked
- Scope drift checked
- Secret/API/Phase-3 wording checked
- Documentation / history gate checked
- Real file content checked where needed
- Stale PR body discarded where contradicted by diff
- Valid Codex findings, if any, are classified under the GPT pre-prompt failure rule.

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

3. Audit Evidence Ledger
   [audit-evidence blocks: SPEC_RECITATION per modified file,
    CALLSITE per changed symbol, NEGATIVE x2+, READ_MANIFEST]

4. Findings
   [Finding format below]

5. Documentation / history gate
   README:
   docs:
   changelog / history docs:
   generator scripts:
   data history / ledger:

6. Merge decision
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
