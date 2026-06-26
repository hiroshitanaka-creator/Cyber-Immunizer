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

from scripts.update_readme import update_readme, _build_status_block, _GENOME_PATH, _LEDGER_PATH, _parse_bool, _PROJECT_STATE_PATH

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
    original_ledger = mod._LEDGER_PATH
    original_project_state = mod._PROJECT_STATE_PATH

    mod._GENOME_PATH = genome_path
    mod._HISTORY_PATH = tmp_path / "evolution_history.json"
    (tmp_path / "evolution_history.json").write_text("[]")
    mod._THREATS_PATH = tmp_path / "active_threats.json"
    (tmp_path / "active_threats.json").write_text("[]")
    mod._REPORT_PATH = tmp_path / "nonexistent_report.json"  # doesn't exist → fitness=None
    mod._LEDGER_PATH = tmp_path / "api_usage_ledger.json"
    (tmp_path / "api_usage_ledger.json").write_text("[]")  # empty ledger → no past runs
    # doesn't exist → project_state absent → ledger-derived fallback wording
    mod._PROJECT_STATE_PATH = tmp_path / "nonexistent_project_state.json"

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
        mod._LEDGER_PATH = original_ledger
        mod._PROJECT_STATE_PATH = original_project_state


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
        original_ledger = mod._LEDGER_PATH

        readme_path = _make_readme_no_block(tmp_path)
        genome_path = _make_genome(tmp_path)
        mod._GENOME_PATH = genome_path
        mod._HISTORY_PATH = tmp_path / "evolution_history.json"
        (tmp_path / "evolution_history.json").write_text("[]")
        mod._THREATS_PATH = tmp_path / "active_threats.json"
        (tmp_path / "active_threats.json").write_text("[]")
        mod._REPORT_PATH = tmp_path / "nonexistent_report.json"
        mod._LEDGER_PATH = tmp_path / "api_usage_ledger.json"
        (tmp_path / "api_usage_ledger.json").write_text("[]")

        try:
            success = update_readme(readme_path)
            content = readme_path.read_text(encoding="utf-8")
        finally:
            mod._GENOME_PATH = original_genome
            mod._HISTORY_PATH = original_history
            mod._THREATS_PATH = original_threats
            mod._REPORT_PATH = original_report
            mod._LEDGER_PATH = original_ledger

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
        """Status block must state Phase 3 Gate requires Project Owner decision."""
        _, block = _run_update(tmp_path)
        assert "Phase 3 Gate" in block, (
            "Status block must contain 'Phase 3 Gate'"
        )
        assert (
            "Project Owner" in block
        ), (
            "Status block must state Phase 3 Gate requires Project Owner decision"
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

    def test_api_connection_phase3_when_true(self, tmp_path: Path) -> None:
        """When live_model_enabled=true, status block must show Phase 3 (not BLOCKED)."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "Phase 3" in block, (
            "When live_model_enabled=true, status block must show Phase 3"
        )
        assert "BLOCKED" not in block, (
            "When live_model_enabled=true (Phase 3), BLOCKED must not appear"
        )
        assert "live_model_enabled=true is not allowed in Phase 2" not in block, (
            "Phase 2 BLOCKED message must not appear when live_model_enabled=true"
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

    def test_current_phase_changes_with_live_model(self, tmp_path: Path) -> None:
        """Current Phase must be Phase 2 when live_model_enabled=false, Phase 3 when true."""
        _, block_false = _run_update(tmp_path, genome_overrides={"live_model_enabled": False})
        assert "Phase 2 — API-disconnected operations" in block_false, (
            "Current Phase must be 'Phase 2 — API-disconnected operations' when live_model_enabled=false"
        )
        _, block_true = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "Phase 3" in block_true, (
            "Current Phase must show Phase 3 when live_model_enabled=true"
        )
        assert "Phase 2 — API-disconnected operations" not in block_true, (
            "Phase 2 text must not appear when live_model_enabled=true"
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
    """Verify that the real README.md has a Phase 3 status block.

    These tests are read-only — they check the committed README state.
    Updated for Phase 3 current-state SSOT (PR #58-#62 merged; gemini-3-flash-preview
    paid-credit API call success records exist in data/api_usage_ledger.json; per
    data/project_state.json no valid mutation patch was produced; next action is to
    fix the propose/output-contract root cause; promote_approved=false).
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

    def test_real_readme_block_has_phase3_value(self) -> None:
        """Real README.md status block must show Phase 3 state."""
        assert "Phase 3" in self.block, (
            "Status block must show Phase 3 state"
        )

    def test_real_readme_block_shows_live_model_enabled_true(self) -> None:
        """Real README.md status block must show live_model_enabled = true (PR #58)."""
        assert "live_model_enabled" in self.block
        assert "true" in self.block.lower(), (
            "Status block must show live_model_enabled=true (set in PR #58)"
        )

    def test_real_readme_block_shows_gemini_primary_model(self) -> None:
        """Real README.md status block must show gemini-3-flash-preview as primary model (PR #62)."""
        assert "gemini-3-flash-preview" in self.block, (
            "Status block must show primary model gemini-3-flash-preview (PR #62)"
        )

    def test_real_readme_block_shows_paid_credit_run_state(self) -> None:
        """Real README.md status block must reflect current paid-credit run state from ledger.

        When ledger has success records for the primary model, the block must show 'Executed'
        and must NOT show 'Not yet executed'.  When no success records exist, the block must
        show a pending or failed state.  The assertion is derived from the live ledger so it
        stays correct as the ledger evolves.
        """
        import json as _json
        ledger_path = _PROJECT_ROOT / "data" / "api_usage_ledger.json"
        genome_path = _PROJECT_ROOT / "data" / "genome.json"
        try:
            ledger = _json.loads(ledger_path.read_text(encoding="utf-8"))
            genome = _json.loads(genome_path.read_text(encoding="utf-8"))
            model_name = genome.get("model_name", "")
            primary_success = [
                e for e in ledger
                if isinstance(e, dict)
                and e.get("model") == model_name
                and e.get("api_mode") == "gemini_paid_credit"
                and e.get("success") is True
            ]
        except Exception:
            primary_success = []
        if primary_success:
            assert "Executed" in self.block, (
                "Status block must show 'Executed' when ledger has paid-credit success records"
            )
            assert "Not yet executed" not in self.block, (
                "Status block must NOT show 'Not yet executed' when success records exist"
            )
        else:
            assert (
                "Not yet executed" in self.block
                or "Attempted but failed" in self.block
                or "first run" in self.block.lower()
            ), (
                "Status block must show pending or failed state when no success records in ledger"
            )

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

    def test_real_readme_block_has_phase3_activation_state(self) -> None:
        """Real README.md status block must show Phase 3 activation state."""
        assert "Phase 3 Activation" in self.block or "Phase 3 First" in self.block, (
            "Status block must contain Phase 3 activation state field"
        )

    def test_real_readme_block_has_safety_fields_false(self) -> None:
        """Real README.md must show all safety fields as false."""
        assert "| Send Full Repository Text | false |" in self.block
        assert "| Send Raw Payloads | false |" in self.block
        assert "| Send Secrets | false |" in self.block


# ---------------------------------------------------------------------------
# Tests: _parse_bool unit tests (regression guard for bool("false") == True)
# ---------------------------------------------------------------------------

class TestParseBoolUnit:
    """Unit tests for _parse_bool to guard against bool("false") == True."""

    # --- JSON boolean values (must pass through unchanged) ---

    def test_bool_false_returns_false(self) -> None:
        """JSON boolean false must return False."""
        assert _parse_bool(False) is False

    def test_bool_true_returns_true(self) -> None:
        """JSON boolean true must return True."""
        assert _parse_bool(True) is True

    # --- String "false" / "true" ---

    def test_string_false_returns_false(self) -> None:
        """String 'false' must return False (not True as bool() would)."""
        assert _parse_bool("false") is False

    def test_string_true_returns_true(self) -> None:
        """String 'true' must return True."""
        assert _parse_bool("true") is True

    def test_string_false_uppercase_returns_false(self) -> None:
        """String 'FALSE' (uppercase) must return False."""
        assert _parse_bool("FALSE") is False

    def test_string_true_uppercase_returns_true(self) -> None:
        """String 'TRUE' (uppercase) must return True."""
        assert _parse_bool("TRUE") is True

    def test_string_false_mixed_case_returns_false(self) -> None:
        """String 'False' (mixed case) must return False."""
        assert _parse_bool("False") is False

    def test_string_true_mixed_case_returns_true(self) -> None:
        """String 'True' (mixed case) must return True."""
        assert _parse_bool("True") is True

    def test_string_false_with_whitespace_returns_false(self) -> None:
        """String '  false  ' (with whitespace) must return False."""
        assert _parse_bool("  false  ") is False

    def test_string_true_with_whitespace_returns_true(self) -> None:
        """String '  true  ' (with whitespace) must return True."""
        assert _parse_bool("  true  ") is True

    # --- Invalid / unknown strings fall back to default ---

    def test_string_nope_returns_default_false(self) -> None:
        """Invalid string 'nope' must fall back to default (False)."""
        assert _parse_bool("nope") is False

    def test_string_nope_returns_default_true_when_set(self) -> None:
        """Invalid string 'nope' must fall back to explicit default=True."""
        assert _parse_bool("nope", default=True) is True

    def test_string_zero_returns_default_false(self) -> None:
        """String '0' is not recognized as bool; must return default False."""
        assert _parse_bool("0") is False

    def test_string_one_returns_default_false(self) -> None:
        """String '1' is not recognized as bool; must return default False."""
        assert _parse_bool("1") is False

    def test_empty_string_returns_default_false(self) -> None:
        """Empty string must fall back to default False."""
        assert _parse_bool("") is False

    # --- None falls back to default ---

    def test_none_returns_default_false(self) -> None:
        """None must return default False."""
        assert _parse_bool(None) is False

    def test_none_returns_default_true_when_set(self) -> None:
        """None must return explicit default=True."""
        assert _parse_bool(None, default=True) is True

    # --- Non-string / non-bool types fall back to default ---

    def test_integer_0_returns_default_false(self) -> None:
        """Integer 0 is not bool; must return default False."""
        assert _parse_bool(0) is False

    def test_integer_1_returns_default_false(self) -> None:
        """Integer 1 is not bool (not isinstance bool); must return default False."""
        assert _parse_bool(1) is False

    def test_list_returns_default_false(self) -> None:
        """List value must fall back to default False."""
        assert _parse_bool([]) is False
        assert _parse_bool([True]) is False


# ---------------------------------------------------------------------------
# Tests: string booleans in genome.json produce correct dashboard output
# ---------------------------------------------------------------------------

class TestStringBooleanInGenome:
    """Regression tests: genome.json with string booleans must show correct dashboard.

    Scenario: genome.json accidentally contains string "false" instead of
    JSON boolean false. The old bool("false") == True bug would show 'true'
    in the dashboard; _parse_bool must correct this.
    """

    def test_live_model_enabled_string_false_shows_false(self, tmp_path: Path) -> None:
        """live_model_enabled='false' (string) must display as false in dashboard."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": "false"})
        assert "| live_model_enabled | false |" in block, (
            "String 'false' for live_model_enabled must show 'false', not 'true'"
        )

    def test_live_model_enabled_string_false_api_connection_not_connected(
        self, tmp_path: Path
    ) -> None:
        """live_model_enabled='false' (string) must yield 'Not connected' API Connection."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": "false"})
        assert "Not connected" in block, (
            "String 'false' for live_model_enabled must yield 'Not connected'"
        )
        assert "BLOCKED" not in block, (
            "String 'false' for live_model_enabled must NOT yield BLOCKED"
        )

    def test_live_model_enabled_string_true_shows_true(self, tmp_path: Path) -> None:
        """live_model_enabled='true' (string) must display as true and trigger Phase 3."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": "true"})
        assert "| live_model_enabled | true |" in block, (
            "String 'true' for live_model_enabled must show 'true'"
        )
        assert "Phase 3" in block, (
            "String 'true' for live_model_enabled must trigger Phase 3 display"
        )
        assert "BLOCKED" not in block, (
            "String 'true' for live_model_enabled must NOT trigger BLOCKED in Phase 3"
        )

    def test_send_repository_full_text_string_false_shows_false(
        self, tmp_path: Path
    ) -> None:
        """send_repository_full_text='false' (string) must display as false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"send_repository_full_text": "false"},
        )
        assert "| Send Full Repository Text | false |" in block, (
            "String 'false' for send_repository_full_text must show 'false', not 'true'"
        )

    def test_send_raw_payloads_string_false_shows_false(self, tmp_path: Path) -> None:
        """send_raw_payloads='false' (string) must display as false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"send_raw_payloads": "false"},
        )
        assert "| Send Raw Payloads | false |" in block, (
            "String 'false' for send_raw_payloads must show 'false', not 'true'"
        )

    def test_send_secrets_string_false_shows_false(self, tmp_path: Path) -> None:
        """send_secrets='false' (string) must display as false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"send_secrets": "false"},
        )
        assert "| Send Secrets | false |" in block, (
            "String 'false' for send_secrets must show 'false', not 'true'"
        )

    def test_invalid_string_live_model_enabled_defaults_to_false(
        self, tmp_path: Path
    ) -> None:
        """Invalid string 'nope' for live_model_enabled must default to false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"live_model_enabled": "nope"},
        )
        assert "| live_model_enabled | false |" in block, (
            "Invalid string 'nope' must default to false, not true"
        )
        assert "Not connected" in block, (
            "Invalid string 'nope' for live_model_enabled must yield 'Not connected'"
        )

    def test_invalid_string_send_repo_text_defaults_to_false(
        self, tmp_path: Path
    ) -> None:
        """Invalid string 'nope' for send_repository_full_text must default to false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"send_repository_full_text": "nope"},
        )
        assert "| Send Full Repository Text | false |" in block

    def test_json_boolean_false_still_shows_false(self, tmp_path: Path) -> None:
        """JSON boolean false (Python False) must still display as false."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"live_model_enabled": False},
        )
        assert "| live_model_enabled | false |" in block

    def test_json_boolean_true_still_shows_true(self, tmp_path: Path) -> None:
        """JSON boolean true (Python True) must still display as true."""
        _, block = _run_update(
            tmp_path,
            genome_overrides={"live_model_enabled": True},
        )
        assert "| live_model_enabled | true |" in block


# ---------------------------------------------------------------------------
# Tests: Fitness Report N/A explanation (Option A)
# ---------------------------------------------------------------------------

def _run_update_with_report(
    tmp_path: Path,
    report_data: dict | None,
    genome_overrides: dict | None = None,
) -> tuple[str, str]:
    """Run update_readme with an optional fitness report file.

    If report_data is None, no report file is created (missing state).
    If report_data is a dict, it is written to tmp_path/fitness_report.json.
    Returns (full_readme_content, status_block_content).
    """
    readme_path = _make_readme(tmp_path)
    genome_path = _make_genome(tmp_path, genome_overrides)

    import scripts.update_readme as mod
    original_genome = mod._GENOME_PATH
    original_history = mod._HISTORY_PATH
    original_threats = mod._THREATS_PATH
    original_report = mod._REPORT_PATH
    original_ledger = mod._LEDGER_PATH
    original_project_state = mod._PROJECT_STATE_PATH

    mod._GENOME_PATH = genome_path
    mod._HISTORY_PATH = tmp_path / "evolution_history.json"
    (tmp_path / "evolution_history.json").write_text("[]")
    mod._THREATS_PATH = tmp_path / "active_threats.json"
    (tmp_path / "active_threats.json").write_text("[]")
    mod._LEDGER_PATH = tmp_path / "api_usage_ledger.json"
    (tmp_path / "api_usage_ledger.json").write_text("[]")
    mod._PROJECT_STATE_PATH = tmp_path / "nonexistent_project_state.json"

    if report_data is None:
        mod._REPORT_PATH = tmp_path / "nonexistent_report.json"  # doesn't exist
    else:
        report_path = tmp_path / "fitness_report.json"
        report_path.write_text(json.dumps(report_data, indent=2))
        mod._REPORT_PATH = report_path

    try:
        success = update_readme(readme_path)
        assert success
        content = readme_path.read_text(encoding="utf-8")
        block = _extract_block(content)
        return content, block
    finally:
        mod._GENOME_PATH = original_genome
        mod._HISTORY_PATH = original_history
        mod._THREATS_PATH = original_threats
        mod._REPORT_PATH = original_report
        mod._LEDGER_PATH = original_ledger
        mod._PROJECT_STATE_PATH = original_project_state


def _run_update_with_ledger(
    tmp_path: Path,
    ledger_data: list,
    genome_overrides: dict | None = None,
    project_state_data: dict | None = None,
) -> tuple[str, str]:
    """Run update_readme with a specific ledger content.

    ledger_data is a list of dicts (each a ledger entry).
    project_state_data: if provided, written to a temp project_state.json and
        used as the current-state authority. If None, project_state is absent
        (ledger-derived fallback wording is used).
    Returns (full_readme_content, status_block_content).
    """
    readme_path = _make_readme(tmp_path)
    genome_path = _make_genome(tmp_path, genome_overrides)
    ledger_path = tmp_path / "custom_ledger.json"
    ledger_path.write_text(json.dumps(ledger_data))

    import scripts.update_readme as mod
    original_genome = mod._GENOME_PATH
    original_history = mod._HISTORY_PATH
    original_threats = mod._THREATS_PATH
    original_report = mod._REPORT_PATH
    original_ledger = mod._LEDGER_PATH
    original_project_state = mod._PROJECT_STATE_PATH

    mod._GENOME_PATH = genome_path
    mod._HISTORY_PATH = tmp_path / "evolution_history.json"
    (tmp_path / "evolution_history.json").write_text("[]")
    mod._THREATS_PATH = tmp_path / "active_threats.json"
    (tmp_path / "active_threats.json").write_text("[]")
    mod._REPORT_PATH = tmp_path / "nonexistent_report.json"
    mod._LEDGER_PATH = ledger_path
    if project_state_data is not None:
        project_state_path = tmp_path / "project_state.json"
        project_state_path.write_text(json.dumps(project_state_data))
        mod._PROJECT_STATE_PATH = project_state_path
    else:
        mod._PROJECT_STATE_PATH = tmp_path / "nonexistent_project_state.json"

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
        mod._LEDGER_PATH = original_ledger
        mod._PROJECT_STATE_PATH = original_project_state


_SAMPLE_FITNESS_REPORT = {
    "fitness_report": {
        "total_cases": 20,
        "true_positive": 10,
        "false_positive": 1,
        "true_negative": 8,
        "false_negative": 1,
        "tp_rate": 0.909,
        "fp_rate": 0.111,
        "fn_rate": 0.091,
        "score": 500.0,
        "passed_adoption_gate": False,
        "rejection_reasons": [],
    }
}


class TestFitnessReportNaExplanation:
    """When fitness_report.json is missing, an explanatory row must appear.

    Rules (from GPT Audit Gate REQUEST CHANGES):
    - Do not fake or hard-code fitness numbers.
    - When no report: show 'Not available' explanation, keep N/A values.
    - When report present: show actual values, no 'Not available' row.
    """

    # --- Missing report ---

    def test_fitness_report_row_present_when_no_report(self, tmp_path: Path) -> None:
        """Fitness Report row must appear when no fitness report file exists."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        assert "Fitness Report" in block, (
            "When no fitness report exists, a 'Fitness Report' row must appear"
        )

    def test_fitness_report_not_available_text_when_no_report(
        self, tmp_path: Path
    ) -> None:
        """Fitness Report row must contain 'Not available' when no report exists."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        assert "Not available" in block, (
            "Fitness Report row must say 'Not available' when no report file exists"
        )

    def test_fitness_report_explains_how_to_populate(self, tmp_path: Path) -> None:
        """Fitness Report row must mention how to populate TP/FP/TN/FN."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        assert (
            "baseline fitness" in block
            or "TP/FP/TN/FN" in block
            or "fitness" in block.lower()
        ), (
            "Fitness Report row must explain how to populate the fitness fields"
        )

    def test_total_test_cases_is_na_when_no_report(self, tmp_path: Path) -> None:
        """Total Test Cases must be N/A when no fitness report exists."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        assert "| Total Test Cases | N/A |" in block, (
            "Total Test Cases must remain N/A when no report exists"
        )

    def test_tp_fp_tn_fn_is_na_when_no_report(self, tmp_path: Path) -> None:
        """TP / FP / TN / FN must all be N/A when no fitness report exists."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        assert "| TP / FP / TN / FN | N/A / N/A / N/A / N/A |" in block, (
            "TP/FP/TN/FN must all be N/A when no report exists"
        )

    def test_no_stale_hard_coded_values_when_no_report(
        self, tmp_path: Path
    ) -> None:
        """Must not show hard-coded stale values (15, 8 / 0 / 7 / 0) when no report."""
        _, block = _run_update_with_report(tmp_path, report_data=None)
        # These are the old stale values that must not appear
        assert "| Total Test Cases | 15 |" not in block, (
            "Must not hard-code stale total_cases=15"
        )
        assert "8 / 0 / 7 / 0" not in block, (
            "Must not hard-code stale TP/FP/TN/FN values"
        )

    # --- Present report ---

    def test_total_test_cases_populated_when_report_present(
        self, tmp_path: Path
    ) -> None:
        """Total Test Cases must show the value from the fitness report."""
        _, block = _run_update_with_report(tmp_path, report_data=_SAMPLE_FITNESS_REPORT)
        assert "| Total Test Cases | 20 |" in block, (
            "Total Test Cases must show total_cases from the fitness report"
        )

    def test_tp_fp_tn_fn_populated_when_report_present(
        self, tmp_path: Path
    ) -> None:
        """TP / FP / TN / FN must show values from the fitness report."""
        _, block = _run_update_with_report(tmp_path, report_data=_SAMPLE_FITNESS_REPORT)
        assert "| TP / FP / TN / FN | 10 / 1 / 8 / 1 |" in block, (
            "TP/FP/TN/FN must be populated from the fitness report"
        )

    def test_fitness_report_not_available_row_absent_when_report_present(
        self, tmp_path: Path
    ) -> None:
        """'Not available' row must NOT appear when a valid fitness report exists."""
        _, block = _run_update_with_report(tmp_path, report_data=_SAMPLE_FITNESS_REPORT)
        assert "Not available" not in block, (
            "When a valid fitness report exists, 'Not available' must not be shown"
        )

    def test_fitness_report_row_absent_when_report_present(
        self, tmp_path: Path
    ) -> None:
        """'Fitness Report | Not available' row must NOT appear when report exists."""
        _, block = _run_update_with_report(tmp_path, report_data=_SAMPLE_FITNESS_REPORT)
        assert "| Fitness Report |" not in block, (
            "The 'Fitness Report' explanatory row must not appear when report is present"
        )

    def test_report_with_top_level_fitness_fields(self, tmp_path: Path) -> None:
        """Fitness values at top-level (no 'fitness_report' key) must also work."""
        top_level_report = {
            "total_cases": 15,
            "true_positive": 8,
            "false_positive": 0,
            "true_negative": 7,
            "false_negative": 0,
        }
        _, block = _run_update_with_report(tmp_path, report_data=top_level_report)
        assert "| Total Test Cases | 15 |" in block
        assert "| TP / FP / TN / FN | 8 / 0 / 7 / 0 |" in block
        assert "Not available" not in block


# ---------------------------------------------------------------------------
# Tests: Phase 3 mandatory fields (live_model_enabled=true)
# ---------------------------------------------------------------------------

class TestPhase3MandatoryFields:
    """When live_model_enabled=true, status block must show Phase 3 fields, not BLOCKED."""

    def test_phase3_current_phase_shown(self, tmp_path: Path) -> None:
        """Phase 3 must appear in Current Phase when live_model_enabled=true."""
        _, block = _run_update(tmp_path, genome_overrides={
            "live_model_enabled": True,
            "model_name": "gemini-3-flash-preview",
            "fallback_model_name": "gemini-3.1-flash-lite",
        })
        assert "Phase 3" in block, (
            "Current Phase must show Phase 3 when live_model_enabled=true"
        )

    def test_phase3_no_blocked_message(self, tmp_path: Path) -> None:
        """BLOCKED must NOT appear when live_model_enabled=true (Phase 3)."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "BLOCKED" not in block, (
            "Phase 3 status block must not contain BLOCKED message"
        )
        assert "live_model_enabled=true is not allowed in Phase 2" not in block, (
            "Phase 2 BLOCKED text must not appear in Phase 3"
        )

    def test_phase3_no_phase2_text(self, tmp_path: Path) -> None:
        """Phase 2 — API-disconnected text must NOT appear when live_model_enabled=true."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "Phase 2 — API-disconnected operations" not in block, (
            "Phase 2 text must not appear in Phase 3 status block"
        )

    def test_phase3_shows_gemini_primary_model(self, tmp_path: Path) -> None:
        """Gemini Primary Model row must appear with model_name value."""
        _, block = _run_update(tmp_path, genome_overrides={
            "live_model_enabled": True,
            "model_name": "gemini-3-flash-preview",
        })
        assert "Gemini Primary Model" in block, (
            "Phase 3 status block must contain 'Gemini Primary Model' row"
        )
        assert "gemini-3-flash-preview" in block, (
            "Gemini Primary Model must show model_name from genome.json"
        )

    def test_phase3_shows_gemini_fallback_model(self, tmp_path: Path) -> None:
        """Gemini Fallback Model row must appear with fallback_model_name value."""
        _, block = _run_update(tmp_path, genome_overrides={
            "live_model_enabled": True,
            "fallback_model_name": "gemini-3.1-flash-lite",
        })
        assert "Gemini Fallback Model" in block, (
            "Phase 3 status block must contain 'Gemini Fallback Model' row"
        )
        assert "gemini-3.1-flash-lite" in block, (
            "Gemini Fallback Model must show fallback_model_name from genome.json"
        )

    def test_phase3_shows_not_yet_executed_when_empty_ledger(self, tmp_path: Path) -> None:
        """When ledger has no paid-credit attempts for primary model, show Not yet executed."""
        _, block = _run_update(tmp_path, genome_overrides={
            "live_model_enabled": True,
            "model_name": "gemini-3-flash-preview",
        })
        assert "Not yet executed" in block, (
            "Phase 3 First Paid-Credit Run must show 'Not yet executed' when ledger has no primary model paid-credit attempts"
        )

    def test_phase3_shows_promote_approved(self, tmp_path: Path) -> None:
        """promote_approved row must appear in Phase 3 status block."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "promote_approved" in block, (
            "Phase 3 status block must contain 'promote_approved' row"
        )

    def test_phase3_shows_phase3_activation_or_first(self, tmp_path: Path) -> None:
        """Phase 3 Activation or Phase 3 First must appear in Phase 3 status block."""
        _, block = _run_update(tmp_path, genome_overrides={"live_model_enabled": True})
        assert "Phase 3 Activation" in block or "Phase 3 First" in block, (
            "Phase 3 status block must contain Phase 3 Activation or Phase 3 First row"
        )

    def test_phase3_executed_count_when_ledger_has_primary_success(
        self, tmp_path: Path
    ) -> None:
        """When ledger has a successful paid-credit run for primary model, show Executed."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": True,
                "api_mode": "gemini_paid_credit",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
        )
        assert "Executed" in block, (
            "Phase 3 First Paid-Credit Run must show Executed when ledger has primary model success"
        )
        assert "successful" in block, (
            "Executed status must include successful count"
        )
        assert "attempt" in block, (
            "Executed status must include total attempt count"
        )
        assert "Not yet executed" not in block, (
            "Not yet executed must not appear when there are primary model paid-credit successes"
        )

    def test_phase3_project_state_drives_current_state_wording(
        self, tmp_path: Path
    ) -> None:
        """When data/project_state.json exists, it (not the ledger) drives the
        current_phase / next_focus / promote wording.

        The ledger-derived run count (Executed N successful / M attempts) is
        retained, but the stale 'Review existing paid-credit run results' /
        'post-run result review pending' wording must be replaced by the
        project_state next_action and patch-not-produced phase.
        """
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": True,
                "api_mode": "gemini_paid_credit",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
            project_state_data={
                "paid_credit_api_calls": {"valid_mutation_patch_produced": False},
                "promotion": {"promote_approved": False},
                "next_action": "fix_propose_output_contract_before_new_paid_credit_run",
            },
        )
        # Ledger-derived run count retained.
        assert "Executed" in block, "run-count status must remain ledger-derived"
        # project_state-driven wording present.
        assert "no valid mutation patch produced" in block, (
            "current_phase must reflect project_state patch-not-produced state"
        )
        assert "Fix propose/output-contract root cause before any new paid-credit run" in block, (
            "next_focus must come from project_state next_action"
        )
        # Stale wording must be gone.
        assert "Review existing paid-credit run results" not in block, (
            "stale ledger-only next focus must not appear when project_state exists"
        )
        assert "post-run result review pending" not in block, (
            "stale ledger-only current_phase must not appear when project_state exists"
        )

    def test_phase3_project_state_evaluate_rejected_wording(
        self, tmp_path: Path
    ) -> None:
        """project_state with evaluate_reached=true and adoption gate never passed
        (runs 5 & 6 outcome) must drive the runs-5-6 current_phase, the Owner-decision
        next_focus, and the 'no candidate has passed the adoption gate' promote note —
        and must NOT fall back to the stale ledger-derived wording.
        """
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": True,
                "api_mode": "gemini_paid_credit",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
            project_state_data={
                "paid_credit_api_calls": {
                    "valid_mutation_patch_produced": True,
                    "apply_reached": True,
                    "evaluate_reached": True,
                    "adoption_gate_ever_passed": False,
                },
                "promotion": {"promote_approved": False},
                "next_action": (
                    "runs_5_6_artifact_triage_complete_evaluate_rejected"
                    "_await_owner_decision_on_propose_side_improvement"
                ),
            },
        )
        # Ledger-derived run count retained.
        assert "Executed" in block, "run-count status must remain ledger-derived"
        # project_state-driven current_phase for the evaluate-rejected state.
        assert (
            "runs 5 & 6 triaged: both reached evaluate, adoption gate rejected"
            " (score regression)"
        ) in block, "current_phase must reflect the runs-5-6 evaluate-rejected state"
        # next_focus comes from the new _NEXT_ACTION_TEXT entry.
        assert (
            "Owner decision: runs 5 & 6 reached evaluate but regressed below best=729.34;"
            " decide propose-side improvement before any rerun"
        ) in block, "next_focus must come from the runs-5-6 project_state next_action"
        # promote note for evaluate-reached-but-gate-never-passed.
        assert "no candidate has passed the adoption gate" in block, (
            "promote note must reflect that no candidate has passed the adoption gate"
        )
        # Stale fallback wording must be gone.
        assert "Review existing paid-credit run results" not in block, (
            "stale ledger-only next focus must not appear when project_state exists"
        )
        assert "post-run result review pending" not in block, (
            "stale ledger-only current_phase must not appear when project_state exists"
        )

    def test_phase3_propose_side_hardened_next_action_wording(
        self, tmp_path: Path
    ) -> None:
        """After propose-side baseline-preservation hardening, project_state's
        new next_action must drive the corresponding next_focus wording via the
        _NEXT_ACTION_TEXT mapping (the machine facts — evaluate reached, gate
        never passed — are unchanged, so current_phase still reflects runs 5/6)."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": True,
                "api_mode": "gemini_paid_credit",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
            project_state_data={
                "paid_credit_api_calls": {
                    "valid_mutation_patch_produced": True,
                    "apply_reached": True,
                    "evaluate_reached": True,
                    "adoption_gate_ever_passed": False,
                },
                "promotion": {"promote_approved": False},
                "next_action": (
                    "propose_side_baseline_preservation_hardened"
                    "_await_owner_approved_rerun_review"
                ),
            },
        )
        # current_phase still reflects the runs-5-6 evaluate-rejected machine state.
        assert (
            "runs 5 & 6 triaged: both reached evaluate, adoption gate rejected"
            " (score regression)"
        ) in block, "current_phase must still reflect the runs-5-6 machine state"
        # next_focus comes from the new _NEXT_ACTION_TEXT entry.
        assert (
            "Propose-side baseline-preservation hardening implemented"
        ) in block, "next_focus must come from the propose-side-hardened next_action"
        assert "awaiting Owner-approved paid-credit rerun review" in block
        # Stale prior next_focus wording must be gone.
        assert "decide propose-side improvement before any rerun" not in block, (
            "stale runs-5-6 'decide propose-side improvement' next_focus must not appear"
        )

    def test_phase3_attempted_but_failed_when_primary_only_fails(
        self, tmp_path: Path
    ) -> None:
        """When ledger has failed paid-credit attempts for primary model, show Attempted but failed."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": False,
                "api_mode": "gemini_paid_credit",
                "error": "ClientError",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
        )
        assert "Attempted but failed" in block, (
            "Phase 3 First Paid-Credit Run must show 'Attempted but failed' when all primary paid-credit attempts failed"
        )
        assert "Not yet executed" not in block, (
            "Failed attempt must NOT be shown as 'Not yet executed'"
        )
        assert "inspect ledger" in block.lower(), (
            "Attempted but failed status must prompt to inspect ledger before rerun"
        )

    def test_phase3_not_yet_executed_when_only_fallback_model_in_ledger(
        self, tmp_path: Path
    ) -> None:
        """Ledger records for a different (fallback) model must not count as primary attempts."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3.1-flash-lite",
                "success": True,
                "api_mode": "gemini_paid_credit",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
                "fallback_model_name": "gemini-3.1-flash-lite",
            },
        )
        assert "Not yet executed" in block, (
            "gemini-3.1-flash-lite success must not count as gemini-3-flash-preview attempt"
        )

    def test_phase3_not_yet_executed_when_non_paid_credit_mode(
        self, tmp_path: Path
    ) -> None:
        """Records with api_mode other than gemini_paid_credit must not count as paid-credit attempts."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[{
                "model": "gemini-3-flash-preview",
                "success": True,
                "api_mode": "offline_sample",
            }],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
        )
        assert "Not yet executed" in block, (
            "non-gemini_paid_credit api_mode records must not count as paid-credit attempts"
        )

    def test_phase3_failed_attempt_not_shown_as_not_yet_executed_regression(
        self, tmp_path: Path
    ) -> None:
        """Regression guard: success=False primary model record must never show Not yet executed."""
        _, block = _run_update_with_ledger(
            tmp_path,
            ledger_data=[
                {
                    "model": "gemini-3-flash-preview",
                    "success": False,
                    "api_mode": "gemini_paid_credit",
                    "error": "NOT_FOUND",
                },
                {
                    "model": "gemini-3-flash-preview",
                    "success": False,
                    "api_mode": "gemini_paid_credit",
                    "error": "QUOTA_EXCEEDED",
                },
            ],
            genome_overrides={
                "live_model_enabled": True,
                "model_name": "gemini-3-flash-preview",
            },
        )
        assert "Not yet executed" not in block, (
            "Regression: failed attempts must NOT be shown as 'Not yet executed'"
        )
        assert "Attempted but failed" in block, (
            "Multiple failures must show 'Attempted but failed'"
        )
        assert "2" in block, (
            "Attempted but failed must show the attempt count (2)"
        )


# ---------------------------------------------------------------------------
# Tests: Phase 3 run-8 recovery state (adoption gate passed, promote push failed)
# ---------------------------------------------------------------------------

class TestPhase3Run8RecoveryState:
    """When project_state reflects run 8 (adoption gate passed, promote push failed),
    generated README wording must direct maintainers to owner-audited candidate
    recovery — NOT to generic post-run review or a new paid-credit rerun."""

    _LEDGER = [{"model": "gemini-3-flash-preview", "success": True, "api_mode": "gemini_paid_credit"}]
    _GENOME = {"live_model_enabled": True, "model_name": "gemini-3-flash-preview"}

    def _ps(self) -> dict:
        return {
            "paid_credit_api_calls": {
                "valid_mutation_patch_produced": True,
                "apply_reached": True,
                "evaluate_reached": True,
                "adoption_gate_ever_passed": True,
                "promote_reached": True,
            },
            "promotion": {"promote_approved": False},
            "next_action": "owner_audited_candidate_recovery_after_run8_promote_push_failure",
        }

    def test_next_focus_says_owner_recovery(self, tmp_path: Path) -> None:
        """next_focus must explicitly name owner-audited candidate recovery."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "Owner-audited candidate recovery" in block, (
            "next_focus must say 'Owner-audited candidate recovery'"
        )

    def test_next_focus_mentions_promote_push_failure(self, tmp_path: Path) -> None:
        """next_focus must mention that the promote push failed."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "push failed" in block, (
            "next_focus must mention promote push failure"
        )

    def test_next_focus_says_candidate_not_promoted(self, tmp_path: Path) -> None:
        """next_focus must state that the candidate was not promoted to main."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "not promoted" in block, (
            "next_focus must state candidate was not promoted to main"
        )

    def test_next_focus_no_new_paid_credit_rerun_required(self, tmp_path: Path) -> None:
        """next_focus must state no new paid-credit rerun is the immediate next step."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "no new paid-credit rerun required as immediate next step" in block, (
            "next_focus must explicitly state no new paid-credit rerun is required immediately"
        )

    def test_current_phase_reflects_adoption_gate_passed(self, tmp_path: Path) -> None:
        """current_phase must reflect adoption gate pass and promote push failure."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "adoption gate" in block.lower(), (
            "current_phase must reflect adoption gate pass"
        )
        assert "promote" in block.lower(), (
            "current_phase must reflect promote stage was reached"
        )

    def test_no_generic_post_run_review_wording(self, tmp_path: Path) -> None:
        """Generic stale wording must not appear in run-8 recovery state."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "post-run result review pending" not in block, (
            "generic 'post-run result review pending' must not appear for run-8 state"
        )
        assert "Review existing paid-credit run results" not in block, (
            "generic 'Review existing paid-credit run results' must not appear for run-8 state"
        )

    def test_promote_note_does_not_say_gate_never_passed(self, tmp_path: Path) -> None:
        """promote_note must not claim no candidate passed the adoption gate."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "no candidate has passed the adoption gate" not in block, (
            "promote note must not claim adoption gate was never passed — run 8 passed it"
        )

    def test_promote_note_says_push_failed_and_not_promoted(self, tmp_path: Path) -> None:
        """promote_note must communicate push failure and that candidate was not promoted."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "push failed" in block or "promote push failed" in block, (
            "promote_note must communicate promote push failure"
        )
        assert "not promoted" in block, (
            "promote_note must state candidate was not promoted"
        )

    def test_promote_approved_is_false(self, tmp_path: Path) -> None:
        """promote_approved field must appear and show false — no completed promotion."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "promote_approved" in block, "promote_approved field must be present"
        assert "false" in block.lower(), "promote_approved must show false"
        assert "candidate was promoted" not in block.lower(), (
            "block must not claim the candidate was promoted"
        )


# ---------------------------------------------------------------------------
# Tests: Real README.md Fitness Report state (read-only integration)
# ---------------------------------------------------------------------------

class TestRealReadmeFitnessReportState:
    """Read-only check of the real README.md fitness report display."""

    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md must exist"
        self.content = readme.read_text(encoding="utf-8")
        self.block = _extract_block(self.content)

    def test_real_readme_generation4_fitness_values_present(self) -> None:
        """Real README may show committed generation 4 promotion metrics, or an
        explicit not-available explanation. update_readme.py emits N/A for the
        fitness table when no legacy fitness report is present at generation time
        (e.g. after the run #80 structured promotion regenerated the block); the
        gen-4 legacy fitness (15 cases, 8/0/7/0) remains recorded in
        data/evolution_history.json. This mirrors
        test_real_readme_fitness_report_values_or_explanation."""
        assert (
            ("| Total Test Cases | 15 |" in self.block and "8 / 0 / 7 / 0" in self.block)
            or "Not available" in self.block
            or "| Total Test Cases | N/A |" in self.block
        )

    def test_real_readme_fitness_report_values_or_explanation(self) -> None:
        """Real README must show generation 4 metrics or a not-available explanation."""
        assert (
            "| Total Test Cases | 15 |" in self.block
            or "Not available" in self.block
            or "| Total Test Cases | N/A |" in self.block
        )

    def test_real_readme_generation_4_present(self) -> None:
        """Real README must show generation 4 (promoted via paid-credit run #59)."""
        assert "| Generation | 4 |" in self.block, (
            "Real README must show Generation 4 after paid-credit run #59 promotion"
        )

    def test_real_readme_best_score_948_04_present(self) -> None:
        """Real README must show best_score 948.04 (generation 4)."""
        assert "948.04" in self.block, (
            "Real README must show best_score=948.04 (generation 4)"
        )

    def test_real_readme_generation4_metrics_present_unconditional(self) -> None:
        """Real README records the committed generation 4 promotion metrics, or an
        explicit not-available explanation when the generator had no legacy fitness
        report at generation time (see
        test_real_readme_generation4_fitness_values_present)."""
        assert (
            ("8 / 0 / 7 / 0" in self.block and "| Total Test Cases | 15 |" in self.block)
            or "Not available" in self.block
            or "| Total Test Cases | N/A |" in self.block
        )

    def test_real_readme_generation4_wording_present(self) -> None:
        """Real README must contain generation 4 promotion wording."""
        assert "generation 4" in self.block.lower() or "Generation 4" in self.block, (
            "README status block must reference generation 4 after promotion"
        )


# ---------------------------------------------------------------------------
# Tests: Phase 3 run-8 candidate recovered state (candidate_promoted=True)
# ---------------------------------------------------------------------------

class TestPhase3Run8CandidateRecoveredState:
    """When project_state reflects the completed run-8 recovery
    (candidate_promoted=True, promote_approved=True), the generated README
    must show generation 3, score 947.66, owner-merge wording, and must NOT
    show stale fitness metrics or 'not promoted' language."""

    _LEDGER = [{"model": "gemini-3-flash-preview", "success": True, "api_mode": "gemini_paid_credit"}]
    _GENOME = {"live_model_enabled": True, "model_name": "gemini-3-flash-preview"}

    def _ps(self) -> dict:
        return {
            "paid_credit_api_calls": {
                "valid_mutation_patch_produced": True,
                "apply_reached": True,
                "evaluate_reached": True,
                "adoption_gate_ever_passed": True,
                "promote_reached": True,
                "candidate_promoted": True,
                "candidate_promoted_generation": 3,
                "candidate_promoted_score": 947.66,
                "candidate_promoted_hash": "c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6",
            },
            "promotion": {
                "promote_approved": True,
                "meaning": "run_8_candidate_promoted_to_generation_3_via_recovery",
            },
            "next_action": "post_recovery_monitor_generation3_and_owner_decide_next_phase3_step",
        }

    def test_promote_approved_shows_true(self, tmp_path: Path) -> None:
        """promote_approved must show true after candidate recovery."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "promote_approved" in block, "promote_approved field must appear"
        assert "true" in block.lower(), "promote_approved must show true after recovery"

    def test_current_phase_shows_generation_3_active(self, tmp_path: Path) -> None:
        """current_phase must say generation 3 is active on main (post-merge)."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "generation 3" in block.lower(), (
            "current_phase must reflect generation 3 after candidate recovery"
        )
        assert (
            "active on main" in block.lower()
            or "recovery complete" in block.lower()
        ), (
            "current_phase must say generation 3 is active on main or recovery is complete"
        )

    def test_next_focus_says_post_recovery_monitoring(self, tmp_path: Path) -> None:
        """next_focus must direct maintainers to post-recovery monitoring (not owner merge review)."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "Post-recovery monitoring" in block or "post-recovery monitoring" in block, (
            "next_focus must reference post-recovery monitoring after PR #117 merged"
        )

    def test_next_focus_no_owner_merge_review_pending(self, tmp_path: Path) -> None:
        """next_focus must NOT say 'owner merge review pending' after PR #117 merged."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "owner merge review pending" not in block, (
            "next_focus must not say 'owner merge review pending' after PR #117 merged"
        )
        assert "pending owner merge" not in block, (
            "next_focus must not say 'pending owner merge' after PR #117 merged"
        )

    def test_no_stale_not_promoted_language(self, tmp_path: Path) -> None:
        """Must not say 'not promoted' after the candidate has been promoted."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "candidate was not promoted" not in block.lower(), (
            "recovered state must not say 'candidate was not promoted'"
        )

    def test_no_stale_push_failed_language(self, tmp_path: Path) -> None:
        """Must not foreground the push failure after successful recovery."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "promote push failed" not in block.lower() or "recovered" in block.lower(), (
            "if push-failure wording remains, recovery context must also appear"
        )

    def test_no_concrete_fitness_metrics_without_report(self, tmp_path: Path) -> None:
        """Must not embed concrete TP/FP/TN/FN values when no report is present.

        _run_update_with_ledger sets _REPORT_PATH to a nonexistent file, so
        the generator must fall back to N/A — not stale hard-coded values.
        """
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "8 / 0 / 7 / 0" not in block, (
            "Must not show stale TP/FP/TN/FN=8/0/7/0 when no fitness report is present"
        )
        assert "| Total Test Cases | 15 |" not in block, (
            "Must not show stale total_cases=15 when no fitness report is present"
        )

    def test_na_or_not_available_when_no_report(self, tmp_path: Path) -> None:
        """When no fitness report exists, README must use N/A or 'Not available'."""
        _, block = _run_update_with_ledger(
            tmp_path, self._LEDGER, self._GENOME, self._ps()
        )
        assert "N/A" in block or "Not available" in block, (
            "Must show N/A or 'Not available' for fitness metrics when no report exists"
        )
