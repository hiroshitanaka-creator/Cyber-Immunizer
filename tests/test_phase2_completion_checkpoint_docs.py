"""tests/test_phase2_completion_checkpoint_docs.py

Phase 2 Completion Checkpoint documentation tests.

Verifies:
1. docs/PHASE_2_COMPLETION_CHECKPOINT.md exists with all required sections
2. All Phase 2-A through 2-E are recorded as Completed with PR evidence
3. Current state is documented (Phase 3 not started, API not connected, etc.)
4. Safety invariants are documented
5. README / PHASE_2_PLAN / API_ACTIVATION_RUNBOOK link to the checkpoint
6. Regression guard: dangerous phrases are not present in key docs
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_README = _PROJECT_ROOT / "README.md"
_PHASE2_PLAN = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
_RUNBOOK = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"
_CHECKPOINT = _PROJECT_ROOT / "docs" / "PHASE_2_COMPLETION_CHECKPOINT.md"


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


class _DocFixture:
    """Mixin to load a document and expose its content."""

    _path: Path

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert self._path.exists(), f"{self._path} does not exist"
        self.content = self._path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Document existence
# ---------------------------------------------------------------------------


class TestCheckpointDocExists(_DocFixture):
    _path = _CHECKPOINT

    def test_checkpoint_doc_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must exist."""
        assert _CHECKPOINT.exists(), (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md must exist"
        )

    def test_checkpoint_doc_is_not_empty(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must not be empty."""
        assert len(self.content.strip()) > 0, (
            "docs/PHASE_2_COMPLETION_CHECKPOINT.md must not be empty"
        )


# ---------------------------------------------------------------------------
# 2. Required sections
# ---------------------------------------------------------------------------


class TestCheckpointDocSections(_DocFixture):
    _path = _CHECKPOINT

    def test_purpose_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Purpose section."""
        assert "## Purpose" in self.content or "# Purpose" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Purpose section"
        )

    def test_completion_status_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Completion status section."""
        assert "## Completion status" in self.content or "Completion status" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Completion status section"
        )

    def test_current_state_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Current state after Phase 2 section."""
        assert (
            "## Current state after Phase 2" in self.content
            or "Current state after Phase 2" in self.content
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Current state after Phase 2' section"
        )

    def test_safety_invariants_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Safety invariants preserved section."""
        assert (
            "## Safety invariants preserved" in self.content
            or "Safety invariants preserved" in self.content
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Safety invariants preserved' section"
        )

    def test_phase3_entry_conditions_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Phase 3 entry conditions section."""
        assert (
            "## Phase 3 entry conditions" in self.content
            or "Phase 3 entry conditions" in self.content
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a 'Phase 3 entry conditions' section"
        )

    def test_non_goals_section_exists(self) -> None:
        """docs/PHASE_2_COMPLETION_CHECKPOINT.md must have a Non-goals section."""
        assert (
            "## Non-goals" in self.content
            or "Non-goals" in self.content
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must have a Non-goals section"
        )


# ---------------------------------------------------------------------------
# 3. Phase 2-A through 2-E completion and PR evidence
# ---------------------------------------------------------------------------


class TestCheckpointPhaseCompletion(_DocFixture):
    _path = _CHECKPOINT

    def test_phase2a_is_completed(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must record Phase 2-A as Completed."""
        content = self.content
        assert "Phase 2-A" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Phase 2-A"
        )
        # Find Phase 2-A row
        for line in content.splitlines():
            if "Phase 2-A" in line and "|" in line:
                assert (
                    "Completed" in line or "completed" in line or "✅" in line
                ), f"Phase 2-A row must show Completed, got: {line!r}"
                return
        # Fallback: check window
        idx = content.find("Phase 2-A")
        assert (
            "Completed" in content[idx:idx+200]
            or "completed" in content[idx:idx+200]
            or "✅" in content[idx:idx+200]
        ), "PHASE_2_COMPLETION_CHECKPOINT.md must indicate Phase 2-A Completed"

    def test_phase2b_is_completed(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must record Phase 2-B as Completed."""
        content = self.content
        assert "Phase 2-B" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Phase 2-B"
        )
        for line in content.splitlines():
            if "Phase 2-B" in line and "|" in line:
                assert (
                    "Completed" in line or "completed" in line or "✅" in line
                ), f"Phase 2-B row must show Completed, got: {line!r}"
                return
        idx = content.find("Phase 2-B")
        assert (
            "Completed" in content[idx:idx+200]
            or "completed" in content[idx:idx+200]
            or "✅" in content[idx:idx+200]
        ), "PHASE_2_COMPLETION_CHECKPOINT.md must indicate Phase 2-B Completed"

    def test_phase2c_is_completed(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must record Phase 2-C as Completed."""
        content = self.content
        assert "Phase 2-C" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Phase 2-C"
        )
        for line in content.splitlines():
            if "Phase 2-C" in line and "|" in line:
                assert (
                    "Completed" in line or "completed" in line or "✅" in line
                ), f"Phase 2-C row must show Completed, got: {line!r}"
                return
        idx = content.find("Phase 2-C")
        assert (
            "Completed" in content[idx:idx+200]
            or "completed" in content[idx:idx+200]
            or "✅" in content[idx:idx+200]
        ), "PHASE_2_COMPLETION_CHECKPOINT.md must indicate Phase 2-C Completed"

    def test_phase2d_is_completed(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must record Phase 2-D as Completed."""
        content = self.content
        assert "Phase 2-D" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Phase 2-D"
        )
        for line in content.splitlines():
            if "Phase 2-D" in line and "|" in line:
                assert (
                    "Completed" in line or "completed" in line or "✅" in line
                ), f"Phase 2-D row must show Completed, got: {line!r}"
                return
        idx = content.find("Phase 2-D")
        assert (
            "Completed" in content[idx:idx+200]
            or "completed" in content[idx:idx+200]
            or "✅" in content[idx:idx+200]
        ), "PHASE_2_COMPLETION_CHECKPOINT.md must indicate Phase 2-D Completed"

    def test_phase2e_is_completed(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must record Phase 2-E as Completed."""
        content = self.content
        assert "Phase 2-E" in content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Phase 2-E"
        )
        for line in content.splitlines():
            if "Phase 2-E" in line and "|" in line:
                assert (
                    "Completed" in line or "completed" in line or "✅" in line
                ), f"Phase 2-E row must show Completed, got: {line!r}"
                return
        idx = content.find("Phase 2-E")
        assert (
            "Completed" in content[idx:idx+200]
            or "completed" in content[idx:idx+200]
            or "✅" in content[idx:idx+200]
        ), "PHASE_2_COMPLETION_CHECKPOINT.md must indicate Phase 2-E Completed"

    def test_pr22_evidence(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #22 as evidence."""
        assert "PR #22" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #22 as evidence for Phase 2-A"
        )

    def test_pr23_evidence(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #23 as evidence."""
        assert "PR #23" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #23 as evidence for Phase 2-B"
        )

    def test_pr24_evidence(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #24 as evidence."""
        assert "PR #24" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #24 as evidence for Phase 2-C"
        )

    def test_pr26_evidence(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #26 as evidence."""
        assert "PR #26" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #26 as evidence for Phase 2-D"
        )

    def test_pr27_evidence(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #27 as evidence."""
        assert "PR #27" in self.content, (
            "PHASE_2_COMPLETION_CHECKPOINT.md must reference PR #27 as evidence for Phase 2-E"
        )


# ---------------------------------------------------------------------------
# 4. Current state assertions
# ---------------------------------------------------------------------------


class TestCheckpointCurrentState(_DocFixture):
    _path = _CHECKPOINT

    def test_phase3_not_started(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state Phase 3 is not started."""
        content_lower = self.content.lower()
        assert (
            "phase 3 not started" in content_lower
            or "phase 3 is not started" in content_lower
            or ("phase 3" in content_lower and "not started" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state that Phase 3 is not started"
        )

    def test_api_not_connected(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state API is not connected."""
        content_lower = self.content.lower()
        assert (
            "not connected" in content_lower
            or "api connection: not connected" in content_lower
            or "未接続" in self.content
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state that API is not connected"
        )

    def test_live_model_enabled_false(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state live_model_enabled is false."""
        content_lower = self.content.lower()
        assert (
            "live_model_enabled: false" in content_lower
            or "live_model_enabled=false" in content_lower
            or ("live_model_enabled" in content_lower and "false" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state live_model_enabled is false"
        )

    def test_gemini_api_key_not_in_repo(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state GEMINI_API_KEY is not in repository files."""
        content_lower = self.content.lower()
        assert (
            "not present in repository files" in content_lower
            or ("gemini_api_key" in content_lower and "not present" in content_lower)
            or ("gemini_api_key" in content_lower and "not in repository" in content_lower)
            or "no gemini_api_key in repository files" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state GEMINI_API_KEY is not present in repository files"
        )

    def test_schedule_noop_only(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state schedule mode is noop only."""
        content_lower = self.content.lower()
        assert (
            "noop only" in content_lower
            or "schedule mode: noop only" in content_lower
            or ("schedule" in content_lower and "noop" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state that schedule mode is noop only"
        )

    def test_human_owner_decision_required(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state Human Owner decision is required."""
        content_lower = self.content.lower()
        assert (
            "human owner decision required" in content_lower
            or "human owner explicit decision" in content_lower
            or (
                "human owner" in content_lower
                and ("decision" in content_lower or "required" in content_lower)
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Human Owner decision is required"
        )

    def test_dedicated_phase3_pr_required(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state Phase 3 activation requires a dedicated PR."""
        content_lower = self.content.lower()
        assert (
            "dedicated pr" in content_lower
            or "phase 3 activation must be a dedicated pr" in content_lower
            or "phase 3 activation requires dedicated pr" in content_lower
            or ("dedicated" in content_lower and "phase 3" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Phase 3 activation must be a dedicated PR"
        )

    def test_normal_ci_read_only(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state Normal CI is read-only."""
        content_lower = self.content.lower()
        assert (
            "normal ci: read-only" in content_lower
            or "normal ci" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must mention Normal CI read-only state"
        )

    def test_gemini_api_not_executed_by_phase2(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state Gemini API calls not executed by Phase 2."""
        content_lower = self.content.lower()
        assert (
            "not executed by phase 2" in content_lower
            or "gemini api calls: not executed" in content_lower
            or ("gemini api" in content_lower and "not executed" in content_lower)
            or "no gemini api call in phase 2" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Gemini API calls were not executed by Phase 2"
        )


# ---------------------------------------------------------------------------
# 5. Safety invariants
# ---------------------------------------------------------------------------


class TestCheckpointSafetyInvariants(_DocFixture):
    _path = _CHECKPOINT

    def test_no_gemini_api_call_in_phase2(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state no Gemini API call in Phase 2."""
        content_lower = self.content.lower()
        assert (
            "no gemini api call in phase 2" in content_lower
            or ("no gemini api call" in content_lower)
            or ("gemini api" in content_lower and "not executed" in content_lower)
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state 'No Gemini API call in Phase 2'"
        )

    def test_no_workflow_permission_escalation(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state no workflow permission escalation."""
        content_lower = self.content.lower()
        assert (
            "no workflow permission escalation" in content_lower
            or "workflow permission escalation" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state 'No workflow permission escalation'"
        )

    def test_no_generated_code_execution_write_permission(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state no generated code execution in write-permission jobs."""
        content_lower = self.content.lower()
        assert (
            "no generated code execution in write-permission jobs" in content_lower
            or (
                "generated code execution" in content_lower
                and "write-permission" in content_lower
            )
            or (
                "generated code" in content_lower
                and "write" in content_lower
                and "permission" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'No generated code execution in write-permission jobs'"
        )

    def test_ledger_not_reset_or_overwritten_or_rolled_back(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state ledger is not reset, overwritten, or rolled back."""
        content_lower = self.content.lower()
        assert (
            "not reset, overwritten, or rolled back" in content_lower
            or "ledger is not reset" in content_lower
            or (
                "ledger" in content_lower
                and "not reset" in content_lower
            )
            or (
                "ledger" in content_lower
                and "not overwritten" in content_lower
            )
            or (
                "api usage ledger is not reset" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "ledger is not reset, overwritten, or rolled back"
        )

    def test_normal_ci_must_not_call_gemini(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state normal CI does not call Gemini."""
        content_lower = self.content.lower()
        assert (
            "no normal ci gemini api call" in content_lower
            or "normal ci: read-only" in content_lower
            or ("normal ci" in content_lower and "read-only" in content_lower)
            or "no normal ci" in content_lower
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state normal CI does not call Gemini API"
        )

    def test_promote_requires_human_owner_and_gpt_audit_gate(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state promote requires Human Owner + GPT Audit Gate."""
        content_lower = self.content.lower()
        assert (
            "promote requires human owner approval and gpt audit gate approve" in content_lower
            or (
                "promote" in content_lower
                and "human owner" in content_lower
                and "gpt audit gate" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state "
            "'Promote requires Human Owner approval and GPT Audit Gate APPROVE'"
        )

    def test_no_gemini_api_key_in_repo(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state no GEMINI_API_KEY in repository files."""
        content_lower = self.content.lower()
        assert (
            "no gemini_api_key in repository files" in content_lower
            or (
                "gemini_api_key" in content_lower
                and (
                    "not present in repository" in content_lower
                    or "not in repository" in content_lower
                    or "no gemini_api_key" in content_lower
                )
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state no GEMINI_API_KEY in repository files"
        )

    def test_no_live_model_enabled_true_in_phase2(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must state no live_model_enabled=true in Phase 2."""
        content_lower = self.content.lower()
        assert (
            "no live_model_enabled=true in phase 2" in content_lower
            or (
                "live_model_enabled" in content_lower
                and "phase 2" in content_lower
                and (
                    "false" in content_lower
                    or "not" in content_lower
                )
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state no live_model_enabled=true in Phase 2"
        )

    def test_phase3_activation_requires_dedicated_pr(self) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md Safety invariants must mention dedicated PR for Phase 3."""
        content_lower = self.content.lower()
        assert (
            "phase 3 activation requires dedicated pr" in content_lower
            or (
                "phase 3 activation" in content_lower
                and "dedicated" in content_lower
                and "pr" in content_lower
            )
        ), (
            "PHASE_2_COMPLETION_CHECKPOINT.md must state Phase 3 activation requires dedicated PR"
        )


# ---------------------------------------------------------------------------
# 6. Links: README / PHASE_2_PLAN / RUNBOOK → PHASE_2_COMPLETION_CHECKPOINT.md
# ---------------------------------------------------------------------------


class TestCheckpointLinks:
    """Verify README, PHASE_2_PLAN, and API_ACTIVATION_RUNBOOK link to the checkpoint."""

    @pytest.fixture(autouse=True)
    def _load_all(self) -> None:
        for p in (_README, _PHASE2_PLAN, _RUNBOOK, _CHECKPOINT):
            assert p.exists(), f"{p} does not exist"
        self.readme = _README.read_text(encoding="utf-8")
        self.plan = _PHASE2_PLAN.read_text(encoding="utf-8")
        self.runbook = _RUNBOOK.read_text(encoding="utf-8")
        self.checkpoint = _CHECKPOINT.read_text(encoding="utf-8")

    def test_readme_links_to_checkpoint(self) -> None:
        """README.md must link to PHASE_2_COMPLETION_CHECKPOINT.md."""
        assert "PHASE_2_COMPLETION_CHECKPOINT.md" in self.readme, (
            "README.md must contain a link to PHASE_2_COMPLETION_CHECKPOINT.md"
        )

    def test_phase2_plan_links_to_checkpoint(self) -> None:
        """docs/PHASE_2_PLAN.md must link to PHASE_2_COMPLETION_CHECKPOINT.md."""
        assert "PHASE_2_COMPLETION_CHECKPOINT.md" in self.plan, (
            "docs/PHASE_2_PLAN.md must contain a link to PHASE_2_COMPLETION_CHECKPOINT.md"
        )

    def test_runbook_links_to_checkpoint(self) -> None:
        """docs/API_ACTIVATION_RUNBOOK.md must link to PHASE_2_COMPLETION_CHECKPOINT.md."""
        assert "PHASE_2_COMPLETION_CHECKPOINT.md" in self.runbook, (
            "docs/API_ACTIVATION_RUNBOOK.md must contain a link to PHASE_2_COMPLETION_CHECKPOINT.md"
        )

    def test_readme_states_phase3_not_started(self) -> None:
        """README.md must state Phase 3 is not started."""
        content_lower = self.readme.lower()
        assert (
            "phase 3 is not started" in content_lower
            or "phase 3 not started" in content_lower
            or (
                "phase 3" in content_lower
                and "human owner" in content_lower
                and ("not started" in content_lower or "requires" in content_lower)
            )
        ), (
            "README.md must state Phase 3 is not started / requires Human Owner decision"
        )

    def test_readme_states_api_not_connected(self) -> None:
        """README.md must state API is not connected."""
        content_lower = self.readme.lower()
        assert (
            "not connected" in content_lower
            or "api connection | not connected" in content_lower
            or "未接続" in self.readme
        ), (
            "README.md must state API is not connected"
        )

    def test_readme_states_live_model_enabled_false(self) -> None:
        """README.md must state live_model_enabled remains false."""
        content_lower = self.readme.lower()
        assert (
            "live_model_enabled remains false" in content_lower
            or "live_model_enabled | false" in content_lower
            or (
                "live_model_enabled" in content_lower
                and "false" in content_lower
            )
        ), (
            "README.md must state live_model_enabled remains false"
        )

    def test_phase2_plan_states_phase3_not_started(self) -> None:
        """docs/PHASE_2_PLAN.md must state Phase 3 is not started."""
        content_lower = self.plan.lower()
        assert (
            "phase 3 not started" in content_lower
            or "phase 3 requires" in content_lower
            or (
                "phase 3" in content_lower
                and "human owner" in content_lower
                and ("requires" in content_lower or "decision" in content_lower)
            )
        ), (
            "docs/PHASE_2_PLAN.md must state Phase 3 is not started / requires Human Owner decision"
        )

    def test_phase2_plan_states_api_not_connected(self) -> None:
        """docs/PHASE_2_PLAN.md must state API is not connected."""
        content_lower = self.plan.lower()
        assert (
            "api remains disconnected" in content_lower
            or "not connected" in content_lower
            or "disconnected" in content_lower
            or "未接続" in self.plan
        ), (
            "docs/PHASE_2_PLAN.md must state API is not connected"
        )

    def test_phase2_plan_states_live_model_enabled_false(self) -> None:
        """docs/PHASE_2_PLAN.md must state live_model_enabled remains false."""
        content_lower = self.plan.lower()
        assert (
            "live_model_enabled" in content_lower
            and "false" in content_lower
        ), (
            "docs/PHASE_2_PLAN.md must state live_model_enabled remains false"
        )

    def test_runbook_states_phase2_completion_does_not_authorize_activation(self) -> None:
        """docs/API_ACTIVATION_RUNBOOK.md must state Phase 2 completion does not authorize API activation."""
        content_lower = self.runbook.lower()
        assert (
            "phase 2 completion does not authorize api activation by itself" in content_lower
            or "phase 2 completion does not authorize" in content_lower
            or (
                "phase 2" in content_lower
                and "does not authorize" in content_lower
            )
            or (
                "phase 2 completion" in content_lower
                and "by itself" in content_lower
            )
        ), (
            "docs/API_ACTIVATION_RUNBOOK.md must state Phase 2 completion does not authorize API activation by itself"
        )


# ---------------------------------------------------------------------------
# 7. Regression guard — dangerous phrases must not appear in key docs
# ---------------------------------------------------------------------------


_DANGEROUS_PHRASES_EN = [
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

_DANGEROUS_PHRASES_JA = [
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


class TestRegressionGuardReadme:
    """Regression guard: dangerous phrases must not appear in README.md."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _README.exists()
        self.content = _README.read_text(encoding="utf-8")

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_EN)
    def test_readme_no_dangerous_phrase_en(self, phrase: str) -> None:
        """README.md must not contain dangerous English phrase."""
        assert phrase not in self.content, (
            f"README.md must NOT contain dangerous phrase: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_JA)
    def test_readme_no_dangerous_phrase_ja(self, phrase: str) -> None:
        """README.md must not contain dangerous Japanese phrase."""
        assert phrase not in self.content, (
            f"README.md must NOT contain dangerous phrase: {phrase!r}"
        )


class TestRegressionGuardPhase2Plan:
    """Regression guard: dangerous phrases must not appear in PHASE_2_PLAN.md."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _PHASE2_PLAN.exists()
        self.content = _PHASE2_PLAN.read_text(encoding="utf-8")

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_EN)
    def test_phase2_plan_no_dangerous_phrase_en(self, phrase: str) -> None:
        """PHASE_2_PLAN.md must not contain dangerous English phrase."""
        assert phrase not in self.content, (
            f"docs/PHASE_2_PLAN.md must NOT contain dangerous phrase: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_JA)
    def test_phase2_plan_no_dangerous_phrase_ja(self, phrase: str) -> None:
        """PHASE_2_PLAN.md must not contain dangerous Japanese phrase."""
        assert phrase not in self.content, (
            f"docs/PHASE_2_PLAN.md must NOT contain dangerous phrase: {phrase!r}"
        )


class TestRegressionGuardCheckpoint:
    """Regression guard: dangerous phrases must not appear in PHASE_2_COMPLETION_CHECKPOINT.md."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKPOINT.exists()
        self.content = _CHECKPOINT.read_text(encoding="utf-8")

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_EN)
    def test_checkpoint_no_dangerous_phrase_en(self, phrase: str) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must not contain dangerous English phrase."""
        assert phrase not in self.content, (
            f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain dangerous phrase: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", _DANGEROUS_PHRASES_JA)
    def test_checkpoint_no_dangerous_phrase_ja(self, phrase: str) -> None:
        """PHASE_2_COMPLETION_CHECKPOINT.md must not contain dangerous Japanese phrase."""
        assert phrase not in self.content, (
            f"PHASE_2_COMPLETION_CHECKPOINT.md must NOT contain dangerous phrase: {phrase!r}"
        )
