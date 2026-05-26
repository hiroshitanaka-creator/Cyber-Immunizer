"""
tests/test_evolution_history_audit_docs.py

Phase 2-C: Evolution History Audit — document existence, content, and
lightweight format tests for the current data/evolution_history.json.

Scope:
- Verify docs/EVOLUTION_HISTORY_AUDIT.md exists and contains required sections
- Verify README.md and PHASE_2_PLAN.md link to EVOLUTION_HISTORY_AUDIT.md
- Lightly validate the current data/evolution_history.json (fail-closed test)

Intentionally NOT in scope:
- API connections / Gemini API calls
- live_model_enabled=true
- GEMINI_API_KEY handling
- rollback CLI implementation tests
- workflow changes
"""

import json
import pathlib
import re

import pytest

# ──────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────

ROOT = pathlib.Path(__file__).parent.parent
AUDIT_DOC = ROOT / "docs" / "EVOLUTION_HISTORY_AUDIT.md"
PHASE2_PLAN = ROOT / "docs" / "PHASE_2_PLAN.md"
README = ROOT / "README.md"
EVOLUTION_HISTORY = ROOT / "data" / "evolution_history.json"


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# 1. docs/EVOLUTION_HISTORY_AUDIT.md — existence
# ──────────────────────────────────────────────────────────────

class TestAuditDocExists:
    def test_file_exists(self):
        """docs/EVOLUTION_HISTORY_AUDIT.md must exist."""
        assert AUDIT_DOC.exists(), (
            f"{AUDIT_DOC} not found. "
            "Phase 2-C requires this document to be present."
        )

    def test_file_is_nonempty(self):
        """The document must not be empty."""
        content = _read(AUDIT_DOC)
        assert len(content.strip()) > 0, "EVOLUTION_HISTORY_AUDIT.md is empty."


# ──────────────────────────────────────────────────────────────
# 2. docs/EVOLUTION_HISTORY_AUDIT.md — purpose section
# ──────────────────────────────────────────────────────────────

class TestAuditDocPurpose:
    def test_purpose_section_present(self):
        """Document must have a Purpose section."""
        content = _read(AUDIT_DOC)
        assert "Purpose" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must contain a 'Purpose' section."
        )

    def test_evolution_history_json_is_scope(self):
        """evolution_history.json must be mentioned as audit target."""
        content = _read(AUDIT_DOC)
        assert "evolution_history.json" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention data/evolution_history.json "
            "as the audit target."
        )


# ──────────────────────────────────────────────────────────────
# 3. api_usage_ledger exclusion
# ──────────────────────────────────────────────────────────────

class TestApiUsageLedgerExclusion:
    def test_api_usage_ledger_listed_as_out_of_scope(self):
        """api_usage_ledger.json must be mentioned as out of scope."""
        content = _read(AUDIT_DOC)
        assert "api_usage_ledger.json" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention api_usage_ledger.json "
            "as out of scope / not to be rolled back."
        )

    def test_api_usage_ledger_not_rolled_back_policy(self):
        """Document must state api_usage_ledger.json is not rolled back."""
        content = _read(AUDIT_DOC)
        # Allow Japanese or English expressions of this policy
        policy_phrases = [
            "巻き戻さない",
            "never rolled back",
            "not rolled back",
            "絶対に巻き戻さない",
            "巻き戻し禁止",
        ]
        found = any(phrase in content for phrase in policy_phrases)
        assert found, (
            "EVOLUTION_HISTORY_AUDIT.md must state that api_usage_ledger.json "
            "is never rolled back. "
            f"Expected one of: {policy_phrases}"
        )


# ──────────────────────────────────────────────────────────────
# 3b. api_usage_ledger regression guard
#     Verifies that docs/EVOLUTION_HISTORY_AUDIT.md does NOT contain
#     any dangerous reverse-direction phrases that would incorrectly
#     include or permit modification of the API usage ledger in
#     evolution history rollback / backtrack / promote scope.
# ──────────────────────────────────────────────────────────────

class TestApiUsageLedgerRegressionGuard:
    """Regression guard: prohibit dangerous inclusion/modification phrases for api_usage_ledger.

    These tests guard against future document degradation where the audit design doc
    might accidentally permit rolling back or modifying data/api_usage_ledger.json.

    The Cost/API Governance invariant is:
      data/api_usage_ledger.json is NEVER included in evolution_history rollback/backtrack scope
      and NEVER modified by rollback/backtrack/promote operations.

    If any of the prohibited phrases appear in EVOLUTION_HISTORY_AUDIT.md,
    the corresponding test must fail immediately to catch the regression.
    """

    def test_api_usage_ledger_not_included_in_rollback_regression_guard(self):
        """EVOLUTION_HISTORY_AUDIT.md must NOT state that api_usage_ledger.json
        is included in evolution history rollback scope.

        Prohibited phrases signal a dangerous policy reversal.
        """
        content = _read(AUDIT_DOC)
        prohibited_phrases = [
            "api_usage_ledger.json is included in evolution history rollback",
            "API usage ledger is included in rollback",
            "API usage ledger is included in backtrack",
            "api_usage_ledger.json を rollback 対象に含める",
            "api_usage_ledger.json をrollback対象に含める",
            "api_usage_ledger.json をbacktrack対象に含める",
            "api_usage_ledger.json を evolution history rollback 対象",
            "ledger も rollback 対象",
            "ledger も backtrack 対象",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in content, (
                f"EVOLUTION_HISTORY_AUDIT.md must NOT contain '{phrase}'. "
                "This phrase incorrectly includes api_usage_ledger.json in "
                "evolution history rollback/backtrack scope, which violates the "
                "Cost/API Governance invariant."
            )

    def test_api_usage_ledger_modification_permission_is_forbidden(self):
        """EVOLUTION_HISTORY_AUDIT.md must NOT state that api_usage_ledger.json
        may or can be modified during rollback/backtrack operations.

        These phrases represent a direct violation of the Cost/API Governance invariant.
        """
        content = _read(AUDIT_DOC)
        prohibited_phrases = [
            "API usage ledger may be modified during rollback",
            "API usage ledger can be modified during rollback",
            "API usage ledger may be modified during backtrack",
            "API usage ledger can be modified during backtrack",
            "API usage ledger を変更してよい",
            "API usage ledger を変更してもよい",
            "api_usage_ledger.json を変更してよい",
            "api_usage_ledger.json を変更してもよい",
            "API usage ledger は変更可",
            "API usage ledger は修正可",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in content, (
                f"EVOLUTION_HISTORY_AUDIT.md must NOT contain '{phrase}'. "
                "This phrase incorrectly permits modification of api_usage_ledger.json, "
                "which is a Cost/API Governance violation. "
                "The ledger is an immutable billing/audit record and must never be modified."
            )

    def test_api_usage_ledger_reverse_policy_phrases_are_rejected(self):
        """EVOLUTION_HISTORY_AUDIT.md must NOT contain any phrase that reverses the
        'api_usage_ledger.json is never rolled back' policy.

        This is the core invariant: the ledger tracks real API spend and must remain
        immutable regardless of evolution history operations.
        """
        content = _read(AUDIT_DOC)
        prohibited_phrases = [
            # English reverse-policy phrases
            "API usage ledger is rolled back",
            "api_usage_ledger.json is rolled back",
            "API usage ledger should be rolled back",
            "API usage ledger must be rolled back",
            "API usage ledger is reverted",
            "API usage ledger は rollback 対象",
            "API usage ledger は rollback対象",
            "API usage ledger は backtrack 対象",
            "API usage ledger は backtrack対象",
            # Japanese reverse-policy phrases
            "api_usage_ledger.json を巻き戻す",
            "API usage ledger を巻き戻す",
            "api_usage_ledger.json も巻き戻す",
            "API usage ledger も巻き戻す",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in content, (
                f"EVOLUTION_HISTORY_AUDIT.md must NOT contain '{phrase}'. "
                "This phrase reverses the policy that api_usage_ledger.json is "
                "NEVER rolled back. The ledger is an immutable billing/audit record. "
                "Violating this invariant would corrupt the Cost/API Governance trail."
            )


# ──────────────────────────────────────────────────────────────
# 4. Required record fields
# ──────────────────────────────────────────────────────────────

class TestRequiredRecordFields:
    def test_required_fields_section_present(self):
        """Document must have a 'Required record fields' section."""
        content = _read(AUDIT_DOC)
        assert "Required record fields" in content or "required record fields" in content.lower(), (
            "EVOLUTION_HISTORY_AUDIT.md must have a 'Required record fields' section."
        )

    def test_generation_field_mentioned(self):
        """'generation' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "generation" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'generation' as a required field."
        )

    def test_detector_hash_field_mentioned(self):
        """'detector_hash' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "detector_hash" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'detector_hash' as a required field."
        )

    def test_score_field_mentioned(self):
        """'score' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "score" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'score' as a required field."
        )

    def test_passed_adoption_gate_field_mentioned(self):
        """'passed_adoption_gate' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "passed_adoption_gate" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'passed_adoption_gate' as a required field."
        )

    def test_rejection_reasons_field_mentioned(self):
        """'rejection_reasons' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "rejection_reasons" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'rejection_reasons' as a required field."
        )

    def test_ast_policy_ok_field_mentioned(self):
        """'ast_policy_ok' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "ast_policy_ok" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'ast_policy_ok' as a required field."
        )

    def test_regression_passed_field_mentioned(self):
        """'regression_passed' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "regression_passed" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'regression_passed' as a required field."
        )

    def test_audit_gate_decision_field_mentioned(self):
        """'audit_gate_decision' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "audit_gate_decision" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'audit_gate_decision' as a required field."
        )

    def test_human_owner_approval_field_mentioned(self):
        """'human_owner_approval' must be listed as a required field."""
        content = _read(AUDIT_DOC)
        assert "human_owner_approval" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention 'human_owner_approval' as a required field."
        )


# ──────────────────────────────────────────────────────────────
# 5. fail-closed policy
# ──────────────────────────────────────────────────────────────

class TestFailClosedPolicy:
    def test_fail_closed_mentioned(self):
        """Document must mention fail-closed policy."""
        content = _read(AUDIT_DOC)
        assert "fail-closed" in content or "fail_closed" in content, (
            "EVOLUTION_HISTORY_AUDIT.md must mention the fail-closed policy."
        )

    def test_history_record_not_deleted_policy(self):
        """Document must state that history records are appended, not deleted."""
        content = _read(AUDIT_DOC)
        # Allow both Japanese and English
        append_phrases = [
            "削除せず",
            "追記",
            "not deleted",
            "append",
            "追記を基本",
            "do not delete",
        ]
        found = any(phrase in content for phrase in append_phrases)
        assert found, (
            "EVOLUTION_HISTORY_AUDIT.md must state that history records are not deleted "
            "and are appended. "
            f"Expected one of: {append_phrases}"
        )


# ──────────────────────────────────────────────────────────────
# 6. rollback/backtrack relationship
# ──────────────────────────────────────────────────────────────

class TestRollbackBacktrackRelationship:
    def test_rollback_backtrack_section_present(self):
        """Document must have a section about relationship with rollback/backtrack."""
        content = _read(AUDIT_DOC)
        rollback_phrases = [
            "Relationship with rollback",
            "rollback / backtrack",
            "rollback/backtrack",
        ]
        found = any(phrase in content for phrase in rollback_phrases)
        assert found, (
            "EVOLUTION_HISTORY_AUDIT.md must have a section describing the "
            "relationship with rollback/backtrack. "
            f"Expected one of: {rollback_phrases}"
        )

    def test_rollback_records_are_appended_not_deleted(self):
        """Document must state rollback records are appended as new records."""
        content = _read(AUDIT_DOC)
        # The document should mention new record appending for rollback/backtrack
        assert "rollback" in content.lower() and (
            "追記" in content or "append" in content.lower() or "new record" in content.lower()
        ), (
            "EVOLUTION_HISTORY_AUDIT.md must state that rollback/backtrack results "
            "are appended as new history records, not deletions."
        )


# ──────────────────────────────────────────────────────────────
# 7. Non-goals section
# ──────────────────────────────────────────────────────────────

class TestNonGoals:
    def test_non_goals_section_present(self):
        """Document must have a Non-goals section."""
        content = _read(AUDIT_DOC)
        assert "Non-goals" in content or "non-goals" in content.lower(), (
            "EVOLUTION_HISTORY_AUDIT.md must have a 'Non-goals' section."
        )

    def test_no_api_connection_in_phase_2c(self):
        """Non-goals must mention that API connection is not done in Phase 2-C."""
        content = _read(AUDIT_DOC)
        api_phrases = [
            "API 接続",
            "API接続",
            "API connection",
            "live_model_enabled",
            "GEMINI_API_KEY",
        ]
        found = any(phrase in content for phrase in api_phrases)
        assert found, (
            "EVOLUTION_HISTORY_AUDIT.md must mention that API connection / "
            "live_model_enabled=true is not done in Phase 2-C."
        )

    def test_no_workflow_changes_in_phase_2c(self):
        """Non-goals must mention that workflow changes are not done in Phase 2-C."""
        content = _read(AUDIT_DOC)
        workflow_phrases = [
            "workflow",
            "ワークフロー",
        ]
        found = any(phrase in content for phrase in workflow_phrases)
        assert found, (
            "EVOLUTION_HISTORY_AUDIT.md must mention that workflow changes are not done "
            "in Phase 2-C."
        )


# ──────────────────────────────────────────────────────────────
# 8. README.md links to EVOLUTION_HISTORY_AUDIT.md
# ──────────────────────────────────────────────────────────────

class TestReadmeLinks:
    def test_readme_links_to_evolution_history_audit(self):
        """README.md must contain a link to EVOLUTION_HISTORY_AUDIT.md."""
        content = _read(README)
        assert "EVOLUTION_HISTORY_AUDIT.md" in content, (
            "README.md must contain a link to docs/EVOLUTION_HISTORY_AUDIT.md."
        )


# ──────────────────────────────────────────────────────────────
# 9. PHASE_2_PLAN.md links to EVOLUTION_HISTORY_AUDIT.md
# ──────────────────────────────────────────────────────────────

class TestPhase2PlanLinks:
    def test_phase2_plan_links_to_evolution_history_audit(self):
        """docs/PHASE_2_PLAN.md must contain a link to EVOLUTION_HISTORY_AUDIT.md."""
        assert PHASE2_PLAN.exists(), "docs/PHASE_2_PLAN.md not found."
        content = _read(PHASE2_PLAN)
        assert "EVOLUTION_HISTORY_AUDIT.md" in content, (
            "docs/PHASE_2_PLAN.md must contain a link to docs/EVOLUTION_HISTORY_AUDIT.md."
        )

    def test_phase2_plan_mentions_audit_spec(self):
        """PHASE_2_PLAN.md must mention evolution_history audit spec in Phase 2-C."""
        content = _read(PHASE2_PLAN)
        assert "evolution_history" in content or "EVOLUTION_HISTORY" in content, (
            "docs/PHASE_2_PLAN.md must mention evolution_history audit in Phase 2-C context."
        )

    def test_phase2_plan_mentions_no_auto_repair_or_workflow(self):
        """PHASE_2_PLAN.md must note that auto repair/workflow changes are not done."""
        content = _read(PHASE2_PLAN)
        no_change_phrases = [
            "自動修復",
            "workflow変更",
            "workflow changes",
            "API接続は行わない",
            "API 接続は行わない",
            "no implementation",
            "design and audit spec only",
            "design-only",
        ]
        found = any(phrase in content for phrase in no_change_phrases)
        assert found, (
            "docs/PHASE_2_PLAN.md must mention that automatic repair / workflow changes "
            "/ API connections are not done in Phase 2-C. "
            f"Expected one of: {no_change_phrases}"
        )


# ──────────────────────────────────────────────────────────────
# 10. data/evolution_history.json — lightweight format tests
# ──────────────────────────────────────────────────────────────

class TestEvolutionHistoryJsonFormat:
    """
    Lightweight format tests for the CURRENT data/evolution_history.json.

    These tests verify:
    - The file can be parsed as valid JSON
    - The top-level structure is a list
    - Each record is a dict
    - Fields present in current records satisfy minimal type constraints

    These tests are intentionally lenient — the current history uses an older
    schema and Phase 2-C only mandates the future schema. The goal is to
    confirm the file is not broken, not to enforce the full new schema.
    """

    @pytest.fixture(scope="class")
    def history(self):
        """Load and return the parsed evolution_history.json."""
        assert EVOLUTION_HISTORY.exists(), (
            f"{EVOLUTION_HISTORY} not found. "
            "data/evolution_history.json must exist."
        )
        content = EVOLUTION_HISTORY.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"data/evolution_history.json is not valid JSON: {exc}"
            )
        return data

    def test_file_exists(self):
        """data/evolution_history.json must exist."""
        assert EVOLUTION_HISTORY.exists(), (
            "data/evolution_history.json not found."
        )

    def test_file_is_valid_json(self, history):
        """data/evolution_history.json must be parseable as valid JSON."""
        # If fixture loaded without error, the file is valid JSON.
        assert history is not None

    def test_top_level_is_list(self, history):
        """Top-level value must be a JSON array (list)."""
        assert isinstance(history, list), (
            f"data/evolution_history.json top-level must be a list, got {type(history).__name__}."
        )

    def test_each_record_is_dict(self, history):
        """Every element in the history list must be a dict (JSON object)."""
        for idx, record in enumerate(history):
            assert isinstance(record, dict), (
                f"data/evolution_history.json record at index {idx} is not a dict "
                f"(got {type(record).__name__})."
            )

    def test_generation_field_is_integer_when_present(self, history):
        """If 'generation' is present in a record, it must be a strict integer (not bool).

        Python's isinstance(True, int) returns True, so booleans must be explicitly
        excluded. A record like {"generation": true} must be treated as invalid.
        """
        for idx, record in enumerate(history):
            if "generation" in record:
                value = record["generation"]
                assert isinstance(value, int) and not isinstance(value, bool), (
                    f"data/evolution_history.json record[{idx}]['generation'] "
                    f"must be a strict integer (not bool), "
                    f"got {type(value).__name__}: {value!r}. "
                    "JSON booleans (true/false) are not valid generation values."
                )

    def test_hash_fields_are_nonempty_when_present(self, history):
        """
        If hash-related fields are present in a record, they must not be empty strings.
        Checks: detector_hash, current_detector_hash, candidate_hash.
        """
        hash_field_names = {"detector_hash", "current_detector_hash", "candidate_hash"}
        for idx, record in enumerate(history):
            for field in hash_field_names:
                if field in record:
                    value = record[field]
                    # Allow None (field not yet filled) but not empty string
                    if value is not None:
                        assert isinstance(value, str) and len(value.strip()) > 0, (
                            f"data/evolution_history.json record[{idx}]['{field}'] "
                            f"must not be an empty string, got: {value!r}."
                        )

    def test_passed_adoption_gate_is_bool_when_present(self, history):
        """If 'passed_adoption_gate' is present in a record, it must be a boolean."""
        for idx, record in enumerate(history):
            if "passed_adoption_gate" in record:
                value = record["passed_adoption_gate"]
                assert isinstance(value, bool), (
                    f"data/evolution_history.json record[{idx}]['passed_adoption_gate'] "
                    f"must be a boolean, got {type(value).__name__}: {value!r}."
                )

    def test_rejection_reasons_is_list_when_present(self, history):
        """If 'rejection_reasons' is present in a record, it must be a list."""
        for idx, record in enumerate(history):
            if "rejection_reasons" in record:
                value = record["rejection_reasons"]
                assert isinstance(value, list), (
                    f"data/evolution_history.json record[{idx}]['rejection_reasons'] "
                    f"must be a list, got {type(value).__name__}: {value!r}."
                )

    def test_rejection_reasons_items_are_strings_when_present(self, history):
        """Each item in 'rejection_reasons' must be a string when the field is present."""
        for idx, record in enumerate(history):
            if "rejection_reasons" in record:
                reasons = record["rejection_reasons"]
                if isinstance(reasons, list):
                    for ridx, reason in enumerate(reasons):
                        assert isinstance(reason, str), (
                            f"data/evolution_history.json record[{idx}]['rejection_reasons'][{ridx}] "
                            f"must be a string, got {type(reason).__name__}: {reason!r}."
                        )

    def test_score_is_number_when_present(self, history):
        """If 'score' is present in a record, it must be a numeric value (int or float,
        but NOT bool).

        Python's isinstance(True, (int, float)) returns True, so booleans must be
        explicitly excluded. A record like {"score": true} must be treated as invalid.
        """
        for idx, record in enumerate(history):
            if "score" in record:
                value = record["score"]
                assert isinstance(value, (int, float)) and not isinstance(value, bool), (
                    f"data/evolution_history.json record[{idx}]['score'] "
                    f"must be a numeric value (int or float, not bool), "
                    f"got {type(value).__name__}: {value!r}. "
                    "JSON booleans (true/false) are not valid score values."
                )

    def test_generation_monotonically_nondecreasing(self, history):
        """
        Generations with 'generation' field should be non-decreasing
        (allows equal values only if rollback/backtrack context is considered).
        This is a soft check — future records may use rollback with lower generation numbers.
        For the current history (which has no rollback records), verify no decreases.
        Bool values are excluded from this check (they fail the strict-int test above).
        """
        generations = [
            (idx, record["generation"])
            for idx, record in enumerate(history)
            if "generation" in record
            and isinstance(record["generation"], int)
            and not isinstance(record["generation"], bool)
        ]
        # Check current history has non-decreasing generations
        # (rollback records would have explicit source_mode, which is not in current history)
        for i in range(1, len(generations)):
            prev_idx, prev_gen = generations[i - 1]
            curr_idx, curr_gen = generations[i]
            has_rollback_mode = (
                history[curr_idx].get("source_mode") in {"rollback", "backtrack"}
            )
            if not has_rollback_mode:
                assert curr_gen >= prev_gen, (
                    f"data/evolution_history.json: generation decreased from "
                    f"record[{prev_idx}].generation={prev_gen} to "
                    f"record[{curr_idx}].generation={curr_gen} "
                    "without a rollback/backtrack source_mode. "
                    "Generations must be non-decreasing (or have explicit rollback context)."
                )


# ──────────────────────────────────────────────────────────────
# 11. Bool contamination regression tests
#     Verifies that the type-checking helpers above correctly reject
#     JSON boolean values (true/false) in generation and score fields.
#     Python's isinstance(True, int) is True and isinstance(True, float) is True,
#     so explicit bool exclusion is required.
# ──────────────────────────────────────────────────────────────

def _is_valid_generation(value: object) -> bool:
    """Return True iff value is a strict integer (not bool) — the valid type for 'generation'."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_score(value: object) -> bool:
    """Return True iff value is a numeric value (int or float, not bool) — valid for 'score'."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class TestBoolContaminationRegressionGuard:
    """Regression tests confirming that bool values are correctly rejected for
    'generation' and 'score' fields in history records.

    These tests do NOT modify data/evolution_history.json.
    They exercise the type-checking logic in isolation using synthetic values.
    """

    # ── generation: invalid cases ──────────────────────────────

    def test_generation_true_is_invalid(self):
        """generation=true (JSON boolean) must be rejected as an invalid type."""
        assert not _is_valid_generation(True), (
            "True must be rejected as a generation value. "
            "isinstance(True, int) is True in Python, so explicit bool exclusion is required."
        )

    def test_generation_false_is_invalid(self):
        """generation=false (JSON boolean) must be rejected as an invalid type."""
        assert not _is_valid_generation(False), (
            "False must be rejected as a generation value. "
            "isinstance(False, int) is True in Python, so explicit bool exclusion is required."
        )

    # ── generation: valid cases ────────────────────────────────

    def test_generation_zero_is_valid(self):
        """generation=0 (integer) must be accepted as a valid generation value."""
        assert _is_valid_generation(0), (
            "0 must be accepted as a valid generation value."
        )

    def test_generation_positive_integer_is_valid(self):
        """generation=1 (positive integer) must be accepted as a valid generation value."""
        assert _is_valid_generation(1), (
            "1 must be accepted as a valid generation value."
        )

    def test_generation_large_integer_is_valid(self):
        """generation=999 (large integer) must be accepted as a valid generation value."""
        assert _is_valid_generation(999), (
            "999 must be accepted as a valid generation value."
        )

    # ── score: invalid cases ───────────────────────────────────

    def test_score_true_is_invalid(self):
        """score=true (JSON boolean) must be rejected as an invalid numeric type."""
        assert not _is_valid_score(True), (
            "True must be rejected as a score value. "
            "isinstance(True, (int, float)) is True in Python, "
            "so explicit bool exclusion is required."
        )

    def test_score_false_is_invalid(self):
        """score=false (JSON boolean) must be rejected as an invalid numeric type."""
        assert not _is_valid_score(False), (
            "False must be rejected as a score value. "
            "isinstance(False, (int, float)) is True in Python, "
            "so explicit bool exclusion is required."
        )

    # ── score: valid cases ─────────────────────────────────────

    def test_score_integer_is_valid(self):
        """score=1 (integer) must be accepted as a valid score value."""
        assert _is_valid_score(1), (
            "1 must be accepted as a valid score value."
        )

    def test_score_float_is_valid(self):
        """score=1.5 (float) must be accepted as a valid score value."""
        assert _is_valid_score(1.5), (
            "1.5 must be accepted as a valid score value."
        )

    def test_score_negative_float_is_valid(self):
        """score=-1000000.0 (large negative float) must be accepted as a valid score value."""
        assert _is_valid_score(-1000000.0), (
            "-1000000.0 must be accepted as a valid score value "
            "(used for the baseline generation-0 record)."
        )

    def test_score_zero_is_valid(self):
        """score=0 (zero integer) must be accepted as a valid score value."""
        assert _is_valid_score(0), (
            "0 must be accepted as a valid score value."
        )
