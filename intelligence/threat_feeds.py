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


def load_active_threats(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> list[ThreatRecord]:
    """Load threat records from data/active_threats.json.

    When strict=True (default), raises ValueError on malformed JSON, non-list
    top-level, non-dict records, empty IDs, empty summaries, unknown
    defensive_focus values, or duplicate IDs.  This prevents a poisoned feed
    from silently becoming an empty set.

    When strict=False, falls back to the legacy behaviour: returns an empty
    list on parse errors and skips malformed records silently.  Use only for
    backward-compatibility contexts where strict validation is not required.
    """
    path = path or (_DATA_DIR / "active_threats.json")

    if strict:
        return _load_active_threats_strict(path)
    return _load_active_threats_lenient(path)


def _load_active_threats_strict(path: Path) -> list[ThreatRecord]:
    """Strict loader — raises ValueError on any schema violation."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read threat feed {path}: {exc}") from exc
    try:
        raw_list = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in threat feed {path}: {exc}") from exc
    if not isinstance(raw_list, list):
        raise ValueError(
            f"Threat feed {path} top-level must be a JSON list, "
            f"got {type(raw_list).__name__!r}"
        )

    seen_ids: set[str] = set()
    records: list[ThreatRecord] = []
    for i, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            raise ValueError(
                f"Threat feed {path} record [{i}] must be dict, "
                f"got {type(raw).__name__!r}"
            )
        id_val = raw.get("id", "")
        if not isinstance(id_val, str) or not id_val:
            raise ValueError(
                f"Threat feed {path} record [{i}]: 'id' must be non-empty str, "
                f"got {id_val!r}"
            )
        if id_val in seen_ids:
            raise ValueError(
                f"Threat feed {path}: duplicate record id {id_val!r}"
            )
        seen_ids.add(id_val)

        summary = raw.get("summary", "")
        if not isinstance(summary, str) or not summary:
            raise ValueError(
                f"Threat feed {path} record {id_val!r}: 'summary' must be non-empty str"
            )

        df = raw.get("defensive_focus", "generic")
        if df not in ThreatRecord._ALLOWED_FOCUSES:
            raise ValueError(
                f"Threat feed {path} record {id_val!r}: "
                f"'defensive_focus' must be one of {sorted(ThreatRecord._ALLOWED_FOCUSES)}, "
                f"got {df!r}"
            )

        records.append(
            ThreatRecord(
                id=id_val,
                source=str(raw.get("source", "unknown")),
                summary=summary,
                defensive_focus=df,
                created_at=str(raw.get("created_at", "")),
            )
        )
    return records


def _load_active_threats_lenient(path: Path) -> list[ThreatRecord]:
    """Legacy lenient loader — returns [] on errors, skips malformed records."""
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
