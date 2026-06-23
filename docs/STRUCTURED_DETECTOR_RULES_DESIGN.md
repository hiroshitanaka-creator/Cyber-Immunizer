# Structured Detector Rules Design Proposal

## Purpose

This document proposes moving future detector mutations away from raw Python edits and toward a constrained structured rule representation. The goal is to preserve the current mutation loop's ability to improve request inspection while reducing the blast radius of generated changes.

This document began as a design-only proposal. The repository now includes a static schema validator and CLI, a fixed runtime evaluator, and an explicit opt-in adapter/equivalence test harness for the proposed rule shape. The default `core.detector.inspect_request()` path remains unchanged: structured rules are not loaded automatically, proposer output has not migrated to structured rules, the raw Python mutation path has not been retired, and this work does not introduce model-setting changes, budget changes, promotion behavior, or paid-credit execution.

## Current baseline summary

The current detector mutation surface is intentionally narrow:

- `core/detector.py::inspect_request` is the only mutation target for automated detector changes.
- Only the internal logic between the mutation markers is eligible for mutation; the stable interface around it is not.
- The current generation-4 baseline builds a bounded request surface from allowed request fields:
  - `request.method`
  - `request.path`
  - `request.query` keys and values
  - `request.headers` keys and values
  - `request.body`
- It lowercases the bounded surface and performs simple symbolic token matching against neutralized indicators, including:
  - `path_traversal_indicator`
  - `script_injection_indicator`
  - `sqli_indicator`
  - `command_delimiter_indicator`
  - `encoded_traversal_indicator`
- It returns `DetectionResult(blocked=True, ...)` when one or more tokens are matched and otherwise returns the non-blocking fallback result.

In short: the current baseline is already constrained in intent, but it is still represented as mutable Python. The proposed next step is to represent future detector changes as structured data and evaluate that data through a fixed, reviewed interpreter.

## Proposed rule representation

Future mutations could produce a JSON or YAML document instead of Python source. The document would describe features, rules, the blocking decision, and the fallback behavior. The evaluator would be fixed code maintained outside the mutation payload.

### Illustrative JSON shape

```json
{
  "schema_version": 1,
  "features": {
    "surface": {
      "fields": ["method", "path", "query.keys", "query.values", "headers.keys", "headers.values", "body"],
      "normalization": ["lowercase"],
      "max_collection_entries": {"query": 100, "headers": 100},
      "max_scalar_bytes": {"method": 64, "path": 4096, "query.item": 4096, "header.item": 4096},
      "body_scan": {"mode": "full", "max_bytes": 524288}
    }
  },
  "rules": [
    {
      "id": "symbolic_path_traversal",
      "field": "surface",
      "operator": "contains_literal",
      "literal": "path_traversal_indicator",
      "signal": "path_traversal_indicator",
      "confidence": 0.86
    },
    {
      "id": "symbolic_script_injection",
      "field": "surface",
      "operator": "contains_literal",
      "literal": "script_injection_indicator",
      "signal": "script_injection_indicator",
      "confidence": 0.86
    }
  ],
  "decision": {
    "block_when": "any_rule_matches",
    "reason": "suspicious indicator matched",
    "confidence_strategy": {
      "type": "bounded_match_count",
      "default": 0.86,
      "two_matches": 0.94,
      "three_or_more_matches": 0.99
    },
    "matched_signals": "matched_rule_signals"
  },
  "fallback": {
    "blocked": false,
    "reason": "no suspicious indicator matched",
    "confidence": 0.0,
    "matched_signals": []
  }
}
```

### Equivalent YAML sketch

```yaml
schema_version: 1
features:
  surface:
    fields:
      - method
      - path
      - query.keys
      - query.values
      - headers.keys
      - headers.values
      - body
    normalization:
      - lowercase
    max_collection_entries:
      query: 100
      headers: 100
    max_scalar_bytes:
      method: 64
      path: 4096
      query.item: 4096
      header.item: 4096
    body_scan:
      mode: full
      max_bytes: 524288
rules:
  - id: symbolic_path_traversal
    field: surface
    operator: contains_literal
    literal: path_traversal_indicator
    signal: path_traversal_indicator
    confidence: 0.86
  - id: symbolic_script_injection
    field: surface
    operator: contains_literal
    literal: script_injection_indicator
    signal: script_injection_indicator
    confidence: 0.86
decision:
  block_when: any_rule_matches
  reason: suspicious indicator matched
  confidence_strategy:
    type: bounded_match_count
    default: 0.86
    two_matches: 0.94
    three_or_more_matches: 0.99
  matched_signals: matched_rule_signals
fallback:
  blocked: false
  reason: no suspicious indicator matched
  confidence: 0.0
  matched_signals: []
```

## Schema concepts

### `features`

`features` defines the bounded inputs derived from a `Request`. A first implementation should keep the surface deliberately small and explicit:

- Allowed fields only: `method`, `path`, `query.keys`, `query.values`, `headers.keys`, `headers.values`, and `body`.
- Allowed normalization only: deterministic string transforms such as `lowercase`.
- Required bounds for collection traversal and per-field string length, while preserving full-body scanning up to the current tested payload budget. `body_scan.max_bytes` must be at least 524288 bytes to preserve large-body coverage and may not exceed the validator's configured upper bound.

The structured evaluator should not implement equivalence by truncating a single joined surface before rule matching. The current generation-4 detector scans the full request body included in the request surface, and `tests/test_detector_performance.py::test_indicator_near_end_of_large_body_is_detected` requires detecting `path_traversal_indicator` after an approximately 256 KiB benign prefix. Bounds should therefore be expressed as explicit collection, scalar-field, and body-scan budgets; body matching must cover the entire configured body budget rather than only the first few KiB of a concatenated surface.

### `rules`

`rules` defines a bounded list of declarative checks. Initial operators should be intentionally limited, for example:

- `contains_literal`
- `equals_literal`
- `starts_with_literal`
- `ends_with_literal`

Each rule should have a stable `id`, target one declared feature, use one allowed operator, and provide a bounded literal. Rule output should be limited to a symbolic signal name and bounded confidence metadata.

### `decision`

`decision` defines how matched rules become a `DetectionResult`. Initial strategies should avoid arbitrary scoring expressions and should instead use a small allowlist such as:

- `any_rule_matches`
- `all_rules_match`
- `minimum_match_count`
- bounded confidence strategies such as fixed confidence, maximum matched confidence, or a small match-count table.

### `fallback`

`fallback` defines the deterministic non-blocking result used when no decision rule triggers or when the structured rules cannot be safely evaluated. The fallback must preserve a non-blocking default so malformed or unsupported structured rules do not create a fail-closed denial-of-service risk in local simulation.


## Implemented static schema validation

The schema-validation step of the migration plan is implemented in `core/structured_validator.py`. The public entry point is:

```python
from core.structured_validator import validate_rules_schema

result = validate_rules_schema(parsed_rules)
# {"success": True, "violations": []} on success
# {"success": False, "violations": ["..."]} on validation failure
```

The validator is intentionally strict: it rejects missing required keys, unknown fields, non-string mapping keys, unsupported operators, invalid confidence values, non-positive integer bounds, duplicate feature values, duplicate rule IDs, non-integer schema versions, unencodable bounded string values, and argument-like payload keys such as `args`, `kwargs`, `*args`, and `**kwargs` because structured rules are data, not callable Python invocations. It treats the rule-count maximum as a hard cap and returns immediately when the list is oversized. Confidence strategies use strategy-specific required and allowed keys: `fixed` and `bounded_match_count` require `default`, while `maximum_matched_confidence` accepts only `type`. When `decision.block_when` is `minimum_match_count`, `decision.minimum_match_count` is required and must be a positive integer no larger than the number of rules; that field is rejected for other decision modes.

A CLI wrapper is available at `scripts/validate_structured_rules.py`:

```bash
python scripts/validate_structured_rules.py path/to/rules.json
python scripts/validate_structured_rules.py --json path/to/rules.yaml
```

The CLI accepts JSON and a deliberately small YAML subset matching the sketch in this document. It uses only the Python standard library, rejects duplicate mapping keys where they can be observed during parsing, and performs static validation only. It does not evaluate rules, alter `core/detector.py`, call external APIs, modify ledgers, dispatch workflows, or promote candidates.

## Explicit non-goals

This design does not permit generated detector mutations to include or request:

- Arbitrary Python code.
- Python imports.
- File-system access.
- Network access.
- Shell command execution.
- Dynamic evaluation such as `eval`, `exec`, or template-expanded code.
- Reflection or object traversal beyond explicitly allowed request fields.
- Unbounded loops, recursion, comprehensions over unbounded data, or generated control flow.
- Model, budget, ledger, promotion, CI, or workflow changes.

## Safety invariants

Any future implementation should enforce these invariants before a structured rule document can influence detector behavior:

1. **Bounded rule count** — reject documents with more than a small configured maximum number of rules.
2. **Bounded literal size** — reject empty, oversized, or non-string literals; cap total literal bytes across the document.
3. **Allowed request fields only** — rule documents may reference only approved `Request` fields and derived features.
4. **Allowed operators only** — rule documents may use only a fixed operator allowlist implemented by reviewed evaluator code.
5. **Deterministic evaluation** — evaluation must be order-stable, side-effect-free, time-bounded, and independent of wall-clock time, randomness, files, network, environment variables, and external services.
6. **Bounded input processing without coverage regression** — feature extraction must cap scalar string lengths and collection traversal to avoid memory or runtime expansion, but it must not silently truncate the body below the current regression budget. Equivalent structured rules must still detect a symbolic indicator near the end of a large body, including the existing approximately 256 KiB body-performance case.
7. **Non-blocking fallback** — unsupported schemas, validation failures, evaluator errors, and no-match cases must return a deterministic non-blocking fallback result.
8. **Stable output contract** — evaluator output must remain a `DetectionResult`, never a bare boolean or exception-driven result.
9. **No privilege expansion** — structured rules must not modify files, ledgers, model names, budgets, promotion state, workflow configuration, or any code outside the approved integration path.

## Migration plan

1. **Design-only PR**
   - Add this proposal document only.
   - Do not modify runtime code, workflows, ledgers, model settings, budget settings, or promotion state.

2. **Schema validation PR**
   - Add a JSON Schema or equivalent validator for structured detector rules. **Implemented by `core/structured_validator.py`.**
   - Include positive and negative validation tests. **Implemented by `tests/test_structured_validator.py`.**
   - Keep validation separate from runtime integration. **Still true: the CLI and validator do not affect detector runtime behavior.**

3. **Evaluator PR**
   - Add a fixed evaluator for validated structured rules. **Implemented by `core/structured_evaluator.py`.**
   - Enforce safety invariants in code. **Implemented in the evaluator and validator.**
   - Test determinism, bounds, fallback behavior, and output contract preservation. **Implemented by `tests/test_structured_evaluator.py`.**
   - Include a large-body equivalence test showing that an indicator near the end of the configured body-scan budget is still matched. **Implemented by evaluator tests.**

4. **Opt-in adapter and equivalence PR**
   - Add an explicit call-site opt-in adapter for evaluating a `Request` with a supplied structured rules document. **Implemented by `core/structured_detector.py`.**
   - Keep `core.detector.inspect_request()` unchanged and avoid automatic structured-rule loading. **Confirmed by integration tests.**
   - Include sample-level, corpus-level, confidence, matched-signal-order, fallback, no-mutation, and large-body equivalence tests comparing structured rules to the current symbolic detector. **Implemented by `tests/test_structured_detector_integration.py` and `tests/test_structured_detector_equivalence.py`.**

5. **Mutation-output PR**
   - Update proposal tooling to emit structured rule documents instead of Python replacement code.
   - Keep existing raw-Python mutation path disabled or guarded until integration is complete.

6. **Automatic runtime integration PR**
   - Wire validated structured rules into the detector pipeline through reviewed code.
   - Preserve `inspect_request`'s public contract and non-blocking fallback.
   - Include regression tests comparing current symbolic-token behavior to equivalent structured rules, including the large-body near-end indicator coverage already required by `tests/test_detector_performance.py`.

7. **Retirement PR**
   - Remove or permanently disable raw Python detector mutation once structured rules are validated, evaluated, tested, and adopted.

## Scope guard for structured-rule validation work

Schema-validation work is limited to the validator module, CLI, validator tests, this design document, and narrowly scoped CI test invocation updates. It must not modify runtime detector behavior or integration code.

It must not modify:

- `data/**`
- ledgers, including `data/api_usage_ledger.json`
- model names
- budget settings
- promotion state

It must not run paid-credit workflows, invoke `workflow_dispatch`, call the Gemini API, promote a candidate, or set `promote_approved=true`.

## L1-F14 Decision Record (structured detector integration decision)

**Decision (recorded 2026-06-23): Option (b) — the structured detector modules
are an explicitly-invoked, opt-in path that is intentionally NOT auto-integrated
into the promoted runtime detector.** This resolves the open `L1-F14` criterion
in `docs/DEFINITION_OF_DONE.md`, which requires that `core/structured_*` be
either (a) integrated into a single runtime call path with equivalence tests, or
(b) explicitly documented as experimental / non-integrated with tests asserting
the separation.

### What is decided

- The promoted runtime detector `core/detector.py::inspect_request` remains the
  only automated mutation target and is **not** wired to structured rules. No
  environment variable, file read, or implicit loader can switch it to the
  structured path.
- The structured path is reachable only by an explicit caller that supplies both
  a mode and a rules document, via
  `core/runtime_selector.py::inspect_request_with_runtime_selector(mode="structured_rules", structured_rules_doc=...)`
  or directly via
  `core/structured_detector.py::inspect_request_with_structured_rules`.
- The structured evaluator is fixed, reviewed code (`core/structured_evaluator.py`)
  validated by a strict static schema validator (`core/structured_validator.py`);
  rule documents are treated as data, never as executable payloads.

### Evidence (machine-verifiable)

- **Separation asserted**: `tests/test_structured_detector_integration.py::test_default_detector_source_has_no_structured_integration_references`
  fails if `core/detector.py` ever references `structured_detector`,
  `structured_evaluator`, `inspect_request_with_structured_rules`, or
  `evaluate_structured_rules`.
- **No implicit activation**: `...::test_default_detector_still_requires_no_explicit_structured_rules`
  asserts the default detector behaves identically with no structured rules in play.
- **Equivalence proven on the current corpus**: `tests/test_structured_detector_equivalence.py::test_corpus_level_equivalence_for_main_and_adaptive_tiers`
  asserts the structured path produces identical `blocked` and `matched_signals`
  outcomes to `core/detector.py` across all six tiers (benign, attack,
  regression, holdout, counterfactual, drift), with additional sample-level,
  confidence, matched-signal-order, fallback, no-mutation, and large-body
  equivalence tests.

### What is explicitly NOT decided here

Phases 5–7 above (migrating proposer output to structured documents, automatic
runtime integration, and retiring the raw-Python mutation path) remain future,
Owner-gated work. This record does not authorize them; it only fixes the current
state as the tested, separated option (b).
