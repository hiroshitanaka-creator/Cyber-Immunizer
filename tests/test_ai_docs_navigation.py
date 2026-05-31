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

PHASE_2_5_CLOSEOUT_PATH = "docs/PHASE_2_5_CLOSEOUT_AUDIT.md"
PHASE_3_7_ROADMAP_PATH = "docs/human用roadmap/phase3_to_phase7_roadmap.md"


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


def test_readme_lists_phase3_go_no_go_checklist():
    assert "PHASE_3_GO_NO_GO_CHECKLIST.md" in _readme_text(), (
        "README.md must reference docs/PHASE_3_GO_NO_GO_CHECKLIST.md"
    )


def test_phase3_go_no_go_checklist_exists():
    full = REPO_ROOT / "docs" / "PHASE_3_GO_NO_GO_CHECKLIST.md"
    assert full.exists(), (
        "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must exist on disk"
    )


def test_ai_entrypoint_routes_phase3_readiness_to_checklist():
    text = (REPO_ROOT / "docs" / "AI_ENTRYPOINT.md").read_text(encoding="utf-8")
    assert "PHASE_3_GO_NO_GO_CHECKLIST.md" in text, (
        "docs/AI_ENTRYPOINT.md must reference docs/PHASE_3_GO_NO_GO_CHECKLIST.md "
        "in its Phase 3 readiness / Go-No-Go task routing"
    )


# --- Phase 2.5 closeout and human roadmap invariants ---


def test_phase_2_5_closeout_audit_exists():
    full = REPO_ROOT / PHASE_2_5_CLOSEOUT_PATH
    assert full.exists(), (
        f"{PHASE_2_5_CLOSEOUT_PATH} must exist on disk"
    )


def test_phase_2_5_closeout_audit_has_ai_doc_meta():
    full = REPO_ROOT / PHASE_2_5_CLOSEOUT_PATH
    assert full.exists(), f"{PHASE_2_5_CLOSEOUT_PATH} must exist"
    text = full.read_text(encoding="utf-8")
    assert "AI_DOC_META" in text, (
        f"{PHASE_2_5_CLOSEOUT_PATH} must contain an AI_DOC_META metadata block"
    )


def test_phase_2_5_closeout_audit_has_status_current():
    full = REPO_ROOT / PHASE_2_5_CLOSEOUT_PATH
    assert full.exists(), f"{PHASE_2_5_CLOSEOUT_PATH} must exist"
    text = full.read_text(encoding="utf-8")
    assert "status: CURRENT" in text, (
        f"{PHASE_2_5_CLOSEOUT_PATH} must declare status: CURRENT in its AI_DOC_META block"
    )


def test_phase3_to_phase7_roadmap_exists():
    full = REPO_ROOT / PHASE_3_7_ROADMAP_PATH
    assert full.exists(), (
        f"{PHASE_3_7_ROADMAP_PATH} must exist on disk"
    )


def test_phase3_to_phase7_roadmap_has_ai_doc_meta():
    full = REPO_ROOT / PHASE_3_7_ROADMAP_PATH
    assert full.exists(), f"{PHASE_3_7_ROADMAP_PATH} must exist"
    text = full.read_text(encoding="utf-8")
    assert "AI_DOC_META" in text, (
        f"{PHASE_3_7_ROADMAP_PATH} must contain an AI_DOC_META metadata block"
    )


def test_phase3_to_phase7_roadmap_has_status_current():
    full = REPO_ROOT / PHASE_3_7_ROADMAP_PATH
    assert full.exists(), f"{PHASE_3_7_ROADMAP_PATH} must exist"
    text = full.read_text(encoding="utf-8")
    assert "status: CURRENT" in text, (
        f"{PHASE_3_7_ROADMAP_PATH} must declare status: CURRENT in its AI_DOC_META block"
    )


def test_readme_references_phase_2_5_closeout_audit():
    readme = _readme_text()
    assert "PHASE_2_5_CLOSEOUT_AUDIT.md" in readme, (
        "README.md must reference docs/PHASE_2_5_CLOSEOUT_AUDIT.md"
    )


def test_readme_references_phase3_to_phase7_roadmap():
    readme = _readme_text()
    assert "phase3_to_phase7_roadmap.md" in readme, (
        "README.md must reference docs/human用roadmap/phase3_to_phase7_roadmap.md"
    )


def test_ai_entrypoint_routes_to_phase_2_5_closeout_audit():
    text = (REPO_ROOT / "docs" / "AI_ENTRYPOINT.md").read_text(encoding="utf-8")
    assert "PHASE_2_5_CLOSEOUT_AUDIT.md" in text, (
        "docs/AI_ENTRYPOINT.md must route to docs/PHASE_2_5_CLOSEOUT_AUDIT.md"
    )


def test_ai_entrypoint_routes_to_phase3_to_phase7_roadmap():
    text = (REPO_ROOT / "docs" / "AI_ENTRYPOINT.md").read_text(encoding="utf-8")
    assert "phase3_to_phase7_roadmap.md" in text, (
        "docs/AI_ENTRYPOINT.md must route to docs/human用roadmap/phase3_to_phase7_roadmap.md"
    )


def test_phase3_go_no_go_checklist_references_phase_2_5_closeout_audit():
    full = REPO_ROOT / "docs" / "PHASE_3_GO_NO_GO_CHECKLIST.md"
    assert full.exists(), "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must exist"
    text = full.read_text(encoding="utf-8")
    assert "PHASE_2_5_CLOSEOUT_AUDIT.md" in text, (
        "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must reference docs/PHASE_2_5_CLOSEOUT_AUDIT.md"
    )


def test_phase3_go_no_go_checklist_references_phase3_to_phase7_roadmap():
    full = REPO_ROOT / "docs" / "PHASE_3_GO_NO_GO_CHECKLIST.md"
    assert full.exists(), "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must exist"
    text = full.read_text(encoding="utf-8")
    assert "phase3_to_phase7_roadmap.md" in text, (
        "docs/PHASE_3_GO_NO_GO_CHECKLIST.md must reference docs/human用roadmap/phase3_to_phase7_roadmap.md"
    )
