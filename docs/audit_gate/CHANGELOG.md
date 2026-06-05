# Audit Gate Protocol Changelog

This file records why specific rules were added to the Audit Gate protocols,
keyed to the PR lesson that motivated each addition.

This is not a project status document. Keep entries focused on protocol lessons.

---

## PR #XX — Task Prompt Gate v2 / Codex pre-emption requirement

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
