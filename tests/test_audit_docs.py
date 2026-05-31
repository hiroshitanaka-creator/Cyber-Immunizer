"""tests/test_audit_docs.py — Tests for audit governance documents.

Verifies that required governance files exist and contain mandatory
content sections defined in the AUDIT_CHARTER.md specification.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# File existence tests
# ---------------------------------------------------------------------------


class TestAuditDocumentsExist:
    def test_audit_charter_exists(self) -> None:
        """docs/AUDIT_CHARTER.md must exist."""
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), (
            "docs/AUDIT_CHARTER.md is missing. "
            "This file is required for GPT Audit Gate governance."
        )

    def test_pr_template_exists(self) -> None:
        """.github/PULL_REQUEST_TEMPLATE.md must exist."""
        template = _PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        assert template.exists(), (
            ".github/PULL_REQUEST_TEMPLATE.md is missing. "
            "This file is required for PR audit workflow."
        )

    def test_audit_charter_is_not_empty(self) -> None:
        """docs/AUDIT_CHARTER.md must not be empty."""
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), "docs/AUDIT_CHARTER.md does not exist"
        content = charter.read_text(encoding="utf-8")
        assert len(content.strip()) > 100, (
            "docs/AUDIT_CHARTER.md appears to be nearly empty"
        )

    def test_pr_template_is_not_empty(self) -> None:
        """.github/PULL_REQUEST_TEMPLATE.md must not be empty."""
        template = _PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        assert template.exists(), ".github/PULL_REQUEST_TEMPLATE.md does not exist"
        content = template.read_text(encoding="utf-8")
        assert len(content.strip()) > 100, (
            ".github/PULL_REQUEST_TEMPLATE.md appears to be nearly empty"
        )


# ---------------------------------------------------------------------------
# AUDIT_CHARTER.md content tests
# ---------------------------------------------------------------------------


class TestAuditCharterContent:
    @pytest.fixture(autouse=True)
    def load_charter(self) -> None:
        charter = _PROJECT_ROOT / "docs" / "AUDIT_CHARTER.md"
        assert charter.exists(), "docs/AUDIT_CHARTER.md is required for these tests"
        self.content = charter.read_text(encoding="utf-8")

    def test_charter_has_role_assignments(self) -> None:
        """Charter must define role assignments."""
        assert "Human Owner" in self.content, "Charter must define Human Owner role"
        assert "GPT Audit Gate" in self.content, "Charter must define GPT Audit Gate role"
        assert "Claude Code" in self.content, "Charter must define Claude Code role"

    def test_charter_has_architecture_category(self) -> None:
        """Charter must include Architecture audit category."""
        assert "アーキテクチャ" in self.content or "Architecture" in self.content, (
            "Charter must include Architecture audit category"
        )

    def test_charter_has_security_boundary_category(self) -> None:
        """Charter must include Security Boundary audit category."""
        assert "セキュリティ境界" in self.content or "Security Boundary" in self.content, (
            "Charter must include Security Boundary audit category"
        )

    def test_charter_has_fitness_regression_category(self) -> None:
        """Charter must include Fitness & Regression audit category."""
        assert "フィットネス" in self.content or "Fitness" in self.content, (
            "Charter must include Fitness & Regression audit category"
        )

    def test_charter_has_cost_governance_category(self) -> None:
        """Charter must include Cost & API Governance category."""
        assert "コスト" in self.content or "Cost" in self.content, (
            "Charter must include Cost & API Governance category"
        )

    def test_charter_has_approve_decision(self) -> None:
        """Charter must define APPROVE decision."""
        assert "APPROVE" in self.content, "Charter must define APPROVE decision"

    def test_charter_has_request_changes_decision(self) -> None:
        """Charter must define REQUEST CHANGES decision."""
        assert "REQUEST CHANGES" in self.content, (
            "Charter must define REQUEST CHANGES decision"
        )

    def test_charter_has_block_decision(self) -> None:
        """Charter must define BLOCK decision."""
        assert "BLOCK" in self.content, "Charter must define BLOCK decision"

    def test_charter_block_includes_attack_code(self) -> None:
        """BLOCK conditions must mention attack code / offensive tooling."""
        # Check that some form of attack/exploit prohibition is mentioned in BLOCK context
        content_lower = self.content.lower()
        assert "攻撃" in self.content or "exploit" in content_lower or "attack" in content_lower, (
            "Charter BLOCK conditions must mention attack code prohibition"
        )

    def test_charter_block_includes_secret_leakage(self) -> None:
        """BLOCK conditions must mention secret leakage."""
        assert "シークレット" in self.content or "secret" in self.content.lower(), (
            "Charter BLOCK conditions must mention secret leakage"
        )

    def test_charter_block_includes_ast_policy(self) -> None:
        """BLOCK conditions must mention AST policy weakening."""
        assert "AST" in self.content, (
            "Charter BLOCK conditions must mention AST policy"
        )

    def test_charter_has_output_format_section(self) -> None:
        """Charter must define the mandatory GPT Audit Gate output format."""
        assert "フォーマット" in self.content or "Format" in self.content, (
            "Charter must define the mandatory output format"
        )

    def test_charter_output_format_has_category_table(self) -> None:
        """The output format must include a category evaluation table."""
        # The format includes a table with categories A through F
        assert "カテゴリ" in self.content or "Category" in self.content, (
            "Charter output format must include category evaluation table"
        )


# ---------------------------------------------------------------------------
# PULL_REQUEST_TEMPLATE.md content tests
# ---------------------------------------------------------------------------


class TestPRTemplateContent:
    @pytest.fixture(autouse=True)
    def load_template(self) -> None:
        template = _PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        assert template.exists(), (
            ".github/PULL_REQUEST_TEMPLATE.md is required for these tests"
        )
        self.content = template.read_text(encoding="utf-8")

    def test_template_has_change_summary_section(self) -> None:
        """PR template must have a change summary section."""
        assert "変更概要" in self.content or "Summary" in self.content, (
            "PR template must have a change summary section"
        )

    def test_template_has_audit_categories(self) -> None:
        """PR template must reference audit categories."""
        assert "監査カテゴリ" in self.content or "Audit" in self.content, (
            "PR template must reference audit categories"
        )

    def test_template_has_safety_checklist(self) -> None:
        """PR template must have a safety checklist."""
        assert "安全チェック" in self.content or "Safety" in self.content or "checklist" in self.content.lower(), (
            "PR template must include a safety checklist"
        )

    def test_template_safety_checklist_has_attack_code_item(self) -> None:
        """Safety checklist must include attack code check."""
        assert "攻撃コード" in self.content or "attack" in self.content.lower(), (
            "Safety checklist must include attack code prohibition check"
        )

    def test_template_safety_checklist_has_secret_item(self) -> None:
        """Safety checklist must include secret management check."""
        assert "GEMINI_API_KEY" in self.content or "シークレット" in self.content, (
            "Safety checklist must include secret management check"
        )

    def test_template_safety_checklist_has_ast_policy_item(self) -> None:
        """Safety checklist must include AST policy check."""
        assert "AST" in self.content, (
            "Safety checklist must include AST policy check"
        )

    def test_template_has_gpt_audit_section(self) -> None:
        """PR template must have a GPT Audit Gate section."""
        assert "GPT Audit Gate" in self.content, (
            "PR template must have a GPT Audit Gate section"
        )

    def test_template_audit_section_has_approve(self) -> None:
        """PR template GPT Audit section must include APPROVE option."""
        assert "APPROVE" in self.content, (
            "PR template must include APPROVE option in GPT Audit section"
        )

    def test_template_audit_section_has_request_changes(self) -> None:
        """PR template GPT Audit section must include REQUEST CHANGES option."""
        assert "REQUEST CHANGES" in self.content, (
            "PR template must include REQUEST CHANGES in GPT Audit section"
        )

    def test_template_audit_section_has_block(self) -> None:
        """PR template GPT Audit section must include BLOCK option."""
        assert "BLOCK" in self.content, (
            "PR template must include BLOCK option in GPT Audit section"
        )

    def test_template_has_human_owner_section(self) -> None:
        """PR template must have a Human Owner final decision section."""
        assert "Human Owner" in self.content, (
            "PR template must have a Human Owner final decision section"
        )

    def test_template_has_merge_approval_checkbox(self) -> None:
        """PR template Human Owner section must include merge approval checkbox."""
        assert "マージ承認" in self.content or "merge" in self.content.lower(), (
            "PR template must include a merge approval checkbox"
        )


# ---------------------------------------------------------------------------
# Symbolic indicator consistency tests
# ---------------------------------------------------------------------------


class TestSymbolicIndicatorConsistency:
    """Verify that symbolic indicators are consistent across all files.

    After the rename from __path_traversal_indicator__ to
    path_traversal_indicator, no file should reference the old
    double-underscore indicator format in functional code.
    """

    def test_detector_uses_new_indicator_format(self) -> None:
        """core/detector.py must use indicators without double-underscore prefix."""
        detector = _PROJECT_ROOT / "core" / "detector.py"
        assert detector.exists(), "core/detector.py is required"
        content = detector.read_text(encoding="utf-8")
        # New format: path_traversal_indicator (no __ prefix/suffix in the token itself)
        assert '"path_traversal_indicator"' in content, (
            "detector.py must use 'path_traversal_indicator' (no double-underscore)"
        )
        # Old format must not appear in the functional token list
        assert '"__path_traversal_indicator__"' not in content, (
            "detector.py must not use old __path_traversal_indicator__ format"
        )

    def test_attack_requests_use_new_indicator_format(self) -> None:
        """data/attack_requests.json must use new indicator format (no __ prefix/suffix)."""
        attack_requests = _PROJECT_ROOT / "data" / "attack_requests.json"
        assert attack_requests.exists(), "data/attack_requests.json is required"
        content = attack_requests.read_text(encoding="utf-8")
        assert "PATH_TRAVERSAL_INDICATOR" in content, (
            "attack_requests.json must use PATH_TRAVERSAL_INDICATOR"
        )
        assert "__PATH_TRAVERSAL_INDICATOR__" not in content, (
            "attack_requests.json must not use old __PATH_TRAVERSAL_INDICATOR__ format"
        )

    def test_regression_cases_use_new_indicator_format(self) -> None:
        """data/regression_cases.json must use new indicator format."""
        regression = _PROJECT_ROOT / "data" / "regression_cases.json"
        assert regression.exists(), "data/regression_cases.json is required"
        content = regression.read_text(encoding="utf-8")
        assert "PATH_TRAVERSAL_INDICATOR" in content, (
            "regression_cases.json must use PATH_TRAVERSAL_INDICATOR"
        )
        assert "__PATH_TRAVERSAL_INDICATOR__" not in content, (
            "regression_cases.json must not use old format"
        )

    def test_sample_mutation_uses_new_indicator_format(self) -> None:
        """_SAMPLE_MUTATION in propose_mutation.py must use new indicator format."""
        import scripts.propose_mutation as pm
        replacement_code = pm._SAMPLE_MUTATION["replacement_code"]
        assert "path_traversal_indicator" in replacement_code, (
            "_SAMPLE_MUTATION replacement_code must use 'path_traversal_indicator'"
        )
        assert "__path_traversal_indicator__" not in replacement_code, (
            "_SAMPLE_MUTATION must not use old __path_traversal_indicator__ format"
        )

    def test_sample_mutation_passes_validation(self) -> None:
        """_SAMPLE_MUTATION replacement_code must pass _validate_replacement_code.

        After removing double-underscore from indicator names, the sample code
        no longer triggers the dunder prohibition and passes validation cleanly.
        """
        import scripts.propose_mutation as pm
        code = pm._SAMPLE_MUTATION["replacement_code"]
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"_SAMPLE_MUTATION replacement_code must pass validation, got: {err!r}"
        )

    def test_system_prompt_uses_new_indicator_format(self) -> None:
        """_LLM_SYSTEM_PROMPT must reference new indicator format."""
        import scripts.propose_mutation as pm
        prompt = pm._LLM_SYSTEM_PROMPT
        assert "path_traversal_indicator" in prompt, (
            "_LLM_SYSTEM_PROMPT must mention 'path_traversal_indicator'"
        )
        # Old format with double underscores should not appear as the canonical name
        assert "__path_traversal_indicator__" not in prompt, (
            "_LLM_SYSTEM_PROMPT must not instruct LLM to use old __xxx__ format"
        )

    def test_indicator_lowercase_matches_json_uppercase(self) -> None:
        """Verify that JSON uppercase indicators match detector lowercase tokens.

        JSON uses PATH_TRAVERSAL_INDICATOR (uppercase).
        Detector lowercases input, so it matches 'path_traversal_indicator'.
        """
        import json
        import scripts.propose_mutation as pm
        detector = _PROJECT_ROOT / "core" / "detector.py"
        attack_requests = _PROJECT_ROOT / "data" / "attack_requests.json"

        detector_content = detector.read_text(encoding="utf-8")
        requests_data = json.loads(attack_requests.read_text(encoding="utf-8"))

        # Collect all path values and check they lowercase to a known indicator
        known_indicators = {
            "path_traversal_indicator",
            "script_injection_indicator",
            "sqli_indicator",
            "command_delimiter_indicator",
            "encoded_traversal_indicator",
        }

        for record in requests_data:
            req = record.get("request", {})
            all_values = (
                [req.get("path", "")]
                + list(req.get("query", {}).values())
                + [req.get("body", "")]
            )
            for val in all_values:
                val_lower = val.lower()
                # If it looks like an indicator value, it should match a known one
                for indicator in known_indicators:
                    if indicator in val_lower:
                        assert indicator in detector_content, (
                            f"Indicator '{indicator}' appears in attack_requests.json "
                            f"but is not in core/detector.py _SUSPICIOUS_TOKENS"
                        )


# ---------------------------------------------------------------------------
# Audit Gate CHANGELOG lessons — PR #40–#43
# ---------------------------------------------------------------------------


class TestAuditGateChangelogLessons:
    """Verify that docs/audit_gate/CHANGELOG.md records lessons from PR #40–#43."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.changelog = _PROJECT_ROOT / "docs" / "audit_gate" / "CHANGELOG.md"
        assert self.changelog.exists(), "docs/audit_gate/CHANGELOG.md must exist"
        self.content = self.changelog.read_text(encoding="utf-8")

    def _extract_pr_section(self, pr_label: str) -> str:
        """Extract the section for a given PR label (e.g. 'PR #40')."""
        lines = self.content.splitlines()
        in_section = False
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("##"):
                if pr_label in stripped:
                    in_section = True
                    result.append(line)
                    continue
                if in_section:
                    break
            if in_section:
                result.append(line)
        return "\n".join(result)

    def test_changelog_has_pr40_section(self) -> None:
        assert "PR #40" in self.content, (
            "docs/audit_gate/CHANGELOG.md must have a PR #40 section"
        )

    def test_changelog_has_pr41_section(self) -> None:
        assert "PR #41" in self.content, (
            "docs/audit_gate/CHANGELOG.md must have a PR #41 section"
        )

    def test_changelog_has_pr42_section(self) -> None:
        assert "PR #42" in self.content, (
            "docs/audit_gate/CHANGELOG.md must have a PR #42 section"
        )

    def test_changelog_has_pr43_section(self) -> None:
        assert "PR #43" in self.content, (
            "docs/audit_gate/CHANGELOG.md must have a PR #43 section"
        )

    def test_pr40_section_mentions_memoryerror_or_recursionerror(self) -> None:
        section = self._extract_pr_section("PR #40")
        assert section, "PR #40 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "memoryerror" in section_lower or "recursionerror" in section_lower
        ), (
            "PR #40 section in CHANGELOG.md must mention MemoryError or RecursionError"
        )

    def test_pr40_source_size_guard_before_parse(self) -> None:
        """PR #40 section must state source-size guard runs before ast.parse."""
        section = self._extract_pr_section("PR #40")
        assert section, "PR #40 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "source-size" in section_lower or "source size" in section_lower
        ) and (
            "before" in section_lower
        ), (
            "PR #40 section must state source-size guard runs before ast.parse"
        )

    def test_pr40_node_count_guard_runs_after_parsing(self) -> None:
        """PR #40 section must state node-count guard runs after parsing, not before."""
        section = self._extract_pr_section("PR #40")
        assert section, "PR #40 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "node-count" in section_lower or "node count" in section_lower
        ) and (
            "after" in section_lower
        ), (
            "PR #40 section must state node-count guard runs only after ast.parse succeeds"
        )

    def test_pr40_does_not_require_node_count_before_ast_parse(self) -> None:
        """Regression guard: PR #40 section must NOT say node-count guard runs before ast.parse.

        Node-count is not knowable before AST construction.
        """
        section = self._extract_pr_section("PR #40")
        assert section, "PR #40 section must be extractable from CHANGELOG.md"
        forbidden_phrases = [
            "node-count guards must occur before",
            "node-count and depth guards must occur before",
            "source-size and node-count guards must occur before",
        ]
        section_lower = section.lower()
        for phrase in forbidden_phrases:
            assert phrase not in section_lower, (
                f"PR #40 section in CHANGELOG.md must NOT contain '{phrase}'. "
                "Node-count requires a built AST and can only run after ast.parse."
            )

    def test_pr41_section_mentions_computed_repeat_multiplier(self) -> None:
        section = self._extract_pr_section("PR #41")
        assert section, "PR #41 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "computed repeat multiplier" in section_lower
            or "repeat multiplier" in section_lower
            or '10 ** 9' in section
        ), (
            "PR #41 section in CHANGELOG.md must mention computed repeat multiplier"
        )

    def test_pr41_section_mentions_join_generator(self) -> None:
        section = self._extract_pr_section("PR #41")
        assert section, "PR #41 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "join(generator)" in section_lower
            or "join" in section_lower and "generator" in section_lower
        ), (
            "PR #41 section in CHANGELOG.md must mention join(generator)"
        )

    def test_pr42_section_mentions_timeout_unit(self) -> None:
        section = self._extract_pr_section("PR #42")
        assert section, "PR #42 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "timeout unit" in section_lower
            or ("timeout" in section_lower and ("seconds" in section_lower or "milliseconds" in section_lower))
        ), (
            "PR #42 section in CHANGELOG.md must mention timeout unit (seconds vs milliseconds)"
        )

    def test_pr42_section_mentions_max_model_requests_per_run(self) -> None:
        section = self._extract_pr_section("PR #42")
        assert section, "PR #42 section must be extractable from CHANGELOG.md"
        assert "max_model_requests_per_run" in section, (
            "PR #42 section in CHANGELOG.md must mention max_model_requests_per_run"
        )

    def test_pr43_section_mentions_output_root_symlink(self) -> None:
        section = self._extract_pr_section("PR #43")
        assert section, "PR #43 section must be extractable from CHANGELOG.md"
        section_lower = section.lower()
        assert (
            "output_root" in section_lower
            and "symlink" in section_lower
        ), (
            "PR #43 section in CHANGELOG.md must mention output_root symlink"
        )
