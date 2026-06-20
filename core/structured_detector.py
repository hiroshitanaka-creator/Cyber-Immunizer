"""Explicit opt-in adapter for structured detector rule evaluation.

This module intentionally does not integrate with ``core.detector``. Callers
must pass a ``Request`` and a parsed structured rules document directly to opt
in to structured rule evaluation.
"""
from __future__ import annotations

from core.structured_evaluator import evaluate_structured_rules
from core.types import DetectionResult, Request


def inspect_request_with_structured_rules(
    request: Request,
    rules_doc: dict,
) -> DetectionResult:
    """Evaluate ``request`` with an explicitly supplied structured rules doc.

    Invalid or malformed rules documents use the evaluator's non-blocking
    fallback behavior. The adapter performs no file, network, environment, or
    dynamic-code operations and does not mutate its inputs.
    """
    result = evaluate_structured_rules(request, rules_doc)
    if type(result) is DetectionResult:
        return result
    return DetectionResult(
        blocked=False,
        reason="structured rules fallback",
        confidence=0.0,
        matched_signals=(),
    )
