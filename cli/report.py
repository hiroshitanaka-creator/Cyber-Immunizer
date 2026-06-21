"""Owner/auditor-facing read-only evolution report CLI for Cyber-Immunizer.

The report summarizes internal symbolic-corpus evolution evidence for validation
review. It does not prove real-world defensive usefulness, does not connect to
real traffic, and does not validate production WAF suitability.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Sequence

from core.types import FitnessReport

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
_PROTECTED_DIRS = ("data", "core", "scripts", ".github")
_PROTECTED_FILES = (
    "README.md",
    "pyproject.toml",
    "docs/PROJECT_STATE.md",
    "docs/DEFINITION_OF_DONE.md",
    "docs/VALUE_DELIVERY_BLUEPRINT.md",
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


def _current_generation(history: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        raise ValueError("Evolution history is empty")
    return max(history, key=lambda entry: int(entry["generation"]))


def _first_measured_generation(history: Sequence[dict[str, Any]]) -> dict[str, Any]:
    measured = [
        entry
        for entry in history
        if int(entry["generation"]) > 0 and isinstance(entry.get("score"), (int, float))
    ]
    if not measured:
        raise ValueError("No measured generation with a score was found")
    return min(measured, key=lambda entry: int(entry["generation"]))


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _display_value(entry: dict[str, Any], field: str) -> str:
    if int(entry["generation"]) == 0 and field == "score":
        return "placeholder"
    return _format_value(entry.get(field))


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


def _relative_to_repo(path: Path, repo_root: Path) -> Path | None:
    resolved = path.resolve()
    root = repo_root.resolve()
    if resolved == root:
        return Path(".")
    if root in resolved.parents:
        return resolved.relative_to(root)
    return None


def _is_protected_export_path(export_path: Path, repo_root: Path) -> bool:
    raw_parts = export_path.parts
    if raw_parts and raw_parts[0] in _PROTECTED_DIRS:
        return True
    if export_path.as_posix() in _PROTECTED_FILES:
        return True

    relative = _relative_to_repo(export_path, repo_root)
    if relative is None:
        return False
    parts = relative.parts
    if not parts:
        return True
    if parts[0] in _PROTECTED_DIRS:
        return True
    return relative.as_posix() in _PROTECTED_FILES


def _history_source_label(history_path: Path, repo_root: Path | None) -> str:
    if repo_root is not None:
        relative = _relative_to_repo(history_path, repo_root)
        if relative is not None:
            return relative.as_posix()
    return str(history_path)


def build_markdown(history_path: Path, repo_root: Path | None = None) -> str:
    """Build a portable Markdown report from an explicit evolution-history path."""
    history = _load_history(history_path)
    measured_before = _first_measured_generation(history)
    current = _current_generation(history)
    generation_zero = next((entry for entry in history if int(entry["generation"]) == 0), None)

    lines = [
        "# Cyber-Immunizer Owner/Auditor Evolution Validation Report",
        "",
        "Layer 2 validation support: summarizes internal symbolic-corpus evolution evidence for Owner/auditor review only.",
        "It does not prove real-world defensive usefulness, does not connect to real traffic, does not validate production WAF suitability, and does not justify package distribution, public demos, dashboards, or GitHub Action templates.",
        "",
        f"Source: `{_history_source_label(history_path, repo_root)}`",
        "",
        f"## Measured Score Comparison: Gen {measured_before['generation']} → Gen {current['generation']}",
        "",
        "| Metric | Measured before | Current | Delta |",
        "|---|---:|---:|---:|",
    ]
    for field in _REPORT_COLUMNS:
        lines.append(
            "| "
            f"{_metric_label(field)} | "
            f"{_display_value(measured_before, field)} | "
            f"{_display_value(current, field)} | "
            f"{_delta(measured_before, current, field)} |"
        )

    if generation_zero is not None:
        lines.extend([
            "",
            "## Generation 0 Placeholder",
            "",
            "Generation 0 is an unevaluated baseline placeholder. Its sentinel score is unavailable for measured improvement and is excluded from score deltas.",
            "",
            "| Generation | Score status | Gate | Promoted at |",
            "|---:|---|---|---|",
            "| "
            f"{_format_value(generation_zero.get('generation'))} | "
            "placeholder / unevaluated | "
            f"{_format_value(generation_zero.get('passed_adoption_gate'))} | "
            f"{_format_value(generation_zero.get('promoted_at'))} |",
        ])

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
            f"{_display_value(entry, 'score')} | "
            f"{_format_value(entry.get('tp_rate'))} | "
            f"{_format_value(entry.get('fp_rate'))} | "
            f"{_format_value(entry.get('fn_rate'))} | "
            f"{_format_value(entry.get('total_cases'))} | "
            f"{_format_value(entry.get('passed_adoption_gate'))} | "
            f"{_format_value(entry.get('promoted_at'))} |"
        )

    missing = [field for field in _RATE_FIELDS if generation_zero is not None and generation_zero.get(field) is None]
    if missing:
        lines.extend([
            "",
            "Note: generation 0 predates exported FitnessReport rate fields, so its rate values are reported as `n/a` and excluded from deltas.",
        ])
    unknown_fields = sorted(
        set().union(*(entry.keys() for entry in history))
        - _REPORT_FIELDS
        - {"generation", "detector_hash", "promoted_at", "note"}
    )
    if unknown_fields:
        lines.extend([
            "",
            "Additional history-only fields observed: " + ", ".join(f"`{field}`" for field in unknown_fields) + ".",
        ])
    lines.append("")
    return "\n".join(lines)


def _resolve_inputs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[Path, Path | None]:
    repo_root = args.repo_root.resolve() if args.repo_root is not None else None
    if args.history_path is None and repo_root is None:
        parser.error("report requires --repo-root or --history-path for Owner/auditor checkout validation")
    if args.history_path is not None:
        history_path = args.history_path.resolve()
    else:
        history_path = repo_root / "data" / "evolution_history.json"
    return history_path, repo_root


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] == "report":
        args_list = args_list[1:]

    parser = argparse.ArgumentParser(
        prog="python -m cli.report report",
        description="Print an Owner/auditor-facing read-only internal evolution validation report.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Repository checkout root; reads data/evolution_history.json below this path.",
    )
    parser.add_argument(
        "--history-path",
        type=Path,
        help="Explicit evolution_history.json path for checkout validation.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Write the report as Markdown to an unprotected path.",
    )
    args = parser.parse_args(args_list)

    history_path, repo_root = _resolve_inputs(args, parser)
    markdown = build_markdown(history_path, repo_root)
    if args.export is not None:
        protection_root = repo_root if repo_root is not None else Path.cwd()
        if _is_protected_export_path(args.export, protection_root):
            parser.error(f"refusing to overwrite protected repository path: {args.export}")
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
