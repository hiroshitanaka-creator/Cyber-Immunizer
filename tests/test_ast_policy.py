"""tests/test_ast_policy.py — Verify AST policy enforcement."""
from __future__ import annotations

import sys
import textwrap
import tempfile
from pathlib import Path

import pytest

from core.policy import (
    MAX_POLICY_SOURCE_CHARS,
    MAX_AST_NODES,
    MAX_AST_DEPTH,
    MAX_LITERAL_CHARS,
    MAX_COLLECTION_ITEMS,
)

from scripts.validate_mutation import validate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(body: str) -> Path:
    """Write a minimal candidate file with given mutation body.

    The body is dedented then re-indented to 4 spaces so it sits correctly
    inside the inspect_request function.  All body lines must be at 0-space
    indentation (relative to each other) before being passed here — the
    function adds the 4-space indent uniformly.
    """
    body_indented = textwrap.indent(textwrap.dedent(body).strip(), "    ")
    lines = [
        "from core.types import Request, DetectionResult",
        "",
        "def inspect_request(request: Request) -> DetectionResult:",
        "    # === MUTATION_START ===",
        body_indented,
        "    # === MUTATION_END ===",
        "",
    ]
    source = "\n".join(lines)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(source)
    tmp.flush()
    return Path(tmp.name)


def _assert_rejected(candidate_path: Path, pattern: str | None = None) -> None:
    result = validate(candidate_path)
    assert not result["valid"], (
        f"Expected rejection but got valid=True. Violations: {result['violations']}"
    )
    if pattern:
        combined = " ".join(result["violations"]).lower()
        assert pattern.lower() in combined, (
            f"Expected violation containing {pattern!r} but got: {result['violations']}"
        )


def _assert_accepted(candidate_path: Path) -> None:
    result = validate(candidate_path)
    assert result["valid"], (
        f"Expected acceptance but got violations: {result['violations']}"
    )


# ---------------------------------------------------------------------------
# Tests: rejected patterns
# All body strings below use 0-space indentation (uniform); _make_candidate
# adds the 4-space indent needed to be inside the function.
# ---------------------------------------------------------------------------

class TestForbiddenImports:
    def test_rejects_import_os(self):
        p = _make_candidate("""\
import os
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "os")

    def test_rejects_import_subprocess(self):
        p = _make_candidate("""\
import subprocess
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "subprocess")

    def test_rejects_import_socket(self):
        p = _make_candidate("""\
import socket
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "socket")

    def test_rejects_import_pathlib(self):
        p = _make_candidate("""\
import pathlib
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "pathlib")

    def test_rejects_import_sys(self):
        p = _make_candidate("""\
import sys
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "sys")

    def test_rejects_from_os(self):
        p = _make_candidate("""\
from os import path
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "os")

    def test_rejects_aliased_detectionresult_import(self):
        """Aliased core.types import must be rejected regardless of what name is used."""
        source = "\n".join([
            "from core.types import Request, DetectionResult as DR",
            "",
            "def inspect_request(request: Request) -> DR:",
            "    # === MUTATION_START ===",
            "    return DR(blocked=False, reason='ok', confidence=0.0, matched_signals=())",
            "    # === MUTATION_END ===",
            "",
        ])
        p = _write_raw_candidate(source)
        _assert_rejected(p, "aliased import")

    def test_rejects_aliased_request_import(self):
        """Aliased import of any core.types name must be rejected."""
        source = "\n".join([
            "from core.types import Request as Req, DetectionResult",
            "",
            "def inspect_request(request: Req) -> DetectionResult:",
            "    # === MUTATION_START ===",
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())",
            "    # === MUTATION_END ===",
            "",
        ])
        p = _write_raw_candidate(source)
        _assert_rejected(p, "aliased import")

    def test_rejects_aliased_detectionresult_positional_args_bypass(self):
        """Aliased DR(...) positional call must be caught by the alias rejection."""
        source = "\n".join([
            "from core.types import Request, DetectionResult as DR",
            "",
            "def inspect_request(request: Request) -> DR:",
            "    # === MUTATION_START ===",
            "    return DR(False, 'ok', 0.0, ())",
            "    # === MUTATION_END ===",
            "",
        ])
        p = _write_raw_candidate(source)
        result = validate(p)
        assert not result["valid"]
        assert "aliased import" in " ".join(result["violations"]).lower()

    def test_canonical_import_still_accepted(self):
        """Non-aliased from core.types import ... must remain valid."""
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())"
        )
        _assert_accepted(p)


class TestDetectionResultLocalAliases:
    """DR = DetectionResult (local alias creation) must be rejected."""

    def test_rejects_local_detectionresult_alias_assignment(self):
        p = _make_candidate("""\
DR = DetectionResult
return DetectionResult(
    blocked=False,
    reason="ok",
    confidence=0.0,
    matched_signals=(),
)
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_local_detectionresult_alias_positional_bypass(self):
        p = _make_candidate("""\
DR = DetectionResult
return DR(False, "ok", 0.0, ())
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_annotated_detectionresult_alias_assignment(self):
        p = _make_candidate("""\
DR: object = DetectionResult
return DetectionResult(
    blocked=False,
    reason="ok",
    confidence=0.0,
    matched_signals=(),
)
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_chained_alias_assignment(self):
        p = _make_candidate("""\
a = b = DetectionResult
return DetectionResult(
    blocked=False,
    reason="ok",
    confidence=0.0,
    matched_signals=(),
)
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_tuple_unpacking_alias(self):
        p = _make_candidate("""\
DR, x = DetectionResult, None
return DetectionResult(
    blocked=False,
    reason="ok",
    confidence=0.0,
    matched_signals=(),
)
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_canonical_detectionresult_call_not_rejected(self):
        """Canonical return statement must not trigger alias check."""
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())"
        )
        result = validate(p)
        assert result["valid"], f"Expected valid but got: {result['violations']}"

    def test_dynamic_canonical_call_not_rejected(self):
        """Dynamic values via canonical keyword call must remain accepted."""
        p = _make_candidate("""\
signals = []
blocked = bool(signals)
return DetectionResult(
    blocked=blocked,
    reason="ok",
    confidence=min(1.0, 0.5),
    matched_signals=tuple(signals),
)
""")
        result = validate(p)
        assert result["valid"], f"Expected valid but got: {result['violations']}"

    def test_rejects_tuple_subscript_detectionresult_alias(self):
        p = _make_candidate("""\
DR = (DetectionResult,)[0]
return DR(False, "ok", 0.0, ())
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_list_subscript_detectionresult_alias(self):
        p = _make_candidate("""\
DR = [DetectionResult][0]
return DR(False, "ok", 0.0, ())
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_ifexp_detectionresult_alias(self):
        p = _make_candidate("""\
DR = DetectionResult if True else DetectionResult
return DR(False, "ok", 0.0, ())
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_rejects_dict_subscript_detectionresult_alias(self):
        p = _make_candidate("""\
DR = {"ctor": DetectionResult}["ctor"]
return DR(False, "ok", 0.0, ())
""")
        result = validate(p)
        assert not result["valid"]
        assert "detectionresult alias" in " ".join(result["violations"]).lower()

    def test_canonical_detectionresult_result_assignment_allowed(self):
        """Assigning the result of a canonical constructor call must be accepted."""
        p = _make_candidate("""\
result = DetectionResult(
    blocked=False,
    reason="ok",
    confidence=0.0,
    matched_signals=(),
)
return result
""")
        result = validate(p)
        assert result["valid"], f"Expected valid but got: {result['violations']}"


class TestForbiddenBuiltins:
    def test_rejects_open(self):
        p = _make_candidate("""\
f = open('/etc/passwd')
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "open")

    def test_rejects_eval(self):
        p = _make_candidate("""\
eval('1+1')
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "eval")

    def test_rejects_exec(self):
        p = _make_candidate("""\
exec('pass')
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "exec")

    def test_rejects_compile(self):
        p = _make_candidate("""\
compile('pass', '<s>', 'exec')
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "compile")

    def test_rejects_globals(self):
        p = _make_candidate("""\
g = globals()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "globals")

    def test_rejects_locals(self):
        p = _make_candidate("""\
l = locals()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "locals")

    def test_rejects_getattr(self):
        p = _make_candidate("""\
x = getattr(object, '__class__')
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p)

    def test_rejects_setattr(self):
        p = _make_candidate("""\
setattr(object, 'x', 1)
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "setattr")


class TestForbiddenDunders:
    def test_rejects_dunder_class(self):
        p = _make_candidate("""\
x = request.__class__
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__class__")

    def test_rejects_dunder_dict(self):
        p = _make_candidate("""\
x = request.__dict__
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__dict__")

    def test_rejects_dunder_globals(self):
        p = _make_candidate("""\
x = inspect_request.__globals__
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__globals__")

    def test_rejects_dunder_subclasses(self):
        p = _make_candidate("""\
x = object.__subclasses__()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__subclasses__")


class TestSubprocessUsage:
    def test_rejects_subprocess_import(self):
        p = _make_candidate("""\
import subprocess
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "subprocess")


class TestForbiddenReflectionBuiltins:
    """type, dir, super, breakpoint, callable must be rejected as forbidden builtins."""

    def test_rejects_type_call(self):
        p = _make_candidate("""\
t = type(request)
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "type")

    def test_rejects_dir_call(self):
        p = _make_candidate("""\
attrs = dir(request)
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "dir")

    def test_rejects_super_call(self):
        p = _make_candidate("""\
s = super()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "super")

    def test_rejects_breakpoint_call(self):
        p = _make_candidate("""\
breakpoint()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "breakpoint")

    def test_rejects_callable_call(self):
        p = _make_candidate("""\
if callable(request):
    pass
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "callable")


class TestForbiddenArbitraryDunders:
    """ANY dunder attribute (__ prefix and suffix) must be rejected."""

    def test_rejects_dunder_len(self):
        p = _make_candidate("""\
n = request.__len__()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__len__")

    def test_rejects_dunder_str(self):
        p = _make_candidate("""\
s = request.__str__()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__str__")

    def test_rejects_dunder_init(self):
        p = _make_candidate("""\
request.__init__()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__init__")

    def test_rejects_dunder_reduce(self):
        """__reduce__ is a pickle-deserialization vector — must be rejected."""
        p = _make_candidate("""\
x = request.__reduce__()
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__reduce__")

    def test_rejects_dunder_class_still(self):
        """__class__ was in the old finite list and must still be rejected."""
        p = _make_candidate("""\
x = request.__class__
return DetectionResult(False, '', 0.0, ())
""")
        _assert_rejected(p, "__class__")


# ---------------------------------------------------------------------------
# Tests: accepted patterns
# ---------------------------------------------------------------------------

class TestAcceptedPatterns:
    def test_accepts_baseline_detector(self):
        """The baseline core/detector.py must pass AST validation."""
        _PROJECT_ROOT = Path(__file__).parent.parent
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        _assert_accepted(baseline)

    def test_accepts_simple_safe_body(self):
        p = _make_candidate("""\
if "../" in request.path:
    return DetectionResult(blocked=True, reason="traversal", confidence=0.9, matched_signals=("../",))
return DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)

    def test_accepts_string_operations(self):
        p = _make_candidate("""\
surface = request.path.lower()
tokens = ["<script", "union select"]
for t in tokens:
    if t in surface:
        return DetectionResult(blocked=True, reason="match", confidence=0.8, matched_signals=(t,))
return DetectionResult(blocked=False, reason="no match", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)

    def test_rejects_detectionresult_positional_args(self):
        """DetectionResult called with positional args must be rejected by AST policy."""
        p = _make_candidate(
            "return DetectionResult(False, 'ok', 0.0, ())"
        )
        _assert_rejected(p, "positional arguments")

    def test_rejects_detectionresult_missing_required_field(self):
        """DetectionResult missing a required keyword field must be rejected by AST policy."""
        p = _make_candidate(
            "return DetectionResult(blocked=False, reason='ok', confidence=0.0)"
        )
        _assert_rejected(p, "missing required keyword field")


# ---------------------------------------------------------------------------
# Tests: AST complexity / DoS guard (backlog #14)
# ---------------------------------------------------------------------------

def _write_raw_candidate(source: str) -> Path:
    """Write raw source text directly (no template wrapping)."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(source)
    tmp.flush()
    return Path(tmp.name)


class TestComplexityGuardAcceptsNormalCode:
    def test_accepts_simple_safe_body_via_complexity_path(self):
        """Normal candidate well within all limits must still be accepted."""
        p = _make_candidate("""\
if "drop table" in request.path.lower():
    return DetectionResult(blocked=True, reason="sqli", confidence=0.9, matched_signals=("drop table",))
return DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)


class TestSourceSizeGuard:
    def test_rejects_oversized_source(self):
        """Source exceeding MAX_POLICY_SOURCE_CHARS must be rejected before parse."""
        # Build a valid-looking candidate that is just over the size limit
        header = (
            "from core.types import Request, DetectionResult\n\n"
            "def inspect_request(request: Request) -> DetectionResult:\n"
            "    # === MUTATION_START ===\n"
        )
        filler_line = "    # " + "x" * 100 + "\n"
        footer = (
            "    return DetectionResult(False, '', 0.0, ())\n"
            "    # === MUTATION_END ===\n"
        )
        # Pad until we exceed the limit
        needed = MAX_POLICY_SOURCE_CHARS - len(header) - len(footer) + 1
        filler = filler_line * (needed // len(filler_line) + 1)
        source = header + filler + footer
        assert len(source) > MAX_POLICY_SOURCE_CHARS
        p = _write_raw_candidate(source)
        _assert_rejected(p, "MAX_POLICY_SOURCE_CHARS")

    def test_accepts_source_exactly_at_limit(self):
        """Source at exactly MAX_POLICY_SOURCE_CHARS should not be rejected for size."""
        # A minimal valid candidate is far below the limit; just confirm no
        # false-positive at a size we control.
        p = _make_candidate("return DetectionResult(False, '', 0.0, ())")
        result = validate(p)
        # May pass or fail for other reasons, but NOT for source size
        combined = " ".join(result.get("violations", []))
        assert "MAX_POLICY_SOURCE_CHARS" not in combined


class TestASTNodeCountGuard:
    def test_rejects_excessive_node_count(self):
        """A body with many statements must be rejected when node count > MAX_AST_NODES."""
        # Each "x = 0" yields ~3 AST nodes. Use MAX_AST_NODES // 2 lines to stay
        # under source-size limit while exceeding the node count limit.
        n = MAX_AST_NODES // 2
        many_stmts = "\n".join(f"x{i} = 0" for i in range(n))
        many_stmts += "\nreturn DetectionResult(False, '', 0.0, ())"
        p = _make_candidate(many_stmts)
        _assert_rejected(p, "MAX_AST_NODES")


class TestASTDepthGuard:
    def test_rejects_deeply_nested_ifs(self):
        """Deeply nested if-statements must be rejected when depth > MAX_AST_DEPTH."""
        # Build a syntactically valid deeply nested structure
        depth = MAX_AST_DEPTH + 5
        indent = "    "
        lines = []
        for i in range(depth):
            lines.append(indent * (i + 1) + f"if True:")
        lines.append(indent * (depth + 1) + "pass")
        body = "\n".join(lines) + "\nreturn DetectionResult(False, '', 0.0, ())"
        p = _make_candidate(body)
        _assert_rejected(p, "MAX_AST_DEPTH")


class TestLiteralSizeGuard:
    def test_rejects_giant_string_literal(self):
        """A string literal exceeding MAX_LITERAL_CHARS must be rejected."""
        big_str = "a" * (MAX_LITERAL_CHARS + 1)
        body = f'x = "{big_str}"\nreturn DetectionResult(False, "", 0.0, ())'
        p = _make_candidate(body)
        _assert_rejected(p, "MAX_LITERAL_CHARS")

    def test_accepts_normal_string_literal(self):
        """A small string literal must not trigger the literal size guard."""
        p = _make_candidate('x = "hello"\nreturn DetectionResult(False, "", 0.0, ())')
        result = validate(p)
        combined = " ".join(result.get("violations", []))
        assert "MAX_LITERAL_CHARS" not in combined


class TestCollectionSizeGuard:
    def test_rejects_giant_list_literal(self):
        """A list literal with more than MAX_COLLECTION_ITEMS elements must be rejected."""
        items = ", ".join(str(i) for i in range(MAX_COLLECTION_ITEMS + 1))
        body = f"x = [{items}]\nreturn DetectionResult(False, '', 0.0, ())"
        p = _make_candidate(body)
        _assert_rejected(p, "MAX_COLLECTION_ITEMS")

    def test_rejects_giant_dict_literal_via_check_directly(self):
        """check_literal_sizes must reject a dict with > MAX_COLLECTION_ITEMS keys."""
        import ast as _ast
        from core.policy import check_literal_sizes
        # Build an AST dict node directly, bypassing source-size / node-count limits
        keys = [_ast.Constant(value=i) for i in range(MAX_COLLECTION_ITEMS + 1)]
        values = [_ast.Constant(value=0)] * len(keys)
        dict_node = _ast.Dict(keys=keys, values=values)
        module = _ast.Module(body=[_ast.Expr(value=dict_node)], type_ignores=[])
        violations = check_literal_sizes(module)
        assert any("MAX_COLLECTION_ITEMS" in v for v in violations), (
            f"Expected MAX_COLLECTION_ITEMS violation, got: {violations}"
        )

    def test_accepts_normal_collection(self):
        """A small list literal must not trigger the collection size guard."""
        p = _make_candidate('x = [1, 2, 3]\nreturn DetectionResult(False, "", 0.0, ())')
        result = validate(p)
        combined = " ".join(result.get("violations", []))
        assert "MAX_COLLECTION_ITEMS" not in combined


class TestComplexityRejectionDoesNotTraceback:
    def test_huge_source_no_traceback(self):
        """Oversized source must return a structured result, not raise an exception."""
        source = "x = 1\n" * (MAX_POLICY_SOURCE_CHARS // 6 + 1)
        p = _write_raw_candidate(source)
        result = validate(p)  # must not raise
        assert isinstance(result, dict)
        assert "valid" in result
        assert not result["valid"]

    def test_deep_nesting_no_traceback(self):
        """Deeply nested body must return a structured failure, not RecursionError."""
        depth = MAX_AST_DEPTH + 20
        indent = "    "
        lines = []
        for i in range(depth):
            lines.append(indent * (i + 1) + "if True:")
        lines.append(indent * (depth + 1) + "pass")
        body = "\n".join(lines) + "\nreturn DetectionResult(False, '', 0.0, ())"
        p = _make_candidate(body)
        result = validate(p)  # must not raise RecursionError
        assert isinstance(result, dict)
        assert not result["valid"]


# ---------------------------------------------------------------------------
# Tests: parser stack overflow / pathological input (Codex P1)
# ---------------------------------------------------------------------------

class TestParserStackOverflowHandling:
    """Pathological inputs that trigger MemoryError / RecursionError in ast.parse
    must produce a structured failure, never a raw traceback."""

    def _make_unary_chain_candidate(self) -> Path:
        """Return a candidate file with a parser-stack-busting unary chain.

        The source stays within MAX_POLICY_SOURCE_CHARS so the pre-parse size
        guard does not intercept it first.
        """
        # "x = ---...---1" with ~9000 unary minuses triggers MemoryError in
        # the CPython parser without exceeding the source size limit.
        body = "x = " + "-" * 9000 + "1\nreturn DetectionResult(False, '', 0.0, ())"
        assert len(body) < MAX_POLICY_SOURCE_CHARS, (
            "Test body must stay within MAX_POLICY_SOURCE_CHARS "
            "to reach the parser, not the pre-parse size guard"
        )
        return _make_candidate(body)

    def test_validate_does_not_raise_on_parser_stack_overflow(self):
        """validate() must return a structured dict, not raise MemoryError."""
        p = self._make_unary_chain_candidate()
        result = validate(p)  # must NOT raise
        assert isinstance(result, dict), "validate() must always return a dict"
        assert "valid" in result

    def test_validate_returns_false_on_parser_stack_overflow(self):
        """validate() must return valid=False for parser-stack-busting input."""
        p = self._make_unary_chain_candidate()
        result = validate(p)
        assert not result["valid"], (
            "Parser-stack-busting input must be rejected"
        )

    def test_validate_violation_describes_parser_failure(self):
        """The violation message must indicate a parser-level failure."""
        p = self._make_unary_chain_candidate()
        result = validate(p)
        combined = " ".join(result.get("violations", [])).lower()
        assert any(
            kw in combined
            for kw in ("parser", "memoryerror", "too complex", "syntaxerror", "recursionerror")
        ), f"Violation must describe parser failure, got: {result.get('violations')}"

    def test_run_full_policy_does_not_raise_on_parser_stack_overflow(self, tmp_path):
        """run_full_policy() itself must not raise on pathological parse input."""
        from core.policy import run_full_policy
        p = self._make_unary_chain_candidate()
        result = run_full_policy(p)  # must NOT raise
        assert isinstance(result, dict)
        assert not result["valid"]


# ---------------------------------------------------------------------------
# Tests: runtime allocation risk guard (PR #41)
# ---------------------------------------------------------------------------

class TestRuntimeAllocationRiskGuard:
    """Patterns that can cause large runtime allocations must be rejected
    by check_runtime_allocation_risks() before evaluation/promote."""

    def test_rejects_list_comprehension(self):
        p = _make_candidate("""\
values = [i for i in range(1000000)]
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "list comprehension")

    def test_rejects_dict_comprehension(self):
        p = _make_candidate("""\
mapping = {str(i): i for i in range(1000000)}
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "dict comprehension")

    def test_rejects_generator_expression_in_any(self):
        p = _make_candidate("""\
result = any(i for i in range(1000000))
return DetectionResult(False, "", 0.0, ())
""")
        # Generator expression must be rejected (not permitted outside join)
        _assert_rejected(p, "generator expression")

    def test_rejects_large_range_in_for_loop(self):
        p = _make_candidate("""\
for i in range(1000000):
    pass
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "MAX_RANGE_CONSTANT")

    def test_rejects_nonconstant_range_argument(self):
        p = _make_candidate("""\
n = len(request.path)
for i in range(n):
    pass
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "non-constant")

    def test_rejects_giant_string_repeat(self):
        p = _make_candidate("""\
x = "a" * 1000000
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "MAX_REPEAT_MULTIPLIER")

    def test_rejects_giant_list_repeat(self):
        p = _make_candidate("""\
x = [0] * 1000000
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "MAX_REPEAT_MULTIPLIER")

    def test_rejects_join_over_large_range_generator(self):
        p = _make_candidate("""\
x = "".join(str(i) for i in range(1000000))
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "join(generator)")

    def test_accepts_simple_for_loop_with_small_range(self):
        p = _make_candidate("""\
tokens = ["a", "b", "c"]
for t in tokens:
    if t in request.path:
        return DetectionResult(blocked=True, reason="match", confidence=0.8, matched_signals=(t,))
return DetectionResult(blocked=False, reason="", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)

    def test_accepts_small_range_constant(self):
        """range() with a small constant must be accepted."""
        p = _make_candidate("""\
for i in range(10):
    pass
return DetectionResult(blocked=False, reason="", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)

    def test_string_concat_bomb_rejected_by_some_guard(self):
        """A long chain of + operations is rejected (by node count or depth guard)."""
        # Build many concatenations — rejected by existing MAX_AST_NODES guard
        n = MAX_AST_NODES // 3
        expr = " + ".join(f'"x{i}"' for i in range(n))
        body = f"x = {expr}\nreturn DetectionResult(False, '', 0.0, ())"
        p = _make_candidate(body)
        result = validate(p)
        assert not result["valid"], (
            "String concatenation bomb must be rejected by some guard"
        )

    def test_no_traceback_on_any_rejected_pattern(self):
        """All rejected patterns must return structured dict without raising."""
        patterns = [
            "values = [i for i in range(9999)]\nreturn DetectionResult(False, '', 0.0, ())",
            "x = 'a' * 999999\nreturn DetectionResult(False, '', 0.0, ())",
            "mapping = {str(i): i for i in range(9999)}\nreturn DetectionResult(False, '', 0.0, ())",
        ]
        for body in patterns:
            p = _make_candidate(body)
            result = validate(p)  # must not raise
            assert isinstance(result, dict)
            assert "valid" in result


# ---------------------------------------------------------------------------
# Tests: computed repeat multiplier guard (Codex P1 fix)
# ---------------------------------------------------------------------------

class TestComputedRepeatMultiplierGuard:
    """Constant-expression repeat multipliers that evaluate to large values must
    be rejected even when they are not bare integer literals."""

    def test_rejects_power_expression_multiplier(self):
        """x = "a" * (10 ** 9) must be rejected."""
        p = _make_candidate("""\
x = "a" * (10 ** 9)
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "MAX_REPEAT_MULTIPLIER")

    def test_rejects_addition_expression_multiplier(self):
        """x = "a" * (500_000 + 500_000) must be rejected."""
        p = _make_candidate("""\
x = "a" * (500000 + 500000)
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "MAX_REPEAT_MULTIPLIER")

    def test_accepts_small_constant_expression_multiplier(self):
        """x = "a" * (10 + 5) is small and must not be rejected for multiplier size."""
        p = _make_candidate("""\
x = "a" * (10 + 5)
return DetectionResult(False, "", 0.0, ())
""")
        result = validate(p)
        combined = " ".join(result.get("violations", []))
        assert "MAX_REPEAT_MULTIPLIER" not in combined, (
            f"Small computed multiplier must not trigger size guard; got: {combined}"
        )

    def test_rejects_unknown_multiplier_from_input(self):
        """x = "a" * len(request.path) must be rejected (non-constant, fail-closed)."""
        p = _make_candidate("""\
x = "a" * len(request.path)
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "non-constant")


# ---------------------------------------------------------------------------
# Tests: join(generator) strict iterable guard (Codex P1 fix)
# ---------------------------------------------------------------------------

class TestJoinGeneratorStrictIterableGuard:
    """join(generator) is only permitted for request.query.items() and
    request.headers.items(). All other iterables must be rejected."""

    def test_rejects_join_over_request_body(self):
        """''.join('x' for _ in request.body) must be rejected (input-sized)."""
        p = _make_candidate("""\
x = "".join("x" for _ in request.body)
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "join(generator)")

    def test_rejects_join_over_request_path(self):
        """''.join('x' for _ in request.path) must be rejected (input-sized)."""
        p = _make_candidate("""\
x = "".join("x" for _ in request.path)
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "join(generator)")

    def test_rejects_join_over_large_range(self):
        """join over large range must still be rejected."""
        p = _make_candidate("""\
x = "".join(str(i) for i in range(1000000))
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "join(generator)")

    def test_rejects_join_over_nonconstant_range(self):
        """join over non-constant range must be rejected."""
        p = _make_candidate("""\
n = len(request.path)
x = "".join(str(i) for i in range(n))
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "join(generator)")

    def test_accepts_join_over_request_query_items(self):
        """join(f'...' for k, v in request.query.items()) must be permitted (baseline pattern)."""
        p = _make_candidate("""\
q = " ".join(f"{k}={v}" for k, v in request.query.items()).lower()
return DetectionResult(False, "", 0.0, ())
""")
        result = validate(p)
        combined = " ".join(result.get("violations", []))
        assert "join(generator)" not in combined, (
            f"Baseline query.items() join must be allowed; got violations: {combined}"
        )

    def test_accepts_join_over_request_headers_items(self):
        """join(f'...' for k, v in request.headers.items()) must be permitted (baseline pattern)."""
        p = _make_candidate("""\
h = " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower()
return DetectionResult(False, "", 0.0, ())
""")
        result = validate(p)
        combined = " ".join(result.get("violations", []))
        assert "join(generator)" not in combined, (
            f"Baseline headers.items() join must be allowed; got violations: {combined}"
        )


# ---------------------------------------------------------------------------
# Tests: alias-bypass closure (AST alias hardening)
# ---------------------------------------------------------------------------

class TestAliasAndDunderNameBypassClosure:
    """Alias-based bypasses of forbidden builtins must be rejected.

    These tests verify that the alias-bypass class is closed in core/policy.py:
    binding a forbidden capability to a local name and calling through that
    alias must be rejected because the forbidden Name reference itself is a
    violation even before the alias is called.
    """

    def test_rejects_alias_to_open_call(self):
        p = _make_candidate("""\
f = open
f("/tmp/x")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_to_eval_call(self):
        p = _make_candidate("""\
e = eval
e("1 + 1")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_to_exec_call(self):
        p = _make_candidate("""\
x = exec
x("pass")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_to_compile_call(self):
        p = _make_candidate("""\
c = compile
c("pass", "<s>", "exec")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_to_import_call(self):
        p = _make_candidate("""\
imp = __import__
m = imp("os")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_chain_to_import_call(self):
        p = _make_candidate("""\
a = __import__
b = a
m = b("os")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_builtins_name_reference(self):
        p = _make_candidate("""\
b = __builtins__
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "dunder name reference")

    def test_rejects_dunder_name_reference(self):
        p = _make_candidate("""\
x = __import__
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_rejects_alias_import_then_attribute_call(self):
        p = _make_candidate("""\
imp = __import__
os_mod = imp("os")
os_mod.system("id")
return DetectionResult(False, "", 0.0, ())
""")
        _assert_rejected(p, "forbidden name reference")

    def test_baseline_detector_still_valid_after_alias_hardening(self):
        """core/detector.py must still pass validation after alias hardening."""
        _PROJECT_ROOT = Path(__file__).parent.parent
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        _assert_accepted(baseline)


# ---------------------------------------------------------------------------
# Tests: structural disallowed AST construct guard (Phase 2.5 Stage A)
# ---------------------------------------------------------------------------

class TestDisallowedAstConstructs:
    """Structural constructs unnecessary for candidate detectors must be rejected.

    Rejection tests verify that each disallowed construct causes check_disallowed_ast_constructs
    to fire.  Acceptance tests verify that baseline-safe patterns still pass after the
    new guard is added to run_full_policy().
    """

    # ------------------------------------------------------------------
    # Rejection tests
    # ------------------------------------------------------------------

    def test_rejects_try_except(self):
        p = _make_candidate("""\
try:
    x = 1
except Exception:
    x = 0
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_raise(self):
        p = _make_candidate("""\
raise RuntimeError("blocked")
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_with_statement(self):
        # Use 'with request:' so the rejection is structural (With node),
        # not triggered by a forbidden builtin such as open().
        p = _make_candidate("""\
with request:
    pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_nested_function_def(self):
        p = _make_candidate("""\
def helper():
    return "x"
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_nested_class_def(self):
        p = _make_candidate("""\
class Helper:
    pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_lambda(self):
        p = _make_candidate("""\
f = lambda x: x
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_while_loop(self):
        # Structural rejection — while False: pass is rejected even though it
        # never executes.
        p = _make_candidate("""\
while False:
    pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_global_nonlocal(self):
        # global is syntactically valid inside inspect_request.
        p = _make_candidate("""\
global x
x = 1
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_nonlocal_via_ast(self):
        # nonlocal requires an enclosing scope; test at the AST level directly.
        import ast as _ast
        from core.policy import check_disallowed_ast_constructs
        nonlocal_node = _ast.Nonlocal(names=["x"])
        _ast.fix_missing_locations(nonlocal_node)
        inner_fn = _ast.FunctionDef(
            name="inspect_request",
            args=_ast.arguments(
                posonlyargs=[], args=[], vararg=None,
                kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[],
            ),
            body=[nonlocal_node, _ast.Pass()],
            decorator_list=[],
            returns=None,
        )
        _ast.fix_missing_locations(inner_fn)
        module = _ast.Module(body=[inner_fn], type_ignores=[])
        _ast.fix_missing_locations(module)
        violations = check_disallowed_ast_constructs(module)
        assert any("Nonlocal" in v for v in violations), (
            f"Expected Nonlocal violation; got: {violations}"
        )

    def test_rejects_delete(self):
        p = _make_candidate("""\
x = 1
del x
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_named_expr(self):
        # Walrus operator (:=) must be rejected.
        p = _make_candidate("""\
if (x := request.path):
    pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_assert_statement(self):
        # assert can raise AssertionError instead of returning DetectionResult,
        # and is silently stripped under python -O. Structural rejection is required.
        p = _make_candidate("""\
assert request.path
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_assert_false(self):
        p = _make_candidate("""\
assert False
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_async_for(self):
        # async for inside a synchronous function is structurally rejected by
        # policy before it can reach the subprocess compile/import path.
        p = _make_candidate("""\
async for item in request.query.items():
    pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="match/case requires Python 3.10+")
    def test_rejects_match_statement_if_supported(self):
        p = _make_candidate("""\
match request.path:
    case "/":
        pass
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_rejected(p, "disallowed AST construct")

    def test_rejects_duplicate_top_level_inspect_request(self):
        # Two top-level inspect_request definitions: allowed_id becomes None,
        # so both FunctionDef nodes are flagged.
        source = (
            "from core.types import Request, DetectionResult\n\n"
            "def inspect_request(request: Request) -> DetectionResult:\n"
            "    # === MUTATION_START ===\n"
            "    return DetectionResult(False, 'ok', 0.0, ())\n"
            "    # === MUTATION_END ===\n\n"
            "def inspect_request(request: Request) -> DetectionResult:\n"
            "    return DetectionResult(False, 'ok2', 0.0, ())\n"
        )
        p = _write_raw_candidate(source)
        _assert_rejected(p)

    def test_rejects_top_level_helper_function(self):
        # A top-level helper function alongside inspect_request must be rejected.
        source = (
            "from core.types import Request, DetectionResult\n\n"
            "def helper():\n"
            "    return 'x'\n\n"
            "def inspect_request(request: Request) -> DetectionResult:\n"
            "    # === MUTATION_START ===\n"
            "    return DetectionResult(False, 'ok', 0.0, ())\n"
            "    # === MUTATION_END ===\n"
        )
        p = _write_raw_candidate(source)
        _assert_rejected(p, "disallowed AST construct")

    # ------------------------------------------------------------------
    # Acceptance tests
    # ------------------------------------------------------------------

    def test_accepts_baseline_detector_after_structural_guard(self):
        """Existing baseline core/detector.py must still pass after the new guard."""
        _PROJECT_ROOT = Path(__file__).parent.parent
        baseline = _PROJECT_ROOT / "core" / "detector.py"
        _assert_accepted(baseline)

    def test_accepts_simple_neutralized_indicator_detector(self):
        """A simple detector using only neutralized symbolic indicators must pass."""
        p = _make_candidate("""\
surface = request.path.lower() + " " + request.body.lower()
indicators = [
    "path_traversal_indicator",
    "sqli_indicator",
    "script_injection_indicator",
]
for token in indicators:
    if token in surface:
        return DetectionResult(blocked=True, reason=f"matched {token}", confidence=0.8, matched_signals=(token,))
return DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)

    def test_accepts_baseline_like_join_query_headers(self):
        """Baseline-like join over query.items() and headers.items() must be accepted."""
        p = _make_candidate("""\
q = " ".join(f"{k}={v}" for k, v in request.query.items()).lower()
h = " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower()
surface = request.path.lower() + " " + q + " " + h
if "path_traversal_indicator" in surface:
    return DetectionResult(blocked=True, reason="traversal", confidence=0.8, matched_signals=("path_traversal_indicator",))
return DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())
""")
        _assert_accepted(p)
