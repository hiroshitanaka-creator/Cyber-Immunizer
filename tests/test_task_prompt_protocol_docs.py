"""Regression tests: Task Prompt Protocol must enforce Source Evidence requirements."""

import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
PROTOCOL = REPO_ROOT / "docs/audit_gate/TASK_PROMPT_PROTOCOL.md"
ENTRYPOINT = REPO_ROOT / "docs/AI_ENTRYPOINT.md"


def _protocol_text() -> str:
    return PROTOCOL.read_text(encoding="utf-8")


def _entrypoint_text() -> str:
    return ENTRYPOINT.read_text(encoding="utf-8")


def test_task_prompt_protocol_exists():
    assert PROTOCOL.exists(), "docs/audit_gate/TASK_PROMPT_PROTOCOL.md must exist"


def test_protocol_template_has_source_evidence_section():
    assert "Source Evidence" in _protocol_text(), (
        "TASK_PROMPT_PROTOCOL.md template must contain a Source Evidence section"
    )


def test_protocol_forbids_assertion_only_evidence():
    text = _protocol_text()
    assert "assertion" in text or "assertion禁止" in text or "コードを貼らず" in text, (
        "TASK_PROMPT_PROTOCOL.md must explicitly forbid assertion-only evidence "
        "(e.g. 'reviewed'/'checked' without verbatim code)"
    )


def test_protocol_requires_file_line_citation_format():
    text = _protocol_text()
    assert "start_line" in text or "file_path:" in text, (
        "TASK_PROMPT_PROTOCOL.md must show a file_path:start_line-end_line citation format"
    )


def test_protocol_mandatory_rules_include_source_evidence():
    text = _protocol_text()
    # Source Evidence must appear in the mandatory construction rules section
    rules_section = text.split("## Mandatory construction rules")[-1]
    assert "Source Evidence" in rules_section, (
        "Source Evidence requirement must be listed in the Mandatory construction rules section"
    )


def test_protocol_mandatory_rules_include_assertion_ban():
    text = _protocol_text()
    rules_section = text.split("## Mandatory construction rules")[-1]
    assert "assertion" in rules_section or "reviewed" in rules_section, (
        "Mandatory construction rules must explicitly ban assertion-only evidence"
    )


def test_entrypoint_has_source_evidence_intake_check():
    assert "Source Evidence" in _entrypoint_text(), (
        "docs/AI_ENTRYPOINT.md must instruct Claude Code to verify Source Evidence "
        "citations before starting implementation"
    )


def test_entrypoint_intake_check_mentions_mismatch_stop():
    text = _entrypoint_text()
    # Must instruct to stop on mismatch
    assert "mismatch" in text or "stop" in text.lower() or "停止" in text, (
        "docs/AI_ENTRYPOINT.md intake check must instruct Claude Code to stop "
        "when a Source Evidence citation does not match actual file content"
    )
