"""tests/test_update_readme.py — Tests for README dashboard Phase 2 status block.

Verifies that scripts/update_readme.py:
- Only modifies content inside the status block markers
- Includes all required Phase 2 fields
- Correctly reads values from genome.json
- Shows BLOCKED message when live_model_enabled=true

All tests use tmp_path so that real README.md is never mutated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.update_readme import update_readme, _build_status_block, _GENOME_PATH

_STATUS_START = "<!-- CYBER_IMMUNIZER_STATUS_START -->"
_STATUS_END = "<!-- CYBER_IMMUNIZER_STATUS_END -->"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL_BEFORE = "## SENTINEL_SECTION_BEFORE"
_SENTINEL_AFTER = "## SENTINEL_SECTION_AFTER"

_MINIMAL_GENOME = {
    "generation": 1,
    "current_detector_hash": "aabbccdd" * 8,
    "best_score": 100.0,
    "last_updated": "2026-01-01T00:00:00Z",
    "live_model_enabled": False,
    "api_mode": "gemini_paid_credit",
    "model_provider": "gemini",
    "max_model_requests_per_run": 1,
    "max_commits_per_run": 1,
    "monthly_api_budget_usd": 10.0,
    "daily_api_budget_usd": 0.25,
    "send_repository_full_text": False,
    "send_raw_payloads": False,
    "send_secrets": False,
}


def _make_readme(tmp_path: Path, extra_before: str = "", extra_after: str = "") -> Path:
    """Create a minimal README.md with status block markers."""
    content = (
        f"{_SENTINEL_BEFORE}\n\n"
        f"Some content before the block.\n"
        f"{extra_before}\n"
        f"{_STATUS_START}\n"
        f"Old status content\n"
        f"{_STATUS_END}\n"
        f"\n{extra_after}"
        f"{_SENTINEL_AFTER}\n"
    )
    p = tmp_path / "README.md"
    p.write_text(content, encoding="utf-8")
    return p


def _make_readme_no_block(tmp_path: Path) -> Path:
    """Create a README.md WITHOUT status block markers."""
    content = f"{_SENTINEL_BEFORE}\nSome content.\n{_SENTINEL_AFTER}\n"
    p = tmp_path / "README.md"
    p.write_text(content, encoding="utf-8")
    return p


def _make_genome(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a genome.json with optional field overrides."""
    data = dict(_MINIMAL_GENOME)
    if overrides:
        data.update(overrides)
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def _extract_block(text: str) -> str:
    """Extract content between status block markers (inclusive)."""
    start = text.find(_STATUS_START)
    end = text.find(_STATUS_END)
    if start == -1 or end == -1:
        return ""
    return text[start:end + len(_STATUS_END)]


def _run_update(tmp_path: Path, genome_overrides: dict | None = None) -> tuple[str, str]:
    """
    Run update_readme against isolated files.
    Returns (full_readme_content, status_block_content).
    """
    readme_path = _make_readme(tmp_path)
    genome_path = _make_genome(tmp_path, genome_overrides)

    # Patch module-level paths to use tmp_path files
    import scripts.update_readme as mod
    original_genome = mod._GENOME_PATH
    original_history = mod._HISTORY_PATH
    original_threats = mod._THREATS_PATH
    original_report = mod._REPORT_PATH

    mod._GENOME_PATH = genome_path
    mod._HISTORY_PATH = tmp_path / "evolution_history.json"
    (tmp_path / "evolution_history.json").write_text("[]")
    mod._THREATS_PATH = tmp_path / "active_threats.json"
    (tmp_path / "active_threats.json").write_text("[]")
    mod._REPORT_PATH = tmp_path / "nonexistent_report.json"  # doesn't exist → fitness=None

    try:
        success = update_readme(readme_path)
        assert success, "update_readme returned False"
        content = readme_path.read_text(encoding="utf-8")
        block = _extract_block(content)
        return content, block
    finally:
        mod._GENOME_PATH = original_genome
        mod._HISTORY_PATH = original_history
        mod._THREATS_PATH = original_threats
        mod._REPORT_PATH = original_report


# ---------------------------------------------------------------------------
# Tests: status block preservation of content outside the markers
# ---------------------------------------------------------------------------

class TestStatusBlockPreservation:
    """update_readme.py must NOT modify content outside the status block."""

    def test_content_before_block_is_unchanged(self, tmp_path: Path) -> None:
        """Text before the status block markers must be byte-for-byte preserved."""
        content, _ = _run_update(tmp_path)
        assert _SENTINEL_BEFORE in content, (
            "Content before the status block must be preserved"
        )
        assert "Some content before the block." in content, (
            "Paragraph before the status block must be preserved"
        )

    def test_content_after_block_is_unchanged(self, tmp_path: Path) -> None:
        """Text after the status block markers must be byte-for-byte preserved."""
        content, _ = _run_update(tmp_path)
        assert _SENTINEL_AFTER in content, (
            "Content after the status block must be preserved"
        )

    def test_markers_still_present(self, tmp_path: Path) -> None:
        """Both status block markers must still be present after update."""
        content, _ = _run_update(tmp_path)
        assert _STATUS_START in content
        assert _STATUS_END in content

    def test_only_one_status_start_marker(self, tmp_path: Path) -> None:
        """There must be exactly one STATUS_START marker."""
        content, _ = _run_update(tmp_path)
        assert content.count(_STATUS_START) == 1

    def test_only_one_status_end_marker(self, tmp_path: Path) -> None:
        """There must be exactly one STATUS_END marker."""
        content, _ = _run_update(tmp_path)
        assert content.count(_STATUS_END) == 1

    def test_readme_without_block_gets_block_appended(self, tmp_path: Path) -> None:
        """A README without markers gets the block appended without touching existing text."""
        import scripts.update_readme as mod
        original_genome = mod._GENOME_PATH
        original_history = mod._HISTORY_PATH
        original_threats = mod._THREATS_PATH
        original_report = mod._REPORT_PATH

        readme_path = _make_readme_no_block(tmp_path)
        genome_path = _make_genome(tmp_path)
        mod._GENOME_PATH = genome_path
        mod._HISTORY_PATH = tmp_path / "evolution_history.json"
        (tmp_path / "evolution_history.json").write_text("[]")
        mod._THREATS_PATH = tmp_path / "active_threats.json"
        (tmp_path / "active_threats.json").write_text("[]")
        mod._REPORT_PATH = tmp_path / "nonexistent_report.json"

        try:
            success = update_readme(readme_path)
            content = readme_path.read_text(encoding="utf-8")
        finally:
            mod._GENOME_PATH = original_genome
            mod._HISTORY_PATH = original_history
            mod._THREATS_PATH = original_threats
            mod._REPORT_PATH = original_report

        assert success
        assert _SENTINEL_BEFORE in content
        assert _SENTINEL_AFTER in content
        assert _STATUS_START in content
        assert _STATUS_END in content


# ---------------------------------------------------------------------------
# Tests: Phase 2 mandatory fields in status block
# ---------------------------------------------------------------------------

class TestPhase2MandatoryFields:
    """All required Phase 2 fields must appear in the status block."""

    def test_current_phase_field_present(self, tmp_path: Path) -> None:
        """Status block must contain 'Current Phase' field."""
        _, block = _run_update(tmp_path)
        assert "Current Phase" in block, (
            "Status block must contain 'Current Phase' field"
        )

    def test_current_phase_value_is_phase2(self, tmp_path: Path) -> None:
        """Status block must display 'Phase 2 — API-disconnected operations'."""
        _, block = _run_update(tmp_path)
        assert "Phase 2 — API-disconnected operations" in block, (
            "Status block must show 'Phase 2 — API-disconnected operations'"
        )

    def test_api_connection_field_present(self, tmp_path: Path) -> None:
        """Status block must contain 'API Connection' field."""
        _, block = _run_update(tmp_path)
        assert "API Connection" in block, (
            "Status block must contain 'API Connection' field"
        )

    def test_live_model_enabled_false_displayed(self, tmp_path: Path) -> None:
        """Status block must display live_model_enabled = false."""
        _, block = _run_update(tmp_path)
        assert "live_model_enabled" in block, (
            "Status block must contain 'live_model_enabled'"
        )
        assert "| live_model_enabled | false |" in block, (
            "Status block must show live_model_enabled = false when genome has false"
        )

    def test_api_mode_displayed(self, tmp_path: Path) -> None:
        """Status block must display API Mode from genome.json."""
        _, block = _run_update(tmp_path)
        assert "API Mode" in block, "Status block must contain 'API Mode'"
        assert "gemini_paid_credit" in block, (
            "Status block must show the api_mode value from genome.json"
        )

    def test_model_provider_displayed(self, tmp_path: Path) -> None:
        """Status block must display Model Provider from genome.json."""
        _, block = _run_update(tmp_path)
        assert "Model Provider" in block, "Status block must contain 'Model Provider'"
        assert "gemini" in block, (
            "Status block must show the model_provider value from genome.json"
        )

    def test_max_model_requests_per_run_displayed(self, tmp_path: Path) -> None:
        """Status block must display Max Model Requests / Run = 1."""
        _, block = _run_update(tmp_path)
        assert "Max Model Requests / Run" in block, (
            "Status block must contain 'Max Model Requests / Run'"
        )
        assert "| Max Model Requests / Run | 1 |" in block, (
            "Status block must show Max Model Requests / Run = 1"
        )

    def test_max_commits_per_run_displayed(self, tmp_path: Path) -> None:
        """Status block must display Max Commits / Run = 1."""
        _, block = _run_update(tmp_path)
        assert "Max Commits / Run" in block, (
            "Status block must contain 'Max Commits / Run'"
        )
        assert "| Max Commits / Run | 1 |" in block, (
            "Status block must show Max Commits / Run = 1"
        )

    def test_monthly_api_budget_displayed(self, tmp_path: Path) -> None:
        """Status block must display Monthly API Budget from genome.json."""
        _, block = _run_update(tmp_path)
        assert "Monthly API Budget" in block, (
            "Status block must contain 'Monthly API Budget'"
        )
        assert "10.0 USD" in block, (
            "Status block must show the monthly_api_budget_usd value"
        )

    def test_daily_api_budget_displayed(self, tmp_path: Path) -> None:
        """Status block must display Daily API Budget from genome.json."""
        _, block = _run_update(tmp_path)
        assert "Daily API Budget" in block, (
            "Status block must contain 'Daily API Budget'"
        )
        assert "0.25 USD" in block, (
            "Status block must show the daily_api_budget_usd value"
        )

    def test_send_full_repository_text_false(self, tmp_path: Path) -> None:
        """Status block must display Send Full Repository Text = false."""
        _, block = _run_update(tmp_path)
        assert "Send Full Repository Text" in block, (
            "Status block must contain 'Send Full Repository Text'"
        )
        assert "| Send Full Repository Text | false |" in block, (
            "Status block must show Send Full Repository Text = false"
        )

    def test_send_raw_payloads_false(self, tmp_path: Path) -> None:
        """Status block must display Send Raw Payloads = false."""
        _, block = _run_update(tmp_path)
        assert "Send Raw Payloads" in block, (
            "Status block must contain 'Send Raw Payloads'"
        )
        assert "| Send Raw Payloads | false |" in block, (
            "Status block must show Send Raw Payloads = false"
        )

    def test_send_secrets_false(self, tmp_path: Path) -> None:
        """Status block must display Send Secrets = false."""
        _, block = _run_update(tmp_path)
        assert "Send Secrets" in block, (
            "Status block must contain 'Send Secrets'"
        )
        assert "| Send Secrets | false |" in block, (
            "Status block must show Send Secrets = false"
        )

    def test_schedule_mode_noop_only(self, tmp_path: Path) -> None:
        """Status block must display Schedule Mode = noop only."""
        _, block = _run_update(tmp_path)
        assert "Schedule Mode" in block, (
            "Status block must contain 'Schedule Mode'"
        )
        assert "noop only" in block, (
            "Status block must show Schedule Mode = noop only"
        )

    def test_paid_credit_preflight_fail_closed(self, tmp_path: Path) -> None:
        """Status block must describe Paid-Credit Preflight as fail-closed."""
        _, block = _run_update(tmp_path)
        assert "Paid-Credit Preflight" in block, (
            "Status block must contain 'Paid-Credit Preflight'"
        )
        # Must mention fail-closed behavior (GEMINI_API_KEY missing → fail)
        assert (
            "Fail-closed" in block
            or "fail-closed" in block
            or "GEMINI_API_KEY missing" in block
        ), (
            "Status block must describe fail-closed behavior when GEMINI_API_KEY is missing"
        )

    def test_phase3_gate_human_owner(self, tmp_path: Path) -> None:
        """Status block must state Phase 3 Gate requires Human Owner decision."""
        _, block = _run_update(tmp_path)
        assert "Phase 3 Gate" in block, (
            "Status block must contain 'Phase 3 Gate'"
        )
        assert (
            "Human Owner" in block
        ), (
            "Status block must state Phase 3 Gate requires Human Owner decision"
        )


# ---------------------------------------------------------------------------
# Tests: Legacy fields are preserved
# ---------------------------------------------------------------------------

class TestLegacyFieldsPreserved:
    """Original status block fields must still appear in the updated block."""

    def test_generation_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Generation" in block

    def test_best_score_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Best Score" in block

    def test_detector_hash_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Detector Hash" in block

    def test_last_updated_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Last Updated" in block

    def test_total_test_cases_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Total Test Cases" in block

    def test_tp_fp_tn_fn_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "TP / FP / TN / FN" in block

    def test_adoption_gate_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Adoption Gate" in block

    def test_active_threat_ids_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Active Threat IDs" in block

    def test_status_block_updated_field_present(self, tmp_path: Path) -> None:
        _, block = _run_update(tmp_path)
        assert "Status Block Updated" in block


# ---------------------------------------------------------------------------
# Tests: API Connection reflects genome.json live_model_enabled value
# ---------------------------------------------------------------------------

class TestApiConnectionDisplay:
    """API Connection field must reflect live_model_enabled from genome.json."""

    def test_api_connection_not_connected_when_false(self, tmp_path: Path) -> None:
        """When live_model_enabled=false, API Connection must say 'Not connected'."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": False})
        assert "Not connected" in block, (
            "When live_model_enabled=false, API Connection must be 'Not connected'"
        )

    def test_api_connection_blocked_when_true(self, tmp_path: Path) -> None:
        """When live_model_enabled=true, API Connection must show BLOCKED message."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "BLOCKED" in block, (
            "When live_model_enabled=true, API Connection must show 'BLOCKED' in Phase 2"
        )
        assert "live_model_enabled=true is not allowed in Phase 2" in block, (
            "BLOCKED message must explain that live_model_enabled=true is not allowed in Phase 2"
        )

    def test_live_model_enabled_true_shows_true(self, tmp_path: Path) -> None:
        """When genome has live_model_enabled=true, the row must show 'true'."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "| live_model_enabled | true |" in block, (
            "live_model_enabled row must display 'true' when genome has true"
        )

    def test_live_model_enabled_false_shows_false(self, tmp_path: Path) -> None:
        """When genome has live_model_enabled=false, the row must show 'false'."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": False})
        assert "| live_model_enabled | false |" in block, (
            "live_model_enabled row must display 'false' when genome has false"
        )

    def test_current_phase_unchanged_regardless_of_live_model(self, tmp_path: Path) -> None:
        """Current Phase must always be 'Phase 2 — API-disconnected operations'."""
        for value in (True, False):
            _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": value})
            assert "Phase 2 — API-disconnected operations" in block, (
                f"Current Phase must be fixed regardless of live_model_enabled={value}"
            )


# ---------------------------------------------------------------------------
# Tests: Genome values are read from genome.json (not hard-coded)
# ---------------------------------------------------------------------------

class TestGenomeValuesAreReadFromFile:
    """Values in the status block must come from genome.json, not hard-coded."""

    def test_custom_api_mode_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"api_mode": "custom_test_mode"}
        )
        assert "custom_test_mode" in block, (
            "api_mode value from genome.json must appear in status block"
        )

    def test_custom_model_provider_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"model_provider": "test_provider"}
        )
        assert "test_provider" in block, (
            "model_provider value from genome.json must appear in status block"
        )

    def test_custom_monthly_budget_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"monthly_api_budget_usd": 42.5}
        )
        assert "42.5" in block, (
            "monthly_api_budget_usd value from genome.json must appear in status block"
        )

    def test_custom_daily_budget_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"daily_api_budget_usd": 1.75}
        )
        assert "1.75" in block, (
            "daily_api_budget_usd value from genome.json must appear in status block"
        )

    def test_custom_max_model_requests_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"max_model_requests_per_run": 3}
        )
        assert "| Max Model Requests / Run | 3 |" in block, (
            "max_model_requests_per_run value from genome.json must appear in status block"
        )

    def test_custom_max_commits_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"max_commits_per_run": 2}
        )
        assert "| Max Commits / Run | 2 |" in block, (
            "max_commits_per_run value from genome.json must appear in status block"
        )

    def test_send_repo_text_true_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"send_repository_full_text": True}
        )
        assert "| Send Full Repository Text | true |" in block, (
            "send_repository_full_text=true must show 'true' in status block"
        )

    def test_send_raw_payloads_true_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"send_raw_payloads": True}
        )
        assert "| Send Raw Payloads | true |" in block, (
            "send_raw_payloads=true must show 'true' in status block"
        )

    def test_send_secrets_true_displayed(self, tmp_path: Path) -> None:
        _, block = _run_update(
            tmp_path, genome_overrides={"send_secrets": True}
        )
        assert "| Send Secrets | true |" in block, (
            "send_secrets=true must show 'true' in status block"
        )


# ---------------------------------------------------------------------------
# Tests: Real README.md status block content (integration-style, read-only)
# ---------------------------------------------------------------------------

class TestRealReadmeStatusBlock:
    """Verify that the real README.md already has a Phase 2 status block.

    These tests are read-only — they check the committed README state.
    """

    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md must exist"
        self.content = readme.read_text(encoding="utf-8")
        self.block = _extract_block(self.content)

    def test_real_readme_has_status_block(self) -> None:
        """README.md must contain the status block markers."""
        assert _STATUS_START in self.content
        assert _STATUS_END in self.content
        assert self.block, "Status block must not be empty"

    def test_real_readme_block_has_current_phase(self) -> None:
        """Real README.md status block must show Current Phase."""
        assert "Current Phase" in self.block

    def test_real_readme_block_has_phase2_value(self) -> None:
        """Real README.md status block must show Phase 2 — API-disconnected operations."""
        assert "Phase 2 — API-disconnected operations" in self.block

    def test_real_readme_block_has_api_connection(self) -> None:
        """Real README.md status block must show API Connection."""
        assert "API Connection" in self.block

    def test_real_readme_block_shows_live_model_disabled(self) -> None:
        """Real README.md status block must show live_model_enabled = false."""
        assert "| live_model_enabled | false |" in self.block

    def test_real_readme_block_shows_not_connected(self) -> None:
        """Real README.md must show 'Not connected' (live_model_enabled is false)."""
        assert "Not connected" in self.block

    def test_real_readme_block_has_api_mode(self) -> None:
        """Real README.md status block must show API Mode."""
        assert "API Mode" in self.block

    def test_real_readme_block_has_model_provider(self) -> None:
        """Real README.md status block must show Model Provider."""
        assert "Model Provider" in self.block

    def test_real_readme_block_has_schedule_mode_noop(self) -> None:
        """Real README.md status block must show Schedule Mode = noop only."""
        assert "noop only" in self.block

    def test_real_readme_block_has_paid_credit_preflight(self) -> None:
        """Real README.md status block must show Paid-Credit Preflight."""
        assert "Paid-Credit Preflight" in self.block

    def test_real_readme_block_has_phase3_gate(self) -> None:
        """Real README.md status block must show Phase 3 Gate."""
        assert "Phase 3 Gate" in self.block
        assert "Human Owner" in self.block

    def test_real_readme_block_has_safety_fields_false(self) -> None:
        """Real README.md must show all safety fields as false."""
        assert "| Send Full Repository Text | false |" in self.block
        assert "| Send Raw Payloads | false |" in self.block
        assert "| Send Secrets | false |" in self.block
