"""tests/test_ast_policy.py — Verify AST policy enforcement."""
from __future__ import annotations

import textwrap
import tempfile
from pathlib import Path

import pytest

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
