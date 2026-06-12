"""tests/test_propose_output_contract.py — Propose output-contract regression tests.

Pins the root cause of the three 2026-06-03/04 paid-credit runs that recorded
API success (HTTP 200 + tokens) but produced no valid mutation patch: the model
returned ``replacement_code`` that violated the function-body-fragment contract
(first line at column 0), so ``ast.parse()`` rejected it fail-closed and
``mutation_patch.json`` was never written.

See docs/audit_gate/PROPOSE_OUTPUT_CONTRACT_ROOT_CAUSE.md for the evidence map.

All tests are local-only: no Gemini API call, no workflow_dispatch, no ledger
access, no network. No paid-credit run is required to execute this suite.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so imports work regardless of how
# pytest is invoked.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.propose_mutation as pm  # noqa: E402

# The exact error recorded in all three failed paid-credit propose job logs
# (runs 26919888348 / 26922191264 / 26924388218; see
# docs/audit_gate/PAID_CREDIT_RUN_RESULT_REVIEW_INVENTORY.md §6).
_RUN_LOG_SYNTAX_ERROR = (
    "expected an indented block after function definition on line 1"
)

# A replacement_code shape consistent with the run-log evidence: the model
# emitted the detector body starting at column 0 instead of 4-space body
# indentation (hypothesis H1 in the root-cause doc).
_COLUMN0_BODY = (
    'surface = request.path.lower()\n'
    'return DetectionResult(blocked=False, reason="no match", '
    'confidence=0.0, matched_signals=())'
)

# Alternative shape also consistent with the run-log evidence: the model
# emitted its own def with an effectively empty body (hypothesis H3).
_MODEL_EMITTED_DEF = 'def inspect_request(request):\n    # improved detection\n'

# A valid 4-space-indented function-body fragment that satisfies the full
# contract (indentation, return shape, fallthrough guard, static values).
_VALID_BODY = (
    '    surface = request.path.lower() + " " + request.body.lower()\n'
    '    matched = []\n'
    '    if "path_traversal_indicator" in surface:\n'
    '        matched.append("path_traversal_indicator")\n'
    '    if matched:\n'
    '        return DetectionResult(blocked=True, reason="suspicious indicator matched", '
    'confidence=0.7, matched_signals=tuple(matched))\n'
    '    return DetectionResult(blocked=False, reason="no suspicious indicator matched", '
    'confidence=0.0, matched_signals=())'
)


def _patch_json(replacement_code: str) -> str:
    """Build a schema-complete Gemini response JSON with the given code."""
    return json.dumps(
        {
            "mutation_rationale": "test rationale",
            "target_threats": ["THREAT-2024-001"],
            "expected_improvement": "test improvement",
            "risk": "test risk",
            "replacement_code": replacement_code,
        }
    )


# ---------------------------------------------------------------------------
# 1. Historical failure shape — evidence pin and current-validator regression
# ---------------------------------------------------------------------------


class TestHistoricalPaidCreditFailureShape:
    """Pin the 2026-06-03/04 failure shape so it can never silently recur."""

    @staticmethod
    def _runtime_wrapper(code: str) -> str:
        """The validator wrapper as it existed at the failed-run SHAs
        (90d39c86 / 4482b416 / 6b428f14) — before the anchored wrapper and
        the indentation pre-checks were merged."""
        return (
            "def _candidate_body(request):\n"
            "    " + pm._MUTATION_START_MARKER + "\n"
            + code
            + "\n" + pm._MUTATION_END_MARKER + "\n"
        )

    def test_column0_body_reproduces_run_log_error(self) -> None:
        """A column-0 body reproduces the exact run-log SyntaxError at line 3."""
        with pytest.raises(SyntaxError) as excinfo:
            ast.parse(self._runtime_wrapper(_COLUMN0_BODY))
        assert _RUN_LOG_SYNTAX_ERROR in str(excinfo.value)
        assert excinfo.value.lineno == 3, (
            "first line of replacement_code is wrapped line 3 — must match "
            "the '(<unknown>, line 3)' recorded in all three run logs"
        )

    def test_model_emitted_def_reproduces_run_log_error(self) -> None:
        """A model-emitted def with empty body also reproduces the error at line 3."""
        with pytest.raises(SyntaxError) as excinfo:
            ast.parse(self._runtime_wrapper(_MODEL_EMITTED_DEF))
        assert _RUN_LOG_SYNTAX_ERROR in str(excinfo.value)
        assert excinfo.value.lineno == 3

    def test_column0_body_rejected_with_indentation_diagnostic(self) -> None:
        """The current validator rejects the historical shape with a specific
        indentation-contract diagnostic instead of a bare SyntaxError."""
        err = pm._validate_replacement_code(_COLUMN0_BODY)
        assert "indentation contract violation" in err

    def test_model_emitted_def_rejected_with_def_diagnostic(self) -> None:
        err = pm._validate_replacement_code(_MODEL_EMITTED_DEF)
        assert "must not include a function definition" in err

    def test_historical_shape_rejected_through_full_contract_path(self) -> None:
        """End to end: a schema-valid response carrying the historical
        replacement_code shape is rejected and yields no patch dict."""
        patch, err = pm._parse_and_validate_response(_patch_json(_COLUMN0_BODY))
        assert patch is None
        assert "Gemini replacement_code validation failed" in err


# ---------------------------------------------------------------------------
# 2. Meaningless-candidate rejections (empty / pass-only / ellipsis / markdown)
# ---------------------------------------------------------------------------


class TestMeaninglessCandidateRejections:
    """Invalid model output must be rejected fail-closed, never repaired."""

    def test_empty_body_rejected(self) -> None:
        patch, err = pm._parse_and_validate_response(_patch_json(""))
        assert patch is None
        assert "Gemini replacement_code validation failed" in err

    def test_comment_only_body_rejected(self) -> None:
        patch, err = pm._parse_and_validate_response(
            _patch_json("    # only a comment")
        )
        assert patch is None
        assert "Gemini replacement_code validation failed" in err

    def test_pass_only_body_rejected(self) -> None:
        err = pm._validate_replacement_code("    pass")
        assert err != "", "pass-only body must be rejected"
        assert "pass-only body" in err

    def test_ellipsis_only_body_rejected(self) -> None:
        """A placeholder-only body (... as the only statement) must be
        rejected — it would create a meaningless candidate."""
        err = pm._validate_replacement_code("    ...")
        assert err != "", "ellipsis-only body must be rejected"
        assert "return" in err, (
            "rejection must point at the missing return DetectionResult(...) "
            f"obligation, got: {err!r}"
        )

    def test_markdown_wrapped_code_rejected_not_stripped(self) -> None:
        """Markdown fences are rejected outright; the validator never strips
        them into a candidate."""
        fenced = "```python\n" + _VALID_BODY + "\n```"
        err = pm._validate_replacement_code(fenced)
        assert "markdown code fence" in err


# ---------------------------------------------------------------------------
# 3. Valid fixture still passes the full contract path
# ---------------------------------------------------------------------------


class TestValidContractFixture:
    def test_valid_body_passes_validator(self) -> None:
        assert pm._validate_replacement_code(_VALID_BODY) == ""

    def test_valid_response_passes_full_contract_path(self) -> None:
        patch, err = pm._parse_and_validate_response(_patch_json(_VALID_BODY))
        assert err == "", f"valid fixture must pass, got: {err!r}"
        assert patch is not None
        assert patch["replacement_code"] == _VALID_BODY

    def test_offline_sample_passes_full_contract_path(self) -> None:
        """The built-in offline sample must satisfy the same contract the
        model is held to."""
        patch, err = pm._parse_and_validate_response(
            json.dumps(pm._SAMPLE_MUTATION)
        )
        assert err == "", f"offline sample must pass the contract, got: {err!r}"
        assert patch is not None


# ---------------------------------------------------------------------------
# 4. Prompt obligations — the contract must be stated to the model
# ---------------------------------------------------------------------------


class TestPromptStatesOutputContractObligations:
    """The 2026-06-03/04 failures happened while the prompt did not state the
    body-fragment contract. These tests pin each obligation so it cannot be
    dropped from the system prompt again."""

    def test_prompt_requires_syntactic_validity(self) -> None:
        prompt = pm._LLM_SYSTEM_PROMPT
        assert "syntactically valid Python" in prompt
        assert "ast.parse()" in prompt
        assert "SyntaxError is rejected" in prompt

    def test_prompt_forbids_empty_body(self) -> None:
        assert "Do NOT return an empty body" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_forbids_pass_only_body(self) -> None:
        assert "Do NOT produce a pass-only body" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_forbids_placeholder_ellipsis(self) -> None:
        assert "Do NOT use placeholder ellipsis" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_forbids_markdown_fences(self) -> None:
        assert "Do NOT wrap in markdown fences" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_states_indentation_contract(self) -> None:
        prompt = pm._LLM_SYSTEM_PROMPT
        assert "EXACTLY 4 spaces" in prompt
        assert "multiple of 4" in prompt

    def test_prompt_forbids_def_statement(self) -> None:
        assert "Do NOT include def inspect_request(...)" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_requires_json_only_output(self) -> None:
        assert "Return JSON only" in pm._LLM_SYSTEM_PROMPT

    def test_prompt_with_obligations_stays_within_prompt_length_gate(self) -> None:
        """The added obligations must not push the real prompt past the
        max_prompt_chars gate that guards every live call."""
        genome = json.loads(
            (_PROJECT_ROOT / "data" / "genome.json").read_text(encoding="utf-8")
        )
        detector_source = (_PROJECT_ROOT / "core" / "detector.py").read_text(
            encoding="utf-8"
        )
        user_prompt = pm._build_user_prompt(genome, detector_source)
        full = pm._LLM_SYSTEM_PROMPT + "\n" + user_prompt
        max_prompt_chars = int(genome["max_prompt_chars"])
        assert len(full) <= max_prompt_chars, (
            f"full prompt is {len(full)} chars; exceeds "
            f"max_prompt_chars={max_prompt_chars} — live calls would fail "
            "at the prompt-length gate"
        )


# ---------------------------------------------------------------------------
# 5. Failure diagnostics — output-contract failure, not API failure
# ---------------------------------------------------------------------------


class TestFailureDiagnosticsIdentifyContractStage:
    """The three failed runs recorded ledger success=true while propose failed,
    which was repeatedly misread as API/promotion state confusion. Every
    model-output rejection must therefore name the stage explicitly."""

    def test_invalid_replacement_code_error_names_contract_stage(self) -> None:
        _, err = pm._parse_and_validate_response(_patch_json(_COLUMN0_BODY))
        assert "propose/output-contract failure" in err
        assert "API call succeeded" in err

    def test_invalid_json_error_names_contract_stage(self) -> None:
        _, err = pm._parse_and_validate_response("not json at all")
        assert "Gemini response is not valid JSON" in err
        assert "propose/output-contract failure" in err

    def test_schema_error_names_contract_stage(self) -> None:
        _, err = pm._parse_and_validate_response(json.dumps({"foo": "bar"}))
        assert "failed schema validation" in err
        assert "propose/output-contract failure" in err

    def test_contract_failure_is_not_described_as_api_failure(self) -> None:
        for raw in (
            _patch_json(_COLUMN0_BODY),
            _patch_json(""),
            "not json at all",
        ):
            _, err = pm._parse_and_validate_response(raw)
            assert "API call failed" not in err, (
                "an output-contract rejection must never read like an API "
                f"failure, got: {err!r}"
            )

    def test_stage_marker_distinct_from_api_failure_wording(self) -> None:
        """The API-failure path uses 'Gemini API call failed ...'; the stage
        marker must not collide with it."""
        assert "API call failed" not in pm._OUTPUT_CONTRACT_STAGE
        assert "propose/output-contract failure" in pm._OUTPUT_CONTRACT_STAGE


# ---------------------------------------------------------------------------
# 6. Runtime allocation risk gap (G1) — S4 repeat-multiplier regression
# ---------------------------------------------------------------------------

# Helper: build a minimal-valid replacement_code body with the given
# confidence expression injected as the second statement.
def _g1_body(conf_expr: str) -> str:
    return (
        '    matched = ["x"]\n'
        f'    confidence = {conf_expr}\n'
        '    return DetectionResult(blocked=True, reason="test", '
        'confidence=confidence, matched_signals=tuple(matched))'
    )


# Branch-based confidence — no multiplier, always safe.
_G1_BRANCH_BODY = (
    '    matched = ["x"]\n'
    '    confidence = 0.5\n'
    '    if len(matched) > 1:\n'
    '        confidence = 0.7\n'
    '    if len(matched) > 2:\n'
    '        confidence = 0.9\n'
    '    return DetectionResult(blocked=True, reason="test", '
    'confidence=confidence, matched_signals=tuple(matched))'
)


class TestRuntimeAllocationRiskGap:
    """Pin the G1 gap closure: propose-side check 6.5 must reject all 12
    multiplication patterns that apply-side core/policy.py _check_repeat_mult()
    rejects, covering both operand orders and all runtime-expression kinds."""

    # --- 12 rejection tests ---------------------------------------------------

    def test_float_times_name_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("0.3 * indicator_count"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_name_times_float_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("indicator_count * 0.3"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_float_times_call_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("0.12 * len(matched)"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_call_times_float_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("len(matched) * 0.12"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_float_times_attribute_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("0.2 * request.score"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_attribute_times_float_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("request.score * 0.2"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_int_times_name_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("2 * indicator_count"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_name_times_int_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("indicator_count * 2"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_int_times_call_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("2 * len(matched)"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_call_times_int_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("len(matched) * 2"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_int_times_attribute_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("2 * request.score"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    def test_attribute_times_int_rejected(self) -> None:
        err = pm._validate_replacement_code(_g1_body("request.score * 2"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err

    # --- 2 string-constant rejection tests (Codex P2 #2) ----------------------

    def test_str_times_call_rejected(self) -> None:
        """\"a\" * len(request.path) — string constant × Call — must be rejected.
        Apply-side _check_repeat_mult rejects this as runtime allocation risk."""
        err = pm._validate_replacement_code(_g1_body('"a" * len(request.path)'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"str×Call must be rejected, got: {err!r}"
        )

    def test_call_times_str_rejected(self) -> None:
        """len(request.path) * \"a\" — Call × string constant — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('len(request.path) * "a"'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"Call×str must be rejected, got: {err!r}"
        )

    def test_str_times_name_rejected(self) -> None:
        """\"a\" * indicator_count — string constant × Name — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('"a" * indicator_count'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"str×Name must be rejected, got: {err!r}"
        )

    def test_name_times_str_rejected(self) -> None:
        """indicator_count * \"a\" — Name × string constant — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('indicator_count * "a"'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"Name×str must be rejected, got: {err!r}"
        )

    def test_str_times_attribute_rejected(self) -> None:
        """\"a\" * request.score — string constant × Attribute — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('"a" * request.score'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"str×Attribute must be rejected, got: {err!r}"
        )

    def test_attribute_times_str_rejected(self) -> None:
        """request.score * \"a\" — Attribute × string constant — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('request.score * "a"'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"Attribute×str must be rejected, got: {err!r}"
        )

    # --- 2 arithmetic BinOp rejection tests (Codex P2 #3) ---------------------

    def test_float_times_arithmetic_name_rejected(self) -> None:
        """0.3 * (indicator_count + 1) — float × BinOp(Name) — must be rejected."""
        err = pm._validate_replacement_code(_g1_body("0.3 * (indicator_count + 1)"))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"float×BinOp(Name) must be rejected, got: {err!r}"
        )

    def test_str_times_arithmetic_call_rejected(self) -> None:
        """\"a\" * (len(matched) + 1) — str × BinOp(Call) — must be rejected."""
        err = pm._validate_replacement_code(_g1_body('"a" * (len(matched) + 1)'))
        assert "runtime allocation risk" in err and "repeat multiplier is non-constant" in err, (
            f"str×BinOp(Call) must be rejected, got: {err!r}"
        )

    # --- 7 pass-through / regression tests ------------------------------------

    def test_branch_based_confidence_still_passes(self) -> None:
        """Branch-based confidence (no multiplier) must not be flagged."""
        assert pm._validate_replacement_code(_G1_BRANCH_BODY) == "", (
            "branch-based confidence must pass check 6.5"
        )

    def test_valid_fixture_still_passes(self) -> None:
        """Standard _VALID_BODY fixture must continue to pass after G1 broadening."""
        assert pm._validate_replacement_code(_VALID_BODY) == "", (
            "valid fixture must still pass after G1 check broadening"
        )

    def test_offline_sample_still_passes(self) -> None:
        """Offline sample must pass: it uses branch-based confidence after the
        _SAMPLE_MUTATION update, so no multiplier expression is present."""
        patch, err = pm._parse_and_validate_response(
            json.dumps(pm._SAMPLE_MUTATION)
        )
        assert err == "", (
            f"offline sample must still pass after G1 broadening, got: {err!r}"
        )
        assert patch is not None

    def test_constant_only_multiplication_passes(self) -> None:
        """0.3 * 0.9 (constant × constant) must NOT be flagged — purely static."""
        body = (
            '    confidence = 0.3 * 0.9\n'
            '    return DetectionResult(blocked=False, reason="no match", '
            'confidence=confidence, matched_signals=())'
        )
        assert pm._validate_replacement_code(body) == "", (
            "constant×constant multiplication must not be rejected by check 6.5"
        )

    def test_full_contract_path_rejects_unsafe_multiplier(self) -> None:
        """End to end: a schema-valid patch carrying a G1-violating body is
        rejected by _parse_and_validate_response and yields no patch dict."""
        unsafe_body = _g1_body("0.3 * indicator_count")
        patch, err = pm._parse_and_validate_response(_patch_json(unsafe_body))
        assert patch is None, "G1-violating body must not produce a valid patch"
        assert "runtime allocation risk" in err, (
            f"contract-path error must name the G1 violation, got: {err!r}"
        )

    def test_full_contract_path_rejects_str_repeat_multiplier(self) -> None:
        """End to end: string repeat multiplier in schema-valid patch is rejected."""
        str_repeat_body = (
            '    matched = ["x"]\n'
            '    confidence = 0.7\n'
            '    repeated = "a" * len(request.path)\n'
            '    return DetectionResult(blocked=True, reason="test", '
            'confidence=confidence, matched_signals=tuple(matched))'
        )
        patch, err = pm._parse_and_validate_response(_patch_json(str_repeat_body))
        assert patch is None, "string repeat multiplier must not produce a valid patch"
        assert "runtime allocation risk" in err
        assert "repeat multiplier is non-constant" in err

    def test_prompt_states_runtime_allocation_obligation(self) -> None:
        """Rule 17 in _LLM_SYSTEM_PROMPT must explicitly state the runtime
        allocation risk constraint so the model cannot generate violating code."""
        prompt = pm._LLM_SYSTEM_PROMPT
        assert "runtime allocation risk" in prompt, (
            "prompt must state 'runtime allocation risk' (rule 17)"
        )
        assert "repeat multiplier" in prompt, (
            "prompt must name 'repeat multiplier' so the model knows the constraint"
        )
        assert "non-constant" in prompt, (
            "prompt must use 'non-constant' to describe the rejected multiplier pattern"
        )
