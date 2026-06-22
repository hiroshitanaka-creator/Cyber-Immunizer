"""core/runtime_selector.py — Explicit runtime selector for detector mode.

This module provides a single explicit gate between the legacy detector path
and the structured-rules detector path.  Callers must supply both mode and
(for structured mode) an explicit rules document.  No environment variables,
file reads, network calls, or dynamic code execution are performed.
"""
from __future__ import annotations

from typing import Literal

from core.detector import inspect_request
from core.structured_detector import inspect_request_with_structured_rules
from core.types import DetectionResult, Request

DetectorRuntimeMode = Literal["legacy", "structured_rules"]


def inspect_request_with_runtime_selector(
    request: Request,
    *,
    mode: DetectorRuntimeMode = "legacy",
    structured_rules_doc: dict | None = None,
) -> DetectionResult:
    """Select and invoke a detector path based on explicit caller-supplied arguments.

    Args:
        request: The request to evaluate.
        mode: ``"legacy"`` (default) or ``"structured_rules"``.
        structured_rules_doc: Required when mode is ``"structured_rules"``;
            must be ``None`` when mode is ``"legacy"``.

    Returns:
        DetectionResult from the selected detector.

    Raises:
        ValueError: If mode and structured_rules_doc are inconsistent, or if
            mode is not a supported value.
    """
    if mode == "legacy":
        if structured_rules_doc is not None:
            raise ValueError("legacy mode does not accept structured_rules_doc")
        return inspect_request(request)

    if mode == "structured_rules":
        if structured_rules_doc is None:
            raise ValueError("structured_rules mode requires structured_rules_doc")
        return inspect_request_with_structured_rules(request, structured_rules_doc)

    raise ValueError(f"unsupported detector runtime mode: {mode!r}")
