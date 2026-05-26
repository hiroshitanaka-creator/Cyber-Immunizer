"""tests/test_ci_workflow.py — Structural tests for .github/workflows/ci.yml.

These tests verify that ci.yml has the correct trigger syntax, security
properties, and does not include any forbidden patterns that would cause
GitHub Actions to reject the workflow or make CI fail-open.

Key invariants tested:
  - ci.yml file exists
  - name: CI is present
  - on: / "on": trigger is present
  - workflow_dispatch: trigger is present (allows manual runs from GitHub UI)
  - push: and pull_request: triggers are present without branch filters
  - branches: ["**"] is NOT present (causes GitHub Actions to reject the file)
  - contents: read permission is present
  - contents: write is NOT present (read-only CI)
  - GEMINI_API_KEY is not used outside comments
  - promote_candidate.py is not referenced
  - git push is not present
  - gemini-paid-credit is not present
  - live-model is not present
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
_CI_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def ci_content() -> str:
    """Return the full ci.yml workflow YAML as a string."""
    assert _CI_WORKFLOW_PATH.exists(), (
        f"ci.yml not found at: {_CI_WORKFLOW_PATH}"
    )
    return _CI_WORKFLOW_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------


class TestCiWorkflowExists:
    def test_ci_yml_exists(self) -> None:
        """ci.yml must exist at .github/workflows/ci.yml."""
        assert _CI_WORKFLOW_PATH.exists(), (
            f"ci.yml not found at {_CI_WORKFLOW_PATH}. "
            "The file must exist so GitHub Actions can load the CI workflow."
        )


# ---------------------------------------------------------------------------
# 2. Workflow name
# ---------------------------------------------------------------------------


class TestCiWorkflowName:
    def test_ci_has_name_ci(self, ci_content: str) -> None:
        """ci.yml must have 'name: CI' so the workflow is displayed as 'CI'
        in the GitHub Actions UI instead of the filename."""
        assert "name: CI" in ci_content, (
            "ci.yml must contain 'name: CI'. "
            "Without this, GitHub Actions displays the filename instead of 'CI'."
        )


# ---------------------------------------------------------------------------
# 3. Trigger definition
# ---------------------------------------------------------------------------


class TestCiWorkflowTriggers:
    def test_ci_has_on_trigger(self, ci_content: str) -> None:
        """ci.yml must have an 'on:' or '\"on\":' trigger section."""
        has_on = '"on":' in ci_content or re.search(r"^on:\s*$", ci_content, re.MULTILINE) is not None
        assert has_on, (
            "ci.yml must contain 'on:' or '\"on\":' trigger definition. "
            "'on' must be quoted in YAML to avoid being parsed as boolean true."
        )

    def test_ci_has_push_trigger(self, ci_content: str) -> None:
        """ci.yml must have a 'push:' trigger."""
        assert "push:" in ci_content, (
            "ci.yml must contain 'push:' trigger so CI runs on every push."
        )

    def test_ci_has_pull_request_trigger(self, ci_content: str) -> None:
        """ci.yml must have a 'pull_request:' trigger."""
        assert "pull_request:" in ci_content, (
            "ci.yml must contain 'pull_request:' trigger so CI runs on every PR."
        )

    def test_ci_has_workflow_dispatch_trigger(self, ci_content: str) -> None:
        """ci.yml must have a 'workflow_dispatch:' trigger.

        This allows the CI workflow to be manually triggered from the GitHub
        Actions UI (Run workflow button), which is useful for diagnosing
        whether Actions is properly configured without waiting for a push or PR.
        """
        assert "workflow_dispatch:" in ci_content, (
            "ci.yml must contain 'workflow_dispatch:' trigger so the CI can be "
            "manually triggered from the GitHub Actions UI. "
            "Add 'workflow_dispatch:' under the '\"on\":' section."
        )

    def test_ci_has_no_branches_wildcard_filter(self, ci_content: str) -> None:
        """ci.yml must NOT contain 'branches: [\"**\"]'.

        This branch filter pattern is rejected by GitHub Actions and causes
        immediate 0-second failures before any job steps run.  Omitting
        the branch filter means CI runs on all branches, which is the
        intended behaviour.
        """
        assert 'branches: ["**"]' not in ci_content, (
            "ci.yml must NOT contain 'branches: [\"**\"]'. "
            "This pattern causes GitHub Actions to reject the workflow file, "
            "resulting in 0-second failures before any job starts. "
            "Remove the branch filter to run CI on all branches."
        )


# ---------------------------------------------------------------------------
# 4. Permissions — read-only CI
# ---------------------------------------------------------------------------


class TestCiWorkflowPermissions:
    def test_ci_has_contents_read(self, ci_content: str) -> None:
        """ci.yml must have 'contents: read' permission (read-only CI)."""
        assert "contents: read" in ci_content, (
            "ci.yml must contain 'contents: read' permission. "
            "CI is read-only and must not write to the repository."
        )

    def test_ci_has_no_contents_write(self, ci_content: str) -> None:
        """ci.yml must NOT have 'contents: write' permission.

        The CI workflow is intentionally read-only.  Adding write permissions
        would allow the workflow to modify the repository, which violates the
        safe CI contract.
        """
        assert "contents: write" not in ci_content, (
            "ci.yml must NOT contain 'contents: write'. "
            "The CI workflow is read-only and must never write to the repository."
        )


# ---------------------------------------------------------------------------
# 5. Forbidden patterns — no live API calls, no promote, no git writes
# ---------------------------------------------------------------------------


class TestCiWorkflowForbiddenPatterns:
    def test_ci_has_no_gemini_api_key_usage(self, ci_content: str) -> None:
        """ci.yml must not use GEMINI_API_KEY outside of comments.

        Any reference to GEMINI_API_KEY in non-comment lines would indicate
        a live Gemini API call, which must never happen in the read-only CI.
        Comments may mention it for documentation purposes.
        """
        non_comment_lines = [
            line for line in ci_content.splitlines()
            if "GEMINI_API_KEY" in line and not line.lstrip().startswith("#")
        ]
        assert len(non_comment_lines) == 0, (
            "ci.yml must NOT reference GEMINI_API_KEY outside of comments. "
            "The CI workflow must not make live Gemini API calls. "
            f"Found in: {non_comment_lines}"
        )

    def test_ci_has_no_promote_candidate(self, ci_content: str) -> None:
        """ci.yml must NOT reference promote_candidate.py.

        The CI workflow is read-only and must not promote any candidates
        to the repository.  Promotion is handled separately by the
        immunization_loop.yml workflow.
        """
        assert "promote_candidate.py" not in ci_content, (
            "ci.yml must NOT reference 'promote_candidate.py'. "
            "The CI workflow is read-only; promotion is handled by immunization_loop.yml."
        )

    def test_ci_has_no_git_push(self, ci_content: str) -> None:
        """ci.yml must NOT contain 'git push'.

        The CI workflow is read-only and must never push commits or tags
        to the repository.
        """
        assert "git push" not in ci_content, (
            "ci.yml must NOT contain 'git push'. "
            "The CI workflow is read-only and must not write to the repository."
        )

    def test_ci_has_no_gemini_paid_credit(self, ci_content: str) -> None:
        """ci.yml must NOT reference 'gemini-paid-credit'.

        Any reference to gemini-paid-credit would indicate a live API call
        with billing implications, which is strictly forbidden in read-only CI.
        """
        assert "gemini-paid-credit" not in ci_content, (
            "ci.yml must NOT contain 'gemini-paid-credit'. "
            "The CI workflow must not make billable Gemini API calls."
        )

    def test_ci_has_no_live_model(self, ci_content: str) -> None:
        """ci.yml must NOT reference 'live-model'.

        Any reference to a live model in CI would indicate an attempt to
        make real API calls during testing, which is forbidden.
        """
        assert "live-model" not in ci_content, (
            "ci.yml must NOT contain 'live-model'. "
            "The CI workflow must not use live models."
        )
