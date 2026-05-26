"""core/detector.py — Stable detector interface for Project Cyber-Immunizer.

SAFETY NOTICE
=============
Only the region between MUTATION_START and MUTATION_END may be modified by
automated mutation tools.  Everything outside those markers is part of the
stable interface contract and must remain unchanged.

ALLOWED IMPORTS (inside mutation region):  none — only the import below
is permitted in this file.

TEST DATA NOTE
==============
Suspicious tokens use neutralized symbolic indicators (e.g.,
PATH_TRAVERSAL_INDICATOR) rather than raw exploit-looking strings.
Test request payloads in data/*.json use the same symbolic indicators
(uppercase in the JSON; lowercased at match time by the detector).
This keeps the test corpus free of copyable exploit patterns.
Double-underscore prefixes/suffixes are intentionally absent so that
LLM-generated replacement_code can reference these tokens without
triggering the dunder-access prohibition in _validate_replacement_code.
"""
from core.types import Request, DetectionResult


def inspect_request(request: Request) -> DetectionResult:
    """Evaluate a local simulated request and return a DetectionResult.

    This is the ONLY function an LLM mutation may modify, and only the
    internal logic between the mutation markers.

    Args:
        request: A frozen Request object (local simulation only).

    Returns:
        DetectionResult — never raises, never returns bool.
    """
    # === MUTATION_START ===
    # Normalise all textual fields into one lowercase inspection surface.
    surface_parts = [
        request.method.lower(),
        request.path.lower(),
        " ".join(f"{k}={v}" for k, v in request.query.items()).lower(),
        " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower(),
        request.body.lower(),
    ]
    surface = " ".join(surface_parts)

    # Neutralized symbolic indicators — not real exploit strings.
    # Test data in data/attack_requests.json and data/regression_cases.json
    # uses the same indicators (uppercase in JSON; lowercased at match time).
    # No double-underscore prefix/suffix — avoids conflict with the dunder
    # prohibition in _validate_replacement_code while remaining clearly
    # non-exploitable placeholder strings.
    _SUSPICIOUS_TOKENS: tuple[str, ...] = (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    )

    matched: list[str] = []
    for token in _SUSPICIOUS_TOKENS:
        if token in surface:
            matched.append(token)

    if matched:
        confidence = min(1.0, 0.4 + 0.15 * len(matched))
        return DetectionResult(
            blocked=True,
            reason=f"suspicious indicator matched: {matched[0]!r}",
            confidence=confidence,
            matched_signals=tuple(matched),
        )

    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
    # === MUTATION_END ===
