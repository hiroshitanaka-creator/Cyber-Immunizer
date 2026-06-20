"""Deterministic evaluator for validated structured detector rule documents.

This module is intentionally separate from ``core.detector``. It interprets the
constrained rule shape validated by ``core.structured_validator`` and returns a
``DetectionResult`` without file, network, environment, randomness, or dynamic
code execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.structured_validator import validate_rules_schema
from core.types import DetectionResult, Request

_DEFAULT_FALLBACK_REASON = "structured rules fallback"
_DEFAULT_FALLBACK_CONFIDENCE = 0.0


def evaluate_structured_rules(request: Request, rules_doc: dict) -> DetectionResult:
    """Evaluate a structured rules document against a request.

    Validation failures, no-match outcomes, and evaluator errors all return the
    document's non-blocking fallback when it is safe to construct, otherwise a
    conservative built-in non-blocking fallback.
    """
    try:
        validation = validate_rules_schema(rules_doc)
        if validation.get("success") is not True:
            return _fallback_result(rules_doc)

        surface = _extract_surface(request, rules_doc)
        if surface is None:
            return _fallback_result(rules_doc)

        matched_rules: list[dict[str, Any]] = []
        for rule in rules_doc["rules"]:
            if _rule_matches(rule, surface, "lowercase" in rules_doc["features"]["surface"]["normalization"]):
                matched_rules.append(rule)

        if not _decision_blocks(rules_doc["decision"], len(rules_doc["rules"]), len(matched_rules)):
            return _fallback_result(rules_doc)

        matched_signals = tuple(str(rule["signal"]) for rule in matched_rules)
        confidence = _confidence(rules_doc["decision"]["confidence_strategy"], matched_rules)
        return DetectionResult(
            blocked=True,
            reason=rules_doc["decision"]["reason"],
            confidence=confidence,
            matched_signals=matched_signals,
        )
    except Exception:
        return _fallback_result(rules_doc)


def _fallback_result(rules_doc: Any) -> DetectionResult:
    fallback = rules_doc.get("fallback", {}) if isinstance(rules_doc, dict) else {}
    reason = fallback.get("reason", _DEFAULT_FALLBACK_REASON)
    confidence = fallback.get("confidence", _DEFAULT_FALLBACK_CONFIDENCE)
    if type(reason) is not str:
        reason = _DEFAULT_FALLBACK_REASON
    if type(confidence) is bool or type(confidence) not in (int, float):
        confidence = _DEFAULT_FALLBACK_CONFIDENCE
    try:
        return DetectionResult(blocked=False, reason=reason, confidence=confidence, matched_signals=())
    except Exception:
        return DetectionResult(
            blocked=False,
            reason=_DEFAULT_FALLBACK_REASON,
            confidence=_DEFAULT_FALLBACK_CONFIDENCE,
            matched_signals=(),
        )


def _extract_surface(request: Request, rules_doc: dict) -> tuple[str, ...] | None:
    surface_config = rules_doc["features"]["surface"]
    fields = set(surface_config["fields"])
    lowercase = "lowercase" in surface_config["normalization"]
    scalar_limits = surface_config["max_scalar_bytes"]
    collection_limits = surface_config["max_collection_entries"]
    body_limit = surface_config["body_scan"]["max_bytes"]

    parts: list[str] = []
    if "method" in fields:
        parts.append(_normalize(_bounded_text(request.method, scalar_limits["method"]), lowercase))
    if "path" in fields:
        parts.append(_normalize(_bounded_text(request.path, scalar_limits["path"]), lowercase))
    if "query.keys" in fields or "query.values" in fields:
        _append_mapping_parts(
            parts,
            request.query,
            collection_limits["query"],
            scalar_limits["query.item"],
            include_keys="query.keys" in fields,
            include_values="query.values" in fields,
            lowercase=lowercase,
        )
    if "headers.keys" in fields or "headers.values" in fields:
        _append_mapping_parts(
            parts,
            request.headers,
            collection_limits["headers"],
            scalar_limits["header.item"],
            include_keys="headers.keys" in fields,
            include_values="headers.values" in fields,
            lowercase=lowercase,
        )
    if "body" in fields:
        parts.append(_normalize(_bounded_text(request.body, body_limit), lowercase))
    if any(part is None for part in parts):
        return None
    return tuple(parts)


def _append_mapping_parts(
    parts: list[str | None],
    mapping: Mapping[str, str],
    max_entries: int,
    max_bytes: int,
    *,
    include_keys: bool,
    include_values: bool,
    lowercase: bool,
) -> None:
    for index, (key, value) in enumerate(mapping.items()):
        if index >= max_entries:
            break
        if include_keys:
            parts.append(_normalize(_bounded_text(key, max_bytes), lowercase))
        if include_values:
            parts.append(_normalize(_bounded_text(value, max_bytes), lowercase))


def _bounded_text(value: Any, max_bytes: int) -> str | None:
    if type(value) is not str:
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _normalize(value: str | None, lowercase: bool) -> str | None:
    if value is None:
        return None
    if lowercase:
        return value.lower()
    return value


def _rule_matches(rule: dict[str, Any], surface: tuple[str, ...], lowercase: bool) -> bool:
    literal = rule["literal"].lower() if lowercase else rule["literal"]
    operator = rule["operator"]
    if operator == "contains_literal":
        return any(literal in item for item in surface)
    if operator == "equals_literal":
        return any(literal == item for item in surface)
    if operator == "starts_with_literal":
        return any(item.startswith(literal) for item in surface)
    if operator == "ends_with_literal":
        return any(item.endswith(literal) for item in surface)
    return False


def _decision_blocks(decision: dict[str, Any], rule_count: int, match_count: int) -> bool:
    block_when = decision["block_when"]
    if block_when == "any_rule_matches":
        return match_count > 0
    if block_when == "all_rules_match":
        return match_count == rule_count
    if block_when == "minimum_match_count":
        threshold = decision["minimum_match_count"]
        return 1 <= threshold <= rule_count and match_count >= threshold
    return False


def _confidence(strategy: dict[str, Any], matched_rules: list[dict[str, Any]]) -> float:
    strategy_type = strategy["type"]
    if strategy_type == "maximum_matched_confidence":
        return max(float(rule["confidence"]) for rule in matched_rules)
    if strategy_type == "bounded_match_count":
        match_count = len(matched_rules)
        if match_count >= 3:
            return float(strategy.get("three_or_more_matches", strategy["default"]))
        if match_count == 2:
            return float(strategy.get("two_matches", strategy["default"]))
    return float(strategy["default"])
