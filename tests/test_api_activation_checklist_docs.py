"""tests/test_api_activation_checklist_docs.py — Phase 2-E: API Activation Checklist hardening tests.

Verifies that:
- docs/API_ACTIVATION_CHECKLIST.md exists with all required sections
- Safety boundaries are documented (no API key registration, no live_model_enabled=true,
  no Gemini API call in Phase 2-E)
- Budget/ledger governance is documented
- Workflow/schedule constraints are documented
- Privacy/data minimization constraints are documented
- README.md and PHASE_2_PLAN.md link to the checklist and show Phase 2-E completed
- Dangerous/forbidden phrases are NOT present in target documents
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_CHECKLIST = _PROJECT_ROOT / "docs" / "API_ACTIVATION_CHECKLIST.md"
_README = _PROJECT_ROOT / "README.md"
_PHASE2_PLAN = _PROJECT_ROOT / "docs" / "PHASE_2_PLAN.md"

# All target documents for dangerous-phrase regression guard
_TARGET_DOCS = [_CHECKLIST, _README, _PHASE2_PLAN]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


class _ChecklistFixture:
    """Mixin to load docs/API_ACTIVATION_CHECKLIST.md."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _CHECKLIST.exists(), (
            "docs/API_ACTIVATION_CHECKLIST.md must exist — run Phase 2-E to create it"
        )
        self.content = _CHECKLIST.read_text(encoding="utf-8")


def _extract_phase_row(content: str, phase_label: str) -> str:
    """Extract the Markdown table row where the first column contains phase_label."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = stripped.split("|")
        if len(parts) >= 3 and phase_label in parts[1]:
            return line
    return ""


# ---------------------------------------------------------------------------
# 1. Document existence
# ---------------------------------------------------------------------------


class TestApiActivationChecklistExists:
    def test_checklist_exists(self) -> None:
        """docs/API_ACTIVATION_CHECKLIST.md must exist."""
        assert _CHECKLIST.exists(), (
            "docs/API_ACTIVATION_CHECKLIST.md is missing. "
            "Phase 2-E must create this file."
        )

    def test_checklist_not_empty(self) -> None:
        """docs/API_ACTIVATION_CHECKLIST.md must not be empty."""
        assert _CHECKLIST.exists(), "docs/API_ACTIVATION_CHECKLIST.md does not exist"
        content = _CHECKLIST.read_text(encoding="utf-8")
        assert len(content.strip()) > 500, (
            "docs/API_ACTIVATION_CHECKLIST.md appears to be nearly empty"
        )


# ---------------------------------------------------------------------------
# 2. Required sections
# ---------------------------------------------------------------------------


class TestApiActivationChecklistSections(_ChecklistFixture):
    def test_has_purpose_section(self) -> None:
        """Checklist must have a Purpose section."""
        assert "## Purpose" in self.content or "# Purpose" in self.content or (
            "Purpose" in self.content
        ), "docs/API_ACTIVATION_CHECKLIST.md must have a Purpose section"

    def test_has_current_phase_status_section(self) -> None:
        """Checklist must have a Current phase status section."""
        assert "Current phase status" in self.content, (
            "docs/API_ACTIVATION_CHECKLIST.md must have a 'Current phase status' section"
        )

    def test_has_human_owner_approval_gate_section(self) -> None:
        """Checklist must have a Project Owner approval gate section."""
        assert "Project Owner approval gate" in self.content or (
            "Project Owner" in self.content and "approval gate" in self.content
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must have a 'Project Owner approval gate' section"
        )

    def test_has_required_pre_activation_checks_section(self) -> None:
        """Checklist must have a Required pre-activation checks section."""
        assert "Required pre-activation checks" in self.content or (
            "pre-activation checks" in self.content
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must have a 'Required pre-activation checks' section"
        )

    def test_has_fail_closed_conditions_section(self) -> None:
        """Checklist must have a Fail-closed conditions section."""
        assert "Fail-closed conditions" in self.content or (
            "fail-closed conditions" in self.content.lower()
        ), (
            "docs/API_ACTIVATION_CHECKLIST.md must have a 'Fail-closed conditions' section"
        )

    def test_has_non_goals_section(self) -> None:
        """Checklist must have a Non-goals section."""
        assert "Non-goals" in self.content or "non-goals" in self.content.lower(), (
            "docs/API_ACTIVATION_CHECKLIST.md must have a 'Non-goals' section"
        )


# ---------------------------------------------------------------------------
# 3. Safety boundaries
# ---------------------------------------------------------------------------


class TestApiActivationChecklistSafetyBoundaries(_ChecklistFixture):
    def test_states_no_api_key_registration_in_phase2e(self) -> None:
        """Checklist must state that GEMINI_API_KEY registration is not done in Phase 2-E."""
        content_lower = self.content.lower()
        # Must mention GEMINI_API_KEY and indicate it's not registered
        assert "GEMINI_API_KEY" in self.content, (
            "Checklist must mention GEMINI_API_KEY"
        )
        assert (
            "not registered" in content_lower
            or "未登録" in self.content
            or "登録を行わない" in self.content
            or "registration" in content_lower
        ), (
            "Checklist must state that GEMINI_API_KEY is not registered in Phase 2-E"
        )

    def test_states_no_live_model_enabled_true_in_phase2e(self) -> None:
        """Checklist must confirm live_model_enabled=false in Phase 2-E.

        live_model_enabled=true must NOT be treated as positive evidence that the
        document correctly records the constraint.  The checklist must explicitly
        state the value is false (e.g. 'live_model_enabled | false' in the Current
        phase status table) and/or use prohibition language such as 'にしない' or
        'trueにしない'.  A bare occurrence of 'live_model_enabled=true' anywhere in
        the document (even in a non-goal bullet) is insufficient and must not pass
        this test.
        """
        assert "live_model_enabled" in self.content, (
            "Checklist must mention live_model_enabled"
        )
        content_lower = self.content.lower()

        # Must state live_model_enabled=false explicitly, NOT just mention =true
        assert (
            "live_model_enabled=false" in content_lower
            or "live_model_enabled | false" in content_lower
            or "live_model_enabled** | false" in content_lower
            or "にしない" in self.content
            or "trueにしない" in self.content
        ), (
            "Checklist must explicitly state live_model_enabled=false or use prohibition "
            "language; a bare 'live_model_enabled=true' is not sufficient evidence"
        )

        # The Current phase status section must explicitly show false
        if "Current phase status" in self.content:
            status_start = self.content.find("Current phase status")
            status_end = self.content.find("\n---", status_start + 1)
            if status_end == -1:
                status_end = status_start + 2000
            status_block = self.content[status_start:status_end].lower()
            assert (
                "live_model_enabled | false" in status_block
                or "live_model_enabled=false" in status_block
                or ("live_model_enabled" in status_block and "false" in status_block)
            ), (
                "Current phase status section must explicitly show live_model_enabled = false, "
                "not merely mention live_model_enabled=true"
            )

    def test_states_no_gemini_api_call_in_phase2e(self) -> None:
        """Checklist must state that Gemini API calls are not executed in Phase 2-E."""
        content_lower = self.content.lower()
        assert (
            "gemini api call" in content_lower
            or "gemini api calls" in content_lower
            or "Gemini API call" in self.content
        ), (
            "Checklist must mention Gemini API calls"
        )
        assert (
            "not executed" in content_lower
            or "行わない" in self.content
            or "呼ばない" in self.content
            or "never call" in content_lower
            or "phase 2-e では" in content_lower
        ), (
            "Checklist must state that Gemini API calls are not made in Phase 2-E"
        )

    def test_states_phase3_requires_human_owner_decision(self) -> None:
        """Checklist must state that Phase 3 requires Project Owner decision."""
        assert "Phase 3" in self.content, (
            "Checklist must mention Phase 3"
        )
        content_lower = self.content.lower()
        assert (
            "project owner" in content_lower
            or "Project Owner" in self.content
        ), (
            "Checklist must mention Project Owner"
        )
        assert (
            "requires" in content_lower
            or "decision" in content_lower
            or "判断" in self.content
            or "明示的" in self.content
        ), (
            "Checklist must state that Phase 3 requires Project Owner decision"
        )

    def test_states_api_activation_in_dedicated_pr(self) -> None:
        """Checklist must state that API activation must happen in a dedicated PR."""
        content_lower = self.content.lower()
        assert (
            "dedicated pr" in content_lower
            or "dedicated PR" in self.content
            or "専用 PR" in self.content
            or "専用PR" in self.content
        ), (
            "Checklist must state that API activation must happen in a dedicated PR"
        )

    def test_states_no_github_secrets_operation_in_phase2e(self) -> None:
        """Checklist must state that GitHub Secrets operations are not done in Phase 2-E."""
        content_lower = self.content.lower()
        assert (
            "github secrets" in content_lower
            or "GitHub Secrets" in self.content
        ), (
            "Checklist must mention GitHub Secrets"
        )
        # Non-goals or current status must indicate no Secrets operations
        assert (
            "non-goals" in content_lower
            or "non_goals" in content_lower
            or "行わない" in self.content
            or "操作" in self.content
        ), (
            "Checklist must state that GitHub Secrets operations are not done in Phase 2-E"
        )


# ---------------------------------------------------------------------------
# 4. Budget / ledger governance
# ---------------------------------------------------------------------------


class TestApiActivationChecklistBudgetLedger(_ChecklistFixture):
    def test_mentions_monthly_budget_cap(self) -> None:
        """Checklist must mention monthly budget cap."""
        content_lower = self.content.lower()
        assert (
            "monthly budget cap" in content_lower
            or "monthly_api_budget" in content_lower
            or "月次上限" in self.content
            or "monthly" in content_lower
        ) and (
            "budget" in content_lower
            or "予算" in self.content
        ), (
            "Checklist must mention monthly budget cap"
        )

    def test_mentions_daily_budget_cap(self) -> None:
        """Checklist must mention daily budget cap."""
        content_lower = self.content.lower()
        assert (
            "daily budget cap" in content_lower
            or "daily_api_budget" in content_lower
            or "日次上限" in self.content
            or "daily" in content_lower
        ) and (
            "budget" in content_lower
            or "予算" in self.content
        ), (
            "Checklist must mention daily budget cap"
        )

    def test_ledger_corruption_fail_closed(self) -> None:
        """Checklist must state that ledger corruption fails closed."""
        content_lower = self.content.lower()
        assert "ledger" in content_lower, (
            "Checklist must mention the API usage ledger"
        )
        assert (
            "corruption" in content_lower
            or "fail-closed" in content_lower
            or "fails closed" in content_lower
            or "破損" in self.content
        ), (
            "Checklist must mention that ledger corruption fails closed"
        )

    def test_ledger_missing_fail_closed(self) -> None:
        """Checklist must state that ledger missing fails closed."""
        content_lower = self.content.lower()
        assert (
            "ledger missing fails closed" in content_lower
            or (
                "missing" in content_lower
                and "fails closed" in content_lower
                and "ledger" in content_lower
            )
            or "欠損" in self.content
        ), (
            "Checklist must state that a missing ledger fails closed"
        )

    def test_ledger_write_failure_fails_workflow(self) -> None:
        """Checklist must state that ledger write failure fails the workflow."""
        content_lower = self.content.lower()
        assert (
            "write failure fails workflow" in content_lower
            or (
                "write failure" in content_lower
                and "workflow" in content_lower
                and "ledger" in content_lower
            )
            or (
                "書き込み失敗" in self.content
                and "ledger" in content_lower
            )
        ), (
            "Checklist must state that ledger write failure fails the workflow"
        )

    def test_ledger_not_reset_or_overwritten_or_rolled_back(self) -> None:
        """Checklist must state that ledger is not reset, overwritten, or rolled back."""
        content_lower = self.content.lower()
        assert "ledger" in content_lower
        # Must mention not being reset/overwritten/rolled back
        assert (
            "not reset" in content_lower
            or "overwritten" in content_lower
            or "rolled back" in content_lower
            or "リセット" in self.content
            or "上書き" in self.content
            or "巻き戻し" in self.content
        ), (
            "Checklist must state that ledger is not reset, overwritten, or rolled back"
        )

    def test_ledger_changed_requires_persist_ledger_success(self) -> None:
        """Checklist must state that ledger_changed=true requires persist-ledger success."""
        content_lower = self.content.lower()
        assert (
            "ledger_changed=true" in content_lower
            or "ledger_changed" in content_lower
        ), (
            "Checklist must mention ledger_changed"
        )
        assert (
            "persist-ledger" in content_lower
            or "persist_ledger" in content_lower
        ), (
            "Checklist must mention persist-ledger in relation to ledger_changed"
        )


# ---------------------------------------------------------------------------
# 5. Workflow / schedule constraints
# ---------------------------------------------------------------------------


class TestApiActivationChecklistWorkflowSchedule(_ChecklistFixture):
    def test_schedule_remains_noop(self) -> None:
        """Checklist must state that schedule remains noop."""
        content_lower = self.content.lower()
        assert (
            "schedule" in content_lower
            or "スケジュール" in self.content
        ), (
            "Checklist must mention schedule"
        )
        assert (
            "noop" in content_lower
        ), (
            "Checklist must state that schedule must remain noop"
        )

    def test_normal_ci_must_not_call_gemini(self) -> None:
        """Checklist must state that normal CI must not call Gemini."""
        content_lower = self.content.lower()
        assert (
            "normal ci" in content_lower
            or "通常ci" in content_lower
        ), (
            "Checklist must mention normal CI"
        )
        assert (
            "never call gemini" in content_lower
            or "must never call" in content_lower
            or "呼ばない" in self.content
        ), (
            "Checklist must state that normal CI must never call Gemini"
        )

    def test_workflow_dispatch_paid_credit_is_explicit(self) -> None:
        """Checklist must state that workflow_dispatch for paid-credit is explicit opt-in."""
        content_lower = self.content.lower()
        assert (
            "workflow_dispatch" in content_lower
            or "paid-credit" in content_lower
        ), (
            "Checklist must mention workflow_dispatch or paid-credit path"
        )
        assert (
            "explicit" in content_lower
            or "opt-in" in content_lower
            or "手動" in self.content
        ), (
            "Checklist must state that paid-credit path is explicit opt-in"
        )

    def test_no_contents_write_in_normal_ci(self) -> None:
        """Checklist must confirm normal CI has no 'contents: write' (read-only only).

        A bare occurrence of 'contents: write' anywhere in the document is NOT
        sufficient — the check must confirm a prohibition context:
          - 'read-only' or 'read only' (the CI is described as read-only), OR
          - 'contents: read' (the permitted permission is named), OR
          - 'No `contents: write`' / 'no contents: write' (explicit prohibition).

        This prevents a document that says 'normal CI uses contents: write' from
        passing the test.
        """
        content_lower = self.content.lower()

        has_read_only = "read-only" in content_lower or "read only" in content_lower
        has_contents_read = "contents: read" in content_lower
        # Accept backtick-quoted form ("no `contents: write`") or plain form
        has_no_write_prohibition = (
            "no `contents: write`" in content_lower
            or "no contents: write" in content_lower
            or "no contents:write" in content_lower
        )

        assert has_read_only or has_contents_read or has_no_write_prohibition, (
            "Checklist must confirm normal CI is read-only / has no 'contents: write' "
            "permission using prohibition context (e.g. 'CI workflow remains read-only', "
            "'No `contents: write` in normal CI', or 'contents: read'); "
            "a bare 'contents: write' mention is insufficient"
        )


# ---------------------------------------------------------------------------
# 6. Privacy / data minimization
# ---------------------------------------------------------------------------


class TestApiActivationChecklistPrivacy(_ChecklistFixture):
    def test_send_repository_full_text_false(self) -> None:
        """Checklist must mention send_repository_full_text=false."""
        assert (
            "send_repository_full_text" in self.content
            or "send_repository_full_text=false" in self.content
        ), (
            "Checklist must mention send_repository_full_text=false"
        )

    def test_send_raw_payloads_false(self) -> None:
        """Checklist must mention send_raw_payloads=false."""
        assert (
            "send_raw_payloads" in self.content
            or "send_raw_payloads=false" in self.content
        ), (
            "Checklist must mention send_raw_payloads=false"
        )

    def test_send_secrets_false(self) -> None:
        """Checklist must mention send_secrets=false."""
        assert (
            "send_secrets" in self.content
            or "send_secrets=false" in self.content
        ), (
            "Checklist must mention send_secrets=false"
        )

    def test_no_secrets_sent_to_gemini(self) -> None:
        """Checklist must state that no secrets are sent to Gemini."""
        content_lower = self.content.lower()
        assert (
            "no secrets" in content_lower
            or "シークレット" in self.content
            or "secrets" in content_lower
        ) and (
            "gemini" in content_lower
        ), (
            "Checklist must state that no secrets are sent to Gemini"
        )

    def test_no_raw_exploit_payloads_sent(self) -> None:
        """Checklist must state that no raw exploit payloads are sent."""
        content_lower = self.content.lower()
        assert (
            "raw exploit payloads" in content_lower
            or "raw_payloads" in content_lower
            or "エクスプロイト" in self.content
        ), (
            "Checklist must mention that raw exploit payloads are not sent"
        )


# ---------------------------------------------------------------------------
# 7. README / PHASE_2_PLAN link checks and Phase 2-E completed
# ---------------------------------------------------------------------------


class TestReadmeAndPlanChecklistLinks:
    @pytest.fixture(autouse=True)
    def _load_both(self) -> None:
        assert _README.exists(), "README.md must exist"
        assert _PHASE2_PLAN.exists(), "docs/PHASE_2_PLAN.md must exist"
        self.readme = _README.read_text(encoding="utf-8")
        self.plan = _PHASE2_PLAN.read_text(encoding="utf-8")

    def test_readme_links_to_checklist(self) -> None:
        """README.md must link to docs/API_ACTIVATION_CHECKLIST.md."""
        assert "API_ACTIVATION_CHECKLIST.md" in self.readme, (
            "README.md must contain a link to docs/API_ACTIVATION_CHECKLIST.md"
        )

    def test_phase2_plan_links_to_checklist(self) -> None:
        """docs/PHASE_2_PLAN.md must link to docs/API_ACTIVATION_CHECKLIST.md."""
        assert "API_ACTIVATION_CHECKLIST.md" in self.plan, (
            "docs/PHASE_2_PLAN.md must contain a link to docs/API_ACTIVATION_CHECKLIST.md"
        )

    def test_readme_phase2e_completed(self) -> None:
        """README.md Phase 2-E table row must show Completed / ✅."""
        assert "Phase 2-E" in self.readme, "README.md must mention Phase 2-E"
        row = _extract_phase_row(self.readme, "Phase 2-E")
        assert row, "README.md must contain a Markdown table row for Phase 2-E"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
        )
        assert has_completed, (
            f"README.md Phase 2-E row must show Completed/✅, got: {row!r}"
        )

    def test_phase2_plan_phase2e_completed(self) -> None:
        """docs/PHASE_2_PLAN.md Phase 2-E table row must show Completed / ✅."""
        assert "Phase 2-E" in self.plan, "PHASE_2_PLAN.md must mention Phase 2-E"
        row = _extract_phase_row(self.plan, "Phase 2-E")
        assert row, "PHASE_2_PLAN.md must contain a Markdown table row for Phase 2-E"
        has_completed = (
            "Completed" in row
            or "completed" in row
            or "✅" in row
        )
        assert has_completed, (
            f"PHASE_2_PLAN.md Phase 2-E row must show Completed/✅, got: {row!r}"
        )

    def test_readme_phase3_not_started(self) -> None:
        """README.md must state that Phase 3 is not started."""
        content_lower = self.readme.lower()
        assert (
            "phase 3 is not started" in content_lower
            or "phase 3 not started" in content_lower
            or "phase 3（実" in self.readme and "project owner" in content_lower
        ), (
            "README.md must state that Phase 3 is not started"
        )

    def test_phase2_plan_phase3_not_started(self) -> None:
        """PHASE_2_PLAN.md must state that Phase 3 is not started / requires Project Owner decision."""
        content_lower = self.plan.lower()
        assert (
            "phase 3 not started" in content_lower
            or "phase 3 requires" in content_lower
            or "phase 3 への移行は project owner" in content_lower
            or (
                "phase 3" in content_lower
                and "project owner" in content_lower
                and "decision" in content_lower
            )
        ), (
            "PHASE_2_PLAN.md must state that Phase 3 is not started / requires Project Owner decision"
        )

    def test_readme_api_not_connected(self) -> None:
        """README.md must state that API remains not connected."""
        content_lower = self.readme.lower()
        assert (
            "api remains not connected" in content_lower
            or "not connected" in content_lower
            or "api connection | not connected" in content_lower
            or "未接続" in self.readme
        ), (
            "README.md must state that API remains not connected"
        )

    def test_phase2_plan_api_not_connected(self) -> None:
        """PHASE_2_PLAN.md must state that API remains disconnected."""
        content_lower = self.plan.lower()
        assert (
            "api remains disconnected" in content_lower
            or "api 未接続" in self.plan
            or "api未接続" in self.plan
            or "api is not connected" in content_lower
            or "未接続" in self.plan
        ), (
            "PHASE_2_PLAN.md must state that API remains not connected"
        )

    def test_readme_phase2_complete_does_not_mean_api_connected(self) -> None:
        """README.md must not conflate Phase 2 completion with API activation."""
        content_lower = self.readme.lower()
        # Must not say Phase 3 started
        assert "phase 3 started" not in content_lower, (
            "README.md must NOT say Phase 3 started"
        )
        # Must not say API connected
        assert "api connected" not in content_lower, (
            "README.md must NOT say API connected"
        )

    def test_phase2_plan_complete_does_not_mean_api_connected(self) -> None:
        """PHASE_2_PLAN.md must not conflate Phase 2 completion with API activation."""
        content_lower = self.plan.lower()
        # Must explicitly acknowledge that completion ≠ Phase 3 is underway
        assert (
            "does not mean phase 3 is underway" in content_lower
            or "does not mean phase 3" in content_lower
            or "phase 3 requires project owner" in content_lower
            or "phase 3 への移行は project owner" in content_lower
        ), (
            "PHASE_2_PLAN.md must clarify that Phase 2 complete does not mean Phase 3 is underway"
        )

    def test_readme_phase2e_states_docs_tests_only(self) -> None:
        """README.md must state Phase 2-E is docs/tests only."""
        content_lower = self.readme.lower()
        assert (
            "docs/tests only" in content_lower
            or "docs only" in content_lower
            or "documents only" in content_lower
        ), (
            "README.md must state that Phase 2-E is docs/tests only"
        )

    def test_phase2_plan_phase2e_states_docs_tests_only(self) -> None:
        """PHASE_2_PLAN.md must state Phase 2-E is docs-only."""
        content_lower = self.plan.lower()
        assert (
            "docs-only" in content_lower
            or "docs/tests only" in content_lower
            or "docs only" in content_lower
        ), (
            "PHASE_2_PLAN.md must state that Phase 2-E is docs-only"
        )


# ---------------------------------------------------------------------------
# 8. Forbidden / dangerous phrase regression guard
# ---------------------------------------------------------------------------


class TestForbiddenPhrases:
    """Ensure dangerous phrases are NOT present in API_ACTIVATION_CHECKLIST.md,
    README.md, or PHASE_2_PLAN.md.

    These phrases represent current-state affirmations, permission grants, or
    false-started claims that must never appear in the documents.
    Prohibition contexts (e.g. "do not set X") are allowed because they do NOT
    produce exact substring matches for the forbidden phrases below.
    """

    @pytest.fixture(autouse=True)
    def _load_docs(self) -> None:
        assert _CHECKLIST.exists(), "docs/API_ACTIVATION_CHECKLIST.md must exist"
        assert _README.exists(), "README.md must exist"
        assert _PHASE2_PLAN.exists(), "docs/PHASE_2_PLAN.md must exist"
        self.docs = {
            "API_ACTIVATION_CHECKLIST.md": _CHECKLIST.read_text(encoding="utf-8"),
            "README.md": _README.read_text(encoding="utf-8"),
            "PHASE_2_PLAN.md": _PHASE2_PLAN.read_text(encoding="utf-8"),
        }

    def _assert_phrase_absent(self, phrase: str) -> None:
        """Assert that the phrase does not appear in any target document."""
        for doc_name, content in self.docs.items():
            assert phrase not in content, (
                f"{doc_name} must NOT contain the phrase {phrase!r} "
                "(this phrase represents a dangerous affirmative or permission statement)"
            )

    # --- English dangerous phrases ---

    def test_no_phase3_started(self) -> None:
        """'Phase 3 started' must not appear in any target document."""
        self._assert_phrase_absent("Phase 3 started")

    def test_no_phase3_is_in_progress(self) -> None:
        """'Phase 3 is in progress' must not appear in any target document."""
        self._assert_phrase_absent("Phase 3 is in progress")

    def test_no_api_is_connected(self) -> None:
        """'API is connected' must not appear in any target document."""
        self._assert_phrase_absent("API is connected")

    def test_no_api_connected_as_assertion(self) -> None:
        """'API connected' must not appear in any target document as an affirmative assertion.

        Note: 'API is not connected', 'API remains not connected', 'API not connected'
        are all safe because they do NOT contain 'API connected' as a substring.
        """
        self._assert_phrase_absent("API connected")

    def test_no_gemini_api_is_enabled(self) -> None:
        """'Gemini API is enabled' must not appear in any target document."""
        self._assert_phrase_absent("Gemini API is enabled")

    def test_no_gemini_api_key_is_registered(self) -> None:
        """'GEMINI_API_KEY is registered' must not appear in any target document."""
        self._assert_phrase_absent("GEMINI_API_KEY is registered")

    def test_no_live_model_enabled_true_is_active(self) -> None:
        """'live_model_enabled=true is active' must not appear in any target document."""
        self._assert_phrase_absent("live_model_enabled=true is active")

    def test_no_live_model_enabled_true_in_phase2e_as_permission(self) -> None:
        """'live_model_enabled=true in Phase 2-E' must not appear as a permission statement."""
        self._assert_phrase_absent("live_model_enabled=true in Phase 2-E")

    def test_no_phase2e_calls_gemini_api(self) -> None:
        """'Phase 2-E calls Gemini API' must not appear in any target document."""
        self._assert_phrase_absent("Phase 2-E calls Gemini API")

    def test_no_schedule_calls_gemini_api(self) -> None:
        """'schedule calls Gemini API' must not appear in any target document."""
        self._assert_phrase_absent("schedule calls Gemini API")

    def test_no_normal_ci_calls_gemini_api(self) -> None:
        """'normal CI calls Gemini API' must not appear in any target document."""
        self._assert_phrase_absent("normal CI calls Gemini API")

    def test_no_budget_cap_is_optional(self) -> None:
        """'budget cap is optional' must not appear in any target document."""
        self._assert_phrase_absent("budget cap is optional")

    def test_no_ledger_can_be_reset(self) -> None:
        """'ledger can be reset' must not appear in any target document."""
        self._assert_phrase_absent("ledger can be reset")

    def test_no_ledger_may_be_overwritten(self) -> None:
        """'ledger may be overwritten' must not appear in any target document."""
        self._assert_phrase_absent("ledger may be overwritten")

    def test_no_ledger_can_be_rolled_back(self) -> None:
        """'ledger can be rolled back' must not appear in any target document."""
        self._assert_phrase_absent("ledger can be rolled back")

    def test_no_human_owner_approval_is_optional(self) -> None:
        """'Project Owner approval is optional' must not appear in any target document."""
        self._assert_phrase_absent("Project Owner approval is optional")

    def test_no_gpt_audit_gate_approval_is_optional(self) -> None:
        """'GPT Audit Gate approval is optional' must not appear in any target document."""
        self._assert_phrase_absent("GPT Audit Gate approval is optional")

    def test_no_codex_review_is_optional(self) -> None:
        """'Codex review is optional' must not appear in any target document."""
        self._assert_phrase_absent("Codex review is optional")

    def test_no_api_key_may_be_stored_in_repository(self) -> None:
        """'API key may be stored in repository' must not appear in any target document."""
        self._assert_phrase_absent("API key may be stored in repository")

    # --- Japanese dangerous phrases ---

    def test_no_phase3_started_japanese(self) -> None:
        """'Phase 3開始済み' must not appear in any target document."""
        self._assert_phrase_absent("Phase 3開始済み")

    def test_no_api_connected_japanese(self) -> None:
        """'API接続済み' must not appear in any target document."""
        self._assert_phrase_absent("API接続済み")

    def test_no_gemini_api_enabled_japanese(self) -> None:
        """'Gemini API有効化済み' must not appear in any target document."""
        self._assert_phrase_absent("Gemini API有効化済み")

    def test_no_gemini_api_key_registered_japanese(self) -> None:
        """'GEMINI_API_KEY登録済み' must not appear in any target document."""
        self._assert_phrase_absent("GEMINI_API_KEY登録済み")

    def test_no_phase2e_live_model_true_japanese(self) -> None:
        """'Phase 2-Eでlive_model_enabled=true' must not appear in any target document.

        Note: 'Phase 2-EではGemini...' is safe because 'では' breaks the substring match.
        """
        self._assert_phrase_absent("Phase 2-Eでlive_model_enabled=true")

    def test_no_phase2e_calls_gemini_api_japanese(self) -> None:
        """'Phase 2-EでGemini APIを呼ぶ' must not appear in any target document."""
        self._assert_phrase_absent("Phase 2-EでGemini APIを呼ぶ")

    def test_no_schedule_calls_gemini_api_japanese(self) -> None:
        """'scheduleでGemini APIを呼ぶ' must not appear in any target document."""
        self._assert_phrase_absent("scheduleでGemini APIを呼ぶ")

    def test_no_normal_ci_calls_gemini_api_japanese(self) -> None:
        """'通常CIでGemini APIを呼ぶ' must not appear in any target document."""
        self._assert_phrase_absent("通常CIでGemini APIを呼ぶ")

    def test_no_budget_cap_optional_japanese(self) -> None:
        """'予算上限は任意' must not appear in any target document."""
        self._assert_phrase_absent("予算上限は任意")

    def test_no_ledger_reset_japanese(self) -> None:
        """'ledgerをリセットしてよい' must not appear in any target document."""
        self._assert_phrase_absent("ledgerをリセットしてよい")

    def test_no_ledger_overwrite_japanese(self) -> None:
        """'ledgerを上書きしてよい' must not appear in any target document."""
        self._assert_phrase_absent("ledgerを上書きしてよい")

    def test_no_ledger_rollback_japanese(self) -> None:
        """'ledgerを巻き戻してよい' must not appear in any target document."""
        self._assert_phrase_absent("ledgerを巻き戻してよい")

    def test_no_human_owner_approval_unnecessary_japanese(self) -> None:
        """'Project Owner承認は不要' must not appear in any target document."""
        self._assert_phrase_absent("Project Owner承認は不要")

    def test_no_gpt_audit_gate_approval_unnecessary_japanese(self) -> None:
        """'GPT Audit Gate承認は不要' must not appear in any target document."""
        self._assert_phrase_absent("GPT Audit Gate承認は不要")

    def test_no_api_key_stored_in_repo_japanese(self) -> None:
        """'APIキーをリポジトリに保存してよい' must not appear in any target document."""
        self._assert_phrase_absent("APIキーをリポジトリに保存してよい")

    # --- live_model_enabled=true affirmative phrases (Codex指摘1 addition) ---

    def test_no_phase2e_sets_live_model_enabled_true(self) -> None:
        """'Phase 2-E sets live_model_enabled=true' must not appear in any target document.

        Codex指摘1: live_model_enabled=true affirmative guard — Phase 2-E must NOT
        set live_model_enabled=true; only 'にしない' / prohibition contexts are allowed.
        """
        self._assert_phrase_absent("Phase 2-E sets live_model_enabled=true")

    def test_no_phase2e_enables_live_model_enabled_true(self) -> None:
        """'Phase 2-E enables live_model_enabled=true' must not appear in any target document.

        Codex指摘1: live_model_enabled=true affirmative guard.
        """
        self._assert_phrase_absent("Phase 2-E enables live_model_enabled=true")

    def test_no_live_model_enabled_true_activated_japanese(self) -> None:
        """'live_model_enabled=true有効化済み' must not appear in any target document.

        Codex指摘1: Japanese affirmative guard for live_model_enabled=true.
        """
        self._assert_phrase_absent("live_model_enabled=true有効化済み")

    # --- contents: write permission grant phrases (Codex指摘2 addition) ---

    def test_no_normal_ci_uses_contents_write(self) -> None:
        """'normal CI uses contents: write' must not appear in any target document.

        Codex指摘2: contents: write permission grant guard — normal CI must be
        read-only; granting write permission to normal CI is forbidden.
        """
        self._assert_phrase_absent("normal CI uses contents: write")

    def test_no_normal_ci_has_contents_write(self) -> None:
        """'normal CI has contents: write' must not appear in any target document.

        Codex指摘2: contents: write permission grant guard.
        """
        self._assert_phrase_absent("normal CI has contents: write")

    def test_no_ci_workflow_uses_contents_write(self) -> None:
        """'CI workflow uses contents: write' must not appear in any target document.

        Codex指摘2: contents: write permission grant guard.
        """
        self._assert_phrase_absent("CI workflow uses contents: write")

    def test_no_ci_grants_contents_write(self) -> None:
        """'CI grants contents: write' must not appear in any target document.

        Codex指摘2: contents: write permission grant guard.
        """
        self._assert_phrase_absent("CI grants contents: write")

    def test_no_contents_write_is_allowed_in_normal_ci(self) -> None:
        """'contents: write is allowed in normal CI' must not appear in any target document.

        Codex指摘2: contents: write permission grant guard.
        """
        self._assert_phrase_absent("contents: write is allowed in normal CI")

    def test_no_normal_ci_uses_contents_write_japanese(self) -> None:
        """'通常CIでcontents: writeを使う' must not appear in any target document.

        Codex指摘2: Japanese contents: write permission grant guard.
        """
        self._assert_phrase_absent("通常CIでcontents: writeを使う")

    def test_no_normal_ci_write_permission_granted_japanese(self) -> None:
        """'通常CIにwrite権限を付与する' must not appear in any target document.

        Codex指摘2: Japanese contents: write permission grant guard.
        """
        self._assert_phrase_absent("通常CIにwrite権限を付与する")
