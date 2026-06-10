"""tests/test_validate_audit_evidence.py — Tests for the audit-evidence ledger validator.

Covers parsing of ```audit-evidence``` blocks, quote/count verification against a
synthetic repository, diff-coverage rules, and the CLI entry point.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_audit_evidence import (  # noqa: E402
    EvidenceBlock,
    FileDiff,
    main,
    parse_line_range,
    parse_name_status,
    parse_report,
    parse_unified_diff_ranges,
    validate_report,
    verify_callsite,
    verify_diff_coverage,
    verify_negative,
    verify_read_manifest,
    verify_spec_recitation,
)

# ---------------------------------------------------------------------------
# Fixtures: a synthetic repository (no git required — validator falls back to
# a filesystem walk when `git ls-files` fails outside a repo)
# ---------------------------------------------------------------------------

_DETECTOR_SOURCE = """\
import re


def normalize(payload):
    return payload.lower()


def detect(payload):
    normalized = normalize(payload)
    return "attack" in normalized
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "detector.py").write_text(_DETECTOR_SOURCE, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text(
        "# Spec\n\n## Detection rules\n\nLowercase before matching.\n",
        encoding="utf-8",
    )
    return tmp_path


def _block(type_: str, fields: dict, body: list[str]) -> EvidenceBlock:
    return EvidenceBlock(type=type_, fields=fields, body=body, report_line=1)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParsing:
    def test_parse_report_extracts_blocks(self) -> None:
        text = (
            "intro\n"
            "```audit-evidence\n"
            "TYPE: NEGATIVE\n"
            "PATTERN: os.system\n"
            "COUNT: 0\n"
            "NOTE: no shell execution path exists\n"
            "---\n"
            "```\n"
        )
        blocks, errors = parse_report(text)
        assert errors == []
        assert len(blocks) == 1
        assert blocks[0].type == "NEGATIVE"
        assert blocks[0].fields["PATTERN"] == "os.system"

    def test_parse_report_rejects_missing_separator(self) -> None:
        text = "```audit-evidence\nTYPE: READ_MANIFEST\n```\n"
        blocks, errors = parse_report(text)
        assert blocks == []
        assert any("separator" in e for e in errors)

    def test_parse_report_rejects_unknown_type(self) -> None:
        text = "```audit-evidence\nTYPE: BOGUS\n---\n```\n"
        blocks, errors = parse_report(text)
        assert blocks == []
        assert any("unknown or missing TYPE" in e for e in errors)

    def test_parse_report_rejects_missing_required_field(self) -> None:
        text = "```audit-evidence\nTYPE: CALLSITE\nSYMBOL: detect\n---\n```\n"
        blocks, errors = parse_report(text)
        assert blocks == []
        assert any("COUNT" in e for e in errors)

    def test_parse_report_rejects_unclosed_block(self) -> None:
        text = "```audit-evidence\nTYPE: READ_MANIFEST\n---\nFULL: a.py\n"
        _, errors = parse_report(text)
        assert any("not closed" in e for e in errors)

    def test_parse_line_range(self) -> None:
        assert parse_line_range("40") == (40, 40)
        assert parse_line_range("40-44") == (40, 44)
        assert parse_line_range("44-40") is None
        assert parse_line_range("0") is None
        assert parse_line_range("a-b") is None

    def test_parse_name_status(self) -> None:
        text = "M\tcore/detector.py\nA\tdocs/NEW.md\nR100\told.py\tnew.py\n"
        assert parse_name_status(text) == {
            "core/detector.py": "M",
            "docs/NEW.md": "A",
            "new.py": "R",
        }

    def test_parse_unified_diff_ranges(self) -> None:
        diff = (
            "diff --git a/core/detector.py b/core/detector.py\n"
            "--- a/core/detector.py\n"
            "+++ b/core/detector.py\n"
            "@@ -8,1 +8,2 @@ def detect\n"
            "+    extra\n"
            "+    lines\n"
            "@@ -20,3 +22,0 @@ tail\n"
        )
        ranges = parse_unified_diff_ranges(diff)
        assert ranges["core/detector.py"][0] == (8, 9)
        # pure deletion is recorded as a zero-length position
        assert ranges["core/detector.py"][1] == (22, 22)


# ---------------------------------------------------------------------------
# SPEC_RECITATION
# ---------------------------------------------------------------------------


class TestSpecRecitation:
    def _good_block(self) -> EvidenceBlock:
        return _block(
            "SPEC_RECITATION",
            {
                "FILE": "core/detector.py",
                "LINES": "8-10",
                "SYMBOL": "detect",
                "SPEC": "detect() lowercases the payload then substring-matches 'attack'.",
            },
            [
                "def detect(payload):",
                "    normalized = normalize(payload)",
                '    return "attack" in normalized',
            ],
        )

    def test_valid_recitation_passes(self, repo: Path) -> None:
        assert verify_spec_recitation(self._good_block(), repo) == []

    def test_quote_mismatch_fails(self, repo: Path) -> None:
        block = self._good_block()
        block.body[1] = "    normalized = payload.upper()"
        errors = verify_spec_recitation(block, repo)
        assert any("does not match" in e for e in errors)

    def test_wrong_line_count_fails(self, repo: Path) -> None:
        block = self._good_block()
        block.body = block.body[:2]
        errors = verify_spec_recitation(block, repo)
        assert any("covers" in e for e in errors)

    def test_missing_file_fails(self, repo: Path) -> None:
        block = self._good_block()
        block.fields["FILE"] = "core/nonexistent.py"
        errors = verify_spec_recitation(block, repo)
        assert any("does not exist" in e for e in errors)

    def test_out_of_range_lines_fail(self, repo: Path) -> None:
        block = self._good_block()
        block.fields["LINES"] = "8-99"
        errors = verify_spec_recitation(block, repo)
        assert any("exceeds" in e for e in errors)

    def test_py_file_requires_symbol(self, repo: Path) -> None:
        block = self._good_block()
        del block.fields["SYMBOL"]
        errors = verify_spec_recitation(block, repo)
        assert any("SYMBOL" in e for e in errors)

    def test_symbol_must_appear_in_quote(self, repo: Path) -> None:
        block = self._good_block()
        block.fields["SYMBOL"] = "normalize_v2"
        errors = verify_spec_recitation(block, repo)
        assert any("does not appear in the quoted lines" in e for e in errors)

    def test_short_spec_fails(self, repo: Path) -> None:
        block = self._good_block()
        block.fields["SPEC"] = "checked"
        errors = verify_spec_recitation(block, repo)
        assert any("too short" in e for e in errors)

    def test_quote_overlapping_diff_fails(self, repo: Path) -> None:
        diff_ranges = {"core/detector.py": [(9, 9)]}
        errors = verify_spec_recitation(self._good_block(), repo, diff_ranges)
        assert any("OUTSIDE the diff" in e for e in errors)

    def test_quote_outside_diff_passes(self, repo: Path) -> None:
        diff_ranges = {"core/detector.py": [(1, 2)]}
        assert verify_spec_recitation(self._good_block(), repo, diff_ranges) == []

    def test_docs_file_heading_quote_passes_without_symbol(self, repo: Path) -> None:
        block = _block(
            "SPEC_RECITATION",
            {
                "FILE": "docs/SPEC.md",
                "LINES": "3-5",
                "SPEC": "Detection rules section mandates lowercasing before matching.",
            },
            ["## Detection rules", "", "Lowercase before matching."],
        )
        assert verify_spec_recitation(block, repo) == []


# ---------------------------------------------------------------------------
# CALLSITE
# ---------------------------------------------------------------------------


class TestCallsite:
    def test_valid_callsite_passes(self, repo: Path) -> None:
        # literal substring search: "normalized" on lines 9-10 also matches
        block = _block(
            "CALLSITE",
            {"SYMBOL": "normalize", "COUNT": "3"},
            [
                "core/detector.py:4:def normalize(payload):",
                "core/detector.py:9:    normalized = normalize(payload)",
                'core/detector.py:10:    return "attack" in normalized',
            ],
        )
        assert verify_callsite(block, repo) == []

    def test_count_vs_listed_mismatch_fails(self, repo: Path) -> None:
        block = _block(
            "CALLSITE",
            {"SYMBOL": "normalize", "COUNT": "2"},
            ["core/detector.py:4:def normalize(payload):"],
        )
        errors = verify_callsite(block, repo)
        assert any("match line(s) are listed" in e for e in errors)

    def test_undercount_vs_reality_fails(self, repo: Path) -> None:
        block = _block(
            "CALLSITE",
            {"SYMBOL": "normalize", "COUNT": "1"},
            ["core/detector.py:4:def normalize(payload):"],
        )
        errors = verify_callsite(block, repo)
        assert any("incomplete or stale" in e for e in errors)

    def test_fabricated_content_fails(self, repo: Path) -> None:
        block = _block(
            "CALLSITE",
            {"SYMBOL": "normalize", "COUNT": "2"},
            [
                "core/detector.py:4:def normalize(payload, strict=True):",
                "core/detector.py:9:    normalized = normalize(payload)",
            ],
        )
        errors = verify_callsite(block, repo)
        assert any("content mismatch" in e for e in errors)

    def test_scope_prefix_limits_search(self, repo: Path) -> None:
        block = _block(
            "CALLSITE",
            {"SYMBOL": "Lowercase", "COUNT": "1", "SCOPE": "docs/"},
            ["docs/SPEC.md:5:Lowercase before matching."],
        )
        assert verify_callsite(block, repo) == []


# ---------------------------------------------------------------------------
# NEGATIVE
# ---------------------------------------------------------------------------


class TestNegative:
    def test_true_absence_passes(self, repo: Path) -> None:
        block = _block(
            "NEGATIVE",
            {
                "PATTERN": "os.system",
                "COUNT": "0",
                "NOTE": "no shell execution path exists in the detector",
            },
            [],
        )
        assert verify_negative(block, repo) == []

    def test_false_absence_claim_fails(self, repo: Path) -> None:
        block = _block(
            "NEGATIVE",
            {
                "PATTERN": "normalize",
                "COUNT": "0",
                "NOTE": "claiming normalize is unused (it is not)",
            },
            [],
        )
        errors = verify_negative(block, repo)
        assert any("found 3" in e for e in errors)

    def test_short_note_fails(self, repo: Path) -> None:
        block = _block(
            "NEGATIVE",
            {"PATTERN": "os.system", "COUNT": "0", "NOTE": "ok"},
            [],
        )
        errors = verify_negative(block, repo)
        assert any("too short" in e for e in errors)


# ---------------------------------------------------------------------------
# READ_MANIFEST
# ---------------------------------------------------------------------------


class TestReadManifest:
    def test_valid_manifest_passes(self, repo: Path) -> None:
        block = _block(
            "READ_MANIFEST",
            {},
            [
                "FULL: core/detector.py",
                "DIFF_ONLY: docs/SPEC.md reason: prose-only file, headings cross-checked",
            ],
        )
        assert verify_read_manifest(block, repo) == []

    def test_empty_manifest_fails(self, repo: Path) -> None:
        block = _block("READ_MANIFEST", {}, [])
        errors = verify_read_manifest(block, repo)
        assert any("empty" in e for e in errors)

    def test_diff_only_without_reason_fails(self, repo: Path) -> None:
        block = _block("READ_MANIFEST", {}, ["DIFF_ONLY: docs/SPEC.md"])
        errors = verify_read_manifest(block, repo)
        assert any("reason" in e for e in errors)

    def test_nonexistent_full_entry_fails(self, repo: Path) -> None:
        block = _block("READ_MANIFEST", {}, ["FULL: core/ghost.py"])
        errors = verify_read_manifest(block, repo)
        assert any("does not exist" in e for e in errors)


# ---------------------------------------------------------------------------
# Diff coverage
# ---------------------------------------------------------------------------


class TestDiffCoverage:
    def _ledger(self) -> list[EvidenceBlock]:
        return [
            _block(
                "SPEC_RECITATION",
                {"FILE": "core/detector.py", "LINES": "8-10", "SYMBOL": "detect",
                 "SPEC": "x" * 20},
                [],
            ),
            _block("CALLSITE", {"SYMBOL": "detect", "COUNT": "1"}, []),
            _block("READ_MANIFEST", {}, ["FULL: core/detector.py", "FULL: docs/NEW.md"]),
        ]

    def test_covered_diff_passes(self) -> None:
        diffs = {
            "core/detector.py": FileDiff(status="M", new_ranges=[(1, 2)]),
            "docs/NEW.md": FileDiff(status="A"),
        }
        assert verify_diff_coverage(self._ledger(), diffs) == []

    def test_unrecited_modified_file_fails(self) -> None:
        diffs = {"docs/SPEC.md": FileDiff(status="M")}
        errors = verify_diff_coverage(self._ledger(), diffs)
        assert any("no SPEC_RECITATION" in e for e in errors)
        assert any("missing from READ_MANIFEST" in e for e in errors)

    def test_new_file_is_exempt_from_recitation(self) -> None:
        diffs = {"docs/NEW.md": FileDiff(status="A")}
        assert verify_diff_coverage(self._ledger(), diffs) == []

    def test_py_change_without_callsite_fails(self) -> None:
        ledger = [b for b in self._ledger() if b.type != "CALLSITE"]
        diffs = {"core/detector.py": FileDiff(status="M")}
        errors = verify_diff_coverage(ledger, diffs)
        assert any("CALLSITE" in e for e in errors)

    def test_deleted_file_is_skipped(self) -> None:
        diffs = {"core/old.py": FileDiff(status="D")}
        assert verify_diff_coverage(self._ledger(), diffs) == []


# ---------------------------------------------------------------------------
# End-to-end report validation + CLI
# ---------------------------------------------------------------------------

_VALID_REPORT = """\
# Audit report

```audit-evidence
TYPE: SPEC_RECITATION
FILE: core/detector.py
LINES: 8-10
SYMBOL: detect
SPEC: detect() lowercases the payload then substring-matches 'attack'.
---
def detect(payload):
    normalized = normalize(payload)
    return "attack" in normalized
```

```audit-evidence
TYPE: NEGATIVE
PATTERN: os.system
COUNT: 0
NOTE: no shell execution path exists in the repository
---
```

```audit-evidence
TYPE: NEGATIVE
PATTERN: subprocess.Popen
COUNT: 0
NOTE: detector never spawns processes
---
```

```audit-evidence
TYPE: READ_MANIFEST
---
FULL: core/detector.py
FULL: docs/SPEC.md
```
"""


class TestValidateReport:
    def test_valid_report_passes(self, repo: Path, tmp_path: Path) -> None:
        report = tmp_path / "report.md"
        report.write_text(_VALID_REPORT, encoding="utf-8")
        result = validate_report(report, repo)
        assert result["errors"] == []
        assert result["valid"] is True
        assert result["blocks"] == 4

    def test_diff_only_report_fails_closed(self, repo: Path, tmp_path: Path) -> None:
        """A report with no evidence blocks at all (diff-only audit) must fail."""
        report = tmp_path / "report.md"
        report.write_text("# Audit report\n\nLGTM, the diff looks fine.\n", encoding="utf-8")
        result = validate_report(report, repo)
        assert result["valid"] is False
        joined = "\n".join(result["errors"])
        assert "SPEC_RECITATION" in joined
        assert "READ_MANIFEST" in joined
        assert "NEGATIVE" in joined

    def test_fabricated_quote_fails(self, repo: Path, tmp_path: Path) -> None:
        report = tmp_path / "report.md"
        report.write_text(
            _VALID_REPORT.replace(
                '    return "attack" in normalized',
                '    return "attack" in payload',
            ),
            encoding="utf-8",
        )
        result = validate_report(report, repo)
        assert result["valid"] is False
        assert any("does not match" in e for e in result["errors"])

    def test_report_inside_repo_is_excluded_from_recount(self, repo: Path) -> None:
        """The ledger's own PATTERN text must not count as an occurrence."""
        report = repo / "docs" / "audit_report.md"
        report.write_text(_VALID_REPORT, encoding="utf-8")
        result = validate_report(report, repo)
        assert result["errors"] == []

    def test_cli_main_valid(self, repo: Path, tmp_path: Path, capsys) -> None:
        report = tmp_path / "report.md"
        report.write_text(_VALID_REPORT, encoding="utf-8")
        rc = main(["--report", str(report), "--root", str(repo)])
        assert rc == 0
        assert "VALID" in capsys.readouterr().out

    def test_cli_main_invalid_json(self, repo: Path, tmp_path: Path, capsys) -> None:
        report = tmp_path / "report.md"
        report.write_text("no evidence here\n", encoding="utf-8")
        rc = main(["--report", str(report), "--root", str(repo), "--json"])
        assert rc == 1
        out = capsys.readouterr().out
        assert '"valid": false' in out
