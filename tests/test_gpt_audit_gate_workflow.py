"""tests/test_gpt_audit_gate_workflow.py — Structural tests for the GPT Audit Gate workflow.

Verifies:
  1. .github/workflows/gpt-audit-gate.yml exists and is wired to pull_request only
  2. No workflow_dispatch trigger (manual triggers are forbidden by CLAUDE.md)
  3. No API-key exposure (GEMINI_API_KEY absent; GITHUB_TOKEN only)
  4. Read-only permissions
  5. The gate builds the packet with build_audit_packet.py and evaluates with
     audit_policy_engine.py in --mode ci-gate, pinned to the event head SHA
  6. The packet is uploaded as an artifact
"""
from __future__ import annotations

from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "gpt-audit-gate.yml"


@pytest.fixture(scope="module")
def workflow_content() -> str:
    assert _WORKFLOW_PATH.exists(), f"Workflow not found: {_WORKFLOW_PATH}"
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def effective_content(workflow_content: str) -> str:
    """Workflow content with comment lines stripped — negative assertions must
    test the configuration, not the documentation comments."""
    lines = []
    for line in workflow_content.splitlines():
        code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
        lines.append(code)
    return "\n".join(lines)


class TestTriggers:
    def test_pull_request_trigger_present(self, workflow_content: str) -> None:
        assert "pull_request:" in workflow_content, (
            "gpt-audit-gate.yml must trigger on pull_request events"
        )

    def test_retriggers_on_synchronize(self, workflow_content: str) -> None:
        """A new push must rebuild the packet (head-SHA freshness)."""
        assert "synchronize" in workflow_content, (
            "gpt-audit-gate.yml must re-run on synchronize so the packet "
            "always describes the current head SHA"
        )

    def test_no_workflow_dispatch(self, effective_content: str) -> None:
        """Manual CI triggers are forbidden (CLAUDE.md 絶対にやってはいけないこと)."""
        assert "workflow_dispatch" not in effective_content, (
            "gpt-audit-gate.yml must not be manually triggerable"
        )

    def test_skips_draft_prs(self, workflow_content: str) -> None:
        assert "github.event.pull_request.draft == false" in workflow_content, (
            "gpt-audit-gate.yml must skip draft PRs (they cannot merge)"
        )


class TestSafety:
    def test_no_gemini_api_key(self, effective_content: str) -> None:
        assert "GEMINI_API_KEY" not in effective_content, (
            "gpt-audit-gate.yml must never reference GEMINI_API_KEY"
        )

    def test_read_only_permissions(self, workflow_content: str, effective_content: str) -> None:
        for perm in ("contents: read", "pull-requests: read", "checks: read"):
            assert perm in workflow_content, (
                f"gpt-audit-gate.yml must declare read-only permission {perm!r}"
            )
        assert "write" not in effective_content, (
            "gpt-audit-gate.yml must not request any write permission"
        )

    def test_uses_actions_github_token_only(self, workflow_content: str, effective_content: str) -> None:
        assert "${{ github.token }}" in workflow_content, (
            "the packet builder must authenticate with the workflow-scoped token"
        )
        assert "secrets." not in effective_content, (
            "gpt-audit-gate.yml must not read repository secrets"
        )


class TestGateSteps:
    def test_builds_packet_in_ci(self, workflow_content: str) -> None:
        assert "scripts/build_audit_packet.py" in workflow_content, (
            "the packet must be built in CI (an LLM-built packet could be fabricated)"
        )
        assert "--github" in workflow_content

    def test_excludes_own_check_run(self, workflow_content: str) -> None:
        """The gate's own in-progress check would otherwise freeze a
        self-referential PENDING into every CI-built packet (Codex P1)."""
        assert "--exclude-check gpt-audit-gate" in workflow_content, (
            "the build step must exclude the gate's own check run from CI classification"
        )

    def test_evaluates_in_ci_gate_mode(self, workflow_content: str) -> None:
        assert "scripts/audit_policy_engine.py" in workflow_content
        assert "--mode ci-gate" in workflow_content, (
            "CI must evaluate the ci-gate subset, not full mode (full mode would "
            "block on sibling checks — circular — and on judgment inputs that "
            "are filled after collection)"
        )

    def test_freshness_pinned_to_event_head_sha(self, workflow_content: str) -> None:
        assert (
            "--current-head-sha" in workflow_content
            and "github.event.pull_request.head.sha" in workflow_content
        ), "the engine must verify the packet against the event head SHA"

    def test_checks_out_pr_head_not_merge_ref(self, workflow_content: str) -> None:
        assert "ref: ${{ github.event.pull_request.head.sha }}" in workflow_content, (
            "checkout must pin the PR head so SSOT facts describe the audited SHA"
        )

    def test_uploads_packet_artifact(self, workflow_content: str) -> None:
        assert "upload-artifact" in workflow_content
        assert "gpt_audit_packet.json" in workflow_content
