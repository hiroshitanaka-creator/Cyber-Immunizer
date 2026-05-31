# Audit Gate Protocol Changelog

This file records why specific rules were added to the Audit Gate protocols,
keyed to the PR lesson that motivated each addition.

This is not a project status document. Keep entries focused on protocol lessons.

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
