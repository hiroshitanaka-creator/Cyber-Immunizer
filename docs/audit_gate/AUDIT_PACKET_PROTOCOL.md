<!--
AI_DOC_META
status: CANONICAL
scope: Machine audit gate — Audit Packet collection, normalization, and policy-engine evaluation that decides whether an APPROVE verdict is even allowed.
use_for:
  - building an Audit Packet for a PR before any LLM audit verdict
  - running the policy engine to compute machine_verdict / approve_allowed
  - understanding the machine_facts vs judgment_inputs trust boundary
do_not_use_for:
  - constructing the Audit Evidence Ledger itself (see PR_AUDIT_PROTOCOL.md)
  - implementation task prompt construction (see TASK_PROMPT_PROTOCOL.md)
related:
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - schemas/gpt_audit_packet.schema.json
  - scripts/build_audit_packet.py
  - scripts/audit_policy_engine.py
  - scripts/validate_audit_evidence.py
  - .github/workflows/gpt-audit-gate.yml
  - CLAUDE.md
last_reviewed: 2026-06-10
AI_DOC_META_END
-->
# Audit Packet Protocol — Machine Audit Gate

The LLM auditor does not decide whether APPROVE is possible. A script collects
the primary evidence, a script normalizes it, and a script computes whether an
APPROVE verdict is allowed. The LLM may only emit APPROVE when the policy
engine exits 0; an APPROVE emitted under any other condition is invalid.

This is layer 0 of the three-layer audit defense:

| Layer | Role | Tooling |
|---|---|---|
| 0. Machine audit gate (this protocol) | Collect machine facts; compute whether APPROVE is allowed | `scripts/build_audit_packet.py` + `scripts/audit_policy_engine.py` |
| 1. Audit Evidence Ledger | Prove the auditor read beyond the diff (verbatim, machine-verified) | `scripts/validate_audit_evidence.py` (see `PR_AUDIT_PROTOCOL.md`) |
| 2. Reception gate | Receiving side re-verifies everything before presenting to the Project Owner | `CLAUDE.md` 監査受信ゲート (12 items) |

---

## Trust boundary: machine_facts vs judgment_inputs

The packet (`schemas/gpt_audit_packet.schema.json`) has exactly two compartments:

| Compartment | Written by | Trusted how |
|---|---|---|
| `machine_facts` | `scripts/build_audit_packet.py` only (GitHub API / repository files) | Directly — it was produced by script, not by an LLM |
| `judgment_inputs` | The LLM auditor, after the collector emits them as null | Only via evidence: a claim counts when its `evidence_report` passes `scripts/validate_audit_evidence.py`, re-run by the policy engine itself |

Hard rules that keep self-reports from being laundered into machine evidence:

1. **The collector always emits `judgment_inputs` as null skeletons.** It also
   discards any judgment data found in its raw inputs. There is no collection
   path by which an LLM claim enters the packet looking machine-made.
2. **A bare `"claim": true` is a HOLD reason, not an approval input.** The
   policy engine honors a claim only when `claimed_by` is set and the
   referenced `evidence_report` passes the evidence validator at evaluation
   time. The engine never trusts a recorded "validation passed" assertion —
   it re-runs the validator.
3. **Semantic judgments stay out of `machine_facts`.** Fields like "the task's
   100-point conditions are met" are not machine-computable; they live in
   `judgment_inputs` and are gated by evidence. Machine-computable facts
   (head SHA, CI, threads, frozen paths, SSOT token match) never appear in
   `judgment_inputs`.

The defined judgment keys (fixed set; unknown keys invalidate the packet):

| Key | Meaning |
|---|---|
| `task_conditions_met` | The task prompt's completion conditions are satisfied |
| `scope_semantics_ok` | Scope-in/scope-out review found no unauthorized drift |
| `code_findings_resolved` | All valid code findings are resolved or classified |

---

## machine_facts contents

| Field | Source | Notes |
|---|---|---|
| `pr.*` (number, state, merged, draft, base/head ref+SHA, changed_files) | GitHub REST API | head SHA is collected, never transcribed by the auditor |
| `ci.classification` | check runs for the head SHA | `SUCCESS` / `FAILURE` / `PENDING` / `NOT_TRIGGERED`; unknown conclusions classify as `FAILURE` (fail closed); names in `ci.excluded_checks` (e.g. the gate's own run) are dropped before classification |
| `review_threads.*` | GitHub GraphQL `reviewThreads` | unresolved = not resolved AND not outdated; `P1`/`P2` tokens detected by word-boundary regex on the first comment |
| `frozen_paths.touched` | changed files × frozen prefixes (`core/`, `scripts/`, `.github/`, `data/`, `tests/` — mirrors `CLAUDE.md`) | touching is a fact; whether it blocks is policy (`--allow-frozen`); **rename sources count** — `previous_path` of renamed files is checked so moving a file out of a frozen directory cannot evade detection |
| `ssot.*` | `data/project_state.json` + `docs/PROJECT_STATE.md` | consistent = `state_id` exists and appears verbatim in the md (missing files → inconsistent, fail closed) |

---

## Policy engine rules

`scripts/audit_policy_engine.py` computes `machine_verdict`:

| Verdict | Exit code | Meaning |
|---|---|---|
| `APPROVE_ALLOWED` | 0 | The LLM auditor may emit APPROVE (it is still not required to) |
| `HOLD` | 1 | APPROVE is forbidden; reasons listed |
| `PACKET_INVALID` | 2 | The packet is structurally broken; the audit cannot proceed |

`APPROVE_ALLOWED` requires ALL of:

- `pr.state == open`, not merged, not draft
- `--current-head-sha` supplied AND equal to `pr.head_sha` (freshness lock;
  omitting the flag is itself a HOLD reason — an unverified packet may be stale)
- `ci.classification == SUCCESS` and the CI result is for the packet head SHA
- `review_threads.unresolved == 0` and `unresolved_p1_p2 == 0`
- every frozen path touched is covered by an explicit `--allow-frozen` prefix
  granted by the Project Owner (from the task prompt's ALLOWED section)
- `ssot.consistent == true`
- every judgment input: `claim == true`, `claimed_by` set, and its
  `evidence_report` passes `scripts/validate_audit_evidence.py` (re-run by the
  engine, with `--base-ref` passed through)

---

## Usage

```bash
# 1. Collect (requires GITHUB_TOKEN; or --from-raw for injected inputs)
python scripts/build_audit_packet.py \
    --github hiroshitanaka-creator/Cyber-Immunizer --pr <N> --out packet.json

# 2. The LLM auditor fills judgment_inputs in packet.json, with each claim
#    referencing an evidence-ledger report (see PR_AUDIT_PROTOCOL.md).

# 3. Evaluate
python scripts/audit_policy_engine.py --packet packet.json \
    --current-head-sha <fresh head SHA> --base-ref origin/main \
    [--allow-frozen <owner-approved prefix>] --json
```

Where the packet is built matters: a packet built by an LLM-controlled process
can be fabricated. The authoritative packet is built in CI by
`.github/workflows/gpt-audit-gate.yml` on every pull_request event (opened /
reopened / synchronize / ready_for_review) and uploaded as the
`gpt-audit-packet-<head SHA>` artifact.

**Snapshot semantics**: CI status and review threads are time-varying, so the
CI-built artifact is an at-build-time snapshot (sibling checks may still be
pending while the gate runs; the gate excludes its own still-running check via
`--exclude-check gpt-audit-gate`, recorded in `ci.excluded_checks`). For the
full-mode reception evaluation, the receiving side (Claude) builds a **fresh
packet at evaluation time** with the same script and uses the CI artifact as
the immutable record that collection ran in CI, cross-checking the two where
they should agree (head SHA, changed files, frozen touches, SSOT).

---

## CI gate vs full mode — enforcement division

The CI required check runs the engine with `--mode ci-gate`, which blocks only
on rules that are deterministic at CI time. A green `gpt-audit-gate` check
means `CI_GATE_PASS` — it is **never** approval permission (`approve_allowed`
is always false in ci-gate output; verdict vocabularies do not overlap).

| Rule | ci-gate (CI required check) | full (reception gate) | Why the split |
|---|---|---|---|
| Packet structure valid | blocking | blocking | deterministic |
| PR open / not merged | blocking | blocking | deterministic |
| head-SHA freshness | blocking | blocking | CI re-runs on synchronize, so the packet always tracks the head |
| SSOT consistency | blocking | blocking | repository-state fact at the audited SHA |
| CI status of sibling checks | warning | blocking | circular at CI time (this gate is itself a check; siblings may be pending) |
| Unresolved threads / P1-P2 | warning | blocking | resolving a thread does not re-trigger pull_request events; enforced live by branch protection "Require conversation resolution" |
| Frozen-path allowance | warning | blocking (`--allow-frozen`) | the Owner's allowance lives in the task prompt, unknown to CI |
| Judgment inputs + evidence | warning | blocking | filled by the auditor after collection |

### Branch protection (Project Owner — GitHub Settings, manual, zero code)

The gate becomes physically merge-blocking only with these repository settings
(Settings → Branches → branch protection rule for `main`):

1. **Require status checks to pass before merging** → add **`gpt-audit-gate`**
   (and the existing CI check) as required.
2. **Require conversation resolution before merging** → ON. This enforces the
   unresolved-thread rule live, with zero code, at the exact moment of merge.

---

## Failure handling

| Situation | Handling |
|---|---|
| Collector cannot reach the GitHub API / token missing | Build fails (exit 2). No packet means no audit — do not hand-write a packet |
| Packet edited to add unknown judgment keys | `PACKET_INVALID` |
| Judgment claim without evidence, or evidence fails validation | `HOLD` with reason; resubmission follows the `DIFF_ONLY_AUDIT` / `AUDIT_EVIDENCE_MISMATCH` classification in `PR_AUDIT_PROTOCOL.md` |
| Machine HOLD that the Project Owner decides to override (e.g. intentional frozen-path PR) | The Owner merges manually; the engine is a gate for LLM verdicts, not for the Owner |
