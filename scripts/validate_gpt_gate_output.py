#!/usr/bin/env python3
"""Validate Cyber-Immunizer GPT Audit Gate receipt blocks.

Stdlib-only CLI for task prompt, PR audit, and PR-body GPT gate outputs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

START = "<!-- AUDIT_GATE_RECEIPT_START -->"
END = "<!-- AUDIT_GATE_RECEIPT_END -->"
REPO = "hiroshitanaka-creator/Cyber-Immunizer"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
PATH_RANGE_RE = re.compile(r"^###\s+[^\s:]+:\d+-\d+\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```[\w+-]*\n.*?```", re.DOTALL)

CI_VALUES = {
    "NOT TRIGGERED", "WORKFLOW PARSE FAILURE", "RUNNER START FAILURE",
    "CHECKOUT FAILURE", "SETUP FAILURE", "INSTALL FAILURE", "TEST FAILURE",
    "DOMAIN FAILURE", "SUCCESS",
}
CODEX_VALUES = {
    "VERIFIED", "FAILED", "NOT VERIFIED", "VERIFIED BY REACTION ONLY",
    "UNRESOLVED THREAD PRESENT",
}
MERGE_VALUES = {"APPROVE", "HOLD", "BLOCK"}
KINDS = {"task_prompt", "pr_audit", "pr_body"}
PLACEHOLDERS = ("<40-hex-sha>", "ここに", "TODO", "TBD", "未記入", "paste")
ASSERTION_WORDS = ("確認済み", "reviewed", "checked", "読了", "確認した")
TASK_SECTIONS = (
    "# Task:", "## Context", "## Scope", "## Files", "### ALLOWED",
    "### REFERENCE_ONLY", "### FROZEN", "### IMPACT", "## Constraints",
    "## Definition of Done", "## On Ambiguity", "## Change Request",
    "## Pre-Prompt Investigation Gate", "## Source Evidence", "## Self Score",
)
TASK_BOOL_KEYS = (
    "source_evidence_present", "pre_prompt_investigation_complete",
    "allowed_files_declared", "impact_declared", "change_request_complete",
    "docs_history_gate_checked", "adversarial_matrix_present",
)
PR_BOOL_KEYS = (
    "docs_history_gate_checked", "scope_checked", "changed_files_checked",
    "current_diff_checked", "current_head_checked", "codex_threads_checked",
)

class ValidationError(Exception):
    pass

def _fail(msg: str) -> None:
    raise ValidationError(msg)

def extract_receipt(text: str) -> tuple[dict[str, Any], str]:
    if text.count(START) != 1 or text.count(END) != 1:
        _fail("expected exactly one audit gate receipt block")
    start = text.index(START) + len(START)
    end = text.index(END)
    if end <= start:
        _fail("receipt end marker appears before start marker")
    area = text[start:end]
    match = re.search(r"```json\s*(.*?)\s*```", area, re.DOTALL)
    if not match:
        _fail("receipt block must contain a fenced json object")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        _fail(f"malformed receipt JSON: {exc}")
    if not isinstance(data, dict):
        _fail("receipt JSON must be an object")
    return data, area

def require_bool_true(data: dict[str, Any], key: str) -> None:
    if data.get(key) is not True:
        _fail(f"{key} must be true")

def validate_shared(data: dict[str, Any], expected_kind: str | None) -> str:
    for key in ("kind", "protocol_version", "repo", "head_sha", "validator_expectation"):
        if key not in data:
            _fail(f"missing required key: {key}")
    kind = data["kind"]
    if kind not in KINDS:
        _fail(f"unknown kind: {kind!r}")
    if expected_kind and kind != expected_kind and not (expected_kind == "pr_body" and kind == "pr_audit"):
        _fail(f"expected kind {expected_kind!r}, got {kind!r}")
    if data["protocol_version"] != 1:
        _fail("protocol_version must be integer 1")
    if data["repo"] != REPO:
        _fail("repo is invalid")
    if not isinstance(data["head_sha"], str) or not SHA_RE.fullmatch(data["head_sha"]):
        _fail("head_sha must be a 40-character hex SHA")
    if data["validator_expectation"] != "PASS":
        _fail("validator_expectation must be PASS")
    return kind

def validate_source_evidence(text: str) -> None:
    marker = "## Source Evidence"
    if marker not in text:
        _fail("missing Source Evidence section")
    section = text.split(marker, 1)[1].split("## Self Score", 1)[0]
    if not PATH_RANGE_RE.search(section) or not FENCE_RE.search(section):
        _fail("Source Evidence must include a path:start-end header and fenced excerpt")
    stripped = re.sub(r"\s+", " ", section).strip().lower()
    if any(word.lower() in stripped for word in ASSERTION_WORDS) and not (PATH_RANGE_RE.search(section) and FENCE_RE.search(section)):
        _fail("Source Evidence is assertion-only")

def validate_task_prompt(data: dict[str, Any], text: str) -> None:
    if not isinstance(data.get("self_score"), int) or data["self_score"] < 98:
        _fail("task_prompt self_score must be an integer >= 98")
    for key in TASK_BOOL_KEYS:
        require_bool_true(data, key)
    missing = [section for section in TASK_SECTIONS if section not in text]
    if missing:
        _fail("missing task prompt section: " + missing[0])
    validate_source_evidence(text)
    for field in ("WHAT", "WHY", "INVARIANT", "DO_NOT", "VERIFY"):
        if not re.search(rf"^-\s*{field}:\s*\S+", text, re.MULTILINE):
            _fail(f"missing Change Request field: {field}")

def validate_pr_audit(data: dict[str, Any], text: str) -> None:
    for key in ("ci_classification", "codex_verification", "merge_recommendation"):
        if key not in data:
            _fail(f"missing required key: {key}")
    if data["ci_classification"] not in CI_VALUES:
        _fail("invalid ci_classification")
    if data["codex_verification"] not in CODEX_VALUES:
        _fail("invalid codex_verification")
    if data["merge_recommendation"] not in MERGE_VALUES:
        _fail("invalid merge_recommendation")
    for key in PR_BOOL_KEYS:
        require_bool_true(data, key)
    for line in ("Code Audit:", "CI Verification:", "Codex Verification:", "Merge Recommendation:"):
        if line not in text:
            _fail(f"missing merge decision line: {line}")
    if data["merge_recommendation"] == "APPROVE":
        if data["ci_classification"] != "SUCCESS":
            _fail("APPROVE requires ci_classification SUCCESS")
        if data["codex_verification"] != "VERIFIED":
            _fail("APPROVE requires codex_verification VERIFIED")
        for key in PR_BOOL_KEYS:
            require_bool_true(data, key)

def validate_pr_body(data: dict[str, Any], text: str, receipt_area: str) -> None:
    lowered_area = receipt_area.lower()
    for token in PLACEHOLDERS:
        if token.lower() in lowered_area:
            _fail(f"placeholder remains in receipt area: {token}")
    if data["kind"] == "pr_body":
        # PR bodies use the PR-audit consistency fields for the machine receipt.
        validate_pr_audit(data, text)
    elif data["kind"] == "pr_audit":
        validate_pr_audit(data, text)
    approve_checked = re.search(r"- \[[xX]\]\s*✅\s*APPROVE", text) is not None
    if approve_checked and data.get("merge_recommendation") != "APPROVE":
        _fail("PR body APPROVE checkbox requires APPROVE receipt")

def validate_text(text: str, expected_kind: str | None = None) -> None:
    data, receipt_area = extract_receipt(text)
    kind = validate_shared(data, expected_kind)
    context = expected_kind or kind
    if context == "task_prompt":
        validate_task_prompt(data, text)
    elif context == "pr_audit":
        validate_pr_audit(data, text)
    elif context == "pr_body":
        validate_pr_body(data, text, receipt_area)
    else:
        _fail(f"unsupported validation context: {context}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--kind", choices=sorted(KINDS), default=None)
    args = parser.parse_args(argv)
    try:
        validate_text(args.path.read_text(encoding="utf-8"), args.kind)
    except (OSError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {args.path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
