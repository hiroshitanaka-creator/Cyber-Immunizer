"""Latency-aware Owner/auditor structured rules evaluation CLI.

Usage:
    python -m cli.structured_eval_latency --rules <rules.json> --corpus <corpus.json>
    python -m cli.structured_eval_latency --rules <rules.json> --corpus <corpus.json> --json

This module complements ``cli.structured_eval`` by adding per-case and
per-aggregate latency measurements required for Layer 2 value-validation
evidence (DEFINITION_OF_DONE.md L2-V2). It is read-only: it does not write
repository state, call external APIs, dispatch workflows, or promote detectors.

Owner/auditor use only. These reports are validation evidence, not a claim of
external user value, production WAF suitability, or Layer 2 completion without
Project Owner review and acceptance.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from cli.structured_eval import EvalError, load_corpus, load_rules
from core.structured_detector import inspect_request_with_structured_rules
from core.types import Request

_KIND_TAGS: frozenset[str] = frozenset(
    {"attack", "benign", "regression", "holdout", "counterfactual", "drift"}
)
_TIER_TAGS: frozenset[str] = frozenset({"holdout", "drift", "counterfactual"})
_REQUIRED_CATEGORIES: tuple[str, ...] = ("path-traversal", "xss", "sqli", "cmdi")
_COUNT_KEYS: tuple[str, ...] = ("TP", "FP", "TN", "FN", "exceptions")

Clock = Callable[[], float]


def _make_request(entry: dict[str, Any]) -> Request:
    req = entry["request"]
    return Request(
        method=req.get("method", "GET"),
        path=req.get("path", "/"),
        query=dict(req.get("query") or {}),
        headers=dict(req.get("headers") or {}),
        body=req.get("body", ""),
        source_ip=req.get("source_ip"),
    )


def _primary_category(tags: object) -> str:
    """Return the first tag that is not a kind/tier tag, or ``uncategorized``."""
    if not isinstance(tags, list):
        return "uncategorized"
    for tag in tags:
        if isinstance(tag, str) and tag not in _KIND_TAGS and tag not in _TIER_TAGS:
            return tag
    return "uncategorized"


def _empty_bucket() -> dict[str, Any]:
    return {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "exceptions": 0, "_latencies_ms": []}


def _ensure_bucket(target: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    if key not in target:
        target[key] = _empty_bucket()
    return target[key]


def _classify(expected_blocked: bool, actual_blocked: bool, exception: bool) -> str:
    if exception:
        return "exception"
    if expected_blocked and actual_blocked:
        return "TP"
    if expected_blocked and not actual_blocked:
        return "FN"
    if not expected_blocked and actual_blocked:
        return "FP"
    return "TN"


def _record(bucket: dict[str, Any], outcome: str, latency_ms: float) -> None:
    if outcome in _COUNT_KEYS:
        bucket[outcome] += 1
    bucket["_latencies_ms"].append(latency_ms)


def _latency_summary(latencies_ms: list[float]) -> dict[str, float | int | None]:
    if not latencies_ms:
        return {
            "latency_count": 0,
            "avg_latency_ms": None,
            "min_latency_ms": None,
            "max_latency_ms": None,
        }
    return {
        "latency_count": len(latencies_ms),
        "avg_latency_ms": sum(latencies_ms) / len(latencies_ms),
        "min_latency_ms": min(latencies_ms),
        "max_latency_ms": max(latencies_ms),
    }


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    counts = {key: int(bucket[key]) for key in _COUNT_KEYS}
    return {**counts, **_latency_summary(list(bucket["_latencies_ms"]))}


def _finalize_buckets(buckets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {key: _finalize_bucket(value) for key, value in sorted(buckets.items())}


def _tp_rate(counts: dict[str, Any]) -> float | None:
    denom = int(counts["TP"]) + int(counts["FN"])
    return int(counts["TP"]) / denom if denom else None


def _fp_rate(counts: dict[str, Any]) -> float | None:
    denom = int(counts["TN"]) + int(counts["FP"])
    return int(counts["FP"]) / denom if denom else None


def _fn_rate(counts: dict[str, Any]) -> float | None:
    denom = int(counts["TP"]) + int(counts["FN"])
    return int(counts["FN"]) / denom if denom else None


def _pass_rate(counts: dict[str, Any]) -> float | None:
    denom = int(counts["TP"]) + int(counts["FP"]) + int(counts["TN"]) + int(counts["FN"])
    return (int(counts["TP"]) + int(counts["TN"])) / denom if denom else None


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate * 100:.1f}%"


def _ms(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _with_rates(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        **bucket,
        "tp_rate": _tp_rate(bucket),
        "fp_rate": _fp_rate(bucket),
        "fn_rate": _fn_rate(bucket),
        "pass_rate": _pass_rate(bucket),
    }


def run_evaluation_with_latency(
    rules_doc: dict[str, Any],
    corpus: list[dict[str, Any]],
    *,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Evaluate a rules document and capture per-case latency.

    ``clock`` defaults to ``time.perf_counter`` and is injectable for deterministic
    tests. Latency is measured around the detector call only, not around JSON load
    or report rendering.
    """
    now = clock or time.perf_counter
    per_case: list[dict[str, Any]] = []
    per_category: dict[str, dict[str, Any]] = {}
    per_kind: dict[str, dict[str, Any]] = {}
    per_tier: dict[str, dict[str, Any]] = {}
    overall = _empty_bucket()

    for entry in corpus:
        case_id = str(entry.get("id", "unknown"))
        expected_blocked_raw = entry.get("expected_blocked")
        if not isinstance(expected_blocked_raw, bool):
            raise EvalError(
                f"corpus entry {case_id!r}: 'expected_blocked' must be a JSON boolean "
                f"(true/false), got {type(expected_blocked_raw).__name__}: {expected_blocked_raw!r}"
            )
        expected_blocked = expected_blocked_raw
        tags = entry.get("tags", [])
        kind = str(entry.get("kind", "unknown"))
        category = _primary_category(tags)

        start = now()
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
        latency_ms = max(0.0, (now() - start) * 1000.0)
        outcome = _classify(expected_blocked, actual_blocked, exception)

        _record(overall, outcome, latency_ms)
        _record(_ensure_bucket(per_category, category), outcome, latency_ms)
        _record(_ensure_bucket(per_kind, kind), outcome, latency_ms)
        if isinstance(tags, list):
            for tier in {tag for tag in tags if isinstance(tag, str) and tag in _TIER_TAGS}:
                _record(_ensure_bucket(per_tier, tier), outcome, latency_ms)

        per_case.append(
            {
                "id": case_id,
                "kind": kind,
                "category": category,
                "expected_blocked": expected_blocked,
                "actual_blocked": actual_blocked,
                "outcome": outcome,
                "exception": exception,
                "matched_signals": matched_signals,
                "latency_ms": latency_ms,
            }
        )

    finalized_overall = _finalize_bucket(overall)
    return {
        "per_case": per_case,
        "per_category": _finalize_buckets(per_category),
        "per_kind": _finalize_buckets(per_kind),
        "per_tier": _finalize_buckets(per_tier),
        "overall": finalized_overall,
    }


def _sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_json_report(rules_path: Path, corpus_path: Path) -> dict[str, Any]:
    rules_doc = load_rules(rules_path)
    corpus = load_corpus(corpus_path)
    results = run_evaluation_with_latency(rules_doc, corpus)

    overall = _with_rates(results["overall"])
    return {
        "rules_path": str(rules_path),
        "rules_sha256": _sha256_file(rules_path),
        "corpus_path": str(corpus_path),
        "corpus_sha256": _sha256_file(corpus_path),
        "overall": {
            **overall,
            "total_corpus_entries": len(corpus),
            "total_cases": sum(int(overall[k]) for k in ("TP", "FP", "TN", "FN")),
        },
        "per_category": {key: _with_rates(value) for key, value in results["per_category"].items()},
        "per_kind": {key: _with_rates(value) for key, value in results["per_kind"].items()},
        "per_tier": {key: _with_rates(value) for key, value in results["per_tier"].items()},
        "per_case": results["per_case"],
        "layer2_note": (
            "Latency is measured around detector evaluation per case. Layer 2 completion still requires "
            "Project Owner review and realistic, safely neutralized corpus evidence."
        ),
    }


def build_markdown(rules_path: Path, corpus_path: Path) -> str:
    report = build_json_report(rules_path, corpus_path)
    overall = report["overall"]
    lines = [
        "# Cyber-Immunizer Structured Rules Latency Evaluation Report",
        "",
        "**Owner/auditor use only.** This report adds per-case and aggregate latency evidence to structured-rules evaluation.",
        "It does not prove real-world defensive value or production WAF suitability without Owner-accepted realistic-corpus evidence.",
        "",
        f"Rules: `{rules_path}`",
        f"Rules SHA-256: `{report['rules_sha256']}`",
        f"Corpus: `{corpus_path}`",
        f"Corpus SHA-256: `{report['corpus_sha256']}`",
        "",
        "## Overall Results",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| True Positive (TP) | {overall['TP']} |",
        f"| False Positive (FP) | {overall['FP']} |",
        f"| True Negative (TN) | {overall['TN']} |",
        f"| False Negative (FN) | {overall['FN']} |",
        f"| Exceptions | {overall['exceptions']} |",
        f"| TP rate | {_pct(overall['tp_rate'])} |",
        f"| FP rate | {_pct(overall['fp_rate'])} |",
        f"| FN rate | {_pct(overall['fn_rate'])} |",
        f"| Avg latency ms | {_ms(overall['avg_latency_ms'])} |",
        f"| Min latency ms | {_ms(overall['min_latency_ms'])} |",
        f"| Max latency ms | {_ms(overall['max_latency_ms'])} |",
        "",
        "## Per-Category Results",
        "",
        "| Category | TP | FP | TN | FN | Exc | TP rate | FP rate | FN rate | Avg ms | Max ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cat in _REQUIRED_CATEGORIES:
        stats = report["per_category"].get(cat)
        if stats is None:
            lines.append(f"| {_md_cell(cat)} *(absent)* | — | — | — | — | — | — | — | — | — | — |")
        else:
            lines.append(
                f"| {_md_cell(cat)} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']} | {stats['exceptions']}"
                f" | {_pct(stats['tp_rate'])} | {_pct(stats['fp_rate'])} | {_pct(stats['fn_rate'])}"
                f" | {_ms(stats['avg_latency_ms'])} | {_ms(stats['max_latency_ms'])} |"
            )
    for cat, stats in report["per_category"].items():
        if cat not in _REQUIRED_CATEGORIES:
            lines.append(
                f"| {_md_cell(cat)} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']} | {stats['exceptions']}"
                f" | {_pct(stats['tp_rate'])} | {_pct(stats['fp_rate'])} | {_pct(stats['fn_rate'])}"
                f" | {_ms(stats['avg_latency_ms'])} | {_ms(stats['max_latency_ms'])} |"
            )

    lines.extend([
        "",
        "## L2-V3 Tier Results",
        "",
        "| Tier | TP | FP | TN | FN | Exc | Pass rate | Avg ms | Max ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for tier in ("holdout", "drift", "counterfactual"):
        stats = report["per_tier"].get(tier)
        if stats is None:
            lines.append(f"| {_md_cell(tier)} *(absent)* | — | — | — | — | — | — | — | — |")
        else:
            lines.append(
                f"| {_md_cell(tier)} | {stats['TP']} | {stats['FP']} | {stats['TN']} | {stats['FN']} | {stats['exceptions']}"
                f" | {_pct(stats['pass_rate'])} | {_ms(stats['avg_latency_ms'])} | {_ms(stats['max_latency_ms'])} |"
            )

    lines.extend([
        "",
        "## Per-Case Results",
        "",
        "| ID | Kind | Category | Expected | Actual | Outcome | Latency ms | Matched signals |",
        "|---|---|---|---|---|---|---:|---|",
    ])
    for case in report["per_case"]:
        expected = "block" if case["expected_blocked"] else "allow"
        actual = "block" if case["actual_blocked"] else "allow"
        signals = _md_cell(", ".join(case["matched_signals"]) or "—")
        lines.append(
            f"| {_md_cell(case['id'])} | {_md_cell(case['kind'])} | {_md_cell(case['category'])}"
            f" | {expected} | {actual} | {_md_cell(case['outcome'])} | {_ms(case['latency_ms'])} | {signals} |"
        )

    lines.extend([
        "",
        "## Layer 2 Context",
        "",
        "This CLI supplies latency evidence for L2-V2, but Layer 2 is not complete unless the Project Owner accepts realistic, safely neutralized corpus evidence across L2-V1 through L2-V5.",
        "Repository fixtures remain symbolic / neutralized and do not constitute external defensive value evidence.",
        "",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else None
    parser = argparse.ArgumentParser(
        prog="python -m cli.structured_eval_latency",
        description="Owner/auditor structured rules evaluation with per-case latency reporting.",
    )
    parser.add_argument("--rules", type=Path, required=True, help="Structured rules JSON document.")
    parser.add_argument("--corpus", type=Path, required=True, help="Evaluation corpus JSON file.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown.")
    args = parser.parse_args(args_list)

    try:
        if args.json:
            print(json.dumps(build_json_report(args.rules, args.corpus), indent=2))
        else:
            print(build_markdown(args.rules, args.corpus))
    except (OSError, EvalError, json.JSONDecodeError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
