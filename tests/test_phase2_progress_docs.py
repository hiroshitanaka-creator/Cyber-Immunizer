"""tests/test_phase2_progress_docs.py — Phase 2-A/B/C/D/E completion tests.

Verifies that:
- README.md explicitly records Phase 2-A, 2-B, 2-C, 2-D, 2-E as completed
- docs/PHASE_2_PLAN.md contains the same progress information
- Neither README nor PHASE_2_PLAN contains false completion claims
  (Phase 3 started, API connected, live_model_enabled=true)
- Phase 3 is not started
- API is not connected
- Phase 2 complete does not mean API connected

PR #26 Codex comment fixes:
1. Phase 2-E validation requires explicit "Phase 2-E" label (no skip if absent).
2. Phase 2-D must be verified as Completed (all variants), not as Next/Pending.
   Phase status is validated via Markdown table row extraction, not window search.

Phase 2-E update:
- Phase 2-E is now Completed (was Next in PR #26 state).
- Added regression guards for Phase 3 not started / API not connected.
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


def _extract_phase_row(content: str, phase_label: str) -> str:
    """Extract the Markdown table row where the FIRST column contains the given phase label.

    Scans every line of *content* for a table row (starting with '|') where
    the first column (the text immediately after the leading '|') contains
    *phase_label*.  This avoids false positives from rows where the label
    appears only in description columns (e.g. the test-coverage table).
    Returns the first matching line, or an empty string if none is found.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Split into columns: ['', col1, col2, ..., '']
        parts = stripped.split("|")
        if len(parts) >= 3 and phase_label in parts[1]:
            return line
    return ""


# ---------------------------------------------------------------------------
# README.md — Phase 2-A/B/C/D completed, Phase 2-E next
# ---------------------------------------------------------------------------


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


class TestReadmePhase2DCompleted(_DocFixture):
    """Phase 2-D must be marked as Completed in README.md.

    PR #26 Codex fix: replaced the old 'Phase 2-D is Next' guard with an
    explicit 'Phase 2-D is Completed' assertion validated via table row
    extraction.  All Completed variants (Completed / completed / ✅ / 完了)
    are accepted.  If the row still shows Next / Pending / ⏭ / ⏳ / 未着手 the
    test fails.
    """

    _path = _README

    def test_readme_phase2d_completed(self) -> None:
        """README.md Phase 2-D table row must show Completed / ✅ / 完了."""
        content = self.content
        assert "Phase 2-D" in content, "README.md must mention Phase 2-D"
        row = _extract_phase_row(content, "Phase 2-D")
        assert row, "README.md must contain a Markdown table row for Phase 2-D"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
            or "完了" in row
        )
        assert has_completed, (
            f"README.md Phase 2-D row must show Completed/✅/完了, got: {row!r}"
        )

    def test_readme_phase2d_not_next_or_pending(self) -> None:
        """README.md Phase 2-D row must NOT show Next / Pending / ⏭ / ⏳ / 未着手.

        PR #26 Codex fix: rejects all in-progress variants, not just '✅ Completed'.
        """
        content = self.content
        row = _extract_phase_row(content, "Phase 2-D")
        assert row, "README.md must contain a Markdown table row for Phase 2-D"
        forbidden_tokens = [
            "⏭ Next", "⏭Next", "Next", "next",
            "⏳ Pending", "⏳Pending", "⏳", "Pending", "pending",
            "未着手",
        ]
        for token in forbidden_tokens:
            assert token not in row, (
                f"README.md Phase 2-D row must NOT contain {token!r}, got: {row!r}"
            )


class TestReadmePhase2ECompleted(_DocFixture):
    """Phase 2-E must be marked as Completed in README.md.

    Phase 2-E update: Phase 2-E is now Completed (was Next in PR #26 state).
    Phase 2-E (API activation checklist hardening) is docs/tests only.
    """

    _path = _README

    def test_readme_phase2e_explicitly_present(self) -> None:
        """README.md must explicitly mention Phase 2-E (not just generic checklist text)."""
        assert "Phase 2-E" in self.content, (
            "README.md must explicitly mention Phase 2-E — "
            "generic 'API activation checklist' text alone is insufficient"
        )

    def test_readme_phase2e_is_completed(self) -> None:
        """README.md Phase 2-E table row must show Completed / ✅."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "README.md must contain a Markdown table row for Phase 2-E"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
        )
        assert has_completed, (
            f"README.md Phase 2-E row must indicate Completed/✅, got: {row!r}"
        )

    def test_readme_phase2e_not_next_or_pending(self) -> None:
        """README.md Phase 2-E row must NOT show Next / ⏭ / Pending."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "README.md must contain a Markdown table row for Phase 2-E"
        forbidden_tokens = ["⏭ Next", "⏭Next", "⏭", "⏳ Pending", "⏳Pending", "⏳"]
        for token in forbidden_tokens:
            assert token not in row, (
                f"README.md Phase 2-E row must NOT contain {token!r} — "
                f"Phase 2-E is completed, got: {row!r}"
            )


# ---------------------------------------------------------------------------
# docs/PHASE_2_PLAN.md — Phase 2-A/B/C/D completed, Phase 2-E next
# ---------------------------------------------------------------------------


class TestPhase2PlanPhase2ACompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2a_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-A is completed."""
        content = self.content
        assert "Phase 2-A" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-A"
        )
        row = _extract_phase_row(content, "Phase 2-A")
        if row:
            assert (
                "Completed" in row
                or "completed" in row
                or "✅" in row
            ), f"docs/PHASE_2_PLAN.md Phase 2-A row must indicate Completed, got: {row!r}"
        else:
            # Fallback: window check
            phase2a_pos = content.find("Phase 2-A")
            surrounding = content[phase2a_pos : phase2a_pos + 200]
            assert (
                "Completed" in surrounding
                or "completed" in surrounding
                or "✅" in surrounding
            ), "docs/PHASE_2_PLAN.md must indicate Phase 2-A is completed"


class TestPhase2PlanPhase2BCompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2b_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-B is completed."""
        content = self.content
        assert "Phase 2-B" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-B"
        )
        row = _extract_phase_row(content, "Phase 2-B")
        if row:
            assert (
                "Completed" in row
                or "completed" in row
                or "✅" in row
            ), f"docs/PHASE_2_PLAN.md Phase 2-B row must indicate Completed, got: {row!r}"
        else:
            phase2b_pos = content.find("Phase 2-B")
            surrounding = content[phase2b_pos : phase2b_pos + 200]
            assert (
                "Completed" in surrounding
                or "completed" in surrounding
                or "✅" in surrounding
            ), "docs/PHASE_2_PLAN.md must indicate Phase 2-B is completed"


class TestPhase2PlanPhase2CCompleted(_DocFixture):
    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2c_completed(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 2-C is completed."""
        content = self.content
        assert "Phase 2-C" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-C"
        )
        row = _extract_phase_row(content, "Phase 2-C")
        if row:
            assert (
                "Completed" in row
                or "completed" in row
                or "✅" in row
            ), f"docs/PHASE_2_PLAN.md Phase 2-C row must indicate Completed, got: {row!r}"
        else:
            phase2c_pos = content.find("Phase 2-C")
            surrounding = content[phase2c_pos : phase2c_pos + 200]
            assert (
                "Completed" in surrounding
                or "completed" in surrounding
                or "✅" in surrounding
            ), "docs/PHASE_2_PLAN.md must indicate Phase 2-C is completed"


class TestPhase2PlanPhase2DCompleted(_DocFixture):
    """Phase 2-D must be marked as Completed in PHASE_2_PLAN.md.

    PR #26 Codex fix: replaced the old 'Phase 2-D is Next' guard with an
    explicit 'Phase 2-D is Completed' assertion.  Table row extraction is
    used for precise validation.  All Completed variants and all in-progress
    variants (Next / Pending / ⏭ / ⏳ / 未着手) are handled.
    """

    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2d_completed(self) -> None:
        """PHASE_2_PLAN.md Phase 2-D table row must show Completed / ✅ / 完了."""
        content = self.content
        assert "Phase 2-D" in content, (
            "docs/PHASE_2_PLAN.md must mention Phase 2-D"
        )
        row = _extract_phase_row(content, "Phase 2-D")
        assert row, "docs/PHASE_2_PLAN.md must contain a Markdown table row for Phase 2-D"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
            or "完了" in row
        )
        assert has_completed, (
            f"docs/PHASE_2_PLAN.md Phase 2-D row must show Completed/✅/完了, got: {row!r}"
        )

    def test_phase2_plan_phase2d_not_next_or_pending(self) -> None:
        """PHASE_2_PLAN.md Phase 2-D row must NOT show Next / Pending / ⏭ / ⏳ / 未着手.

        PR #26 Codex fix: rejects all in-progress variants, not just '✅ Completed'.
        """
        content = self.content
        row = _extract_phase_row(content, "Phase 2-D")
        assert row, "docs/PHASE_2_PLAN.md must contain a Markdown table row for Phase 2-D"
        forbidden_tokens = [
            "⏭ Next", "⏭Next", "Next", "next",
            "⏳ Pending", "⏳Pending", "⏳", "Pending", "pending",
            "未着手",
        ]
        for token in forbidden_tokens:
            assert token not in row, (
                f"docs/PHASE_2_PLAN.md Phase 2-D row must NOT contain {token!r}, got: {row!r}"
            )


class TestPhase2PlanPhase2ECompleted(_DocFixture):
    """Phase 2-E must be marked as Completed in PHASE_2_PLAN.md.

    Phase 2-E update: Phase 2-E is now Completed (was Next in PR #26 state).
    Phase 2-E (API activation checklist hardening) is docs/tests only.
    """

    _path = _PHASE2_PLAN

    def test_phase2_plan_phase2e_explicitly_present(self) -> None:
        """PHASE_2_PLAN.md must explicitly mention Phase 2-E.

        Generic 'API activation checklist' / 'API接続前の運用チェックリスト' text
        alone is insufficient — Phase 2-E must be identified by its label.
        """
        assert "Phase 2-E" in self.content, (
            "docs/PHASE_2_PLAN.md must explicitly mention Phase 2-E — "
            "generic checklist text ('API activation checklist' / '運用チェックリスト整備') "
            "alone is insufficient"
        )

    def test_phase2_plan_phase2e_is_completed(self) -> None:
        """PHASE_2_PLAN.md Phase 2-E table row must show Completed / ✅."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, (
            "docs/PHASE_2_PLAN.md must contain a Markdown table row for Phase 2-E"
        )
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
        )
        assert has_completed, (
            f"docs/PHASE_2_PLAN.md Phase 2-E row must indicate Completed/✅, got: {row!r}"
        )

    def test_phase2_plan_phase2e_not_next_or_pending(self) -> None:
        """PHASE_2_PLAN.md Phase 2-E row must NOT show Next / ⏭ / ⏳ Pending / 未着手."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "docs/PHASE_2_PLAN.md must contain a Markdown table row for Phase 2-E"
        forbidden_tokens = [
            "⏭ Next", "⏭Next", "⏭",
            "⏳ Pending", "⏳Pending", "⏳",
            "未着手",
        ]
        for token in forbidden_tokens:
            assert token not in row, (
                f"docs/PHASE_2_PLAN.md Phase 2-E row must NOT contain {token!r} — "
                f"Phase 2-E is completed, got: {row!r}"
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
        forbidden_phrases = [
            "API connected",
            "API connection: active",
            "API is connected",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in self.readme, (
                f"README.md must NOT contain '{phrase}'"
            )

    def test_readme_live_model_enabled_matches_phase_in_status_block(self) -> None:
        """README.md status block live_model_enabled must match current phase.

        Phase 2 (live_model_enabled=false): true must NOT appear.
        Phase 3 (activation complete, PR #58-#62, live_model_enabled=true): true is correct.
        References to the concept outside the status block are allowed.
        """
        status_start = self.readme.find("CYBER_IMMUNIZER_STATUS_START")
        status_end = self.readme.find("CYBER_IMMUNIZER_STATUS_END")
        if status_start != -1 and status_end != -1:
            status_block = self.readme[status_start:status_end]
            if "Phase 3" in status_block:
                # Phase 3: live_model_enabled=true is correct (PR #58)
                assert "| live_model_enabled | true |" in status_block, (
                    "Phase 3 status block must show live_model_enabled = true (PR #58)"
                )
            else:
                # Phase 2: live_model_enabled=true must not appear
                assert "| live_model_enabled | true |" not in status_block, (
                    "Phase 2 status block must NOT show live_model_enabled = true"
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
        checklist_start = self.plan.find("Phase 2 進捗チェックリスト")
        if checklist_start != -1:
            next_section = self.plan.find("\n## ", checklist_start + 1)
            if next_section != -1:
                checklist_section = self.plan[checklist_start:next_section]
            else:
                checklist_section = self.plan[checklist_start:]
            assert "live_model_enabled=true" not in checklist_section, (
                "PHASE_2_PLAN.md progress checklist must NOT contain live_model_enabled=true"
            )


# ---------------------------------------------------------------------------
# Phase 3 not started / API not connected guards (Phase 2-E addition)
# ---------------------------------------------------------------------------


class TestPhase3NotStartedAndApiNotConnected:
    """Guard that Phase 3 is not started and API is not connected.

    Phase 2-E addition: explicit positive checks that README and PHASE_2_PLAN
    record the correct post-Phase-2 state.
    """

    @pytest.fixture(autouse=True)
    def _load_both(self) -> None:
        assert _README.exists()
        assert _PHASE2_PLAN.exists()
        self.readme = _README.read_text(encoding="utf-8")
        self.plan = _PHASE2_PLAN.read_text(encoding="utf-8")

    def test_readme_states_phase3_not_started(self) -> None:
        """README.md must state that Phase 3 is not started."""
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
            "README.md must state that Phase 3 is not started / requires Human Owner decision"
        )

    def test_readme_states_api_not_connected(self) -> None:
        """README.md must state that API remains not connected."""
        content_lower = self.readme.lower()
        assert (
            "api remains not connected" in content_lower
            or "api connection | not connected" in content_lower
            or "not connected" in content_lower
            or "未接続" in self.readme
        ), (
            "README.md must state that API remains not connected"
        )

    def test_readme_phase2_complete_does_not_claim_api_connected(self) -> None:
        """README.md Phase 2 completion note must not claim API is connected."""
        content_lower = self.readme.lower()
        assert "api connected" not in content_lower, (
            "README.md must NOT say 'API connected' — "
            "Phase 2 completion does not mean API is connected"
        )

    def test_phase2_plan_states_phase3_not_started(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 3 is not started."""
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
            "PHASE_2_PLAN.md must state that Phase 3 is not started / requires Human Owner decision"
        )

    def test_phase2_plan_states_api_not_connected(self) -> None:
        """PHASE_2_PLAN.md must state that API remains not connected / disconnected."""
        content_lower = self.plan.lower()
        assert (
            "api remains disconnected" in content_lower
            or "api 未接続" in self.plan
            or "api未接続" in self.plan
            or "not connected" in content_lower
            or "disconnected" in content_lower
            or "未接続" in self.plan
        ), (
            "PHASE_2_PLAN.md must state that API remains not connected"
        )

    def test_phase2_plan_phase2_complete_does_not_mean_api_connected(self) -> None:
        """PHASE_2_PLAN.md must clarify that Phase 2 completion ≠ API activated / Phase 3 begun."""
        content_lower = self.plan.lower()
        assert (
            "does not mean phase 3 is underway" in content_lower
            or "does not mean phase 3" in content_lower
            or "phase 3 requires human owner" in content_lower
            or (
                "phase 3" in content_lower
                and "human owner" in content_lower
                and ("requires" in content_lower or "decision" in content_lower)
            )
        ), (
            "PHASE_2_PLAN.md must clarify that Phase 2 complete does not mean Phase 3 is underway"
        )

    def test_readme_live_model_enabled_remains_false(self) -> None:
        """README.md must state that live_model_enabled remains false."""
        content_lower = self.readme.lower()
        assert (
            "live_model_enabled remains false" in content_lower
            or "live_model_enabled | false" in content_lower
            or (
                "live_model_enabled" in content_lower
                and "false" in content_lower
            )
        ), (
            "README.md must state that live_model_enabled remains false"
        )

    def test_phase2_plan_phase3_started_not_in_progress_table(self) -> None:
        """PHASE_2_PLAN.md progress checklist must NOT claim Phase 3 started."""
        checklist_start = self.plan.find("Phase 2 進捗チェックリスト")
        if checklist_start != -1:
            next_section = self.plan.find("\n## ", checklist_start + 1)
            if next_section != -1:
                checklist_section = self.plan[checklist_start:next_section]
            else:
                checklist_section = self.plan[checklist_start:]
            content_lower = checklist_section.lower()
            assert "phase 3 started" not in content_lower, (
                "PHASE_2_PLAN.md progress checklist must NOT claim Phase 3 started"
            )
            assert "api connected" not in content_lower, (
                "PHASE_2_PLAN.md progress checklist must NOT claim API connected"
            )
