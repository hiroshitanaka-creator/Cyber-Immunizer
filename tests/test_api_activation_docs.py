"""tests/test_api_activation_docs.py — Tests for API Activation Runbook (Phase 1-D).

Verifies that:
- docs/API_ACTIVATION_RUNBOOK.md exists and contains mandatory content
- README.md links to the runbook
- AUDIT_CHARTER.md contains API activation audit conditions
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


class TestApiActivationRunbookExists:
    def test_runbook_exists(self) -> None:
        """docs/API_ACTIVATION_RUNBOOK.md must exist."""
        runbook = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"
        assert runbook.exists(), (
            "docs/API_ACTIVATION_RUNBOOK.md is missing. "
            "This file is required for Phase 1-D API activation governance."
        )

    def test_runbook_is_not_empty(self) -> None:
        """docs/API_ACTIVATION_RUNBOOK.md must not be empty."""
        runbook = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"
        assert runbook.exists(), "docs/API_ACTIVATION_RUNBOOK.md does not exist"
        content = runbook.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, (
            "docs/API_ACTIVATION_RUNBOOK.md appears to be nearly empty"
        )


# ---------------------------------------------------------------------------
# Runbook content tests
# ---------------------------------------------------------------------------


class TestApiActivationRunbookContent:
    @pytest.fixture(autouse=True)
    def load_runbook(self) -> None:
        runbook = _PROJECT_ROOT / "docs" / "API_ACTIVATION_RUNBOOK.md"
        assert runbook.exists(), (
            "docs/API_ACTIVATION_RUNBOOK.md is required for these tests"
        )
        self.content = runbook.read_text(encoding="utf-8")

    def test_runbook_mentions_github_secrets_registration(self) -> None:
        """Runbook must explain how to register GEMINI_API_KEY in GitHub Secrets."""
        content_lower = self.content.lower()
        assert "GEMINI_API_KEY" in self.content, (
            "Runbook must mention GEMINI_API_KEY"
        )
        assert "github secrets" in content_lower or "secrets" in content_lower, (
            "Runbook must explain GitHub Secrets registration"
        )

    def test_runbook_prohibits_api_key_commit(self) -> None:
        """Runbook must explicitly prohibit committing API key to repository."""
        # Must mention prohibition of committing key
        content_lower = self.content.lower()
        assert "コミット" in self.content or "commit" in content_lower, (
            "Runbook must mention prohibition of committing API key"
        )
        # Must contain a prohibition section
        assert "禁止" in self.content or "禁止事項" in self.content or "must not" in content_lower, (
            "Runbook must have a prohibition / must-not section"
        )

    def test_runbook_states_live_model_enabled_false(self) -> None:
        """Runbook must state that live_model_enabled remains false."""
        assert "live_model_enabled" in self.content, (
            "Runbook must mention live_model_enabled"
        )
        assert "false" in self.content.lower(), (
            "Runbook must mention that live_model_enabled stays false"
        )

    def test_runbook_states_live_model_enabled_requires_reviewed_pr(self) -> None:
        """Runbook must state that live_model_enabled=true requires a reviewed PR."""
        assert "live_model_enabled" in self.content, (
            "Runbook must mention live_model_enabled"
        )
        # Must reference reviewed PR / レビュー済みPR
        content_lower = self.content.lower()
        assert "レビュー済みpr" in content_lower or "reviewed pr" in content_lower or (
            "レビュー" in self.content and "PR" in self.content
        ), (
            "Runbook must state that live_model_enabled=true requires a reviewed PR"
        )

    def test_runbook_prohibits_cron_gemini_paid_credit(self) -> None:
        """Runbook must prohibit running gemini-paid-credit on a cron schedule."""
        content_lower = self.content.lower()
        assert "cron" in content_lower or "スケジュール" in self.content, (
            "Runbook must mention prohibition of cron/scheduled gemini-paid-credit execution"
        )
        assert "gemini-paid-credit" in content_lower or "paid-credit" in content_lower, (
            "Runbook must mention gemini-paid-credit in the prohibition context"
        )

    def test_runbook_prohibits_overwriting_malformed_ledger(self) -> None:
        """Runbook must state not to overwrite a malformed ledger without inspection."""
        content_lower = self.content.lower()
        assert (
            "ledger" in content_lower
            or "api_usage_ledger" in content_lower
        ), (
            "Runbook must mention the API usage ledger"
        )
        assert (
            "上書き" in self.content
            or "overwrite" in content_lower
            or "勝手に" in self.content
        ), (
            "Runbook must mention not to overwrite a malformed ledger without inspection"
        )


# ---------------------------------------------------------------------------
# README link tests
# ---------------------------------------------------------------------------


class TestReadmeLinksToRunbook:
    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md is required for these tests"
        self.content = readme.read_text(encoding="utf-8")

    def test_readme_links_to_api_activation_runbook(self) -> None:
        """README.md must contain a link to docs/API_ACTIVATION_RUNBOOK.md."""
        assert "API_ACTIVATION_RUNBOOK.md" in self.content, (
            "README.md must link to docs/API_ACTIVATION_RUNBOOK.md"
        )

    def test_readme_runbook_link_is_near_phase1c_section(self) -> None:
        """The runbook link in README must appear near the Phase 1-C / preflight section."""
        runbook_pos = self.content.find("API_ACTIVATION_RUNBOOK.md")
        assert runbook_pos != -1, "docs/API_ACTIVATION_RUNBOOK.md not found in README"

        # Phase 1-C section should appear in the README
        phase1c_pos = self.content.find("Phase 1-C")
        assert phase1c_pos != -1, "Phase 1-C section not found in README"

        # The runbook link must appear within a reasonable distance (5000 chars) of Phase 1-C
        distance = abs(runbook_pos - phase1c_pos)
        assert distance <= 5000, (
            f"Runbook link ({runbook_pos}) is too far from Phase 1-C section ({phase1c_pos}). "
            f"Distance={distance}, expected <= 5000 chars."
        )

    def test_readme_states_github_secrets_only(self) -> None:
        """README must state that GEMINI_API_KEY is stored only in GitHub Secrets."""
        # Find the runbook link section and check nearby text
        assert "GEMINI_API_KEY" in self.content, (
            "README must mention GEMINI_API_KEY in the runbook reference section"
        )
        content_lower = self.content.lower()
        assert "github secrets" in content_lower or "secrets" in content_lower, (
            "README must mention that GEMINI_API_KEY is stored in GitHub Secrets"
        )

    def test_readme_states_live_model_enabled_pr_only(self) -> None:
        """README must state that live_model_enabled=true change requires a reviewed PR."""
        assert "live_model_enabled" in self.content, (
            "README must mention live_model_enabled"
        )
        content_lower = self.content.lower()
        assert "レビュー済みpr" in content_lower or "reviewed pr" in content_lower or (
            "レビュー" in self.content and "PR" in self.content
        ), (
            "README must state that live_model_enabled=true requires a reviewed PR"
        )


# ---------------------------------------------------------------------------
# AUDIT_CHARTER.md API activation condition tests
# ---------------------------------------------------------------------------


class TestAuditCharterApiActivationConditions:
    @pytest.fixture(autouse=True)
    def load_charter(self) -> None:
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), (
            "docs/AUDIT_CHARTER.md is required for these tests"
        )
        self.content = charter.read_text(encoding="utf-8")

    def test_charter_has_api_activation_section(self) -> None:
        """AUDIT_CHARTER.md must have an API activation audit section."""
        content_lower = self.content.lower()
        assert (
            "api activation" in content_lower
            or "api有効化" in self.content
            or "Phase 1-D" in self.content
        ), (
            "AUDIT_CHARTER.md must have an API activation audit section (Phase 1-D)"
        )

    def test_charter_api_block_includes_gemini_key_exposure(self) -> None:
        """AUDIT_CHARTER.md API activation BLOCK must include GEMINI_API_KEY exposure."""
        assert "GEMINI_API_KEY" in self.content, (
            "AUDIT_CHARTER.md must mention GEMINI_API_KEY in API activation BLOCK conditions"
        )
        content_lower = self.content.lower()
        assert "露出" in self.content or "exposed" in content_lower or "漏洩" in self.content or (
            "含まれている" in self.content
        ), (
            "AUDIT_CHARTER.md must mention GEMINI_API_KEY exposure as a BLOCK condition"
        )

    def test_charter_api_block_includes_cron_execution(self) -> None:
        """AUDIT_CHARTER.md API activation BLOCK must include cron execution prohibition."""
        content_lower = self.content.lower()
        assert "cron" in content_lower or "スケジュール" in self.content, (
            "AUDIT_CHARTER.md must include cron/scheduled execution as a BLOCK condition"
        )

    def test_charter_api_block_includes_budget_fail_open(self) -> None:
        """AUDIT_CHARTER.md API activation BLOCK must include budget cap fail-open."""
        content_lower = self.content.lower()
        assert (
            "budget" in content_lower
            or "予算" in self.content
            or "fail-open" in content_lower
        ), (
            "AUDIT_CHARTER.md must include budget cap fail-open as a BLOCK condition"
        )

    def test_charter_api_approve_includes_preflight_confirmation(self) -> None:
        """AUDIT_CHARTER.md API activation APPROVE must require preflight confirmation."""
        content_lower = self.content.lower()
        assert "preflight" in content_lower, (
            "AUDIT_CHARTER.md APPROVE conditions must require preflight confirmation"
        )

    def test_charter_api_approve_includes_reviewed_pr(self) -> None:
        """AUDIT_CHARTER.md API activation APPROVE must require a reviewed PR."""
        content_lower = self.content.lower()
        assert "レビュー済みpr" in content_lower or "reviewed pr" in content_lower or (
            "レビュー" in self.content and "PR" in self.content
        ), (
            "AUDIT_CHARTER.md APPROVE conditions must require a reviewed PR"
        )

    def test_charter_api_approve_includes_ledger_confirmation(self) -> None:
        """AUDIT_CHARTER.md API activation APPROVE must require ledger recording confirmation."""
        content_lower = self.content.lower()
        assert (
            "ledger" in content_lower
            or "api_usage_ledger" in content_lower
            or "記録" in self.content
        ), (
            "AUDIT_CHARTER.md APPROVE conditions must require ledger recording confirmation"
        )
