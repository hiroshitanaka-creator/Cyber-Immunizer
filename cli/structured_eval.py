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
        if "expected_blocked" not in entry:
            raise EvalError(f"Corpus entry {i} missing 'expected_blocked' field")
        if not isinstance(entry["expected_blocked"], bool):
            raise EvalError(
                f"Corpus entry {i} 'expected_blocked' must be a JSON boolean "
                f"(true/false), got {type(entry['expected_blocked']).__name__}: "
                f"{entry['expected_blocked']!r}"
            )
    return data


def _make_request(entry: dict) -> Request:
    req = entry["request"]
    return Request(
        method=req.get("method", "GET"),
        path=req.get("path", "/"),
        query=dict(req.get("query") or {}),
        headers=dict(req.get("headers") or {}),
        body=str(req.get("body") or ""),
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


def run_evaluation(rules_doc: dict, corpus: list[dict]) -> dict[str, Any]:
    """Evaluate a rules document against a corpus.

    Returns a dict with keys 'per_case', 'per_category', and 'overall'.
    """
    per_case: list[dict] = []
    per_category: dict[str, dict[str, int]] = {}
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
        if outcome is not None:
            per_category[category][outcome] += 1
            overall[outcome] += 1
        if exception:
            per_category[category]["exceptions"] += 1
            overall["exceptions"] += 1

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

    return {"per_case": per_case, "per_category": per_category, "overall": overall}


def _tp_rate(counts: dict[str, int]) -> float:
    denom = counts["TP"] + counts["FN"]
    return counts["TP"] / denom if denom else 0.0


def _fp_rate(counts: dict[str, int]) -> float:
    denom = counts["TN"] + counts["FP"]
    return counts["FP"] / denom if denom else 0.0


def _fn_rate(counts: dict[str, int]) -> float:
    denom = counts["TP"] + counts["FN"]
    return counts["FN"] / denom if denom else 0.0


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def build_markdown(rules_path: Path, corpus_path: Path) -> str:
    """Build a per-category evaluation Markdown report.

    Raises EvalError, OSError, or json.JSONDecodeError on load failures.
    """
    rules_doc = load_rules(rules_path)
    corpus = load_corpus(corpus_path)
    results = run_evaluation(rules_doc, corpus)

    overall = results["overall"]
    per_category = results["per_category"]
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
            f"| {cat} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']}"
            f" | {_pct(_tp_rate(stats))} | {_pct(_fp_rate(stats))} | {_pct(_fn_rate(stats))} |"
        )

    lines += [
        "",
        "## Per-Case Results",
        "",
        "| ID | Kind | Category | Expected | Actual | Outcome | Matched signals |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in per_case:
        signals = ", ".join(case["matched_signals"]) or "—"
        expected = "block" if case["expected_blocked"] else "allow"
        actual = "block" if case["actual_blocked"] else "allow"
        lines.append(
            f"| {case['id']} | {case['kind']} | {case['category']}"
            f" | {expected} | {actual} | {case['outcome']} | {signals} |"
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
    total_cases = sum(overall[k] for k in ("TP", "FP", "TN", "FN"))

    cat_summary: dict[str, Any] = {}
    for cat, stats in per_category.items():
        cat_summary[cat] = {
            **stats,
            "tp_rate": _tp_rate(stats),
            "fp_rate": _fp_rate(stats),
            "fn_rate": _fn_rate(stats),
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
        "per_case": results["per_case"],
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
