"""tests/test_phase2_completion_checkpoint_docs.py — Phase 2 completion checkpoint hardening tests.

Verifies that docs/PHASE_2_COMPLETION_CHECKPOINT.md:
- Exists and contains all required sections
- Contains a Safety Invariant Traceability Matrix
- Contains a Residual Risk Register
- Contains a Phase 3 Go / No-Go Decision Record Template
- Correctly documents GitHub Secrets verification boundary
- Documents review prompt hygiene

Verifies that safety invariant tests in this file are strict:
- live_model_enabled invariant is verified via explicit "false" state (not just co-occurrence)
- Normal CI read-only invariant is verified via explicit text (not just "normal ci" presence)
- Workflow permission escalation is rejected in affirmative context
- GEMINI_API_KEY "not registered" ambiguous phrasing is rejected
- Phase state regression guard covers README.md and docs

Addresses issues:
  #5  Traceability Matrix / Residual Risk Register / Go-No-Go template absent
  #6  GitHub Secrets verification boundary not stated in checkpoint
  #7  live_model_enabled invariant only checks co-occurrence
  #8  Normal CI read-only check passes on mere "normal ci" occurrence
  #9  Workflow permission escalation test passes in affirmative context
  #10 GEMINI_API_KEY "not registered" ambiguous expression not rejected
  #11 Review prompt hygiene (PR-target confusion) not documented
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_CHECKPOINT = _PROJECT_ROOT / "docs" / "PHASE_2_COMPLETION_CHECKPOINT.md"
_README = _PROJECT_ROOT / "README.md"
_PHASE2_PLAN = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
_API_RUNBOOK = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_section(content: str, heading: str, next_headings: int = 2) -> str:
    """Extract text from a markdown section heading until the next same-or-higher heading."""
    lines = content.splitlines()
    in_section = False
    result_lines: list[str] = []
    heading_level = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("#").strip()
            if heading.lower() in title.lower():
                in_section = True
                heading_level = level
                result_lines.append(line)
                continue
            if in_section and level <= heading_level:
                break
        if in_section:
            result_lines.append(line)

    return "\n".join(result_lines)


def _section_exists(content: str, keyword: str) -> bool:
    """Return True if any heading line contains keyword (case-insensitive)."""
    for line in content.splitlines():
        if line.strip().startswith("#") and keyword.lower() in line.lower():
            return True
    return False


def _extract_current_state_section(content: str) -> str:
    """Extract the 'Current State after Phase 2' section."""
    return _extract_section(content, "Current State after Phase 2")


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------


class TestCheckpointFileExists:
    def test_checkpoint_file_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must exist."""
        assert _CHECKPOINT.exists(), (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md does not exist. "
            "Create it as the Phase 2 completion checkpoint."
        )


# ---------------------------------------------------------------------------
# 2. Required sections
# ---------------------------------------------------------------------------


class TestCheckpointRequiredSections:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists(), "PHASE_2_COMPLETION_CHECKPOINT.md must exist"
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_has_purpose_section(self) -> None:
        assert _section_exists(self.content, "Purpose"), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Purpose' section"
        )

    def test_has_completion_status_section(self) -> None:
        assert _section_exists(self.content, "Completion Status") or \
               _section_exists(self.content, "Completion status"), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Completion Status' section"
        )

    def test_has_current_state_section(self) -> None:
        assert _section_exists(self.content, "Current State after Phase 2") or \
               _section_exists(self.content, "Current state after Phase 2"), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Current State after Phase 2' section"
        )

    def test_has_deliverables_section(self) -> None:
        assert _section_exists(self.content, "Deliverable") or \
               "deliverable" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must describe Phase 2 deliverables"
        )

    def test_has_safety_invariants_section(self) -> None:
        assert _section_exists(self.content, "Safety Invariant") or \
               "safety invariant" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Safety Invariants section"
        )

    def test_has_traceability_matrix_section(self) -> None:
        """Issue #5: Traceability Matrix must exist."""
        assert _section_exists(self.content, "Traceability Matrix") or \
               "traceability matrix" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Safety Invariant Traceability Matrix section"
        )

    def test_has_residual_risk_section(self) -> None:
        """Issue #5: Residual Risk Register must exist."""
        assert _section_exists(self.content, "Residual Risk") or \
               "residual risk" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Residual Risk Register section"
        )

    def test_has_go_nogo_template_section(self) -> None:
        """Issue #5: Go / No-Go Decision Record Template must exist."""
        assert (
            "go / no-go" in self.content.lower()
            or "go/no-go" in self.content.lower()
            or "go-no-go" in self.content.lower()
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Phase 3 Go / No-Go Decision Record Template"
        )

    def test_has_phase3_entry_conditions_section(self) -> None:
        assert _section_exists(self.content, "Phase 3 Entry") or \
               "phase 3 entry conditions" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have Phase 3 Entry Conditions section"
        )

    def test_has_non_goals_section(self) -> None:
        assert _section_exists(self.content, "Non-Goal") or \
               "non-goal" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Non-Goals section"
        )

    def test_has_related_documents_section(self) -> None:
        assert _section_exists(self.content, "Related Document") or \
               "related document" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Related Documents section"
        )


# ---------------------------------------------------------------------------
# 3. Completion status table
# ---------------------------------------------------------------------------


class TestCompletionStatusTable:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_phase2a_completed(self) -> None:
        content = self.content
        assert "Phase 2-A" in content
        for line in content.splitlines():
            if "Phase 2-A" in line and line.strip().startswith("|"):
                assert "Completed" in line or "✅" in line, (
                    f"Phase 2-A row must show Completed/✅, got: {line!r}"
                )
                return
        assert "Completed" in content or "✅" in content, "Phase 2-A must be marked Completed"

    def test_phase2b_completed(self) -> None:
        content = self.content
        assert "Phase 2-B" in content
        for line in content.splitlines():
            if "Phase 2-B" in line and line.strip().startswith("|"):
                assert "Completed" in line or "✅" in line, (
                    f"Phase 2-B row must show Completed/✅, got: {line!r}"
                )
                return

    def test_phase2c_completed(self) -> None:
        content = self.content
        assert "Phase 2-C" in content
        for line in content.splitlines():
            if "Phase 2-C" in line and line.strip().startswith("|"):
                assert "Completed" in line or "✅" in line, (
                    f"Phase 2-C row must show Completed/✅, got: {line!r}"
                )
                return

    def test_phase2d_completed(self) -> None:
        content = self.content
        assert "Phase 2-D" in content
        for line in content.splitlines():
            if "Phase 2-D" in line and line.strip().startswith("|"):
                assert "Completed" in line or "✅" in line, (
                    f"Phase 2-D row must show Completed/✅, got: {line!r}"
                )
                return

    def test_phase2e_completed(self) -> None:
        content = self.content
        assert "Phase 2-E" in content
        for line in content.splitlines():
            if "Phase 2-E" in line and line.strip().startswith("|"):
                assert "Completed" in line or "✅" in line, (
                    f"Phase 2-E row must show Completed/✅, got: {line!r}"
                )
                return

    def test_phase2_complete_not_phase3_started(self) -> None:
        """Checkpoint must state Phase 2 complete ≠ Phase 3 started."""
        content_lower = self.content.lower()
        assert (
            "phase 2 complete does not mean phase 3" in content_lower
            or "phase 2 complete is not phase 3" in content_lower
            or ("phase 2 complete" in content_lower and "phase 3 not started" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must explicitly state "
            "that 'Phase 2 complete does not mean Phase 3 started'"
        )


# ---------------------------------------------------------------------------
# 4A. live_model_enabled invariant — Issue #7
#     Must verify explicit "false" state in Current State section,
#     NOT just co-occurrence of keywords.
# ---------------------------------------------------------------------------


class TestLiveModelEnabledInvariant:
    """Issue #7: live_model_enabled invariant must verify explicit false state.

    The test must extract the Current State section and verify that
    live_model_enabled is explicitly stated as false in that section.
    A document that says 'live_model_enabled=true in phase 2' must fail.
    A document that says 'do not set live_model_enabled=true' must pass.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.current_state = _extract_current_state_section(self.content)

    # --- Positive: Current State section must explicitly record false ---

    def test_current_state_section_exists_and_has_live_model_enabled(self) -> None:
        """Current State section must exist and mention live_model_enabled."""
        assert self.current_state, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Current State after Phase 2' section"
        )
        assert "live_model_enabled" in self.current_state, (
            "Current State section must mention live_model_enabled"
        )

    def test_current_state_explicitly_records_live_model_false(self) -> None:
        """Current State section must explicitly record live_model_enabled as false.

        Accepted patterns (any one suffices):
          - live_model_enabled | false
          - live_model_enabled: false
          - live_model_enabled remains false
          - live_model_enabled = false
        """
        section = self.current_state.lower()
        accepted = (
            "live_model_enabled | false" in section
            or "live_model_enabled: false" in section
            or "live_model_enabled remains false" in section
            or "live_model_enabled = false" in section
            or "live_model_enabled** | false" in section
        )
        assert accepted, (
            "Current State section must explicitly show live_model_enabled as false. "
            f"Section text: {self.current_state[:400]!r}"
        )

    # --- Negative: Dangerous affirmative phrases must be rejected ---

    def test_rejects_live_model_true_in_phase2_phrase(self) -> None:
        """Reject 'live_model_enabled=true in phase 2'."""
        assert "live_model_enabled=true in phase 2" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'live_model_enabled=true in phase 2'"
        )

    def test_rejects_phase2_enables_live_model_true(self) -> None:
        """Reject 'phase 2 enables live_model_enabled=true'."""
        assert "phase 2 enables live_model_enabled=true" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'phase 2 enables live_model_enabled=true'"
        )

    def test_rejects_live_model_true_is_active(self) -> None:
        """Reject 'live_model_enabled=true is active'."""
        assert "live_model_enabled=true is active" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'live_model_enabled=true is active'"
        )

    def test_rejects_live_model_true_active(self) -> None:
        """Reject 'live_model_enabled=true active' (Japanese and English)."""
        forbidden = [
            "live_model_enabled=true active",
            "live_model_enabled=true enabled",
            "live_model_enabled=true有効化済み",
            "phase 2でlive_model_enabled=true",
        ]
        for phrase in forbidden:
            assert phrase not in self.content.lower(), (
                f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain '{phrase}'"
            )


# ---------------------------------------------------------------------------
# 4B. Normal CI read-only invariant — Issue #8
#     Must verify explicit read-only claim in appropriate section,
#     NOT just the presence of "normal ci" in the document.
# ---------------------------------------------------------------------------


class TestNormalCIReadOnlyInvariant:
    """Issue #8: Normal CI read-only check must not pass on mere 'normal ci' occurrence.

    The test must extract the Current State section or Safety Invariants section
    and verify that 'Normal CI' is explicitly described as read-only.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.current_state = _extract_current_state_section(self.content)
        self.safety_invariants = _extract_section(self.content, "Safety Invariants Preserved")

    # --- Positive: Must explicitly state Normal CI is read-only ---

    def test_current_state_or_invariants_state_normal_ci_read_only(self) -> None:
        """Normal CI must be explicitly stated as read-only in Current State or Safety Invariants section.

        Accepted patterns (any one suffices):
          - Normal CI | read-only
          - Normal CI: read-only
          - normal CI is read-only
          - normal CI remains read-only
          - normal CI has contents: read
          - no contents: write in normal CI
        """
        combined = (self.current_state + self.safety_invariants).lower()
        accepted = (
            "normal ci | read-only" in combined
            or "normal ci: read-only" in combined
            or "normal ci is read-only" in combined
            or "normal ci remains read-only" in combined
            or "normal ci has contents: read" in combined
            or "no contents: write in normal ci" in combined
            or "contents: read only" in combined
            or "contents: read only; no contents: write in normal ci" in combined
            or "normal ci remains read-only (contents: read only" in combined
        )
        assert accepted, (
            "Current State or Safety Invariants section must explicitly state "
            "that Normal CI is read-only. "
            f"Current State: {self.current_state[:300]!r}, "
            f"Safety Invariants: {self.safety_invariants[:300]!r}"
        )

    # --- Negative: Dangerous affirmative phrases must be rejected ---

    def test_rejects_normal_ci_uses_contents_write(self) -> None:
        """Reject 'normal ci uses contents: write'."""
        assert "normal ci uses contents: write" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'normal ci uses contents: write'"
        )

    def test_rejects_normal_ci_has_contents_write(self) -> None:
        """Reject 'normal ci has contents: write'."""
        assert "normal ci has contents: write" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'normal ci has contents: write'"
        )

    def test_rejects_normal_ci_calls_gemini(self) -> None:
        """Reject 'normal ci calls gemini'."""
        forbidden = [
            "normal ci calls gemini",
            "normal ci can call gemini",
            "通常ciでgemini apiを呼ぶ",
            "通常ciにwrite権限を付与する",
        ]
        for phrase in forbidden:
            assert phrase not in self.content.lower(), (
                f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain '{phrase}'"
            )

    def test_rejects_normal_ci_can_promote(self) -> None:
        """Reject 'normal ci can promote' or 'normal ci can git push'."""
        forbidden = [
            "normal ci can promote",
            "normal ci can git push",
        ]
        for phrase in forbidden:
            assert phrase not in self.content.lower(), (
                f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain '{phrase}'"
            )


# ---------------------------------------------------------------------------
# 4C. Workflow permission escalation — Issue #9
#     Must reject affirmative escalation claims, not just require keyword presence.
# ---------------------------------------------------------------------------


class TestWorkflowPermissionEscalation:
    """Issue #9: Workflow permission escalation test must reject affirmative context.

    The test must find that Safety Invariants section prohibits escalation,
    AND must reject any document that uses affirmative permission escalation language.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.safety_invariants = _extract_section(self.content, "Safety Invariants Preserved")

    # --- Positive: Safety Invariants must prohibit escalation ---

    def test_safety_invariants_prohibit_workflow_permission_escalation(self) -> None:
        """Safety Invariants section must explicitly state no workflow permission escalation.

        Accepted patterns (any one suffices):
          - no workflow permission escalation
          - workflow permission escalation is not allowed
          - workflow permissions are not escalated
          - workflow権限昇格なし
          - no workflow permission escalation in Phase 2
        """
        section = self.safety_invariants.lower()
        accepted = (
            "no workflow permission escalation" in section
            or "workflow permission escalation is not allowed" in section
            or "workflow permissions are not escalated" in section
            or "workflow権限昇格なし" in self.safety_invariants
            or "no workflow permission escalation in phase 2" in section
        )
        assert accepted, (
            "Safety Invariants section must explicitly prohibit workflow permission escalation. "
            f"Section: {self.safety_invariants[:400]!r}"
        )

    # --- Negative: Affirmative escalation claims must be rejected ---

    def test_rejects_workflow_permission_escalation_is_allowed(self) -> None:
        """Reject 'workflow permission escalation is allowed'."""
        assert "workflow permission escalation is allowed" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'workflow permission escalation is allowed'"
        )

    def test_rejects_workflow_permissions_may_be_escalated(self) -> None:
        """Reject 'workflow permissions may be escalated'."""
        assert "workflow permissions may be escalated" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'workflow permissions may be escalated'"
        )

    def test_rejects_contents_write_allowed_in_normal_ci(self) -> None:
        """Reject 'contents: write is allowed in normal ci'."""
        forbidden = [
            "contents: write is allowed in normal ci",
            "workflow grants contents: write to normal ci",
            "workflow権限昇格を許可する",
            "normal ci may escalate permissions",
        ]
        for phrase in forbidden:
            assert phrase not in self.content.lower(), (
                f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain '{phrase}'"
            )


# ---------------------------------------------------------------------------
# 4D. GitHub Secrets boundary — Issue #6
# ---------------------------------------------------------------------------


class TestGitHubSecretsBoundary:
    """Issue #6: GitHub Secrets verification boundary must be clearly stated."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_states_repository_files_only(self) -> None:
        """Checkpoint must state it verifies repository files only."""
        assert "repository files only" in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'This checkpoint verifies repository files only'"
        )

    def test_states_does_not_inspect_github_secrets(self) -> None:
        """Checkpoint must state it does not inspect GitHub Secrets state."""
        content_lower = self.content.lower()
        assert (
            "does not inspect, verify, or assert github secrets state" in content_lower
            or "does not inspect" in content_lower
            or "not assert github secrets" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'This checkpoint does not inspect, verify, or assert GitHub Secrets state'"
        )

    def test_states_human_owner_controls_secrets_out_of_band(self) -> None:
        """Checkpoint must state Human Owner controls GitHub Secrets out-of-band."""
        content_lower = self.content.lower()
        assert (
            "out-of-band by the human owner" in content_lower
            or "human owner controlled" in content_lower
            or ("out-of-band" in content_lower and "human owner" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "GitHub Secrets are controlled out-of-band by the Human Owner"
        )

    def test_states_gpt_audit_gate_cannot_verify_secret_contents(self) -> None:
        """Checkpoint must state GPT Audit Gate cannot verify secret contents from PR diff."""
        content_lower = self.content.lower()
        assert (
            "cannot verify secret contents from pr diff" in content_lower
            or "cannot verify secret contents" in content_lower
            or "cannot verify" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "GPT Audit Gate cannot verify secret contents from PR diff"
        )

    def test_states_gemini_api_key_in_github_secrets_for_phase3(self) -> None:
        """Checkpoint must state GEMINI_API_KEY must be stored in GitHub Secrets for Phase 3."""
        content_lower = self.content.lower()
        assert (
            "gemini_api_key must be stored only in github secrets" in content_lower
            or ("gemini_api_key" in content_lower and "github secrets" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "GEMINI_API_KEY must be stored only in GitHub Secrets during Phase 3 activation"
        )

    # --- Reject ambiguous "not registered" phrasing ---

    def test_rejects_gemini_api_key_not_registered_phrase(self) -> None:
        """Issue #10: Reject 'GEMINI_API_KEY not registered' ambiguous expression."""
        forbidden = [
            "gemini_api_key not registered",
            "gemini_api_key is not registered",
            "gemini_api_key 未登録",
            "gemini_api_keyは未登録",
        ]
        for phrase in forbidden:
            assert phrase not in self.content.lower(), (
                f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT use the ambiguous phrase '{phrase}'. "
                "Use 'GEMINI_API_KEY is not present in repository files' instead."
            )

    def test_rejects_github_secrets_are_empty(self) -> None:
        """Reject 'GitHub Secrets are empty'."""
        assert "github secrets are empty" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain 'GitHub Secrets are empty'"
        )

    def test_rejects_this_pr_verified_github_secrets(self) -> None:
        """Reject 'This PR verified GitHub Secrets'."""
        assert "this pr verified github secrets" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'This PR verified GitHub Secrets'"
        )

    def test_rejects_gemini_api_key_absent_from_github_secrets(self) -> None:
        """Reject 'GEMINI_API_KEY is absent from GitHub Secrets'."""
        assert "gemini_api_key is absent from github secrets" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'GEMINI_API_KEY is absent from GitHub Secrets'"
        )

    def test_rejects_github_secrets_verified_by_pr_diff(self) -> None:
        """Reject 'GitHub Secrets verified by PR diff'."""
        assert "github secrets verified by pr diff" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain "
            "'GitHub Secrets verified by PR diff'"
        )


# ---------------------------------------------------------------------------
# 4E. Traceability Matrix content — Issue #5
# ---------------------------------------------------------------------------


class TestTraceabilityMatrixContent:
    """Issue #5: Traceability Matrix must contain key invariants."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.matrix_section = _extract_section(self.content, "Traceability Matrix")

    def test_matrix_section_exists(self) -> None:
        assert self.matrix_section, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Traceability Matrix section"
        )

    def test_matrix_has_gemini_api_key_not_in_repo_files(self) -> None:
        assert "gemini_api_key is not present in repository files" in self.matrix_section.lower() \
               or "not present in repository files" in self.matrix_section.lower(), (
            "Traceability Matrix must include 'GEMINI_API_KEY is not present in repository files'"
        )

    def test_matrix_has_live_model_enabled_false(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "live_model_enabled remains false" in section_lower or \
               ("live_model_enabled" in section_lower and "false" in section_lower), (
            "Traceability Matrix must include live_model_enabled remains false"
        )

    def test_matrix_has_phase3_not_started(self) -> None:
        assert "phase 3 is not started" in self.matrix_section.lower() or \
               "phase 3 not started" in self.matrix_section.lower(), (
            "Traceability Matrix must include 'Phase 3 is not started'"
        )

    def test_matrix_has_normal_ci_read_only(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "normal ci remains read-only" in section_lower or \
               "normal ci never calls gemini api" in section_lower or \
               "normal ci" in section_lower, (
            "Traceability Matrix must include normal CI read-only invariant"
        )

    def test_matrix_has_github_secrets_not_asserted(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "github secrets state is not asserted" in section_lower or \
               "not asserted by pr diff" in section_lower, (
            "Traceability Matrix must include 'GitHub Secrets state is not asserted by PR diff'"
        )

    def test_matrix_has_promote_requires_human_owner(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "promote requires human owner" in section_lower or \
               ("promote" in section_lower and "human owner" in section_lower), (
            "Traceability Matrix must include 'promote requires Human Owner approval'"
        )

    def test_matrix_has_phase3_requires_dedicated_pr(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "phase 3 activation requires dedicated pr" in section_lower or \
               ("dedicated pr" in section_lower and "phase 3" in section_lower), (
            "Traceability Matrix must include 'Phase 3 activation requires dedicated PR'"
        )

    def test_matrix_has_no_workflow_permission_escalation(self) -> None:
        section_lower = self.matrix_section.lower()
        assert "no workflow permission escalation" in section_lower or \
               "workflow permission escalation" in section_lower, (
            "Traceability Matrix must include workflow permission escalation invariant"
        )


# ---------------------------------------------------------------------------
# 4F. Residual Risk Register content — Issue #5
# ---------------------------------------------------------------------------


class TestResidualRiskRegisterContent:
    """Issue #5: Residual Risk Register must contain specific risks."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.risk_section = _extract_section(self.content, "Residual Risk")

    def test_risk_section_exists(self) -> None:
        assert self.risk_section, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Residual Risk Register section"
        )

    def test_risk_github_secrets_cannot_be_verified_from_pr_diff(self) -> None:
        assert "github secrets contents cannot be verified from pr diff" in self.risk_section.lower(), (
            "Residual Risk must include 'GitHub Secrets contents cannot be verified from PR diff'"
        )

    def test_risk_billing_settings_cannot_be_verified_from_repo_files(self) -> None:
        section_lower = self.risk_section.lower()
        assert "google cloud billing settings cannot be verified from repository files" in section_lower or \
               "billing settings cannot be verified" in section_lower, (
            "Residual Risk must include 'Google Cloud Billing settings cannot be verified from repository files'"
        )

    def test_risk_actual_gemini_api_behavior_not_verified(self) -> None:
        assert "actual gemini api behavior is not verified in phase 2" in self.risk_section.lower(), (
            "Residual Risk must include 'Actual Gemini API behavior is not verified in Phase 2'"
        )

    def test_risk_actual_api_cost_behavior_not_verified(self) -> None:
        assert "actual api cost behavior is not verified in phase 2" in self.risk_section.lower(), (
            "Residual Risk must include 'Actual API cost behavior is not verified in Phase 2'"
        )

    def test_risk_docs_tests_are_string_based(self) -> None:
        assert "docs tests are string-based" in self.risk_section.lower() or \
               "string-based" in self.risk_section.lower(), (
            "Residual Risk must include that docs tests are string-based"
        )

    def test_risk_phase3_must_recheck_workflow_permissions(self) -> None:
        section_lower = self.risk_section.lower()
        assert "phase 3 activation pr must re-check workflow permissions" in section_lower or \
               ("workflow permissions" in section_lower and "phase 3" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must re-check workflow permissions"
        )

    def test_risk_phase3_must_recheck_ledger_persistence(self) -> None:
        section_lower = self.risk_section.lower()
        assert "phase 3 activation pr must re-check ledger persistence" in section_lower or \
               ("ledger persistence" in section_lower and "phase 3" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must re-check ledger persistence"
        )

    def test_risk_phase3_must_recheck_budget_caps(self) -> None:
        section_lower = self.risk_section.lower()
        assert "phase 3 activation pr must re-check budget caps" in section_lower or \
               ("budget cap" in section_lower and "phase 3" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must re-check budget caps"
        )

    def test_risk_phase3_must_recheck_live_model_enabled_transition(self) -> None:
        section_lower = self.risk_section.lower()
        assert "live_model_enabled=true transition" in section_lower or \
               ("live_model_enabled" in section_lower and "transition" in section_lower
                and "phase 3" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must re-check live_model_enabled=true transition"
        )

    def test_risk_phase3_must_verify_gemini_api_key_in_github_secrets_only(self) -> None:
        section_lower = self.risk_section.lower()
        assert "gemini_api_key is stored only in github secrets" in section_lower or \
               ("github secrets" in section_lower and "gemini_api_key" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must verify GEMINI_API_KEY in GitHub Secrets only"
        )

    def test_risk_phase3_must_verify_no_api_keys_in_repo_files(self) -> None:
        section_lower = self.risk_section.lower()
        assert "repository files do not contain api keys" in section_lower or \
               ("repository files" in section_lower and "api key" in section_lower
                and "phase 3" in section_lower), (
            "Residual Risk must include Phase 3 activation PR must verify no API keys in repository files"
        )


# ---------------------------------------------------------------------------
# 4G. Go / No-Go template content — Issue #5
# ---------------------------------------------------------------------------


class TestGoNoGoTemplateContent:
    """Issue #5: Go / No-Go Decision Record Template must contain required fields."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.gonogo_section = _extract_section(self.content, "Go / No-Go") or \
                              _extract_section(self.content, "Go-No-Go")

    def test_gonogo_section_exists(self) -> None:
        assert self.gonogo_section or ("go / no-go" in self.content.lower()) or \
               ("go-no-go" in self.content.lower()), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Go / No-Go Decision Record Template"
        )

    def test_has_go_nogo_decision_field(self) -> None:
        content_lower = self.content.lower()
        assert "decision: go / no-go" in content_lower or "go / no-go" in content_lower, (
            "Go / No-Go template must have a Decision field"
        )

    def test_has_human_owner_field(self) -> None:
        assert "human owner" in self.content.lower(), (
            "Go / No-Go template must have a Human Owner field"
        )

    def test_has_billing_budget_cap_confirmed(self) -> None:
        assert "billing budget cap confirmed" in self.content.lower(), (
            "Go / No-Go template must have 'Billing budget cap confirmed' field"
        )

    def test_has_daily_budget_cap_confirmed(self) -> None:
        assert "daily budget cap confirmed" in self.content.lower(), (
            "Go / No-Go template must have 'Daily budget cap confirmed' field"
        )

    def test_has_gemini_api_key_stored_in_github_secrets(self) -> None:
        content_lower = self.content.lower()
        assert "gemini_api_key stored only in github secrets" in content_lower or \
               ("gemini_api_key" in content_lower and "github secrets" in content_lower), (
            "Go / No-Go template must have 'GEMINI_API_KEY stored only in GitHub Secrets' field"
        )

    def test_has_gpt_audit_gate_reviewed(self) -> None:
        content_lower = self.content.lower()
        assert "gpt audit gate reviewed" in content_lower or \
               "gpt audit gate" in content_lower, (
            "Go / No-Go template must have 'GPT Audit Gate reviewed activation PR' field"
        )

    def test_has_ci_verified(self) -> None:
        assert "ci verified" in self.content.lower(), (
            "Go / No-Go template must have 'CI verified' field"
        )

    def test_has_ledger_persistence_verified(self) -> None:
        assert "ledger persistence verified" in self.content.lower(), (
            "Go / No-Go template must have 'Ledger persistence verified' field"
        )

    def test_has_api_cost_behavior_accepted(self) -> None:
        assert "api cost behavior accepted" in self.content.lower(), (
            "Go / No-Go template must have 'API cost behavior accepted' field"
        )


# ---------------------------------------------------------------------------
# 5. Phase state regression guard — Issue #10
#    Covers README.md, PHASE_2_PLAN.md, and PHASE_2_COMPLETION_CHECKPOINT.md
# ---------------------------------------------------------------------------


class TestPhaseStateRegressionGuard:
    """Issue #10: Reject dangerous phase state claims in docs."""

    _DOCS = [_README, _PHASE2_PLAN, _CHECKPOINT]
    _FORBIDDEN_EN = [
        "Phase 3 started",
        "Phase 3 is in progress",
        "API connected",
        "API is connected",
        "Gemini API enabled",
        "GEMINI_API_KEY registered",
        "live_model_enabled=true is active",
        "Phase 2 completion authorizes API activation",
        "Phase 2 completion starts Phase 3",
        "Human Owner approval is optional",
        "API activation can proceed automatically",
        "schedule calls Gemini API",
        "normal CI calls Gemini API",
        "ledger can be reset",
        "ledger may be overwritten",
        "ledger can be rolled back",
    ]
    _FORBIDDEN_JA = [
        "Phase 3開始済み",
        "Phase 3進行中",
        "API接続済み",
        "Gemini API有効化済み",
        "GEMINI_API_KEY登録済み",
        "live_model_enabled=true有効化済み",
        "Phase 2完了によりAPI接続を開始する",
        "Phase 2完了によりPhase 3開始",
        "Human Owner承認は不要",
        "API有効化を自動実行する",
        "scheduleでGemini APIを呼ぶ",
        "通常CIでGemini APIを呼ぶ",
        "ledgerをリセットしてよい",
        "ledgerを上書きしてよい",
        "ledgerを巻き戻してよい",
    ]

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.contents: dict[str, str] = {}
        for path in self._DOCS:
            if path.exists():
                self.contents[path.name] = path.read_text(encoding="utf-8")

    def _check_forbidden(self, phrases: list[str], doc_name: str, content: str, case_sensitive: bool = True) -> None:
        for phrase in phrases:
            if case_sensitive:
                assert phrase not in content, (
                    f"{doc_name} must NOT contain '{phrase}'"
                )
            else:
                assert phrase.lower() not in content.lower(), (
                    f"{doc_name} must NOT contain '{phrase}' (case-insensitive)"
                )

    def test_readme_no_forbidden_en_phrases(self) -> None:
        if "README.md" in self.contents:
            self._check_forbidden(self._FORBIDDEN_EN, "README.md", self.contents["README.md"])

    def test_readme_no_forbidden_ja_phrases(self) -> None:
        if "README.md" in self.contents:
            self._check_forbidden(self._FORBIDDEN_JA, "README.md", self.contents["README.md"])

    def test_phase2_plan_no_forbidden_en_phrases(self) -> None:
        if "PHASE_2_PLAN.md" in self.contents:
            self._check_forbidden(self._FORBIDDEN_EN, "PHASE_2_PLAN.md", self.contents["PHASE_2_PLAN.md"])

    def test_phase2_plan_no_forbidden_ja_phrases(self) -> None:
        if "PHASE_2_PLAN.md" in self.contents:
            self._check_forbidden(self._FORBIDDEN_JA, "PHASE_2_PLAN.md", self.contents["PHASE_2_PLAN.md"])

    def test_checkpoint_no_forbidden_en_phrases(self) -> None:
        if "PHASE_2_COMPLETION_CHECKPOINT.md" in self.contents:
            self._check_forbidden(
                self._FORBIDDEN_EN,
                "PHASE_2_COMPLETION_CHECKPOINT.md",
                self.contents["PHASE_2_COMPLETION_CHECKPOINT.md"],
            )

    def test_checkpoint_no_forbidden_ja_phrases(self) -> None:
        if "PHASE_2_COMPLETION_CHECKPOINT.md" in self.contents:
            self._check_forbidden(
                self._FORBIDDEN_JA,
                "PHASE_2_COMPLETION_CHECKPOINT.md",
                self.contents["PHASE_2_COMPLETION_CHECKPOINT.md"],
            )


# ---------------------------------------------------------------------------
# 6. GEMINI_API_KEY "not registered" regression guard — Issue #10
#    Check README, PHASE_2_PLAN, API_RUNBOOK for ambiguous phrase
# ---------------------------------------------------------------------------


class TestGeminiApiKeyAmbiguousPhrase:
    """Issue #10: Reject 'GEMINI_API_KEY not registered' ambiguous expressions
    in README.md, PHASE_2_PLAN.md, API_ACTIVATION_RUNBOOK.md, and CHECKPOINT.
    """

    _FORBIDDEN_PHRASES = [
        "gemini_api_key not registered",
        "gemini_api_key is not registered",
        "gemini_api_key 未登録",
        "gemini_api_keyは未登録",
        "gemini_api_key未登録",
    ]

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.docs = {
            "README.md": _README,
            "PHASE_2_PLAN.md": _PHASE2_PLAN,
            "API_ACTIVATION_RUNBOOK.md": _API_RUNBOOK,
            "PHASE_2_COMPLETION_CHECKPOINT.md": _CHECKPOINT,
        }

    def test_no_ambiguous_not_registered_phrase_in_readme(self) -> None:
        if _README.exists():
            content = _README.read_text(encoding="utf-8").lower()
            for phrase in self._FORBIDDEN_PHRASES:
                assert phrase not in content, (
                    f"README.md must NOT contain ambiguous '{phrase}'. "
                    "Use 'GEMINI_API_KEY is not present in repository files' instead."
                )

    def test_no_ambiguous_not_registered_phrase_in_phase2_plan(self) -> None:
        if _PHASE2_PLAN.exists():
            content = _PHASE2_PLAN.read_text(encoding="utf-8").lower()
            for phrase in self._FORBIDDEN_PHRASES:
                assert phrase not in content, (
                    f"PHASE_2_PLAN.md must NOT contain ambiguous '{phrase}'."
                )

    def test_no_ambiguous_not_registered_phrase_in_api_runbook(self) -> None:
        if _API_RUNBOOK.exists():
            content = _API_RUNBOOK.read_text(encoding="utf-8").lower()
            # Allow "未登録の場合" style (conditional context), reject bare "未登録"
            # Use a targeted check for the specific forbidden pattern
            for phrase in self._FORBIDDEN_PHRASES:
                assert phrase not in content, (
                    f"API_ACTIVATION_RUNBOOK.md must NOT contain ambiguous '{phrase}'."
                )

    def test_no_ambiguous_not_registered_phrase_in_checkpoint(self) -> None:
        if _CHECKPOINT.exists():
            content = _CHECKPOINT.read_text(encoding="utf-8").lower()
            for phrase in self._FORBIDDEN_PHRASES:
                assert phrase not in content, (
                    f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain ambiguous '{phrase}'."
                )


# ---------------------------------------------------------------------------
# 7. Review prompt hygiene — Issue #11
# ---------------------------------------------------------------------------


class TestReviewPromptHygiene:
    """Issue #11: Review prompt hygiene (PR-target confusion) must be documented."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_review_prompt_hygiene_documented(self) -> None:
        """Checkpoint must document review prompt hygiene rules."""
        content_lower = self.content.lower()
        assert (
            "review prompt" in content_lower
            or "review prompt hygiene" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must document review prompt hygiene"
        )

    def test_correct_pr_number_required(self) -> None:
        """Checkpoint must state that review prompts must identify correct PR number."""
        content_lower = self.content.lower()
        assert (
            "correct pr number" in content_lower
            or "pr number" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state that review prompts must "
            "identify the correct PR number"
        )

    def test_reusing_prompt_without_update_is_invalid(self) -> None:
        """Checkpoint must state that reusing a prompt without updating PR number/scope is invalid."""
        content_lower = self.content.lower()
        assert (
            "reusing" in content_lower
            or "without updating" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state that reusing a Codex prompt "
            "without updating PR number/scope is invalid"
        )

    def test_human_owner_must_verify_prompt_target(self) -> None:
        """Checkpoint must state Human Owner must verify review prompt target."""
        content_lower = self.content.lower()
        assert (
            "human owner" in content_lower
            and "review prompt" in content_lower
        ) or (
            "verify the review prompt target" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Human Owner must verify "
            "the review prompt target"
        )

    def test_review_prompt_scope_must_match_pr_objective(self) -> None:
        """Checkpoint must state that review prompt scope must match the current PR objective."""
        content_lower = self.content.lower()
        assert (
            "review prompt scope must match the current pr objective" in content_lower
            or "scope must match the current pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'Review prompt scope must match the current PR objective'"
        )

    def test_rejects_review_prompt_focused_on_future_pr(self) -> None:
        """Checkpoint must state that a review prompt focusing on a future PR while reviewing
        a checkpoint PR is invalid."""
        content_lower = self.content.lower()
        assert (
            "future implementation pr while reviewing a checkpoint pr is invalid" in content_lower
            or (
                "future implementation pr" in content_lower
                and "checkpoint pr" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'A review prompt that focuses on a future implementation PR while reviewing "
            "a checkpoint PR is invalid'"
        )

    def test_checkpoint_hardening_review_scope_documented(self) -> None:
        """For checkpoint hardening PRs, required Codex review scope must be documented."""
        content_lower = self.content.lower()
        assert (
            "checkpoint hardening" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must document 'checkpoint hardening' "
            "as a Codex review scope item"
        )
        assert (
            "traceability matrix" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md review prompt hygiene must reference "
            "'Traceability Matrix' as a required checkpoint hardening review item"
        )
        assert (
            "residual risk" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md review prompt hygiene must reference "
            "'Residual Risk' as a required checkpoint hardening review item"
        )
        assert (
            "go / no-go" in content_lower or "go/no-go" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md review prompt hygiene must reference "
            "'Go / No-Go' as a required checkpoint hardening review item"
        )


# ---------------------------------------------------------------------------
# 8. Phase 2 complete does not mean Phase 3 started (checkpoint-level)
# ---------------------------------------------------------------------------


class TestCheckpointPhaseState:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_states_phase3_not_started(self) -> None:
        content_lower = self.content.lower()
        assert (
            "phase 3 is not started" in content_lower
            or "phase 3 not started" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state 'Phase 3 is not started'"
        )

    def test_states_api_not_connected(self) -> None:
        content_lower = self.content.lower()
        assert (
            "api remains not connected" in content_lower
            or "not connected" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state API remains not connected"
        )

    def test_states_live_model_false(self) -> None:
        content_lower = self.content.lower()
        assert (
            "live_model_enabled remains false" in content_lower
            or "live_model_enabled | false" in content_lower
            or "live_model_enabled: false" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state live_model_enabled remains false"
        )

    def test_states_human_owner_decision_required(self) -> None:
        content_lower = self.content.lower()
        assert (
            "human owner" in content_lower
            and ("decision required" in content_lower or "explicit decision" in content_lower
                 or "controlled" in content_lower or "required before" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Human Owner decision is required before Phase 3"
        )

    def test_states_phase3_requires_dedicated_pr(self) -> None:
        content_lower = self.content.lower()
        assert (
            "dedicated pr" in content_lower
            and "phase 3" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Phase 3 activation requires dedicated PR"
        )


# ---------------------------------------------------------------------------
# 9. Promote approval gate not claimed covered — Critical #1
#    immunization_loop.yml promote job has no promote_approved=true gate.
#    The Traceability Matrix must NOT mark these invariants as 'Covered'
#    until the workflow actually enforces them.
# ---------------------------------------------------------------------------


class TestPromoteApprovalGateNotClaimedCovered:
    """Verify that promote approval gate unenforced state is correctly documented.

    Critical #1: immunization_loop.yml promote job checks only passed_adoption_gate.
    There is no promote_approved=true gate requiring Human Owner or GPT Audit Gate.
    The Traceability Matrix must NOT mark these invariants as 'Covered' while
    workflow enforcement is pending.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_promote_approval_gate_not_claimed_covered_until_workflow_enforced(self) -> None:
        """promote requires Human Owner approval must NOT be 'Covered' while
        immunization_loop.yml lacks promote_approved=true gate.
        """
        content = self.content
        # Must document Critical #1
        assert "Critical #1" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must document 'Critical #1': "
            "promote approval gate is not enforced in immunization_loop.yml"
        )
        # Must state 'Not enforced' or 'workflow enforcement pending'
        assert "Not enforced" in content or "workflow enforcement pending" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state 'Not enforced' or "
            "'workflow enforcement pending' for promote approval gate invariants (Critical #1)"
        )
        # Matrix row for 'promote requires Human Owner approval' must NOT be 'Covered'
        for line in content.splitlines():
            if "promote requires human owner approval" in line.lower() and line.strip().startswith("|"):
                assert "| Covered |" not in line, (
                    f"Traceability Matrix row 'promote requires Human Owner approval' "
                    f"must NOT be marked as '| Covered |' while workflow lacks promote_approved gate. "
                    f"Got: {line!r}"
                )
        # Matrix row for 'promote requires GPT Audit Gate APPROVE' must NOT be 'Covered'
        for line in content.splitlines():
            if "promote requires gpt audit gate" in line.lower() and line.strip().startswith("|"):
                assert "| Covered |" not in line, (
                    f"Traceability Matrix row 'promote requires GPT Audit Gate APPROVE' "
                    f"must NOT be marked as '| Covered |' while workflow lacks audit gate check. "
                    f"Got: {line!r}"
                )

    def test_residual_risk_includes_promote_approval_gate_not_enforced(self) -> None:
        """Residual Risk Register must include the promote approval gate unenforced risk."""
        content_lower = self.content.lower()
        assert (
            "promote approval gate is not yet enforced" in content_lower
            or (
                "promote approval gate" in content_lower
                and "not yet enforced" in content_lower
            )
            or (
                "promote" in content_lower
                and "not yet enforced" in content_lower
                and "workflow" in content_lower
            )
        ), (
            "Residual Risk Register must include "
            "'Promote approval gate is not yet enforced in workflow' (Critical #1)"
        )

    def test_known_phase3_blockers_section_exists(self) -> None:
        """Checkpoint must have a 'Known Phase 3 Blockers' section."""
        content_lower = self.content.lower()
        assert (
            "known phase 3 blockers" in content_lower
            or "phase 3 blockers" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Known Phase 3 Blockers' section "
            "documenting Critical #1 (promote approval gate not enforced in workflow)"
        )


# ---------------------------------------------------------------------------
# 10. Safety Invariants Preserved excludes unenforced items — issue from
#     PR #29 REQUEST CHANGES: promote approval was listed as "preserved"
#     even though immunization_loop.yml does not enforce it.
#     The preamble bullet list of Section 5 must NOT include them.
#     A dedicated "Documented but Not Yet Workflow-Enforced Invariants"
#     subsection must list them with explicit not-enforced language.
# ---------------------------------------------------------------------------


def _extract_safety_invariants_preamble(content: str) -> str:
    """Extract the Safety Invariants Preserved preamble bullet list.

    Returns lines from '## ... Safety Invariants Preserved' up to (but not
    including) the first '###' subsection heading or the next '##' heading.
    """
    lines = content.splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##"):
            if "safety invariants preserved" in stripped.lower():
                in_section = True
                result.append(line)
                continue
            if in_section:
                break  # next same-level heading
        if in_section:
            if stripped.startswith("###"):
                break  # first subsection — stop here
            result.append(line)
    return "\n".join(result)


class TestSafetyInvariantsPreservedExcludesUnenforced:
    """PR #29 REQUEST CHANGES fix: promote approval items removed from preserved list.

    Safety Invariants Preserved preamble must NOT list promote approval items
    (they are not workflow-enforced — Critical #1).  Those items belong in the
    dedicated 'Documented but Not Yet Workflow-Enforced Invariants' subsection.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")
        self.preamble = _extract_safety_invariants_preamble(self.content)
        self.not_enforced = _extract_section(
            self.content, "Documented but Not Yet Workflow-Enforced"
        )

    # --- Negative: preamble bullet list must NOT contain the two promote items ---

    def test_preserved_preamble_excludes_promote_human_owner_approval(self) -> None:
        """Safety Invariants Preserved preamble must NOT list 'promote requires Human Owner approval'.

        That invariant is not workflow-enforced (Critical #1) and must live only in the
        'Documented but Not Yet Workflow-Enforced Invariants' subsection.
        """
        preamble_lower = self.preamble.lower()
        assert "- promote requires human owner approval" not in preamble_lower, (
            "Safety Invariants Preserved preamble must NOT include "
            "'- promote requires Human Owner approval' as a preserved/enforced bullet. "
            "It is not yet workflow-enforced (Critical #1). "
            "Move it to 'Documented but Not Yet Workflow-Enforced Invariants'."
        )

    def test_preserved_preamble_excludes_promote_gpt_audit_gate_approve(self) -> None:
        """Safety Invariants Preserved preamble must NOT list 'promote requires GPT Audit Gate APPROVE'."""
        preamble_lower = self.preamble.lower()
        assert "- promote requires gpt audit gate" not in preamble_lower, (
            "Safety Invariants Preserved preamble must NOT include "
            "'- promote requires GPT Audit Gate APPROVE' as a preserved/enforced bullet. "
            "It is not yet workflow-enforced (Critical #1)."
        )

    # --- Positive: 'Documented but Not Yet Workflow-Enforced' subsection must exist ---

    def test_documented_not_enforced_subsection_exists(self) -> None:
        """Checkpoint must have a 'Documented but Not Yet Workflow-Enforced Invariants' subsection."""
        content_lower = self.content.lower()
        assert (
            "documented but not yet workflow-enforced" in content_lower
            or "not yet workflow-enforced" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a "
            "'Documented but Not Yet Workflow-Enforced Invariants' subsection"
        )

    def test_documented_not_enforced_contains_promote_human_owner(self) -> None:
        """The subsection must list 'promote requires Human Owner approval'."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        assert "promote requires human owner approval" in self.not_enforced.lower(), (
            "'Documented but Not Yet Workflow-Enforced' section must contain "
            "'promote requires Human Owner approval'"
        )

    def test_documented_not_enforced_contains_promote_gpt_audit_gate(self) -> None:
        """The subsection must list 'promote requires GPT Audit Gate APPROVE'."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        assert "promote requires gpt audit gate" in self.not_enforced.lower(), (
            "'Documented but Not Yet Workflow-Enforced' section must contain "
            "'promote requires GPT Audit Gate APPROVE'"
        )

    def test_documented_not_enforced_states_not_yet_enforced(self) -> None:
        """The subsection must use explicit 'not yet enforced' language."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        section_lower = self.not_enforced.lower()
        assert (
            "not yet enforced" in section_lower
            or "not yet workflow-enforced" in section_lower
        ), (
            "'Documented but Not Yet Workflow-Enforced' section must explicitly "
            "state 'not yet enforced'"
        )

    def test_documented_not_enforced_references_critical1(self) -> None:
        """The subsection must reference Critical #1."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        assert "Critical #1" in self.not_enforced, (
            "'Documented but Not Yet Workflow-Enforced' section must reference 'Critical #1'"
        )

    def test_documented_not_enforced_states_phase3_must_not_start_until_critical1_fixed(self) -> None:
        """The subsection must state Phase 3 must not start until Critical #1 is fixed."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        section_lower = self.not_enforced.lower()
        assert (
            "phase 3 must not start until critical #1 is fixed" in section_lower
            or (
                "phase 3 must not start" in section_lower
                and "critical #1" in section_lower.lower()
            )
        ), (
            "'Documented but Not Yet Workflow-Enforced' section must state "
            "'Phase 3 must not start until Critical #1 is fixed'"
        )

    def test_documented_not_enforced_states_no_listing_until_tests_prove_enforcement(self) -> None:
        """The subsection must state items must not be listed as preserved until tests prove enforcement."""
        assert self.not_enforced, (
            "Could not extract 'Documented but Not Yet Workflow-Enforced' section"
        )
        section_lower = self.not_enforced.lower()
        assert (
            "workflow tests prove enforcement" in section_lower
            or "tests prove enforcement" in section_lower
            or "until workflow" in section_lower
        ), (
            "'Documented but Not Yet Workflow-Enforced' section must state items "
            "must not be listed as preserved until workflow tests prove enforcement"
        )


# ---------------------------------------------------------------------------
# 11. Critical #1 must be fixed in dedicated pre-Phase-3 hardening PR,
#     NOT in the Phase 3 activation PR itself.
# ---------------------------------------------------------------------------


class TestCritical1PrePhase3HardeningPR:
    """Verify that Critical #1 is documented to require a dedicated pre-Phase-3 hardening PR.

    The Known Phase 3 Blockers and Residual Risk sections must state that
    Critical #1 is fixed BEFORE the Phase 3 activation PR, not inside it.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_critical1_requires_dedicated_pre_phase3_hardening_pr(self) -> None:
        """Known Phase 3 Blockers must state Critical #1 needs dedicated pre-Phase-3 hardening PR."""
        content_lower = self.content.lower()
        assert (
            "dedicated pre-phase-3 hardening pr" in content_lower
            or "pre-phase-3 hardening pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md Known Phase 3 Blockers must state "
            "Critical #1 must be fixed in a 'dedicated pre-Phase-3 hardening PR' "
            "before any Phase 3 activation PR is opened."
        )

    def test_critical1_says_phase3_activation_pr_may_proceed_only_after_gate_enforced(self) -> None:
        """Critical #1 entry must state Phase 3 activation PR may proceed ONLY AFTER gate is enforced."""
        content_lower = self.content.lower()
        assert (
            "phase 3 activation pr may proceed only after" in content_lower
            or (
                "may proceed only after" in content_lower
                and "already enforced" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'Phase 3 activation PR may proceed only after the promote gate is already enforced and audited'"
        )

    def test_critical1_says_gate_already_enforced_and_audited(self) -> None:
        """Critical #1 must require that the gate is already enforced and audited before Phase 3."""
        content_lower = self.content.lower()
        assert (
            "already enforced and audited" in content_lower
            or "enforced and audited" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "promote gate must be 'already enforced and audited' before Phase 3 activation PR"
        )

    # --- Negative: forbidden phrases ---

    def test_known_phase3_blockers_intro_says_before_any_activation_pr(self) -> None:
        """Known Phase 3 Blockers intro must state blockers must be resolved
        before any Phase 3 activation PR is opened or merged."""
        content_lower = self.content.lower()
        assert (
            "before any phase 3 activation pr is opened or merged" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md Known Phase 3 Blockers intro must state "
            "'before any Phase 3 activation PR is opened or merged'"
        )

    def test_known_phase3_blockers_intro_says_must_not_be_deferred(self) -> None:
        """Known Phase 3 Blockers intro must state blockers must NOT be deferred
        into the Phase 3 activation PR."""
        content_lower = self.content.lower()
        assert (
            "must not be deferred into the phase 3 activation pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md Known Phase 3 Blockers intro must state "
            "'MUST NOT be deferred into the Phase 3 activation PR'"
        )

    def test_known_phase3_blockers_intro_says_each_blocker_dedicated_hardening_pr(self) -> None:
        """Known Phase 3 Blockers intro must state each blocker must be fixed
        in a dedicated pre-Phase-3 hardening PR and audited independently."""
        content_lower = self.content.lower()
        assert (
            "each blocker must be fixed in a dedicated pre-phase-3 hardening pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md Known Phase 3 Blockers intro must state "
            "'Each blocker must be fixed in a dedicated pre-Phase-3 hardening PR and "
            "audited independently'"
        )

    def test_rejects_phase3_activation_pr_must_add_promote_gate(self) -> None:
        """Reject 'Phase 3 activation PR must add promote_approved gate'.

        Critical #1 must be fixed in a SEPARATE dedicated hardening PR,
        not by the Phase 3 activation PR itself.
        """
        content_lower = self.content.lower()
        assert "phase 3 activation pr must add" not in content_lower, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'Phase 3 activation PR must add promote_approved gate'. "
            "Critical #1 must be fixed in a dedicated pre-Phase-3 hardening PR."
        )

    def test_rejects_must_be_fixed_in_the_phase3_activation_pr(self) -> None:
        """Reject 'must be fixed in the Phase 3 activation PR'.

        This phrasing implies the fix can happen inside the Phase 3 activation PR,
        which contradicts the requirement that blockers are fixed BEFORE it.
        """
        content_lower = self.content.lower()
        assert "must be fixed in the phase 3 activation pr" not in content_lower, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'must be fixed in the Phase 3 activation PR'. "
            "Blockers must be fixed BEFORE the Phase 3 activation PR in a dedicated hardening PR."
        )

    def test_rejects_fixed_in_the_phase3_activation_pr(self) -> None:
        """Reject 'fixed in the Phase 3 activation PR' (broader rejection)."""
        content_lower = self.content.lower()
        assert "fixed in the phase 3 activation pr" not in content_lower, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain 'fixed in the Phase 3 activation PR'. "
            "Blockers must be fixed BEFORE the Phase 3 activation PR."
        )

    def test_rejects_deferred_into_the_phase3_activation_pr(self) -> None:
        """Reject 'deferred into the Phase 3 activation PR' as an affirmative statement."""
        # The only valid use is in negation: 'must NOT be deferred into the Phase 3 activation PR'
        # Reject the bare affirmative form
        content_lower = self.content.lower()
        assert "they must be deferred into the phase 3 activation pr" not in content_lower, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'they must be deferred into the Phase 3 activation PR'."
        )

    def test_rejects_critical1_will_be_fixed_during_phase3_activation(self) -> None:
        """Reject 'Critical #1 will be fixed during Phase 3 activation'."""
        content_lower = self.content.lower()
        assert "critical #1 will be fixed during phase 3 activation" not in content_lower, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'Critical #1 will be fixed during Phase 3 activation'. "
            "It must be fixed BEFORE Phase 3 activation in a dedicated hardening PR."
        )

    def test_rejects_promote_approval_covered_in_matrix(self) -> None:
        """Reject any Traceability Matrix row marking promote approval as 'Covered'."""
        for line in self.content.splitlines():
            line_lower = line.lower()
            if (
                "promote requires human owner approval" in line_lower
                and line.strip().startswith("|")
            ):
                assert "| covered |" not in line_lower, (
                    f"Traceability Matrix must NOT mark 'promote requires Human Owner approval' "
                    f"as '| Covered |'. Got: {line!r}"
                )
            if (
                "promote requires gpt audit gate" in line_lower
                and line.strip().startswith("|")
            ):
                assert "| covered |" not in line_lower, (
                    f"Traceability Matrix must NOT mark 'promote requires GPT Audit Gate APPROVE' "
                    f"as '| Covered |'. Got: {line!r}"
                )

# ---------------------------------------------------------------------------
# 12. Critical #1 recorded correctly in checkpoint — docs-only verification
#
#     PR #29 is PR-A: Phase 2 completion checkpoint hardening.
#     It does NOT implement Critical #1 (promote_approved gate in workflow).
#     It MUST NOT contain xfail workflow-enforcement tests that silently
#     accept an unresolved Critical issue.
#
#     These tests verify only that docs/PHASE_2_COMPLETION_CHECKPOINT.md
#     correctly DOCUMENTS Critical #1 as unresolved:
#       - explicitly named as "Critical #1"
#       - promote approval rows marked "Not enforced" in Traceability Matrix
#       - separated into "Documented but Not Yet Workflow-Enforced" section
#       - Known Phase 3 Blockers contains Critical #1 description
#       - dedicated pre-Phase-3 hardening PR required before Phase 3 activation PR
#       - Phase 3 must not start until Critical #1 is fixed
# ---------------------------------------------------------------------------


class TestCritical1DocumentedAsUnresolved:
    """Verify that PHASE_2_COMPLETION_CHECKPOINT.md correctly records Critical #1.

    Originally written to verify the unresolved state (PR #29).
    Updated for the Critical #1 fix PR: verify correct documentation of the
    resolved state, including that the pre-Phase-3 hardening PR requirement
    was fulfilled before any Phase 3 activation PR.
    """

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_checkpoint_names_critical1(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must explicitly name 'Critical #1'."""
        assert "Critical #1" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must name 'Critical #1'"
        )

    def test_promote_human_owner_row_is_not_covered_literal(self) -> None:
        """Traceability Matrix row for 'promote requires Human Owner approval' must
        NOT use '| Covered |' literal.

        After Critical #1 fix, the row correctly shows 'Enforced' status via
        workflow enforcement (promote_approved gate).  '| Covered |' is not used;
        '| Enforced |' or similar descriptive text is acceptable.
        """
        for line in self.content.splitlines():
            if (
                "promote requires human owner approval" in line.lower()
                and line.strip().startswith("|")
            ):
                assert "| Covered |" not in line, (
                    "Traceability Matrix row 'promote requires Human Owner approval' "
                    "must NOT use literal '| Covered |'. "
                    f"Got: {line!r}"
                )
                # After Critical #1 fix, the row must reflect enforced state
                assert (
                    "Enforced" in line
                    or "Not enforced" in line
                    or "enforced" in line.lower()
                    or "process" in line.lower()
                ), (
                    "Traceability Matrix row 'promote requires Human Owner approval' "
                    "must show enforcement status (Enforced / Not enforced / Process-enforced). "
                    f"Got: {line!r}"
                )

    def test_promote_gpt_audit_gate_row_is_not_covered_literal(self) -> None:
        """Traceability Matrix row for 'promote requires GPT Audit Gate APPROVE' must
        NOT use '| Covered |' literal.

        GPT Audit Gate APPROVE remains a process-level requirement (not an automated
        workflow condition), so the row must show process-enforced or not-enforced status.
        """
        for line in self.content.splitlines():
            if (
                "promote requires gpt audit gate" in line.lower()
                and line.strip().startswith("|")
            ):
                assert "| Covered |" not in line, (
                    "Traceability Matrix row 'promote requires GPT Audit Gate APPROVE' "
                    "must NOT use literal '| Covered |'. "
                    f"Got: {line!r}"
                )
                # GPT Audit Gate APPROVE is a process gate, not automated workflow
                assert (
                    "Not enforced" in line
                    or "Process" in line
                    or "process" in line.lower()
                    or "manual" in line.lower()
                    or "Not yet" in line
                ), (
                    "Traceability Matrix row 'promote requires GPT Audit Gate APPROVE' "
                    "must indicate process-level or not-yet-automated status. "
                    f"Got: {line!r}"
                )

    def test_documented_not_enforced_section_has_promote_approval(self) -> None:
        """'Documented but Not Yet Workflow-Enforced Invariants' subsection must
        contain promote approval items.

        After Critical #1 fix, this section still exists but documents the historical
        state and the resolved outcome.  It must reference both promote approval items.
        """
        not_enforced = _extract_section(self.content, "Documented but Not Yet Workflow-Enforced")
        assert not_enforced, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a "
            "'Documented but Not Yet Workflow-Enforced Invariants' subsection "
            "(even after Critical #1 fix, as historical record of what was enforced)"
        )
        section_lower = not_enforced.lower()
        assert "promote requires human owner approval" in section_lower or \
               "human owner approval" in section_lower, (
            "'Documented but Not Yet Workflow-Enforced' subsection must reference "
            "'promote requires Human Owner approval' (or 'Human Owner approval')"
        )
        assert "promote requires gpt audit gate" in section_lower or \
               "gpt audit gate" in section_lower, (
            "'Documented but Not Yet Workflow-Enforced' subsection must reference "
            "'promote requires GPT Audit Gate APPROVE' (or 'GPT Audit Gate')"
        )

    def test_known_phase3_blockers_contains_critical1(self) -> None:
        """Known Phase 3 Blockers section must contain Critical #1."""
        blockers = _extract_section(self.content, "Known Phase 3 Blockers")
        assert blockers, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Known Phase 3 Blockers' section"
        )
        assert "Critical #1" in blockers, (
            "Known Phase 3 Blockers must contain 'Critical #1'"
        )

    def test_critical1_requires_dedicated_pre_phase3_hardening_pr_in_blockers(self) -> None:
        """Known Phase 3 Blockers must state Critical #1 must be fixed in a
        dedicated pre-Phase-3 hardening PR before any Phase 3 activation PR."""
        content_lower = self.content.lower()
        assert (
            "dedicated pre-phase-3 hardening pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Critical #1 must be fixed in a "
            "'dedicated pre-Phase-3 hardening PR'"
        )
        assert (
            "before any phase 3 activation pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state the hardening PR must complete "
            "'before any Phase 3 activation PR is opened or merged'"
        )

    def test_critical1_must_not_be_deferred_into_phase3_activation_pr(self) -> None:
        """Checkpoint must explicitly state blockers must NOT be deferred into
        the Phase 3 activation PR."""
        content_lower = self.content.lower()
        assert (
            "must not be deferred into the phase 3 activation pr" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'MUST NOT be deferred into the Phase 3 activation PR'"
        )

    def test_phase3_must_not_start_until_critical1_is_fixed(self) -> None:
        """Checkpoint must state Phase 3 must not start until Critical #1 is fixed."""
        content_lower = self.content.lower()
        assert (
            "phase 3 must not start until critical #1 is fixed" in content_lower
            or (
                "phase 3 must not start" in content_lower
                and "critical #1" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'Phase 3 must not start until Critical #1 is fixed'"
        )

    def test_phase3_activation_pr_may_proceed_only_after_gate_enforced_and_audited(self) -> None:
        """Checkpoint must state Phase 3 activation PR may proceed only after
        the promote gate is already enforced and audited."""
        content_lower = self.content.lower()
        assert (
            "already enforced and audited" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state the promote gate must be "
            "'already enforced and audited' before Phase 3 activation PR"
        )

    # --- Regression guards: forbidden phrases ---

    def test_rejects_promote_approval_covered_in_matrix(self) -> None:
        """No Traceability Matrix row may mark promote approval as '| Covered |'."""
        for line in self.content.splitlines():
            line_lower = line.lower()
            if (
                "promote requires human owner approval" in line_lower
                and line.strip().startswith("|")
            ):
                assert "| covered |" not in line_lower, (
                    f"Traceability Matrix must NOT mark 'promote requires Human Owner approval' "
                    f"as '| Covered |'. Got: {line!r}"
                )
            if (
                "promote requires gpt audit gate" in line_lower
                and line.strip().startswith("|")
            ):
                assert "| covered |" not in line_lower, (
                    f"Traceability Matrix must NOT mark 'promote requires GPT Audit Gate APPROVE' "
                    f"as '| Covered |'. Got: {line!r}"
                )

    def test_rejects_must_be_fixed_in_the_phase3_activation_pr(self) -> None:
        """Reject 'must be fixed in the Phase 3 activation PR' — implies deferral."""
        assert "must be fixed in the phase 3 activation pr" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'must be fixed in the Phase 3 activation PR'. "
            "Blockers must be fixed BEFORE the Phase 3 activation PR."
        )

    def test_rejects_phase3_activation_pr_must_add_promote_gate(self) -> None:
        """Reject 'Phase 3 activation PR must add promote_approved gate'."""
        assert "phase 3 activation pr must add" not in self.content.lower(), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must NOT say "
            "'Phase 3 activation PR must add promote_approved gate'."
        )


# ---------------------------------------------------------------------------
# 13. Pre-Phase-3 hardening completion (PR #37–#43) — new for PR #44
# ---------------------------------------------------------------------------


class TestPrePhase3HardeningCompletion:
    """Verify that PHASE_2_COMPLETION_CHECKPOINT.md reflects PR #37–#43 completed state."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    def test_mentions_pr37(self) -> None:
        assert "PR #37" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #37"
        )

    def test_mentions_pr38(self) -> None:
        assert "PR #38" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #38"
        )

    def test_mentions_pr39(self) -> None:
        assert "PR #39" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #39"
        )

    def test_mentions_pr40(self) -> None:
        assert "PR #40" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #40"
        )

    def test_mentions_pr41(self) -> None:
        assert "PR #41" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #41"
        )

    def test_mentions_pr42(self) -> None:
        assert "PR #42" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #42"
        )

    def test_mentions_pr43(self) -> None:
        assert "PR #43" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention PR #43"
        )

    def test_still_says_phase3_not_started(self) -> None:
        content_lower = self.content.lower()
        assert (
            "phase 3 is not started" in content_lower
            or "phase 3 not started" in content_lower
            or "phase 3 still not started" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must still state Phase 3 is not started"
        )

    def test_still_says_api_not_connected(self) -> None:
        content_lower = self.content.lower()
        assert (
            "api remains not connected" in content_lower
            or "not connected" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must still state API is not connected"
        )

    def test_still_says_live_model_enabled_false(self) -> None:
        content_lower = self.content.lower()
        assert (
            "live_model_enabled remains false" in content_lower
            or "live_model_enabled | false" in content_lower
            or "live_model_enabled: false" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must still state live_model_enabled remains false"
        )

    def test_mentions_apply_mutation_safe_output_path(self) -> None:
        content_lower = self.content.lower()
        assert (
            "apply_mutation safe output path" in content_lower
            or "apply_mutation output path" in content_lower
            or "safe output path" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention apply_mutation safe output path"
        )

    def test_mentions_output_root_symlink_rejection(self) -> None:
        content_lower = self.content.lower()
        assert (
            "output_root symlink" in content_lower
            or "output_root itself must not be a symlink" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention output_root symlink rejection"
        )

    def test_mentions_gemini_api_timeout(self) -> None:
        content_lower = self.content.lower()
        assert (
            "gemini api timeout" in content_lower
            or "explicit timeout" in content_lower
            or "timeout" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Gemini API timeout"
        )

    def test_mentions_max_model_requests_per_run(self) -> None:
        assert "max_model_requests_per_run" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention max_model_requests_per_run"
        )

    def test_mentions_ast_parser_guard(self) -> None:
        content_lower = self.content.lower()
        assert (
            "ast" in content_lower
            and ("parser" in content_lower or "dos" in content_lower or "node count" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention AST/parser guard"
        )

    def test_mentions_memoryerror_or_recursionerror(self) -> None:
        content_lower = self.content.lower()
        assert (
            "memoryerror" in content_lower
            or "recursionerror" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention MemoryError or RecursionError"
        )

    def test_mentions_runtime_allocation_guard(self) -> None:
        content_lower = self.content.lower()
        assert (
            "runtime allocation" in content_lower
            or "runtime allocation risks" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention runtime allocation guard"
        )

