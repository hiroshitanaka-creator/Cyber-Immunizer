"""Read-only evolution report CLI for Cyber-Immunizer.

The report converts internal evolution-history records into a portable
before/after summary without mutating genome, detector, ledger, or history data.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Sequence

from core.types import FitnessReport

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_HISTORY_PATH = _REPO_ROOT / "data" / "evolution_history.json"
_REPORT_FIELDS = {field.name for field in fields(FitnessReport)}
_RATE_FIELDS = ("tp_rate", "fp_rate", "fn_rate")
_REPORT_COLUMNS = (
    "generation",
    "score",
    "tp_rate",
    "fp_rate",
    "fn_rate",
    "total_cases",
    "passed_adoption_gate",
)


def _load_history(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    generations: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"Expected object entries in {path}")
        if "generation" not in entry:
            raise ValueError(f"History entry missing generation in {path}")
        generations.append(entry)
    return sorted(generations, key=lambda item: int(item["generation"]))


def _select_generation(history: Sequence[dict[str, Any]], generation: int) -> dict[str, Any]:
    for entry in history:
        if int(entry["generation"]) == generation:
            return entry
    raise ValueError(f"Generation {generation} not found in evolution history")


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _delta(before: dict[str, Any], after: dict[str, Any], field: str) -> str:
    before_value = before.get(field)
    after_value = after.get(field)
    if isinstance(before_value, bool) or isinstance(after_value, bool):
        return "n/a"
    if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)):
        return "n/a"
    change = after_value - before_value
    return f"{change:+.4f}"


def _metric_label(field: str) -> str:
    labels = {
        "generation": "Generation",
        "score": "Fitness score",
        "tp_rate": "Detection rate (TP)",
        "fp_rate": "False-positive rate",
        "fn_rate": "False-negative rate",
        "total_cases": "Evaluated cases",
        "passed_adoption_gate": "Adoption gate",
    }
    return labels[field]


def build_markdown(history_path: Path = _DEFAULT_HISTORY_PATH) -> str:
    """Build a portable Markdown report from evolution history only."""
    history = _load_history(history_path)
    before = _select_generation(history, 0)
    after = _select_generation(history, 4)

    lines = [
        "# Cyber-Immunizer Evolution Report",
        "",
        "Read-only summary of exported detection improvement evidence from generation 0 to generation 4.",
        "",
        f"Source: `{history_path.relative_to(_REPO_ROOT) if history_path.is_relative_to(_REPO_ROOT) else history_path}`",
        "",
        "## Before / After",
        "",
        "| Metric | Gen 0 before | Gen 4 after | Delta |",
        "|---|---:|---:|---:|",
    ]
    for field in _REPORT_COLUMNS:
        lines.append(
            "| "
            f"{_metric_label(field)} | "
            f"{_format_value(before.get(field))} | "
            f"{_format_value(after.get(field))} | "
            f"{_delta(before, after, field)} |"
        )

    lines.extend([
        "",
        "## Generation Evidence",
        "",
        "| Generation | Score | TP rate | FP rate | FN rate | Cases | Gate | Promoted at |",
        "|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for entry in history:
        lines.append(
            "| "
            f"{_format_value(entry.get('generation'))} | "
            f"{_format_value(entry.get('score'))} | "
            f"{_format_value(entry.get('tp_rate'))} | "
            f"{_format_value(entry.get('fp_rate'))} | "
            f"{_format_value(entry.get('fn_rate'))} | "
            f"{_format_value(entry.get('total_cases'))} | "
            f"{_format_value(entry.get('passed_adoption_gate'))} | "
            f"{_format_value(entry.get('promoted_at'))} |"
        )

    missing = [field for field in _RATE_FIELDS if before.get(field) is None]
    if missing:
        lines.extend([
            "",
            "Note: generation 0 predates exported FitnessReport rate fields, so rate deltas are reported as `n/a`.",
        ])
    unknown_fields = sorted(set().union(*(entry.keys() for entry in history)) - _REPORT_FIELDS - {"generation", "detector_hash", "promoted_at", "note"})
    if unknown_fields:
        lines.extend([
            "",
            "Additional history-only fields observed: " + ", ".join(f"`{field}`" for field in unknown_fields) + ".",
        ])
    lines.append("")
    return "\n".join(lines)


def _print_console(markdown: str) -> None:
    if importlib.util.find_spec("rich") is not None:
        from rich.console import Console
        from rich.markdown import Markdown

        Console().print(Markdown(markdown))
    else:
        print(markdown)


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] == "report":
        args_list = args_list[1:]

    parser = argparse.ArgumentParser(
        prog="cyber-immunize report",
        description="Print a read-only gen0→gen4 detection improvement report.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Write the report as Markdown to the given path.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=_DEFAULT_HISTORY_PATH,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(args_list)

    markdown = build_markdown(args.history)
    if args.export is not None:
        args.export.write_text(markdown, encoding="utf-8")
    else:
        _print_console(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
