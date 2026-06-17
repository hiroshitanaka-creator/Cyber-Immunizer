the full original test content plus new class at the end:

class TestPromotePushRetryHardening:
    """Structural tests for the new promote push rebase retry hardening."""

    def test_promote_checkout_uses_ref_main(self, promote_section: str) -> None:
        """promote job checkout must explicitly use ref: main."""
        assert "ref: main" in promote_section, (
            "promote job must checkout with explicit ref: main to ensure it operates on the canonical branch."
        )

    def test_promote_checkout_has_token(self, promote_section: str) -> None:
        """promote job checkout must include token for write permission."""
        assert "token: ${{ secrets.GITHUB_TOKEN }}" in promote_section

    def test_promote_commit_step_has_push_origin_head_main(self, promote_section: str) -> None:
        """promote commit step must use git push origin HEAD:main (not bare git push)."""
        assert "git push origin HEAD:main" in promote_section

    def test_promote_commit_step_has_fetch_origin_main(self, promote_section: str) -> None:
        """promote commit step must fetch before rebase on failure."""
        assert "git fetch origin main" in promote_section

    def test_promote_commit_step_has_rebase(self, promote_section: str) -> None:
        """promote commit step must attempt rebase onto origin/main."""
        assert "git rebase origin/main" in promote_section

    def test_promote_commit_step_has_max_attempts(self, promote_section: str) -> None:
        """promote commit step must have max_attempts=5 retry logic."""
        assert "max_attempts=5" in promote_section

    def test_promote_commit_step_no_force(self, promote_section: str) -> None:
        """promote commit step must never use --force."""
        assert "--force" not in promote_section
        assert "-f " not in promote_section

    def test_promote_commit_step_no_bare_git_push(self, promote_section: str) -> None:
        """promote commit step must not end with a bare 'git push'."""
        # The retry logic uses git push origin HEAD:main inside the loop
        assert "git push origin HEAD:main" in promote_section
        # Should not have a bare git push at the end of the step
        lines = promote_section.splitlines()
        last_push_lines = [l for l in lines if 'git push' in l and 'origin HEAD:main' not in l]
        assert len(last_push_lines) == 0 or all('origin HEAD:main' in l for l in last_push_lines), (
            "promote commit step should not contain a bare git push."
        )

    def test_persist_ledger_retry_still_present(self, persist_ledger_section: str) -> None:
        """Existing persist-ledger rebase retry behavior must remain unchanged."""
        assert "max_attempts=5" in persist_ledger_section
        assert "git fetch origin main" in persist_ledger_section
        assert "git rebase origin/main" in persist_ledger_section
        assert "git push origin HEAD:main" in persist_ledger_section
