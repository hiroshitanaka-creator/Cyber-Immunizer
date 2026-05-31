"""Regression tests: AI navigation docs must stay present in README and on disk."""

import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
README = REPO_ROOT / "README.md"

AUDIT_GATE_FILES = [
    "docs/audit_gate/README.md",
    "docs/audit_gate/PULLBACK_PROMPT.md",
    "docs/audit_gate/PR_AUDIT_PROTOCOL.md",
    "docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md",
    "docs/audit_gate/CHANGELOG.md",
]

EXISTING_DOCS_WITH_META = [
    "docs/AUDIT_CHARTER.md",
    "docs/PHASE_1_BASELINE.md",
    "docs/PHASE_2_PLAN.md",
    "docs/PHASE_2_COMPLETION_CHECKPOINT.md",
    "docs/API_ACTIVATION_CHECKLIST.md",
    "docs/API_ACTIVATION_RUNBOOK.md",
    "docs/ROLLBACK_BACKTRACK_DESIGN.md",
    "docs/EVOLUTION_HISTORY_AUDIT.md",
    "docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md",
]


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_lists_ai_entrypoint():
    assert "AI_ENTRYPOINT.md" in _readme_text(), (
        "README.md must reference docs/AI_ENTRYPOINT.md"
    )


def test_readme_lists_audit_gate_protocol_files():
    readme = _readme_text()
    for path in AUDIT_GATE_FILES:
        assert path in readme, (
            f"README.md must reference full path {path}"
        )


def test_audit_gate_protocol_files_exist():
    for path in AUDIT_GATE_FILES:
        full = REPO_ROOT / path
        assert full.exists(), f"Expected file {path} to exist on disk"


def test_ai_entrypoint_exists():
    assert (REPO_ROOT / "docs" / "AI_ENTRYPOINT.md").exists(), (
        "docs/AI_ENTRYPOINT.md must exist"
    )


def test_ai_entrypoint_routes_pr_audit_to_changelog():
    text = (REPO_ROOT / "docs" / "AI_ENTRYPOINT.md").read_text(encoding="utf-8")
    assert "audit_gate/CHANGELOG.md" in text, (
        "docs/AI_ENTRYPOINT.md must reference docs/audit_gate/CHANGELOG.md "
        "in its PR audit / merge decision guidance"
    )


def test_existing_docs_have_ai_doc_meta_blocks():
    for path in EXISTING_DOCS_WITH_META:
        full = REPO_ROOT / path
        assert full.exists(), f"Expected file {path} to exist"
        text = full.read_text(encoding="utf-8")
        assert "AI_DOC_META" in text, (
            f"{path} must contain an AI_DOC_META metadata block"
        )
