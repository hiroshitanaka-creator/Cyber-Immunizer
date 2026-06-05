<!--
AI_DOC_META
status: SPEC-FROZEN
scope: X-007 static type/value-range checks for DetectionResult fields. Policy frozen in PR #69; safe-subset implementation reserved for PR #70.
use_for:
  - understanding which literal value cases PR #70 may statically reject
  - understanding which dynamic expressions PR #70 must allow or defer
  - planning the PR #70 adversarial test matrix
  - confirming that check 11 is NOT implemented in PR #69
do_not_use_for:
  - claiming check 11 is implemented (it is not — PR #69 is docs-only)
  - over-rejecting dynamic expressions such as confidence=min(1.0, score) (see Category B)
  - executing or evaluating candidate code during validation (see Category C)
  - asserting that all runtime value correctness is guaranteed by static checks (see Category D)
related:
  - docs/API_ACTIVATION_RUNBOOK.md
  - core/types.py
  - scripts/propose_mutation.py
last_reviewed: 2026-06-05
pr_69_x007_spec_freeze: X-007 policy frozen in PR #69 — check 11 NOT implemented here
AI_DOC_META_END
-->

# X-007 Static Value-Check Policy — Specification Freeze (PR #69)

> **Status: FROZEN — PR #69 freezes this specification. It does NOT implement check 11.**  
> **PR #70 is reserved for safe-subset implementation based on this frozen policy.**  
> The current validator implements checks 1–10 only.  
> Do not claim X-007 type/value checks are enforced in the current validator.

---

## Background

`DetectionResult` is defined in `core/types.py` as:

```python
DetectionResult(blocked: bool, reason: str, confidence: float, matched_signals: tuple[str, ...])
```

PR #67 (check 10) validates that every bare `DetectionResult(...)` call in `replacement_code` uses
keyword-only arguments with exactly the four canonical keyword names (`blocked`, `reason`,
`confidence`, `matched_signals`). Check 10 does **not** validate:

- that `blocked` is a `bool` literal (not a string, number, or `None`)
- that `reason` is a string (not a number, `bool`, or `None`)
- that `confidence` is in the range `[0.0, 1.0]` and is a `float` (not a string or `bool`)
- that `matched_signals` is a `tuple` (not a `list`, `dict`, or `str`)

Those type/value-range checks are the X-007 scope, deferred to PR #70.

---

## Why a Docs-First Freeze Is Required

Implementing X-007 without a frozen policy risks over-rejecting valid detector logic.
For example:

- `confidence=min(1.0, score)` is a dynamic expression that may produce a valid `float` at
  runtime, but static analysis cannot prove its range.
- `matched_signals=tuple(matched)` is a common pattern that produces a `tuple` at runtime,
  but static analysis cannot confirm the element type.
- `blocked=score > threshold` is a valid comparison expression that produces a `bool`, but
  a naive literal check would reject it.

The frozen policy below defines exactly which cases are safe for static rejection and which
must remain deferred or explicitly allowed.

---

## Category A — Cases PR #70 May Statically Reject (Obvious Invalid Literals)

These are AST-detectable obvious invalid literals that a well-formed detector would never use.
PR #70 may reject these without Project Owner override.

| Field | Obvious invalid literal examples | Why safe to reject |
|---|---|---|
| `blocked` | string literal (`"true"`, `"false"`), number literal (`0`, `1`), `None`, list literal, tuple literal | `blocked` must be `bool`; these literals are never valid for a `bool` field |
| `reason` | number literal (`42`, `3.14`), `bool` literal (`True`, `False`), `None`, list literal, tuple literal | `reason` must be `str`; these literals are never valid for a string description |
| `confidence` | string literal (`"high"`), `None`, list literal, tuple literal, `bool` literal (`True`, `False`), literal numeric value outside `[0.0, 1.0]` (e.g., `1.5`, `-0.1`, `2`) | `confidence` must be `float` in `[0.0, 1.0]`; out-of-range or non-numeric literals are never valid |
| `matched_signals` | string literal (`"sql"`), list literal (`["a", "b"]`), dict literal, tuple literal containing non-string constants (e.g., `(1, 2)`, `(True,)`, `(None,)`) | `matched_signals` must be `tuple[str, ...]`; non-tuple container literals and tuples with non-string elements are never valid |

### Notes on `confidence=True` / `confidence=False`

Python treats `bool` as a subclass of `int`, so `confidence=True` compiles and may even pass
a loose type check (`isinstance(True, (int, float))` is `True`). However:

- `True` evaluates to `1` and `False` to `0` as a float, both technically in `[0.0, 1.0]`.
- This is almost certainly a mistake (confusion of `blocked` with `confidence`).
- PR #70 **should** reject `confidence=True` / `confidence=False` as obvious invalid literals
  (`bool` literal is never a valid `confidence` value regardless of numeric coercion).

### Notes on `confidence=float("nan")`

`float("nan")` is a function call expression, not a literal. PR #70 **must not** evaluate it.
Options:
- Treat `float(...)` calls as dynamic expressions and defer (recommended).
- Reject any `float(...)` call with a string argument as a forbidden pattern if existing
  forbidden-token policy covers it.
- Do not add `float("nan")` to Category A. Category A is for bare AST literals only.

---

## Category B — Expressions PR #70 Must Allow or Defer (Dynamic Patterns)

These dynamic expressions produce valid values at runtime and must not be rejected by PR #70
unless the Project Owner explicitly approves stricter policy.

| Field | Dynamic expression examples | Disposition |
|---|---|---|
| `blocked` | `bool(matched)`, `len(signals) > 0`, variable reference, conditional expression | **Allow / defer** — comparison and `bool()` calls produce valid `bool` at runtime |
| `reason` | f-string (`f"Detected {pattern}"`), string concatenation, variable reference, conditional expression | **Allow / defer** — these produce valid `str` at runtime |
| `confidence` | `min(1.0, score)`, `max(0.0, raw)`, arithmetic expressions, variable reference, conditional expression, `round(x, 4)` | **Allow / defer** — these may produce valid `float` in `[0.0, 1.0]` at runtime; static analysis cannot prove range |
| `matched_signals` | `tuple(matched)`, `tuple(s for s in signals if isinstance(s, str))`, variable reference, conditional expression | **Allow / defer** — these produce valid `tuple` at runtime; element type cannot be proved statically without execution |

**Default disposition rule**: If an expression is not an obvious invalid literal from Category A,
PR #70 must defer rather than reject. When in doubt, defer.

---

## Category C — AST-Only Constraint (No Execution)

PR #70 static validation must remain AST-only. The validator:

- **Must not** call `eval()`, `compile()`, `exec()`, or `import` on candidate code.
- **Must not** invoke Python's runtime type system on candidate expressions.
- **Must not** execute the candidate or any part of it to determine value ranges.
- **Must** use `ast.parse()` and AST node inspection only (consistent with checks 1–10).
- **Must** treat any expression that is not an obvious AST-literal from Category A as a dynamic
  expression subject to Category B disposition (allow/defer).

This constraint is the same as checks 1–10 and must not be weakened in PR #70.

---

## Category D — Fitness/Runtime Responsibility and Its Limits

PR #70 safe-subset static checks **cannot** prove that all runtime values are valid.
However, fitness/evaluate is **not** a complete type-safety net either. This section states
precisely what the current runtime path does and does **not** catch, so that neither PR #70
nor future agents over-rely on it.

### What the runtime path actually verifies (verified against current code)

`core/fitness.py::_contract_ok` checks only:

- `inspect_request` exists and is callable,
- it does not **raise** on a smoke-test `Request`,
- the returned object is an instance of `DetectionResult`,
- `result.confidence` is within `[0.0, 1.0]`.

`core/test_attacker.py::summarize_results` scores `actual_blocked = result.blocked` by
**truthiness** (`if expected and actual: ...`), and counts any exception **raised during
evaluation** toward `exception_count`.

### What the runtime path does NOT catch (the residual gap)

`DetectionResult` is a plain dataclass and **does not enforce field types**. Therefore the
following pass construction without raising `TypeError`, pass `_contract_ok`, and get scored:

- `blocked="yes"` — a non-`bool` that is truthy; scored as "blocked" by truthiness.
- `reason=42` — a non-`str` that breaks nothing downstream.
- `matched_signals=(1, 2)` — non-string elements; `list(result.matched_signals)` just wraps them.

In short: a wrong-type value that neither raises during evaluation nor pushes `confidence`
outside `[0.0, 1.0]` is **not** rejected by fitness/evaluate today.

### What this means for PR #70

- Do **not** claim that fitness/evaluate detects all wrong-type `DetectionResult` values.
  It does not.
- This residual gap is precisely **why Category A static literal rejection matters**: for
  obvious invalid literals, the static check (Category A) is the only line of defense, since
  the runtime path will silently score them.
- Fitness/evaluate **does** reliably catch: expressions that raise during evaluation (e.g.,
  `confidence=min(1.0, score)` where `score` is `None` raises `TypeError` at call time →
  counted as an exception), `confidence` outside `[0.0, 1.0]`, and behavioral quality
  (TP/FP/FN, regression pass rate, FP-rate gate, exception count).
- For Category B dynamic expressions that are deferred, "deferred" means "not statically
  rejected" — it does **not** mean "guaranteed valid at runtime." The residual type risk is a
  known, accepted limitation of the AST-only safe subset, not something fitness fully covers.
  Tightening this further (runtime contract checks for `blocked`/`reason`/`matched_signals`
  element types) is a separate, Project Owner-overridable item (see Scope-Out).

---

## PR #70 Adversarial Test Matrix Proposal

The following test cases must be covered by PR #70 before implementation is considered complete.
This matrix is non-normative for PR #69 (docs-only) but is the contract for PR #70.

| # | Case | Field | Input | Expected result |
|---|---|---|---|---|
| 1 | Valid literal `blocked` | `blocked` | `blocked=True` | Accept |
| 2 | Valid literal `reason` | `reason` | `reason="detected sql"` | Accept |
| 3 | Valid literal `confidence` | `confidence` | `confidence=0.9` | Accept |
| 4 | Valid literal `matched_signals` | `matched_signals` | `matched_signals=("sql",)` | Accept |
| 5 | Valid empty `matched_signals` | `matched_signals` | `matched_signals=()` | Accept |
| 6 | Dynamic `blocked` | `blocked` | `blocked=len(signals) > 0` | Accept (defer) |
| 7 | Dynamic `reason` | `reason` | `reason=f"Detected {pattern}"` | Accept (defer) |
| 8 | Dynamic `confidence` | `confidence` | `confidence=min(1.0, score)` | Accept (defer) |
| 9 | Dynamic `matched_signals` | `matched_signals` | `matched_signals=tuple(matched)` | Accept (defer) |
| 10 | Variable reference | all | `blocked=result`, `confidence=val` | Accept (defer) |
| 11 | Invalid literal `blocked` — string | `blocked` | `blocked="true"` | **Reject** |
| 12 | Invalid literal `blocked` — number | `blocked` | `blocked=1` | **Reject** |
| 13 | Invalid literal `blocked` — None | `blocked` | `blocked=None` | **Reject** |
| 14 | Invalid literal `reason` — number | `reason` | `reason=42` | **Reject** |
| 15 | Invalid literal `reason` — bool | `reason` | `reason=True` | **Reject** |
| 16 | Invalid literal `reason` — None | `reason` | `reason=None` | **Reject** |
| 17 | Invalid literal `confidence` — string | `confidence` | `confidence="high"` | **Reject** |
| 18 | Invalid literal `confidence` — None | `confidence` | `confidence=None` | **Reject** |
| 19 | Out-of-range `confidence` — above 1.0 | `confidence` | `confidence=1.5` | **Reject** |
| 20 | Out-of-range `confidence` — negative | `confidence` | `confidence=-0.1` | **Reject** |
| 21 | `confidence=True` — bool-as-number confusion | `confidence` | `confidence=True` | **Reject** (bool literal never valid) |
| 22 | `confidence=False` — bool-as-number confusion | `confidence` | `confidence=False` | **Reject** (bool literal never valid) |
| 23 | Invalid literal `matched_signals` — string | `matched_signals` | `matched_signals="sql"` | **Reject** |
| 24 | Invalid literal `matched_signals` — list | `matched_signals` | `matched_signals=["a", "b"]` | **Reject** |
| 25 | Tuple with non-string constant | `matched_signals` | `matched_signals=(1, 2)` | **Reject** |
| 26 | Tuple with `None` element | `matched_signals` | `matched_signals=(None,)` | **Reject** |
| 27 | `confidence=float("nan")` | `confidence` | `confidence=float("nan")` | Defer (function call, not literal) |
| 28 | `reason=f"..."` f-string | `reason` | `reason=f"Detected {x}"` | Accept (defer) |
| 29 | `blocked=score > threshold` comparison | `blocked` | `blocked=score > 0.5` | Accept (defer) |
| 30 | Parse-succeeds but runtime value may be wrong | all | `confidence=compute_score()` | Accept (defer) — residual runtime risk; not fully covered by fitness (see Category D) |
| 31 | Stricter `matched_signals` element-type check | `matched_signals` | `matched_signals=tuple(matched)` | Scope-out — defer unless Project Owner approves |

### False-Rejection Regression Cases (PR #70 must not break these)

| # | Case | Input | Must not reject |
|---|---|---|---|
| R1 | `confidence=min(1.0, score)` | dynamic expression | Must not reject — Category B |
| R2 | `confidence=max(0.0, raw_score)` | dynamic expression | Must not reject — Category B |
| R3 | `matched_signals=tuple(matched)` | dynamic expression | Must not reject — Category B |
| R4 | `blocked=bool(any_match)` | dynamic expression | Must not reject — Category B |
| R5 | `reason=f"Blocked: {pattern}"` | f-string | Must not reject — Category B |
| R6 | `confidence=round(raw, 4)` | function call | Must not reject — Category B |
| R7 | `blocked=True` | valid literal bool | Must not reject — Category A allows True/False for `blocked` |
| R8 | `confidence=0.0` | boundary literal | Must not reject — in range `[0.0, 1.0]` |
| R9 | `confidence=1.0` | boundary literal | Must not reject — in range `[0.0, 1.0]` |

---

## Scope-Out Items (Project Owner-Overridable)

The following items are explicitly out of scope for PR #70 unless the Project Owner approves:

- Full range proof for dynamic `confidence` expressions (requires symbolic execution or SMT solver).
- Element-type verification for `tuple(matched)` — whether `matched` contains only strings.
- Semantic validation that `reason` is a non-empty string at runtime.
- Runtime contract checks for `blocked` (must be `bool`), `reason` (must be `str`), and
  `matched_signals` element types in `core/fitness.py::_contract_ok`. The current contract
  check verifies only `DetectionResult` instance and `confidence` range; extending it to
  enforce the other field types at runtime would close the Category D residual gap but is a
  runtime change outside the X-007 AST-only static scope.
- X-002 / X-003 / X-006 policy alignment — these remain separate policy items.
- Full CFG/reachability analysis beyond the existing check 9 fallthrough guard.

---

## Relationship to Other Checks

| Check | What it validates | What it does NOT validate |
|---|---|---|
| Check 8 (PR #65) | Every `return` is `return DetectionResult(...)` | Argument types or values |
| Check 9 (PR #66) | Last top-level node is `ast.Return` (fallthrough guard) | Argument types or values |
| Check 10 (PR #67, H-3) | Keyword-only args, exactly the 4 canonical names | Argument types or values |
| **Check 11 (PR #70, X-007)** | **Safe-subset literal type/value rejection** | **Dynamic expression correctness (deferred)** |

> **Check 11 is NOT implemented in PR #69.**  
> `scripts/propose_mutation.py` `_validate_replacement_code` currently has 10 checks.  
> PR #70 will add check 11 based on Category A of this specification.

---

## Reference

- `core/types.py` — canonical `DetectionResult` dataclass definition
- `scripts/propose_mutation.py` — `_validate_replacement_code` (checks 1–10, current implementation)
- `docs/API_ACTIVATION_RUNBOOK.md` — check order table and X-007 frozen note
- `docs/audit_gate/CHANGELOG.md` — PR #69 design lesson
