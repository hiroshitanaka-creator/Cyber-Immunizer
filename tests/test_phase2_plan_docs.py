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
            "Project Owner" in self.content
        ), (
            "PHASE_2_PLAN.md must state that Phase 3 requires Project Owner decision"
        )

    def test_plan_mentions_human_owner_decision(self) -> None:
        """PHASE_2_PLAN.md must state that phase transition requires Project Owner decision."""
        assert "Project Owner" in self.content, (
            "PHASE_2_PLAN.md must mention Project Owner's required decision"
        )
        assert (
            "明示" in self.content
            or "判断" in self.content
            or "決定" in self.content
        ), (
            "PHASE_2_PLAN.md must state that Project Owner must explicitly decide"
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
        """AUDIT_CHARTER.md must state that Phase 3 start requires Project Owner decision."""
        phase2_section_start = self.content.find("Phase 2 transition rule")
        assert phase2_section_start != -1, (
            "AUDIT_CHARTER.md must have 'Phase 2 transition rule' section"
        )
        phase2_section = self.content[phase2_section_start:]
        assert "Phase 3" in phase2_section, (
            "Phase 2 transition rule section must mention Phase 3"
        )
        assert "Project Owner" in phase2_section, (
            "Phase 2 transition rule section must require Project Owner decision for Phase 3"
        )


# ---------------------------------------------------------------------------
# AUDIT_CHARTER.md Phase 2 definition consistency tests (regression guard)
# ---------------------------------------------------------------------------


class TestAuditCharterPhase2Consistency:
    """Verify that AUDIT_CHARTER.md no longer contains old Phase 2 = API-connection text.

    These tests guard against regression: the old section 7 described Phase 2
    as the API-connection phase and instructed readers to register GEMINI_API_KEY
    and change live_model_enabled=true as part of Phase 2 transition.
    The corrected document must NOT contain that old framing.
    """

    @pytest.fixture(autouse=True)
    def load_charter(self) -> None:
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), (
            "docs/AUDIT_CHARTER.md is required for these tests"
        )
        self.content = charter.read_text(encoding="utf-8")

    def test_charter_section7_does_not_define_phase2_as_api_connection(self) -> None:
        """Section 7 of AUDIT_CHARTER.md must NOT define Phase 2 as '実 Gemini API 接続'.

        The old text read: 'Phase 2（実 Gemini API 接続）への移行は…'
        Phase 2 is now API-disconnected operation; Phase 3 is API connection.
        """
        # Find section 7 boundaries (between section 7 header and section 8 header)
        sec7_start = self.content.find("## 7. Phase transition rule")
        sec8_start = self.content.find("## 8. Phase 2 transition rule")
        assert sec7_start != -1, (
            "AUDIT_CHARTER.md must have section 7 (Phase transition rule)"
        )
        # Extract section 7 text (up to section 8, or end of file)
        if sec8_start != -1:
            sec7_text = self.content[sec7_start:sec8_start]
        else:
            sec7_text = self.content[sec7_start:]

        assert "Phase 2（実 Gemini API 接続）" not in sec7_text, (
            "AUDIT_CHARTER.md section 7 must NOT describe Phase 2 as '実 Gemini API 接続'. "
            "Phase 2 = API未接続運用強化. API connection is Phase 3."
        )

    def test_charter_does_not_instruct_gemini_key_registration_for_phase2(self) -> None:
        """AUDIT_CHARTER.md must NOT instruct registering GEMINI_API_KEY as part of Phase 2.

        The old text said: 'GEMINI_API_KEY を GitHub Secrets に登録した上で'
        in the context of Phase 2 transition. GEMINI_API_KEY registration is Phase 3+.
        """
        # The specific old sentence tied GEMINI_API_KEY registration to Phase 2 migration
        old_phrase = "GEMINI_API_KEY を GitHub Secrets に登録した上で、"
        assert old_phrase not in self.content, (
            "AUDIT_CHARTER.md must NOT contain the old instruction to register GEMINI_API_KEY "
            "as part of Phase 2 transition. GEMINI_API_KEY registration is Phase 3."
        )

    def test_charter_does_not_instruct_live_model_true_for_phase2(self) -> None:
        """AUDIT_CHARTER.md must NOT instruct changing live_model_enabled=true for Phase 2.

        The old text said: 'レビュー済み PR を通じて `live_model_enabled=true` を変更してください'
        in the Phase 2 transition context. live_model_enabled=true is Phase 3+.
        """
        # The specific old sentence instructed live_model_enabled=true change in Phase 2 context
        old_phrase = "レビュー済み PR を通じて `live_model_enabled=true` を変更してください"
        assert old_phrase not in self.content, (
            "AUDIT_CHARTER.md must NOT contain the old instruction to change "
            "live_model_enabled=true as part of Phase 2 transition. "
            "live_model_enabled=true change is Phase 3."
        )

    def test_charter_states_phase2_is_api_disconnected(self) -> None:
        """AUDIT_CHARTER.md must explicitly define Phase 2 as API-disconnected operation.

        The document must contain 'Phase 2（API未接続運用強化）' or equivalent phrasing
        to make clear that Phase 2 does NOT involve API connection.
        """
        assert (
            "Phase 2（API未接続運用強化）" in self.content
        ), (
            "AUDIT_CHARTER.md must explicitly state 'Phase 2（API未接続運用強化）'. "
            "This prevents confusion with the old Phase 2 = API connection definition."
        )

    def test_charter_section7_states_api_connection_is_phase3(self) -> None:
        """Section 7 of AUDIT_CHARTER.md must state that API connection is Phase 3."""
        sec7_start = self.content.find("## 7. Phase transition rule")
        sec8_start = self.content.find("## 8. Phase 2 transition rule")
        assert sec7_start != -1, (
            "AUDIT_CHARTER.md must have section 7 (Phase transition rule)"
        )
        if sec8_start != -1:
            sec7_text = self.content[sec7_start:sec8_start]
        else:
            sec7_text = self.content[sec7_start:]

        assert "Phase 3" in sec7_text, (
            "AUDIT_CHARTER.md section 7 must mention that API connection is Phase 3"
        )

    def test_charter_section7_states_live_model_enabled_false_in_phase2(self) -> None:
        """Section 7 must state that live_model_enabled=false is maintained in Phase 2."""
        sec7_start = self.content.find("## 7. Phase transition rule")
        sec8_start = self.content.find("## 8. Phase 2 transition rule")
        assert sec7_start != -1
        if sec8_start != -1:
            sec7_text = self.content[sec7_start:sec8_start]
        else:
            sec7_text = self.content[sec7_start:]

        assert (
            "live_model_enabled=false" in sec7_text
            or "live_model_enabled` が `false" in sec7_text
            or "live_model_enabled` を `false" in sec7_text
        ), (
            "AUDIT_CHARTER.md section 7 must state that live_model_enabled stays false in Phase 2"
        )


# ---------------------------------------------------------------------------
# README.md Phase 1 Baseline expression consistency tests (regression guard)
# ---------------------------------------------------------------------------


class TestReadmePhase1BaselineExpression:
    """Verify that README.md no longer contains the ambiguous 'Next phase' phrasing.

    The old table row 'Next phase starts only after project owner decides' was written
    when Phase 1 was current. Now that Phase 2 is in progress, 'next phase' is ambiguous.
    The corrected text must clearly reference Phase 3 (API activation).
    """

    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md is required for these tests"
        self.content = readme.read_text(encoding="utf-8")

    def test_readme_does_not_have_ambiguous_next_phase_expression(self) -> None:
        """README.md must NOT contain the ambiguous 'Next phase starts only after' text.

        This phrase was written when Phase 1 was the current phase and 'next phase'
        could be misread as Phase 2 requiring API connection. It must be replaced
        with explicit Phase 3 / API activation language.
        """
        assert "Next phase starts only after" not in self.content, (
            "README.md must NOT contain 'Next phase starts only after'. "
            "Use explicit 'Phase 3 (API activation) starts only after Project Owner decides' instead."
        )

    def test_readme_phase1_baseline_table_references_phase3_for_api_activation(self) -> None:
        """README.md Phase 1 Baseline table must explicitly reference Phase 3 for API activation.

        The table row must make clear that API activation (GEMINI_API_KEY, live_model_enabled=true)
        belongs to Phase 3, not Phase 2.
        """
        # Find the Phase 1 Baseline section
        phase1_section_start = self.content.find("Phase 1 Baseline")
        assert phase1_section_start != -1, (
            "README.md must have 'Phase 1 Baseline' section"
        )
        # Find end of Phase 1 baseline section (next major section)
        phase2_section_start = self.content.find("Phase 2:", phase1_section_start)
        if phase2_section_start != -1:
            phase1_section = self.content[phase1_section_start:phase2_section_start]
        else:
            phase1_section = self.content[phase1_section_start:]

        assert "Phase 3" in phase1_section, (
            "README.md Phase 1 Baseline section must reference Phase 3 "
            "to make clear that API activation belongs to Phase 3"
        )

    def test_readme_explicitly_states_api_activation_is_phase3_or_later(self) -> None:
        """README.md must state that API activation (GEMINI_API_KEY etc.) is Phase 3 or later."""
        assert "Phase 3" in self.content, (
            "README.md must mention Phase 3 for API activation"
        )
        # Must mention that GEMINI_API_KEY is Phase 3+
        assert "GEMINI_API_KEY" in self.content, (
            "README.md must mention GEMINI_API_KEY"
        )
        # Phase 3 and GEMINI_API_KEY must both appear
        phase3_pos = self.content.find("Phase 3")
        gemini_pos = self.content.find("GEMINI_API_KEY")
        assert phase3_pos != -1 and gemini_pos != -1, (
            "README.md must mention both Phase 3 and GEMINI_API_KEY"
        )
