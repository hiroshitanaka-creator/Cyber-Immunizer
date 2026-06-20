from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.structured_validator import validate_rules_schema

ROOT = Path(__file__).parent.parent
CLI = ROOT / "scripts" / "validate_structured_rules.py"


def illustrative_rules() -> dict:
    return {
        "schema_version": 1,
        "features": {
            "surface": {
                "fields": [
                    "method",
                    "path",
                    "query.keys",
                    "query.values",
                    "headers.keys",
                    "headers.values",
                    "body",
                ],
                "normalization": ["lowercase"],
                "max_collection_entries": {"query": 100, "headers": 100},
                "max_scalar_bytes": {
                    "method": 64,
                    "path": 4096,
                    "query.item": 4096,
                    "header.item": 4096,
                },
                "body_scan": {"mode": "full", "max_bytes": 524288},
            }
        },
        "rules": [
            {
                "id": "symbolic_path_traversal",
                "field": "surface",
                "operator": "contains_literal",
                "literal": "path_traversal_indicator",
                "signal": "path_traversal_indicator",
                "confidence": 0.86,
            },
            {
                "id": "symbolic_script_injection",
                "field": "surface",
                "operator": "contains_literal",
                "literal": "script_injection_indicator",
                "signal": "script_injection_indicator",
                "confidence": 0.86,
            },
        ],
        "decision": {
            "block_when": "any_rule_matches",
            "reason": "suspicious indicator matched",
            "confidence_strategy": {
                "type": "bounded_match_count",
                "default": 0.86,
                "two_matches": 0.94,
                "three_or_more_matches": 0.99,
            },
            "matched_signals": "matched_rule_signals",
        },
        "fallback": {
            "blocked": False,
            "reason": "no suspicious indicator matched",
            "confidence": 0.0,
            "matched_signals": [],
        },
    }


def assert_invalid(data: dict, expected_fragment: str) -> None:
    result = validate_rules_schema(data)
    assert result["success"] is False
    assert any(expected_fragment in violation for violation in result["violations"]), result


def test_illustrative_json_shape_passes() -> None:
    result = validate_rules_schema(illustrative_rules())
    assert result == {"success": True, "violations": []}


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda d: d.pop("features"), "missing required key 'features'"),
        (lambda d: d.__setitem__("featurez", {}), "unexpected key 'featurez'"),
        (lambda d: d["features"]["surface"].__setitem__("fieldz", []), "unexpected key 'fieldz'"),
        (lambda d: d.__setitem__("schema_version", "1"), "schema_version"),
        (lambda d: d["features"]["surface"].__setitem__("fields", "path"), "fields: must be a list"),
        (lambda d: d["features"]["surface"]["fields"].append("query.args"), "unsupported value 'query.args'"),
        (lambda d: d["features"]["surface"]["fields"].append("path"), "duplicate value 'path'"),
        (lambda d: d["features"]["surface"].__setitem__("normalization", ["casefold"]), "unsupported value 'casefold'"),
        (lambda d: d["features"]["surface"]["max_collection_entries"].__setitem__("query", 0), "positive integer"),
        (lambda d: d["features"]["surface"].__setitem__("body_scan", {"mode": "prefix", "max_bytes": 1}), "mode: must be 'full'"),
        (lambda d: d["rules"][0].__setitem__("operator", "regex"), "unsupported operator 'regex'"),
        (lambda d: d["rules"][0].__setitem__("literal", ""), "literal: must be non-empty"),
        (lambda d: d["rules"][0].__setitem__("confidence", 1.1), "confidence: must be a finite number"),
        (lambda d: d["decision"].__setitem__("block_when", "python_expression"), "unsupported decision mode"),
        (lambda d: d["decision"]["confidence_strategy"].__setitem__("type", "eval"), "unsupported strategy"),
        (lambda d: d["fallback"].__setitem__("blocked", True), "blocked: must be false"),
        (lambda d: d["fallback"].__setitem__("matched_signals", ["x"]), "must be an empty list"),
    ],
)
def test_invalid_documents_report_detailed_violations(mutate, fragment: str) -> None:
    data = illustrative_rules()
    mutate(data)
    assert_invalid(data, fragment)


def test_duplicate_rule_ids_are_rejected() -> None:
    data = illustrative_rules()
    data["rules"][1]["id"] = data["rules"][0]["id"]
    assert_invalid(data, "duplicate rule id")


def test_positional_args_and_call_signature_shapes_are_rejected() -> None:
    data = illustrative_rules()
    data["rules"][0].update({"args": ["body"], "kwargs": {"literal": "x"}})
    assert_invalid(data, "unexpected key 'args'")
    assert_invalid(data, "unexpected key 'kwargs'")


@pytest.mark.parametrize("bad_key", ["positional_args", "*args", "**kwargs"])
def test_adversarial_extra_argument_keys_are_rejected(bad_key: str) -> None:
    data = illustrative_rules()
    data["rules"][0][bad_key] = []
    assert_invalid(data, f"unexpected key '{bad_key}'")


def test_cli_json_accepts_valid_json_file(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(illustrative_rules()), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CLI), "--json", str(rules_path)],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"success": True, "violations": []}


def test_cli_detects_duplicate_json_keys(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CLI), "--json", str(rules_path)],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 1
    assert "duplicate key" in completed.stdout


def test_cli_accepts_documented_yaml_subset(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        """
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
""".lstrip(),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(CLI), "--json", str(rules_path)],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["success"] is True
