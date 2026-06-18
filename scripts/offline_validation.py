"""Shared offline validation helpers for pre-paid-credit readiness.

All helpers are deterministic, local-only, and do not call external APIs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MUTATION_START = "# === MUTATION_START ==="
MUTATION_END = "# === MUTATION_END ==="


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    detail: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mutation_marker_issues(source: str) -> list[ValidationIssue]:
    start_count = source.count(MUTATION_START)
    end_count = source.count(MUTATION_END)
    issues: list[ValidationIssue] = []
    if start_count == 0 or end_count == 0:
        issues.append(ValidationIssue(
            "mutation_marker_missing",
            f"Expected exactly one mutation start and end marker; found start={start_count}, end={end_count}.",
        ))
        return issues
    if start_count != 1 or end_count != 1:
        issues.append(ValidationIssue(
            "mutation_marker_duplicate",
            f"Expected exactly one mutation start and end marker; found start={start_count}, end={end_count}.",
        ))
    start_idx = source.find(MUTATION_START)
    end_idx = source.find(MUTATION_END)
    if start_idx != -1 and end_idx != -1 and end_idx <= start_idx:
        issues.append(ValidationIssue(
            "mutation_marker_order_invalid",
            "Mutation end marker must appear after mutation start marker.",
        ))
    return issues


def replacement_marker_issues(replacement_code: str, *, prefix: str = "mutation") -> list[ValidationIssue]:
    if MUTATION_START in replacement_code or MUTATION_END in replacement_code:
        code = "proposal_mutation_boundary_tampering" if prefix == "proposal" else "mutation_region_escape"
        return [ValidationIssue(code, "Replacement code must not contain mutation boundary markers.")]
    return []


def outside_region_issues(candidate_source: str, base_source: str) -> list[ValidationIssue]:
    cand_issues = mutation_marker_issues(candidate_source)
    base_issues = mutation_marker_issues(base_source)
    if cand_issues:
        return cand_issues
    if base_issues:
        return base_issues
    c_start = candidate_source.find(MUTATION_START)
    c_end = candidate_source.find(MUTATION_END)
    b_start = base_source.find(MUTATION_START)
    b_end = base_source.find(MUTATION_END)
    cand_before = candidate_source[: c_start + len(MUTATION_START)]
    cand_after = candidate_source[c_end:]
    base_before = base_source[: b_start + len(MUTATION_START)]
    base_after = base_source[b_end:]
    if cand_before != base_before or cand_after != base_after:
        return [ValidationIssue("mutation_region_escape", "Candidate changes text outside the mutation boundary markers.")]
    return []


def hash_consistency_issues(candidate_source: str, candidate_hash: str | None, report: dict[str, Any] | None = None) -> list[ValidationIssue]:
    actual = sha256_text(candidate_source)
    issues: list[ValidationIssue] = []
    if candidate_hash is not None and candidate_hash != actual:
        issues.append(ValidationIssue("candidate_hash_mismatch", "Candidate hash does not match materialized candidate content."))
    if report is not None:
        reported = report.get("candidate_hash") or report.get("candidate_detector_sha256")
        if reported is not None and reported != actual:
            issues.append(ValidationIssue("candidate_report_hash_mismatch", "Report candidate hash does not match materialized candidate content."))
    return issues


def load_json_object(path: Path) -> tuple[dict[str, Any] | None, ValidationIssue | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, ValidationIssue("candidate_materialization_failed", f"Could not load JSON object {path}: {exc}")
    if not isinstance(data, dict):
        return None, ValidationIssue("candidate_materialization_failed", f"Expected JSON object at {path}.")
    return data, None
