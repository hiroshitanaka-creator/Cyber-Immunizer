# Structured Detector Rules Design Proposal

## Purpose

This document proposes moving future detector mutations away from raw Python edits and toward a constrained structured rule representation. The goal is to preserve the current mutation loop's ability to improve request inspection while reducing the blast radius of generated changes.

This is a design-only proposal. It does not introduce a schema validator, evaluator, tests, runtime integration, model-setting changes, budget changes, promotion behavior, or paid-credit execution.

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
      "max_joined_length": 8192
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
    max_joined_length: 8192
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
- Required bounds for joined surface length and per-field string length.

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
6. **Bounded input processing** — feature extraction must cap string lengths and collection traversal to avoid memory or runtime expansion.
7. **Non-blocking fallback** — unsupported schemas, validation failures, evaluator errors, and no-match cases must return a deterministic non-blocking fallback result.
8. **Stable output contract** — evaluator output must remain a `DetectionResult`, never a bare boolean or exception-driven result.
9. **No privilege expansion** — structured rules must not modify files, ledgers, model names, budgets, promotion state, workflow configuration, or any code outside the approved integration path.

## Migration plan

1. **Design-only PR**
   - Add this proposal document only.
   - Do not modify runtime code, workflows, ledgers, model settings, budget settings, or promotion state.

2. **Schema validation PR**
   - Add a JSON Schema or equivalent validator for structured detector rules.
   - Include positive and negative validation tests.
   - Keep validation separate from runtime integration.

3. **Evaluator PR**
   - Add a fixed evaluator for validated structured rules.
   - Enforce safety invariants in code.
   - Test determinism, bounds, fallback behavior, and output contract preservation.

4. **Mutation-output PR**
   - Update proposal tooling to emit structured rule documents instead of Python replacement code.
   - Keep existing raw-Python mutation path disabled or guarded until integration is complete.

5. **Integration PR**
   - Wire validated structured rules into the detector pipeline through reviewed code.
   - Preserve `inspect_request`'s public contract and non-blocking fallback.
   - Include regression tests comparing current symbolic-token behavior to equivalent structured rules.

6. **Retirement PR**
   - Remove or permanently disable raw Python detector mutation once structured rules are validated, evaluated, tested, and adopted.

## Scope guard for this PR

This docs-only PR must not modify:

- `core/**`
- `.github/**`
- `data/**`
- ledgers, including `data/api_usage_ledger.json`
- model names
- budget settings
- promotion state

It must not run paid-credit workflows, invoke `workflow_dispatch`, call the Gemini API, promote a candidate, or set `promote_approved=true`.
