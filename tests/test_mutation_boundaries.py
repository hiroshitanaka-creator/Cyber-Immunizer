"""tests/test_mutation_boundaries.py — Verify mutation boundary enforcement."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

import scripts.apply_mutation as _am
from scripts.apply_mutation import apply_mutation, _resolve_safe_output_path

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


def _read_region(source: str) -> str:
    """Extract everything between mutation markers."""
    s = source.find(_MUTATION_START)
    e = source.find(_MUTATION_END)
    return source[s + len(_MUTATION_START) : e]


class TestBoundaryReplacement:
    def test_only_mutation_region_changes(self, tmp_path):
        """Lines outside the mutation markers must remain byte-for-byte identical."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        replacement = "    return DetectionResult(blocked=False, reason='test', confidence=0.0, matched_signals=())\n"
        patch_path = _make_patch(replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
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

    def test_apply_mutation_modifies_only_marked_region(self, tmp_path):
        """After apply_mutation, only the mutation region changes."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        # replacement_code is the verbatim function body — must use 4-space indent
        # so the generated file is syntactically valid inside inspect_request().
        replacement = textwrap.dedent("""\
            return DetectionResult(blocked=False, reason="mutated", confidence=0.5, matched_signals=())
        """)
        # Add 4-space indent so replacement sits correctly inside the function
        replacement = textwrap.indent(replacement.strip(), "    ") + "\n"
        patch_path = _make_patch(replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
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

    def test_mutation_markers_remain_present(self, tmp_path):
        """Both markers must exist in the output file."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        replacement = "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        patch_path = _make_patch(replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert result["success"], f"Expected success: {result}"

        cand_source = out_path.read_text(encoding="utf-8")
        assert _MUTATION_START in cand_source, "MUTATION_START marker missing"
        assert _MUTATION_END in cand_source, "MUTATION_END marker missing"

    def test_replacement_code_in_region(self, tmp_path):
        """The replacement code must appear between the markers."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        magic = "# MAGIC_REPLACEMENT_TOKEN_12345"
        replacement = f"{magic}\n    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        patch_path = _make_patch(replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert result["success"], f"Expected success: {result}"

        cand_source = out_path.read_text(encoding="utf-8")
        region = _read_region(cand_source)
        assert magic in region, "Replacement code not found in mutation region"


class TestRejectedPatches:
    def test_rejects_replacement_containing_mutation_start(self, tmp_path):
        """Replacement code containing MUTATION_START must be rejected."""
        bad_replacement = f"# {_MUTATION_START}\nreturn DetectionResult(False,'',0.0,())\n"
        patch_path = _make_patch(bad_replacement)
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert not result["success"], (
            "Replacement containing MUTATION_START should be rejected"
        )

    def test_rejects_replacement_containing_mutation_end(self, tmp_path):
        """Replacement code containing MUTATION_END must be rejected."""
        bad_replacement = f"# {_MUTATION_END}\nreturn DetectionResult(False,'',0.0,())\n"
        patch_path = _make_patch(bad_replacement)
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert not result["success"], (
            "Replacement containing MUTATION_END should be rejected"
        )

    def test_rejects_missing_required_fields(self, tmp_path):
        """Patch missing 'replacement_code' must be rejected."""
        patch_path = _make_patch("", mutation_rationale="ok")
        # Manually remove replacement_code from the written JSON
        patch_data = json.loads(patch_path.read_text())
        del patch_data["replacement_code"]
        patch_path.write_text(json.dumps(patch_data))
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert not result["success"]

    def test_rejects_unsafe_candidate_after_apply(self, tmp_path):
        """If replacement_code contains eval(), candidate must be rejected."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        bad_replacement = textwrap.dedent("""\
            eval("1+1")
            return DetectionResult(False, "bad", 0.0, ())
        """)
        patch_path = _make_patch(bad_replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)
        assert not result["success"], "eval() in replacement should be rejected"
        # The unsafe candidate file should not exist
        assert not out_path.exists(), "Invalid candidate file must be removed"

    def test_rejects_nonexistent_patch(self, tmp_path):
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        result = apply_mutation(
            Path("/nonexistent/patch.json"), _BASE_DETECTOR, out_path, output_root=output_root
        )
        assert not result["success"]

    def test_rejects_nonexistent_base(self, tmp_path):
        patch_path = _make_patch("return DetectionResult(False,'',0.0,())\n")
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        result = apply_mutation(
            patch_path, Path("/nonexistent/detector.py"), out_path, output_root=output_root
        )
        assert not result["success"]

    def test_rejects_base_with_duplicate_mutation_start(self, tmp_path):
        """Base file with two MUTATION_START markers must be rejected."""
        base_source = _BASE_DETECTOR.read_text(encoding="utf-8")
        # Insert a second MUTATION_START marker at the very top
        doubled = _MUTATION_START + "\n" + base_source
        base_doubled = tmp_path / "doubled_start.py"
        base_doubled.write_text(doubled, encoding="utf-8")

        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch("    return DetectionResult(False, 'ok', 0.0, ())\n")

        result = apply_mutation(patch_path, base_doubled, out_path, output_root=output_root)
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

        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch("    return DetectionResult(False, 'ok', 0.0, ())\n")

        result = apply_mutation(patch_path, base_doubled, out_path, output_root=output_root)
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
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "should_not_be_created.py"

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

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
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(
            "    if '../' in request.path:\n"
            "        return DetectionResult(blocked=True, reason='traversal', confidence=0.9, matched_signals=('../',))\n"
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

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
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "should_not_exist.py"
        body = "    x = " + "-" * 9000 + "1\n    return DetectionResult(False, '', 0.0, ())\n"
        patch_path = _make_patch(body)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

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
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(
            "    if 'xss' in request.path.lower():\n"
            "        return DetectionResult(blocked=True, reason='xss', confidence=0.9, matched_signals=('xss',))\n"
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert result["success"], f"Normal replacement must succeed: {result}"
        assert out_path.exists(), "out_path must be created for a valid candidate"


# ---------------------------------------------------------------------------
# Safe output path tests (PR #43)
# ---------------------------------------------------------------------------

class TestSafeOutputPath:
    """Verify that the safe output path guard prevents unsafe writes."""

    _GOOD_REPLACEMENT = (
        "    if '../' in request.path:\n"
        "        return DetectionResult(blocked=True, reason='traversal', confidence=0.9, matched_signals=('../',))\n"
        "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
    )

    def test_safe_output_path_accepted(self, tmp_path):
        """Candidate under output_root must succeed."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert result["success"], f"Safe output path should succeed: {result}"
        assert out_path.exists(), "Candidate file must be created"
        assert Path(result["candidate_path"]).resolve().is_relative_to(output_root.resolve())

    def test_relative_cyber_immunizer_path_accepted(self, tmp_path):
        """Helper must accept a path already under output_root."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate_detector.py"
        resolved, err = _resolve_safe_output_path(out_path, output_root)
        assert err == "", f"Expected no error, got: {err}"
        assert resolved is not None

    def test_absolute_path_outside_output_root_rejected(self, tmp_path):
        """Absolute path outside output_root must be rejected without creating the file."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = tmp_path / "outside.py"  # sibling of output_root, not inside it
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Path outside output_root must be rejected"
        assert not out_path.exists(), "Rejected path must not be created"
        err_lower = result["error"].lower()
        assert "unsafe output path" in err_lower or "outside allowed output root" in err_lower, (
            f"Error must mention unsafe path, got: {result['error']!r}"
        )

    def test_path_traversal_rejected(self, tmp_path):
        """../ traversal escaping output_root must be rejected."""
        output_root = tmp_path / ".cyber_immunizer"
        # This resolves to tmp_path / "escape.py" — outside output_root
        out_path = output_root / ".." / "escape.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Path traversal must be rejected"
        assert not (tmp_path / "escape.py").exists(), "Escaped file must not be created"

    def test_repo_important_path_rejected(self, tmp_path):
        """Output path pointing at a real repo file must be rejected (helper level)."""
        output_root = tmp_path / ".cyber_immunizer"
        # core/detector.py is outside output_root
        important_path = _PROJECT_ROOT / "core" / "detector.py"
        resolved, err = _resolve_safe_output_path(important_path, output_root)
        assert resolved is None, "Repo important file must be rejected by helper"
        assert err != "", "Error message must be non-empty"
        # Verify the real file was NOT touched
        assert important_path.exists(), "core/detector.py must still exist"

    def test_symlink_escape_rejected(self, tmp_path):
        """Symlink pointing outside output_root must be rejected."""
        try:
            output_root = tmp_path / ".cyber_immunizer"
            output_root.mkdir(parents=True, exist_ok=True)
            outside_dir = tmp_path / "outside"
            outside_dir.mkdir()
            link = output_root / "link"
            link.symlink_to(outside_dir)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not supported on this platform")

        out_path = link / "candidate.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Symlink escape must be rejected"
        assert not (outside_dir / "candidate.py").exists(), (
            "File must not be created in symlink-escaped directory"
        )

    def test_unsafe_path_does_not_write_any_file(self, tmp_path):
        """No file must be created when output path is unsafe."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = tmp_path / "evil.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"]
        assert not out_path.exists(), "No file must be created for unsafe path"
        # Also check nothing leaked into the sibling location
        assert list(tmp_path.glob("*.py")) == [], "No .py files should appear under tmp_path root"

    def test_invalid_candidate_cleanup_still_works(self, tmp_path):
        """Candidate written to safe path must be removed after AST validation failure."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        bad_replacement = textwrap.dedent("""\
            eval("evil")
            return DetectionResult(False, "bad", 0.0, ())
        """)
        patch_path = _make_patch(bad_replacement)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "eval() must be rejected"
        assert not out_path.exists(), "Cleaned-up candidate must not exist"

    def test_cli_json_unsafe_out_path(self, tmp_path, capsys):
        """CLI with --json and unsafe --out must exit 1 with structured JSON failure."""
        from scripts.apply_mutation import main

        patch_path = _make_patch(self._GOOD_REPLACEMENT)
        unsafe_out = str(tmp_path / "outside.py")

        # We need a patch file and a base file; use real base detector.
        exit_code = main([
            "--patch", str(patch_path),
            "--base", str(_BASE_DETECTOR),
            "--out", unsafe_out,
            "--json",
        ])

        assert exit_code == 1, "CLI must exit 1 for unsafe output path"

        captured = capsys.readouterr()
        try:
            data = json.loads(captured.out)
        except json.JSONDecodeError:
            pytest.fail(f"CLI --json output is not valid JSON: {captured.out!r}")

        assert data["success"] is False, "JSON result must have success=false"
        assert "error" in data and data["error"], "JSON result must contain an error"
        err_lower = data["error"].lower()
        assert "unsafe output path" in err_lower or "outside allowed output root" in err_lower, (
            f"Error must describe unsafe path, got: {data['error']!r}"
        )
        # No traceback in stdout
        assert "Traceback" not in captured.out

    def test_normal_replacement_still_applies_safe(self, tmp_path):
        """Existing happy-path still works with explicit safe output_root."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert result["success"], f"Normal replacement must succeed: {result}"
        assert out_path.exists()


class TestResolveSafeOutputPathHelper:
    """Unit tests for the _resolve_safe_output_path helper directly."""

    def test_file_under_root_accepted(self, tmp_path):
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "sub" / "candidate.py"
        resolved, err = _resolve_safe_output_path(out_path, output_root)
        assert err == ""
        assert resolved is not None

    def test_non_py_extension_rejected(self, tmp_path):
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.sh"
        resolved, err = _resolve_safe_output_path(out_path, output_root)
        assert resolved is None
        assert "unsafe output path" in err.lower()

    def test_directory_target_rejected(self, tmp_path):
        output_root = tmp_path / ".cyber_immunizer"
        output_root.mkdir(parents=True, exist_ok=True)
        # Create a directory at the output path
        dir_path = output_root / "adir.py"
        dir_path.mkdir()
        resolved, err = _resolve_safe_output_path(dir_path, output_root)
        assert resolved is None
        assert "directory" in err.lower()

    def test_traversal_rejected(self, tmp_path):
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / ".." / "escape.py"
        resolved, err = _resolve_safe_output_path(out_path, output_root)
        assert resolved is None
        assert err != ""


class TestOutputRootSymlinkRejection:
    """output_root itself is a symlink — must be rejected before any write."""

    _GOOD_REPLACEMENT = (
        "    if '../' in request.path:\n"
        "        return DetectionResult(blocked=True, reason='traversal', confidence=0.9, matched_signals=('../',))\n"
        "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
    )

    def _try_symlink(self, link: Path, target: Path) -> bool:
        """Create symlink; return False and skip if platform doesn't support it."""
        try:
            link.symlink_to(target)
            return True
        except (OSError, NotImplementedError):
            return False

    def test_output_root_symlink_rejected(self, tmp_path):
        """output_root that is itself a symlink must be rejected fail-closed."""
        outside = tmp_path / "outside"
        outside.mkdir()
        output_root = tmp_path / ".cyber_immunizer"

        if not self._try_symlink(output_root, outside):
            pytest.skip("Symlink creation not supported on this platform")

        out_path = output_root / "candidate.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Symlinked output_root must be rejected"
        err_lower = result["error"].lower()
        assert "symlink" in err_lower, (
            f"Error must mention symlink, got: {result['error']!r}"
        )
        assert "output root" in err_lower, (
            f"Error must mention output root, got: {result['error']!r}"
        )
        assert not (outside / "candidate.py").exists(), (
            "Candidate must not be created in symlink target"
        )

    def test_output_root_symlink_to_repo_like_dir_cannot_write_important_file(self, tmp_path):
        """Symlinked output_root pointing to a repo-like dir cannot write core files."""
        fake_repo = tmp_path / "fake_repo"
        fake_repo.mkdir()
        output_root = tmp_path / ".cyber_immunizer"

        if not self._try_symlink(output_root, fake_repo):
            pytest.skip("Symlink creation not supported on this platform")

        # Attempt to write what would look like core/detector.py under fake_repo
        out_path = output_root / "core" / "detector.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Symlinked output_root must be rejected"
        # File must not appear under the fake_repo tree
        assert not (fake_repo / "core" / "detector.py").exists(), (
            "Important file must not be created in symlink-redirected directory"
        )
        # Real repo core/detector.py must be untouched
        assert _BASE_DETECTOR.exists(), "Real core/detector.py must be untouched"

    def test_real_output_root_directory_still_works(self, tmp_path):
        """A genuine (non-symlink) output_root directory must still be accepted."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert result["success"], f"Real directory output_root must succeed: {result}"
        assert out_path.exists(), "Candidate file must be created"

    def test_symlink_escape_under_real_root_still_rejected(self, tmp_path):
        """Symlink inside a real output_root that escapes the root is still caught."""
        output_root = tmp_path / ".cyber_immunizer"
        output_root.mkdir(parents=True, exist_ok=True)
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        link = output_root / "link"

        if not self._try_symlink(link, outside_dir):
            pytest.skip("Symlink creation not supported on this platform")

        out_path = link / "candidate.py"
        patch_path = _make_patch(self._GOOD_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Symlink escape inside root must be rejected"
        assert not (outside_dir / "candidate.py").exists(), (
            "File must not be created in symlink-escaped directory"
        )


# ---------------------------------------------------------------------------
# Atomic write tests (Phase 2.5 Task 005)
# ---------------------------------------------------------------------------


def _assert_no_atomic_temp_files(parent: Path, final_name: str) -> None:
    """Assert no same-directory temp files from _write_text_atomic remain."""
    leftovers = list(parent.glob(f".{final_name}.*.tmp.py"))
    assert leftovers == [], f"Leftover atomic temp files: {leftovers}"


class TestApplyMutationAtomicWrite:
    """Verify that apply_mutation writes candidates atomically via temp-validate-replace."""

    _VALID_REPLACEMENT = (
        "    if '../' in request.path:\n"
        "        return DetectionResult(blocked=True, reason='traversal', confidence=0.9, matched_signals=('../',))\n"
        "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
    )
    _VALID_REPLACEMENT_ALT = (
        "    if 'xss' in request.path.lower():\n"
        "        return DetectionResult(blocked=True, reason='xss', confidence=0.9, matched_signals=('xss',))\n"
        "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
    )
    _INVALID_REPLACEMENT = (
        "    eval('1+1')\n"
        "    return DetectionResult(False, 'bad', 0.0, ())\n"
    )

    def test_valid_candidate_replaces_final_path(self, tmp_path):
        """Valid replacement must produce a file at the final path with no temp leftovers."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(self._VALID_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert result["success"], f"Expected success: {result}"
        assert out_path.exists(), "Final candidate file must exist after success"
        _assert_no_atomic_temp_files(output_root, "candidate.py")

    def test_invalid_candidate_does_not_create_final_path(self, tmp_path):
        """Invalid replacement must not create the final output path; no temp leftovers."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"
        patch_path = _make_patch(self._INVALID_REPLACEMENT)

        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "eval() replacement must be rejected"
        assert not out_path.exists(), "Final path must not exist after invalid replacement"
        _assert_no_atomic_temp_files(output_root, "candidate.py")

    def test_existing_final_file_survives_invalid_replacement(self, tmp_path):
        """Existing valid final file must be unchanged after a failed invalid replacement.

        This is the key atomicity regression test: direct write_text() would
        destroy the previous final file; temp-validate-replace preserves it.
        """
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        # First: apply a valid replacement to create the final file.
        patch1 = _make_patch(self._VALID_REPLACEMENT)
        result1 = apply_mutation(patch1, _BASE_DETECTOR, out_path, output_root=output_root)
        assert result1["success"], f"First apply_mutation must succeed: {result1}"
        assert out_path.exists()
        original_content = out_path.read_text(encoding="utf-8")

        # Second: attempt an invalid replacement to the same out_path.
        patch2 = _make_patch(self._INVALID_REPLACEMENT)
        result2 = apply_mutation(patch2, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result2["success"], "Invalid replacement must fail"
        assert out_path.exists(), "Final file must still exist after failed replacement"
        assert out_path.read_text(encoding="utf-8") == original_content, (
            "Final file content must be unchanged after invalid replacement attempt"
        )
        _assert_no_atomic_temp_files(output_root, "candidate.py")

    def test_os_replace_failure_cleans_temp_and_preserves_existing_final(
        self, tmp_path, monkeypatch
    ):
        """os.replace failure must clean up the temp file and leave existing final intact."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        # Create a valid existing final file.
        patch1 = _make_patch(self._VALID_REPLACEMENT)
        result1 = apply_mutation(patch1, _BASE_DETECTOR, out_path, output_root=output_root)
        assert result1["success"], f"Setup apply_mutation must succeed: {result1}"
        old_content = out_path.read_text(encoding="utf-8")

        # Monkeypatch os.replace in the apply_mutation module to raise OSError.
        def _fail_replace(*args, **kwargs):
            raise OSError("simulated replace failure")

        monkeypatch.setattr(_am.os, "replace", _fail_replace)

        patch2 = _make_patch(self._VALID_REPLACEMENT_ALT)
        result2 = apply_mutation(patch2, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result2["success"], "os.replace failure must cause apply_mutation to fail"
        assert out_path.read_text(encoding="utf-8") == old_content, (
            "Existing final file must be unchanged after os.replace failure"
        )
        _assert_no_atomic_temp_files(output_root, "candidate.py")
        err_lower = result2["error"].lower()
        assert any(kw in err_lower for kw in ("replace", "write", "atomic")), (
            f"Error must mention replace/write/atomic, got: {result2['error']!r}"
        )

    def test_temp_write_failure_returns_error_without_final_file(
        self, tmp_path, monkeypatch
    ):
        """A write failure in _write_text_atomic must leave no final file and return failure."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        # Monkeypatch _write_text_atomic to simulate an OSError on write.
        monkeypatch.setattr(
            _am,
            "_write_text_atomic",
            lambda path, content: (None, "failed to write temp candidate: simulated OSError"),
        )

        patch_path = _make_patch(self._VALID_REPLACEMENT)
        result = apply_mutation(patch_path, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result["success"], "Write failure must cause apply_mutation to fail"
        assert result["candidate_path"] is None, "candidate_path must be None on write failure"
        assert not out_path.exists(), "Final file must not exist when write failed"

    def test_validation_exception_cleans_temp_and_preserves_final(
        self, tmp_path, monkeypatch
    ):
        """An exception from validate() must clean temp file and leave existing final intact."""
        output_root = tmp_path / ".cyber_immunizer"
        out_path = output_root / "candidate.py"

        # Create a valid existing final file.
        patch1 = _make_patch(self._VALID_REPLACEMENT)
        result1 = apply_mutation(patch1, _BASE_DETECTOR, out_path, output_root=output_root)
        assert result1["success"], f"Setup apply_mutation must succeed: {result1}"
        old_content = out_path.read_text(encoding="utf-8")

        # Monkeypatch validate to raise an unexpected exception.
        def _raise_validate(path):
            raise ValueError("simulated validation failure")

        monkeypatch.setattr(_am, "validate", _raise_validate)

        patch2 = _make_patch(self._VALID_REPLACEMENT_ALT)
        result2 = apply_mutation(patch2, _BASE_DETECTOR, out_path, output_root=output_root)

        assert not result2["success"], "Validation exception must cause apply_mutation to fail"
        assert out_path.exists(), "Existing final file must still exist after validation exception"
        assert out_path.read_text(encoding="utf-8") == old_content, (
            "Existing final file content must be unchanged after validation exception"
        )
        _assert_no_atomic_temp_files(output_root, "candidate.py")
