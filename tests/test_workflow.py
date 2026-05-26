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
