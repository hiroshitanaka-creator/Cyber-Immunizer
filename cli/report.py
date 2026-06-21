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
    "README.md",
    "pyproject.toml",
    "docs/PROJECT_STATE.md",
    "docs/DEFINITION_OF_DONE.md",
    "docs/VALUE_DELIVERY_BLUEPRINT.md",
)
# Generations <= _PRE_MIGRATION_MAX_GENERATION were scored under the old formula
# that included -10.0 * changed_lines. This term was removed at generation 3
# (commit e8026cb, 2026-06-17) to make scores generation-invariant. Scores
# across this boundary are not directly comparable.
_PRE_MIGRATION_MAX_GENERATION = 2


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


def _current_generation(history: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        raise ReportError("Evolution history is empty")
    return max(history, key=lambda item: int(item["generation"]))


def _is_pre_migration(entry: dict[str, Any]) -> bool:
    gen = int(entry["generation"])
    return gen > 0 and gen <= _PRE_MIGRATION_MAX_GENERATION


def _first_same_schema_measured_generation(
    history: Sequence[dict[str, Any]], current_gen: int
) -> dict[str, Any] | None:
    """Return the first measured generation with the same score schema as current_gen, or None."""
    current_is_post = current_gen > _PRE_MIGRATION_MAX_GENERATION
    for entry in history:
        gen = int(entry["generation"])
        if gen == 0 or gen == current_gen:
            continue
        entry_is_post = gen > _PRE_MIGRATION_MAX_GENERATION
        if entry_is_post != current_is_post:
            continue
        if isinstance(entry.get("score"), (int, float)) and not isinstance(entry.get("score"), bool):
            return entry
    return None


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
    score_str = _format_value(entry.get("score"))
    if _is_pre_migration(entry):
        return f"{score_str} (pre-migration)"
    return score_str


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
        if protected_path.is_dir() or protected in {"data", "core", "scripts", ".github"}:
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
    after = _current_generation(history)
    same_schema_baseline = _first_same_schema_measured_generation(history, int(after["generation"]))

    lines = [
        "# Cyber-Immunizer Owner/Auditor Evolution Validation Report",
        "",
        "This read-only report summarizes internal symbolic-corpus evolution evidence for Owner/auditor validation only.",
        "It does not prove real-world defensive value, does not connect to real traffic, and does not validate production WAF suitability.",
        "Externalization remains blocked until Layer 2 value validation is satisfied.",
        "",
        f"Source: `{_relative_to_repo(resolved_history_path, resolved_repo_root)}`",
        "",
        "## Default Scored Comparison",
        "",
        "Scored comparison uses same-schema generations only. Generation 0 is an unevaluated placeholder sentinel."
        " Pre-migration generations (1–2) used a different score formula and are not included in the scored comparison."
        " See Score-Schema Migration below.",
        "",
    ]

    if same_schema_baseline is None:
        lines.extend([
            "No same-schema baseline available for the current generation."
            " All previous measured generations used the pre-migration score formula."
            " Cross-schema comparison is not shown.",
            "",
        ])
    else:
        lines.extend([
            f"| Metric | Gen {same_schema_baseline['generation']} same-schema baseline | Gen {after['generation']} current | Delta |",
            "|---|---:|---:|---:|",
        ])
        for field in _MEASURED_COLUMNS:
            lines.append(
                "| "
                f"{_metric_label(field)} | "
                f"{_format_value(same_schema_baseline.get(field))} | "
                f"{_format_value(after.get(field))} | "
                f"{_delta(same_schema_baseline, after, field)} |"
            )
        lines.append("")

    lines.extend([
        "## Score-Schema Migration",
        "",
        "The fitness score formula was updated at generation 3 (commit `e8026cb`, 2026-06-17).",
        "The `changed_lines` penalty (`-10.0 * changed_lines`) was removed to make scores generation-invariant.",
        "Scores from generation 1–2 (pre-migration formula) are not directly comparable with generation 3+ (post-migration formula).",
        "Cross-schema score deltas are suppressed in the Default Scored Comparison section above.",
        "Pre-migration generations are retained as historical lineage in the Generation Evidence table below.",
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
        "| Generation | Score | TP rate | FP rate | FN rate | Cases | Gate | Promoted at |",
        "|---:|---|---:|---:|---:|---:|---|---|",
    ])
    for entry in history:
        lines.append(
            "| "
            f"{_format_value(entry.get('generation'))} | "
            f"{_score_for_display(entry)} | "
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

    scored_gens = [
        e for e in history
        if e.get("tp_rate") is not None and e.get("fp_rate") is not None
    ]
    if scored_gens and all(
        e.get("tp_rate") == 1.0 and e.get("fp_rate") == 0.0
        for e in scored_gens
    ):
        _score_interp_lead = (
            "**All scored generations show tp_rate=1.0000 and fp_rate=0.0000.** This is expected:"
            " the test corpus uses symbolic indicator tokens (e.g., `path_traversal_indicator`) and"
            " the detector matches those same tokens. Perfect symbolic-corpus detection is by design,"
            " not evidence of realistic threat coverage."
        )
    else:
        _score_interp_lead = (
            "Scored generations show varying TP/FP/FN rates. Review the Generation Evidence table"
            " above. Rates below 1.0/0.0 may indicate corpus cases the current detector does not"
            " fully match."
        )

    lines.extend([
        "",
        "## Score Interpretation",
        "",
        _score_interp_lead,
        "",
        "The fitness score formula is:",
        "",
        "```",
        "score = 1000*tp_rate − 2000*fp_rate − 1500*fn_rate − 50*exceptions − 0.02*code_chars",
        "```",
        "",
        "When tp_rate=1.0 and fp_rate=fn_rate=0 across all scored generations, the score"
        " improvement between generations reflects **code size reduction only** (−0.02 × code_chars)."
        " The generation 3→4 delta is attributable to the LLM producing a more compact implementation,"
        " not to improved threat detection capability.",
        "",
        "This is not a bug in the evolution loop. It is the expected research-foundation result"
        " (Layer 1 complete). The symbolic corpus confirms that the mutation pipeline functions"
        " correctly end-to-end (propose → apply → evaluate → promote). What remains is Layer 2"
        " value validation: demonstrating detection capability against realistic threat patterns.",
        "",
        "## Layer 2 Gap",
        "",
        "Layer 2 value validation (DEFINITION_OF_DONE.md L2-V1 through L2-V5) requires:",
        "",
        "1. **Realistic threat coverage** (L2-V1) — evaluation against realistic but safely neutralized"
        " threat categories, not symbolic-only corpus.",
        "2. **Per-category TP/FP/FN and latency reporting** (L2-V2) — path-traversal, XSS, SQLi,"
        " and command delimiter categories evaluated separately, with latency data.",
        "3. **Holdout / drift / counterfactual evaluation** (L2-V3) — overfitting risk addressed by"
        " evaluating on holdout, drift, and counterfactual request sets; pass rates reported.",
        "4. **Improvement explanation** (L2-V4) — documentation of which threat classes improved"
        " and why.",
        "5. **No overfitting claim** (L2-V5) — results must distinguish symbolic corpus performance"
        " from realistic threat coverage.",
        "",
        "**Current status:** Layer 2 criteria are not yet satisfied. The symbolic corpus score"
        " (generation 4: 948.04) is research-foundation evidence, not defensive value evidence.",
        "",
        "**Path forward:** Use `cli/structured_eval` with Owner-supplied realistic (but safely"
        " neutralized) rules and corpus files outside the repository:",
        "",
        "```bash",
        "python -m cli.structured_eval \\",
        "  --rules /path/to/owner/realistic_rules.json \\",
        "  --corpus /path/to/owner/realistic_corpus.json",
        "```",
        "",
        "See `fixtures/README.md` for the rules document schema and corpus format.",
        "",
    ])
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
