"""Regression tests: Thread Handoff Protocol must enforce verifiable-state handoffs."""

import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
PROTOCOL = REPO_ROOT / "docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md"
ENTRYPOINT = REPO_ROOT / "docs/AI_ENTRYPOINT.md"
GATE_README = REPO_ROOT / "docs/audit_gate/README.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
ROOT_README = REPO_ROOT / "README.md"


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_thread_handoff_protocol_exists():
    assert PROTOCOL.exists(), "docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md must exist"


def test_protocol_has_ai_doc_meta():
    assert "AI_DOC_META" in _text(PROTOCOL), (
        "THREAD_HANDOFF_PROTOCOL.md must contain an AI_DOC_META metadata block"
    )


def test_protocol_requires_head_sha():
    text = _text(PROTOCOL)
    assert "head SHA" in text, (
        "THREAD_HANDOFF_PROTOCOL.md must require a verbatim head SHA in the handoff"
    )


def test_protocol_has_outgoing_construction_rules():
    text = _text(PROTOCOL)
    assert "construction rules" in text and "outgoing" in text, (
        "THREAD_HANDOFF_PROTOCOL.md must define outgoing-session construction rules"
    )


def test_protocol_has_incoming_intake_rules():
    text = _text(PROTOCOL)
    assert "intake rules" in text and "incoming" in text, (
        "THREAD_HANDOFF_PROTOCOL.md must define incoming-session intake rules"
    )


def test_protocol_requires_incoming_to_verify_head_sha():
    text = _text(PROTOCOL)
    # The incoming session must re-verify head SHA and stop on mismatch
    assert "stop" in text.lower() or "停止" in text, (
        "THREAD_HANDOFF_PROTOCOL.md must instruct the incoming session to stop "
        "when the actual head SHA differs from the handoff"
    )


def test_protocol_requires_hard_constraints_section():
    text = _text(PROTOCOL)
    assert "Hard constraints" in text, (
        "THREAD_HANDOFF_PROTOCOL.md template must include a Hard constraints section"
    )


def test_protocol_forbids_assertion_only_done_items():
    text = _text(PROTOCOL)
    # Done items must cite a commit or file, not assertion-only
    assert "commit" in text and ("Assertion-only" in text or "assertion-only" in text), (
        "THREAD_HANDOFF_PROTOCOL.md must require Done items to cite a commit/file "
        "and forbid assertion-only completion claims"
    )


def test_entrypoint_routes_to_handoff_protocol():
    assert "THREAD_HANDOFF_PROTOCOL.md" in _text(ENTRYPOINT), (
        "docs/AI_ENTRYPOINT.md must route thread-handoff tasks to THREAD_HANDOFF_PROTOCOL.md"
    )


def test_gate_readme_describes_handoff_protocol():
    assert "THREAD_HANDOFF_PROTOCOL.md" in _text(GATE_README), (
        "docs/audit_gate/README.md must describe THREAD_HANDOFF_PROTOCOL.md"
    )


def test_claude_md_references_handoff_protocol():
    assert "THREAD_HANDOFF_PROTOCOL.md" in _text(CLAUDE_MD), (
        "CLAUDE.md must reference THREAD_HANDOFF_PROTOCOL.md in its protocol table"
    )


def test_root_readme_lists_handoff_protocol():
    assert "THREAD_HANDOFF_PROTOCOL.md" in _text(ROOT_README), (
        "README.md file tree must list docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md"
    )
