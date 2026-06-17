the full original content from the tool response above, plus at the very end after the last class:

class TestPromotePushRetryHardening:
    """Structural tests for promote push rebase retry hardening."""

    def test_promote_checkout_uses_ref_main(self, promote_section: str) -> None:
        """promote job checkout must explicitly use ref: main."""
        assert "ref: main" in promote_section, (
            "promote job must checkout with explicit ref: main to ensure it operates on the canonical branch."
        )

    def test_promote_checkout_has_token(self, promote_section: str) -> None:
        """promote job checkout must include token for write permission."""
        assert "token: ${{ secrets.GITHUB_TOKEN }}" in promote_section

    def test_promote_commit_step_has_push_origin_head_main(self, promote_section: str) -> None:
        """promote commit step must use git push origin HEAD:main, not bare git push."""
        assert "git push origin HEAD:main" in promote_section

    def test_promote_commit_step_has_fetch_origin_main(self, promote_section: str) -> None:
        """promote commit step must fetch before rebase on failure."""
        assert "git fetch origin main" in promote_section

    def test_promote_commit_step_has_rebase(self, promote_section: str) -> None:
        """promote commit step must attempt rebase onto origin/main."""
        assert "git rebase origin/main" in promote_section

    def test_promote_commit_step_has_max_attempts(self, promote_section: str) -> None:
        """promote commit step must have max_attempts retry logic."""
        assert "max_attempts=5" in promote_section or "max_attempts" in promote_section

    def test_promote_commit_step_no_force_push(self, promote_section: str) -> None:
        """promote commit step must never force-push."""
        assert "--force" not in promote_section

    def test_promote_commit_step_no_bare_git_push(self, promote_section: str) -> None:
        """promote commit step must not contain a bare git push command."""
        lines = promote_section.splitlines()
        push_lines = [
            line.strip()
            for line in lines
            if line.strip() == "git push" or line.strip().startswith("git push ")
        ]
        assert push_lines, "Expected promote section to contain a git push command."
        assert all("git push origin HEAD:main" in line for line in push_lines), (
            f"Found non-explicit or bare promote push command(s): {push_lines}"
        )

    def test_persist_ledger_retry_still_present(self, persist_ledger_section: str) -> None:
        """Existing persist-ledger rebase retry behavior must remain present."""
        assert "max_attempts=5" in persist_ledger_section
        assert "git fetch origin main" in persist_ledger_section
        assert "git rebase origin/main" in persist_ledger_section
        assert "git push origin HEAD:main" in persist_ledger_section
