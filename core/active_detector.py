"""core/active_detector.py — Resolve and invoke the currently active detector.

This module provides a single runtime entry point that dispatches to the
detector configured as active in ``data/genome.json``:

- ``detector_mode == "legacy"`` (default): the promoted Python detector
  ``core.detector.inspect_request``.
- ``detector_mode == "structured_rules"``: the validated active structured rules
  document, evaluated through ``core.runtime_selector`` in structured-rules mode.

Design contract (mirrors ``core.detector.inspect_request``):

- Never raises. Never returns ``bool``. Always returns a ``DetectionResult``.
- **Fail-safe to legacy**: if structured mode is configured but the genome or the
  active rules document cannot be read or validated, this falls back to the
  legacy Python detector (a known-good, deterministic path) rather than failing.
  The structured evaluator itself already returns a non-blocking fallback on
  malformed rules; falling back to the legacy detector here preserves the
  promoted baseline behavior when the active-rules configuration is unusable.

No network, environment, randomness, or dynamic code execution is performed.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.detector import inspect_request
from core.runtime_selector import inspect_request_with_runtime_selector
from core.structured_validator import validate_rules_schema
from core.types import DetectionResult, Request

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DEFAULT_ACTIVE_RULES_PATH = _PROJECT_ROOT / "data" / "active_structured_rules.json"

# Reject pathologically large genome / rules files before reading.
_MAX_FILE_BYTES = 1_048_576


def _read_json_dict(path: Path) -> dict | None:
    """Read a JSON object from path, or return None on any failure.

    Returns None (rather than raising) so callers can fall back safely.
    """
    try:
        st = path.stat()
        if st.st_size > _MAX_FILE_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_mode(genome: dict | None) -> str:
    if not isinstance(genome, dict):
        return "legacy"
    mode = genome.get("detector_mode", "legacy")
    return mode if mode in ("legacy", "structured_rules") else "legacy"


def inspect_active(
    request: Request,
    *,
    genome_path: Path | None = None,
    active_rules_path: Path | None = None,
) -> DetectionResult:
    """Invoke the active detector as configured in the genome.

    Args:
        request: The request to evaluate.
        genome_path: Optional override for ``data/genome.json`` (tests).
        active_rules_path: Optional override for the active structured rules
            document. When omitted, the genome's ``active_structured_rules_path``
            is used, falling back to ``data/active_structured_rules.json``.

    Returns:
        A ``DetectionResult``. Falls back to the legacy detector if structured
        mode is configured but cannot be resolved.
    """
    genome = _read_json_dict(genome_path or _DEFAULT_GENOME_PATH)
    mode = _resolve_mode(genome)

    if mode == "legacy":
        return inspect_request(request)

    # mode == "structured_rules"
    if active_rules_path is not None:
        rules_path = active_rules_path
    elif isinstance(genome, dict) and isinstance(genome.get("active_structured_rules_path"), str):
        candidate = Path(genome["active_structured_rules_path"])
        rules_path = candidate if candidate.is_absolute() else _PROJECT_ROOT / candidate
    else:
        rules_path = _DEFAULT_ACTIVE_RULES_PATH

    rules_doc = _read_json_dict(rules_path)
    if rules_doc is None:
        return inspect_request(request)

    # Validation and dispatch share one fail-safe boundary: validate_rules_schema
    # can itself raise (e.g. OverflowError on an extreme numeric literal), so it
    # must be inside the try to preserve the "never raises" contract.
    try:
        if validate_rules_schema(rules_doc).get("success") is not True:
            return inspect_request(request)
        return inspect_request_with_runtime_selector(
            request, mode="structured_rules", structured_rules_doc=rules_doc
        )
    except Exception:
        return inspect_request(request)
