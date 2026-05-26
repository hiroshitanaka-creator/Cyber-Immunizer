"""tests/test_workflow.py — Structural tests for the GitHub Actions workflow.

These tests verify security and correctness properties of
.github/workflows/immunization_loop.yml using string/line-level inspection.
No YAML parser dependency is required — checks are intentionally kept at
the textual level to be robust against minor formatting differences.

Key invariants tested:
  - persist-ledger job exists and has the correct security properties
  - promote job does NOT handle ledger persistence
  - No continue-on-error on ledger artifact download
  - Workflow has concurrency to prevent ledger race conditions
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "immunization_loop.yml"


@pytest.fixture(scope="module")
def workflow_content() -> str:
    """Return the full workflow YAML as a string."""
    assert _WORKFLOW_PATH.exists(), (
        f"Workflow file not found: {_WORKFLOW_PATH}"
    )
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def persist_ledger_section(workflow_content: str) -> str:
    """Extract the persist-ledger job section from the workflow."""
    # Find the section between persist-ledger: and the next top-level job
    match = re.search(
        r"(persist-ledger:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'persist-ledger:' job in workflow. "
        "The persist-ledger job is required to prevent budget cap fail-open."
    )
    return match.group(1)


@pytest.fixture(scope="module")
def promote_section(workflow_content: str) -> str:
    """Extract the promote job section from the workflow."""
    match = re.search(
        r"(  promote:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, "Could not find 'promote:' job in workflow."
    return match.group(1)


# ---------------------------------------------------------------------------
# 1. persist-ledger job existence and structure
# ---------------------------------------------------------------------------


class TestPersistLedgerJobExists:
    def test_persist_ledger_job_defined(self, workflow_content: str) -> None:
        """persist-ledger job must exist in the workflow."""
        assert "persist-ledger:" in workflow_content, (
            "The 'persist-ledger:' job is missing from the workflow. "
            "This job is required so API usage is recorded even when the "
            "candidate fails the adoption gate."
        )

    def test_persist_ledger_has_contents_write(self, persist_ledger_section: str) -> None:
        """persist-ledger job must have contents: write permission."""
        assert "contents: write" in persist_ledger_section, (
            "persist-ledger job must have 'contents: write' permission "
            "to commit the API usage ledger."
        )

    def test_persist_ledger_depends_on_propose(self, persist_ledger_section: str) -> None:
        """persist-ledger job must depend on the propose job."""
        assert "needs: propose" in persist_ledger_section or (
            "needs:" in persist_ledger_section and "propose" in persist_ledger_section
        ), (
            "persist-ledger job must have 'needs: propose' to ensure it runs "
            "after the propose job uploads the ledger artifact."
        )

    def test_persist_ledger_runs_only_when_ledger_changed(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger must only run when ledger_changed == 'true'."""
        assert "ledger_changed" in persist_ledger_section, (
            "persist-ledger job must check needs.propose.outputs.ledger_changed"
        )

    def test_persist_ledger_downloads_ledger_artifact(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger must download the api-usage-ledger artifact."""
        assert "api-usage-ledger" in persist_ledger_section, (
            "persist-ledger job must download the 'api-usage-ledger' artifact"
        )

    def test_persist_ledger_commits_ledger(self, persist_ledger_section: str) -> None:
        """persist-ledger must commit api_usage_ledger.json."""
        assert "api_usage_ledger.json" in persist_ledger_section, (
            "persist-ledger job must add data/api_usage_ledger.json to git"
        )


# ---------------------------------------------------------------------------
# 2. persist-ledger security: NO secrets, NO generated code
# ---------------------------------------------------------------------------


class TestPersistLedgerSecurity:
    def test_persist_ledger_has_no_gemini_api_key(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger job must NOT pass GEMINI_API_KEY as a secret or env var.

        Write permissions and model API secrets must never appear in the
        same job.  The persist-ledger job has write permission to commit
        the ledger, so it must not receive GEMINI_API_KEY.

        Note: comments may mention GEMINI_API_KEY for documentation;
        we check for actual usage patterns like secrets.GEMINI_API_KEY.
        """
        assert "secrets.GEMINI_API_KEY" not in persist_ledger_section, (
            "persist-ledger job must NOT pass 'secrets.GEMINI_API_KEY'. "
            "Write permissions and model API secrets must be in separate jobs."
        )

    def test_persist_ledger_does_not_download_candidate_detector(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger must NOT download the candidate-detector artifact."""
        assert "candidate-detector" not in persist_ledger_section, (
            "persist-ledger job must NOT download the candidate-detector artifact. "
            "It only handles ledger persistence; generated code must not be "
            "present in a job with write permissions."
        )

    def test_persist_ledger_does_not_download_mutation_patch(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger must NOT download the mutation-patch artifact."""
        assert "mutation-patch" not in persist_ledger_section, (
            "persist-ledger job must NOT download the mutation-patch artifact. "
            "Generated mutation data must not be present in a job with write "
            "permissions and no API-key isolation."
        )


# ---------------------------------------------------------------------------
# 3. promote job does NOT handle ledger persistence
# ---------------------------------------------------------------------------


class TestPromoteJobLedgerIsolation:
    def test_promote_does_not_download_ledger_artifact(
        self, promote_section: str
    ) -> None:
        """promote job must NOT download the api-usage-ledger artifact.

        Ledger persistence is the responsibility of persist-ledger.  If
        promote also downloads and commits the ledger, then API usage from
        rejected candidates (where promote does not run) is not persisted,
        making the budget cap fail-open.
        """
        assert "api-usage-ledger" not in promote_section, (
            "promote job must NOT download the 'api-usage-ledger' artifact. "
            "Ledger persistence is handled by the persist-ledger job."
        )

    def test_promote_does_not_git_add_ledger(self, promote_section: str) -> None:
        """promote job must NOT git add api_usage_ledger.json."""
        assert "api_usage_ledger.json" not in promote_section, (
            "promote job must NOT git add 'api_usage_ledger.json'. "
            "Ledger is committed by the persist-ledger job."
        )


# ---------------------------------------------------------------------------
# 4. No continue-on-error on ledger artifact download
# ---------------------------------------------------------------------------


class TestNoContinueOnErrorForLedger:
    def test_ledger_artifact_download_has_no_continue_on_error(
        self, persist_ledger_section: str
    ) -> None:
        """Ledger artifact download in persist-ledger must not have continue-on-error: true.

        If ledger_changed is true but the artifact cannot be retrieved,
        that is a critical error: failing here prevents the budget cap
        from becoming fail-open on future runs.  Using continue-on-error: true
        would silently allow the run to succeed with missing budget data.

        Note: comments may describe the absence of continue-on-error;
        we check only for the actual YAML directive 'continue-on-error: true'.
        """
        assert "continue-on-error: true" not in persist_ledger_section, (
            "persist-ledger job must NOT use 'continue-on-error: true'. "
            "A missing ledger artifact when ledger_changed=true is a critical error."
        )

    def test_workflow_does_not_use_continue_on_error_true_for_ledger(
        self, workflow_content: str
    ) -> None:
        """The workflow must not have 'continue-on-error: true' in persist-ledger section."""
        lines = workflow_content.splitlines()
        in_persist_ledger = False
        for i, line in enumerate(lines):
            if "persist-ledger:" in line:
                in_persist_ledger = True
            elif in_persist_ledger and re.match(r"  [a-zA-Z][\w-]+:", line):
                in_persist_ledger = False
            # Only flag the actual YAML directive, not comments
            if in_persist_ledger and "continue-on-error: true" in line:
                pytest.fail(
                    f"Found 'continue-on-error: true' in persist-ledger "
                    f"section at line {i+1}: {line!r}"
                )


# ---------------------------------------------------------------------------
# 5. Workflow concurrency prevents ledger race conditions
# ---------------------------------------------------------------------------


class TestWorkflowConcurrency:
    def test_workflow_has_concurrency_key(self, workflow_content: str) -> None:
        """Workflow must have a top-level concurrency configuration.

        Without concurrency control, two simultaneous runs on the same
        branch can both commit to the ledger in a conflicting order,
        leading to lost records or push failures.
        """
        assert "concurrency:" in workflow_content, (
            "Workflow must have a 'concurrency:' key to prevent concurrent "
            "runs from racing to write the API usage ledger."
        )

    def test_concurrency_cancel_in_progress_is_false(
        self, workflow_content: str
    ) -> None:
        """concurrency.cancel-in-progress must be false.

        cancel-in-progress: true would cancel a running evolution cycle,
        potentially leaving the ledger in a partially-written state.
        """
        assert "cancel-in-progress: false" in workflow_content, (
            "concurrency.cancel-in-progress must be 'false' so a running "
            "evolution cycle is never cancelled mid-way."
        )

    def test_concurrency_uses_github_ref(self, workflow_content: str) -> None:
        """Concurrency group should be scoped to the git ref/branch."""
        assert "github.ref" in workflow_content, (
            "Concurrency group should include github.ref to scope "
            "concurrency to a specific branch."
        )


# ---------------------------------------------------------------------------
# 6. GEMINI_API_KEY is only in the propose job
# ---------------------------------------------------------------------------


class TestGeminiApiKeyScoping:
    def test_gemini_api_key_in_propose(self, workflow_content: str) -> None:
        """GEMINI_API_KEY must appear in the propose job."""
        assert "GEMINI_API_KEY" in workflow_content, (
            "GEMINI_API_KEY must be configured in the propose job."
        )

    def test_gemini_api_key_not_passed_in_persist_ledger(
        self, persist_ledger_section: str
    ) -> None:
        """GEMINI_API_KEY secret must NOT be passed in persist-ledger job."""
        assert "secrets.GEMINI_API_KEY" not in persist_ledger_section

    def test_gemini_api_key_not_passed_in_promote(self, promote_section: str) -> None:
        """GEMINI_API_KEY secret must NOT be passed in promote job."""
        assert "secrets.GEMINI_API_KEY" not in promote_section
