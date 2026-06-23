"""scripts/rollback_to_legacy_detector.py — Revert the active detector to legacy.

Sets ``genome.detector_mode`` back to ``"legacy"`` and drops the
``active_structured_rules_*`` activation fields, so ``core.active_detector``
dispatches to the promoted Python detector again. The legacy detector and its
lineage (generation / best_score / current_detector_hash) are never modified,
so this is an instant, lossless rollback. Idempotent.

SAFETY: no network, no Gemini API, no candidate code execution. Touches only
data/genome.json.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"

_ACTIVE_FIELDS = (
    "active_structured_rules_path",
    "active_structured_rules_hash",
    "active_structured_rules_score",
    "active_structured_rules_promoted_at",
)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def rollback_to_legacy(genome_path: Path, *, as_json: bool = False) -> int:
    try:
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = f"could not read genome file: {exc}"
        print(json.dumps({"success": False, "reason": msg}, indent=2) if as_json
              else f"ERROR: {msg}", file=None if as_json else sys.stderr)
        return 1
    if not isinstance(genome, dict):
        msg = "genome.json top-level must be an object"
        print(json.dumps({"success": False, "reason": msg}, indent=2) if as_json
              else f"ERROR: {msg}", file=None if as_json else sys.stderr)
        return 1

    was_structured = genome.get("detector_mode") == "structured_rules"
    genome["detector_mode"] = "legacy"
    removed = [f for f in _ACTIVE_FIELDS if genome.pop(f, None) is not None]
    genome["last_updated"] = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    _atomic_write(genome_path, json.dumps(genome, indent=2) + "\n")

    result = {
        "success": True,
        "detector_mode": "legacy",
        "was_structured": was_structured,
        "removed_fields": removed,
    }
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Rolled back to legacy detector (was_structured={was_structured}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roll the active detector back to legacy.")
    parser.add_argument("--genome", default=None, metavar="PATH", help="Override genome.json path.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)
    genome_path = Path(args.genome) if args.genome else _DEFAULT_GENOME_PATH
    return rollback_to_legacy(genome_path, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
