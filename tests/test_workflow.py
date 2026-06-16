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


class TestPersistLedgerIfCondition:
    def test_persist_ledger_if_has_always(self, persist_ledger_section: str) -> None:
        """persist-ledger job-level if must include always().

        Without always(), if the propose job exits with failure status, GitHub
        Actions will skip all dependent jobs by default — even when the if
        expression would otherwise evaluate to true.  always() overrides that
        behaviour so persist-ledger runs whenever ledger_changed=true, regardless
        of whether propose succeeded or failed.
        """
        assert "always()" in persist_ledger_section, (
            "persist-ledger job if condition must contain 'always()' so it runs "
            "even when the propose job exits with a failure status."
        )

    def test_persist_ledger_if_checks_ledger_changed(
        self, persist_ledger_section: str
    ) -> None:
        """persist-ledger if must still gate on ledger_changed == 'true'.

        always() alone would run persist-ledger unconditionally.  The condition
        must also require ledger_changed=true so no unnecessary write commit
        occurs when no API call was made.
        """
        assert "ledger_changed" in persist_ledger_section, (
            "persist-ledger if condition must include ledger_changed check "
            "so the job only runs when the ledger was actually modified."
        )


class TestFinalizePersistLedgerAcceptance:
    def test_finalize_accepts_skipped_when_ledger_not_changed(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must accept persist-ledger skipped when ledger_changed=false.

        When no API call was made the ledger is unchanged and persist-ledger is
        legitimately skipped.  The finalize job must NOT treat this as an error.
        The strict check (PERSIST_RESULT != success) is only applied when
        LEDGER_CHANGED = true.
        """
        # Verify the guard is conditional on LEDGER_CHANGED=true,
        # not an unconditional persist-ledger result check.
        assert "LEDGER_CHANGED" in finalize_section or "ledger_changed" in finalize_section, (
            "finalize-propose-status must gate the persist-ledger result check "
            "on ledger_changed=true, so skipped is accepted when no API call occurred."
        )
        # The != success check must be inside a ledger_changed=true branch
        finalize_lines = finalize_section.splitlines()
        in_ledger_block = False
        found_not_success_inside_ledger_block = False
        for line in finalize_lines:
            stripped = line.strip()
            if 'LEDGER_CHANGED' in stripped and '"true"' in stripped or \
               "LEDGER_CHANGED" in stripped and "'true'" in stripped:
                in_ledger_block = True
            if in_ledger_block and ('!= "success"' in stripped or "!= 'success'" in stripped):
                found_not_success_inside_ledger_block = True
                break
            # Reset on fi (block end) — simple heuristic
            if stripped == "fi":
                in_ledger_block = False
        assert found_not_success_inside_ledger_block, (
            "The persist-ledger != success check must be nested inside a "
            "ledger_changed=true branch so skipped is only rejected when the "
            "ledger was actually modified."
        )


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


# ---------------------------------------------------------------------------
# 7. propose job outputs propose_exit_code and propose_failed
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def propose_section(workflow_content: str) -> str:
    """Extract the propose job section from the workflow."""
    match = re.search(
        r"(  propose:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, "Could not find 'propose:' job in workflow."
    return match.group(1)


@pytest.fixture(scope="module")
def finalize_section(workflow_content: str) -> str:
    """Extract the finalize-propose-status job section from the workflow."""
    match = re.search(
        r"(  finalize-propose-status:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'finalize-propose-status:' job in workflow. "
        "This job is required to surface propose failures after ledger persistence."
    )
    return match.group(1)


class TestProposeOutputs:
    def test_propose_has_propose_exit_code_output(self, propose_section: str) -> None:
        """propose job must declare propose_exit_code as an output."""
        assert "propose_exit_code" in propose_section, (
            "propose job must declare 'propose_exit_code' output so downstream "
            "jobs can inspect the propose script's exit status."
        )

    def test_propose_has_propose_failed_output(self, propose_section: str) -> None:
        """propose job must declare propose_failed as an output."""
        assert "propose_failed" in propose_section, (
            "propose job must declare 'propose_failed' output so finalize-propose-status "
            "and promote can gate on whether propose_mutation.py succeeded."
        )


# ---------------------------------------------------------------------------
# 8. propose step uses set +e to capture exit code without immediate abort
# ---------------------------------------------------------------------------


class TestProposeSetPlusE:
    def test_propose_step_uses_set_plus_e(self, propose_section: str) -> None:
        """Propose mutation patch step must use 'set +e' to disable immediate exit.

        propose_mutation.py may fail AFTER the API call has already updated the
        ledger.  Without set +e, a non-zero exit would skip ledger_changed
        detection and artifact upload — leaving the budget cap fail-open.
        """
        assert "set +e" in propose_section, (
            "The 'Propose mutation patch' step must use 'set +e' to prevent "
            "immediate exit on non-zero, so ledger artifact upload always runs."
        )

    def test_propose_step_captures_exit_code_in_variable(
        self, propose_section: str
    ) -> None:
        """Propose step must capture exit code in PROPOSE_EXIT (or similar variable).

        After 'set +e', the propose script's exit code must be saved — otherwise
        there is no way to surface the failure via propose_failed output.
        """
        assert "PROPOSE_EXIT" in propose_section, (
            "Propose step must store the propose script exit code in a variable "
            "(e.g., PROPOSE_EXIT=$?) for later output."
        )

    def test_propose_step_does_not_immediately_exit_on_failure(
        self, propose_section: str
    ) -> None:
        """Propose step must NOT immediately exit 1 after the propose if/elif block.

        Immediately exiting would skip ledger_changed detection and artifact upload.
        The failure must be surfaced by finalize-propose-status AFTER persist-ledger.
        """
        # Extract just the propose step run block to avoid false positives
        # from other steps.  Look for the run: block inside the propose step.
        step_match = re.search(
            r"name: Propose mutation patch.*?run: \|(.+?)(?=\n      - name:|\Z)",
            propose_section,
            re.DOTALL,
        )
        if step_match:
            run_block = step_match.group(1)
            # Must not contain a bare "exit 1" after the if/elif chain
            # (there should be no unconditional exit 1 at the end)
            lines = run_block.splitlines()
            # Find lines that are bare exit 1 (not inside comments or conditions)
            bare_exit_lines = [
                l for l in lines
                if re.match(r"\s*exit 1\s*$", l) and not l.lstrip().startswith("#")
            ]
            assert len(bare_exit_lines) == 0, (
                f"Propose step must NOT have a bare 'exit 1' that would skip "
                f"ledger artifact upload. Found: {bare_exit_lines}"
            )

    def test_ledger_changed_detection_follows_propose_command(
        self, propose_section: str
    ) -> None:
        """ledger_changed detection must appear AFTER the propose command block.

        If ledger_changed detection is before the propose command, it will
        always see no change.  It must be computed unconditionally after the
        propose script runs, so even a failed run's ledger update is detected.
        """
        # Verify ledger_changed output is written in the propose step
        assert "ledger_changed" in propose_section, (
            "ledger_changed must be computed and output in the propose step."
        )
        # Verify propose command (the if/elif dispatch) appears before ledger_changed output
        propose_cmd_pos = propose_section.find("PROPOSE_EXIT=$?")
        ledger_changed_pos = propose_section.find("ledger_changed=")
        assert propose_cmd_pos != -1, "PROPOSE_EXIT=$? not found in propose section."
        assert ledger_changed_pos != -1, "ledger_changed= not found in propose section."
        assert propose_cmd_pos < ledger_changed_pos, (
            "ledger_changed detection must come AFTER the propose command "
            "exit code capture, not before."
        )


# ---------------------------------------------------------------------------
# 9. Upload API usage ledger artifact uses if: always()
# ---------------------------------------------------------------------------


class TestLedgerArtifactUploadCondition:
    def test_ledger_upload_uses_always_condition(self, propose_section: str) -> None:
        """Upload API usage ledger artifact step must use 'if: always()'.

        Without always(), if the propose step exits non-zero (e.g. after an API
        call that modified the ledger), the upload step is skipped and the
        ledger artifact is never uploaded — making the budget cap fail-open.
        """
        # Find the ledger upload step
        upload_match = re.search(
            r"Upload API usage ledger artifact.*?(?=\n      - name:|\Z)",
            propose_section,
            re.DOTALL,
        )
        assert upload_match is not None, (
            "Could not find 'Upload API usage ledger artifact' step in propose job."
        )
        upload_block = upload_match.group(0)
        assert "always()" in upload_block, (
            "'Upload API usage ledger artifact' step must use 'if: always()' "
            "(or an expression containing always()) so it runs even when the "
            "propose script exits non-zero."
        )


# ---------------------------------------------------------------------------
# 10. finalize-propose-status job structure and behavior
# ---------------------------------------------------------------------------


class TestFinalizeProposeStatusJob:
    def test_finalize_propose_status_job_exists(
        self, workflow_content: str
    ) -> None:
        """finalize-propose-status job must exist in the workflow."""
        assert "finalize-propose-status:" in workflow_content, (
            "The 'finalize-propose-status:' job is missing. "
            "This job surfaces propose failures after ledger persistence is confirmed."
        )

    def test_finalize_propose_status_needs_persist_ledger(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must depend on persist-ledger.

        This ensures the failure is surfaced only after the ledger is committed,
        keeping the budget cap fail-closed even when propose_mutation.py fails.
        """
        assert "persist-ledger" in finalize_section, (
            "finalize-propose-status job must have persist-ledger in its needs list."
        )

    def test_finalize_propose_status_runs_always(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must run unconditionally (if: always()).

        It must run regardless of whether persist-ledger was skipped (no ledger
        change) to always reflect the true propose outcome.
        """
        assert "always()" in finalize_section, (
            "finalize-propose-status job must have 'if: always()' so it always "
            "runs regardless of whether persist-ledger was skipped."
        )

    def test_finalize_propose_status_fails_on_propose_failure(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must exit 1 when propose_failed is true."""
        assert "exit 1" in finalize_section, (
            "finalize-propose-status job must call 'exit 1' to fail the workflow "
            "when propose_failed is true."
        )
        assert "propose_failed" in finalize_section or "PROPOSE_FAILED" in finalize_section, (
            "finalize-propose-status must check the propose_failed output."
        )

    def test_finalize_propose_status_fails_on_persist_ledger_non_success(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must fail when ledger_changed=true and persist-ledger != success.

        Checking only for 'failure' is insufficient: persist-ledger could be
        'skipped' or 'cancelled' and the ledger would still be uncommitted.
        The condition must use != success so all non-success results are rejected
        when the ledger was modified.
        """
        assert '!= "success"' in finalize_section or "!= 'success'" in finalize_section, (
            "finalize-propose-status must check PERSIST_RESULT != 'success' "
            "(not just == 'failure') when ledger_changed=true.  A skipped or "
            "cancelled persist-ledger job also leaves the ledger uncommitted."
        )

    def test_finalize_propose_status_has_no_gemini_api_key(
        self, finalize_section: str
    ) -> None:
        """finalize-propose-status must NOT pass GEMINI_API_KEY."""
        assert "secrets.GEMINI_API_KEY" not in finalize_section, (
            "finalize-propose-status must not have GEMINI_API_KEY."
        )


# ---------------------------------------------------------------------------
# 11. promote job sequences after persist-ledger
# ---------------------------------------------------------------------------


class TestPromoteSequencing:
    def test_promote_needs_persist_ledger(self, promote_section: str) -> None:
        """promote job must have persist-ledger in its needs list.

        This ensures GitHub Actions runs persist-ledger to completion before
        promote starts, preventing concurrent write commits to the same branch.
        """
        assert "persist-ledger" in promote_section, (
            "promote job must have 'persist-ledger' in its needs list to prevent "
            "concurrent write commits with the persist-ledger job."
        )

    def test_promote_if_checks_persist_ledger_result(
        self, promote_section: str
    ) -> None:
        """promote if condition must verify persist-ledger succeeded or was skipped.

        If persist-ledger failed, API budget data may be uncommitted.  Promote
        must not run in that state.
        """
        # Check for either 'success' or 'skipped' in the promote if condition
        assert "persist-ledger" in promote_section, (
            "promote if condition must reference persist-ledger result."
        )
        assert "success" in promote_section or "skipped" in promote_section, (
            "promote if condition must allow 'success' or 'skipped' for persist-ledger."
        )

    def test_promote_if_checks_propose_failed(self, promote_section: str) -> None:
        """promote if condition must check that propose did not fail.

        If propose_mutation.py exited non-zero, the candidate patch may be
        corrupt or incomplete.  Promote must be blocked in that case.
        """
        assert "propose_failed" in promote_section, (
            "promote if condition must check needs.propose.outputs.propose_failed "
            "to prevent promoting a candidate from a failed propose run."
        )

    def test_promote_if_uses_always(self, promote_section: str) -> None:
        """promote if condition must start with always() to override default skip.

        When upstream jobs are skipped, GitHub Actions skips dependent jobs by
        default.  always() overrides this so the explicit conditions take effect.
        """
        assert "always()" in promote_section, (
            "promote if condition must include always() to allow the explicit "
            "gate conditions to be evaluated even when some needs were skipped."
        )


# ---------------------------------------------------------------------------
# 12. Hyphen-containing job IDs must use bracket notation in expressions
# ---------------------------------------------------------------------------


class TestBracketNotationForHyphenatedJobIds:
    """GitHub Actions does not support dot notation for job IDs that contain
    hyphens inside ${{ }} expressions.  All references to hyphenated job IDs
    must use bracket notation: needs['job-id'].result instead of
    needs.job-id.result.
    """

    def test_no_dot_notation_for_persist_ledger(
        self, workflow_content: str
    ) -> None:
        """Workflow must NOT reference persist-ledger via dot notation.

        ``needs.persist-ledger`` in a ${{ }} expression is a GitHub Actions
        syntax error because hyphens are not valid in dot-notation identifiers.
        """
        assert "needs.persist-ledger" not in workflow_content, (
            "Found 'needs.persist-ledger' (dot notation) in the workflow. "
            "Hyphenated job IDs must be referenced with bracket notation: "
            "needs['persist-ledger'].result"
        )

    def test_bracket_notation_for_persist_ledger_result_exists(
        self, workflow_content: str
    ) -> None:
        """Workflow must use bracket notation needs['persist-ledger'].result."""
        assert "needs['persist-ledger'].result" in workflow_content, (
            "Expected needs['persist-ledger'].result (bracket notation) in the "
            "workflow, but it was not found.  Hyphenated job IDs must use "
            "bracket notation inside ${{ }} expressions."
        )

    def test_no_dot_notation_for_finalize_propose_status(
        self, workflow_content: str
    ) -> None:
        """Workflow must NOT reference finalize-propose-status via dot notation."""
        assert "needs.finalize-propose-status" not in workflow_content, (
            "Found 'needs.finalize-propose-status' (dot notation). "
            "Use bracket notation: needs['finalize-propose-status'].result"
        )

    def test_no_hyphenated_job_id_dot_notation_in_expressions(
        self, workflow_content: str
    ) -> None:
        """No hyphen-containing job ID may appear after 'needs.' inside expressions.

        Scans every ${{ ... }} expression block and rejects any pattern of the
        form needs.<word>-<word> which is invalid GitHub Actions syntax.
        """
        import re as _re

        # Extract all ${{ ... }} expression bodies
        expression_bodies = _re.findall(r"\$\{\{(.*?)\}\}", workflow_content, _re.DOTALL)
        violations = []
        for expr in expression_bodies:
            # Match needs.<identifier-with-hyphen>
            for m in _re.finditer(r"needs\.([A-Za-z][\w]*-[\w\-]*)", expr):
                violations.append(m.group(0))

        assert not violations, (
            "Found hyphenated job IDs referenced via dot notation inside "
            "${{ }} expressions (invalid GitHub Actions syntax): "
            + ", ".join(violations)
            + ".  Use bracket notation, e.g. needs['job-id'].result"
        )


# ---------------------------------------------------------------------------
# 13. YAML fix: passed_adoption_gate extraction is a single-line Python command
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def evaluate_section(workflow_content: str) -> str:
    """Extract the evaluate job section from the workflow."""
    match = re.search(
        r"(  evaluate:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, "Could not find 'evaluate:' job in workflow."
    return match.group(1)


class TestPassedAdoptionGateExtractionYamlFix:
    """Verify that the multi-line python -c YAML syntax error has been fixed.

    The original workflow had a multi-line python -c "\\nimport json, sys\\n..."
    block whose continuation lines were not indented as YAML literal-block
    content, causing 'Invalid workflow file / yaml syntax' errors in GitHub Actions.
    All checks below confirm the fix is in place.
    """

    def test_no_multiline_python_c_gate_pattern(self, workflow_content: str) -> None:
        """GATE=$(python -c "...) must NOT be followed by a newline + bare Python code.

        The pattern GATE=$(python -c "\\n followed by import/continuation lines
        outside the YAML run: | block indentation is invalid YAML and causes
        'yaml syntax error on line N' in GitHub Actions.
        """
        lines = workflow_content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # Detect a line that opens a python -c string but does NOT close it
            if 'GATE=$(python -c "' in stripped and not stripped.endswith('")'):
                # The line ends with an open quote — the python -c spans multiple lines
                pytest.fail(
                    f"Found multi-line python -c pattern at line {i + 1}: {line!r}. "
                    "Replace with a single-line python -c command to avoid YAML syntax errors."
                )

    def test_no_bare_import_json_sys_at_line_start(self, workflow_content: str) -> None:
        """There must be no 'import json, sys' or 'import json,sys' at the start of a line.

        In the broken workflow, 'import json, sys' appeared as a bare shell line
        (after GATE=$(python -c "\\n)) which is invalid YAML inside a run: | block
        when not properly indented.  After the fix, the import is embedded inside
        a single-line python -c string — it never appears at the raw line level.
        """
        for i, line in enumerate(workflow_content.splitlines()):
            stripped = line.lstrip()
            if re.match(r"^import json,\s*sys", stripped):
                pytest.fail(
                    f"Found bare 'import json, sys' at line {i + 1}: {line!r}. "
                    "This was left over from a multi-line python -c block that "
                    "caused YAML syntax errors.  Embed the import inside a "
                    "single-line python -c string instead."
                )

    def test_passed_adoption_gate_extraction_is_single_line_python(
        self, evaluate_section: str
    ) -> None:
        """The passed_adoption_gate extraction command must be a single-line python -c.

        A correct single-line command looks like:
          GATE=$(python -c "import json; r=json.load(...); ...; print(...)")
        All logic must be on one line so YAML does not misparse the continuation
        lines as shell commands.
        """
        match = re.search(
            r'GATE=\$\(python -c "(.*?)"\)',
            evaluate_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find GATE=$(python -c \"...\") in the evaluate job. "
            "The passed_adoption_gate extraction must use a python -c command."
        )
        python_expr = match.group(1)
        # Must not contain a raw newline (which would indicate multi-line)
        assert "\n" not in python_expr, (
            "The python -c expression for passed_adoption_gate extraction spans "
            "multiple lines.  All logic must be on one line to avoid YAML errors. "
            f"Found expression: {python_expr!r}"
        )
        # Must contain the key logic
        assert "passed_adoption_gate" in python_expr, (
            "The single-line python -c expression must reference 'passed_adoption_gate'."
        )

    def test_bracket_notation_persist_ledger_result_maintained(
        self, workflow_content: str
    ) -> None:
        """needs['persist-ledger'].result bracket notation must still be present.

        The YAML fix must not inadvertently remove or break the bracket notation
        required for hyphenated job ID references in GitHub Actions expressions.
        """
        assert "needs['persist-ledger'].result" in workflow_content, (
            "needs['persist-ledger'].result (bracket notation) was removed or broken "
            "by the YAML fix.  This reference is required for correct GitHub Actions "
            "expression evaluation with hyphenated job IDs."
        )

    def test_no_dot_notation_persist_ledger_result(self, workflow_content: str) -> None:
        """needs.persist-ledger.result (dot notation) must not exist in the workflow.

        Dot notation for hyphenated job IDs is invalid in GitHub Actions ${{ }}
        expressions.  Only bracket notation needs['persist-ledger'].result is valid.
        """
        assert "needs.persist-ledger.result" not in workflow_content, (
            "Found 'needs.persist-ledger.result' (dot notation) in the workflow. "
            "Dot notation is invalid for hyphenated job IDs in GitHub Actions. "
            "Use needs['persist-ledger'].result instead."
        )


# ---------------------------------------------------------------------------
# 14. Commit promoted changes step — shell quoting correctness
# ---------------------------------------------------------------------------


class TestCommitPromotedChangesShellQuoting:
    """Verify that the 'Commit promoted changes' step does not use escaped
    nested python -c inside a git commit message (which causes shell syntax
    errors) and instead uses a pre-assigned GENERATION variable.
    """

    def test_no_escaped_nested_python_c_in_commit_message(
        self, workflow_content: str
    ) -> None:
        r"""Workflow must NOT contain an escaped nested python -c in a commit message.

        The pattern:
          git commit -m "... $(python -c \"import json; print(json.load ..."
        uses nested escaped quotes that break the shell with:
          syntax error near unexpected token `json.load'
        This test ensures that anti-pattern is absent from the workflow.
        """
        # Detect the specific broken pattern: python -c with escaped nested quotes
        # inside a git commit -m substitution
        assert 'python -c \\"import json; print(json.load' not in workflow_content, (
            r"Found escaped nested python -c pattern "
            r"(python -c \"import json; print(json.load) "
            "in the workflow.  This causes a shell syntax error "
            "('syntax error near unexpected token `json.load\\'). "
            "Use a GENERATION variable instead: "
            "GENERATION=$(python -c 'import json; ...') and reference ${GENERATION}."
        )

    def test_commit_promoted_changes_uses_generation_variable(
        self, promote_section: str
    ) -> None:
        """'Commit promoted changes' step must assign GENERATION before using it.

        The GENERATION variable is set via:
          GENERATION=$(python -c 'import json; print(json.load(open("data/genome.json"))["generation"])')
        This avoids nested escaped quotes inside the git commit message.
        """
        assert 'GENERATION=$(python -c' in promote_section, (
            "The 'Commit promoted changes' step must assign the GENERATION variable "
            "via GENERATION=$(python -c '...') before using it in the commit message. "
            "Found no such assignment in the promote job section."
        )

    def test_commit_message_uses_generation_variable_reference(
        self, promote_section: str
    ) -> None:
        """git commit message in promote must reference ${GENERATION}, not inline python -c.

        The commit message must use the pre-assigned variable:
          git commit -m "chore(immunizer): promote generation ${GENERATION}"
        rather than a command substitution with python -c inside the message string.
        """
        assert '${GENERATION}' in promote_section, (
            "The git commit message in 'Commit promoted changes' must use "
            "'${GENERATION}' to reference the pre-assigned variable. "
            "Inline python -c command substitution inside the message causes "
            "shell syntax errors."
        )

    def test_promote_does_not_git_add_api_usage_ledger(
        self, promote_section: str
    ) -> None:
        """promote job must NOT git add data/api_usage_ledger.json.

        Ledger persistence is exclusively the responsibility of the
        persist-ledger job (Job 2).  If promote also adds the ledger file,
        API usage from rejected candidates (where promote does not run) is
        never persisted, making the budget cap fail-open.
        """
        assert "api_usage_ledger.json" not in promote_section, (
            "promote job must NOT 'git add data/api_usage_ledger.json'. "
            "The ledger is committed only by the persist-ledger job."
        )

    def test_bracket_notation_persist_ledger_result_still_present(
        self, workflow_content: str
    ) -> None:
        """needs['persist-ledger'].result (bracket notation) must still be present.

        The shell-quoting fix in 'Commit promoted changes' must not remove or
        break the bracket notation required for hyphenated job ID references
        in GitHub Actions expressions.
        """
        assert "needs['persist-ledger'].result" in workflow_content, (
            "needs['persist-ledger'].result was removed or broken. "
            "This bracket notation is required for correct GitHub Actions "
            "expression evaluation with the hyphenated 'persist-ledger' job ID."
        )

    def test_no_dot_notation_persist_ledger_result_after_fix(
        self, workflow_content: str
    ) -> None:
        """needs.persist-ledger.result (dot notation) must not appear after the fix.

        Dot notation for hyphenated job IDs is invalid inside ${{ }} expressions
        in GitHub Actions.  Only bracket notation is accepted.
        """
        assert "needs.persist-ledger.result" not in workflow_content, (
            "Found 'needs.persist-ledger.result' (dot notation) in the workflow. "
            "Use needs['persist-ledger'].result (bracket notation) instead."
        )


# ---------------------------------------------------------------------------
# 15. Critical #1: Project Owner promote_approved gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow_dispatch_inputs_section(workflow_content: str) -> str:
    """Extract the workflow_dispatch inputs section from the workflow."""
    match = re.search(
        r"workflow_dispatch:\s*\n\s*inputs:(.*?)(?=\n  schedule:|\Z)",
        workflow_content,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'workflow_dispatch: inputs:' section in workflow."
    )
    return match.group(1)


class TestPromoteApprovedInputExists:
    """Verify the promote_approved workflow_dispatch input is present and correct."""

    def test_promote_approved_input_exists(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """workflow_dispatch inputs must include promote_approved.

        Project Owner approval gate requires a promote_approved input so the
        promote job can be gated on explicit Project Owner selection.
        """
        assert "promote_approved" in workflow_dispatch_inputs_section, (
            "workflow_dispatch inputs must include 'promote_approved'. "
            "The promote job must require Project Owner explicit approval."
        )

    def test_promote_approved_default_is_false(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """promote_approved input must default to 'false'.

        Defaulting to 'false' ensures the promote job is never triggered
        accidentally without explicit Project Owner decision.
        """
        # Extract the promote_approved sub-section
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'promote_approved:' input block in workflow_dispatch inputs."
        )
        block = match.group(1)
        assert 'default: "false"' in block or "default: 'false'" in block, (
            "promote_approved input must have default: \"false\". "
            "Defaulting to 'true' would allow promote without Project Owner approval."
        )

    def test_promote_approved_default_is_not_true(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """promote_approved input must NOT default to 'true'.

        A default of 'true' would allow the promote job to run without explicit
        Project Owner approval on every workflow_dispatch run.
        """
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'promote_approved:' input block in workflow_dispatch inputs."
        )
        block = match.group(1)
        assert 'default: "true"' not in block and "default: 'true'" not in block, (
            "promote_approved input must NOT have default: \"true\". "
            "The default must be 'false' to require explicit Project Owner approval."
        )

    def test_promote_approved_options_include_false(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """promote_approved options must include 'false'."""
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'promote_approved:' input block in workflow_dispatch inputs."
        )
        block = match.group(1)
        assert '"false"' in block or "'false'" in block, (
            "promote_approved options must include 'false'."
        )

    def test_promote_approved_options_include_true(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """promote_approved options must include 'true'."""
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'promote_approved:' input block in workflow_dispatch inputs."
        )
        block = match.group(1)
        assert '"true"' in block or "'true'" in block, (
            "promote_approved options must include 'true'."
        )

    def test_promote_approved_options_are_exactly_false_and_true(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """promote_approved options must be exactly ["false", "true"] — no other values.

        Extra options (e.g. "maybe", "auto", "skip") would widen the gate beyond
        the two-value safe/unsafe boundary expected by the Project Owner approval design.
        This test parses the YAML options list under promote_approved and verifies
        only the two canonical values are present.
        """
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'promote_approved:' input block in workflow_dispatch inputs."
        )
        block = match.group(1)

        # Extract the options sub-block (lines after "options:")
        options_match = re.search(
            r"options:(.*?)(?=\n        [a-zA-Z]|\n      [a-zA-Z]|\Z)",
            block,
            re.DOTALL,
        )
        assert options_match is not None, (
            "promote_approved block must contain an 'options:' list."
        )
        options_block = options_match.group(1)

        # Collect all option values listed under options:
        # Each option line looks like:  - "false"  or  - "true"
        found_options = re.findall(r'-\s*["\'](\w+)["\']', options_block)

        assert set(found_options) == {"false", "true"}, (
            f"promote_approved options must be exactly ['false', 'true']. "
            f"Found: {found_options!r}. "
            "Extra or missing options would break the two-value Project Owner gate."
        )
        assert len(found_options) == 2, (
            f"promote_approved options must have exactly 2 entries ('false' and 'true'). "
            f"Found {len(found_options)}: {found_options!r}"
        )


class TestPromoteJobIfConditionHumanOwnerGate:
    """Verify the promote job if condition enforces Project Owner approval gate."""

    def test_promote_if_requires_workflow_dispatch(
        self, promote_section: str
    ) -> None:
        """promote job if condition must require github.event_name == 'workflow_dispatch'.

        This prevents schedule runs from ever triggering the promote job,
        even if all other conditions are met.
        """
        assert "github.event_name == 'workflow_dispatch'" in promote_section, (
            "promote job if condition must include "
            "github.event_name == 'workflow_dispatch'. "
            "This prevents schedule runs from promoting candidates."
        )

    def test_promote_if_requires_promote_approved_true(
        self, promote_section: str
    ) -> None:
        """promote job if condition must require promote_approved == 'true'.

        Without this gate, the promote job can run without Project Owner approval.
        """
        assert "github.event.inputs.promote_approved == 'true'" in promote_section, (
            "promote job if condition must include "
            "github.event.inputs.promote_approved == 'true'. "
            "Project Owner must explicitly set promote_approved=true to allow promotion."
        )

    def test_promote_if_still_requires_passed_adoption_gate(
        self, promote_section: str
    ) -> None:
        """promote job if condition must still require passed_adoption_gate == 'true'.

        The promote_approved gate is additive — it does not replace the existing
        adoption gate check.
        """
        assert "needs.evaluate.outputs.passed_adoption_gate == 'true'" in promote_section, (
            "promote job if condition must still include "
            "needs.evaluate.outputs.passed_adoption_gate == 'true'. "
            "The adoption gate must remain in addition to the Project Owner gate."
        )

    def test_promote_if_still_requires_propose_not_failed(
        self, promote_section: str
    ) -> None:
        """promote job if condition must still require propose_failed != 'true'."""
        assert "needs.propose.outputs.propose_failed != 'true'" in promote_section, (
            "promote job if condition must still include "
            "needs.propose.outputs.propose_failed != 'true'."
        )

    def test_promote_if_uses_bracket_notation_for_persist_ledger(
        self, promote_section: str
    ) -> None:
        """promote job if condition must use bracket notation for persist-ledger.

        needs['persist-ledger'].result is required; needs.persist-ledger.result
        is invalid GitHub Actions syntax for hyphenated job IDs.
        """
        assert "needs['persist-ledger'].result" in promote_section, (
            "promote job if condition must use needs['persist-ledger'].result "
            "(bracket notation) for the hyphenated 'persist-ledger' job ID."
        )

    def test_promote_if_allows_persist_ledger_success_or_skipped(
        self, promote_section: str
    ) -> None:
        """promote if condition must allow persist-ledger result of success or skipped."""
        assert (
            "needs['persist-ledger'].result == 'success'" in promote_section
            or "needs['persist-ledger'].result == 'skipped'" in promote_section
        ), (
            "promote job if condition must allow persist-ledger result of "
            "'success' or 'skipped'."
        )

    def test_no_dot_notation_persist_ledger_in_promote(
        self, promote_section: str
    ) -> None:
        """promote job must NOT reference persist-ledger via dot notation.

        needs.persist-ledger.result is invalid inside ${{ }} GitHub Actions expressions.
        """
        assert "needs.persist-ledger.result" not in promote_section, (
            "Found needs.persist-ledger.result (dot notation) in promote job. "
            "Use needs['persist-ledger'].result (bracket notation) instead."
        )


class TestScheduleCannotPromote:
    """Verify that schedule runs cannot trigger the promote job."""

    def test_promote_requires_workflow_dispatch_blocking_schedule(
        self, promote_section: str
    ) -> None:
        """promote job requires github.event_name == 'workflow_dispatch', blocking schedule.

        Schedule runs set github.event_name to 'schedule', which does not match
        'workflow_dispatch', so the promote job is skipped on all scheduled runs.
        """
        assert "github.event_name == 'workflow_dispatch'" in promote_section, (
            "promote job must require github.event_name == 'workflow_dispatch' "
            "to ensure scheduled runs can never promote candidates."
        )

    def test_schedule_comment_indicates_noop(self, workflow_content: str) -> None:
        """Schedule comment must indicate schedule runs are noop.

        This verifies the existing noop-on-schedule design is preserved and not
        broken by the promote_approved gate changes.
        """
        assert "schedule" in workflow_content and "noop" in workflow_content, (
            "Workflow must document that scheduled runs default to noop mode."
        )


class TestOfflineSampleAloneCannotPromote:
    """Verify offline-sample success alone is insufficient to trigger promote."""

    def test_promote_approved_false_blocks_promote_even_if_gate_passed(
        self, promote_section: str
    ) -> None:
        """promote job must check promote_approved == 'true', so promote_approved=false blocks.

        Even if evaluate.outputs.passed_adoption_gate == 'true' (offline-sample succeeded),
        the promote job is skipped when promote_approved=false (the default).
        This test verifies the condition exists; the logic guarantees the skip.
        """
        assert "github.event.inputs.promote_approved == 'true'" in promote_section, (
            "promote job must check promote_approved == 'true'. "
            "offline-sample success alone (adoption gate passed) must not trigger promote. "
            "Project Owner must explicitly set promote_approved=true."
        )


class TestPromoteJobSecretBoundary:
    """Verify promote job does not receive disallowed secrets or files."""

    def test_promote_job_has_no_gemini_api_key(self, promote_section: str) -> None:
        """promote job must NOT pass GEMINI_API_KEY.

        Write permissions and model API secrets must never appear in the same job.
        """
        assert "secrets.GEMINI_API_KEY" not in promote_section, (
            "promote job must NOT pass secrets.GEMINI_API_KEY. "
            "Write permissions and model API secrets must be in separate jobs."
        )

    def test_promote_job_does_not_git_add_api_usage_ledger(
        self, promote_section: str
    ) -> None:
        """promote job must NOT git add data/api_usage_ledger.json.

        Ledger persistence is the responsibility of the persist-ledger job only.
        """
        assert "api_usage_ledger.json" not in promote_section, (
            "promote job must NOT git add data/api_usage_ledger.json. "
            "Ledger is committed exclusively by the persist-ledger job."
        )


class TestNormalCINotAffected:
    """Verify normal CI workflow is not affected by the promote_approved gate changes."""

    def test_ci_workflow_exists(self) -> None:
        """The ci.yml workflow file must still exist."""
        ci_path = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), (
            "The ci.yml workflow file must exist. "
            "Normal CI must not be affected by the promote_approved gate changes."
        )

    def test_ci_workflow_does_not_have_promote_approved(self) -> None:
        """The ci.yml workflow must NOT have promote_approved input.

        The promote_approved gate is specific to the immunization_loop.yml workflow.
        Normal CI must not be changed by this implementation.
        """
        ci_path = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if ci_path.exists():
            ci_content = ci_path.read_text(encoding="utf-8")
            assert "promote_approved" not in ci_content, (
                "ci.yml must NOT contain 'promote_approved'. "
                "Normal CI workflow must not be affected by the Project Owner gate changes."
            )

    def test_ci_workflow_does_not_have_contents_write(self) -> None:
        """ci.yml must NOT gain contents: write permission."""
        ci_path = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if ci_path.exists():
            ci_content = ci_path.read_text(encoding="utf-8")
            assert "contents: write" not in ci_content, (
                "ci.yml must NOT have 'contents: write'. "
                "Normal CI must remain read-only."
            )


class TestRegressionGuardPromoteApproved:
    """Regression guards: ensure forbidden patterns are absent after the change."""

    def test_promote_approved_default_not_true_regression(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """Regression guard: promote_approved must never default to true."""
        # Extract promote_approved block
        match = re.search(
            r"promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            workflow_dispatch_inputs_section,
            re.DOTALL,
        )
        if match:
            block = match.group(1)
            assert 'default: "true"' not in block, (
                "REGRESSION: promote_approved default must not be 'true'."
            )
            assert "default: 'true'" not in block, (
                "REGRESSION: promote_approved default must not be 'true'."
            )

    def test_promote_approved_input_present_regression(
        self, workflow_content: str
    ) -> None:
        """Regression guard: promote_approved input must exist."""
        assert "promote_approved" in workflow_content, (
            "REGRESSION: promote_approved input is missing from workflow. "
            "This gate is required to prevent unauthorized promotion."
        )

    def test_promote_job_checks_promote_approved_regression(
        self, promote_section: str
    ) -> None:
        """Regression guard: promote job must reference promote_approved."""
        assert "promote_approved" in promote_section, (
            "REGRESSION: promote job does not reference promote_approved. "
            "Project Owner gate is not enforced."
        )

    def test_promote_job_checks_workflow_dispatch_regression(
        self, promote_section: str
    ) -> None:
        """Regression guard: promote job must require workflow_dispatch."""
        assert "workflow_dispatch" in promote_section, (
            "REGRESSION: promote job does not require workflow_dispatch. "
            "Schedule runs may be able to trigger promote."
        )

    def test_schedule_cannot_promote_regression(self, promote_section: str) -> None:
        """Regression guard: schedule must not be able to trigger promote."""
        # The promote job must have github.event_name == 'workflow_dispatch'
        # which prevents schedule (event_name == 'schedule') from promoting.
        assert "github.event_name == 'workflow_dispatch'" in promote_section, (
            "REGRESSION: promote job does not block schedule runs. "
            "Schedule must never be able to trigger promote."
        )

    def test_promote_job_no_gemini_api_key_regression(
        self, promote_section: str
    ) -> None:
        """Regression guard: promote job must not receive GEMINI_API_KEY."""
        assert "secrets.GEMINI_API_KEY" not in promote_section, (
            "REGRESSION: promote job now passes GEMINI_API_KEY. "
            "Write permissions and model API secrets must remain separated."
        )

    def test_promote_job_no_api_usage_ledger_regression(
        self, promote_section: str
    ) -> None:
        """Regression guard: promote job must not handle api_usage_ledger.json."""
        assert "api_usage_ledger.json" not in promote_section, (
            "REGRESSION: promote job now references api_usage_ledger.json. "
            "Ledger must be handled exclusively by persist-ledger job."
        )

    def test_no_dot_notation_persist_ledger_regression(
        self, workflow_content: str
    ) -> None:
        """Regression guard: needs.persist-ledger.result dot notation must not appear."""
        assert "needs.persist-ledger.result" not in workflow_content, (
            "REGRESSION: needs.persist-ledger.result (dot notation) found in workflow. "
            "Use needs['persist-ledger'].result (bracket notation) instead."
        )


# ---------------------------------------------------------------------------
# 16. PR-D: Step-level secret scoping — mode-specific propose steps
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def propose_noop_step(propose_section: str) -> str:
    """Extract the 'Propose mutation patch — noop' step block."""
    match = re.search(
        r"- name: Propose mutation patch — noop\b(.*?)(?=\n      - name:|\Z)",
        propose_section,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'Propose mutation patch — noop' step in the propose job. "
        "PR-D requires a dedicated noop step with no GEMINI_API_KEY."
    )
    return match.group(0)


@pytest.fixture(scope="module")
def propose_offline_sample_step(propose_section: str) -> str:
    """Extract the 'Propose mutation patch — offline-sample' step block."""
    match = re.search(
        r"- name: Propose mutation patch — offline-sample\b(.*?)(?=\n      - name:|\Z)",
        propose_section,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'Propose mutation patch — offline-sample' step. "
        "PR-D requires a dedicated offline-sample step with no GEMINI_API_KEY."
    )
    return match.group(0)


@pytest.fixture(scope="module")
def propose_preflight_step(propose_section: str) -> str:
    """Extract the 'Propose mutation patch — gemini-paid-credit-preflight' step."""
    match = re.search(
        r"- name: Propose mutation patch — gemini-paid-credit-preflight\b(.*?)(?=\n      - name:|\Z)",
        propose_section,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'Propose mutation patch — gemini-paid-credit-preflight' step. "
        "PR-D requires a dedicated preflight step with GEMINI_API_KEY_PRESENT signal."
    )
    return match.group(0)




@pytest.fixture(scope="module")
def propose_paid_credit_step(propose_section: str) -> str:
    """Extract the 'Propose mutation patch — gemini-paid-credit' step block.

    Uses a negative-lookahead to exclude the preflight variant so that
    're.search' does not match 'gemini-paid-credit-preflight'.
    """
    match = re.search(
        r"- name: Propose mutation patch — gemini-paid-credit\n(.*?)(?=\n      - name:|\Z)",
        propose_section,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'Propose mutation patch — gemini-paid-credit' step "
        "(distinct from the preflight variant). "
        "PR-D requires a dedicated gemini-paid-credit step with GEMINI_API_KEY."
    )
    return match.group(0)


@pytest.fixture(scope="module")
def propose_aggregate_step(propose_section: str) -> str:
    """Extract the 'Aggregate propose outputs' step block."""
    match = re.search(
        r"- name: Aggregate propose outputs\b(.*?)(?=\n      - name:|\Z)",
        propose_section,
        re.DOTALL,
    )
    assert match is not None, (
        "Could not find 'Aggregate propose outputs' step in the propose job. "
        "PR-D requires an aggregate step (id: propose) that reads the exit code "
        "written by the mode-specific steps and emits all four job outputs."
    )
    return match.group(0)


class TestPhase3LiveModelGate:
    """Phase 3: live-model is blocked at both workflow and script levels."""

    def test_dispatch_options_do_not_include_live_model(
        self, workflow_dispatch_inputs_section: str
    ) -> None:
        """workflow_dispatch mode options must NOT include live-model.

        Phase 3 removes live-model from the allowed dispatch modes. Only
        gemini-paid-credit enforces budget caps and ledger tracking.
        """
        assert "live-model" not in workflow_dispatch_inputs_section, (
            "Phase 3: live-model must not be a workflow_dispatch mode option. "
            "Use gemini-paid-credit for live API calls."
        )

    def test_live_model_step_absent_from_workflow(self, propose_section: str) -> None:
        """Phase 3: 'Propose mutation patch — live-model' step must NOT exist in the workflow."""
        assert "Propose mutation patch — live-model" not in propose_section, (
            "Phase 3: live-model step must be removed from the workflow propose section."
        )

    def test_gemini_paid_credit_still_present(self, propose_section: str) -> None:
        """gemini-paid-credit step must still exist after live-model removal."""
        assert "Propose mutation patch — gemini-paid-credit" in propose_section, (
            "gemini-paid-credit step must remain present as the only live API path."
        )

    def test_gemini_paid_credit_preflight_still_present(
        self, propose_section: str
    ) -> None:
        """gemini-paid-credit-preflight step must still exist after live-model removal."""
        assert "Propose mutation patch — gemini-paid-credit-preflight" in propose_section, (
            "gemini-paid-credit-preflight step must remain present."
        )


class TestModeSpecificStepsExist:
    """Verify four mode-specific propose steps are present in the workflow.

    Phase 3: live-model step is removed. Only noop, offline-sample,
    gemini-paid-credit-preflight, and gemini-paid-credit are present.
    """

    def test_noop_step_exists(self, propose_noop_step: str) -> None:
        """'Propose mutation patch — noop' step must exist."""
        assert "Propose mutation patch — noop" in propose_noop_step

    def test_offline_sample_step_exists(self, propose_offline_sample_step: str) -> None:
        """'Propose mutation patch — offline-sample' step must exist."""
        assert "Propose mutation patch — offline-sample" in propose_offline_sample_step

    def test_preflight_step_exists(self, propose_preflight_step: str) -> None:
        """'Propose mutation patch — gemini-paid-credit-preflight' step must exist."""
        assert "gemini-paid-credit-preflight" in propose_preflight_step

    def test_live_model_step_absent(self, propose_section: str) -> None:
        """Phase 3: 'Propose mutation patch — live-model' step must NOT exist.

        The legacy live-model path is blocked for Phase 3. Only gemini-paid-credit
        is allowed as the live API path because it enforces budget and ledger tracking.
        """
        assert "Propose mutation patch — live-model" not in propose_section, (
            "Phase 3: live-model step must be removed from the workflow. "
            "Use gemini-paid-credit for live API calls."
        )

    def test_paid_credit_step_exists(self, propose_paid_credit_step: str) -> None:
        """'Propose mutation patch — gemini-paid-credit' step must exist."""
        assert "gemini-paid-credit" in propose_paid_credit_step

    def test_aggregate_step_exists(self, propose_aggregate_step: str) -> None:
        """'Aggregate propose outputs' step must exist."""
        assert "Aggregate propose outputs" in propose_aggregate_step


class TestNonApiModeStepsHaveNoRawApiKey:
    """Verify noop and offline-sample steps do NOT receive GEMINI_API_KEY (minimum privilege).

    These modes are pure local execution — no API calls are made and no
    secret is needed.  Injecting GEMINI_API_KEY into these steps would
    violate the minimum-privilege principle without any functional benefit.
    """

    def test_noop_step_has_no_gemini_api_key(self, propose_noop_step: str) -> None:
        """noop step must NOT inject secrets.GEMINI_API_KEY.

        The noop mode runs propose_mutation.py --noop which never calls any
        external API.  Injecting the API key widens the secret's exposure
        surface for no benefit.
        """
        assert "secrets.GEMINI_API_KEY" not in propose_noop_step, (
            "noop step must NOT pass secrets.GEMINI_API_KEY. "
            "noop mode makes no API calls; injecting the key is a minimum-privilege violation."
        )

    def test_offline_sample_step_has_no_gemini_api_key(
        self, propose_offline_sample_step: str
    ) -> None:
        """offline-sample step must NOT inject secrets.GEMINI_API_KEY.

        offline-sample mode uses a bundled sample — no API call is made.
        """
        assert "secrets.GEMINI_API_KEY" not in propose_offline_sample_step, (
            "offline-sample step must NOT pass secrets.GEMINI_API_KEY. "
            "offline-sample makes no API calls; injecting the key is a minimum-privilege violation."
        )

    def test_noop_step_also_has_no_gemini_api_key_present(
        self, propose_noop_step: str
    ) -> None:
        """noop step must NOT inject GEMINI_API_KEY_PRESENT either.

        GEMINI_API_KEY_PRESENT is only needed by the preflight step to signal
        that the key is configured.  noop mode does not need any API key signal.
        """
        assert "GEMINI_API_KEY_PRESENT" not in propose_noop_step, (
            "noop step must NOT pass GEMINI_API_KEY_PRESENT. "
            "noop mode has no use for any API key signal."
        )

    def test_offline_sample_step_also_has_no_gemini_api_key_present(
        self, propose_offline_sample_step: str
    ) -> None:
        """offline-sample step must NOT inject GEMINI_API_KEY_PRESENT either."""
        assert "GEMINI_API_KEY_PRESENT" not in propose_offline_sample_step, (
            "offline-sample step must NOT pass GEMINI_API_KEY_PRESENT. "
            "offline-sample mode has no use for any API key signal."
        )


class TestPreflightStepUsesBooleanSignal:
    """Verify the preflight step uses GEMINI_API_KEY_PRESENT boolean, NOT raw key.

    The preflight step verifies readiness without calling the Gemini API.
    It only needs to know WHETHER the key is configured, not its value.
    Passing GEMINI_API_KEY_PRESENT=true/false keeps the raw secret out of
    this step while still allowing run_gemini_paid_credit_preflight() to
    check key presence.
    """

    def test_preflight_step_has_no_raw_gemini_api_key(
        self, propose_preflight_step: str
    ) -> None:
        """Preflight step must NOT assign secrets.GEMINI_API_KEY as a raw env var.

        The raw key value must be withheld from the preflight step because
        preflight never calls the Gemini API.  The YAML expression
        `secrets.GEMINI_API_KEY != '' && 'true' || 'false'` is permitted — it
        uses the secret only in a boolean comparison, never passing the raw value
        as an environment variable.  Only the direct assignment pattern
        `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}` is forbidden.
        """
        # The forbidden pattern is a direct assignment of the raw key value.
        # The permitted pattern is a boolean expression that compares the key.
        assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" not in propose_preflight_step, (
            "Preflight step must NOT assign 'GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}'. "
            "Preflight never calls the Gemini API; only the boolean existence "
            "signal GEMINI_API_KEY_PRESENT is needed."
        )

    def test_preflight_step_has_gemini_api_key_present_signal(
        self, propose_preflight_step: str
    ) -> None:
        """Preflight step must inject GEMINI_API_KEY_PRESENT as a boolean signal.

        run_gemini_paid_credit_preflight() checks GEMINI_API_KEY_PRESENT to
        determine whether the API key is configured, without receiving its value.
        """
        assert "GEMINI_API_KEY_PRESENT" in propose_preflight_step, (
            "Preflight step must pass GEMINI_API_KEY_PRESENT boolean signal. "
            "run_gemini_paid_credit_preflight() uses this to confirm key presence "
            "without receiving the raw secret value."
        )

    def test_preflight_step_gemini_api_key_present_is_boolean_expression(
        self, propose_preflight_step: str
    ) -> None:
        """GEMINI_API_KEY_PRESENT must be set via a GitHub expression that yields 'true'/'false'.

        The pattern `secrets.GEMINI_API_KEY != '' && 'true' || 'false'` evaluates
        to the string 'true' when the secret is set, 'false' when it is not —
        without exposing the actual key value.
        """
        # Check for the key presence check expression pattern
        assert (
            "secrets.GEMINI_API_KEY != ''" in propose_preflight_step
            or "secrets.GEMINI_API_KEY != \"\"" in propose_preflight_step
        ), (
            "GEMINI_API_KEY_PRESENT must be set using a GitHub expression that checks "
            "secrets.GEMINI_API_KEY != '' to produce a 'true'/'false' boolean signal, "
            "rather than passing the raw key value."
        )


class TestApiModeStepsHaveRawApiKey:
    """Verify gemini-paid-credit step receives GEMINI_API_KEY.

    Phase 3: live-model step is removed. Only gemini-paid-credit calls the Gemini API.
    """

    def test_paid_credit_step_has_gemini_api_key(
        self, propose_paid_credit_step: str
    ) -> None:
        """gemini-paid-credit step must inject secrets.GEMINI_API_KEY.

        gemini-paid-credit mode calls _propose_via_gemini_paid_credit which
        requires the API key.
        """
        assert "secrets.GEMINI_API_KEY" in propose_paid_credit_step, (
            "gemini-paid-credit step must pass secrets.GEMINI_API_KEY. "
            "The Gemini API call requires the raw key to be present."
        )


class TestModeStepsHaveCorrectIfConditions:
    """Verify each mode step has the correct if: condition to restrict execution.

    Without if: conditions, all mode steps would run for every mode, resulting
    in multiple propose attempts per job run.
    """

    def test_noop_step_if_condition(self, propose_noop_step: str) -> None:
        """noop step must only run when effective_mode == 'noop'."""
        assert "effective_mode == 'noop'" in propose_noop_step or \
               'effective_mode == "noop"' in propose_noop_step, (
            "noop step must have if: condition checking effective_mode == 'noop'."
        )

    def test_offline_sample_step_if_condition(
        self, propose_offline_sample_step: str
    ) -> None:
        """offline-sample step must only run when effective_mode == 'offline-sample'."""
        assert "effective_mode == 'offline-sample'" in propose_offline_sample_step or \
               'effective_mode == "offline-sample"' in propose_offline_sample_step, (
            "offline-sample step must have if: condition for effective_mode == 'offline-sample'."
        )

    def test_preflight_step_if_condition(self, propose_preflight_step: str) -> None:
        """preflight step must only run when effective_mode == 'gemini-paid-credit-preflight'."""
        assert (
            "effective_mode == 'gemini-paid-credit-preflight'" in propose_preflight_step
            or 'effective_mode == "gemini-paid-credit-preflight"' in propose_preflight_step
        ), (
            "preflight step must have if: condition for "
            "effective_mode == 'gemini-paid-credit-preflight'."
        )

    def test_paid_credit_step_if_condition(self, propose_paid_credit_step: str) -> None:
        """gemini-paid-credit step must only run when mode == 'gemini-paid-credit'."""
        assert (
            "effective_mode == 'gemini-paid-credit'" in propose_paid_credit_step
            or 'effective_mode == "gemini-paid-credit"' in propose_paid_credit_step
        ), (
            "gemini-paid-credit step must have if: condition for "
            "effective_mode == 'gemini-paid-credit'."
        )


class TestAggregateStepStructure:
    """Verify the Aggregate propose outputs step (id: propose) has the correct structure.

    The aggregate step reads the exit code written by the mode step and emits
    all four job outputs (patch_exists, ledger_changed, propose_exit_code,
    propose_failed) unconditionally.
    """

    def test_aggregate_step_has_id_propose(self, propose_aggregate_step: str) -> None:
        """Aggregate step must have id: propose.

        Downstream steps reference the propose step outputs via
        steps.propose.outputs.*, which requires id: propose on this step.
        """
        assert "id: propose" in propose_aggregate_step, (
            "Aggregate step must have 'id: propose' so downstream steps can "
            "reference steps.propose.outputs.patch_exists, ledger_changed, etc."
        )

    def test_aggregate_step_reads_exit_code_from_file(
        self, propose_aggregate_step: str
    ) -> None:
        """Aggregate step must read propose_exit_code from the file written by mode steps."""
        assert "propose_exit_code" in propose_aggregate_step, (
            "Aggregate step must read .cyber_immunizer/propose_exit_code "
            "written by the mode-specific step."
        )

    def test_aggregate_step_has_fallback_for_missing_exit_code_file(
        self, propose_aggregate_step: str
    ) -> None:
        """Aggregate step must have a fallback default when the exit code file is absent."""
        # The fallback should set PROPOSE_EXIT=1 if the file doesn't exist
        assert "PROPOSE_EXIT=1" in propose_aggregate_step, (
            "Aggregate step must fall back to PROPOSE_EXIT=1 when the exit code "
            "file is absent (unexpected — no mode step ran)."
        )

    def test_aggregate_step_sets_all_four_outputs(
        self, propose_aggregate_step: str
    ) -> None:
        """Aggregate step must set all four job outputs."""
        for output_name in ("patch_exists", "ledger_changed", "propose_exit_code", "propose_failed"):
            assert output_name in propose_aggregate_step, (
                f"Aggregate step must set '{output_name}' in GITHUB_OUTPUT."
            )

    def test_aggregate_step_has_no_gemini_api_key(
        self, propose_aggregate_step: str
    ) -> None:
        """Aggregate step must NOT inject GEMINI_API_KEY.

        The aggregate step only reads the exit code and computes outputs —
        it never calls any API.  Injecting a key here would violate minimum-privilege.
        """
        assert "secrets.GEMINI_API_KEY" not in propose_aggregate_step, (
            "Aggregate step must NOT pass secrets.GEMINI_API_KEY. "
            "This step only reads exit code and computes outputs."
        )


class TestModeStepsWriteExitCodeToFile:
    """Verify each mode step writes its exit code to .cyber_immunizer/propose_exit_code."""

    def test_noop_step_writes_exit_code(self, propose_noop_step: str) -> None:
        """noop step must write PROPOSE_EXIT to .cyber_immunizer/propose_exit_code."""
        assert "propose_exit_code" in propose_noop_step, (
            "noop step must write its exit code to .cyber_immunizer/propose_exit_code "
            "so the Aggregate step can read it."
        )

    def test_offline_sample_step_writes_exit_code(
        self, propose_offline_sample_step: str
    ) -> None:
        """offline-sample step must write PROPOSE_EXIT to propose_exit_code file."""
        assert "propose_exit_code" in propose_offline_sample_step, (
            "offline-sample step must write its exit code to the propose_exit_code file."
        )

    def test_preflight_step_writes_exit_code(self, propose_preflight_step: str) -> None:
        """preflight step must write PROPOSE_EXIT to propose_exit_code file."""
        assert "propose_exit_code" in propose_preflight_step, (
            "preflight step must write its exit code to the propose_exit_code file."
        )

    def test_paid_credit_step_writes_exit_code(self, propose_paid_credit_step: str) -> None:
        """gemini-paid-credit step must write PROPOSE_EXIT to propose_exit_code file."""
        assert "propose_exit_code" in propose_paid_credit_step, (
            "gemini-paid-credit step must write its exit code to the propose_exit_code file."
        )


class TestModeStepsUseSetPlusE:
    """Verify all mode-specific steps use set +e to capture exit codes without aborting."""

    def test_noop_step_uses_set_plus_e(self, propose_noop_step: str) -> None:
        """noop step must use set +e."""
        assert "set +e" in propose_noop_step

    def test_offline_sample_step_uses_set_plus_e(
        self, propose_offline_sample_step: str
    ) -> None:
        """offline-sample step must use set +e."""
        assert "set +e" in propose_offline_sample_step

    def test_preflight_step_uses_set_plus_e(self, propose_preflight_step: str) -> None:
        """preflight step must use set +e."""
        assert "set +e" in propose_preflight_step

    def test_paid_credit_step_uses_set_plus_e(self, propose_paid_credit_step: str) -> None:
        """gemini-paid-credit step must use set +e."""
        assert "set +e" in propose_paid_credit_step


class TestStepLevelSecretScopingRegressionGuards:
    """Regression guards ensuring PR-D minimum-privilege invariants remain intact."""

    def test_no_job_level_gemini_api_key_env_block(
        self, propose_section: str
    ) -> None:
        """The propose job must NOT have a job-level env block with GEMINI_API_KEY.

        After PR-D, GEMINI_API_KEY is injected at step level only (live-model
        and gemini-paid-credit steps).  A job-level env block would reintroduce
        the minimum-privilege violation that PR-D fixes.
        """
        # A job-level env: block would appear BEFORE the first step (i.e., before
        # 'steps:').  We check that GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        # does not appear in the job preamble (before 'steps:').
        steps_pos = propose_section.find("    steps:")
        if steps_pos == -1:
            steps_pos = propose_section.find("steps:")
        preamble = propose_section[:steps_pos] if steps_pos != -1 else ""
        assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" not in preamble, (
            "GEMINI_API_KEY must NOT appear in a job-level env: block in the propose job. "
            "PR-D requires step-level scoping only."
        )

    def test_gemini_api_key_absent_from_non_api_steps_in_propose(
        self, propose_noop_step: str, propose_offline_sample_step: str
    ) -> None:
        """noop and offline-sample steps must not have secrets.GEMINI_API_KEY.

        Regression guard: verifies PR-D minimum-privilege is not reverted.
        """
        assert "secrets.GEMINI_API_KEY" not in propose_noop_step, (
            "REGRESSION: secrets.GEMINI_API_KEY appeared in noop step."
        )
        assert "secrets.GEMINI_API_KEY" not in propose_offline_sample_step, (
            "REGRESSION: secrets.GEMINI_API_KEY appeared in offline-sample step."
        )

    def test_gemini_api_key_present_only_in_api_steps(
        self, propose_paid_credit_step: str
    ) -> None:
        """gemini-paid-credit step must retain secrets.GEMINI_API_KEY.

        Regression guard: verifies the paid-credit step was not accidentally
        stripped of the key it needs. Phase 3: live-model step is removed.
        """
        assert "secrets.GEMINI_API_KEY" in propose_paid_credit_step, (
            "REGRESSION: secrets.GEMINI_API_KEY was removed from gemini-paid-credit step."
        )


# ---------------------------------------------------------------------------
# 17. Failure diagnostics: apply-report artifact and --report flags
# ---------------------------------------------------------------------------


class TestApplyReportArtifact:
    """Verify apply-report artifact upload is present and uses if: always()."""

    def test_apply_report_artifact_upload_exists(
        self, evaluate_section: str
    ) -> None:
        """evaluate job must have an 'Upload apply report artifact' step."""
        assert "apply-report" in evaluate_section, (
            "evaluate job must upload an 'apply-report' artifact so diagnostic "
            "information is preserved even when apply_mutation.py fails."
        )

    def test_apply_report_upload_uses_always(
        self, evaluate_section: str
    ) -> None:
        """apply-report artifact upload must use if: always() or equivalent.

        Without always(), the upload is skipped when apply_mutation.py exits
        non-zero, defeating the purpose of writing the report.
        """
        # Find the apply-report upload step block
        import re as _re
        match = _re.search(
            r"name:.*[Uu]pload apply report.*?(?=\n      - name:|\Z)",
            evaluate_section,
            _re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'Upload apply report' step in evaluate job. "
            "This step is required to persist diagnostics when apply fails."
        )
        upload_block = match.group(0)
        assert "always()" in upload_block, (
            "'Upload apply report artifact' step must include if: always() "
            "so it runs even when the apply step exits non-zero."
        )

    def test_apply_step_uses_report_flag(
        self, evaluate_section: str
    ) -> None:
        """apply_mutation.py call in workflow must include --report flag."""
        assert "--report" in evaluate_section, (
            "scripts/apply_mutation.py must be invoked with --report in the evaluate job "
            "so it writes a diagnostic JSON before exiting on failure."
        )

    def test_apply_report_path_is_cyber_immunizer(
        self, evaluate_section: str
    ) -> None:
        """apply_mutation.py --report path must be under .cyber_immunizer/."""
        assert "apply_report.json" in evaluate_section, (
            "The --report path for apply_mutation.py must reference apply_report.json "
            "so the artifact upload step can find the file."
        )


class TestEvaluateReportFlag:
    """Verify evaluate_candidate.py is invoked with --report flag."""

    def test_evaluate_step_uses_report_flag(
        self, evaluate_section: str
    ) -> None:
        """evaluate_candidate.py must be called with --report in the workflow.

        Explicit --report flag makes the output path unambiguous and allows
        the artifact upload step to reliably find the file.
        """
        assert "fitness_report.json" in evaluate_section, (
            "evaluate job must pass fitness_report.json as the --report path (or "
            "use it as the default path) so artifacts can be uploaded reliably."
        )


class TestEvaluateSkipsWhenApplyFails:
    """Verify evaluate step is gated on apply step success."""

    def test_evaluate_step_has_apply_success_condition(
        self, evaluate_section: str
    ) -> None:
        """The evaluate step must have a condition that prevents it running when apply fails.

        This can be expressed as 'if: steps.apply.outcome == success' or similar.
        Without this gate, a failed apply (partial candidate file) could trigger
        an evaluation of an invalid or missing candidate.
        """
        import re as _re
        # Look for an if: condition on the evaluate step that references apply outcome
        has_apply_gate = (
            "steps.apply.outcome" in evaluate_section
            or "steps.apply.conclusion" in evaluate_section
        )
        assert has_apply_gate, (
            "The evaluate step must be gated on the apply step outcome "
            "(e.g., if: steps.apply.outcome == 'success') so it is skipped "
            "when apply_mutation.py exits non-zero."
        )


class TestArtifactUploadIfNoFilesFound:
    """Verify artifact uploads handle missing files gracefully."""

    def test_candidate_detector_upload_handles_missing(
        self, evaluate_section: str
    ) -> None:
        """candidate-detector upload must not fail fatally when file doesn't exist.

        When apply fails, candidate_detector.py is not written.  The upload
        step should use if-no-files-found: warn or ignore so it does not break CI.
        """
        # Check for if-no-files-found in the candidate-detector upload block
        import re as _re
        match = _re.search(
            r"name:.*[Uu]pload candidate detector.*?(?=\n      - name:|\Z)",
            evaluate_section,
            _re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'Upload candidate detector artifact' step."
        )
        upload_block = match.group(0)
        assert "if-no-files-found" in upload_block, (
            "candidate-detector upload must use if-no-files-found: warn (or ignore) "
            "so it does not fatally fail when apply_mutation.py did not produce "
            "the candidate file."
        )

    def test_fitness_report_upload_handles_missing(
        self, evaluate_section: str
    ) -> None:
        """fitness-report upload must not fail fatally when file doesn't exist.

        When apply fails, evaluate_candidate.py does not run and fitness_report.json
        is not written.  The upload step must handle the missing file gracefully.
        """
        import re as _re
        match = _re.search(
            r"name:.*[Uu]pload fitness report.*?(?=\n      - name:|\Z)",
            evaluate_section,
            _re.DOTALL,
        )
        assert match is not None, (
            "Could not find 'Upload fitness report artifact' step."
        )
        upload_block = match.group(0)
        assert "if-no-files-found" in upload_block, (
            "fitness-report upload must use if-no-files-found: warn (or ignore) "
            "so it does not fatally fail when evaluate_candidate.py did not run."
        )


class TestPromotionConditionsNotRelaxed:
    """Regression guards: promotion gate conditions must not be relaxed."""

    def test_promote_still_requires_passed_adoption_gate(
        self, promote_section: str
    ) -> None:
        """Failure diagnostics must not relax the adoption gate requirement."""
        assert "needs.evaluate.outputs.passed_adoption_gate == 'true'" in promote_section, (
            "REGRESSION: passed_adoption_gate check removed from promote if condition. "
            "The adoption gate must remain enforced."
        )

    def test_promote_still_requires_promote_approved(
        self, promote_section: str
    ) -> None:
        """Failure diagnostics must not relax the promote_approved requirement."""
        assert "github.event.inputs.promote_approved == 'true'" in promote_section, (
            "REGRESSION: promote_approved check removed from promote if condition. "
            "The Project Owner gate must remain enforced."
        )

    def test_promote_still_requires_workflow_dispatch(
        self, promote_section: str
    ) -> None:
        """Failure diagnostics must not allow schedule runs to trigger promote."""
        assert "github.event_name == 'workflow_dispatch'" in promote_section, (
            "REGRESSION: workflow_dispatch check removed from promote if condition. "
            "Schedule runs must never be able to trigger promotion."
        )
