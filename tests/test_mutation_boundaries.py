"""tests/test_mutation_boundaries.py — Verify mutation boundary enforcement."""
from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from scripts.apply_mutation import apply_mutation

_PROJECT_ROOT = Path(__file__).parent.parent
_BASE_DETECTOR = _PROJECT_ROOT / "core" / "detector.py"

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="


def _make_patch(replacement_code: str, **overrides) -> Path:
    patch = {
        "mutation_rationale": "test mutation",
        "target_threats": ["THREAT-TEST-001"],
        "expected_improvement": "test improvement",
        "risk": "test risk",
        "replacement_code": replacement_code,
        **overrides,
    }
    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    json.dump(patch, tmp)
    tmp.flush()
    return Path(tmp.name)


def _make_out_path() -> Path:
    tmp = tempfile.mktemp(suffix=".py")
    return Path(tmp)


def _read_region(source: str) -> str:
    """Extract everything between mutation markers."""
    s = source.find(_MUTATION_START)
    e = source.find(_MUTATION_END)
    return source[s + len(_MUTATION_START) : e]


class TestBoundaryReplacement:
    def test_only_mutation_region_changes(self):
        """Lines outside the mutation markers must remain byte-for-byte identical."""
        replacement = "    return DetectionResult(False, 'test', 0.0, ())\n"
        patch_path = _make_patch(replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert result["success"], f"apply_mutation failed: {result}"

        base_source = _BASE_DETECTOR.read_text(encoding="utf-8")
        cand_source = out_path.read_text(encoding="utf-8")

        # Prefix (everything before MUTATION_START) must be identical
        base_before = base_source[: base_source.find(_MUTATION_START)]
        cand_before = cand_source[: cand_source.find(_MUTATION_START)]
        assert base_before == cand_before, (
            "Text before MUTATION_START changed unexpectedly"
        )

        # Suffix (everything from MUTATION_END onward) must be identical
        base_after = base_source[base_source.find(_MUTATION_END):]
        cand_after = cand_source[cand_source.find(_MUTATION_END):]
        assert base_after == cand_after, (
            "Text after MUTATION_END changed unexpectedly"
        )

    def test_apply_mutation_modifies_only_marked_region(self):
        """After apply_mutation, only the mutation region changes."""
        # replacement_code is the verbatim function body — must use 4-space indent
        # so the generated file is syntactically valid inside inspect_request().
        replacement = textwrap.dedent("""\
            return DetectionResult(False, "mutated", 0.5, ())
        """)
        # Add 4-space indent so replacement sits correctly inside the function
        replacement = textwrap.indent(replacement.strip(), "    ") + "\n"
        patch_path = _make_patch(replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert result["success"], f"apply_mutation failed: {result}"

        base_source = _BASE_DETECTOR.read_text(encoding="utf-8")
        cand_source = out_path.read_text(encoding="utf-8")

        # Everything before MUTATION_START must be identical
        base_before = base_source[: base_source.find(_MUTATION_START)]
        cand_before = cand_source[: cand_source.find(_MUTATION_START)]
        assert base_before == cand_before, (
            "Text before MUTATION_START changed unexpectedly"
        )

        # Everything after MUTATION_END must be identical
        base_after = base_source[base_source.find(_MUTATION_END):]
        cand_after = cand_source[cand_source.find(_MUTATION_END):]
        assert base_after == cand_after, (
            "Text after MUTATION_END changed unexpectedly"
        )

    def test_mutation_markers_remain_present(self):
        """Both markers must exist in the output file."""
        replacement = "    return DetectionResult(False, 'ok', 0.0, ())\n"
        patch_path = _make_patch(replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert result["success"], f"Expected success: {result}"

        cand_source = out_path.read_text(encoding="utf-8")
        assert _MUTATION_START in cand_source, "MUTATION_START marker missing"
        assert _MUTATION_END in cand_source, "MUTATION_END marker missing"

    def test_replacement_code_in_region(self):
        """The replacement code must appear between the markers."""
        magic = "# MAGIC_REPLACEMENT_TOKEN_12345"
        replacement = f"{magic}\n    return DetectionResult(False, 'ok', 0.0, ())\n"
        patch_path = _make_patch(replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert result["success"], f"Expected success: {result}"

        cand_source = out_path.read_text(encoding="utf-8")
        region = _read_region(cand_source)
        assert magic in region, "Replacement code not found in mutation region"


class TestRejectedPatches:
    def test_rejects_replacement_containing_mutation_start(self):
        """Replacement code containing MUTATION_START must be rejected."""
        bad_replacement = f"# {_MUTATION_START}\nreturn DetectionResult(False,'',0.0,())\n"
        patch_path = _make_patch(bad_replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert not result["success"], (
            "Replacement containing MUTATION_START should be rejected"
        )

    def test_rejects_replacement_containing_mutation_end(self):
        """Replacement code containing MUTATION_END must be rejected."""
        bad_replacement = f"# {_MUTATION_END}\nreturn DetectionResult(False,'',0.0,())\n"
        patch_path = _make_patch(bad_replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert not result["success"], (
            "Replacement containing MUTATION_END should be rejected"
        )

    def test_rejects_missing_required_fields(self):
        """Patch missing 'replacement_code' must be rejected."""
        patch_path = _make_patch("", mutation_rationale="ok")
        # Manually remove replacement_code from the written JSON
        patch_data = json.loads(patch_path.read_text())
        del patch_data["replacement_code"]
        patch_path.write_text(json.dumps(patch_data))
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert not result["success"]

    def test_rejects_unsafe_candidate_after_apply(self):
        """If replacement_code contains eval(), candidate must be rejected."""
        bad_replacement = textwrap.dedent("""\
            eval("1+1")
            return DetectionResult(False, "bad", 0.0, ())
        """)
        patch_path = _make_patch(bad_replacement)
        out_path = _make_out_path()

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)
        assert not result["success"], "eval() in replacement should be rejected"
        # The unsafe candidate file should not exist
        assert not out_path.exists(), "Invalid candidate file must be removed"

    def test_rejects_nonexistent_patch(self):
        out_path = _make_out_path()
        result = apply_mutation(Path("/nonexistent/patch.json"), _BASE_DETECTOR, out_path)
        assert not result["success"]

    def test_rejects_nonexistent_base(self):
        patch_path = _make_patch("return DetectionResult(False,'',0.0,())\n")
        out_path = _make_out_path()
        result = apply_mutation(patch_path, Path("/nonexistent/detector.py"), out_path)
        assert not result["success"]

    def test_rejects_base_with_duplicate_mutation_start(self, tmp_path):
        """Base file with two MUTATION_START markers must be rejected."""
        base_source = _BASE_DETECTOR.read_text(encoding="utf-8")
        # Insert a second MUTATION_START marker at the very top
        doubled = _MUTATION_START + "\n" + base_source
        base_doubled = tmp_path / "doubled_start.py"
        base_doubled.write_text(doubled, encoding="utf-8")

        patch_path = _make_patch("    return DetectionResult(False, 'ok', 0.0, ())\n")
        out_path = _make_out_path()

        result = apply_mutation(patch_path, base_doubled, out_path)
        assert not result["success"], (
            "Base with duplicate MUTATION_START should be rejected"
        )
        assert "double" in result["error"].lower() or "2" in result["error"], (
            f"Error should mention duplicate marker, got: {result['error']!r}"
        )

    def test_rejects_base_with_duplicate_mutation_end(self, tmp_path):
        """Base file with two MUTATION_END markers must be rejected."""
        base_source = _BASE_DETECTOR.read_text(encoding="utf-8")
        doubled = base_source + "\n" + _MUTATION_END + "\n"
        base_doubled = tmp_path / "doubled_end.py"
        base_doubled.write_text(doubled, encoding="utf-8")

        patch_path = _make_patch("    return DetectionResult(False, 'ok', 0.0, ())\n")
        out_path = _make_out_path()

        result = apply_mutation(patch_path, base_doubled, out_path)
        assert not result["success"], (
            "Base with duplicate MUTATION_END should be rejected"
        )
        assert "double" in result["error"].lower() or "2" in result["error"], (
            f"Error should mention duplicate marker, got: {result['error']!r}"
        )


class TestApplyMutationSourceSizeGuard:
    def test_rejects_oversized_replacement_before_file_write(self, tmp_path):
        """Oversized replacement_code must be rejected before out_path is created."""
        from core.policy import MAX_POLICY_SOURCE_CHARS

        # Build a replacement_code large enough to push projected candidate over the limit
        giant_replacement = (
            "    # " + "x" * 100 + "\n"
        ) * (MAX_POLICY_SOURCE_CHARS // 100 + 10)
        giant_replacement += "    return DetectionResult(False, '', 0.0, ())\n"

        patch_path = _make_patch(giant_replacement)
        out_path = tmp_path / "should_not_be_created.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)

        assert not result["success"], (
            "apply_mutation must fail when replacement_code makes candidate too large"
        )
        error_lower = result["error"].lower()
        assert (
            "max_policy_source_chars" in error_lower
            or "source too large" in error_lower
            or "candidate source" in error_lower
        ), f"Error must mention size limit, got: {result['error']!r}"
        assert not out_path.exists(), (
            "out_path must NOT be created when projected candidate exceeds size limit"
        )

    def test_normal_replacement_still_applies(self, tmp_path):
        """A normal-sized replacement_code must still produce a valid candidate."""
        patch_path = _make_patch(
            "    if '../' in request.path:\n"
            "        return DetectionResult(True, 'traversal', 0.9, ('../',))\n"
            "    return DetectionResult(False, 'ok', 0.0, ())\n"
        )
        out_path = tmp_path / "candidate.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)

        assert result["success"], (
            f"Normal replacement should succeed, got: {result}"
        )
        assert out_path.exists(), "out_path must be created for a valid candidate"


class TestApplyMutationParserStackOverflow:
    """Parser-stack-busting replacement_code must be handled fail-closed by
    apply_mutation() without writing out_path."""

    def test_rejects_parser_stack_bomb_before_or_at_validate(self, tmp_path):
        """apply_mutation() must fail safely on parser-stack-busting replacement."""
        # ~9000 unary minuses trigger MemoryError in the CPython parser.
        # The source stays within MAX_POLICY_SOURCE_CHARS so it's not caught
        # by the pre-write size guard, but validate() must still handle it.
        body = "    x = " + "-" * 9000 + "1\n    return DetectionResult(False, '', 0.0, ())\n"
        patch_path = _make_patch(body)
        out_path = tmp_path / "should_not_exist.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)

        assert not result["success"], (
            "apply_mutation must fail on parser-stack-busting replacement_code"
        )
        assert not out_path.exists(), (
            "out_path must NOT persist after a parser-failure rejection"
        )
        combined = (
            " ".join(result.get("violations", []))
            + " " + result.get("error", "")
        ).lower()
        assert any(
            kw in combined
            for kw in ("parser", "memoryerror", "too complex", "syntaxerror", "recursionerror", "validation")
        ), f"Failure must describe parser issue, got: result={result}"

    def test_normal_replacement_unaffected(self, tmp_path):
        """Normal replacement_code is not affected by the parser exception guard."""
        patch_path = _make_patch(
            "    if 'xss' in request.path.lower():\n"
            "        return DetectionResult(True, 'xss', 0.9, ('xss',))\n"
            "    return DetectionResult(False, 'ok', 0.0, ())\n"
        )
        out_path = tmp_path / "candidate.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path)

        assert result["success"], f"Normal replacement must succeed: {result}"
        assert out_path.exists(), "out_path must be created for a valid candidate"
