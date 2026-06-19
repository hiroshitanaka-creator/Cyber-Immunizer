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

# Valid kind values for standard corpus files.  Extended by PR-3 for adaptive tiers.
_VALID_CORPUS_KINDS: frozenset[str] = frozenset({"benign", "attack", "regression"})


# ---------------------------------------------------------------------------
# Strict corpus validation helpers
# ---------------------------------------------------------------------------

def _validate_request_dict(req: object, record_id: str) -> None:
    """Validate a request sub-dict. Raises ValueError on schema violation."""
    if not isinstance(req, dict):
        raise ValueError(
            f"Corpus record {record_id!r}: 'request' must be dict, "
            f"got {type(req).__name__!r}"
        )
    for field in ("method", "path", "body"):
        val = req.get(field)
        if val is not None and not isinstance(val, str):
            raise ValueError(
                f"Corpus record {record_id!r}: request.{field} must be str, "
                f"got {type(val).__name__!r}"
            )
    for field in ("query", "headers"):
        val = req.get(field)
        if val is not None:
            if not isinstance(val, dict):
                raise ValueError(
                    f"Corpus record {record_id!r}: request.{field} must be dict, "
                    f"got {type(val).__name__!r}"
                )
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError(
                        f"Corpus record {record_id!r}: request.{field} key must be str, "
                        f"got {type(k).__name__!r}"
                    )
                if not isinstance(v, str):
                    raise ValueError(
                        f"Corpus record {record_id!r}: "
                        f"request.{field}[{k!r}] value must be str, "
                        f"got {type(v).__name__!r}"
                    )


def _validate_corpus_record(
    raw: object,
    default_kind: str | None,
    default_blocked: bool | None,
    seen_ids: set[str],
    valid_kinds: frozenset[str] = _VALID_CORPUS_KINDS,
) -> None:
    """Validate one corpus record dict. Raises ValueError on schema violation."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"Corpus record must be dict, got {type(raw).__name__!r}"
        )

    id_val = raw.get("id")
    if not isinstance(id_val, str) or not id_val:
        raise ValueError(
            f"Corpus record 'id' must be non-empty str, got {id_val!r}"
        )
    if id_val in seen_ids:
        raise ValueError(f"Duplicate corpus record id: {id_val!r}")
    seen_ids.add(id_val)

    req = raw.get("request")
    if req is None:
        raise ValueError(f"Corpus record {id_val!r}: 'request' field is missing")
    _validate_request_dict(req, id_val)

    kind = raw.get("kind", default_kind)
    if not isinstance(kind, str):
        raise ValueError(
            f"Corpus record {id_val!r}: 'kind' must be str, "
            f"got {type(kind).__name__!r} {kind!r}"
        )
    if kind not in valid_kinds:
        raise ValueError(
            f"Corpus record {id_val!r}: 'kind' must be one of {sorted(valid_kinds)}, "
            f"got {kind!r}"
        )

    # expected_blocked must be exactly bool — do NOT coerce with bool()
    blocked = raw.get("expected_blocked", default_blocked)
    if type(blocked) is not bool:
        raise ValueError(
            f"Corpus record {id_val!r}: 'expected_blocked' must be exactly bool "
            f"(JSON true/false), got {type(blocked).__name__!r} {blocked!r}"
        )

    tags = raw.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            raise ValueError(
                f"Corpus record {id_val!r}: 'tags' must be list[str], "
                f"got {type(tags).__name__!r}"
            )
        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                raise ValueError(
                    f"Corpus record {id_val!r}: tags[{i}] must be str, "
                    f"got {type(tag).__name__!r}"
                )


def _load_corpus_file(
    path: Path,
    default_kind: str | None,
    default_blocked: bool | None,
    seen_ids: set[str],
    valid_kinds: frozenset[str] = _VALID_CORPUS_KINDS,
) -> list[dict]:
    """Read and strictly validate a corpus JSON file.

    Raises ValueError if the file is missing, malformed JSON, wrong top-level
    type, or any record fails schema validation.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read corpus file {path}: {exc}") from exc
    try:
        raw_list = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in corpus file {path}: {exc}") from exc
    if not isinstance(raw_list, list):
        raise ValueError(
            f"Corpus file {path} top-level must be a JSON list, "
            f"got {type(raw_list).__name__!r}"
        )
    for raw in raw_list:
        _validate_corpus_record(raw, default_kind, default_blocked, seen_ids, valid_kinds)
    return raw_list


def load_test_cases(
    *,
    benign_path: Path | None = None,
    attack_path: Path | None = None,
    regression_path: Path | None = None,
) -> list[TestCase]:
    """Load test cases from JSON files and return as TestCase objects.

    Raises ValueError if any file contains malformed JSON, wrong top-level type,
    schema violations, or duplicate IDs.  expected_blocked must be exactly bool
    (JSON true/false) — string coercion via bool() is no longer performed.
    """
    benign_path = benign_path or _DATA_DIR / "benign_requests.json"
    attack_path = attack_path or _DATA_DIR / "attack_requests.json"
    regression_path = regression_path or _DATA_DIR / "regression_cases.json"

    cases: list[TestCase] = []
    seen_ids: set[str] = set()

    for path, kind, expected_blocked in [
        (benign_path, "benign", False),
        (attack_path, "attack", True),
        (regression_path, None, None),  # kind and expected_blocked from file
    ]:
        raw_list = _load_corpus_file(path, kind, expected_blocked, seen_ids)
        for raw in raw_list:
            req = build_request(raw["request"])
            case_kind = raw.get("kind", kind)
            case_blocked = raw.get("expected_blocked", expected_blocked)
            cases.append(
                TestCase(
                    id=raw["id"],
                    kind=case_kind,
                    request=req,
                    expected_blocked=case_blocked,  # already validated as bool
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
        if r["exception"]:
            exceptions += 1
            continue
        exp = r["expected_blocked"]
        act = r["actual_blocked"]
        if exp and act:
            tp += 1
        elif (not exp) and act:
            fp += 1
        elif exp and (not act):
            fn += 1
        else:
            tn += 1
        latencies.append(float(r["latency_ms"]))

    total = tp + fp + tn + fn + exceptions
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "exception_count": exceptions,
        "total_cases": total,
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else 0.0,
    }
