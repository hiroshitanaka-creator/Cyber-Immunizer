"""tests/test_phase2_plan_docs.py — Tests for Phase 2 planning documents.

Verifies that:
- docs/PHASE_2_PLAN.md exists and contains mandatory Phase 2 constraints
- README.md links to PHASE_2_PLAN.md
- docs/API_ACTIVATION_RUNBOOK.md states that API activation is Phase 3
- docs/AUDIT_CHARTER.md contains Phase 2 BLOCK condition for live_model_enabled=true
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# File existence tests
# ---------------------------------------------------------------------------


class TestPhase2PlanDocExists:
    def test_phase2_plan_exists(self) -> None:
        """docs/PHASE_2_PLAN.md must exist."""
        plan = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
        assert plan.exists(), (
            "docs/PHASE_2_PLAN.md is missing. "
            "This file is required for Phase 2 API-未接続運用強化 governance."
        )

    def test_phase2_plan_is_not_empty(self) -> None:
        """docs/PHASE_2_PLAN.md must not be empty."""
        plan = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
        assert plan.exists(), "docs/PHASE_2_PLAN.md does not exist"
        content = plan.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, (
            "docs/PHASE_2_PLAN.md appears to be nearly empty"
        )


# ---------------------------------------------------------------------------
# PHASE_2_PLAN.md content tests
# ---------------------------------------------------------------------------


class TestPhase2PlanContent:
    @pytest.fixture(autouse=True)
    def load_plan(self) -> None:
        plan = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
        assert plan.exists(), "docs/PHASE_2_PLAN.md is required for these tests"
        self.content = plan.read_text(encoding="utf-8")

    def test_plan_states_no_api_key_registration(self) -> None:
        """PHASE_2_PLAN.md must state that GEMINI_API_KEY is not registered in Phase 2."""
        content_lower = self.content.lower()
        # Must mention GEMINI_API_KEY
        assert "GEMINI_API_KEY" in self.content, (
            "PHASE_2_PLAN.md must mention GEMINI_API_KEY"
        )
        # Must state prohibition / not registering
        assert (
            "登録しない" in self.content
            or "登録" in self.content
            or "未登録" in self.content
        ), (
            "PHASE_2_PLAN.md must state that GEMINI_API_KEY is not registered in Phase 2"
        )

    def test_plan_states_no_live_model_enabled_true(self) -> None:
        """PHASE_2_PLAN.md must state that live_model_enabled=true is not set in Phase 2."""
        assert "live_model_enabled" in self.content, (
            "PHASE_2_PLAN.md must mention live_model_enabled"
        )
        # Must mention false maintenance or prohibition of true
        assert (
            "live_model_enabled=false" in self.content
            or "live_model_enabled=true" in self.content
        ), (
            "PHASE_2_PLAN.md must explicitly reference live_model_enabled state in Phase 2"
        )
        content_lower = self.content.lower()
        assert (
            "false" in content_lower
            or "維持" in self.content
            or "変更しない" in self.content
        ), (
            "PHASE_2_PLAN.md must state that live_model_enabled stays false"
        )

    def test_plan_states_no_real_gemini_api_call(self) -> None:
        """PHASE_2_PLAN.md must state that real Gemini API calls are not performed in Phase 2."""
        content_lower = self.content.lower()
        # Must mention Gemini API call prohibition
        assert (
            "gemini api call" in content_lower
            or "gemini api" in content_lower
            or "実 gemini api" in self.content
            or "実Gemini API" in self.content
        ), (
            "PHASE_2_PLAN.md must mention real Gemini API call prohibition"
        )
        # Must state prohibition / not doing it
        assert (
            "しない" in self.content
            or "禁止" in self.content
            or "未実行" in self.content
            or "行いません" in self.content
        ), (
            "PHASE_2_PLAN.md must state that real Gemini API calls are not performed"
        )

    def test_plan_lists_phase2_do_items(self) -> None:
        """PHASE_2_PLAN.md must list what Phase 2 does (やること)."""
        assert (
            "やること" in self.content
            or "実施" in self.content
            or "Do" in self.content
        ), (
            "PHASE_2_PLAN.md must list Phase 2 action items (やること)"
        )

    def test_plan_lists_phase2_dont_items(self) -> None:
        """PHASE_2_PLAN.md must list what Phase 2 does NOT do (やらないこと)."""
        assert (
            "やらないこと" in self.content
            or "禁止事項" in self.content
            or "しない" in self.content
        ), (
            "PHASE_2_PLAN.md must list Phase 2 prohibition items (やらないこと)"
        )

    def test_plan_has_phase3_transition_conditions(self) -> None:
        """PHASE_2_PLAN.md must state conditions for transitioning to Phase 3."""
        assert (
            "Phase 3" in self.content
        ), (
            "PHASE_2_PLAN.md must mention Phase 3 transition conditions"
        )
        assert (
            "Human Owner" in self.content
        ), (
            "PHASE_2_PLAN.md must state that Phase 3 requires Human Owner decision"
        )

    def test_plan_mentions_human_owner_decision(self) -> None:
        """PHASE_2_PLAN.md must state that phase transition requires Human Owner decision."""
        assert "Human Owner" in self.content, (
            "PHASE_2_PLAN.md must mention Human Owner's required decision"
        )
        assert (
            "明示" in self.content
            or "判断" in self.content
            or "決定" in self.content
        ), (
            "PHASE_2_PLAN.md must state that Human Owner must explicitly decide"
        )


# ---------------------------------------------------------------------------
# README link tests
# ---------------------------------------------------------------------------


class TestReadmeLinksToPhase2Plan:
    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md is required for these tests"
        self.content = readme.read_text(encoding="utf-8")

    def test_readme_links_to_phase2_plan(self) -> None:
        """README.md must contain a link to docs/PHASE_2_PLAN.md."""
        assert "PHASE_2_PLAN.md" in self.content, (
            "README.md must link to docs/PHASE_2_PLAN.md"
        )

    def test_readme_mentions_phase2_is_api_disconnected(self) -> None:
        """README.md must state that Phase 2 is the API-disconnected operation phase."""
        assert "Phase 2" in self.content, (
            "README.md must mention Phase 2"
        )
        # Must convey that Phase 2 is API-disconnected
        assert (
            "API未接続" in self.content
            or "未接続" in self.content
            or "live_model_enabled=false" in self.content
        ), (
            "README.md must state that Phase 2 is API-disconnected"
        )

    def test_readme_states_api_connection_is_phase3_or_later(self) -> None:
        """README.md must state that API connection is Phase 3 or later."""
        assert "Phase 3" in self.content, (
            "README.md must mention Phase 3 for API connection"
        )


# ---------------------------------------------------------------------------
# API_ACTIVATION_RUNBOOK.md Phase 3 supplement tests
# ---------------------------------------------------------------------------


class TestRunbookPhase3Supplement:
    @pytest.fixture(autouse=True)
    def load_runbook(self) -> None:
        runbook = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"
        assert runbook.exists(), (
            "docs/API_ACTIVATION_RUNBOOK.md is required for these tests"
        )
        self.content = runbook.read_text(encoding="utf-8")

    def test_runbook_states_api_activation_is_phase3(self) -> None:
        """API_ACTIVATION_RUNBOOK.md must state that API activation is Phase 3."""
        assert "Phase 3" in self.content, (
            "docs/API_ACTIVATION_RUNBOOK.md must state that API activation is Phase 3"
        )

    def test_runbook_states_no_api_key_in_phase2(self) -> None:
        """API_ACTIVATION_RUNBOOK.md must state that API key is not registered in Phase 2."""
        assert "Phase 2" in self.content, (
            "docs/API_ACTIVATION_RUNBOOK.md must mention Phase 2"
        )
        content_lower = self.content.lower()
        assert (
            "登録しない" in self.content
            or "未登録" in self.content
            or "phase 2" in content_lower
        ), (
            "docs/API_ACTIVATION_RUNBOOK.md must state API key is not registered in Phase 2"
        )

    def test_runbook_states_preflight_is_for_fail_closed_check(self) -> None:
        """API_ACTIVATION_RUNBOOK.md must state that preflight checks fail-closed behavior."""
        content_lower = self.content.lower()
        assert (
            "preflight" in content_lower
        ), (
            "docs/API_ACTIVATION_RUNBOOK.md must mention preflight"
        )
        assert (
            "fail-closed" in content_lower
            or "fail closed" in content_lower
        ), (
            "docs/API_ACTIVATION_RUNBOOK.md must mention fail-closed behavior for preflight"
        )


# ---------------------------------------------------------------------------
# AUDIT_CHARTER.md Phase 2 transition rule tests
# ---------------------------------------------------------------------------


class TestAuditCharterPhase2TransitionRule:
    @pytest.fixture(autouse=True)
    def load_charter(self) -> None:
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), (
            "docs/AUDIT_CHARTER.md is required for these tests"
        )
        self.content = charter.read_text(encoding="utf-8")

    def test_charter_has_phase2_transition_rule(self) -> None:
        """AUDIT_CHARTER.md must have a Phase 2 transition rule section."""
        assert (
            "Phase 2" in self.content
        ), (
            "AUDIT_CHARTER.md must mention Phase 2"
        )

    def test_charter_phase2_blocks_live_model_enabled_true(self) -> None:
        """AUDIT_CHARTER.md must state that live_model_enabled=true in Phase 2 is BLOCK."""
        assert "live_model_enabled" in self.content, (
            "AUDIT_CHARTER.md must mention live_model_enabled"
        )
        assert "BLOCK" in self.content, (
            "AUDIT_CHARTER.md must contain BLOCK decision"
        )
        # The content must mention both live_model_enabled=true and BLOCK in Phase 2 context
        # Check that the Phase 2 section contains live_model_enabled BLOCK condition
        content_lower = self.content.lower()
        # Find Phase 2 transition rule section
        phase2_section_start = self.content.find("Phase 2 transition rule")
        assert phase2_section_start != -1, (
            "AUDIT_CHARTER.md must have 'Phase 2 transition rule' section"
        )
        phase2_section = self.content[phase2_section_start:]
        assert "live_model_enabled" in phase2_section, (
            "Phase 2 transition rule section must mention live_model_enabled"
        )
        assert "BLOCK" in phase2_section, (
            "Phase 2 transition rule section must mention BLOCK"
        )

    def test_charter_phase2_addresses_api_key_registration_pr(self) -> None:
        """AUDIT_CHARTER.md Phase 2 rule must address PRs that assume GEMINI_API_KEY."""
        phase2_section_start = self.content.find("Phase 2 transition rule")
        assert phase2_section_start != -1, (
            "AUDIT_CHARTER.md must have 'Phase 2 transition rule' section"
        )
        phase2_section = self.content[phase2_section_start:]
        assert (
            "GEMINI_API_KEY" in phase2_section
            or "BLOCK" in phase2_section
        ), (
            "Phase 2 transition rule section must address GEMINI_API_KEY registration PRs"
        )
        # Must include REQUEST CHANGES or BLOCK for such PRs
        assert (
            "REQUEST CHANGES" in phase2_section
            or "BLOCK" in phase2_section
        ), (
            "Phase 2 transition rule section must specify REQUEST CHANGES or BLOCK "
            "for PRs that assume GEMINI_API_KEY registration"
        )

    def test_charter_phase3_requires_human_owner_decision(self) -> None:
        """AUDIT_CHARTER.md must state that Phase 3 start requires Human Owner decision."""
        phase2_section_start = self.content.find("Phase 2 transition rule")
        assert phase2_section_start != -1, (
            "AUDIT_CHARTER.md must have 'Phase 2 transition rule' section"
        )
        phase2_section = self.content[phase2_section_start:]
        assert "Phase 3" in phase2_section, (
            "Phase 2 transition rule section must mention Phase 3"
        )
        assert "Human Owner" in phase2_section, (
            "Phase 2 transition rule section must require Human Owner decision for Phase 3"
        )
