"""Owner/auditor-facing structured rules evaluation CLI for Cyber-Immunizer.

Usage:
    python -m cli.structured_eval --rules <rules.json> --corpus <corpus.json>
    python -m cli.structured_eval --rules <rules.json> --corpus <corpus.json> --json

This tool evaluates a structured rules document against a request corpus and
reports per-category TP/FP/FN statistics.  It is read-only: it does not make
network calls, execute paid-credit API calls, or modify any repository files.

SAFETY NOTICE
=============
Owner/auditor use only.  This tool does not implement production WAF
functionality and does not prove real-world defensive value.

LAYER 2 NOTE
============
This tool provides the evaluation path toward Layer 2 value validation
(DEFINITION_OF_DONE.md L2-V1 through L2-V5).  Realistic test corpora must be
supplied by the Owner outside the repository.  Repository fixtures use
neutralized placeholder patterns only and do not constitute Layer 2 evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from core.structured_detector import inspect_request_with_structured_rules
from core.structured_validator import validate_rules_schema
from core.types import Request


class EvalError(ValueError):
    """Raised for user-correctable evaluation errors."""


# Tags that indicate the kind of test case rather than its threat category.
_KIND_TAGS: frozenset[str] = frozenset(
    {"attack", "benign", "regression", "holdout", "counterfactual", "drift"}
)

# Tags that represent L2-V3 evaluation tiers (holdout / drift / counterfactual).
_TIER_TAGS: frozenset[str] = frozenset({"holdout", "drift", "counterfactual"})


def _validate_optional_str(entry_idx: int, field: str, value: object) -> None:
    if value is not None and not isinstance(value, str):
        raise EvalError(
            f"Corpus entry {entry_idx} {field!r} must be a string or absent, "
            f"got {type(value).__name__}: {value!r}"
        )


def _validate_present_str(entry_idx: int, field: str, value: object) -> None:
    """Validate that an explicitly-present field is a string. None is rejected."""
    if not isinstance(value, str):
        raise EvalError(
            f"Corpus entry {entry_idx} {field!r} must be a string or absent, "
            f"got {type(value).__name__}: {value!r}"
        )


def _validate_optional_str_list(entry_idx: int, field: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise EvalError(
            f"Corpus entry {entry_idx} {field!r} must be a list of strings or absent, "
            f"got {type(value).__name__}: {value!r}"
        )
    for j, item in enumerate(value):
        if not isinstance(item, str):
            raise EvalError(
                f"Corpus entry {entry_idx} {field!r}[{j}] must be a string, "
                f"got {type(item).__name__}: {item!r}"
            )


def _validate_present_str_list(entry_idx: int, field: str, value: object) -> None:
    """Validate that an explicitly-present field is a list of strings. None is rejected."""
    if not isinstance(value, list):
        raise EvalError(
            f"Corpus entry {entry_idx} {field!r} must be a list of strings or absent, "
            f"got {type(value).__name__}: {value!r}"
        )
    for j, item in enumerate(value):
        if not isinstance(item, str):
            raise EvalError(
                f"Corpus entry {entry_idx} {field!r}[{j}] must be a string, "
                f"got {type(item).__name__}: {item!r}"
            )


def _validate_request_mapping(entry_idx: int, field: str, value: object) -> None:
    if not isinstance(value, dict):
        raise EvalError(
            f"Corpus entry {entry_idx} request.{field!r} must be a JSON object or absent, "
            f"got {type(value).__name__}: {value!r}"
        )
    for k, v in value.items():
        if not isinstance(v, str):
            raise EvalError(
                f"Corpus entry {entry_idx} request.{field!r}[{k!r}] value must be a string, "
                f"got {type(v).__name__}: {v!r}"
            )


def load_rules(path: Path) -> dict:
    """Load and validate a structured rules document.

    Raises EvalError for user-correctable problems (invalid JSON, schema violations).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"Rules document is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise EvalError(f"Rules document must be a JSON object: {path}")
    result = validate_rules_schema(data)
    if not result.get("success"):
        violations: list[str] = result.get("violations", [])
        raise EvalError(
            f"Rules document validation failed ({path}):\n"
            + "\n".join(f"  {v}" for v in violations)
        )
    return data


def load_corpus(path: Path) -> list[dict]:
    """Load a test corpus JSON file.

    Expected format: list of objects with at minimum 'request' and
    'expected_blocked' fields.  'id', 'kind', and 'tags' are optional but
    recommended for per-category reporting.

    Raises EvalError for user-correctable problems.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"Corpus is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, list):
        raise EvalError(f"Corpus must be a JSON array: {path}")
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise EvalError(f"Corpus entry {i} must be a JSON object")
        if "request" not in entry:
            raise EvalError(f"Corpus entry {i} missing 'request' field")
        if not isinstance(entry["request"], dict):
            raise EvalError(f"Corpus entry {i} 'request' must be a JSON object")
        _req = entry["request"]
        for _sf in ("method", "path", "body"):
            if _sf in _req:
                _v = _req[_sf]
                if not isinstance(_v, str):
                    raise EvalError(
                        f"Corpus entry {i} request.{_sf!r} must be a string or absent, "
                        f"got {type(_v).__name__}: {_v!r}"
                    )
        _validate_optional_str(i, "source_ip", _req.get("source_ip"))
        if "query" in _req:
            _validate_request_mapping(i, "query", _req["query"])
        if "headers" in _req:
            _validate_request_mapping(i, "headers", _req["headers"])
        if "expected_blocked" not in entry:
            raise EvalError(f"Corpus entry {i} missing 'expected_blocked' field")
        if not isinstance(entry["expected_blocked"], bool):
            raise EvalError(
                f"Corpus entry {i} 'expected_blocked' must be a JSON boolean "
                f"(true/false), got {type(entry['expected_blocked']).__name__}: "
                f"{entry['expected_blocked']!r}"
            )
        if "id" in entry:
            _validate_present_str(i, "id", entry["id"])
        if "kind" in entry:
            _validate_present_str(i, "kind", entry["kind"])
        if "tags" in entry:
            _validate_present_str_list(i, "tags", entry["tags"])
    return data


def _make_request(entry: dict) -> Request:
    req = entry["request"]
    return Request(
        method=req.get("method", "GET"),
        path=req.get("path", "/"),
        query=dict(req.get("query") or {}),
        headers=dict(req.get("headers") or {}),
        body=req.get("body", ""),
        source_ip=req.get("source_ip"),
    )


def _primary_category(tags: list) -> str:
    """Return the first tag that is not a kind tag, or 'uncategorized'."""
    if not isinstance(tags, list):
        return "uncategorized"
    for tag in tags:
        if isinstance(tag, str) and tag not in _KIND_TAGS:
            return tag
    return "uncategorized"


def _empty_counts() -> dict[str, int]:
    return {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "exceptions": 0}


def _pass_rate(counts: dict[str, int]) -> float | None:
    denom = counts["TP"] + counts["FP"] + counts["TN"] + counts["FN"]
    return (counts["TP"] + counts["TN"]) / denom if denom else None


def run_evaluation(rules_doc: dict, corpus: list[dict]) -> dict[str, Any]:
    """Evaluate a rules document against a corpus.

    Returns a dict with keys 'per_case', 'per_category', 'per_kind', 'per_tier', and 'overall'.
    """
    per_case: list[dict] = []
    per_category: dict[str, dict[str, int]] = {}
    per_kind: dict[str, dict[str, int]] = {}
    per_tier: dict[str, dict[str, int]] = {}
    overall = _empty_counts()

    for entry in corpus:
        case_id = str(entry.get("id", "unknown"))
        expected_blocked_raw = entry.get("expected_blocked")
        if not isinstance(expected_blocked_raw, bool):
            raise EvalError(
                f"corpus entry {case_id!r}: 'expected_blocked' must be a JSON boolean "
                f"(true/false), got {type(expected_blocked_raw).__name__}: {expected_blocked_raw!r}"
            )
        expected_blocked: bool = expected_blocked_raw
        tags = entry.get("tags", [])
        kind = str(entry.get("kind", "unknown"))
        category = _primary_category(tags)

        try:
            request = _make_request(entry)
            result = inspect_request_with_structured_rules(request, rules_doc)
            actual_blocked = result.blocked
            matched_signals = list(result.matched_signals)
            exception = False
        except Exception:
            actual_blocked = False
            matched_signals = []
            exception = True

        if exception:
            outcome = None  # excluded from TP/FP/TN/FN; counted only in exceptions
        elif expected_blocked and actual_blocked:
            outcome = "TP"
        elif expected_blocked and not actual_blocked:
            outcome = "FN"
        elif not expected_blocked and actual_blocked:
            outcome = "FP"
        else:
            outcome = "TN"

        if category not in per_category:
            per_category[category] = _empty_counts()
        if kind not in per_kind:
            per_kind[kind] = _empty_counts()
        if outcome is not None:
            per_category[category][outcome] += 1
            per_kind[kind][outcome] += 1
            overall[outcome] += 1
        if exception:
            per_category[category]["exceptions"] += 1
            per_kind[kind]["exceptions"] += 1
            overall["exceptions"] += 1
        if isinstance(tags, list):
            for _tag in tags:
                if isinstance(_tag, str) and _tag in _TIER_TAGS:
                    if _tag not in per_tier:
                        per_tier[_tag] = _empty_counts()
                    if outcome is not None:
                        per_tier[_tag][outcome] += 1
                    if exception:
                        per_tier[_tag]["exceptions"] += 1

        per_case.append(
            {
                "id": case_id,
                "kind": kind,
                "category": category,
                "expected_blocked": expected_blocked,
                "actual_blocked": actual_blocked,
                "outcome": outcome if outcome is not None else "exception",
                "exception": exception,
                "matched_signals": matched_signals,
            }
        )

    return {
        "per_case": per_case,
        "per_category": per_category,
        "per_kind": per_kind,
        "per_tier": per_tier,
        "overall": overall,
    }


def _tp_rate(counts: dict[str, int]) -> float | None:
    denom = counts["TP"] + counts["FN"]
    return counts["TP"] / denom if denom else None


def _fp_rate(counts: dict[str, int]) -> float | None:
    denom = counts["TN"] + counts["FP"]
    return counts["FP"] / denom if denom else None


def _fn_rate(counts: dict[str, int]) -> float | None:
    denom = counts["TP"] + counts["FN"]
    return counts["FN"] / denom if denom else None


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.1f}%"


def _md_cell(value: str) -> str:
    """Escape | and newlines so Owner-supplied values cannot break MD table structure."""
    return value.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def build_markdown(rules_path: Path, corpus_path: Path) -> str:
    """Build a per-category evaluation Markdown report.

    Raises EvalError, OSError, or json.JSONDecodeError on load failures.
    """
    rules_doc = load_rules(rules_path)
    corpus = load_corpus(corpus_path)
    results = run_evaluation(rules_doc, corpus)

    overall = results["overall"]
    per_category = results["per_category"]
    per_kind = results["per_kind"]
    per_tier = results["per_tier"]
    per_case = results["per_case"]

    total_cases = sum(overall[k] for k in ("TP", "FP", "TN", "FN"))
    attack_total = overall["TP"] + overall["FN"]
    benign_total = overall["TN"] + overall["FP"]

    lines: list[str] = [
        "# Cyber-Immunizer Structured Rules Evaluation Report",
        "",
        "**Owner/auditor use only.**"
        " This tool evaluates structured rules against a local test corpus.",
        "It does not prove real-world defensive value or production WAF suitability.",
        "Layer 2 value validation requires Owner review and acceptance of evidence"
        " from a realistic (non-symbolic) threat corpus.",
        "",
        f"Rules: `{rules_path}`",
        f"Corpus: `{corpus_path}`",
        f"Total cases: {total_cases}",
        "",
        "## Overall Results",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| True Positive (TP) | {overall['TP']} |",
        f"| False Positive (FP) | {overall['FP']} |",
        f"| True Negative (TN) | {overall['TN']} |",
        f"| False Negative (FN) | {overall['FN']} |",
        f"| Exceptions | {overall['exceptions']} |",
        f"| Detection rate (TP rate) | {_pct(_tp_rate(overall))} ({overall['TP']}/{attack_total}) |",
        f"| False-positive rate | {_pct(_fp_rate(overall))} ({overall['FP']}/{benign_total}) |",
        f"| False-negative rate | {_pct(_fn_rate(overall))} ({overall['FN']}/{attack_total}) |",
        "",
        "## Per-Category Results",
        "",
        "| Category | TP | FP | TN | FN | TP rate | FP rate | FN rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for cat, stats in sorted(per_category.items()):
        lines.append(
            f"| {_md_cell(cat)} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']}"
            f" | {_pct(_tp_rate(stats))} | {_pct(_fp_rate(stats))} | {_pct(_fn_rate(stats))} |"
        )

    lines += [
        "",
        "## Per-Kind Results",
        "",
        "Pass rate = (TP + TN) / (TP + FP + TN + FN). Holdout, drift, and counterfactual"
        " kind pass rates address L2-V3 overfitting-risk evaluation.",
        "",
        "| Kind | TP | FP | TN | FN | Exc | Pass rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for k, stats in sorted(per_kind.items()):
        lines.append(
            f"| {_md_cell(k)} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']}"
            f" | {stats['exceptions']} | {_pct(_pass_rate(stats))} |"
        )

    lines += [
        "",
        "## L2-V3 Tier Results",
        "",
        "Tag-based aggregation for holdout / drift / counterfactual corpus entries (L2-V3).",
        "A corpus entry contributes to each tier whose tag it carries.",
        "",
        "| Tier | TP | FP | TN | FN | Exc | Pass rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _tier in ("holdout", "drift", "counterfactual"):
        if _tier in per_tier:
            _ts = per_tier[_tier]
            lines.append(
                f"| {_md_cell(_tier)} | {_ts['TP']} | {_ts['FP']} | {_ts['TN']} | {_ts['FN']}"
                f" | {_ts['exceptions']} | {_pct(_pass_rate(_ts))} |"
            )
    if not per_tier:
        lines.append("| (none) | — | — | — | — | — | — |")

    lines += [
        "",
        "## Per-Case Results",
        "",
        "| ID | Kind | Category | Expected | Actual | Outcome | Matched signals |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in per_case:
        signals = _md_cell(", ".join(case["matched_signals"]) or "—")
        expected = "block" if case["expected_blocked"] else "allow"
        actual = "block" if case["actual_blocked"] else "allow"
        lines.append(
            f"| {_md_cell(str(case['id']))} | {_md_cell(case['kind'])}"
            f" | {_md_cell(case['category'])}"
            f" | {expected} | {actual} | {_md_cell(case['outcome'])} | {signals} |"
        )

    lines += [
        "",
        "## Layer 2 Context",
        "",
        "This evaluation used the rule literals for detection.",
        "If the corpus uses **neutralized placeholder patterns** (e.g.,"
        " `PATH_TRAVERSAL_SIGNATURE_PLACEHOLDER`), detection statistics reflect"
        " symbolic coverage only — not realistic threat coverage.",
        "",
        "**Latency note**: This CLI does **not** capture per-request evaluation latency."
        " L2-V2 requires per-category latency data alongside TP/FP/FN statistics."
        " Latency evidence must be collected separately by the Owner during realistic-corpus"
        " evaluation and reported alongside this tool's output."
        " This CLI alone does not satisfy the latency component of L2-V2.",
        "",
        "For Layer 2 value validation (DEFINITION_OF_DONE.md L2-V1 through L2-V5),"
        " the Owner must supply:",
        "",
        "1. A rules document with realistic but safely neutralized detection literals.",
        "2. A test corpus with realistic but safely neutralized request samples.",
        "3. Both files are provided **outside the repository** to avoid committing"
        " exploit-adjacent content.",
        "",
        "Layer 2 is satisfied only when the Owner has reviewed and accepted value"
        " validation evidence from a realistic-corpus evaluation.",
        "",
    ]
    return "\n".join(lines)


def build_json_report(rules_path: Path, corpus_path: Path) -> dict:
    """Build a per-category evaluation JSON report.

    Raises EvalError, OSError, or json.JSONDecodeError on load failures.
    """
    rules_doc = load_rules(rules_path)
    corpus = load_corpus(corpus_path)
    results = run_evaluation(rules_doc, corpus)

    overall = results["overall"]
    per_category = results["per_category"]
    per_kind = results["per_kind"]
    total_cases = sum(overall[k] for k in ("TP", "FP", "TN", "FN"))

    cat_summary: dict[str, Any] = {}
    for cat, stats in per_category.items():
        cat_summary[cat] = {
            **stats,
            "tp_rate": _tp_rate(stats),
            "fp_rate": _fp_rate(stats),
            "fn_rate": _fn_rate(stats),
        }

    kind_summary: dict[str, Any] = {}
    for k, stats in per_kind.items():
        kind_summary[k] = {
            **stats,
            "pass_rate": _pass_rate(stats),
        }

    tier_summary: dict[str, Any] = {}
    for tier, stats in results["per_tier"].items():
        tier_summary[tier] = {
            **stats,
            "pass_rate": _pass_rate(stats),
        }

    return {
        "rules_path": str(rules_path),
        "corpus_path": str(corpus_path),
        "overall": {
            **overall,
            "total_cases": total_cases,
            "tp_rate": _tp_rate(overall),
            "fp_rate": _fp_rate(overall),
            "fn_rate": _fn_rate(overall),
        },
        "per_category": cat_summary,
        "per_kind": kind_summary,
        "per_tier": tier_summary,
        "per_case": results["per_case"],
        "latency_note": (
            "This CLI does not capture per-request latency. "
            "L2-V2 latency evidence must be collected separately."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="python -m cli.structured_eval",
        description=(
            "Owner/auditor structured rules evaluation. "
            "Reports per-category TP/FP/FN for a rules document against a request corpus."
        ),
    )
    parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="Path to structured rules JSON document (validated by core.structured_validator).",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Path to test corpus JSON file (list of {id, kind, expected_blocked, tags, request}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of Markdown.",
    )
    args = parser.parse_args(args_list)

    try:
        if args.json:
            report = build_json_report(args.rules, args.corpus)
            print(json.dumps(report, indent=2))
        else:
            print(build_markdown(args.rules, args.corpus))
    except (OSError, EvalError, json.JSONDecodeError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
