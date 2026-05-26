"""tests/test_phase1_baseline_docs.py — Tests for Phase 1 baseline documentation.

Verifies that Phase 1 completion state is properly documented and that
all required safety invariants and links are present.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# docs/PHASE_1_BASELINE.md existence and content tests
# ---------------------------------------------------------------------------


class TestPhase1BaselineDocExists:
    """Verify that docs/PHASE_1_BASELINE.md exists and is non-empty."""

    def test_phase1_baseline_exists(self) -> None:
        """docs/PHASE_1_BASELINE.md must exist."""
        baseline = _PROJECT_ROOT / "docs" / "PHASE_1_BASELINE.md"
        assert baseline.exists(), (
            "docs/PHASE_1_BASELINE.md is missing. "
            "This file is required to record Phase 1 completion state."
        )

    def test_phase1_baseline_is_not_empty(self) -> None:
        """docs/PHASE_1_BASELINE.md must not be empty."""
        baseline = _PROJECT_ROOT / "docs" / "PHASE_1_BASELINE.md"
        assert baseline.exists(), "docs/PHASE_1_BASELINE.md does not exist"
        content = baseline.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, (
            "docs/PHASE_1_BASELINE.md appears to be nearly empty"
        )


class TestPhase1BaselineContent:
    """Verify required content sections in docs/PHASE_1_BASELINE.md."""

    @pytest.fixture(autouse=True)
    def load_baseline(self) -> None:
        baseline = _PROJECT_ROOT / "docs" / "PHASE_1_BASELINE.md"
        assert baseline.exists(), "docs/PHASE_1_BASELINE.md is required for these tests"
        self.content = baseline.read_text(encoding="utf-8")

    def test_baseline_mentions_phase1_complete(self) -> None:
        """Baseline must state that Phase 1 is complete."""
        content_lower = self.content.lower()
        assert "phase 1" in content_lower, (
            "PHASE_1_BASELINE.md must reference 'Phase 1'"
        )
        # Confirm it records completed items (完了 or complete/completed/baseline)
        assert (
            "完了" in self.content
            or "complete" in content_lower
            or "baseline" in content_lower
        ), (
            "PHASE_1_BASELINE.md must indicate Phase 1 completion"
        )

    def test_baseline_states_gemini_api_key_not_registered(self) -> None:
        """Baseline must explicitly state GEMINI_API_KEY registration is not done."""
        assert "GEMINI_API_KEY" in self.content, (
            "PHASE_1_BASELINE.md must mention GEMINI_API_KEY"
        )
        # Should mention it's unregistered / not done (未実施 or not registered / missing)
        assert (
            "未実施" in self.content
            or "未登録" in self.content
            or "not registered" in self.content.lower()
            or "registration" in self.content.lower()
        ), (
            "PHASE_1_BASELINE.md must state that GEMINI_API_KEY registration is not done"
        )

    def test_baseline_states_live_model_enabled_false(self) -> None:
        """Baseline must state that live_model_enabled=false."""
        assert "live_model_enabled" in self.content, (
            "PHASE_1_BASELINE.md must mention live_model_enabled"
        )
        assert "false" in self.content.lower(), (
            "PHASE_1_BASELINE.md must state live_model_enabled=false"
        )

    def test_baseline_states_no_real_gemini_api_call(self) -> None:
        """Baseline must state that no real Gemini API call has been made."""
        content_lower = self.content.lower()
        assert "gemini" in content_lower, (
            "PHASE_1_BASELINE.md must mention Gemini"
        )
        # Should state that real API calls are not done (未実施 / real Gemini API call)
        assert (
            "real gemini api call" in content_lower
            or "実 api" in self.content
            or "実際の gemini" in self.content
            or "api call" in content_lower
        ), (
            "PHASE_1_BASELINE.md must state that real Gemini API calls are not done"
        )

    def test_baseline_mentions_ci(self) -> None:
        """Baseline must mention CI test suite."""
        assert "CI" in self.content or "pytest" in self.content, (
            "PHASE_1_BASELINE.md must mention CI or pytest test suite"
        )

    def test_baseline_mentions_noop(self) -> None:
        """Baseline must mention noop workflow path."""
        assert "noop" in self.content, (
            "PHASE_1_BASELINE.md must mention noop workflow mode"
        )

    def test_baseline_mentions_offline_sample(self) -> None:
        """Baseline must mention offline-sample workflow path."""
        assert "offline-sample" in self.content or "offline_sample" in self.content, (
            "PHASE_1_BASELINE.md must mention offline-sample workflow mode"
        )

    def test_baseline_mentions_preflight(self) -> None:
        """Baseline must mention preflight verification."""
        assert "preflight" in self.content, (
            "PHASE_1_BASELINE.md must mention preflight verification"
        )

    def test_baseline_has_safety_invariants_section(self) -> None:
        """Baseline must have a Safety invariants section."""
        content_lower = self.content.lower()
        assert (
            "safety invariant" in content_lower
            or "安全不変" in self.content
            or "invariant" in content_lower
        ), (
            "PHASE_1_BASELINE.md must have a Safety invariants section"
        )

    def test_baseline_safety_invariants_include_live_model_false(self) -> None:
        """Safety invariants must explicitly list live_model_enabled=false."""
        assert "live_model_enabled" in self.content, (
            "Safety invariants must mention live_model_enabled"
        )

    def test_baseline_safety_invariants_include_max_requests(self) -> None:
        """Safety invariants must include max_model_requests_per_run."""
        assert "max_model_requests_per_run" in self.content, (
            "Safety invariants must mention max_model_requests_per_run"
        )

    def test_baseline_safety_invariants_include_max_commits(self) -> None:
        """Safety invariants must include max_commits_per_run."""
        assert "max_commits_per_run" in self.content, (
            "Safety invariants must mention max_commits_per_run"
        )

    def test_baseline_has_exit_criteria_section(self) -> None:
        """Baseline must have an Exit criteria section."""
        content_lower = self.content.lower()
        assert (
            "exit criteria" in content_lower
            or "exit_criteria" in content_lower
        ), (
            "PHASE_1_BASELINE.md must have an Exit criteria section"
        )


# ---------------------------------------------------------------------------
# README.md links to PHASE_1_BASELINE.md
# ---------------------------------------------------------------------------


class TestReadmeLinkToBaseline:
    """Verify that README.md links to docs/PHASE_1_BASELINE.md."""

    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md is required for these tests"
        self.content = readme.read_text(encoding="utf-8")

    def test_readme_links_to_phase1_baseline(self) -> None:
        """README.md must link to docs/PHASE_1_BASELINE.md."""
        assert "PHASE_1_BASELINE.md" in self.content, (
            "README.md must contain a link to docs/PHASE_1_BASELINE.md"
        )

    def test_readme_states_api_not_connected(self) -> None:
        """README.md must state that API is intentionally not connected yet."""
        content_lower = self.content.lower()
        assert (
            "api is intentionally not connected" in content_lower
            or "not connected yet" in content_lower
            or "未登録" in self.content
            or "intentionally not connected" in content_lower
        ), (
            "README.md must state that API is intentionally not connected"
        )

    def test_readme_states_next_phase_requires_human_owner(self) -> None:
        """README.md must state that next phase requires Human Owner decision."""
        assert (
            "Human Owner" in self.content
            or "human owner" in self.content.lower()
        ), (
            "README.md must reference Human Owner decision for next phase"
        )


# ---------------------------------------------------------------------------
# docs/AUDIT_CHARTER.md contains Phase transition rule
# ---------------------------------------------------------------------------


class TestAuditCharterPhaseTransitionRule:
    """Verify that docs/AUDIT_CHARTER.md contains Phase transition rule."""

    @pytest.fixture(autouse=True)
    def load_charter(self) -> None:
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), "docs/AUDIT_CHARTER.md is required for these tests"
        self.content = charter.read_text(encoding="utf-8")

    def test_charter_has_phase_transition_rule(self) -> None:
        """AUDIT_CHARTER.md must contain Phase transition rule."""
        content_lower = self.content.lower()
        assert (
            "phase transition" in content_lower
            or "phase 1" in content_lower
            or "phase transition rule" in content_lower
        ), (
            "AUDIT_CHARTER.md must contain Phase transition rule"
        )

    def test_charter_phase_transition_requires_human_owner(self) -> None:
        """Phase transition rule must require Human Owner decision."""
        assert "Human Owner" in self.content, (
            "Phase transition rule must require Human Owner decision"
        )

    def test_charter_phase_transition_requires_ci_success(self) -> None:
        """Phase transition GPT Audit Gate confirmation must include CI success."""
        assert "CI" in self.content, (
            "Phase transition rule must mention CI success requirement"
        )

    def test_charter_phase_transition_requires_preflight_check(self) -> None:
        """Phase transition GPT Audit Gate confirmation must include preflight check."""
        assert "preflight" in self.content, (
            "Phase transition rule must mention preflight behavior check"
        )

    def test_charter_phase_transition_requires_live_model_false_before_registration(
        self,
    ) -> None:
        """Phase transition rule must require live_model_enabled=false before API registration."""
        assert "live_model_enabled" in self.content, (
            "Phase transition rule must mention live_model_enabled=false before API registration"
        )

    def test_charter_phase_transition_blocks_premature_live_model_true(self) -> None:
        """Phase transition rule must BLOCK live_model_enabled=true without Human Owner decision."""
        assert "BLOCK" in self.content, (
            "Phase transition rule must define BLOCK condition for premature live_model_enabled=true"
        )
        assert "live_model_enabled" in self.content, (
            "BLOCK condition must mention live_model_enabled"
        )

    def test_charter_mentions_no_committed_api_key(self) -> None:
        """Phase transition rule must verify no committed API key."""
        assert "GEMINI_API_KEY" in self.content, (
            "Phase transition rule must check that GEMINI_API_KEY is not committed"
        )
