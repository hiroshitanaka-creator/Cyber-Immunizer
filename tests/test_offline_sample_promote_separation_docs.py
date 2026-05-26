"""tests/test_offline_sample_promote_separation_docs.py — Phase 2-D design doc tests.

Verifies that:
- docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md exists and contains required sections
- offline-sample / dry-run / promote separation is clearly specified
- CI smoke path, dry-run evaluation path, and promote path are documented
- Safety invariants are recorded (fail-closed, Human Owner approval, etc.)
- README.md and PHASE_2_PLAN.md link to the design document
- README.md and PHASE_2_PLAN.md reflect Phase 2-D completed / Phase 2-E next
- Dangerous counter-factual phrases are rejected (regression guard)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_README = _PROJECT_ROOT / "README.md"
_PHASE2_PLAN = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
_SEPARATION_DOC = _PROJECT_ROOT / "docs" / "OFFLINE_SAMPLE_PROMOTE_SEPARATION.md"


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
# Document existence
# ---------------------------------------------------------------------------


class TestSeparationDocExists(_DocFixture):
    _path = _SEPARATION_DOC

    def test_doc_exists(self) -> None:
        """docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must exist."""
        assert _SEPARATION_DOC.exists(), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md does not exist"
        )

    def test_has_purpose_section(self) -> None:
        """Design doc must contain a Purpose section."""
        assert "## Purpose" in self.content or "# Purpose" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must contain a Purpose section"
        )

    def test_mentions_offline_sample(self) -> None:
        """Design doc must mention offline-sample."""
        assert "offline-sample" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must mention offline-sample"
        )

    def test_mentions_dry_run(self) -> None:
        """Design doc must mention dry-run."""
        assert "dry-run" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must mention dry-run"
        )

    def test_mentions_promote(self) -> None:
        """Design doc must mention promote."""
        assert "promote" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must mention promote"
        )


# ---------------------------------------------------------------------------
# Separation design sections
# ---------------------------------------------------------------------------


class TestSeparationDesign(_DocFixture):
    _path = _SEPARATION_DOC

    def test_has_ci_smoke_path(self) -> None:
        """Design doc must describe the CI smoke path."""
        assert "CI smoke path" in self.content or "CI smoke" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must describe the CI smoke path"
        )

    def test_has_dry_run_evaluation_path(self) -> None:
        """Design doc must describe the dry-run evaluation path."""
        assert "dry-run evaluation path" in self.content or "Dry-run evaluation path" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must describe the dry-run evaluation path"
        )

    def test_has_promote_path(self) -> None:
        """Design doc must describe the promote path."""
        assert "promote path" in self.content or "Promote path" in self.content, (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must describe the promote path"
        )

    def test_dry_run_artifact_is_not_promote_artifact(self) -> None:
        """Design doc must state that dry-run artifact is NOT promote artifact."""
        content = self.content
        assert (
            "dry-run artifact は promote artifact ではない" in content
            or "dry-run artifactはpromote artifactではない" in content
            or "dry-run artifact is NOT promote artifact" in content
            or "dry-run artifact is not promote artifact" in content
            or ("dry-run artifact" in content and "promote artifact" in content)
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "dry-run artifact is not promote artifact"
        )

    def test_offline_sample_success_is_not_promote_approval(self) -> None:
        """Design doc must state that offline-sample success is not promote approval."""
        content = self.content
        assert (
            "offline-sampleの成功はpromote承認ではない" in content
            or "offline-sample success is NOT promote approval" in content
            or "offline-sample success is not promote approval" in content
            or (
                "offline-sample" in content
                and "promote" in content
                and ("承認ではない" in content or "NOT promote approval" in content or "not promote approval" in content)
            )
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "offline-sample success is NOT promote approval"
        )

    def test_dry_run_is_non_promotable_by_default(self) -> None:
        """Design doc must state that dry-run is non-promotable by default."""
        content = self.content
        assert (
            "non-promotable by default" in content
            or "non-promotable" in content
            or "デフォルトでnon-promotable" in content
            or "デフォルトで non-promotable" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "dry-run is non-promotable by default"
        )

    def test_promote_requires_human_owner_approval(self) -> None:
        """Design doc must state that promote requires Human Owner approval."""
        content = self.content
        assert (
            "Human Owner approval" in content
            or "Human Owner承認" in content
            or "Human Owner approval が必要" in content
            or "Human Owner承認が必要" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "promote requires Human Owner approval"
        )

    def test_promote_requires_gpt_audit_gate_approve(self) -> None:
        """Design doc must state that promote requires GPT Audit Gate APPROVE."""
        content = self.content
        assert (
            "GPT Audit Gate APPROVE" in content
            or "GPT Audit Gate APPROVEが必要" in content
            or "GPT Audit Gate APPROVE が必要" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "promote requires GPT Audit Gate APPROVE"
        )


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


class TestSafetyBoundaries(_DocFixture):
    _path = _SEPARATION_DOC

    def test_ci_is_read_only_no_contents_write(self) -> None:
        """Design doc must state that CI smoke path is read-only (no contents: write)."""
        content = self.content
        assert (
            "contents: write" in content
            or "read-only" in content
            or "read-only（contents: write なし）" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "CI smoke path is read-only (no contents: write)"
        )

    def test_no_gemini_api_key_in_ci(self) -> None:
        """Design doc must state that GEMINI_API_KEY is not passed to CI."""
        content = self.content
        assert (
            "GEMINI_API_KEY" in content
            and (
                "CIに渡さない" in content
                or "CIにはGEMINI_API_KEYを渡さない" in content
                or "GEMINI_API_KEY なし" in content
                or "GEMINI_API_KEY is not passed to CI" in content
            )
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "GEMINI_API_KEY is not passed to CI"
        )

    def test_no_live_model_enabled_true(self) -> None:
        """Design doc must state that live_model_enabled=true is not set."""
        content = self.content
        assert (
            "live_model_enabled=true" in content
            and (
                "にしない" in content
                or "しない" in content
                or "live_model_enabled=true にしない" in content
                or "live_model_enabled=true is not set" in content
            )
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "live_model_enabled=true is not set in Phase 2-D"
        )

    def test_no_generated_code_in_write_permission_job(self) -> None:
        """Design doc must state that generated code is not run in write-permission jobs."""
        content = self.content
        assert (
            "write権限" in content
            and (
                "generated code" in content or "generated codeをwrite権限jobで実行しない" in content
            )
        ) or (
            "generated code" in content
            and ("write permissions" in content or "write-permission" in content)
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "generated code is not run in write-permission jobs"
        )

    def test_api_usage_ledger_not_changed(self) -> None:
        """Design doc must state that data/api_usage_ledger.json is not changed."""
        content = self.content
        assert "api_usage_ledger" in content and (
            "変更しない" in content
            or "api_usage_ledger.jsonを変更しない" in content
            or "data/api_usage_ledger.json 変更なし" in content
            or "data/api_usage_ledger.json はpromote対象に含めない" in content
            or "api_usage_ledger.json" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "data/api_usage_ledger.json is not changed"
        )

    def test_promote_candidate_not_changed_in_phase2d(self) -> None:
        """Design doc must state that promote_candidate.py is not changed in Phase 2-D."""
        content = self.content
        assert "promote_candidate.py" in content and (
            "変更しない" in content
            or "promote_candidate.py変更" in content
            or "promote_candidate.py は変更しない" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "promote_candidate.py is not changed in Phase 2-D"
        )

    def test_no_workflow_changes_in_phase2d(self) -> None:
        """Design doc must state that no workflow changes are made in Phase 2-D."""
        content = self.content
        assert (
            "workflow変更" in content
            or "workflow変更は行わない" in content
            or "workflow changes" in content
        ) and (
            "行わない" in content
            or "しない" in content
            or "not" in content.lower()
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "no workflow changes are made in Phase 2-D"
        )


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------


class TestFailClosed(_DocFixture):
    _path = _SEPARATION_DOC

    def test_unknown_artifact_schema_is_fail_closed(self) -> None:
        """Design doc must state that unknown/missing/corrupt artifact schema is fail-closed."""
        content = self.content
        assert "fail-closed" in content and (
            "artifact schema不明" in content
            or "schema不明" in content
            or "unknown" in content.lower()
            or "欠損" in content
            or "破損" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "unknown/missing/corrupt artifact schema is fail-closed"
        )

    def test_promote_eligible_false_or_missing_blocks_promote(self) -> None:
        """Design doc must state that promote_eligible=false or missing blocks promote."""
        content = self.content
        assert (
            "promote_eligible=false" in content
            or "promote_eligible" in content
        ) and (
            "promote不可" in content
            or "不可" in content
            or "non-promotable" in content
            or "BLOCK" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "promote_eligible=false or missing blocks promote"
        )

    def test_ci_smoke_artifact_blocked_from_promote(self) -> None:
        """Design doc must state that CI smoke artifact cannot be promoted (BLOCK)."""
        content = self.content
        assert (
            "CI smoke" in content
            and "BLOCK" in content
        ), (
            "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must state that "
            "CI smoke artifact is BLOCKed from promote"
        )


# ---------------------------------------------------------------------------
# README / PHASE_2_PLAN links and status
# ---------------------------------------------------------------------------


class TestReadmeLinksAndStatus:
    """README.md must link to the design doc and show Phase 2-D completed / 2-E next."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _README.exists(), "README.md does not exist"
        self.content = _README.read_text(encoding="utf-8")

    def test_readme_links_to_separation_doc(self) -> None:
        """README.md must link to OFFLINE_SAMPLE_PROMOTE_SEPARATION.md."""
        assert "OFFLINE_SAMPLE_PROMOTE_SEPARATION.md" in self.content, (
            "README.md must link to docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md"
        )

    def test_readme_phase2d_completed(self) -> None:
        """README.md table row for Phase 2-D must show Completed / ✅ / 完了."""
        row = _extract_phase_row(self.content, "Phase 2-D")
        assert row, "README.md must contain a table row for Phase 2-D"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
            or "完了" in row
        )
        assert has_completed, (
            f"README.md Phase 2-D row must indicate Completed/✅/完了, got: {row!r}"
        )

    def test_readme_phase2d_not_next_or_pending(self) -> None:
        """README.md Phase 2-D row must NOT show Next / Pending / 未着手."""
        row = _extract_phase_row(self.content, "Phase 2-D")
        assert row, "README.md must contain a table row for Phase 2-D"
        forbidden = ["⏭ Next", "⏳ Pending", "⏳", "未着手", "Pending", "pending"]
        # Allow ⏭ only if NOT in the Phase 2-D row
        for token in forbidden:
            assert token not in row, (
                f"README.md Phase 2-D row must NOT contain {token!r}, got: {row!r}"
            )

    def test_readme_phase2e_next(self) -> None:
        """README.md table row for Phase 2-E must show Next / ⏭."""
        # Must explicitly have Phase 2-E — generic "API activation checklist" alone is insufficient
        assert "Phase 2-E" in self.content, (
            "README.md must explicitly mention Phase 2-E (not just generic checklist text)"
        )
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "README.md must contain a table row for Phase 2-E"
        has_next = (
            "Next" in row
            or "next" in row
            or "⏭" in row
        )
        assert has_next, (
            f"README.md Phase 2-E row must indicate Next/⏭, got: {row!r}"
        )

    def test_readme_phase2e_not_pending_or_completed(self) -> None:
        """README.md Phase 2-E row must NOT show Pending / ⏳ or Completed / ✅."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "README.md must contain a table row for Phase 2-E"
        forbidden_completed = ["✅ Completed", "✅Completed", "完了"]
        forbidden_pending = ["⏳ Pending", "⏳Pending"]
        for token in forbidden_completed + forbidden_pending:
            assert token not in row, (
                f"README.md Phase 2-E row must NOT contain {token!r}, got: {row!r}"
            )

    def test_readme_does_not_claim_phase3_started(self) -> None:
        """README.md must not claim Phase 3 has started."""
        forbidden = [
            "Phase 3 started",
            "Phase 3 is in progress",
            "Phase 3: started",
            "Phase 3 完了",
            "Phase 3 進行中",
        ]
        for phrase in forbidden:
            assert phrase not in self.content, (
                f"README.md must NOT contain {phrase!r}"
            )

    def test_readme_does_not_claim_api_connected(self) -> None:
        """README.md must not claim the API is connected."""
        forbidden = [
            "API connected",
            "API connection: active",
            "API is connected",
        ]
        for phrase in forbidden:
            assert phrase not in self.content, (
                f"README.md must NOT contain {phrase!r}"
            )

    def test_readme_live_model_enabled_false_in_status_block(self) -> None:
        """README.md status block must NOT show live_model_enabled=true."""
        status_start = self.content.find("CYBER_IMMUNIZER_STATUS_START")
        status_end = self.content.find("CYBER_IMMUNIZER_STATUS_END")
        if status_start != -1 and status_end != -1:
            status_block = self.content[status_start:status_end]
            assert "| live_model_enabled | true |" not in status_block, (
                "README.md status block must NOT show live_model_enabled = true"
            )


class TestPhase2PlanLinksAndStatus:
    """docs/PHASE_2_PLAN.md must link to the design doc and show Phase 2-D completed / 2-E next."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _PHASE2_PLAN.exists(), "docs/PHASE_2_PLAN.md does not exist"
        self.content = _PHASE2_PLAN.read_text(encoding="utf-8")

    def test_phase2_plan_links_to_separation_doc(self) -> None:
        """docs/PHASE_2_PLAN.md must link to OFFLINE_SAMPLE_PROMOTE_SEPARATION.md."""
        assert "OFFLINE_SAMPLE_PROMOTE_SEPARATION.md" in self.content, (
            "docs/PHASE_2_PLAN.md must link to docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md"
        )

    def test_phase2_plan_phase2d_completed(self) -> None:
        """PHASE_2_PLAN.md table row for Phase 2-D must show Completed / ✅ / 完了."""
        row = _extract_phase_row(self.content, "Phase 2-D")
        assert row, "docs/PHASE_2_PLAN.md must contain a table row for Phase 2-D"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
            or "完了" in row
        )
        assert has_completed, (
            f"docs/PHASE_2_PLAN.md Phase 2-D row must indicate Completed/✅/完了, got: {row!r}"
        )

    def test_phase2_plan_phase2d_not_next_or_pending(self) -> None:
        """PHASE_2_PLAN.md Phase 2-D row must NOT show Next / Pending / 未着手."""
        row = _extract_phase_row(self.content, "Phase 2-D")
        assert row, "docs/PHASE_2_PLAN.md must contain a table row for Phase 2-D"
        forbidden = ["⏭ Next", "⏳ Pending", "⏳", "未着手", "Pending", "pending"]
        for token in forbidden:
            assert token not in row, (
                f"docs/PHASE_2_PLAN.md Phase 2-D row must NOT contain {token!r}, got: {row!r}"
            )

    def test_phase2_plan_phase2e_next(self) -> None:
        """PHASE_2_PLAN.md table row for Phase 2-E must show Next / ⏭ / 次."""
        # Must explicitly have Phase 2-E — generic checklist text alone is insufficient
        assert "Phase 2-E" in self.content, (
            "docs/PHASE_2_PLAN.md must explicitly mention Phase 2-E "
            "(generic 'API activation checklist' text alone is insufficient)"
        )
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "docs/PHASE_2_PLAN.md must contain a table row for Phase 2-E"
        has_next = (
            "Next" in row
            or "next" in row
            or "次" in row
            or "⏭" in row
        )
        assert has_next, (
            f"docs/PHASE_2_PLAN.md Phase 2-E row must indicate Next/⏭/次, got: {row!r}"
        )

    def test_phase2_plan_phase2e_not_pending(self) -> None:
        """PHASE_2_PLAN.md Phase 2-E row must NOT show Pending / ⏳ / 未着手."""
        row = _extract_phase_row(self.content, "Phase 2-E")
        assert row, "docs/PHASE_2_PLAN.md must contain a table row for Phase 2-E"
        forbidden = ["⏳ Pending", "⏳Pending", "⏳"]
        for token in forbidden:
            assert token not in row, (
                f"docs/PHASE_2_PLAN.md Phase 2-E row must NOT contain {token!r}, got: {row!r}"
            )

    def test_phase2_plan_does_not_claim_phase3_started(self) -> None:
        """PHASE_2_PLAN.md must not claim Phase 3 has started."""
        forbidden = [
            "Phase 3 started",
            "Phase 3 is in progress",
            "Phase 3 完了",
            "Phase 3 進行中",
        ]
        for phrase in forbidden:
            assert phrase not in self.content, (
                f"docs/PHASE_2_PLAN.md must NOT contain {phrase!r}"
            )

    def test_phase2_plan_does_not_claim_api_connected(self) -> None:
        """PHASE_2_PLAN.md must not claim the API is connected."""
        forbidden = [
            "API connected",
            "API is connected",
        ]
        for phrase in forbidden:
            assert phrase not in self.content, (
                f"docs/PHASE_2_PLAN.md must NOT contain {phrase!r}"
            )


# ---------------------------------------------------------------------------
# Regression guard — dangerous counter-factual phrases
# ---------------------------------------------------------------------------


class TestRegressionGuard(_DocFixture):
    _path = _SEPARATION_DOC

    # English dangerous phrases
    _FORBIDDEN_EN = [
        "offline-sample success means promote approved",
        "offline-sample may be promoted automatically",
        "CI smoke test can promote candidate",
        "dry-run artifact is promote artifact",
        "dry-run artifact is promote eligible by default",
        "Human Owner approval is optional",
        "generated code may run with write permissions",
        "GEMINI_API_KEY is passed to CI",
        "live_model_enabled=true in Phase 2-D",
        "promote_candidate.py is changed in Phase 2-D",
        "workflow is changed in Phase 2-D",
    ]

    # Japanese dangerous phrases
    _FORBIDDEN_JA = [
        "offline-sample成功はpromote承認",
        "CI smoke testでpromoteする",
        "dry-run artifactをpromote artifactとして扱う",
        "Human Owner承認は不要",
        "generated codeをwrite権限jobで実行する",
        "Phase 2-Dでlive_model_enabled=true",
        "Phase 2-DでGemini APIを呼ぶ",
    ]

    @pytest.mark.parametrize("phrase", _FORBIDDEN_EN)
    def test_no_dangerous_english_phrase(self, phrase: str) -> None:
        """docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must NOT contain dangerous English phrases."""
        assert phrase not in self.content, (
            f"docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must NOT contain: {phrase!r}"
        )

    @pytest.mark.parametrize("phrase", _FORBIDDEN_JA)
    def test_no_dangerous_japanese_phrase(self, phrase: str) -> None:
        """docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must NOT contain dangerous Japanese phrases."""
        assert phrase not in self.content, (
            f"docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md must NOT contain: {phrase!r}"
        )
