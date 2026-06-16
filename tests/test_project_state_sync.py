"""tests/test_project_state_sync.py — Current-state SSOT drift-prevention tests.

These tests enforce that ``data/project_state.json`` and ``docs/PROJECT_STATE.md``
remain the single source of truth for current state, and that the derived
summaries (README status block, CLAUDE.md) and the machine evidence
(``data/genome.json``, ``data/api_usage_ledger.json``) do not drift away from it.

The "active docs" and "historical docs" checks are deliberately scoped to a
small, explicit set of files so this suite itself cannot become an unbounded
all-docs reconciliation surface — the exact failure mode it exists to prevent.
"""
from __future__ import annotations

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_PROJECT_STATE_PATH = _PROJECT_ROOT / "data" / "project_state.json"
_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_LEDGER_PATH = _PROJECT_ROOT / "data" / "api_usage_ledger.json"
_PROJECT_STATE_DOC = _PROJECT_ROOT / "docs" / "PROJECT_STATE.md"
_README_PATH = _PROJECT_ROOT / "README.md"
_CLAUDE_PATH = _PROJECT_ROOT / "CLAUDE.md"

_STATUS_START = "<!-- CYBER_IMMUNIZER_STATUS_START -->"
_STATUS_END = "<!-- CYBER_IMMUNIZER_STATUS_END -->"

# Forbidden stale current-state strings (task prompt §11). They must not appear
# in active current-state sources. They may remain only in explicitly
# historical-labeled documents.
_FORBIDDEN_STALE = [
    "first paid-credit run pending",
    "paid-credit run not yet executed",
    "Gemini API not connected",
    "Phase 3 not started",
    "live_model_enabled=false",
    "controlled paid-credit run not yet executed",
    "Review existing paid-credit run results",
    # Post-PR-#91-merge: these strings described the pre-merge state and must
    # not appear in active current-state sources once PR #91 is merged.
    "PR #91 (pending merge)",
    "to merge PR #91",
    # Post-run-5: these strings imply only 3 calls or no calls were executed
    # and must not appear in active current-state sources.
    "初回 paid-credit run 待機中",
    "The 3 primary-model paid-credit API calls",
]

# Active current-state surfaces that must never carry a stale claim.
# Scoped intentionally: the README status block and the human-readable SSOT doc.
_ACTIVE_CURRENT_STATE_FILES = [
    ("README status block", None),  # handled specially (block extraction)
    ("docs/PROJECT_STATE.md", _PROJECT_STATE_DOC),
]

# Historical docs that preserve a past phase snapshot and therefore must carry
# the HISTORICAL DOCUMENT label so auditors do not read them as current state.
_HISTORICAL_STATE_DOCS = [
    _PROJECT_ROOT / "docs" / "PHASE_3_GO_NO_GO_CHECKLIST.md",
]

_HISTORICAL_LABEL = "HISTORICAL DOCUMENT"

_REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "state_id",
    "current_phase",
    "phase_3_activation",
    "live_model_enabled",
    "api_mode",
    "model_provider",
    "primary_model",
    "fallback_model",
    "paid_credit_api_calls",
    "promotion",
    "next_action",
    "fresh_verification_policy",
]


def _load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_block() -> str:
    content = _README_PATH.read_text(encoding="utf-8")
    start = content.find(_STATUS_START)
    end = content.find(_STATUS_END)
    assert start != -1 and end != -1, "README must contain the status block markers"
    return content[start : end + len(_STATUS_END)]


# 1.
def test_project_state_file_exists() -> None:
    assert _PROJECT_STATE_PATH.exists(), "data/project_state.json must exist"
    assert isinstance(_load(_PROJECT_STATE_PATH), dict), "project_state.json must be a JSON object"


# 2.
def test_required_top_level_fields_exist() -> None:
    state = _load(_PROJECT_STATE_PATH)
    for field in _REQUIRED_TOP_LEVEL_FIELDS:
        assert field in state, f"project_state.json must contain top-level field '{field}'"


# 3.
def test_project_state_matches_genome() -> None:
    state = _load(_PROJECT_STATE_PATH)
    genome = _load(_GENOME_PATH)
    assert state["live_model_enabled"] == genome.get("live_model_enabled"), (
        "live_model_enabled must match genome.json"
    )
    assert state["api_mode"] == genome.get("api_mode"), "api_mode must match genome.json"
    assert state["model_provider"] == genome.get("model_provider"), (
        "model_provider must match genome.json"
    )
    assert state["primary_model"] == genome.get("model_name"), (
        "primary_model must match genome.json model_name"
    )
    assert state["fallback_model"] == genome.get("fallback_model_name"), (
        "fallback_model must match genome.json fallback_model_name"
    )


# 4.
def test_project_state_matches_ledger_success_count() -> None:
    state = _load(_PROJECT_STATE_PATH)
    ledger = _load(_LEDGER_PATH)
    primary_model = state["primary_model"]
    actual = sum(
        1
        for e in ledger
        if isinstance(e, dict)
        and e.get("provider") == "gemini"
        and e.get("api_mode") == "gemini_paid_credit"
        and e.get("model") == primary_model
        and e.get("success") is True
    )
    declared = state["paid_credit_api_calls"]["gemini_3_flash_preview_success_records"]
    assert actual == declared, (
        f"project_state declares {declared} primary-model success records "
        f"but ledger has {actual}"
    )
    assert actual == 6, "ledger must contain exactly 6 primary-model paid-credit success records"


# 5.
def test_project_state_doc_exists() -> None:
    assert _PROJECT_STATE_DOC.exists(), "docs/PROJECT_STATE.md must exist"


# 6.
def test_project_state_doc_declares_authority() -> None:
    text = _PROJECT_STATE_DOC.read_text(encoding="utf-8")
    assert "Single Source of Truth" in text, (
        "PROJECT_STATE.md must declare itself the single source of truth"
    )
    assert "this file wins" in text, (
        "PROJECT_STATE.md must declare it wins for current-state interpretation"
    )
    assert "authority order" in text, "PROJECT_STATE.md must define the authority order"


# 7.
def test_readme_status_block_does_not_contradict_project_state() -> None:
    state = _load(_PROJECT_STATE_PATH)
    block = _status_block()
    assert state["primary_model"] in block, "README must show the primary model"
    assert state["fallback_model"] in block, "README must show the fallback model"
    assert state["api_mode"] in block, "README must show the api_mode"
    assert "true" in block.lower(), "README must show live_model_enabled=true"
    # No valid mutation patch was produced — the README must not imply otherwise,
    # and must not still route auditors to a generic 'result review'.
    for stale in _FORBIDDEN_STALE:
        assert stale not in block, (
            f"README status block must not contain stale current-state claim: {stale!r}"
        )


# 8.
def test_claude_md_references_ssot() -> None:
    text = _CLAUDE_PATH.read_text(encoding="utf-8")
    assert "data/project_state.json" in text, (
        "CLAUDE.md must reference data/project_state.json for current-state interpretation"
    )
    assert "docs/PROJECT_STATE.md" in text, (
        "CLAUDE.md must reference docs/PROJECT_STATE.md for current-state interpretation"
    )


# 9.
def test_active_current_state_docs_have_no_stale_claims() -> None:
    # README status block
    block = _status_block()
    for stale in _FORBIDDEN_STALE:
        assert stale not in block, (
            f"Active README status block must not contain stale claim: {stale!r}"
        )
    # docs/PROJECT_STATE.md (active SSOT doc)
    text = _PROJECT_STATE_DOC.read_text(encoding="utf-8")
    for stale in _FORBIDDEN_STALE:
        assert stale not in text, (
            f"docs/PROJECT_STATE.md must not contain stale claim: {stale!r}"
        )


# 10.
def test_historical_state_docs_are_labeled() -> None:
    for doc in _HISTORICAL_STATE_DOCS:
        assert doc.exists(), f"expected historical doc to exist: {doc}"
        text = doc.read_text(encoding="utf-8")
        assert _HISTORICAL_LABEL in text, (
            f"{doc.name} preserves old phase state and must carry the "
            f"'{_HISTORICAL_LABEL}' label pointing to the SSOT"
        )


# 11.
def test_phase3_active() -> None:
    state = _load(_PROJECT_STATE_PATH)
    assert state.get("current_phase") == "phase_3", (
        "current_phase must be 'phase_3'"
    )
    assert state.get("live_model_enabled") is True, (
        "live_model_enabled must be true in Phase 3"
    )


# 12.
def test_valid_mutation_patch_produced() -> None:
    state = _load(_PROJECT_STATE_PATH)
    calls = state.get("paid_credit_api_calls", {})
    assert calls.get("valid_mutation_patch_produced") is True, (
        "S4 run #47 produced a valid mutation_patch.json; "
        "valid_mutation_patch_produced must be true"
    )


# 13.
def test_apply_reached() -> None:
    state = _load(_PROJECT_STATE_PATH)
    calls = state.get("paid_credit_api_calls", {})
    assert calls.get("apply_reached") is True, (
        "S4 run #47 reached apply_mutation.py; apply_reached must be true"
    )


# 14.
def test_evaluate_reached_and_promote_not_reached() -> None:
    state = _load(_PROJECT_STATE_PATH)
    calls = state.get("paid_credit_api_calls", {})
    assert calls.get("evaluate_reached") is True, (
        "runs 5 & 6 reached the evaluate stage (triage complete); "
        "evaluate_reached must be true"
    )
    assert calls.get("adoption_gate_ever_passed") is False, (
        "no candidate has passed the adoption gate (runs 5 & 6 rejected for score "
        "regression); adoption_gate_ever_passed must be false"
    )
    assert calls.get("promote_reached") is False, (
        "promote was not reached in any run (Promote job skipped in runs 5 & 6); "
        "promote_reached must be false"
    )


# 15.
def test_promote_approved_is_false() -> None:
    state = _load(_PROJECT_STATE_PATH)
    promo = state.get("promotion", {})
    assert promo.get("promote_approved") is False, (
        "promote_approved must be false — no promotion has been approved"
    )


# 16.
def test_next_action_is_post_pr91_rerun_preparation() -> None:
    state = _load(_PROJECT_STATE_PATH)
    next_action = state.get("next_action", "")
    assert "merge_g1" not in next_action, (
        "next_action must not reference the pre-PR91-merge G1 gap closure "
        "(PR #91 is merged)"
    )
    # After runs 5 & 6 triage, next_action references the completed triage / artifact
    # review and the resulting Owner decision (no longer a pending S4 rerun).
    assert (
        "s4_rerun" in next_action
        or "owner" in next_action
        or "triage" in next_action
        or "artifact" in next_action
    ), (
        "next_action must reference the current state: "
        "the completed artifact triage / Owner decision after runs 5 & 6"
    )


# 17.
def test_readme_roadmap_no_stale_first_run_pending() -> None:
    text = _README_PATH.read_text(encoding="utf-8")
    assert "初回 paid-credit run 待機中" not in text, (
        "README roadmap must not claim 'initial paid-credit run pending' — "
        "6 paid-credit success records have been recorded"
    )


# 18.
def test_project_state_doc_no_stale_3_calls_claim() -> None:
    text = _PROJECT_STATE_DOC.read_text(encoding="utf-8")
    assert "The 3 primary-model paid-credit API calls" not in text, (
        "docs/PROJECT_STATE.md must not claim only 3 primary-model calls were executed "
        "(6 success records are now recorded)"
    )


# 19.
def test_project_state_doc_shows_6_success_records() -> None:
    text = _PROJECT_STATE_DOC.read_text(encoding="utf-8")
    assert "**6**" in text, (
        "docs/PROJECT_STATE.md must show 6 primary-model paid-credit success records"
    )


# 20.
def test_project_state_doc_mentions_runs_5_6_triage_complete() -> None:
    text = _PROJECT_STATE_DOC.read_text(encoding="utf-8")
    assert "run 5" in text, "docs/PROJECT_STATE.md must mention run 5"
    assert "run 6" in text, "docs/PROJECT_STATE.md must mention run 6"
    assert "triage complete" in text, (
        "docs/PROJECT_STATE.md must indicate runs 5 & 6 artifact triage is complete"
    )
    assert "evaluate_rejected" in text, (
        "docs/PROJECT_STATE.md must record the evaluate_rejected triage classification"
    )


# 21.
def test_state_id_is_runs_5_6_evaluate_rejected() -> None:
    state = _load(_PROJECT_STATE_PATH)
    assert state.get("state_id") == "phase3_paid_credit_runs_5_6_evaluate_rejected_score_regression", (
        "state_id must be 'phase3_paid_credit_runs_5_6_evaluate_rejected_score_regression'"
    )


# 22.
def test_next_action_is_owner_decision_after_triage() -> None:
    state = _load(_PROJECT_STATE_PATH)
    assert state.get("next_action") == (
        "runs_5_6_artifact_triage_complete_evaluate_rejected_await_owner_decision_on_propose_side_improvement"
    ), (
        "next_action must be "
        "'runs_5_6_artifact_triage_complete_evaluate_rejected_await_owner_decision_on_propose_side_improvement'"
    )
