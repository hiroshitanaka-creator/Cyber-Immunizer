"""tests/test_phase2_progress_docs.py — Phase 2-A/B/C completion progress tests.

Verifies that:
- README.md explicitly records Phase 2-A, 2-B, 2-C as completed
- README.md records Phase 2-D as Next
- docs/PHASE_2_PLAN.md contains the same progress information
- docs/PHASE_2_PLAN.md records Phase 2-E as Pending
- Neither README nor PHASE_2_PLAN contains false completion claims
  (Phase 3 started, API connected, live_model_enabled=true)
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
# README.md — Phase 2-A/B/C completed, Phase 2-D next
# ---------------------------------------------------------------------------


def _any_occurrence_has_marker(content: str, tag: str, markers: list[str], window: int = 200) -> bool:
    """Return True if ANY occurrence of `tag` in `content` has one of `markers` within `window` chars."""
    idx = 0
    while True:
        pos = content.find(tag, idx)
        if pos == -1:
            return False
        surrounding = content[pos : pos + window]
        if any(m in surrounding for m in markers):
            return True
        idx = pos + 1
    return False


class TestReadmePhase2ACompleted(_DocFixture):
    _path = _README

    def test_readme_phase2a_completed(self) -> None:
        """README.md must state that Phase 2-A (README dashboard accuracy) is completed."""
        content = self.content
        assert "Phase 2-A" in content, "README.md must mention Phase 2-A"
        assert _any_occurrence_has_marker(
            content, "Phase 2-A", ["Completed", "completed", "✅"]
        ), (
            "README.md must indicate that Phase 2-A is completed "
            "(e.g. 'Completed' or '✅' near 'Phase 2-A')"
        )


class TestReadmePhase2BCompleted(_DocFixture):
    _path = _README

    def test_readme_phase2b_completed(self) -> None:
        """README.md must state that Phase 2-B (rollback/backtrack design) is completed."""
        content = self.content
        assert "Phase 2-B" in content, "README.md must mention Phase 2-B"
        assert _any_occurrence_has_marker(
            content, "Phase 2-B", ["Completed", "completed", "✅"]
        ), (
            "README.md must indicate that Phase 2-B is completed "
            "(e.g. 'Completed' or '✅' near 'Phase 2-B')"
        )


class TestReadmePhase2CCompleted(_DocFixture):
    _path = _README

    def test_readme_phase2c_completed(self) -> None:
        """README.md must state that Phase 2-C (evolution_history audit) is completed."""
        content = self.content
        assert "Phase 2-C" in content, "README.md must mention Phase 2-C"
        assert _any_occurrence_has_marker(
            content, "Phase 2-C", ["Completed", "completed", "✅"]
        ), (
            "README.md must indicate that Phase 2-C is completed "
            "(e.g. 'Completed' or '✅' near 'Phase 2-C')"
        )


class TestReadmePhase2DNext(_DocFixture):
    _path = _README

    def test_readme_phase2d_is_next(self) -> None:
        """README.md must indicate that Phase 2-D is the Next item."""
        content = self.content
        assert "Phase 2-D" in content, "README.md must mention Phase 2-D"
        assert _any_occurrence_has_marker(
            content, "Phase 2-D", ["Next", "next", "⏭"], window=250
        ), (
            "README.md must indicate that Phase 2-D is the Next item "
            "(e.g. 'Next' or '⏭' near 'Phase 2-D')"
        )


# ---------------------------------------------------------------------------
# docs/PHASE_2_PLAN.md — Phase 2-A/B/C completed, Phase 2-D next, Phase 2-E pending
# ---------------------------------------------------------------------------


class TestPhase2PlanPhase2ACompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2a_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-A is completed."""
        content = self.content
        assert "Phase 2-A" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-A"
        )
        phase2a_pos = content.find("Phase 2-A")
        surrounding = content[phase2a_pos : phase2a_pos + 200]
        assert (
            "Completed" in surrounding
            or "completed" in surrounding
            or "✅" in surrounding
        ), (
            "docs/PHASE_2_PLAN.md must indicate Phase 2-A is completed"
        )


class TestPhase2PlanPhase2BCompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2b_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-B is completed."""
        content = self.content
        assert "Phase 2-B" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-B"
        )
        phase2b_pos = content.find("Phase 2-B")
        surrounding = content[phase2b_pos : phase2b_pos + 200]
        assert (
            "Completed" in surrounding
            or "completed" in surrounding
            or "✅" in surrounding
        ), (
            "docs/PHASE_2_PLAN.md must indicate Phase 2-B is completed"
        )


class TestPhase2PlanPhase2CCompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2c_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-C is completed."""
        content = self.content
        assert "Phase 2-C" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-C"
        )
        phase2c_pos = content.find("Phase 2-C")
        surrounding = content[phase2c_pos : phase2c_pos + 200]
        assert (
            "Completed" in surrounding
            or "completed" in surrounding
            or "✅" in surrounding
        ), (
            "docs/PHASE_2_PLAN.md must indicate Phase 2-C is completed"
        )


class TestPhase2PlanPhase2DNext(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2d_is_next(self) -> None:
        """PHASE_2_PLAN.md must indicate that Phase 2-D is Next."""
        content = self.content
        assert "Phase 2-D" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-D"
        )
        phase2d_pos = content.find("Phase 2-D")
        surrounding = content[phase2d_pos : phase2d_pos + 250]
        assert (
            "Next" in surrounding
            or "next" in surrounding
            or "次" in surrounding
            or "⏭" in surrounding
        ), (
            "docs/PHASE_2_PLAN.md must indicate that Phase 2-D is the Next item"
        )


class TestPhase2PlanPhase2EPending(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2e_pending(self) -> None:
        """PHASE_2_PLAN.md must mention Phase 2-E (API activation checklist) as Pending."""
        content = self.content
        # Either Phase 2-E explicitly or the API activation checklist item as pending
        has_phase2e = "Phase 2-E" in content
        has_api_checklist = (
            "API activation checklist" in content
            or "API接続前の運用チェックリスト" in content
            or "運用チェックリスト整備" in content
        )
        assert has_phase2e or has_api_checklist, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-E "
            "or the API activation checklist item"
        )
        # Must indicate pending / not started
        if has_phase2e:
            phase2e_pos = content.find("Phase 2-E")
            surrounding = content[phase2e_pos : phase2e_pos + 250]
            assert (
                "Pending" in surrounding
                or "pending" in surrounding
                or "未着手" in surrounding
                or "⏳" in surrounding
            ), (
                "docs/PHASE_2_PLAN.md must indicate Phase 2-E is Pending"
            )


# ---------------------------------------------------------------------------
# Regression guard — no false completion / connection claims
# ---------------------------------------------------------------------------


class TestNoFalseCompletionClaims:
    """Guard against false claims in README.md and PHASE_2_PLAN.md."""

    @pytest.fixture(autouse=True)
    def _load_both(self) -> None:
        assert _README.exists()
        assert _PHASE2_PLAN.exists()
        self.readme = _README.read_text(encoding="utf-8")
        self.plan = _PHASE2_PLAN.read_text(encoding="utf-8")

    def test_readme_does_not_claim_phase3_started(self) -> None:
        """README.md must not claim that Phase 3 has started."""
        forbidden_phrases = [
            "Phase 3 started",
            "Phase 3 is in progress",
            "Phase 3: started",
            "Phase 3 完了",
            "Phase 3 進行中",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self.readme, (
                f"README.md must NOT contain '{phrase}' — Phase 3 has not started"
            )

    def test_readme_does_not_claim_api_connected(self) -> None:
        """README.md must not claim that the API is connected."""
        # The status block says 'Not connected' which is correct
        # We check that no claim of API connection is present
        forbidden_phrases = [
            "API connected",
            "API connection: active",
            "API is connected",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self.readme, (
                f"README.md must NOT contain '{phrase}'"
            )

    def test_readme_does_not_contain_live_model_enabled_true_as_setting(self) -> None:
        """README.md must not contain live_model_enabled=true as a current setting value.

        The status block must retain live_model_enabled = false.
        References to the concept (e.g., in gate descriptions) are allowed,
        but the current status must be false.
        """
        # The status block line is: | live_model_enabled | false |
        # Check that the status block does not show true
        status_start = self.readme.find("CYBER_IMMUNIZER_STATUS_START")
        status_end = self.readme.find("CYBER_IMMUNIZER_STATUS_END")
        if status_start != -1 and status_end != -1:
            status_block = self.readme[status_start:status_end]
            assert "| live_model_enabled | true |" not in status_block, (
                "README.md status block must NOT show live_model_enabled = true"
            )

    def test_phase2_plan_does_not_claim_phase3_started(self) -> None:
        """PHASE_2_PLAN.md must not claim that Phase 3 has started."""
        forbidden_phrases = [
            "Phase 3 started",
            "Phase 3 is in progress",
            "Phase 3 完了",
            "Phase 3 進行中",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self.plan, (
                f"docs/PHASE_2_PLAN.md must NOT contain '{phrase}'"
            )

    def test_phase2_plan_does_not_claim_api_connected(self) -> None:
        """PHASE_2_PLAN.md must not claim that the API is connected."""
        forbidden_phrases = [
            "API connected",
            "API is connected",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self.plan, (
                f"docs/PHASE_2_PLAN.md must NOT contain '{phrase}'"
            )

    def test_phase2_plan_does_not_contain_live_model_true_in_progress_table(
        self,
    ) -> None:
        """PHASE_2_PLAN.md progress table must not contain live_model_enabled=true."""
        # Find the progress checklist section
        checklist_start = self.plan.find("Phase 2 進捗チェックリスト")
        if checklist_start != -1:
            # Extract up to the next section
            next_section = self.plan.find("\n## ", checklist_start + 1)
            if next_section != -1:
                checklist_section = self.plan[checklist_start:next_section]
            else:
                checklist_section = self.plan[checklist_start:]
            assert "live_model_enabled=true" not in checklist_section, (
                "PHASE_2_PLAN.md progress checklist must NOT contain live_model_enabled=true"
            )

    def test_readme_phase2d_is_not_marked_completed(self) -> None:
        """README.md must NOT mark Phase 2-D as completed — it is Next, not done."""
        content = self.readme
        # Find all occurrences of Phase 2-D
        idx = 0
        while True:
            pos = content.find("Phase 2-D", idx)
            if pos == -1:
                break
            surrounding = content[pos : pos + 200]
            # The surrounding must NOT say "Completed" right after Phase 2-D in the table row
            # Check that no table row says Phase 2-D ... Completed
            lines_around = surrounding.split("\n")
            for line in lines_around[:3]:
                if "Phase 2-D" in line:
                    assert "✅ Completed" not in line, (
                        f"README.md must NOT mark Phase 2-D as Completed: {line!r}"
                    )
            idx = pos + 1
