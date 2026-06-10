<!--
AI_DOC_META
status: CANONICAL
scope: Historical record of why each Audit Gate protocol rule was added (protocol lessons, regression prevention).
use_for:
  - checking past protocol lessons before a merge decision
  - recording new protocol lessons (e.g. DIFF_ONLY_AUDIT / AUDIT_EVIDENCE_MISMATCH occurrences)
do_not_use_for:
  - current project state (see docs/PROJECT_STATE.md / data/project_state.json)
related:
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
  - CLAUDE.md
last_reviewed: 2026-06-10
AI_DOC_META_END
-->
# Audit Gate Protocol Changelog

This file records why specific rules were added to the Audit Gate protocols,
keyed to the PR lesson that motivated each addition.

This is not a project status document. Keep entries focused on protocol lessons.

---

## Machine audit gate — machine facts are collected by script; judgment claims cannot be laundered into them

Follow-up to the Audit Evidence Ledger lesson, after reviewing an external proposal
(Evidence Collector / Normalized Evidence Packet / Policy Engine):

- **Machine-computable facts are not the auditor's to report**: head SHA, CI status,
  unresolved review threads, frozen-path touches, and SSOT token consistency are now
  collected by `scripts/build_audit_packet.py` and evaluated by
  `scripts/audit_policy_engine.py`. An LLM transcribing a head SHA was always a
  weaker guarantee than a script fetching it.

- **The packet has a hard trust boundary**: `machine_facts` (script-written, trusted
  directly) vs `judgment_inputs` (LLM claims, trusted only via evidence). The reviewed
  proposal had a single flat `policy_inputs` block where a semantic claim like
  `task_100_point_conditions_met: true` would have sat next to machine facts —
  letting an LLM self-report masquerade as machine evidence. The two-compartment
  design closes that hole: the collector always emits judgment fields as null and
  discards judgment data found in raw inputs, and the policy engine honors a claim
  only when its `evidence_report` passes `scripts/validate_audit_evidence.py`,
  re-run by the engine itself at evaluation time.

- **APPROVE is permission-gated, not self-asserted**: the policy engine computes
  `machine_verdict` (`APPROVE_ALLOWED` / `HOLD` / `PACKET_INVALID`). An LLM APPROVE
  emitted without engine exit 0 for a fresh packet at the current head SHA is invalid
  by protocol. Freshness is fail-closed: omitting `--current-head-sha` is itself a
  HOLD reason.

- **Two Codex P1 findings hardened the collector before merge** (classified
  IMPLEMENTATION_AGENT_FAILURE; both were collector blind spots, not design flaws):
  (1) the gate's own still-running check run would have frozen a self-referential
  `PENDING` into every CI-built packet — the build step now passes
  `--exclude-check gpt-audit-gate`, recorded in `ci.excluded_checks`, and the protocol
  defines CI artifacts as at-build-time snapshots with the reception gate building a
  fresh packet at evaluation time; (2) renamed files only carried the new path, so
  renaming `core/foo.py` out of a frozen directory evaded `frozen_paths.touched` —
  `previous_filename` is now preserved as `changed_files[].previous_path` and rename
  sources count as frozen touches.

- **The authoritative packet is built in CI** (`.github/workflows/gpt-audit-gate.yml`,
  added with explicit Project Owner approval for `.github/**`): a packet built by an
  LLM-controlled process could be fabricated, so the required check builds it from the
  GitHub API on every pull_request event and uploads it as an artifact. The check runs
  the engine in `--mode ci-gate`, which blocks only on CI-decidable rules (structure,
  PR open, head-SHA freshness, SSOT consistency) and reports the rest as warnings —
  blocking on sibling checks would be circular, and thread resolution does not
  re-trigger pull_request events. A green check is verdict `CI_GATE_PASS`, a vocabulary
  deliberately disjoint from `APPROVE_ALLOWED` so a passing gate cannot be cited as
  approval permission. Physical merge-blocking still requires the Project Owner to mark
  `gpt-audit-gate` as a required status check and enable "Require conversation
  resolution before merging" in branch protection (manual GitHub settings).

---

## Audit Evidence Ledger — audits must prove they read beyond the diff; the receiving side verifies mechanically

Lesson driven by a GPT audit that, when questioned, admitted it had reviewed only the diff:

- **"Checked" is not evidence**: The previous protocol required fields like "Real file
  content checked where needed", but execution was self-reported. A diff-only audit could
  produce a perfectly formatted report by writing checkmarks. The protocol now requires an
  **Audit Evidence Ledger** — artifacts that are physically impossible to produce from the
  diff alone (see `PR_AUDIT_PROTOCOL.md` → "Audit Evidence Ledger").

- **Pre-diff spec recitation forces reading order**: Before reviewing the diff, the auditor
  must quote each modified file's core processing (function name + line numbers + verbatim
  lines, all outside the diff hunks) and explain the current spec. This cannot be written
  after-the-fact from the diff alone, so it proves the file was actually opened first.

- **Counts are recomputed, not trusted**: Call-site evidence (`COUNT` of references) and
  negative evidence ("searched for X, found 0") are re-executed by
  `scripts/validate_audit_evidence.py`. A stale or fabricated count fails the audit.

- **One mismatch invalidates the whole audit**: A single quote or count that does not match
  repository reality is classified `AUDIT_EVIDENCE_MISMATCH` and rejects the entire report,
  including otherwise-plausible findings — partial trust in a fabricating auditor is not
  recoverable. A missing/empty ledger is classified `DIFF_ONLY_AUDIT`. Both are recorded in
  this changelog; repetition triggers `PULLBACK_PROMPT.md`.

- **The receiving side runs the validator itself**: Mirroring the Prompt Reception Gate
  lesson below, the auditor's claim that evidence was verified is ignored. `CLAUDE.md`'s
  audit reception gate (now 12 items) requires Claude to execute
  `python scripts/validate_audit_evidence.py --report <report> --base-ref origin/main`
  and gate on its exit code.

---

## Prompt Reception Gate — receiving AI scores incoming prompts; GPT self-score is ignored

Lesson driven by the gap between GPT's self-scoring and actual prompt quality:

- **GPT's 98/100 self-score is unverifiable and gameable**: The self-score threshold in
  `TASK_PROMPT_PROTOCOL.md` was designed to gate GPT's own output. It does not prevent a
  well-formatted but shallow prompt from passing. The receiving AI (Claude, Codex, or any
  other agent) has no obligation to trust or reference the self-score. Protocol now
  explicitly states that the receiving AI ignores the self-score entirely.

- **Receiving AI must apply its own 10-item objective check**: As the repository grows,
  the Project Owner cannot be expected to manually verify every structural requirement in
  a task prompt. `CLAUDE.md` now contains a 10-item reception gate that Claude applies on
  every incoming task prompt before starting work. Each item has a machine-readable
  acceptance criterion (section present / field non-empty / placeholder-free). One missing
  item triggers a structured reject-and-resubmit message to GPT.

- **Separation of roles**: GPT self-scores before output (output gate). Claude checks
  structure on receipt (input gate). These are independent layers — passing one does not
  imply passing the other. The Project Owner's role is to confirm intent, not to audit
  protocol compliance.

- **Rejection message must be structured, not narrative**: A rejection that says
  "this prompt needs more detail" gives GPT no actionable fix. The reception gate
  requires the reject message to name the specific item number and what is missing,
  so GPT can correct exactly the gap without re-submitting a full rewrite.

---

## Thread Handoff Gate — handoff prompts must carry verifiable state, not narrative

Lesson driven by context-loss between threads:

- **Unverified handoffs cause stale-SHA errors and duplicate work**: When work continues
  in a new session, a handoff prompt that carries only narrative ("we fixed the spec, then
  improved the runbook") lets the incoming session act on a stale head SHA, re-implement
  completed work, or violate a constraint the previous session was under. Protocol added:
  `docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md` requires every handoff to carry verifiable
  state (branch, head SHA, PR, CI status, test status) and forbids treating narrative as
  the source of truth.

- **Done means committed**: A described-but-uncommitted change is not "done". Handoff rule:
  every `Done` item must cite a commit SHA or file path; assertion-only completion claims
  are invalid.

- **Incoming session must re-verify before acting**: The protocol requires the incoming
  session to verify branch and head SHA against the repository and stop on mismatch, re-run
  the stated test command, and treat the previous session's hard constraints as binding.
  Trust the repository over the handoff narrative.

---

## Source Evidence Gate — GPT task prompt must include verbatim code citations

Lesson driven by repeated `GPT_PRE_PROMPT_FAILURE` classifications across PR #69:

- **Diff-only and assertion-only investigation produces systematically wrong specs**:
  All three Codex P2 findings in PR #69 (broken runbook link, Category D factual error,
  generator expression allow/defer conflict) shared the same root cause — GPT wrote the
  task prompt and spec from diff inspection or memory without reading the actual source
  files. Protocol now requires every task prompt to include a `Source Evidence` block with
  verbatim code excerpts and `file_path:start_line-end_line` citations for each ALLOWED
  file that affects the change logic.

- **`「確認済み」` / `「reviewed」` without quoted code is invalid evidence**:
  Writing an assertion that a file was read — without pasting actual content — cannot be
  verified by the implementation agent or the auditor. Rule added: assertion-only evidence
  is explicitly forbidden; the task prompt is invalid if Source Evidence is missing or
  assertion-only.

- **Claude Code must verify citations before starting implementation**:
  `docs/AI_ENTRYPOINT.md` now instructs Claude Code to check each Source Evidence citation
  against the actual file before proceeding. If a citation is wrong, Claude Code stops and
  reports the mismatch rather than proceeding on a false foundation.

- **Three P2s on one PR is not normal workflow**:
  Three valid `GPT_PRE_PROMPT_FAILURE` findings in a single PR indicate a structural
  prompt-design failure, not implementation error. The Source Evidence gate is the
  structural fix: GPT cannot claim to have read a file without showing its work.

---

## PR #73 — X-007 check 11 safe-subset implementation

Lessons from implementing Category A static literal rejection:

- **LLM prompt additions are cost-sensitive**: Adding text to `_LLM_SYSTEM_PROMPT` increases
  the estimated input token count, which affects the paid-credit budget gate and cost ledger
  tests. Any `_LLM_SYSTEM_PROMPT` edit must verify that `estimate_cost_usd` stays within the
  existing test threshold (`< $0.005` for the `test_paid_credit_ledger_uses_output_token_cap`
  test). Protocol: measure `len(_LLM_SYSTEM_PROMPT)` before and after; target a net addition
  of no more than ~350 characters to avoid breaking the cost-threshold test.

- **bool is a subclass of int — check order matters**: `isinstance(True, int)` returns `True`
  in Python. Any numeric literal check that runs `isinstance(val, (int, float))` before
  `isinstance(val, bool)` will incorrectly classify `True`/`False` as numeric. The
  `_numeric_literal_value` helper must check `isinstance(val, bool)` first and return `None`
  before checking `isinstance(val, (int, float))`.

- **UnaryOp is the canonical AST for negative literals**: `-0.1` in Python source is parsed
  as `ast.UnaryOp(op=ast.USub(), operand=ast.Constant(0.1))`, not as `ast.Constant(-0.1)`.
  `_numeric_literal_value` must handle `ast.UnaryOp(USub|UAdd, Constant)` to correctly
  classify signed numeric literals without calling eval/compile.

- **Deferred = not statically rejected (not guaranteed valid at runtime)**: Category B
  dynamic expressions are deferred by check 11 because they *may* produce valid values at
  runtime. Deferral does not mean the value is valid; fitness/evaluate remains the runtime
  residual gate for Category B expressions. This distinction prevents future agents from
  claiming check 11 provides stronger guarantees than it does.

- **PR numbering may differ from reserved slots**: PR #70 was consumed by the Source Evidence
  gate redesign; PR #71 by CLAUDE.md. This implementation is PR #73, not PR #70.
  Task prompts must use "PR #N相当" rather than hard-coding expected PR numbers.

- **Finite reject-lists create recurring P2s; field-domain allowlists do not**: The original
  check 11 implementation rejected a known set of invalid constants (bool/None/int/float for
  `reason`; str/None/int/float for `confidence`; etc.) and deferred everything else. This left
  non-enumerated constants such as `bytes`, `Ellipsis`, and `complex` silently accepted or
  deferred even though they are unambiguously wrong for every field. Each gap became a Codex P2.
  The fix is to invert the logic: define what is *accepted* for each field (the allowlist), and
  reject every other obvious AST literal form. The rule is: for each field, accept only the
  literal domain defined by the field's type (`bool` for `blocked`, `str` for `reason`,
  `float` in `[0.0, 1.0]` for `confidence`, `tuple[str, ...]` for `matched_signals`); reject
  everything else that is obviously a literal; defer everything that is not obviously a literal.

- **`_is_unary_constant` closes the UnaryOp-over-any-Constant gap**: The previous
  `_numeric_literal_value` helper handled only `UnaryOp(USub|UAdd, Constant(int|float))`.
  Non-numeric Constant operands (bool, bytes, str, Ellipsis) returned `None` and were deferred.
  Adding `_is_unary_constant(node)` — which returns `True` for `UnaryOp(USub|UAdd, Constant(...))`
  regardless of the constant type — allows `blocked`, `reason`, and `matched_signals` to reject
  all obvious unary-constant expressions without special-casing by constant type.

---

## PR #69 — Static value checks require a docs-first freeze before implementation

Lessons that drove the docs-first freeze decision:

- **Obvious invalid literals and valid dynamic expressions must be separated before
  implementation**: X-007 (type/value-range static checks for `DetectionResult` fields)
  can easily over-reject valid detector logic if implemented without a frozen policy.
  For example, `confidence=min(1.0, score)` and `matched_signals=tuple(matched)` are
  dynamic expressions that produce valid values at runtime but cannot be proved correct
  by AST-only static analysis. A validator that rejects these would break well-formed
  detectors on the first paid-credit run. Protocol now requires a docs-first freeze
  before any implementation of static value-range checks.

- **H-3 and X-007 are orthogonal; conflating them causes scope creep**: Check 10 (H-3,
  PR #67) validates argument count and keyword names. It explicitly does not validate
  types or value ranges. X-007 is the separate, deferred item for type/value-range checks.
  Any agent that re-opens check 10 to add type checks is conflating H-3 with X-007 scope.
  Protocol now records the boundary explicitly: check 10 is complete; X-007 starts at
  check 11 in PR #70.

- **The safe-subset rule is the governing principle for AST-only static checks**: Static
  checks must only reject what is obviously wrong as an AST literal. If a value could be
  correct at runtime via a dynamic expression, the check must defer to fitness/evaluate.
  "When in doubt, defer" is the safety invariant. This prevents false-positive rejections
  that would cause the validator to fail-close on legitimate Gemini outputs.

- **Four-category taxonomy freezes the PR #70 contract**: PR #69 defines four categories
  (A: safe to reject, B: must allow/defer, C: AST-only constraint, D: fitness/runtime
  responsibility) and a 31-case adversarial test matrix. PR #70 must satisfy all Category B
  allow/defer cases and all Category A reject cases before implementation is complete.
  Protocol now requires this matrix to be verified before PR #70 merges.

- **`data/history/ledger` must not be touched in docs-only PRs**: PR #69 is docs-only.
  `data/evolution_history.json` and `data/api_usage_ledger.json` must remain unchanged.
  Protocol now records that docs-freeze PRs have no data impact.

---

## PR #68 — Task Prompt Gate v2 / Codex pre-emption requirement

Lessons that drove protocol additions:

- **Codex Review is supplemental, not the auditor**: Valid PR-scope Codex P2
  findings during PR #67 showed that GPT task prompts were not sufficiently
  adversarial. Codex must not be relied on to discover predictable edge cases.
- **Diff-only prompt creation is insufficient**: Task prompts must be grounded
  in canonical source files, current implementation, downstream behavior,
  tests, docs, and history gates.
- **Adversarial validation matrix is mandatory**: Validator/schema/policy tasks
  must include missing, extra, wrong, duplicate, positional, kwargs,
  return/non-return, assignment, nested, and parse-vs-runtime cases where
  applicable.
- **Self-score gate added**: GPT must self-score every implementation task
  prompt and may only output it at 98/100 or higher. Below threshold, GPT must
  stop and report missing evidence.
- **Valid Codex P2 means prompt-design failure unless classified otherwise**:
  Future PR audits must classify valid Codex findings as
  GPT_PRE_PROMPT_FAILURE, IMPLEMENTATION_AGENT_FAILURE,
  INTENTIONAL_DEFERRED_SCOPE, OUT_OF_SCOPE_NEW_FINDING, or
  UNAVAILABLE_INFORMATION.

---

## PR #67 — Direct constructor call ≠ valid constructor argument shape

Lessons that drove protocol additions:

- **Check 8 proves form, not shape**: Check 8 of `_validate_replacement_code`
  verifies that every `return` statement returns `DetectionResult(...)` (an
  `ast.Call` with `func.id == "DetectionResult"`). It does not inspect
  `call.args`, `call.keywords`, or keyword names. A call such as
  `DetectionResult(True, "x", 0.5, ())` or `DetectionResult(blocked=True,
  reason="x")` passes check 8 and would fail at runtime against the dataclass
  constructor. Protocol now requires check 10: zero positional args, no
  `**kwargs`, exactly the four canonical keyword names.

- **Canonical keyword names are a static contract**: The four keyword names
  (`blocked`, `reason`, `confidence`, `matched_signals`) are a static contract
  derived from `core/types.py`. An LLM that generates code with missing,
  extra, or renamed keyword arguments produces code that will raise `TypeError`
  at runtime. Validating keyword names statically (before any paid-credit run)
  is both feasible and fail-closed. Protocol now records this as H-3 argument
  count/keyword-name validation, completed in PR #67.

- **H-3 is not X-007**: H-3 (argument count / keyword-name validation) and
  X-007 (type/value-range static checks) are orthogonal. Check 10 validates
  that the required keyword arguments are present and correctly named; it does
  not check that `blocked` is a literal `bool`, that `confidence` is in
  `[0.0, 1.0]`, or that `matched_signals` is a tuple. Those type/value-range
  checks remain deferred as X-007 in PR #68+. Protocol now records this
  distinction explicitly to prevent future agents from conflating the two.

- **Prompt and validator must stay in sync (continued)**: When check 10 was
  added, `_LLM_SYSTEM_PROMPT` rule 10 and the FORBIDDEN section were updated
  in the same PR to reflect keyword-only requirement and explicitly list
  rejected patterns (positional, **kwargs, missing, extra). Protocol reinforces
  the lesson from PR #66: every new validator rule must have a matching prompt
  constraint in the same PR.

- **Constructor-shape validation must cover all constructor calls, not only
  returned ones (Codex P2, round 1)**: The initial PR #67 check 10 implementation
  iterated only over `ast.Return` nodes. Codex P2 review found that a
  malformed non-return `DetectionResult(...)` call (expression statement,
  assignment, or nested branch call) would pass check 10 and could raise
  `TypeError` at runtime before any fallback return is reached. Protocol now
  requires that argument-shape validation covers every bare `DetectionResult`
  `ast.Call` in the replacement body, regardless of whether it appears inside
  a `return` statement.

- **Set-based keyword validation collapses duplicates (Codex P2, round 2)**:
  The set comprehension `{kw.arg for kw in n.keywords}` used for missing/extra
  comparison silently deduplicates keyword names. `DetectionResult(blocked=False,
  ..., blocked=True)` produces `provided == _REQUIRED_DR_KWARGS` and passes
  check 10, even though Python compilation would raise `TypeError: keyword
  argument repeated`. `ast.parse()` accepts duplicate keywords without raising
  `SyntaxError` (verified on Python 3.11), so check 6 does not catch this.
  Protocol now requires that duplicate keyword detection runs before the
  set-based comparison, using a list-based scan with an explicit `seen` set.

- **X-002 / X-003 / X-006 / X-007 remain Project Owner-overridable
  recommendations**: These policy extension items remain deferred. X-007
  excludes only type/value-range static checks; H-3 argument count/keyword-name
  validation is completed by PR #67. Protocol records this to prevent future
  agents from reopening H-3 scope or conflating it with X-007.

---

## PR #66 — Return presence ≠ fallthrough safety

Lessons that drove protocol additions:

- **Return existence is not fallthrough safety**: Check 7 of `_validate_replacement_code`
  verifies that at least one `ast.Return` exists anywhere in the replacement body
  (via `ast.walk`, which descends into nested blocks). Check 8 verifies every return
  is `return DetectionResult(...)`. Neither check guarantees that the function cannot
  fall through to implicit `None`. A body whose only returns are inside conditional
  blocks (`if`/`for`/`while`) silently returns `None` when no branch is taken, violating
  the `inspect_request()` contract. Protocol now requires check 9: the last top-level
  AST node in the replacement body must be `ast.Return`.

- **"Some return exists" ≠ "safe return path exists"**: These two properties are
  orthogonal. A validator must explicitly distinguish between them. The fail-closed
  design principle requires that every execution path through the body reaches a
  safe return, not merely that a safe return is reachable from *some* path.
  Protocol now requires this distinction to be documented in the PR body and CHANGELOG
  whenever a new semantic validation check is added to `_validate_replacement_code`.

- **Minimal fallthrough guard is sufficient for H-2**: Full CFG/reachability analysis
  is not required for this guard. Requiring the last top-level node to be `ast.Return`
  is a minimal fail-closed rule that catches the most common fallthrough pattern
  (if-block with nested return, no fallback). Deferred scope:
  H-3 argument count/keyword-name validation, X-007 type/value-range checks,
  X-002/X-003/X-006 policy alignment remain PR #67+ work.

- **LLM prompt must reflect validator constraints**: When check 9 was added, the
  `_LLM_SYSTEM_PROMPT` REQUIRED/FORBIDDEN sections must be updated in the same PR
  so the model is instructed to generate code that satisfies the new rule.
  A validator rule without a matching prompt constraint leaves the model generating
  code that will be rejected on the first paid-credit run. Protocol now requires
  prompt and validator to stay in sync.

- **X-002/X-003/X-006/X-007 remain Project Owner-overridable recommendations**:
  These policy extension items were deferred in PR #66 as non-binding follow-ups.
  X-007 excludes only type/value-range static checks; H-3 argument count/keyword-name
  validation is a separate pending item. Protocol now records this explicitly to
  prevent future agents from conflating X-007 scope with H-3 scope.

---

## PR #65 — Task prompt construction and PR completion gates

Lessons that drove protocol additions:

- **Under-specified task prompts cause scope drift**: Implementation prompts that
  omit ALLOWED / REFERENCE_ONLY / FROZEN / IMPACT boundaries can cause an agent
  to touch adjacent files or perform opportunistic refactors. Protocol now
  requires `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` before writing any task
  prompt.
- **IMPACT cannot be blank**: An empty impact section hides possible call-site,
  docs, or workflow propagation. Protocol now requires `なし（理由）` when there
  is no impact.
- **ALLOWED files require justification**: Listing editable files without a
  reason makes scope expansion easier. Protocol now requires a one-line reason
  for every ALLOWED file.
- **Change Request fields must be complete even for one-line changes**: Small
  changes can still violate invariants. Protocol now requires WHAT, WHY,
  INVARIANT, DO_NOT, and VERIFY for every task prompt.
- **PR completion requires documentation / history verification**: A PR is not
  complete until README, docs, changelog/history, generator scripts, and data
  history / ledger update needs are explicitly checked or ruled out with a
  reason.
- **Prompt wording must distinguish top-level from nested returns**: The
  `_LLM_SYSTEM_PROMPT` contained the line "return DetectionResult(...) must be
  at exactly 4-space indentation" without any exception for nested returns. A
  `return DetectionResult(...)` inside an `if`/`for`/`while` block is
  necessarily at 8/12/16 spaces — not 4 — and must not be rejected. Prompt
  wording that implies all returns must be at exactly 4 spaces is logically
  wrong and contradicts the GOOD example already in the same prompt. Protocol
  now requires prompt indentation rules to explicitly distinguish top-level
  returns (4 spaces) from nested returns (block depth 8/12/16 spaces).
- **Runbook wrapper description must match the actual validator implementation**:
  The Syntax Validation Guard in `docs/API_ACTIVATION_RUNBOOK.md` described the
  AST validation wrapper as `def _candidate_body():\n...`, omitting both the
  `request` parameter and the `_mutation_anchor = None` anchor statement. The
  actual implementation is `def _candidate_body(request):\n    _mutation_anchor =
  None\n    # === MUTATION_START ===`. Simplified wrapper descriptions weaken
  evidence quality and create audit ambiguity about which body nodes constitute
  the replacement region. Protocol now requires that runbook wrapper descriptions
  match the actual implementation signature and include the anchor statement.
- **No-patch artifact boundary must be tested at the CLI level**: Unit tests
  calling `_validate_replacement_code` directly prove the validator rejects bad
  code, but do not prove that `mutation_patch.json` is not written to disk. PR
  completion evidence must include a test that asserts `not patch_path.exists()`
  at the CLI/artifact boundary, not just at the function-return level.

---

## PR #33 — Fitness schema hardening

Lessons that drove protocol additions:

- **bool-as-number**: `score=true` and `score=false` passed numeric validation
  because Python treats `bool` as a subtype of `int`. Protocol now requires
  explicit bool-as-number rejection checks.
- **NaN / Infinity**: Floating-point special values bypassed range checks.
  Protocol now requires NaN and Infinity rejection for all fitness fields.
- **Oversized integer / traceback**: Arbitrarily large integers caused
  `float()` conversion to raise an unhandled exception rather than returning a
  schema error. Protocol now requires that oversized integers produce a clean
  schema error, not a traceback.

---

## PR #34 — Repo-level invariant tests

Lessons that drove protocol additions:

- **Current-head CI**: A local test run in the PR body was presented as
  evidence. Protocol now requires CI to be verified for the current head SHA on
  GitHub, not from a local or self-reported run.
- **Undeclared dependency**: A test passed locally due to an undeclared
  dependency that was present in the local environment but not in CI. Protocol
  now flags undeclared dependency risk as part of INSTALL FAILURE and DOMAIN
  FAILURE classification.
- **Secret scanner re-leak**: The secret scanner was logging redacted evidence
  that still exposed partial secret material in CI logs. Protocol now requires
  that secret scanner output be checked for re-leak during audit.
- **Generated-code / write-permission separation**: A write-permission job was
  executing generated candidate code. Protocol now treats this as scope drift
  requiring explicit justification.

---

## PR #36 — GEMINI_API_KEY wording unification

Lessons that drove protocol additions:

- **GEMINI_API_KEY wording**: The difference between passing the raw key and
  passing a boolean existence signal (`GEMINI_API_KEY_PRESENT`) was not
  consistently enforced. Protocol now requires checking which form is used at
  each scope (step-level, job-level, workflow-level).
- **Codex thread unresolved/outdated**: An unresolved Codex inline thread was
  treated as non-blocking because a general "no major issues" review comment
  existed. Protocol now explicitly separates reaction, review comment, and
  inline thread states.
- **Markdown backticks false negative**: A regex for detecting obsolete wording
  was bypassed by wrapping the key name in Markdown backticks. Protocol now
  requires that wording checks handle both plain and backtick-wrapped forms.

---

## PR #35 — Stale pullback prompt / Codex reaction confusion

Lessons that drove protocol additions:

- **Stale pullback prompt**: The pullback prompt in use still referenced PR
  #29–#33 state while PRs #34–#36 had introduced new lessons. Protocol now
  separates the pullback prompt from the full audit protocol and links to
  CHANGELOG.md so the prompt stays short and the history is explicit.
- **Codex +1 reaction is not full thread review**: A +1 reaction on a Codex
  review was logged as "Codex verified." Protocol now requires explicit
  classification: VERIFIED BY REACTION ONLY vs. VERIFIED (thread-level).
- **Blocked / fallback / low-level operation must be audit-significant**: A
  tool fallback to low-level GitHub blob/tree operations was not reported in the
  PR body. Protocol now requires all such anomalies to appear in the final
  response or PR body as an audit trail.

---

## PR #28 — Stale open PR superseded by main

Lessons that drove protocol additions:

- **Stale open PR can be superseded**: An open PR from an earlier context was
  still referenced as the current plan after main had moved on significantly.
  Protocol now requires checking whether an open PR's base is still current and
  whether it has been superseded by later merged work.
- **Close stale PR instead of rescuing old context**: Attempting to patch an
  old PR whose branch had diverged from main was less safe than closing it and
  opening a new PR from current main. Protocol now recommends this approach when
  a PR's branch is no longer mergeable and main has moved on.

---

## PR #40 — AST complexity / parser DoS guard

Lessons that drove protocol additions:

- **Source-size guard before ast.parse**: Source-size guard must run before
  calling `ast.parse`. Oversized source can cause the parser itself to exhaust
  memory before any AST-level check runs. Source size is checkable without
  building the AST.
- **AST node-count and depth guards run after parsing succeeds**: Node-count is
  not knowable before AST construction. AST node-count, depth, and related
  structural guards run only after `ast.parse` succeeds, before evaluation,
  promote, or other expensive policy processing.
- **ast.parse raises MemoryError / RecursionError**: `ast.parse` may raise
  `MemoryError` or `RecursionError` in addition to `SyntaxError`. Protocol now
  requires that all three exception types are handled fail-closed.
- **Candidate write-before-validation DoS residue**: Writing a candidate file
  before full validation can leave residue on disk if cleanup is bypassed by an
  exception. Protocol now requires that `apply_mutation` fails closed and cleans
  invalid candidate files when validation aborts mid-flight.
- **Fail-closed on parser failure**: When any parser failure (syntax, memory,
  recursion) occurs, the mutation must be rejected with a structured validation
  failure — not silently accepted or partially applied.

---

## PR #41 — Runtime allocation guard

Lessons that drove protocol additions:

- **Small AST can still cause huge runtime allocation**: An AST that passes
  node-count limits can still generate unbounded runtime allocation at
  evaluation time. Source-level AST limits are not sufficient on their own.
- **Computed repeat multiplier must be rejected**: Expressions like
  `"a" * (10 ** 9)` yield a valid small AST but allocate gigabytes at runtime.
  Protocol now requires that computed repeat multipliers are rejected
  fail-closed before evaluation / promote.
- **join(generator) must be restricted to statically bounded iterables**:
  `"".join(generator)` where the generator is not provably bounded can cause
  unbounded allocation. Protocol now requires that such patterns are rejected
  unless the iterable is statically bounded.
- **Non-provably bounded runtime allocation fails closed**: Any allocation
  pattern that cannot be statically proven bounded must be rejected, not
  accepted with a warning.

---

## PR #42 — Gemini API resilience / budget alignment

Lessons that drove protocol additions:

- **SDK timeout units must be verified**: The Gemini SDK may accept timeout
  values in seconds or milliseconds depending on the version or call site.
  A seconds-vs-milliseconds mismatch is audit-significant because it can
  result in either no effective timeout or a timeout far shorter than intended.
  Protocol now requires that timeout unit is verified and documented.
- **Retry attempts are actual API calls**: Each transient retry is a real
  `generate_content` call. Retry attempts must respect `max_model_requests_per_run`.
  Protocol now requires that retry count plus the initial call does not exceed
  the per-run request budget.
- **Paid-credit ledger must not be written per retry attempt**: Writing ledger
  entries per retry attempt (rather than per successful completion) can inflate
  the ledger and violate the budget accounting model. Protocol now requires
  that ledger writes occur outside the retry loop.
- **Budget / ledger accounting must align with actual generate_content call count**:
  The per-run call count tracked in the ledger must match the actual number of
  `generate_content` calls made, including retries.

---

## PR #43 — apply_mutation safe output path

Lessons that drove protocol additions:

- **Output path containment after resolving traversal and symlinks**: Checking
  the raw output path string is not sufficient. The resolved path (after
  traversal and symlink resolution) must be contained within the safe output
  root. Protocol now requires `Path.resolve()` before containment check.
- **output_root itself must not be a symlink**: If `output_root` is a symlink,
  containment checks against its string prefix can be bypassed. Protocol now
  requires that `output_root` itself is not a symlink before accepting any
  output path.
- **Unsafe output paths fail closed before write_text**: Any output path that
  fails the containment check, traversal check, or symlink check must cause
  `apply_mutation` to fail closed — no partial write, no fallback path.
- **Output-root parent symlink assumptions should be documented as residual
  constraints**: When full enforcement of parent-directory symlink assumptions
  is not achieved, the remaining constraint must be documented explicitly as a
  residual risk, not silently assumed safe.
