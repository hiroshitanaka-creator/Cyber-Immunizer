"""tests/test_rollback_backtrack_docs.py — Tests for Phase 2-B rollback/backtrack design documents.

Verifies that:
- docs/ROLLBACK_BACKTRACK_DESIGN.md exists and contains mandatory design content
- README.md links to ROLLBACK_BACKTRACK_DESIGN.md
- docs/PHASE_2_PLAN.md links to ROLLBACK_BACKTRACK_DESIGN.md
- Phase 2-B is explicitly documented as design-only (no implementation)
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


class TestRollbackBacktrackDocExists:
    def test_rollback_backtrack_design_exists(self) -> None:
        """docs/ROLLBACK_BACKTRACK_DESIGN.md must exist."""
        doc = _PROJECT_ROOT / "docs" / "ROLLBACK_BACKTRACK_DESIGN.md"
        assert doc.exists(), (
            "docs/ROLLBACK_BACKTRACK_DESIGN.md is missing. "
            "This file is required for Phase 2-B rollback/backtrack design governance."
        )

    def test_rollback_backtrack_design_is_not_empty(self) -> None:
        """docs/ROLLBACK_BACKTRACK_DESIGN.md must not be empty."""
        doc = _PROJECT_ROOT / "docs" / "ROLLBACK_BACKTRACK_DESIGN.md"
        assert doc.exists(), "docs/ROLLBACK_BACKTRACK_DESIGN.md does not exist"
        content = doc.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, (
            "docs/ROLLBACK_BACKTRACK_DESIGN.md appears to be nearly empty"
        )


# ---------------------------------------------------------------------------
# ROLLBACK_BACKTRACK_DESIGN.md content tests
# ---------------------------------------------------------------------------


class TestRollbackBacktrackDesignContent:
    @pytest.fixture(autouse=True)
    def load_doc(self) -> None:
        doc = _PROJECT_ROOT / "docs" / "ROLLBACK_BACKTRACK_DESIGN.md"
        assert doc.exists(), "docs/ROLLBACK_BACKTRACK_DESIGN.md is required for these tests"
        self.content = doc.read_text(encoding="utf-8")

    def test_rollback_definition_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must define 'Rollback'."""
        assert "Rollback" in self.content or "rollback" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must contain a definition of Rollback"
        )
        assert (
            "直近または指定世代" in self.content
            or "取り消し" in self.content
            or "過去世代へ戻す" in self.content
            or "past generation" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must define Rollback as reverting to a past generation"
        )

    def test_backtrack_definition_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must define 'Backtrack'."""
        assert "Backtrack" in self.content or "backtrack" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must contain a definition of Backtrack"
        )
        assert (
            "複数世代" in self.content
            or "停滞" in self.content
            or "過去最高世代" in self.content
            or "best generation" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must define Backtrack as returning to the historically best generation"
        )

    def test_detector_py_in_scope(self) -> None:
        """core/detector.py must be listed as a file in scope for rollback/backtrack."""
        assert "core/detector.py" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must list core/detector.py as a file in scope"
        )

    def test_genome_json_in_scope(self) -> None:
        """data/genome.json must be listed as a file in scope for rollback/backtrack."""
        assert "data/genome.json" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must list data/genome.json as a file in scope"
        )

    def test_evolution_history_json_in_scope(self) -> None:
        """data/evolution_history.json must be listed as a file in scope for rollback/backtrack."""
        assert "data/evolution_history.json" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must list data/evolution_history.json as a file in scope"
        )

    def test_api_usage_ledger_not_rolled_back(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must state that api_usage_ledger.json must NOT be rolled back."""
        assert "api_usage_ledger.json" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must mention api_usage_ledger.json"
        )
        # Must mention that it is out of scope / must not be rolled back
        assert (
            "巻き戻してはならない" in self.content
            or "巻き戻さない" in self.content
            or "out of scope" in self.content.lower()
            or "絶対に巻き戻してはいけない" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must explicitly state that api_usage_ledger.json "
            "must NOT be rolled back"
        )

    def test_ast_policy_for_rollback_candidates(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must state that rollback candidates go through AST policy."""
        assert (
            "AST policy" in self.content
            or "AST ポリシー" in self.content
            or "ast policy" in self.content.lower()
            or "AST policyを通す" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must state that rollback candidates must pass AST policy"
        )

    def test_no_write_permission_for_generated_code(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must explicitly state the prohibition on running
        generated code in a job with write permissions.

        Mere presence of the words 'generated code' is insufficient —
        the document must contain an explicit prohibition phrase.
        """
        explicit_prohibition_found = (
            "generated codeをwrite権限jobで実行しない" in self.content
            or "write権限jobで実行しない" in self.content
            or "generated code must not run with write permissions" in self.content.lower()
            or "generated code must not be executed in write-permission jobs" in self.content.lower()
        )
        assert explicit_prohibition_found, (
            "ROLLBACK_BACKTRACK_DESIGN.md must contain an explicit prohibition such as "
            "'generated codeをwrite権限jobで実行しない' or "
            "'generated code must not run with write permissions'. "
            "Simply mentioning 'generated code' is not sufficient."
        )

    def test_no_write_permission_for_generated_code_regression_guard(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must NOT contain any text that permits running
        generated code with write permissions.

        This guards against accidental future document degradation.
        """
        prohibited_phrases = [
            # Permissive / positive assertion phrases
            "generated code may run with write permissions",
            "generated code can run with write permissions",
            "generated code is allowed in write-permission jobs",
            "generated code is allowed to run with write permissions",
            # Japanese equivalents permitting execution with write access
            "generated codeをwrite権限jobで実行する",
            "write権限でgenerated codeを実行する",
            "write権限でgenerated codeを実行してよい",
            "generated codeをwrite権限で実行してよい",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in self.content, (
                f"ROLLBACK_BACKTRACK_DESIGN.md must NOT contain '{phrase}'. "
                "This phrase would incorrectly permit running generated code with write permissions."
            )

    def test_dry_run_default_policy(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must state that dry-run is the default."""
        assert (
            "dry-run" in self.content
            or "dry_run" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must mention dry-run"
        )
        assert (
            "デフォルト" in self.content
            or "default" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must state that dry-run is the default"
        )

    def test_human_owner_approval_required(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must state that Project Owner approval is required."""
        assert "Project Owner" in self.content, (
            "ROLLBACK_BACKTRACK_DESIGN.md must mention Project Owner"
        )
        assert (
            "承認" in self.content
            or "approval" in self.content.lower()
            or "承認なしにcommitしない" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must state that Project Owner approval is required "
            "before committing rollback/backtrack"
        )

    def test_future_cli_design_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must include a Future CLI design section."""
        assert (
            "Future CLI" in self.content
            or "future cli" in self.content.lower()
            or "rollback_generation.py" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must include a Future CLI design section "
            "with example commands (e.g., scripts/rollback_generation.py)"
        )

    def test_phase2b_design_only_stated(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must state that Phase 2-B is design-only, not implemented."""
        assert (
            "design-only" in self.content
            or "設計文書" in self.content
            or "実装しない" in self.content
            or "Phase 2-B" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must state that Phase 2-B is design-only "
            "and rollback automation is not yet implemented"
        )

    def test_non_goals_section_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must have a Non-goals section."""
        assert (
            "Non-goals" in self.content
            or "non-goals" in self.content.lower()
            or "実装しない" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must include a Non-goals section listing what "
            "is NOT implemented in Phase 2-B"
        )

    def test_safety_invariants_section_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must have a Safety invariants section."""
        assert (
            "Safety invariants" in self.content
            or "safety invariants" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must include a Safety invariants section"
        )

    def test_rollback_trigger_conditions_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must list rollback trigger conditions."""
        assert (
            "Rollback trigger" in self.content
            or "rollback trigger" in self.content.lower()
            or "trigger conditions" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must list rollback trigger conditions"
        )

    def test_backtrack_trigger_conditions_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must list backtrack trigger conditions."""
        assert (
            "Backtrack trigger" in self.content
            or "backtrack trigger" in self.content.lower()
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must list backtrack trigger conditions"
        )

    def test_audit_log_fields_present(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must list required audit log fields."""
        assert (
            "audit log" in self.content.lower()
            or "action_type" in self.content
            or "rollback_reason" in self.content
        ), (
            "ROLLBACK_BACKTRACK_DESIGN.md must list required audit log fields"
        )

    def test_ledger_not_in_apply_path(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must explicitly state that the API usage ledger
        is NOT modified or rolled back during rollback/backtrack operations.

        Mere presence of the words 'API usage ledger' is insufficient —
        the document must contain an explicit prohibition phrase.
        """
        explicit_prohibition_found = (
            "API usage ledgerは変更しない" in self.content
            or "API usage ledgerは巻き戻さない" in self.content
            or "api_usage_ledger.json must NOT be rolled back" in self.content
            or "api_usage_ledger.json must not be rolled back" in self.content
            or "API usage ledger is not modified" in self.content
            or "API usage ledger must not be modified" in self.content
        )
        assert explicit_prohibition_found, (
            "ROLLBACK_BACKTRACK_DESIGN.md must contain an explicit prohibition such as "
            "'API usage ledgerは変更しない' or 'API usage ledgerは巻き戻さない'. "
            "Simply mentioning 'API usage ledger' is not sufficient."
        )

    def test_ledger_not_in_apply_path_regression_guard(self) -> None:
        """ROLLBACK_BACKTRACK_DESIGN.md must NOT contain any text that includes the ledger
        in the rollback/backtrack scope, or permits modification of the ledger.

        This guards against accidental future document degradation.
        """
        prohibited_phrases = [
            # Inclusion in rollback scope
            "API usage ledger is included in rollback",
            "api_usage_ledger.json をrollback対象に含める",
            "api_usage_ledger.json もrollbackする",
            "api_usage_ledger.json を巻き戻す",
            "ledgerをrollbackする",
            "ledger も rollback 対象",
            # Permission to modify
            "API usage ledger may be modified",
            "API usage ledger can be modified",
            "API usage ledger is modified",
            "api_usage_ledger.json を変更してよい",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in self.content, (
                f"ROLLBACK_BACKTRACK_DESIGN.md must NOT contain '{phrase}'. "
                "The API usage ledger must never be included in rollback/backtrack scope "
                "and must never be modified during rollback/backtrack operations."
            )


# ---------------------------------------------------------------------------
# README.md link tests
# ---------------------------------------------------------------------------


class TestReadmeLinksToRollbackBacktrackDesign:
    @pytest.fixture(autouse=True)
    def load_readme(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md is required for these tests"
        self.content = readme.read_text(encoding="utf-8")

    def test_readme_links_to_rollback_backtrack_design(self) -> None:
        """README.md must contain a link to docs/ROLLBACK_BACKTRACK_DESIGN.md."""
        assert "ROLLBACK_BACKTRACK_DESIGN.md" in self.content, (
            "README.md must link to docs/ROLLBACK_BACKTRACK_DESIGN.md"
        )

    def test_readme_states_phase2b_is_design_only(self) -> None:
        """README.md must state that Phase 2-B is design-only."""
        assert (
            "design-only" in self.content
            or "Phase 2-B" in self.content
        ), (
            "README.md must state that Phase 2-B rollback design is design-only"
        )

    def test_readme_states_no_rollback_automation_yet(self) -> None:
        """README.md must state that no rollback automation is implemented yet."""
        readme_lower = self.content.lower()
        assert (
            "no rollback automation" in readme_lower
            or "not implemented yet" in readme_lower
            or "実装なし" in self.content
            or "not yet implemented" in readme_lower
        ), (
            "README.md must state that rollback automation is not yet implemented"
        )


# ---------------------------------------------------------------------------
# PHASE_2_PLAN.md link tests
# ---------------------------------------------------------------------------


class TestPhase2PlanLinksToRollbackBacktrackDesign:
    @pytest.fixture(autouse=True)
    def load_plan(self) -> None:
        plan = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"
        assert plan.exists(), "docs/PHASE_2_PLAN.md is required for these tests"
        self.content = plan.read_text(encoding="utf-8")

    def test_phase2_plan_links_to_rollback_backtrack_design(self) -> None:
        """docs/PHASE_2_PLAN.md must reference docs/ROLLBACK_BACKTRACK_DESIGN.md."""
        assert "ROLLBACK_BACKTRACK_DESIGN.md" in self.content, (
            "docs/PHASE_2_PLAN.md must contain a reference to docs/ROLLBACK_BACKTRACK_DESIGN.md"
        )

    def test_phase2_plan_states_rollback_section_is_design_only(self) -> None:
        """docs/PHASE_2_PLAN.md must state that rollback/backtrack is design-only."""
        assert (
            "design-only" in self.content
            or "設計文書化" in self.content
            or "設計文書のみ" in self.content
            or "実装なし" in self.content
        ), (
            "docs/PHASE_2_PLAN.md must state that rollback/backtrack work in Phase 2-B "
            "is design-only (no implementation)"
        )
