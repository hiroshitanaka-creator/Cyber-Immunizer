from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from core.structured_validator import MAX_RULES, validate_rules_schema

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


@pytest.mark.parametrize("schema_version", [1.0, True, "1", 2])
def test_schema_version_must_be_strict_integer_one(schema_version) -> None:
    data = illustrative_rules()
    data["schema_version"] = schema_version

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert "$.schema_version: must be integer 1" in result["violations"]


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


def test_body_scan_max_bytes_below_large_body_budget_rejected() -> None:
    data = illustrative_rules()
    data["features"]["surface"]["body_scan"]["max_bytes"] = 1024

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "body_scan.max_bytes" in violation
        and "large-body coverage" in violation
        and "524288" in violation
        for violation in result["violations"]
    ), result


def test_body_scan_max_bytes_upper_bound_remains_enforced() -> None:
    data = illustrative_rules()
    data["features"]["surface"]["body_scan"]["max_bytes"] = 1_048_577

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "body_scan.max_bytes" in violation and "1048576" in violation
        for violation in result["violations"]
    ), result


def test_minimum_match_count_requires_threshold() -> None:
    data = illustrative_rules()
    data["decision"]["block_when"] = "minimum_match_count"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "decision.minimum_match_count" in violation
        and "required" in violation
        for violation in result["violations"]
    ), result


def test_minimum_match_count_with_valid_threshold_passes() -> None:
    data = illustrative_rules()
    data["decision"]["block_when"] = "minimum_match_count"
    data["decision"]["minimum_match_count"] = 2

    result = validate_rules_schema(data)

    assert result == {"success": True, "violations": []}


@pytest.mark.parametrize(
    ("threshold", "fragment"),
    [
        (0, "must be >= 1"),
        (True, "must be an integer"),
        (3, "must be <= number of rules (2)"),
    ],
)
def test_minimum_match_count_invalid_thresholds_are_rejected(threshold, fragment: str) -> None:
    data = illustrative_rules()
    data["decision"]["block_when"] = "minimum_match_count"
    data["decision"]["minimum_match_count"] = threshold

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "decision.minimum_match_count" in violation and fragment in violation
        for violation in result["violations"]
    ), result


@pytest.mark.parametrize("block_when", ["any_rule_matches", "all_rules_match"])
def test_minimum_match_count_forbidden_for_other_decision_modes(block_when: str) -> None:
    data = illustrative_rules()
    data["decision"]["block_when"] = block_when
    data["decision"]["minimum_match_count"] = 1

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "decision.minimum_match_count" in violation
        and "allowed only" in violation
        for violation in result["violations"]
    ), result


def test_unencodable_rule_literal_returns_violation_without_raising() -> None:
    data = illustrative_rules()
    data["rules"][0]["literal"] = "\ud800"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "rules[0].literal" in violation and "valid UTF-8 encodable text" in violation
        for violation in result["violations"]
    ), result


def test_unencodable_fallback_reason_returns_violation_without_raising() -> None:
    data = illustrative_rules()
    data["fallback"]["reason"] = "\ud800"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "fallback.reason" in violation and "valid UTF-8 encodable text" in violation
        for violation in result["violations"]
    ), result


def test_fixed_confidence_strategy_requires_default() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {"type": "fixed"}

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "confidence_strategy" in violation and "missing required key 'default'" in violation
        for violation in result["violations"]
    ), result


def test_fixed_confidence_strategy_with_default_passes() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {"type": "fixed", "default": 0.86}

    result = validate_rules_schema(data)

    assert result == {"success": True, "violations": []}


def test_fixed_confidence_strategy_rejects_match_count_keys() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "fixed",
        "default": 0.86,
        "two_matches": 0.94,
    }

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any("unexpected key 'two_matches'" in violation for violation in result["violations"]), result


def test_bounded_match_count_confidence_strategy_requires_default() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {"type": "bounded_match_count"}

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "confidence_strategy" in violation and "missing required key 'default'" in violation
        for violation in result["violations"]
    ), result


def test_bounded_match_count_confidence_strategy_with_default_passes() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "bounded_match_count",
        "default": 0.86,
    }

    result = validate_rules_schema(data)

    assert result == {"success": True, "violations": []}


def test_bounded_match_count_confidence_strategy_with_optional_counts_passes() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "bounded_match_count",
        "default": 0.86,
        "two_matches": 0.94,
        "three_or_more_matches": 0.99,
    }

    result = validate_rules_schema(data)

    assert result == {"success": True, "violations": []}


def test_bounded_match_count_confidence_strategy_rejects_minimum_match_count_key() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "bounded_match_count",
        "default": 0.86,
        "minimum_match_count": 2,
    }

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any("unexpected key 'minimum_match_count'" in violation for violation in result["violations"]), result


def test_maximum_matched_confidence_strategy_with_only_type_passes() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {"type": "maximum_matched_confidence"}

    result = validate_rules_schema(data)

    assert result == {"success": True, "violations": []}


def test_maximum_matched_confidence_strategy_rejects_default() -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "maximum_matched_confidence",
        "default": 0.86,
    }

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any("unexpected key 'default'" in violation for violation in result["violations"]), result


@pytest.mark.parametrize("bad_value", [True, 1.1, math.nan, "0.86"])
def test_confidence_strategy_values_use_confidence_validation(bad_value) -> None:
    data = illustrative_rules()
    data["decision"]["confidence_strategy"] = {
        "type": "fixed",
        "default": bad_value,
    }

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "confidence_strategy.default" in violation
        and "finite number in [0.0, 1.0]" in violation
        for violation in result["violations"]
    ), result


def test_rules_over_cap_returns_before_walking_extra_rules() -> None:
    data = illustrative_rules()
    valid_rule = data["rules"][0].copy()
    data["rules"] = [valid_rule.copy() for _ in range(MAX_RULES + 1)]
    data["rules"][-1]["literal"] = "\ud800"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert result["violations"] == [f"$.rules: must contain at most {MAX_RULES} rules"]


def test_rules_over_cap_violation_count_does_not_grow_with_attacker_input() -> None:
    data = illustrative_rules()
    valid_rule = data["rules"][0].copy()
    data["rules"] = [valid_rule.copy() for _ in range(MAX_RULES + 1000)]
    data["rules"][-1] = {"literal": "\ud800", "unexpected": object()}

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert result["violations"] == [f"$.rules: must contain at most {MAX_RULES} rules"]


def test_non_string_top_level_key_returns_violation_without_raising() -> None:
    data = illustrative_rules()
    data[1] = "bad"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "mapping key" in violation and "must be a string" in violation
        for violation in result["violations"]
    ), result


def test_non_string_nested_key_returns_violation_without_raising() -> None:
    data = illustrative_rules()
    data["features"]["surface"][1] = "bad"

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert any(
        "features.surface" in violation
        and "mapping key" in violation
        and "must be a string" in violation
        for violation in result["violations"]
    ), result


def test_key_validation_still_reports_unexpected_and_missing_string_keys() -> None:
    data = illustrative_rules()
    data["features"]["surface"].pop("fields")
    data["features"]["surface"]["fieldz"] = []

    result = validate_rules_schema(data)

    assert result["success"] is False
    assert "$.features.surface: missing required key 'fields'" in result["violations"]
    assert "$.features.surface: unexpected key 'fieldz'" in result["violations"]


def test_cli_json_unencodable_bounded_string_returns_json_failure(tmp_path: Path) -> None:
    data = illustrative_rules()
    data["rules"][0]["literal"] = "\ud800"
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(data), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(CLI), "--json", str(rules_path)],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["success"] is False
    assert any("valid UTF-8" in violation for violation in result["violations"])
    assert "Traceback" not in completed.stderr


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
