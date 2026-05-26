"""scripts/update_readme.py — Update the status block in README.md.

Only the region between:
    <!-- CYBER_IMMUNIZER_STATUS_START -->
    <!-- CYBER_IMMUNIZER_STATUS_END -->
is modified.  Everything outside that block is preserved byte-for-byte.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_README_PATH = _PROJECT_ROOT / "README.md"
_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_HISTORY_PATH = _PROJECT_ROOT / "data" / "evolution_history.json"
_THREATS_PATH = _PROJECT_ROOT / "data" / "active_threats.json"
_REPORT_PATH = _PROJECT_ROOT / ".cyber_immunizer" / "fitness_report.json"

_STATUS_START = "<!-- CYBER_IMMUNIZER_STATUS_START -->"
_STATUS_END = "<!-- CYBER_IMMUNIZER_STATUS_END -->"


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_status_block() -> str:
    genome = _load_json(_GENOME_PATH) or {}
    history = _load_json(_HISTORY_PATH) or []
    threats = _load_json(_THREATS_PATH) or []
    fitness: dict | None = None

    raw_report = _load_json(_REPORT_PATH)
    if isinstance(raw_report, dict):
        fitness = raw_report.get("fitness_report") or raw_report

    generation = genome.get("generation", 0)
    best_score = genome.get("best_score", "N/A")
    detector_hash = genome.get("current_detector_hash", "unknown")
    last_updated = genome.get("last_updated", "unknown")

    adoption_status = "⏳ Baseline (not yet evaluated)"
    if history:
        last = history[-1]
        if last.get("passed_adoption_gate"):
            adoption_status = f"✅ Passed (generation {last.get('generation', '?')})"
        else:
            reasons = last.get("rejection_reasons", [])
            adoption_status = f"❌ Failed — {reasons[0]!r}" if reasons else "❌ Failed"

    total_cases = "N/A"
    tp = fp = tn = fn = "N/A"
    if fitness:
        total_cases = fitness.get("total_cases", "N/A")
        tp = fitness.get("true_positive", "N/A")
        fp = fitness.get("false_positive", "N/A")
        tn = fitness.get("true_negative", "N/A")
        fn = fitness.get("false_negative", "N/A")

    threat_ids = " ".join(
        f"`{t.get('id', '?')}`" for t in threats
    ) if threats else "_none_"

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        _STATUS_START,
        "## 🧬 Cyber-Immunizer Status",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Generation | {generation} |",
        f"| Best Score | {best_score} |",
        f"| Detector Hash | `{detector_hash[:16]}…` |",
        f"| Last Updated | {last_updated} |",
        f"| Total Test Cases | {total_cases} |",
        f"| TP / FP / TN / FN | {tp} / {fp} / {tn} / {fn} |",
        f"| Adoption Gate | {adoption_status} |",
        f"| Active Threat IDs | {threat_ids} |",
        f"| Status Block Updated | {now} |",
        "",
        _STATUS_END,
    ]
    return "\n".join(lines)


def update_readme(readme_path: Path | None = None) -> bool:
    readme_path = readme_path or _README_PATH
    if not readme_path.exists():
        print(f"README not found: {readme_path}", file=sys.stderr)
        return False

    content = readme_path.read_text(encoding="utf-8")

    start_idx = content.find(_STATUS_START)
    end_idx = content.find(_STATUS_END)

    new_block = _build_status_block()

    if start_idx == -1 or end_idx == -1:
        # Append block at end
        new_content = content.rstrip("\n") + "\n\n" + new_block + "\n"
    else:
        # Replace existing block
        new_content = (
            content[:start_idx]
            + new_block
            + content[end_idx + len(_STATUS_END):]
        )

    readme_path.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    success = update_readme()
    if success:
        print("README status block updated.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
