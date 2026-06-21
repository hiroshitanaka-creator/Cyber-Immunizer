"""Owner/auditor-facing evolution report for Cyber-Immunizer.

This module is intentionally read-only. It summarizes internal symbolic-corpus
fitness history for repository checkout validation and does not claim external
user value, real-world defensive value, or production WAF suitability.
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
_MEASURED_COLUMNS = (
    "generation",
    "score",
    "tp_rate",
    "fp_rate",
    "fn_rate",
    "total_cases",
    "passed_adoption_gate",
)
_PROTECTED_REPO_PATHS = (
    "data",
    "core",
    "scripts",
    ".github",
    "docs",
    "README.md",
    "pyproject.toml",
)
# Entries treated as whole protected directories (anything inside is protected).
_PROTECTED_REPO_DIRS = frozenset({"data", "core", "scripts", ".github", "docs"})

# Generation 1 and Generation 2 were scored with an older fitness formula.
# Generation 3 onward use the post-migration / generation-invariant score.
# Measured score deltas must only compare same-schema (post-migration) records,
# so the migration boundary is the first post-migration generation.
_SCHEMA_MIGRATION_GENERATION = 3
_SCORE_DELTA_SUPPRESSED_MESSAGE = (
    "Score delta suppressed: score schema changed before Generation 3."
)


class ReportError(ValueError):
    """Raised for user-correctable report generation errors."""


def _load_history(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ReportError(f"Expected list in {path}")
    generations: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ReportError(f"Expected object entries in {path}")
        if "generation" not in entry:
            raise ReportError(f"History entry missing generation in {path}")
        generations.append(entry)
    return sorted(generations, key=lambda item: int(item["generation"]))


def _select_generation(history: Sequence[dict[str, Any]], generation: int) -> dict[str, Any]:
    for entry in history:
        if int(entry["generation"]) == generation:
            return entry
    raise ReportError(f"Generation {generation} not found in evolution history")


def _has_numeric_score(entry: dict[str, Any]) -> bool:
    score = entry.get("score")
    return isinstance(score, (int, float)) and not isinstance(score, bool)


def _same_schema_measured(history: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return post-migration generations carrying a numeric score, ordered by generation.

    Generation 0 (unevaluated placeholder) and pre-migration generations
    (older fitness formula) are excluded so measured deltas never compare
    incompatible score scales.
    """
    records: list[dict[str, Any]] = []
    for entry in history:
        if int(entry["generation"]) < _SCHEMA_MIGRATION_GENERATION:
            continue
        if not _has_numeric_score(entry):
            continue
        records.append(entry)
    return records


def _schema_basis(entry: dict[str, Any]) -> str:
    generation = int(entry["generation"])
    if generation == 0:
        return "unevaluated placeholder"
    if generation < _SCHEMA_MIGRATION_GENERATION:
        return "pre-migration lineage"
    return "post-migration (same-schema)"


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _score_for_display(entry: dict[str, Any]) -> str:
    if int(entry["generation"]) == 0:
        return "unevaluated placeholder"
    return _format_value(entry.get("score"))


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


def _resolve_repo_root(repo_root: Path | None, history_path: Path | None) -> Path:
    if repo_root is not None:
        return repo_root.expanduser().resolve()
    if history_path is not None:
        expanded = history_path.expanduser().resolve()
        if expanded.name == "evolution_history.json" and expanded.parent.name == "data":
            return expanded.parent.parent.resolve()
        raise ReportError("--repo-root is required when --history-path is not data/evolution_history.json")
    raise ReportError("Provide --repo-root or --history-path for repository-checkout validation")


def _resolve_history_path(repo_root: Path, history_path: Path | None) -> Path:
    if history_path is not None:
        return history_path.expanduser().resolve()
    return (repo_root / "data" / "evolution_history.json").resolve()


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return str(resolved)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_protected_export_path(export_path: Path, repo_root: Path) -> bool:
    resolved = export_path.expanduser().resolve()
    root = repo_root.expanduser().resolve()
    for protected in _PROTECTED_REPO_PATHS:
        protected_path = (root / protected).resolve()
        if protected_path.is_dir() or protected in _PROTECTED_REPO_DIRS:
            if _is_within(resolved, protected_path):
                return True
        elif resolved == protected_path:
            return True
    return False


def _write_export(path: Path, markdown: str, repo_root: Path) -> None:
    if _is_protected_export_path(path, repo_root):
        raise ReportError(
            f"Refusing to export into protected repository path: {_relative_to_repo(path, repo_root)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def build_markdown(*, repo_root: Path | None = None, history_path: Path | None = None) -> str:
    """Build a portable Markdown validation report from evolution history only."""
    resolved_repo_root = _resolve_repo_root(repo_root, history_path)
    resolved_history_path = _resolve_history_path(resolved_repo_root, history_path)
    history = _load_history(resolved_history_path)
    placeholder = _select_generation(history, 0)
    same_schema = _same_schema_measured(history)

    lines = [
        "# Cyber-Immunizer Owner/Auditor Evolution Validation Report",
        "",
        "This read-only report summarizes internal symbolic-corpus evolution evidence for Owner/auditor validation only.",
        "It does not prove real-world defensive value, does not connect to real traffic, and does not validate production WAF suitability.",
        "Externalization remains blocked until Layer 2 value validation is satisfied.",
        "",
        f"Source: `{_relative_to_repo(resolved_history_path, resolved_repo_root)}`",
        "",
        "## Score Schema Note",
        "",
        "Score schema note: Scores before the Generation 3 score-schema migration are historical "
        "lineage values and are not directly comparable with post-migration scores. Measured score "
        "deltas are reported only for same-schema records.",
        "",
        "- Generation 0 is an unevaluated placeholder.",
        "- Pre-migration scores (Generation 1 and Generation 2) are historical lineage only.",
        "- Cross-schema score deltas are not measured improvement.",
        "- The default measured score comparison uses same-schema (post-migration) records only.",
        "- Current internal symbolic-corpus evidence still does not prove real-world defensive value.",
        "",
        "## Default Scored Comparison",
        "",
    ]
    if len(same_schema) >= 2:
        before = same_schema[0]
        after = same_schema[-1]
        lines.extend([
            f"Measured score deltas use same-schema generations only "
            f"(Generation {before['generation']} -> Generation {after['generation']}). "
            "Generation 0 is excluded as an unevaluated placeholder, and pre-migration "
            "generations are excluded because their scores use an incompatible formula.",
            "",
            f"| Metric | Gen {before['generation']} measured baseline | Gen {after['generation']} current | Delta |",
            "|---|---:|---:|---:|",
        ])
        for field in _MEASURED_COLUMNS:
            lines.append(
                "| "
                f"{_metric_label(field)} | "
                f"{_format_value(before.get(field))} | "
                f"{_format_value(after.get(field))} | "
                f"{_delta(before, after, field)} |"
            )
    else:
        lines.extend([
            _SCORE_DELTA_SUPPRESSED_MESSAGE,
            "",
            "Fewer than two same-schema (post-migration) generations with numeric scores are "
            "available, so a measured score delta is not reported. Pre-migration scores remain "
            "visible below as historical lineage only.",
        ])

    lines.extend([
        "",
        "## Generation 0 Placeholder",
        "",
        "Generation 0 is retained for lineage only. Its score is unavailable/placeholder and is excluded from measured improvement deltas.",
        "",
        "| Generation | Score status | Gate | Promoted at | Note |",
        "|---:|---|---|---|---|",
        "| "
        f"{_format_value(placeholder.get('generation'))} | "
        f"{_score_for_display(placeholder)} | "
        f"{_format_value(placeholder.get('passed_adoption_gate'))} | "
        f"{_format_value(placeholder.get('promoted_at'))} | "
        f"{_format_value(placeholder.get('note'))} |",
        "",
        "## Generation Evidence",
        "",
        "Pre-migration generations are shown for lineage only and are not used for measured score deltas.",
        "",
        "| Generation | Score | Schema basis | TP rate | FP rate | FN rate | Cases | Gate | Promoted at |",
        "|---:|---|---|---:|---:|---:|---:|---|---|",
    ])
    for entry in history:
        lines.append(
            "| "
            f"{_format_value(entry.get('generation'))} | "
            f"{_score_for_display(entry)} | "
            f"{_schema_basis(entry)} | "
            f"{_format_value(entry.get('tp_rate'))} | "
            f"{_format_value(entry.get('fp_rate'))} | "
            f"{_format_value(entry.get('fn_rate'))} | "
            f"{_format_value(entry.get('total_cases'))} | "
            f"{_format_value(entry.get('passed_adoption_gate'))} | "
            f"{_format_value(entry.get('promoted_at'))} |"
        )

    missing = [field for field in _RATE_FIELDS if placeholder.get(field) is None]
    if missing:
        lines.extend([
            "",
            "Note: generation 0 predates exported FitnessReport rate fields, so gen0 rate deltas are not reported.",
        ])
    unknown_fields = sorted(
        set().union(*(entry.keys() for entry in history))
        - _REPORT_FIELDS
        - {"generation", "detector_hash", "promoted_at", "note"}
    )
    if unknown_fields:
        lines.extend([
            "",
            "Additional history-only fields observed: "
            + ", ".join(f"`{field}`" for field in unknown_fields)
            + ".",
        ])
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="python -m cli.report",
        description="Print a read-only Owner/auditor evolution validation report.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--repo-root",
        type=Path,
        help="Repository checkout root containing data/evolution_history.json.",
    )
    source_group.add_argument(
        "--history-path",
        type=Path,
        help="Explicit path to evolution_history.json for repository-checkout validation.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Write Markdown outside protected repository paths.",
    )
    args = parser.parse_args(args_list)

    try:
        repo_root = _resolve_repo_root(args.repo_root, args.history_path)
        markdown = build_markdown(repo_root=repo_root, history_path=args.history_path)
        if args.export is not None:
            _write_export(args.export, markdown, repo_root)
        else:
            print(markdown)
    except (OSError, ReportError, json.JSONDecodeError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
