"""tests/test_repo_invariants.py — Repo-level safety invariant tests (backlog #13).

These tests pin the repository's safety invariants so that dangerous drift is
caught by CI before Phase 3 begins.  They are intentionally stable and
deterministic: no network calls, no live model, no side effects.

Invariant groups:
  1. Phase 3 not-started invariants (docs)
  2. genome.json safety invariants
  3. Workflow permission invariants (immunization_loop.yml)
  4. Step-level secret scoping invariants
  5. Promote gate invariants
  6. Generated-code / write-permission separation invariants
  7. Repository secret leakage invariants (raw key patterns)

Implementation notes:
  - Python standard library only (json, re, subprocess, pathlib).
    No PyYAML or other third-party YAML parser is used.
  - json is used for genome.json.
  - All workflow checks use string / regex inspection so no YAML parser
    dependency is required.  The workflow file is well-structured enough
    that targeted text extraction is both simpler and more stable.
  - GitHub Actions expression syntax is NOT semantically evaluated; only
    string-structural invariants are asserted.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
_DOCS = _ROOT / "docs"
_DATA = _ROOT / "data"
_WORKFLOWS = _ROOT / ".github" / "workflows"

_CHECKPOINT_PATH = _DOCS / "PHASE_2_COMPLETION_CHECKPOINT.md"
_CHECKLIST_PATH = _DOCS / "API_ACTIVATION_CHECKLIST.md"
_GENOME_PATH = _DATA / "genome.json"
_LOOP_WORKFLOW_PATH = _WORKFLOWS / "immunization_loop.yml"
_CI_WORKFLOW_PATH = _WORKFLOWS / "ci.yml"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def checkpoint_text() -> str:
    assert _CHECKPOINT_PATH.exists(), f"Missing: {_CHECKPOINT_PATH}"
    return _CHECKPOINT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def checklist_text() -> str:
    assert _CHECKLIST_PATH.exists(), f"Missing: {_CHECKLIST_PATH}"
    return _CHECKLIST_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def genome() -> dict:
    assert _GENOME_PATH.exists(), f"Missing: {_GENOME_PATH}"
    with _GENOME_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def loop_workflow_text() -> str:
    assert _LOOP_WORKFLOW_PATH.exists(), f"Missing: {_LOOP_WORKFLOW_PATH}"
    return _LOOP_WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ci_workflow_text() -> str:
    assert _CI_WORKFLOW_PATH.exists(), f"Missing: {_CI_WORKFLOW_PATH}"
    return _CI_WORKFLOW_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helper: extract a named job section from the workflow text
# ---------------------------------------------------------------------------

def _job_section(workflow_text: str, job_name: str) -> str:
    """Return the text block for a given job name.

    Extracts from '<job_name>:' up to the next sibling job at the same
    indentation level (two spaces), or end of file.
    """
    pattern = rf"(  {re.escape(job_name)}:.*?)(?=\n  [a-zA-Z][\w-]+:\n|\Z)"
    m = re.search(pattern, workflow_text, re.DOTALL)
    assert m is not None, (
        f"Job '{job_name}' not found in immunization_loop.yml. "
        "This job is a required safety boundary."
    )
    return m.group(1)


def _all_job_names(workflow_text: str) -> list[str]:
    """Return all job names defined under the 'jobs:' block."""
    jobs_m = re.search(r"\njobs:\n(.*)", workflow_text, re.DOTALL)
    if jobs_m is None:
        return []
    return re.findall(r"^  ([a-zA-Z][\w-]+):", jobs_m.group(1), re.MULTILINE)


def _non_comment_content(text: str) -> str:
    """Return text with comment-only lines removed."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


def _workflow_dispatch_section(workflow_text: str) -> str:
    """Extract the workflow_dispatch: ... block (under 'on:')."""
    m = re.search(
        r"(  workflow_dispatch:.*?)(?=\n  [a-zA-Z]|\Z)",
        workflow_text,
        re.DOTALL,
    )
    return m.group(1) if m else ""


def _promote_if_condition(workflow_text: str) -> str:
    """Return the if: value of the promote job as a single string.

    The promote job uses a folded YAML scalar ('>') so the condition spans
    multiple indented lines.  We collect all lines between 'if:' and the
    next key at the same indentation level.
    """
    section = _job_section(workflow_text, "promote")
    # Collect everything from 'if:' until the next key at 4-space indent.
    m = re.search(
        r"    if:[ >|\n]+(.*?)(?=\n    [a-zA-Z]|\Z)",
        section,
        re.DOTALL,
    )
    if m is None:
        return ""
    # Flatten multi-line folded scalar into a single string.
    return " ".join(m.group(1).split())


# ===========================================================================
# 1. Phase 3 not-started invariants
# ===========================================================================

class TestPhase3NotStarted:
    """docs/PHASE_2_COMPLETION_CHECKPOINT.md must declare Phase 3 not started."""

    def test_checkpoint_exists(self) -> None:
        assert _CHECKPOINT_PATH.exists(), (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md is missing. "
            "This document is required to declare Phase 3 not started."
        )

    def test_checkpoint_declares_phase3_not_started(
        self, checkpoint_text: str
    ) -> None:
        """The checkpoint must explicitly state Phase 3 is not started."""
        # The doc uses several equivalent phrases; check at least one is present.
        indicators = [
            "Phase 3 is not started",
            "Phase 3 not started",
            "Phase 3: not started",
            "Phase 3 Not Started",
        ]
        found = any(ind.lower() in checkpoint_text.lower() for ind in indicators)
        assert found, (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md must explicitly state "
            "that Phase 3 is not started (e.g. 'Phase 3 is not started'). "
            "This invariant prevents silent phase drift."
        )

    def test_checkpoint_phase2_complete(self, checkpoint_text: str) -> None:
        """The checkpoint must declare Phase 2 complete."""
        assert "Phase 2" in checkpoint_text and (
            "complete" in checkpoint_text.lower() or "completed" in checkpoint_text.lower()
        ), (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md must state that Phase 2 is complete."
        )

    def test_checkpoint_phase3_requires_dedicated_pr(
        self, checkpoint_text: str
    ) -> None:
        """The checkpoint must state Phase 3 requires a dedicated PR."""
        assert "dedicated" in checkpoint_text.lower() and "PR" in checkpoint_text, (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md must require a dedicated PR "
            "for Phase 3 activation. Without this guard, Phase 3 could slip in "
            "via an unrelated PR."
        )


class TestApiActivationChecklistBoundaries:
    """docs/API_ACTIVATION_CHECKLIST.md must preserve Phase 2-E boundaries."""

    def test_checklist_exists(self) -> None:
        assert _CHECKLIST_PATH.exists(), (
            "docs/API_ACTIVATION_CHECKLIST.md is missing."
        )

    def test_checklist_phase2e_no_api_connection(
        self, checklist_text: str
    ) -> None:
        """Phase 2-E explicitly declares no API connection."""
        assert "API 接続を行わない" in checklist_text or (
            "API connection" in checklist_text and "not connected" in checklist_text.lower()
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must state that Phase 2-E "
            "does NOT connect the API."
        )

    def test_checklist_phase2e_no_key_registration(
        self, checklist_text: str
    ) -> None:
        """Phase 2-E explicitly declares no GEMINI_API_KEY registration."""
        assert "GEMINI_API_KEY 登録を行わない" in checklist_text or (
            "GEMINI_API_KEY registration" in checklist_text
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must state that Phase 2-E "
            "does NOT register GEMINI_API_KEY."
        )

    def test_checklist_phase2e_live_model_false(
        self, checklist_text: str
    ) -> None:
        """Phase 2-E explicitly declares live_model_enabled is not set to true."""
        assert (
            "live_model_enabled=true にしない" in checklist_text
            or ("live_model_enabled" in checklist_text and "false" in checklist_text)
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must state that Phase 2-E "
            "does NOT set live_model_enabled=true."
        )

    def test_checklist_phase2e_no_gemini_api_call(
        self, checklist_text: str
    ) -> None:
        """Phase 2-E explicitly declares no Gemini API calls."""
        assert (
            "Gemini API call を行わない" in checklist_text
            or "Gemini API call" in checklist_text
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must state that Phase 2-E "
            "does NOT make Gemini API calls."
        )

    def test_checklist_current_phase_live_model_false(
        self, checklist_text: str
    ) -> None:
        """The current phase status table must show live_model_enabled = false."""
        # Look for the table row that has live_model_enabled and false together
        lines = checklist_text.splitlines()
        live_model_lines = [l for l in lines if "live_model_enabled" in l]
        assert any("false" in l for l in live_model_lines), (
            "docs/API_ACTIVATION_CHECKLIST.md current phase status table "
            "must show live_model_enabled = false."
        )

    def test_checklist_current_phase_not_started(
        self, checklist_text: str
    ) -> None:
        """The current phase status table must show Phase 3 not started."""
        lines = checklist_text.splitlines()
        phase3_lines = [l for l in lines if "Phase 3" in l]
        assert any(
            "Not started" in l or "not started" in l for l in phase3_lines
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md current phase status table "
            "must show Phase 3 = Not started."
        )


# ===========================================================================
# 2. genome.json safety invariants
# ===========================================================================

class TestGenomeSafety:
    """data/genome.json must satisfy all safety constraints."""

    def test_genome_is_valid_json(self) -> None:
        """data/genome.json must be parseable as valid JSON."""
        assert _GENOME_PATH.exists(), "data/genome.json is missing."
        try:
            with _GENOME_PATH.open(encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"data/genome.json is not valid JSON: {exc}. "
                "A corrupted genome prevents the evolution loop from running."
            )

    def test_live_model_enabled_is_strictly_false(self, genome: dict) -> None:
        """live_model_enabled must be exactly False (not 0, not None, not 'false')."""
        val = genome.get("live_model_enabled")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json live_model_enabled must be exactly false (bool). "
            f"Got: {val!r} (type={type(val).__name__}). "
            "Setting this to true would trigger live Gemini API calls in Phase 3."
        )

    def test_send_repository_full_text_is_false(self, genome: dict) -> None:
        """send_repository_full_text must be false — prevents full repo exfiltration."""
        val = genome.get("send_repository_full_text")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json send_repository_full_text must be exactly false. Got: {val!r}"
        )

    def test_send_raw_payloads_is_false(self, genome: dict) -> None:
        """send_raw_payloads must be false — prevents raw exploit payload exfiltration."""
        val = genome.get("send_raw_payloads")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json send_raw_payloads must be exactly false. Got: {val!r}"
        )

    def test_send_secrets_is_false(self, genome: dict) -> None:
        """send_secrets must be false — prevents secret exfiltration to Gemini."""
        val = genome.get("send_secrets")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json send_secrets must be exactly false. Got: {val!r}"
        )

    def test_allow_code_execution_tool_is_false(self, genome: dict) -> None:
        """allow_code_execution_tool must be false — prevents arbitrary code execution via Gemini."""
        val = genome.get("allow_code_execution_tool")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json allow_code_execution_tool must be exactly false. Got: {val!r}"
        )

    def test_allow_url_context_is_false(self, genome: dict) -> None:
        """allow_url_context must be false — prevents URL fetch via Gemini."""
        val = genome.get("allow_url_context")
        assert type(val) is bool and val is False, (  # noqa: E721
            f"genome.json allow_url_context must be exactly false. Got: {val!r}"
        )

    def test_monthly_api_budget_exists(self, genome: dict) -> None:
        """monthly_api_budget_usd must be present."""
        assert "monthly_api_budget_usd" in genome, (
            "genome.json must contain monthly_api_budget_usd. "
            "Missing budget cap means no spending limit is enforced."
        )

    def test_monthly_api_budget_is_positive_number(self, genome: dict) -> None:
        """monthly_api_budget_usd must be a positive number (not bool)."""
        val = genome.get("monthly_api_budget_usd")
        assert isinstance(val, (int, float)) and type(val) is not bool and val > 0, (
            f"genome.json monthly_api_budget_usd must be a positive number. Got: {val!r}"
        )

    def test_monthly_api_budget_within_limit(self, genome: dict) -> None:
        """monthly_api_budget_usd must be 10.0 or less."""
        val = genome.get("monthly_api_budget_usd")
        assert isinstance(val, (int, float)) and val <= 10.0, (
            f"genome.json monthly_api_budget_usd must be <= 10.0 USD. Got: {val!r}. "
            "Exceeding this cap indicates an unauthorized budget increase."
        )

    def test_daily_api_budget_exists(self, genome: dict) -> None:
        """daily_api_budget_usd must be present."""
        assert "daily_api_budget_usd" in genome, (
            "genome.json must contain daily_api_budget_usd. "
            "Missing daily cap allows unbounded spending within a single day."
        )

    def test_daily_api_budget_is_positive_number(self, genome: dict) -> None:
        """daily_api_budget_usd must be a positive number (not bool)."""
        val = genome.get("daily_api_budget_usd")
        assert isinstance(val, (int, float)) and type(val) is not bool and val > 0, (
            f"genome.json daily_api_budget_usd must be a positive number. Got: {val!r}"
        )

    def test_daily_api_budget_within_limit(self, genome: dict) -> None:
        """daily_api_budget_usd must be 0.25 or less."""
        val = genome.get("daily_api_budget_usd")
        assert isinstance(val, (int, float)) and val <= 0.25, (
            f"genome.json daily_api_budget_usd must be <= 0.25 USD. Got: {val!r}. "
            "Exceeding this cap indicates an unauthorized daily budget increase."
        )


# ===========================================================================
# 3. Workflow permission invariants
# ===========================================================================

class TestWorkflowExists:
    def test_immunization_loop_exists(self) -> None:
        assert _LOOP_WORKFLOW_PATH.exists(), (
            f"Missing: {_LOOP_WORKFLOW_PATH}. "
            "The immunization loop workflow is required for the evolution pipeline."
        )


class TestWorkflowJobPermissions:
    """Each job must have the correct permissions.contents value.

    Checks are done by extracting each job's text section and scanning for
    'contents: <value>' outside of comment lines — no YAML parser required.
    """

    def _job_has_permission(
        self, loop_workflow_text: str, job_name: str, value: str
    ) -> bool:
        section = _job_section(loop_workflow_text, job_name)
        return f"contents: {value}" in _non_comment_content(section)

    def test_propose_job_contents_read(self, loop_workflow_text: str) -> None:
        """propose job must have contents: read — it must never write to the repo."""
        assert self._job_has_permission(loop_workflow_text, "propose", "read"), (
            "propose job permissions must include 'contents: read'. "
            "The propose job must be read-only to prevent generated code from "
            "being committed without going through the promote gate."
        )
        assert not self._job_has_permission(loop_workflow_text, "propose", "write"), (
            "propose job must NOT have 'contents: write'."
        )

    def test_evaluate_job_contents_read(self, loop_workflow_text: str) -> None:
        """evaluate job must have contents: read — it must never write to the repo."""
        assert self._job_has_permission(loop_workflow_text, "evaluate", "read"), (
            "evaluate job permissions must include 'contents: read'. "
            "The evaluate job runs generated candidate code; write permissions "
            "here would allow untrusted code to modify the repository."
        )
        assert not self._job_has_permission(loop_workflow_text, "evaluate", "write"), (
            "evaluate job must NOT have 'contents: write'."
        )

    def test_finalize_propose_status_job_contents_none(
        self, loop_workflow_text: str
    ) -> None:
        """finalize-propose-status job must have contents: none."""
        assert self._job_has_permission(
            loop_workflow_text, "finalize-propose-status", "none"
        ), (
            "finalize-propose-status job permissions must include 'contents: none'. "
            "This job only surfaces failure status and needs no repository access."
        )

    def test_only_persist_ledger_and_promote_have_contents_write(
        self, loop_workflow_text: str
    ) -> None:
        """Only persist-ledger and promote jobs may have contents: write."""
        allowed_write_jobs = {"persist-ledger", "promote"}
        for job_name in _all_job_names(loop_workflow_text):
            section = _job_section(loop_workflow_text, job_name)
            has_write = "contents: write" in _non_comment_content(section)
            if has_write:
                assert job_name in allowed_write_jobs, (
                    f"Job '{job_name}' has 'contents: write' but is not in the "
                    f"allowed set {allowed_write_jobs}. Only persist-ledger and "
                    "promote may have write permissions."
                )


class TestCiWorkflowNoContentsWrite:
    """ci.yml must be entirely read-only (no contents: write anywhere)."""

    def test_ci_has_no_contents_write(self, ci_workflow_text: str) -> None:
        """Normal CI must never have contents: write."""
        assert "contents: write" not in ci_workflow_text, (
            "ci.yml must NOT contain 'contents: write'. "
            "CI is read-only and must never commit or push to the repository."
        )


# ===========================================================================
# 4. Step-level secret scoping invariants
# ===========================================================================

class TestNoopStepNoApiKey:
    """The noop propose step must not receive GEMINI_API_KEY."""

    def _get_noop_step_text(self, loop_workflow_text: str) -> str:
        """Extract the noop mode step from the workflow text."""
        m = re.search(
            r"(- name: Propose mutation patch — noop.*?)(?=\n      - name:|\Z)",
            loop_workflow_text,
            re.DOTALL,
        )
        assert m is not None, (
            "Could not find 'Propose mutation patch — noop' step. "
            "The noop step is required."
        )
        return m.group(1)

    def test_noop_step_has_no_gemini_api_key_env(
        self, loop_workflow_text: str
    ) -> None:
        """noop step must not have GEMINI_API_KEY in its env block."""
        step_text = self._get_noop_step_text(loop_workflow_text)
        # Check that GEMINI_API_KEY (the raw secret) is not in this step's env.
        # We look for 'GEMINI_API_KEY:' assignment (not just the word in comments).
        assert "GEMINI_API_KEY:" not in step_text, (
            "The noop propose step must NOT inject GEMINI_API_KEY. "
            "noop mode makes no API calls; injecting the secret widens "
            "its exposure surface unnecessarily."
        )


class TestOfflineSampleStepNoApiKey:
    """The offline-sample propose step must not receive GEMINI_API_KEY."""

    def _get_offline_step_text(self, loop_workflow_text: str) -> str:
        m = re.search(
            r"(- name: Propose mutation patch — offline-sample.*?)(?=\n      - name:|\Z)",
            loop_workflow_text,
            re.DOTALL,
        )
        assert m is not None, (
            "Could not find 'Propose mutation patch — offline-sample' step."
        )
        return m.group(1)

    def test_offline_sample_step_has_no_gemini_api_key_env(
        self, loop_workflow_text: str
    ) -> None:
        """offline-sample step must not have GEMINI_API_KEY in its env block."""
        step_text = self._get_offline_step_text(loop_workflow_text)
        assert "GEMINI_API_KEY:" not in step_text, (
            "The offline-sample propose step must NOT inject GEMINI_API_KEY. "
            "offline-sample mode makes no live API calls."
        )


class TestPreflightStepBooleanSignalOnly:
    """gemini-paid-credit-preflight step must use GEMINI_API_KEY_PRESENT, not raw key."""

    def _get_preflight_step_text(self, loop_workflow_text: str) -> str:
        m = re.search(
            r"(- name: Propose mutation patch — gemini-paid-credit-preflight.*?)"
            r"(?=\n      - name:|\Z)",
            loop_workflow_text,
            re.DOTALL,
        )
        assert m is not None, (
            "Could not find 'Propose mutation patch — gemini-paid-credit-preflight' step."
        )
        return m.group(1)

    def test_preflight_uses_gemini_api_key_present(
        self, loop_workflow_text: str
    ) -> None:
        """preflight step must reference GEMINI_API_KEY_PRESENT."""
        step_text = self._get_preflight_step_text(loop_workflow_text)
        assert "GEMINI_API_KEY_PRESENT" in step_text, (
            "gemini-paid-credit-preflight step must inject GEMINI_API_KEY_PRESENT "
            "(boolean signal only) so the preflight can verify the key is configured "
            "without receiving the raw secret value."
        )

    def test_preflight_does_not_receive_raw_gemini_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """preflight step must NOT have GEMINI_API_KEY: (raw secret) in its env."""
        step_text = self._get_preflight_step_text(loop_workflow_text)
        # GEMINI_API_KEY_PRESENT is OK; GEMINI_API_KEY: (as an env assignment) is not.
        # We check that there is no line like `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}`
        # i.e. a raw key assignment. Exclude GEMINI_API_KEY_PRESENT lines.
        lines_with_raw_key = [
            line for line in step_text.splitlines()
            if re.search(r"\bGEMINI_API_KEY\s*:", line)
            and "GEMINI_API_KEY_PRESENT" not in line
        ]
        assert len(lines_with_raw_key) == 0, (
            "gemini-paid-credit-preflight step must NOT inject raw GEMINI_API_KEY. "
            "Only GEMINI_API_KEY_PRESENT (boolean signal) is permitted. "
            f"Found raw key lines: {lines_with_raw_key}"
        )


class TestApiModeStepsHaveRawKey:
    """live-model and gemini-paid-credit steps must have GEMINI_API_KEY env."""

    def _get_step_text(self, loop_workflow_text: str, mode: str) -> str:
        # Use a negative lookahead so 'gemini-paid-credit' does not match
        # 'gemini-paid-credit-preflight' (which has an extra '-' after the mode name).
        escaped = re.escape(mode)
        m = re.search(
            rf"(- name: Propose mutation patch — {escaped}(?!-).*?)"
            r"(?=\n      - name:|\Z)",
            loop_workflow_text,
            re.DOTALL,
        )
        assert m is not None, (
            f"Could not find 'Propose mutation patch — {mode}' step "
            "(exact match, not preflight)."
        )
        return m.group(1)

    def test_live_model_step_has_raw_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """live-model step must inject GEMINI_API_KEY (raw secret)."""
        step_text = self._get_step_text(loop_workflow_text, "live-model")
        assert "GEMINI_API_KEY:" in step_text, (
            "live-model step must inject GEMINI_API_KEY so the script can "
            "authenticate with the Gemini API in live-model mode."
        )

    def test_gemini_paid_credit_step_has_raw_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """gemini-paid-credit step must inject GEMINI_API_KEY (raw secret)."""
        step_text = self._get_step_text(loop_workflow_text, "gemini-paid-credit")
        assert "GEMINI_API_KEY:" in step_text, (
            "gemini-paid-credit step must inject GEMINI_API_KEY so the script "
            "can authenticate with the Gemini API."
        )


class TestOtherJobsHaveNoRawApiKey:
    """persist-ledger, evaluate, and promote jobs must have no GEMINI_API_KEY env."""

    def _job_has_raw_api_key(
        self, workflow_text: str, job_name: str
    ) -> list[str]:
        """Return lines in the job section that assign raw GEMINI_API_KEY."""
        section = _job_section(workflow_text, job_name)
        return [
            line for line in section.splitlines()
            if re.search(r"\bGEMINI_API_KEY\s*:", line)
            and "GEMINI_API_KEY_PRESENT" not in line
            and not line.lstrip().startswith("#")
        ]

    def test_persist_ledger_has_no_raw_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """persist-ledger job must not receive raw GEMINI_API_KEY."""
        bad_lines = self._job_has_raw_api_key(loop_workflow_text, "persist-ledger")
        assert len(bad_lines) == 0, (
            "persist-ledger job must NOT inject GEMINI_API_KEY. "
            "Write permissions and model secrets must remain in separate jobs. "
            f"Found: {bad_lines}"
        )

    def test_evaluate_has_no_raw_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """evaluate job must not receive raw GEMINI_API_KEY."""
        bad_lines = self._job_has_raw_api_key(loop_workflow_text, "evaluate")
        assert len(bad_lines) == 0, (
            "evaluate job must NOT inject GEMINI_API_KEY. "
            "Candidate code is executed in this job; giving it API credentials "
            "would allow the candidate to make unauthorized API calls. "
            f"Found: {bad_lines}"
        )

    def test_promote_has_no_raw_api_key(
        self, loop_workflow_text: str
    ) -> None:
        """promote job must not receive raw GEMINI_API_KEY."""
        bad_lines = self._job_has_raw_api_key(loop_workflow_text, "promote")
        assert len(bad_lines) == 0, (
            "promote job must NOT inject GEMINI_API_KEY. "
            "Write permissions and model secrets must remain in separate jobs. "
            f"Found: {bad_lines}"
        )


# ===========================================================================
# 5. Promote gate invariants
# ===========================================================================

class TestPromoteGate:
    """Promote job must require explicit Human Owner approval via workflow_dispatch.

    All checks use text / regex inspection of the workflow file — no YAML parser.
    """

    def test_workflow_dispatch_input_promote_approved_exists(
        self, loop_workflow_text: str
    ) -> None:
        """workflow_dispatch must have a promote_approved input."""
        wf_dispatch = _workflow_dispatch_section(loop_workflow_text)
        assert "promote_approved:" in wf_dispatch, (
            "workflow_dispatch inputs must include 'promote_approved:'. "
            "Without this input, Human Owner cannot gate the promote job."
        )

    def test_promote_approved_default_is_false(
        self, loop_workflow_text: str
    ) -> None:
        """promote_approved default must be 'false' to prevent accidental promotion.

        We locate the promote_approved input block and confirm that a
        'default: \"false\"' line appears before the next sibling input key.
        """
        wf_dispatch = _workflow_dispatch_section(loop_workflow_text)
        # Extract the promote_approved: block up to the next 6-space-indent key.
        m = re.search(
            r"      promote_approved:(.*?)(?=\n      [a-zA-Z]|\Z)",
            wf_dispatch,
            re.DOTALL,
        )
        assert m is not None, (
            "Could not locate the 'promote_approved:' input block in "
            "the workflow_dispatch inputs section."
        )
        block = m.group(1)
        assert 'default: "false"' in block, (
            f"promote_approved input default must be '\"false\"'. "
            "A truthy default would allow unintended promotion without Human Owner approval. "
            f"promote_approved block:\n{block}"
        )

    def test_promote_if_requires_workflow_dispatch(
        self, loop_workflow_text: str
    ) -> None:
        """promote job if condition must require github.event_name == 'workflow_dispatch'."""
        if_str = _promote_if_condition(loop_workflow_text)
        assert "github.event_name == 'workflow_dispatch'" in if_str, (
            "promote job if condition must require "
            "github.event_name == 'workflow_dispatch'. "
            "Without this, schedule events could trigger promotion. "
            f"Extracted if condition: {if_str!r}"
        )

    def test_promote_if_requires_promote_approved_true(
        self, loop_workflow_text: str
    ) -> None:
        """promote job if condition must require promote_approved == 'true'."""
        if_str = _promote_if_condition(loop_workflow_text)
        assert "promote_approved == 'true'" in if_str, (
            "promote job if condition must require "
            "github.event.inputs.promote_approved == 'true'. "
            "Without this, generated code could be promoted without Human Owner approval. "
            f"Extracted if condition: {if_str!r}"
        )

    def test_promote_cannot_run_on_schedule_alone(
        self, loop_workflow_text: str
    ) -> None:
        """promote job cannot execute on schedule events alone.

        schedule events never set github.event_name to 'workflow_dispatch',
        so requiring workflow_dispatch in the if condition ensures schedule
        runs can never promote.  This test verifies that both the
        workflow_dispatch event-name check and the promote_approved check
        are present simultaneously.
        """
        if_str = _promote_if_condition(loop_workflow_text)
        has_event_name_check = "github.event_name == 'workflow_dispatch'" in if_str
        has_approved_check = "promote_approved == 'true'" in if_str
        assert has_event_name_check and has_approved_check, (
            "promote job if condition must prevent schedule-driven promotion. "
            "Both github.event_name == 'workflow_dispatch' and "
            "promote_approved == 'true' must be present. "
            f"Extracted if condition: {if_str!r}"
        )


# ===========================================================================
# 6. Generated-code / write-permission separation invariants
# ===========================================================================

class TestEvaluateJobReadOnly:
    """evaluate job handles generated candidate but must be read-only."""

    def test_evaluate_downloads_candidate_artifact(
        self, loop_workflow_text: str
    ) -> None:
        """evaluate job must download the candidate artifact for evaluation."""
        section = _job_section(loop_workflow_text, "evaluate")
        assert "candidate-detector" in section or "mutation-patch" in section, (
            "evaluate job must download the candidate or patch artifact."
        )

    def test_evaluate_has_no_git_push(self, loop_workflow_text: str) -> None:
        """evaluate job must not push to the repository."""
        section = _job_section(loop_workflow_text, "evaluate")
        assert "git push" not in section, (
            "evaluate job must NOT contain 'git push'. "
            "Candidate code is executed here; a git push would allow it to "
            "commit changes with write permissions."
        )

    def test_evaluate_has_no_git_commit(self, loop_workflow_text: str) -> None:
        """evaluate job must not make git commits."""
        section = _job_section(loop_workflow_text, "evaluate")
        assert "git commit" not in section, (
            "evaluate job must NOT contain 'git commit'."
        )


class TestPromoteJobNoCandidateExecution:
    """promote job has write permissions but must not execute candidate code."""

    def test_promote_does_not_run_candidate_directly(
        self, loop_workflow_text: str
    ) -> None:
        """promote job must not execute candidate_detector.py directly as a script."""
        section = _job_section(loop_workflow_text, "promote")
        # Candidate execution would look like: python candidate_detector.py
        # or: python .cyber_immunizer/candidate_detector.py
        assert not re.search(
            r"python\s+.*candidate_detector\.py", section
        ), (
            "promote job must NOT execute candidate_detector.py directly. "
            "Candidate execution happens only in the read-only evaluate job."
        )

    def test_promote_does_not_commit_ledger(
        self, loop_workflow_text: str
    ) -> None:
        """promote job git add must not include api_usage_ledger.json."""
        section = _job_section(loop_workflow_text, "promote")
        # Check that api_usage_ledger.json is not in a git add command
        git_add_lines = [
            l for l in section.splitlines() if "git add" in l
        ]
        for line in git_add_lines:
            assert "api_usage_ledger.json" not in line, (
                "promote job must NOT git add api_usage_ledger.json. "
                "Ledger persistence is exclusively the responsibility of "
                "the persist-ledger job to prevent concurrent write races. "
                f"Found: {line!r}"
            )

    def test_promote_commits_expected_files(
        self, loop_workflow_text: str
    ) -> None:
        """promote job git add should include core/detector.py, genome.json, etc."""
        section = _job_section(loop_workflow_text, "promote")
        git_add_lines = [l for l in section.splitlines() if "git add" in l]
        combined = " ".join(git_add_lines)
        # At minimum, the promoted detector and genome must be committed.
        assert "core/detector.py" in combined or "detector.py" in combined, (
            "promote job must git add core/detector.py (the promoted detector)."
        )
        assert "genome.json" in combined, (
            "promote job must git add data/genome.json."
        )


class TestPersistLedgerWritesOnlyLedger:
    """persist-ledger job has write permissions but must only commit the ledger."""

    def test_persist_ledger_does_not_download_patch(
        self, loop_workflow_text: str
    ) -> None:
        """persist-ledger must not download the mutation patch artifact."""
        section = _job_section(loop_workflow_text, "persist-ledger")
        assert "mutation-patch" not in section, (
            "persist-ledger job must NOT download the mutation-patch artifact. "
            "This job must not interact with generated candidate code."
        )

    def test_persist_ledger_does_not_download_candidate(
        self, loop_workflow_text: str
    ) -> None:
        """persist-ledger must not download the candidate-detector artifact."""
        section = _job_section(loop_workflow_text, "persist-ledger")
        assert "candidate-detector" not in section, (
            "persist-ledger job must NOT download the candidate-detector artifact. "
            "Write permissions and candidate code must remain separated."
        )

    def test_persist_ledger_commits_only_ledger(
        self, loop_workflow_text: str
    ) -> None:
        """persist-ledger git add must only include api_usage_ledger.json."""
        section = _job_section(loop_workflow_text, "persist-ledger")
        git_add_lines = [l for l in section.splitlines() if "git add" in l]
        assert len(git_add_lines) > 0, (
            "persist-ledger job must have at least one 'git add' command."
        )
        for line in git_add_lines:
            assert "api_usage_ledger.json" in line, (
                "persist-ledger job 'git add' must reference api_usage_ledger.json. "
                f"Found unexpected git add line: {line!r}"
            )
            # Must not add other files like detector.py or genome.json
            for forbidden in ["detector.py", "genome.json", "evolution_history.json",
                              "README.md"]:
                assert forbidden not in line, (
                    f"persist-ledger job must NOT git add '{forbidden}'. "
                    "Only the API usage ledger should be committed by this job. "
                    f"Found: {line!r}"
                )


# ===========================================================================
# 7. Repository secret leakage invariants
# ===========================================================================

# Raw secret patterns to detect (false-positive resistant):
_RAW_SECRET_PATTERNS = [
    # Google API key — starts with AIza followed by 35 characters
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key (AIza...)"),
    # OpenAI secret key
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI key (sk-...)"),
    # GitHub PAT formats
    (re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"), "GitHub PAT (ghp_...)"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub PAT (github_pat_...)"),
    # PEM private key header
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
     "PEM private key header"),
]

# Files / directories to skip during scan
_SCAN_EXCLUDES = {".git", "venv", ".venv", ".pytest_cache", "__pycache__",
                  "node_modules", ".tox", "dist", "build", "*.egg-info"}


def _collect_tracked_files() -> list[Path]:
    """Return all git-tracked text files under _ROOT, excluding known noise dirs."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = []
        for rel in result.stdout.splitlines():
            p = _ROOT / rel
            # Skip binary-ish extensions
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico",
                                     ".pdf", ".pyc", ".so", ".dylib", ".exe"}:
                continue
            paths.append(p)
        return paths
    except Exception as exc:
        pytest.fail(f"Could not enumerate tracked files via git ls-files: {exc}")


class TestRepositorySecretLeakage:
    """No raw secret values must appear in any git-tracked file."""

    @pytest.fixture(scope="class")
    def tracked_files(self) -> list[Path]:
        return _collect_tracked_files()

    def test_no_google_api_key_pattern(self, tracked_files: list[Path]) -> None:
        """No file must contain an AIza... Google API key pattern."""
        pattern, label = _RAW_SECRET_PATTERNS[0]
        hits: list[str] = []
        for fp in tracked_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                hits.append(f"{fp.relative_to(_ROOT)}:{m.start()}: {m.group()!r}")
        assert len(hits) == 0, (
            f"Found {label} pattern(s) in tracked files:\n"
            + "\n".join(hits[:10])
        )

    def test_no_openai_key_pattern(self, tracked_files: list[Path]) -> None:
        """No file must contain an sk-... OpenAI key pattern."""
        pattern, label = _RAW_SECRET_PATTERNS[1]
        hits: list[str] = []
        for fp in tracked_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                hits.append(f"{fp.relative_to(_ROOT)}:{m.start()}: {m.group()!r}")
        assert len(hits) == 0, (
            f"Found {label} pattern(s) in tracked files:\n"
            + "\n".join(hits[:10])
        )

    def test_no_github_pat_ghp_pattern(self, tracked_files: list[Path]) -> None:
        """No file must contain a ghp_... GitHub PAT pattern."""
        pattern, label = _RAW_SECRET_PATTERNS[2]
        hits: list[str] = []
        for fp in tracked_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                hits.append(f"{fp.relative_to(_ROOT)}:{m.start()}: {m.group()!r}")
        assert len(hits) == 0, (
            f"Found {label} pattern(s) in tracked files:\n"
            + "\n".join(hits[:10])
        )

    def test_no_github_pat_github_pat_pattern(
        self, tracked_files: list[Path]
    ) -> None:
        """No file must contain a github_pat_... GitHub PAT pattern."""
        pattern, label = _RAW_SECRET_PATTERNS[3]
        hits: list[str] = []
        for fp in tracked_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                hits.append(f"{fp.relative_to(_ROOT)}:{m.start()}: {m.group()!r}")
        assert len(hits) == 0, (
            f"Found {label} pattern(s) in tracked files:\n"
            + "\n".join(hits[:10])
        )

    def test_no_pem_private_key_header(
        self, tracked_files: list[Path]
    ) -> None:
        """No file must contain a PEM private key header."""
        pattern, label = _RAW_SECRET_PATTERNS[4]
        hits: list[str] = []
        for fp in tracked_files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                hits.append(f"{fp.relative_to(_ROOT)}:{m.start()}: {m.group()!r}")
        assert len(hits) == 0, (
            f"Found {label} pattern(s) in tracked files:\n"
            + "\n".join(hits[:10])
        )

    def test_gemini_api_key_string_itself_is_not_forbidden(
        self, tracked_files: list[Path]
    ) -> None:
        """Sanity check: the string 'GEMINI_API_KEY' is legal in docs/tests/workflows.

        This test asserts that 'GEMINI_API_KEY' appears in the repository
        (confirming we haven't over-scrubbed legitimate references), while
        the raw pattern tests above ensure no actual key *value* is present.
        """
        # At least one tracked file should mention GEMINI_API_KEY
        found = False
        for fp in tracked_files:
            try:
                if "GEMINI_API_KEY" in fp.read_text(encoding="utf-8", errors="replace"):
                    found = True
                    break
            except OSError:
                continue
        assert found, (
            "Expected to find 'GEMINI_API_KEY' referenced in at least one "
            "tracked file (docs, tests, or workflow). If it's entirely absent "
            "something may have been incorrectly removed."
        )
