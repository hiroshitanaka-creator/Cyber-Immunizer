"""Tests for the stdlib GPT output quality gate validator."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_gpt_gate_output.py"
FIXTURES = ROOT / "tests" / "fixtures" / "gpt_gate"


def run_validator(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args, str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_pass(path: Path, *args: str) -> None:
    result = run_validator(path, *args)
    assert result.returncode == 0, result.stderr
    assert "PASS:" in result.stdout


def assert_fail(name: str, *args: str) -> None:
    result = run_validator(FIXTURES / "invalid" / name, *args)
    assert result.returncode != 0, result.stdout
    assert "FAIL:" in result.stderr


def test_valid_task_prompt_receipt_and_sections_pass() -> None:
    assert_pass(FIXTURES / "valid" / "valid_task_prompt.md")
    assert_pass(FIXTURES / "valid" / "valid_task_prompt.md", "--kind", "task_prompt")


def test_valid_pr_audit_hold_passes() -> None:
    assert_pass(FIXTURES / "valid" / "valid_pr_audit.md", "--kind", "pr_audit")


def test_valid_pr_audit_approve_passes() -> None:
    assert_pass(FIXTURES / "valid" / "valid_pr_audit_approve.md")


def test_valid_pr_body_receipt_passes() -> None:
    assert_pass(FIXTURES / "valid" / "valid_pr_body.md", "--kind", "pr_body")


def test_missing_receipt_block_fails() -> None:
    assert_fail("missing_receipt.md")


def test_multiple_receipt_blocks_fail() -> None:
    assert_fail("multiple_receipts.md")


def test_malformed_json_fails() -> None:
    assert_fail("malformed_json.md")


def test_invalid_kind_fails() -> None:
    assert_fail("invalid_kind.md")


def test_invalid_head_sha_fails() -> None:
    assert_fail("invalid_head_sha.md")


def test_validator_expectation_not_pass_fails() -> None:
    assert_fail("validator_expectation_not_pass.md")


def test_task_prompt_self_score_below_98_fails() -> None:
    assert_fail("task_self_score_below_98.md")


def test_task_prompt_missing_source_evidence_fails() -> None:
    assert_fail("task_missing_source_evidence.md")


def test_task_prompt_assertion_only_source_evidence_fails() -> None:
    assert_fail("task_assertion_only_source_evidence.md")


def test_task_prompt_missing_impact_fails() -> None:
    assert_fail("task_missing_impact.md")


def test_task_prompt_missing_change_request_field_fails() -> None:
    assert_fail("task_missing_change_request_field.md")


def test_pr_audit_invalid_ci_classification_fails() -> None:
    assert_fail("pr_invalid_ci.md")


def test_pr_audit_invalid_codex_verification_fails() -> None:
    assert_fail("pr_invalid_codex.md")


def test_pr_audit_approve_while_ci_not_success_fails() -> None:
    assert_fail("pr_approve_ci_not_success.md")


def test_pr_audit_approve_while_codex_not_verified_fails() -> None:
    assert_fail("pr_approve_codex_not_verified.md")


def test_pr_audit_approve_while_docs_history_gate_false_fails() -> None:
    assert_fail("pr_approve_docs_false.md")


def test_pr_body_placeholder_receipt_fails() -> None:
    assert_fail("pr_body_placeholder_receipt.md", "--kind", "pr_body")


def test_pr_body_checked_approve_requires_approve_receipt_fails() -> None:
    assert_fail("pr_body_approve_bad_receipt.md", "--kind", "pr_body")
