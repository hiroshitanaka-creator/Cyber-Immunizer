"""tests/test_phase3_go_no_go_checklist_docs.py

String-based tests verifying docs/PHASE_3_GO_NO_GO_CHECKLIST.md
contains all required invariant phrases and structural markers.
"""
from __future__ import annotations

import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_CHECKLIST = _REPO_ROOT / "docs" / "PHASE_3_GO_NO_GO_CHECKLIST.md"


def _text() -> str:
    return _CHECKLIST.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------

def test_checklist_file_exists() -> None:
    assert _CHECKLIST.exists(), (
        "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must exist"
    )


# ---------------------------------------------------------------------------
# 2. AI_DOC_META block
# ---------------------------------------------------------------------------

def test_ai_doc_meta_exists() -> None:
    assert "AI_DOC_META" in _text(), (
        "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must contain an AI_DOC_META block"
    )


def test_status_is_canonical() -> None:
    text = _text()
    assert "status: CANONICAL" in text, (
        "AI_DOC_META block must have 'status: CANONICAL'"
    )


# ---------------------------------------------------------------------------
# 3. Non-activation declaration
# ---------------------------------------------------------------------------

def test_document_says_not_phase3_activation() -> None:
    text_lower = _text().lower()
    assert "this document is not phase 3 activation" in text_lower, (
        "Checklist must state 'This document is not Phase 3 activation'"
    )


def test_document_says_phase3_not_started() -> None:
    text_lower = _text().lower()
    assert "phase 3 is not started" in text_lower or "phase 3 not started" in text_lower, (
        "Checklist must state 'Phase 3 is not started'"
    )


def test_document_says_api_not_connected() -> None:
    text_lower = _text().lower()
    assert "api is not connected" in text_lower or "not connected" in text_lower, (
        "Checklist must state 'API is not connected'"
    )


def test_document_says_live_model_enabled_remains_false() -> None:
    text_lower = _text().lower()
    assert (
        "live_model_enabled must remain false" in text_lower
        or "live_model_enabled remains false" in text_lower
    ), (
        "Checklist must state live_model_enabled must remain false "
        "until a dedicated Phase 3 activation PR is approved"
    )


def test_document_requires_human_owner_explicit_approval() -> None:
    text_lower = _text().lower()
    assert (
        "project owner explicit approval is required" in text_lower
        or (
            "project owner" in text_lower
            and "explicit approval" in text_lower
        )
    ), (
        "Checklist must require Project Owner explicit approval before any Phase 3 activation PR"
    )


# ---------------------------------------------------------------------------
# 4. Repository-verifiable vs Project Owner external separation
# ---------------------------------------------------------------------------

def test_document_separates_repo_verifiable_from_human_owner_external() -> None:
    text_lower = _text().lower()
    assert (
        "repository-verifiable" in text_lower
        or "repository verifiable" in text_lower
    ), (
        "Checklist must separate repository-verifiable checks from Project Owner external checks"
    )
    assert (
        "project owner external" in text_lower
        or "project owner" in text_lower
    ), (
        "Checklist must include Project Owner external checks section"
    )


# ---------------------------------------------------------------------------
# 5. GitHub Secrets out-of-band verification
# ---------------------------------------------------------------------------

def test_document_mentions_github_secrets_out_of_band() -> None:
    text_lower = _text().lower()
    assert (
        "out-of-band" in text_lower
        and "github secrets" in text_lower
    ), (
        "Checklist must mention GitHub Secrets out-of-band verification"
    )


# ---------------------------------------------------------------------------
# 6. Google billing / budget / alerts
# ---------------------------------------------------------------------------

def test_document_mentions_google_billing_and_budget_and_alerts() -> None:
    text_lower = _text().lower()
    assert "billing" in text_lower, (
        "Checklist must mention Google Cloud billing"
    )
    assert (
        "budget cap" in text_lower
        or "monthly_api_budget_usd" in text_lower
        or "budget" in text_lower
    ), (
        "Checklist must mention budget cap"
    )
    assert "alert" in text_lower, (
        "Checklist must mention billing alerts"
    )


# ---------------------------------------------------------------------------
# 7. No-Go conditions
# ---------------------------------------------------------------------------

def test_document_mentions_no_go_conditions() -> None:
    text_lower = _text().lower()
    assert "no-go" in text_lower or "no go" in text_lower, (
        "Checklist must include No-Go conditions section"
    )


# ---------------------------------------------------------------------------
# 8. Secret values prohibited in chat / PR body / logs / repo files
# ---------------------------------------------------------------------------

def test_document_prohibits_secret_values_in_chat_pr_body_logs_repo() -> None:
    text_lower = _text().lower()
    assert (
        "chat" in text_lower
        and "pr body" in text_lower
        and (
            "log" in text_lower
            or "repository files" in text_lower
        )
    ), (
        "Checklist must prohibit secret values in chat, PR body, logs, and repository files"
    )


# ---------------------------------------------------------------------------
# 9. Dedicated Phase 3 activation PR required
# ---------------------------------------------------------------------------

def test_document_requires_dedicated_phase3_activation_pr() -> None:
    text_lower = _text().lower()
    assert (
        "dedicated pr" in text_lower
        or "dedicated phase 3 activation pr" in text_lower
    ), (
        "Checklist must require a dedicated Phase 3 activation PR"
    )


# ---------------------------------------------------------------------------
# 10. GPT Audit Gate review required
# ---------------------------------------------------------------------------

def test_document_requires_gpt_audit_gate_review() -> None:
    text_lower = _text().lower()
    assert "gpt audit gate" in text_lower, (
        "Checklist must require GPT Audit Gate review"
    )


# ---------------------------------------------------------------------------
# 11. Codex inline thread check required
# ---------------------------------------------------------------------------

def test_document_requires_codex_inline_thread_check() -> None:
    text_lower = _text().lower()
    assert "codex" in text_lower and (
        "inline thread" in text_lower or "thread" in text_lower
    ), (
        "Checklist must require Codex inline thread check"
    )


# ---------------------------------------------------------------------------
# 12. Exact Japanese explicit gate question
# ---------------------------------------------------------------------------

def test_document_includes_exact_japanese_gate_question() -> None:
    text = _text()
    expected_line1 = "ここからは Phase 3 activation PR です。"
    expected_line2 = "Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。"
    expected_line3 = "進めてよいですか？"
    assert expected_line1 in text, (
        f"Checklist must include the exact Japanese gate question: {expected_line1!r}"
    )
    assert expected_line2 in text, (
        f"Checklist must include the exact Japanese gate question: {expected_line2!r}"
    )
    assert expected_line3 in text, (
        f"Checklist must include the exact Japanese gate question: {expected_line3!r}"
    )


# ---------------------------------------------------------------------------
# 13. Without explicit Project Owner GO, must not proceed
# ---------------------------------------------------------------------------

def test_document_says_without_explicit_human_owner_go_must_not_proceed() -> None:
    text_lower = _text().lower()
    assert (
        "without an explicit project owner" in text_lower
        or (
            "explicit project owner" in text_lower
            and "must not proceed" in text_lower
        )
    ), (
        "Checklist must state: without explicit Project Owner GO, Phase 3 activation must not proceed"
    )
