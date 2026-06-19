"""tests/test_detection_result_contract.py — Verify DetectionResult type contract.

Tests both runtime enforcement (__post_init__) and AST-level enforcement
(check_detection_result_static_values via validate_mutation.py).
"""
from __future__ import annotations

import textwrap
import tempfile
from pathlib import Path

import pytest

from core.types import DetectionResult
from scripts.validate_mutation import validate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(body: str) -> Path:
    """Build a minimal candidate file with the given mutation body.

    Body is written at 0-indentation; the helper adds the 4-space indent
    required to sit inside inspect_request.
    """
    body_indented = textwrap.indent(textwrap.dedent(body).strip(), "    ")
    source = "\n".join([
        "from core.types import Request, DetectionResult",
        "",
        "def inspect_request(request: Request) -> DetectionResult:",
        "    # === MUTATION_START ===",
        body_indented,
        "    # === MUTATION_END ===",
        "",
    ])
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(source)
    tmp.flush()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Runtime validation: __post_init__ on DetectionResult
# ---------------------------------------------------------------------------

class TestDetectionResultRuntimeValidation:
    def test_valid_construction_passes(self):
        r = DetectionResult(
            blocked=True, reason="match", confidence=0.9, matched_signals=("x",)
        )
        assert r.blocked is True
        assert r.reason == "match"
        assert r.confidence == 0.9
        assert r.matched_signals == ("x",)

    def test_valid_empty_signals_passes(self):
        r = DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
        assert r.matched_signals == ()

    def test_valid_confidence_zero_int(self):
        r = DetectionResult(blocked=False, reason="ok", confidence=0, matched_signals=())
        assert r.confidence == 0

    def test_valid_confidence_one_int(self):
        r = DetectionResult(blocked=True, reason="match", confidence=1, matched_signals=())
        assert r.confidence == 1

    # blocked field
    def test_blocked_string_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked="yes", reason="x", confidence=0.5, matched_signals=())

    def test_blocked_int_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=1, reason="x", confidence=0.5, matched_signals=())

    def test_blocked_none_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=None, reason="x", confidence=0.5, matched_signals=())

    # reason field
    def test_reason_int_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason=42, confidence=0.5, matched_signals=())

    def test_reason_bool_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason=True, confidence=0.5, matched_signals=())

    def test_reason_none_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason=None, confidence=0.5, matched_signals=())

    # confidence field
    def test_confidence_bool_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason="x", confidence=True, matched_signals=())

    def test_confidence_string_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason="x", confidence="0.5", matched_signals=())

    def test_confidence_nan_raises_value_error(self):
        with pytest.raises(ValueError, match="DetectionResult contract violation"):
            DetectionResult(
                blocked=True, reason="x", confidence=float("nan"), matched_signals=()
            )

    def test_confidence_inf_raises_value_error(self):
        with pytest.raises(ValueError, match="DetectionResult contract violation"):
            DetectionResult(
                blocked=True, reason="x", confidence=float("inf"), matched_signals=()
            )

    def test_confidence_above_range_raises_value_error(self):
        with pytest.raises(ValueError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason="x", confidence=1.1, matched_signals=())

    def test_confidence_below_range_raises_value_error(self):
        with pytest.raises(ValueError, match="DetectionResult contract violation"):
            DetectionResult(blocked=True, reason="x", confidence=-0.1, matched_signals=())

    # matched_signals field
    def test_matched_signals_list_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(
                blocked=True, reason="x", confidence=0.5, matched_signals=["x"]
            )

    def test_matched_signals_int_element_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(
                blocked=True, reason="x", confidence=0.5, matched_signals=(1,)
            )

    def test_matched_signals_mixed_raises_type_error(self):
        with pytest.raises(TypeError, match="DetectionResult contract violation"):
            DetectionResult(
                blocked=True, reason="x", confidence=0.5, matched_signals=("x", 1)
            )


# ---------------------------------------------------------------------------
# AST-level validation: check_detection_result_static_values
# ---------------------------------------------------------------------------

class TestDetectionResultASTValidation:
    def _violation_phrase(self, result: dict) -> str:
        return " ".join(result["violations"]).lower()

    def test_rejects_blocked_string_literal(self):
        p = _make_candidate(
            'return DetectionResult(blocked="yes", reason="x", confidence=0.5, matched_signals=())'
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_blocked_int_literal(self):
        p = _make_candidate(
            "return DetectionResult(blocked=1, reason='x', confidence=0.5, matched_signals=())"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_reason_int_literal(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason=42, confidence=0.5, matched_signals=())"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_confidence_bool_literal(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=True, matched_signals=())"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_confidence_out_of_range_high(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=1.5, matched_signals=())"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_confidence_out_of_range_negative(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=-0.1, matched_signals=())"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_matched_signals_int_element(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=0.5, matched_signals=(1,))"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_matched_signals_list_literal(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=0.5, matched_signals=['x'])"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_kwargs_expansion(self):
        p = _make_candidate("""\
kw = {"blocked": False, "reason": "x", "confidence": 0.5, "matched_signals": ()}
return DetectionResult(**kw)
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    def test_rejects_extra_keyword_field(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='x', confidence=0.5, "
            "matched_signals=(), extra_field='oops')"
        )
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult contract violation" in self._violation_phrase(result)

    # Dynamic safe cases — must pass the full validate_mutation.py check
    def test_dynamic_blocked_bool_call_passes(self):
        p = _make_candidate("""\
signals = []
if "path_traversal_indicator" in request.path.lower():
    signals.append("path_traversal_indicator")
score = 0.9
return DetectionResult(
    blocked=bool(signals),
    reason="matched signals",
    confidence=min(1.0, score),
    matched_signals=tuple(signals),
)
""")
        result = validate(p)
        assert result["valid"], (
            f"Expected valid but got violations: {result['violations']}"
        )

    def test_valid_literal_values_pass(self):
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='no match', "
            "confidence=0.0, matched_signals=())"
        )
        result = validate(p)
        assert result["valid"], (
            f"Expected valid but got violations: {result['violations']}"
        )

    def test_valid_blocked_true_with_string_signals_pass(self):
        p = _make_candidate(
            'return DetectionResult(blocked=True, reason="match", '
            'confidence=0.9, matched_signals=("path_traversal_indicator",))'
        )
        result = validate(p)
        assert result["valid"], (
            f"Expected valid but got violations: {result['violations']}"
        )

    def test_rejects_positional_args(self):
        """Positional-arg DetectionResult call must be rejected at AST level."""
        p = _make_candidate("return DetectionResult(False, 'ok', 0.0, ())")
        result = validate(p)
        assert not result["valid"]
        phrase = self._violation_phrase(result)
        assert "positional argument" in phrase

    def test_rejects_missing_required_field(self):
        """DetectionResult missing a required keyword field must be rejected at AST level."""
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='ok', confidence=0.0)"
        )
        result = validate(p)
        assert not result["valid"]
        phrase = self._violation_phrase(result)
        assert "missing required keyword field" in phrase
