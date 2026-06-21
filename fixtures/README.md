# Cyber-Immunizer Evaluation Fixtures

This directory contains reference fixtures for the structured rules evaluation
framework (`cli/structured_eval.py`).

## Directory structure

```
fixtures/
  structured_rules/       JSON rule documents validated by core.structured_validator
    symbolic_equivalent.json   Symbolic-corpus equivalent of the gen-4 detector
  evaluation_corpus/      Test corpus JSON files
    symbolic_corpus.json       Neutralized symbolic corpus (10 cases: 5 attack, 5 benign)
```

## What these fixtures are

These fixtures use **symbolic placeholder patterns** — the same indicator tokens
used in `data/attack_requests.json` (e.g., `PATH_TRAVERSAL_INDICATOR`).
They demonstrate the evaluation framework but do **not** provide realistic threat
coverage and do **not** advance Layer 2 value validation.

## Usage

```bash
# Markdown report (symbolic corpus — symbolic only, not Layer 2 evidence)
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json

# JSON report
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json \
  --json
```

## Layer 2 usage (Owner-supplied files, outside the repository)

To achieve Layer 2 value validation (DEFINITION_OF_DONE.md L2-V1 through L2-V5),
the Owner supplies two files **outside the repository**:

1. **A rules document** with realistic but safely neutralized detection literals.
   These follow the same JSON schema as `symbolic_equivalent.json` but use
   actual defensive pattern strings instead of symbolic placeholders.

2. **A test corpus** with realistic but safely neutralized request samples.
   Each entry includes a `request`, `expected_blocked`, and category `tags`.

```bash
# Layer 2 evaluation using Owner-supplied files (paths are outside the repo)
python -m cli.structured_eval \
  --rules /path/to/owner/realistic_rules.json \
  --corpus /path/to/owner/realistic_corpus.json
```

The tool validates the rules document schema, runs evaluation, and outputs
per-category TP/FP/FN statistics.

## Rules document schema

Rules documents must validate against `core.structured_validator.validate_rules_schema`.
See `fixtures/structured_rules/symbolic_equivalent.json` for the complete schema shape.

Key fields:
- `schema_version`: must be `1`
- `features.surface.fields`: which request fields are inspected
- `rules[].operator`: `contains_literal`, `equals_literal`, `starts_with_literal`, `ends_with_literal`
- `rules[].literal`: the string to match (lowercased when `normalization` includes `lowercase`)
- `decision.block_when`: `any_rule_matches`, `all_rules_match`, or `minimum_match_count`

## Test corpus schema

Each corpus entry is a JSON object with:
```json
{
  "id": "case-001",
  "kind": "attack",
  "expected_blocked": true,
  "description": "Optional description",
  "tags": ["attack", "path-traversal"],
  "request": {
    "method": "GET",
    "path": "/some/path",
    "query": {},
    "headers": {},
    "body": ""
  }
}
```

The `tags` field controls per-category aggregation.  The first non-kind tag
(`attack`, `benign`, `regression`, `holdout`, `counterfactual`, `drift`) is used
as the category label in the report.
