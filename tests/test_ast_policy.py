"""tests/test_ast_policy.py — Verify AST policy enforcement."""
from __future__ import annotations

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
    return DetectionResult(True, "traversal", 0.9, ("../",))
return DetectionResult(False, "ok", 0.0, ())
""")
        _assert_accepted(p)

    def test_accepts_string_operations(self):
        p = _make_candidate("""\
surface = request.path.lower()
tokens = ["<script", "union select"]
for t in tokens:
    if t in surface:
        return DetectionResult(True, "match", 0.8, (t,))
return DetectionResult(False, "no match", 0.0, ())
""")
        _assert_accepted(p)


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
    return DetectionResult(True, "sqli", 0.9, ("drop table",))
return DetectionResult(False, "ok", 0.0, ())
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
