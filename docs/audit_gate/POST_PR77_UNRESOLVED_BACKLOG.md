<!--
AI_DOC_META
status: DRAFT-INVENTORY
scope: Post-PR77 unresolved backlog inventory. No implementation authority.
last_reviewed: 2026-06-07
AI_DOC_META_END
-->
# Post-PR77 Unresolved Backlog Inventory

> This document is a factual, source-evidence-based inventory of unresolved work
> after PR #77. It carries **no implementation authority**. It does not change
> runtime, validator, tests, workflows, or model configuration. Every backlog
> item below cites a concrete source file and excerpt verified against the repo
> at the head SHA recorded below.

## Verified repository state

Verified read-only on 2026-06-07 from local Git and the GitHub API.

- **main latest commit:** `1da801876f6c3e866f025d018e78af18263c3924`
  - `1da8018 Merge pull request #77 from hiroshitanaka-creator/claude/post-pr76-cleanup-grok-removal-yI1E0`
  - This matches the PR #77 merge commit observed at prompt creation.
- **PR #72 state:** MERGED — `feat(audit-gate): add thread handoff protocol for session continuation` (merged 2026-06-05, `merged_by: hiroshitanaka-creator`).
- **PR #73 state:** MERGED — X-007 check 11 implementation (`971c901 Merge pull request #73 from hiroshitanaka-creator/claude/x007-static-value-checks-G0kj4`).
- **PR #76 state:** MERGED — README / CLAUDE.md stale state cleanup (`c1f0bd1 Merge pull request #76 ...`).
- **PR #77 state:** MERGED — `docs(audit): clean post-PR76 X-007 state and remove Grok skill files` (merged 2026-06-07T12:39:07Z, `merged: true`, `merged_by: hiroshitanaka-creator`). Changed 6 files, +171 / −532.
- **Open PRs:** none (`list_pull_requests state=open` returned `[]`).
- **Active `.grok/**` files:** none. `find .grok -type f` returns no directory; `git grep "\.grok"` shows only historical/record references (POST_PR76 inventory, TASK_REPORT_PR77).

> ⚠️ **State-table drift found during inventory (see Backlog P0 item).**
> `CLAUDE.md` "現在の状態" table states `Phase 2.5 完了 / Phase 3 Go-No-Go 待ち`
> and `Gemini API 未接続（Phase 3 activation 待ち）`. The canonical
> `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` (last_reviewed 2026-06-03) records that
> Phase 3 activation PRs #58–#62 are **merged**, `live_model_enabled=true`, and
> past paid-credit API call records exist. The two control-plane docs disagree
> about current Phase state.

## Source Evidence

### X-007 / check 11 state

`docs/audit_gate/POST_PR76_STATE_INVENTORY.md:15-21`
```
| PR #72 | thread handoff protocol — merged |
| PR #73 | X-007 check 11 implementation — merged |
| PR #76 | README / CLAUDE.md stale state cleanup — merged |
| X-007 check 11 | implemented in `scripts/propose_mutation.py` |
| Current validator | checks 1–11 |
| Category B dynamic expressions | deferred; not statically rejected |
| Category D runtime gap | known residual; runtime hardening not implemented |
```

`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:275-279`
```
| **Check 11 (PR #73, X-007)** | **Safe-subset literal type/value rejection** | **Dynamic expression correctness (deferred)** |

> **Check 11 is not implemented in PR #69 because PR #69 was docs-only.**
> Check 11 was implemented later in PR #73.
> The current validator implements checks 1–11.
```

PR #77 body (GitHub, `merged: true`): "Removed Grok review skill files under `.grok/**`; no Grok replacement added. Added `docs/audit_gate/POST_PR76_STATE_INVENTORY.md` as factual state record." → confirms PR #77 = X-007 spec cleanup + Grok skill removal + state inventory. The Project-Owner-override task-report rule was added in commit `aff3739 chore(workflow): add task completion report rule and PR77 report file` (part of PR #77).

**Conclusion:** check 11 (X-007 Category A literal rejection) is implemented and merged; validator is at checks 1–11; `.grok/**` active files are absent. No unresolved work remains *inside* X-007 check 11 itself.

### Category D runtime gap

`core/types.py:38-48` — canonical contract the runtime should satisfy:
```
@dataclass(frozen=True)
class DetectionResult:
    blocked: bool
    reason: str
    confidence: float  # [0.0, 1.0]
    matched_signals: tuple[str, ...]
```

`core/fitness.py:143-159` — what runtime actually validates (`_contract_ok`):
```
def _contract_ok(module: Any) -> tuple[bool, str]:
    if not hasattr(module, "inspect_request"):
        return False, "inspect_request not found"
    fn = module.inspect_request
    if not callable(fn):
        return False, "inspect_request is not callable"
    dummy = Request(method="GET", path="/", query={}, headers={}, body="")
    try:
        result = fn(dummy)
    except Exception as exc:
        return False, f"inspect_request raised on smoke test: {exc}"
    if not isinstance(result, DetectionResult):
        return False, f"inspect_request returned {type(result)!r}, not DetectionResult"
    if not (0.0 <= result.confidence <= 1.0):
        return False, f"confidence={result.confidence} out of [0.0, 1.0]"
    return True, ""
```

Classification:
- **What `_contract_ok` checks:** `inspect_request` exists; is callable; does not raise on a smoke-test request; returns a `DetectionResult` instance; `confidence` is within `[0.0, 1.0]`.
- **What it does NOT check:** that `blocked` is a `bool`, that `reason` is a `str`, and that `matched_signals` elements are all `str`. These field types are **not** enforced at runtime.
- **`blocked` / `reason` / `matched_signals` type enforcement is missing** at runtime — confirmed by the absence of any `isinstance` check for those three fields in `_contract_ok`.

`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:258-262` (Scope-Out) confirms this is a **known residual gap** and is **Project Owner-overridable**:
```
- Runtime contract checks for `blocked` (must be `bool`), `reason` (must be `str`), and
  `matched_signals` element types in `core/fitness.py::_contract_ok`. The current contract
  check verifies only `DetectionResult` instance and `confidence` range; extending it to
  enforce the other field types at runtime would close the Category D residual gap but is a
  runtime change outside the X-007 AST-only static scope.
```

`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:188-192` records why the gap is accepted (AST-only safe subset; "deferred" ≠ "guaranteed valid at runtime"; tightening is "a separate, Project Owner-overridable item").

**Conclusion:** Category D is a known, documented residual runtime gap. Closing it is a `core/fitness.py` runtime change → **RUNTIME_HARDENING**, and it is explicitly Project-Owner-overridable. Per CLAUDE.md (`core/**` FROZEN) and the prompt FORBIDDEN list, design may proceed but **implementation requires Project Owner approval**.

### Phase 3 paid-credit readiness

`docs/PHASE_3_GO_NO_GO_CHECKLIST.md:84-97`
```
> **Phase 3 activation PR は main に merge 済み。**
> **paid-credit path 準備完了。過去の paid-credit API call 記録は存在する ...
>   gemini-3-flash-preview での controlled run は未実行。**

| Phase 3 activation PRs | ✅ #58, #59, #60, #61, #62 — all merged into main |
| `live_model_enabled` | `true` (PR #58) |
| Primary model | `gemini-3-flash-preview` (PR #62) |
| Gemini 3 Flash Preview controlled run | **Not yet executed** — ... |
| `promote_approved` | `false` — prohibited until first run result reviewed |
```

Next Project Owner steps are documented at `docs/PHASE_3_GO_NO_GO_CHECKLIST.md:109-116` (run `workflow_dispatch` mode `gemini-paid-credit` once, `promote_approved=false`, review ledger/candidate/apply/evaluate, then decide promote/fix/halt).

Gates before a paid-credit run — `docs/PHASE_3_GO_NO_GO_CHECKLIST.md:154-191` (Project Owner external checks: GitHub Secrets `GEMINI_API_KEY`, billing, budget caps, alerts, max cost/request acceptance, monitoring) and No-Go conditions (CI green on head SHA, no unresolved Codex thread, GPT Audit Gate review, etc.). `docs/PHASE_3_GO_NO_GO_CHECKLIST.md:232-240` requires an explicit Project Owner "GO" via the Next-Step Gate before proceeding.

Workflow facts (`.github/workflows/immunization_loop.yml`): `gemini-paid-credit` runs only on `workflow_dispatch` (line 113-118 refuse outside main), `GEMINI_API_KEY` scoped to the propose job only, `promote_approved == 'true'` gate at line 477-478. `ci.yml` has `GEMINI_API_KEY` intentionally absent (line 29).

**Conclusion:** The first **gemini-3-flash-preview controlled** paid-credit run is still pending. This is a **PAID_CREDIT_OPERATION** requiring Project Owner manual action (**YES_BEFORE_RUN**). No docs change is *required* to run, but the stale `CLAUDE.md`/`README.md` Phase-state wording (see P0) should be corrected first so control-plane docs do not contradict the readiness checklist. **This inventory does not run the workflow.**

### X-002 / X-003 / X-006 policy alignment

`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:263`
```
- X-002 / X-003 / X-006 policy alignment — these remain separate policy items.
```
(under the `## Scope-Out Items After PR #73 (Project Owner-Overridable)` heading, line 251)

`docs/audit_gate/CHANGELOG.md:263-267`
```
- **X-002 / X-003 / X-006 / X-007 remain Project Owner-overridable
  recommendations**: These policy extension items remain deferred. X-007
  excludes only type/value-range static checks; H-3 argument count/keyword-name
  validation is completed by PR #67. Protocol records this to prevent future
  agents from reopening H-3 scope or conflating it with X-007.
```

`README.md:820`
```
> PR #73 で Category A obvious invalid literal rejection（check 11）を実装済み。X-002/X-003/X-006 policy alignment は Project Owner-overridable 推奨事項として保留。
```

**Conclusion:** X-002 / X-003 / X-006 are still **unresolved** and are recorded as **policy/design items** (not implementation tasks), explicitly deferred and Project-Owner-overridable. Source records: the X-007 spec Scope-Out section, the audit-gate CHANGELOG, and README. **Risk if ignored:** the three items remain undefined in concrete validator terms; a future agent could either silently re-open them as unscoped implementation (scope creep, the exact failure the CHANGELOG warns against) or conflate them with H-3/X-007. The safe step is a **policy-alignment inventory** that defines each item before any implementation is considered.

### Audit workflow after Grok removal

`docs/AUDIT_CHARTER.md:30-37` — role table references only Project Owner / GPT Audit Gate / Claude Code; **no Grok**:
```
| **Project Owner** | hiroshitanaka-creator | 最終マージ判断 ... |
| **GPT Audit Gate** | GPT 系監査モデル ... | 6カテゴリの構造的レビュー・APPROVE/REQUEST CHANGES/BLOCK の推薦 |
| **Claude Code** | Claude Code 実装環境 ... | 実装・テスト作成・コミット・PR準備・Audit Gateへの情報提供 |
```

`docs/audit_gate/PR_AUDIT_PROTOCOL.md:153` — Codex remains the supplementary diff-level reviewer:
```
Codex Review is a supplemental signal, not the auditor.
```

`docs/audit_gate/POST_PR76_STATE_INVENTORY.md:28-30,44` — `.grok/**` skill files removed; "No new Grok protocol replacement." Remaining Grok mentions are historical: `docs/PHASE_2_5_CLOSEOUT_AUDIT.md:41,127` label Grok as "supporting evidence only" (not an active workflow step).

**Conclusion:**
- **Does any active workflow still reference Grok?** No. The only remaining mentions are historical/supporting-evidence labels and removal records.
- **Codex Review remains as supplementary diff-level reviewer?** Yes (`PR_AUDIT_PROTOCOL.md:153`).
- **GPT Audit Gate remains final merge decision integrator?** Yes; Project Owner holds final authority (`AUDIT_CHARTER.md:20-24,32-33`).
- **Gap after `.grok/**` removal needing a docs-only clarification PR?** No functional gap. Codex (supplemental) + GPT Audit Gate (integrator) + Project Owner (final) remains a complete chain. At most an *optional* one-line note could record that Grok is no longer part of the workflow, but this is not required — it is already implied by the POST_PR76 inventory.

## Backlog table

| Priority | Item | Type | Current status | Source evidence | Owner approval required? | Recommended next action |
|---|---|---|---|---|---|---|
| P0 | Stale Phase-3 state in `CLAUDE.md` "現在の状態" table (and README references) contradicts `PHASE_3_GO_NO_GO_CHECKLIST.md` (says API 未接続 / Go-No-Go 待ち, but #58–#62 merged & `live_model_enabled=true`) | DOCS_CONTROL_PLANE | Unresolved — active contradiction read at every session start | `CLAUDE.md` 現在の状態 table vs `docs/PHASE_3_GO_NO_GO_CHECKLIST.md:29-31,84-97` | NO — safe docs/control-plane cleanup | DO_NEXT |
| P1 | Category D runtime contract gap: `_contract_ok` does not enforce `blocked: bool`, `reason: str`, `matched_signals: tuple[str,...]` | RUNTIME_HARDENING | Unresolved — known, documented residual gap; design only first | `core/fitness.py:143-159`; `core/types.py:38-48`; `REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:258-262` | YES_BEFORE_IMPLEMENTATION — design may proceed; `core/**` edit needs Project Owner approval | DESIGN_ONLY |
| P1 | Phase 3 first **gemini-3-flash-preview controlled** paid-credit run | PAID_CREDIT_OPERATION | Unresolved — path ready, run not executed; `promote_approved=false` | `docs/PHASE_3_GO_NO_GO_CHECKLIST.md:84-97,109-116,154-191,232-240` | YES_BEFORE_RUN — Project Owner manual `workflow_dispatch` + external gates | WAIT |
| P2 | X-002 / X-003 / X-006 policy alignment | POLICY_ALIGNMENT | Unresolved — deferred policy items, not yet concretely defined | `REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md:263`; `docs/audit_gate/CHANGELOG.md:263-267`; `README.md:820` | YES_BEFORE_IMPLEMENTATION — policy/design inventory may proceed; implementation needs approval | DESIGN_ONLY |
| P2 | Optional docs note that Grok is no longer part of the audit workflow | AUDIT_WORKFLOW | No functional gap; Codex + GPT Audit Gate + Project Owner is complete | `docs/AUDIT_CHARTER.md:30-37`; `PR_AUDIT_PROTOCOL.md:153`; `POST_PR76_STATE_INVENTORY.md:28-44` | NO — optional safe docs note | DO_NOT_TOUCH (no action needed; fold into P0 only if a doc is already being edited) |

## Recommended next PR

State exactly one recommended next PR.

- **Title:** `docs(state): correct stale Phase-3 status in CLAUDE.md and README to match Go/No-Go checklist`
- **Scope:** Docs/control-plane only. Update the `CLAUDE.md` "現在の状態" table (and any README state references) so they reflect the canonical `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` state: Phase 3 activation PRs #58–#62 merged, `live_model_enabled=true`, past paid-credit records exist, and the `gemini-3-flash-preview` controlled run is the pending next step. No factual claim beyond what the Go/No-Go checklist already records.
- **Files allowed:** `CLAUDE.md`, `README.md` (state/status wording only), and optionally the new `docs/audit_gate/POST_PR77_UNRESOLVED_BACKLOG.md` as the cited source.
- **Files forbidden:** `scripts/**`, `core/**`, `tests/**`, `.github/**`, `data/**`, ledger files, `data/genome.json`, validator logic, fitness logic, model names/budgets/prompt text.
- **Why this first:** It is the lowest-risk, no-Owner-approval-required action, and it removes an **active contradiction** between two control-plane documents that every AI session reads at startup (`CLAUDE.md` is the mandated first read). Leaving it stale risks a future agent acting on wrong Phase-3 state (e.g., treating API as "未接続" when `live_model_enabled` is already `true`).
- **Why not the alternatives:**
  - *Category D runtime hardening (P1):* touches `core/fitness.py` (FROZEN) → requires Project Owner approval; correct first step is a DESIGN_ONLY spike, not an immediate code PR.
  - *Phase 3 controlled paid-credit run (P1):* not a PR at all — it is a Project Owner manual `workflow_dispatch` operation gated by external billing/secret checks (YES_BEFORE_RUN); also depends on the P0 state correction landing first.
  - *X-002/X-003/X-006 policy alignment (P2):* design/policy inventory only; lower urgency and no active contradiction, so it can follow.
  - *Grok audit-workflow note (P2):* no functional gap exists; not worth a standalone PR.

## Explicit non-goals

- No runtime hardening in this inventory task.
- No paid-credit workflow run.
- No validator changes.
- No core changes.
- No tests changes.
- No workflow changes.
- No Grok replacement.
