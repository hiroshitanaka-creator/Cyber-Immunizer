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
