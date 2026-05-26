"""core/test_attacker.py — Deterministic local test-case simulator.

SAFETY NOTICE
=============
This module is NOT an offensive attacker.  It is a pure in-process simulator
that constructs static Request objects from JSON test-case files and passes
them to a detector function.  It performs NO network calls, opens NO sockets,
and runs NO external commands.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from core.types import DetectionResult, Request, TestCase

# Default paths — override via function arguments for flexibility.
_DATA_DIR = Path(__file__).parent.parent / "data"


def load_test_cases(
    *,
    benign_path: Path | None = None,
    attack_path: Path | None = None,
    regression_path: Path | None = None,
) -> list[TestCase]:
    """Load test cases from JSON files and return as TestCase objects."""
    benign_path = benign_path or _DATA_DIR / "benign_requests.json"
    attack_path = attack_path or _DATA_DIR / "attack_requests.json"
    regression_path = regression_path or _DATA_DIR / "regression_cases.json"

    cases: list[TestCase] = []

    for path, kind, expected_blocked in [
        (benign_path, "benign", False),
        (attack_path, "attack", True),
        (regression_path, None, None),  # kind from file
    ]:
        raw_list = json.loads(path.read_text(encoding="utf-8"))
        for raw in raw_list:
            req = build_request(raw["request"])
            case_kind = raw.get("kind", kind)
            case_blocked = raw.get("expected_blocked", expected_blocked)
            cases.append(
                TestCase(
                    id=raw["id"],
                    kind=case_kind,
                    request=req,
                    expected_blocked=bool(case_blocked),
                    tags=tuple(raw.get("tags", [])),
                    description=raw.get("description", ""),
                )
            )

    return cases


def build_request(raw: dict) -> Request:
    """Construct a frozen Request from a raw JSON dict."""
    return Request(
        method=raw.get("method", "GET"),
        path=raw.get("path", "/"),
        query=raw.get("query", {}),
        headers=raw.get("headers", {}),
        body=raw.get("body", ""),
        source_ip=raw.get("source_ip"),
    )


def evaluate_detector(
    detector_fn: Callable[[Request], DetectionResult],
    cases: list[TestCase],
) -> list[dict]:
    """Run each test case through detector_fn and record results.

    Returns a list of result dicts (serialisation-friendly).
    No network calls, no subprocesses, no I/O beyond what is passed in.
    """
    results: list[dict] = []
    for case in cases:
        t0 = time.perf_counter()
        try:
            result = detector_fn(case.request)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            results.append(
                {
                    "id": case.id,
                    "kind": case.kind,
                    "expected_blocked": case.expected_blocked,
                    "actual_blocked": result.blocked,
                    "reason": result.reason,
                    "confidence": result.confidence,
                    "matched_signals": list(result.matched_signals),
                    "latency_ms": latency_ms,
                    "exception": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - t0) * 1000.0
            results.append(
                {
                    "id": case.id,
                    "kind": case.kind,
                    "expected_blocked": case.expected_blocked,
                    "actual_blocked": False,
                    "reason": "",
                    "confidence": 0.0,
                    "matched_signals": [],
                    "latency_ms": latency_ms,
                    "exception": str(exc),
                }
            )
    return results


def summarize_results(results: list[dict]) -> dict:
    """Aggregate result list into summary counts."""
    tp = fp = tn = fn = 0
    exceptions = 0
    latencies: list[float] = []

    for r in results:
        latencies.append(r["latency_ms"])
        if r["exception"]:
            exceptions += 1
        exp = r["expected_blocked"]
        act = r["actual_blocked"]
        if exp and act:
            tp += 1
        elif not exp and act:
            fp += 1
        elif not exp and not act:
            tn += 1
        else:
            fn += 1

    total = len(results)
    avg_latency = sum(latencies) / total if total else 0.0

    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "total_cases": total,
        "exception_count": exceptions,
        "avg_latency_ms": avg_latency,
    }
