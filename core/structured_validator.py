"""Strict schema validation for structured detector rule documents.

This module validates the constrained JSON/YAML-shaped rule documents proposed
in docs/STRUCTURED_DETECTOR_RULES_DESIGN.md. It only validates structure and
safety bounds; it does not evaluate rules or integrate with the runtime detector.
"""
from __future__ import annotations

import math
from typing import Any

ALLOWED_TOP_LEVEL_KEYS = {"schema_version", "features", "rules", "decision", "fallback"}
ALLOWED_SURFACE_KEYS = {
    "fields",
    "normalization",
    "max_collection_entries",
    "max_scalar_bytes",
    "body_scan",
}
ALLOWED_FIELDS = {
    "method",
    "path",
    "query.keys",
    "query.values",
    "headers.keys",
    "headers.values",
    "body",
}
ALLOWED_NORMALIZATION = {"lowercase"}
ALLOWED_COLLECTION_BOUNDS = {"query", "headers"}
ALLOWED_SCALAR_BOUNDS = {"method", "path", "query.item", "header.item"}
ALLOWED_RULE_KEYS = {"id", "field", "operator", "literal", "signal", "confidence"}
ALLOWED_OPERATORS = {
    "contains_literal",
    "equals_literal",
    "starts_with_literal",
    "ends_with_literal",
}
ALLOWED_DECISION_KEYS = {
    "block_when",
    "reason",
    "confidence_strategy",
    "matched_signals",
    "minimum_match_count",
}
ALLOWED_BLOCK_WHEN = {"any_rule_matches", "all_rules_match", "minimum_match_count"}
ALLOWED_CONFIDENCE_STRATEGY_KEYS = {
    "type",
    "default",
    "two_matches",
    "three_or_more_matches",
    "minimum_match_count",
}
ALLOWED_CONFIDENCE_STRATEGIES = {
    "bounded_match_count",
    "fixed",
    "maximum_matched_confidence",
}
ALLOWED_FALLBACK_KEYS = {"blocked", "reason", "confidence", "matched_signals"}

MAX_RULES = 64
MAX_ID_BYTES = 128
MAX_LITERAL_BYTES = 4096
MAX_TOTAL_LITERAL_BYTES = 65536
MAX_SIGNAL_BYTES = 128
MAX_REASON_BYTES = 512
MAX_MATCHED_SIGNALS = 64
MAX_BOUND_VALUE = 1_048_576
MIN_BODY_SCAN_BYTES = 524_288


def validate_rules_schema(data: dict) -> dict:
    """Validate a structured detector rules document.

    Args:
        data: Parsed JSON/YAML mapping.

    Returns:
        dict with ``success`` bool and ``violations`` list of human-readable
        violation strings. No exception is raised for validation failures.
    """
    violations: list[str] = []
    if not isinstance(data, dict):
        return {"success": False, "violations": ["$: document must be an object"]}

    _check_keys("$", data, ALLOWED_TOP_LEVEL_KEYS, ALLOWED_TOP_LEVEL_KEYS, violations)
    schema_version = data.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != 1
    ):
        violations.append("$.schema_version: must be integer 1")

    _validate_features(data.get("features"), violations)
    _validate_rules(data.get("rules"), violations)
    _validate_decision(data.get("decision"), data.get("rules"), violations)
    _validate_fallback(data.get("fallback"), violations)
    return {"success": not violations, "violations": violations}


def _validate_features(value: Any, violations: list[str]) -> None:
    if not isinstance(value, dict):
        violations.append("$.features: must be an object")
        return
    _check_keys("$.features", value, {"surface"}, {"surface"}, violations)
    surface = value.get("surface")
    if not isinstance(surface, dict):
        violations.append("$.features.surface: must be an object")
        return
    _check_keys("$.features.surface", surface, ALLOWED_SURFACE_KEYS, ALLOWED_SURFACE_KEYS, violations)
    _check_unique_string_list(
        "$.features.surface.fields", surface.get("fields"), ALLOWED_FIELDS, violations
    )
    _check_unique_string_list(
        "$.features.surface.normalization",
        surface.get("normalization"),
        ALLOWED_NORMALIZATION,
        violations,
    )
    _check_positive_int_map(
        "$.features.surface.max_collection_entries",
        surface.get("max_collection_entries"),
        ALLOWED_COLLECTION_BOUNDS,
        violations,
    )
    _check_positive_int_map(
        "$.features.surface.max_scalar_bytes",
        surface.get("max_scalar_bytes"),
        ALLOWED_SCALAR_BOUNDS,
        violations,
    )
    body_scan = surface.get("body_scan")
    if not isinstance(body_scan, dict):
        violations.append("$.features.surface.body_scan: must be an object")
        return
    _check_keys("$.features.surface.body_scan", body_scan, {"mode", "max_bytes"}, {"mode", "max_bytes"}, violations)
    if body_scan.get("mode") != "full":
        violations.append("$.features.surface.body_scan.mode: must be 'full'")
    _check_body_scan_bytes("$.features.surface.body_scan.max_bytes", body_scan.get("max_bytes"), violations)


def _validate_rules(value: Any, violations: list[str]) -> None:
    if not isinstance(value, list):
        violations.append("$.rules: must be a list")
        return
    if not value:
        violations.append("$.rules: must contain at least one rule")
    if len(value) > MAX_RULES:
        violations.append(f"$.rules: must contain at most {MAX_RULES} rules")
    seen_ids: set[str] = set()
    total_literal_bytes = 0
    for i, rule in enumerate(value):
        path = f"$.rules[{i}]"
        if not isinstance(rule, dict):
            violations.append(f"{path}: must be an object")
            continue
        _check_keys(path, rule, ALLOWED_RULE_KEYS, ALLOWED_RULE_KEYS, violations)
        rule_id = rule.get("id")
        if _check_bounded_string(f"{path}.id", rule_id, MAX_ID_BYTES, violations) is not None and rule_id in seen_ids:
            violations.append(f"{path}.id: duplicate rule id {rule_id!r}")
        if isinstance(rule_id, str):
            seen_ids.add(rule_id)
        if rule.get("field") != "surface":
            violations.append(f"{path}.field: must be 'surface'")
        if rule.get("operator") not in ALLOWED_OPERATORS:
            violations.append(f"{path}.operator: unsupported operator {rule.get('operator')!r}")
        literal_bytes = _check_bounded_string(f"{path}.literal", rule.get("literal"), MAX_LITERAL_BYTES, violations)
        if literal_bytes is not None:
            total_literal_bytes += literal_bytes
        _check_bounded_string(f"{path}.signal", rule.get("signal"), MAX_SIGNAL_BYTES, violations)
        _check_confidence(f"{path}.confidence", rule.get("confidence"), violations)
    if total_literal_bytes > MAX_TOTAL_LITERAL_BYTES:
        violations.append(f"$.rules: total literal bytes must be <= {MAX_TOTAL_LITERAL_BYTES}")


def _validate_decision(value: Any, rules: Any, violations: list[str]) -> None:
    if not isinstance(value, dict):
        violations.append("$.decision: must be an object")
        return
    _check_keys(
        "$.decision",
        value,
        {"block_when", "reason", "confidence_strategy", "matched_signals"},
        ALLOWED_DECISION_KEYS,
        violations,
    )
    block_when = value.get("block_when")
    if block_when not in ALLOWED_BLOCK_WHEN:
        violations.append("$.decision.block_when: unsupported decision mode")
    _check_bounded_string("$.decision.reason", value.get("reason"), MAX_REASON_BYTES, violations)
    if value.get("matched_signals") != "matched_rule_signals":
        violations.append("$.decision.matched_signals: must be 'matched_rule_signals'")
    rule_count = len(rules) if isinstance(rules, list) else None
    minimum_match_count = value.get("minimum_match_count")
    if block_when == "minimum_match_count":
        if "minimum_match_count" not in value:
            violations.append(
                "$.decision.minimum_match_count: required when block_when is 'minimum_match_count'"
            )
        else:
            _check_minimum_match_count(
                "$.decision.minimum_match_count",
                minimum_match_count,
                rule_count,
                violations,
            )
    elif "minimum_match_count" in value:
        violations.append(
            "$.decision.minimum_match_count: allowed only when block_when is 'minimum_match_count'"
        )
    strategy = value.get("confidence_strategy")
    if not isinstance(strategy, dict):
        violations.append("$.decision.confidence_strategy: must be an object")
        return
    _check_keys("$.decision.confidence_strategy", strategy, {"type"}, ALLOWED_CONFIDENCE_STRATEGY_KEYS, violations)
    if strategy.get("type") not in ALLOWED_CONFIDENCE_STRATEGIES:
        violations.append("$.decision.confidence_strategy.type: unsupported strategy")
    for key, item in strategy.items():
        if key == "type":
            continue
        if key == "minimum_match_count":
            _check_positive_int(f"$.decision.confidence_strategy.{key}", item, violations)
        else:
            _check_confidence(f"$.decision.confidence_strategy.{key}", item, violations)


def _validate_fallback(value: Any, violations: list[str]) -> None:
    if not isinstance(value, dict):
        violations.append("$.fallback: must be an object")
        return
    _check_keys("$.fallback", value, ALLOWED_FALLBACK_KEYS, ALLOWED_FALLBACK_KEYS, violations)
    if value.get("blocked") is not False:
        violations.append("$.fallback.blocked: must be false")
    _check_bounded_string("$.fallback.reason", value.get("reason"), MAX_REASON_BYTES, violations)
    _check_confidence("$.fallback.confidence", value.get("confidence"), violations)
    signals = value.get("matched_signals")
    if not isinstance(signals, list):
        violations.append("$.fallback.matched_signals: must be a list")
    elif signals:
        violations.append("$.fallback.matched_signals: must be an empty list")


def _check_keys(path: str, obj: dict, required: set[str], allowed: set[str], violations: list[str]) -> None:
    for key in sorted(required - obj.keys()):
        violations.append(f"{path}: missing required key {key!r}")
    for key in sorted(obj.keys() - allowed):
        violations.append(f"{path}: unexpected key {key!r}")


def _check_unique_string_list(path: str, value: Any, allowed: set[str], violations: list[str]) -> None:
    if not isinstance(value, list):
        violations.append(f"{path}: must be a list")
        return
    seen: set[str] = set()
    for i, item in enumerate(value):
        item_path = f"{path}[{i}]"
        if not isinstance(item, str):
            violations.append(f"{item_path}: must be a string")
            continue
        if item not in allowed:
            violations.append(f"{item_path}: unsupported value {item!r}")
        if item in seen:
            violations.append(f"{item_path}: duplicate value {item!r}")
        seen.add(item)


def _check_positive_int_map(path: str, value: Any, allowed_keys: set[str], violations: list[str]) -> None:
    if not isinstance(value, dict):
        violations.append(f"{path}: must be an object")
        return
    _check_keys(path, value, allowed_keys, allowed_keys, violations)
    for key, item in value.items():
        _check_positive_int(f"{path}.{key}", item, violations)


def _check_positive_int(path: str, value: Any, violations: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value > MAX_BOUND_VALUE:
        violations.append(f"{path}: must be a positive integer <= {MAX_BOUND_VALUE}")


def _check_body_scan_bytes(path: str, value: Any, violations: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        violations.append(f"{path}: must be an integer")
        return
    if value < MIN_BODY_SCAN_BYTES:
        violations.append(
            f"{path}: must be >= {MIN_BODY_SCAN_BYTES} "
            "to preserve large-body coverage"
        )
    if value > MAX_BOUND_VALUE:
        violations.append(f"{path}: must be <= {MAX_BOUND_VALUE}")


def _check_minimum_match_count(
    path: str,
    value: Any,
    rule_count: int | None,
    violations: list[str],
) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        violations.append(f"{path}: must be an integer")
        return
    if value < 1:
        violations.append(f"{path}: must be >= 1")
    if rule_count is not None and value > rule_count:
        violations.append(f"{path}: must be <= number of rules ({rule_count})")


def _check_confidence(path: str, value: Any, violations: list[str]) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        violations.append(f"{path}: must be a finite number in [0.0, 1.0]")


def _check_bounded_string(path: str, value: Any, max_bytes: int, violations: list[str]) -> int | None:
    if not isinstance(value, str):
        violations.append(f"{path}: must be a string")
        return None
    if not value:
        violations.append(f"{path}: must be non-empty")
        return None
    byte_length = _utf8_len(path, value, violations)
    if byte_length is None:
        return None
    if byte_length > max_bytes:
        violations.append(f"{path}: must be at most {max_bytes} bytes")
        return None
    return byte_length


def _utf8_len(path: str, value: str, violations: list[str]) -> int | None:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        violations.append(f"{path}: must be valid UTF-8 encodable text")
        return None
