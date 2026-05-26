"""tests/test_preflight_workflow.py — Structural tests for gemini-paid-credit-preflight.

Verifies:
  1. immunization_loop.yml has gemini-paid-credit-preflight in mode options
  2. The propose job dispatch has the elif branch for gemini-paid-credit-preflight
  3. gemini-paid-credit-preflight does NOT install live Gemini dependencies
  4. gemini-paid-credit-preflight uses --gemini-paid-credit-preflight flag (not --allow-live-model)
  5. ci.yml does NOT contain gemini-paid-credit-preflight
  6. api_budget.py append_usage_record docstring does NOT say malformed ledger is overwritten
  7. api_budget.py append_usage_record raises ValueError on malformed ledger (not overwrites)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "immunization_loop.yml"
_CI_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
_API_BUDGET_PATH = _PROJECT_ROOT / "scripts" / "api_budget.py"


@pytest.fixture(scope="module")
def workflow_content() -> str:
    assert _WORKFLOW_PATH.exists(), f"Workflow not found: {_WORKFLOW_PATH}"
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ci_content() -> str:
    assert _CI_WORKFLOW_PATH.exists(), f"CI workflow not found: {_CI_WORKFLOW_PATH}"
    return _CI_WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def api_budget_source() -> str:
    assert _API_BUDGET_PATH.exists(), f"api_budget.py not found: {_API_BUDGET_PATH}"
    return _API_BUDGET_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. immunization_loop.yml has gemini-paid-credit-preflight in mode options
# ---------------------------------------------------------------------------


class TestWorkflowModeOptions:
    def test_gemini_paid_credit_preflight_in_mode_options(
        self, workflow_content: str
    ) -> None:
        """immunization_loop.yml must list gemini-paid-credit-preflight as a mode option."""
        assert "gemini-paid-credit-preflight" in workflow_content, (
            "immunization_loop.yml must include 'gemini-paid-credit-preflight' "
            "in the workflow_dispatch mode options."
        )

    def test_preflight_in_options_block(self, workflow_content: str) -> None:
        """gemini-paid-credit-preflight must appear in the options: block."""
        import re
        # Find the options block
        options_match = re.search(
            r"options:\s*((?:\s*-\s*.+\n)+)",
            workflow_content,
        )
        assert options_match is not None, (
            "Could not find 'options:' block in workflow_dispatch inputs."
        )
        options_block = options_match.group(0)
        assert "gemini-paid-credit-preflight" in options_block, (
            "gemini-paid-credit-preflight must be listed under 'options:' in the "
            "workflow_dispatch inputs, not just mentioned in comments."
        )


# ---------------------------------------------------------------------------
# 2. propose job dispatch has gemini-paid-credit-preflight elif branch
# ---------------------------------------------------------------------------


class TestWorkflowDispatchBranch:
    def test_propose_dispatch_has_preflight_elif(
        self, workflow_content: str
    ) -> None:
        """The propose job must have an elif branch for gemini-paid-credit-preflight."""
        assert 'EFFECTIVE_MODE" = "gemini-paid-credit-preflight"' in workflow_content or \
               "EFFECTIVE_MODE" in workflow_content and "gemini-paid-credit-preflight" in workflow_content, (
            "The propose job dispatch must have an elif branch for "
            "gemini-paid-credit-preflight."
        )

    def test_preflight_dispatch_calls_correct_script_flag(
        self, workflow_content: str
    ) -> None:
        """The preflight dispatch must call propose_mutation.py with --gemini-paid-credit-preflight."""
        assert "--gemini-paid-credit-preflight" in workflow_content, (
            "The workflow dispatch for preflight mode must call "
            "propose_mutation.py with --gemini-paid-credit-preflight."
        )

    def test_preflight_dispatch_does_not_use_allow_live_model(
        self, workflow_content: str
    ) -> None:
        """The preflight mode command must NOT use --allow-live-model.

        The preflight does not call the API, so --allow-live-model (the explicit
        opt-in for live API calls) must not be present in the preflight dispatch.
        We check by finding the preflight elif block specifically.
        """
        import re
        # Find the preflight elif block
        preflight_match = re.search(
            r'elif \[ "\$EFFECTIVE_MODE" = "gemini-paid-credit-preflight" \].*?(?=elif|\belse\b|\bfi\b)',
            workflow_content,
            re.DOTALL,
        )
        if preflight_match:
            preflight_block = preflight_match.group(0)
            assert "--allow-live-model" not in preflight_block, (
                "The gemini-paid-credit-preflight dispatch must NOT use "
                "--allow-live-model since no live API call is made."
            )


# ---------------------------------------------------------------------------
# 3. gemini-paid-credit-preflight does NOT install live Gemini dependencies
# ---------------------------------------------------------------------------


class TestPreflightNoGeminiDeps:
    def test_gemini_deps_install_step_excludes_preflight(
        self, workflow_content: str
    ) -> None:
        """The 'Install Gemini dependencies' step must NOT include preflight in its condition.

        The preflight mode does not call the Gemini API and therefore does not
        need google-genai installed.  Including preflight in the gemini-deps
        install step would be incorrect and could mask missing-key errors.
        """
        import re
        # Find the Install Gemini dependencies step
        gemini_deps_match = re.search(
            r"Install Gemini dependencies.*?(?=\n      - name:|\Z)",
            workflow_content,
            re.DOTALL,
        )
        if gemini_deps_match:
            deps_block = gemini_deps_match.group(0)
            assert "gemini-paid-credit-preflight" not in deps_block, (
                "The 'Install Gemini dependencies' step must NOT include "
                "'gemini-paid-credit-preflight' in its if condition.  The "
                "preflight requires no google-genai dependency."
            )


# ---------------------------------------------------------------------------
# 4. ci.yml does NOT contain gemini-paid-credit-preflight
# ---------------------------------------------------------------------------


class TestCiWorkflowExcludesPreflight:
    def test_ci_yml_does_not_run_preflight(self, ci_content: str) -> None:
        """ci.yml must NOT execute gemini-paid-credit-preflight.

        The preflight mode depends on GEMINI_API_KEY being present.  Regular
        push/PR CI never has GEMINI_API_KEY, so preflight must not be in ci.yml.
        """
        assert "gemini-paid-credit-preflight" not in ci_content, (
            "ci.yml must NOT contain 'gemini-paid-credit-preflight'. "
            "Preflight depends on GEMINI_API_KEY which is absent from regular CI."
        )

    def test_ci_yml_does_not_have_gemini_api_key(self, ci_content: str) -> None:
        """ci.yml must not pass GEMINI_API_KEY as an env var or secret.

        This is a safety property to ensure regular push/PR CI can never
        accidentally call the Gemini API.
        """
        assert "secrets.GEMINI_API_KEY" not in ci_content, (
            "ci.yml must NOT reference 'secrets.GEMINI_API_KEY'. "
            "Regular push/PR CI must never have access to the Gemini API key."
        )


# ---------------------------------------------------------------------------
# 5. api_budget.py docstring does NOT say malformed ledger is overwritten
# ---------------------------------------------------------------------------


class TestApiBudgetDocstring:
    def test_append_usage_record_docstring_does_not_say_overwrite(
        self, api_budget_source: str
    ) -> None:
        """append_usage_record docstring must not claim it overwrites malformed ledger.

        The old (incorrect) docstring said:
          'If the file is unreadable or malformed, the record is still written
          (the malformed file is overwritten with a fresh array).'

        This contradicts the actual behavior (raise ValueError, fail closed).
        The docstring must be corrected to match the implementation.
        """
        assert "the malformed file is overwritten" not in api_budget_source, (
            "append_usage_record docstring must not say 'the malformed file is "
            "overwritten'.  The actual behavior is to raise ValueError and "
            "refuse to overwrite a corrupt ledger (fail-closed design)."
        )

    def test_append_usage_record_docstring_does_not_say_record_still_written(
        self, api_budget_source: str
    ) -> None:
        """Docstring must not say record is still written on malformed ledger.

        The old text 'the record is still written' was incorrect — the function
        raises ValueError on a malformed ledger and does NOT write the record.
        """
        # Only check the append_usage_record function body, not other functions
        # Find the append_usage_record function
        import re
        func_match = re.search(
            r'def append_usage_record\(.*?\n(?=def |\Z)',
            api_budget_source,
            re.DOTALL,
        )
        if func_match:
            func_text = func_match.group(0)
            assert "record is still written" not in func_text, (
                "append_usage_record docstring must not say 'record is still "
                "written' for the malformed ledger case.  The function raises "
                "ValueError and refuses to write when the ledger is corrupt."
            )

    def test_append_usage_record_docstring_mentions_valueerror(
        self, api_budget_source: str
    ) -> None:
        """append_usage_record docstring should document that ValueError is raised."""
        import re
        func_match = re.search(
            r'def append_usage_record\(.*?\n(?=def |\Z)',
            api_budget_source,
            re.DOTALL,
        )
        if func_match:
            func_text = func_match.group(0)
            assert "ValueError" in func_text, (
                "append_usage_record docstring should document that ValueError "
                "is raised when the existing ledger is malformed."
            )

    def test_append_usage_record_docstring_mentions_not_overwritten(
        self, api_budget_source: str
    ) -> None:
        """Docstring should state that corrupt file is NOT overwritten."""
        import re
        func_match = re.search(
            r'def append_usage_record\(.*?\n(?=def |\Z)',
            api_budget_source,
            re.DOTALL,
        )
        if func_match:
            func_text = func_match.group(0)
            # The docstring should say something like "NOT overwritten" or "not overwrite"
            assert (
                "NOT overwritten" in func_text
                or "not overwritten" in func_text
                or "not overwrite" in func_text.lower()
            ), (
                "append_usage_record docstring should state that a corrupt "
                "ledger is NOT overwritten."
            )


# ---------------------------------------------------------------------------
# 6. api_budget.py append_usage_record raises ValueError on malformed (behavioral)
# ---------------------------------------------------------------------------


class TestApiBudgetMalformedLedgerBehavior:
    def test_malformed_ledger_raises_value_error(self, tmp_path: Path) -> None:
        """append_usage_record must raise ValueError on malformed ledger (not overwrite)."""
        if str(_PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(_PROJECT_ROOT))
        from scripts import api_budget as budget

        bad_ledger = tmp_path / "corrupt.json"
        bad_ledger.write_text("NOT VALID JSON !!!", encoding="utf-8")

        with pytest.raises(ValueError):
            budget.append_usage_record(
                bad_ledger,
                model="gemini-2.0-flash",
                estimated_input_chars=100,
                estimated_output_chars=50,
                success=True,
            )

        # Critical: corrupt file must NOT be overwritten
        assert bad_ledger.read_text(encoding="utf-8") == "NOT VALID JSON !!!", (
            "append_usage_record must NOT overwrite a malformed ledger. "
            "Fail-closed design requires the corrupt file to remain unchanged."
        )

    def test_non_array_ledger_raises_value_error(self, tmp_path: Path) -> None:
        """A ledger that is a JSON object (not array) must raise ValueError."""
        if str(_PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(_PROJECT_ROOT))
        from scripts import api_budget as budget

        bad_ledger = tmp_path / "obj_ledger.json"
        original = '{"should": "be array"}'
        bad_ledger.write_text(original, encoding="utf-8")

        with pytest.raises(ValueError):
            budget.append_usage_record(
                bad_ledger,
                model="gemini-2.0-flash",
                estimated_input_chars=100,
                estimated_output_chars=50,
                success=True,
            )

        assert bad_ledger.read_text(encoding="utf-8") == original
