"""core/detector.py — Stable detector interface for Project Cyber-Immunizer.

SAFETY NOTICE
=============
Only the region between MUTATION_START and MUTATION_END may be modified by
automated mutation tools.  Everything outside those markers is part of the
stable interface contract and must remain unchanged.

ALLOWED IMPORTS (inside mutation region):  none — only the two imports below
are permitted in this file.
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
    # --- mutated detector logic (sample) ---
    surface_parts = [
        request.method.lower(),
        request.path.lower(),
        " ".join(f"{k}={v}" for k, v in request.query.items()).lower(),
        " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower(),
        request.body.lower(),
    ]
    surface = " ".join(surface_parts)

    _SUSPICIOUS_TOKENS: tuple[str, ...] = (
        # path-traversal
        "../", "..\\", "%2e%2e%2f", "%2e%2e/",
        # script-injection
        "<script", "javascript:", "onerror=", "onload=",
        # SQL-like
        "\' or \'1\'=\'1", "union select", "drop table", "\'; --",
        "insert into", "select * from", "delete from",
        # command-like
        "; ls ", "| cat ", "`id`", "$(id)",
        # encoded
        "%00", "%0d%0a",
    )

    matched: list[str] = []
    for token in _SUSPICIOUS_TOKENS:
        if token in surface:
            matched.append(token)

    if matched:
        confidence = min(1.0, 0.4 + 0.15 * len(matched))
        return DetectionResult(
            blocked=True,
            reason=f"suspicious pattern(s) matched: {matched[0]!r}",
            confidence=confidence,
            matched_signals=tuple(matched),
        )

    return DetectionResult(
        blocked=False,
        reason="no suspicious pattern matched",
        confidence=0.0,
        matched_signals=(),
    )
# === MUTATION_END ===
