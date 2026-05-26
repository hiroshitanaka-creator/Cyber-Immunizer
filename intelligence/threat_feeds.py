"""intelligence/threat_feeds.py — Safe placeholder threat intelligence module.

SAFETY NOTICE
=============
This module does NOT fetch live data during tests.
It does NOT download exploit code.
It does NOT store exploit payloads.
It does NOT generate offensive proof-of-concept code.

The NVD/CVE fetch stub is permanently disabled and may only be enabled
after a future security review.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

_DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass(frozen=True)
class ThreatRecord:
    """A normalised threat intelligence record.

    All fields are plain strings; no executable or exploit payloads.
    """

    id: str
    source: str
    summary: str
    defensive_focus: str
    created_at: str

    # Allowed defensive_focus values — extend as needed.
    _ALLOWED_FOCUSES: ClassVar[frozenset[str]] = frozenset(
        {
            "path-traversal",
            "path-traversal-encoded",
            "sqli",
            "xss",
            "cmdi",
            "generic",
        }
    )

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ThreatRecord.id must not be empty")
        if not self.summary:
            raise ValueError("ThreatRecord.summary must not be empty")


def load_active_threats(path: Path | None = None) -> list[ThreatRecord]:
    """Load threat records from data/active_threats.json.

    Returns an empty list on any read/parse error rather than raising,
    to avoid failing unrelated tests.
    """
    path = path or (_DATA_DIR / "active_threats.json")
    try:
        raw_list = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []

    records: list[ThreatRecord] = []
    for raw in raw_list:
        try:
            records.append(
                ThreatRecord(
                    id=str(raw.get("id", "")),
                    source=str(raw.get("source", "unknown")),
                    summary=str(raw.get("summary", "")),
                    defensive_focus=str(raw.get("defensive_focus", "generic")),
                    created_at=str(raw.get("created_at", "")),
                )
            )
        except (ValueError, KeyError):
            continue  # Skip malformed records silently

    return records


def get_threat_ids(path: Path | None = None) -> list[str]:
    """Return the list of threat IDs from the active threat feed."""
    return [r.id for r in load_active_threats(path)]


# ---------------------------------------------------------------------------
# DISABLED STUB — Future live feed integration
# ---------------------------------------------------------------------------
# The following function is intentionally disabled.  It may only be enabled
# after a security review, rate-limit policy, and secret management plan.
#
# def _fetch_nvd_cve_stub(cve_id: str) -> dict:
#     """DISABLED: Would fetch from NVD API.
#
#     NOT called from any test or production path.
#     No exploit payloads will be fetched or stored.
#     """
#     raise NotImplementedError(
#         "Live CVE fetching is disabled in this MVP.  "
#         "Enable only after security review."
#     )
