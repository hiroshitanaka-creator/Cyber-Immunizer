"""tests/test_apply_mutation.py — Tests for apply_mutation.py --report option.

Covers:
  A. malformed / missing-field patch → apply_report.json generated
  B. policy violation → report generated, replacement_code full text absent
  C. valid patch → report has success=true and candidate_path
  D. report schema: stage, replacement_code_sha256, required fields
  E. --report write failure is fail-closed (non-zero exit)
  F. No --report → no file written
  G. _write_apply_report_atomic unit tests
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.apply_mutation import (
    apply_mutation,
    main,
    _write_apply_report_atomic,
    _sanitize_report_string,
    _sanitize_target_threats,
    _SECRET_MARKERS,
    _CODELIKE_MARKERS,
    _SANITIZE_MAX_STRING_LEN,
    _SANITIZE_MAX_THREATS,
)

# ---------------------------------------------------------------------------
# Shared test helpers / fixtures
# ---------------------------------------------------------------------------

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="

_BASE_SOURCE = f"""\
\"\"\"Minimal base detector for tests.\"\"\"
from core.types import Request, DetectionResult

def inspect_request(request: Request) -> DetectionResult:
    {_MUTATION_START}
    return DetectionResult(flagged=False, reasons=[])
    {_MUTATION_END}
"""

_REPLACEMENT_CODE = "    return DetectionResult(flagged=False, reasons=[])"

_VALID_PATCH = {
    "mutation_rationale": "test rationale",
    "target_threats": ["test_threat"],
    "expected_improvement": "none",
    "risk": "low",
    "replacement_code": _REPLACEMENT_CODE,
}


def _write_base(tmp_path: Path) -> Path:
    p = tmp_path / "detector.py"
    p.write_text(_BASE_SOURCE, encoding="utf-8")
    return p


def _write_patch(tmp_path: Path, patch_data: dict) -> Path:
    p = tmp_path / "patch.json"
    p.write_text(json.dumps(patch_data), encoding="utf-8")
    return p


def _apply_via_function(
    tmp_path: Path,
    patch_data: dict,
    validate_result: dict | None = None,
) -> dict:
    """Helper: call apply_mutation() directly with output_root=tmp_path."""
    patch_path = _write_patch(tmp_path, patch_data)
    base_path = _write_base(tmp_path)
    out_path = tmp_path / "output" / "candidate_detector.py"

    if validate_result is not None:
        with patch("scripts.apply_mutation.validate", return_value=validate_result):
            return apply_mutation(
                patch_path=patch_path,
                base_path=base_path,
                out_path=out_path,
                output_root=tmp_path,
            )
    else:
        return apply_mutation(
            patch_path=patch_path,
            base_path=base_path,
            out_path=out_path,
            output_root=tmp_path,
        )


def _build_report_payload(result: dict) -> dict:
    """Build apply_report.json payload from an apply_mutation() result dict."""
    exit_code = 0 if result["success"] else 1
    return {
        "stage": "apply_mutation",
        "success": result["success"],
        "exit_code": exit_code,
        "candidate_path": result.get("candidate_path"),
        "violations": result.get("violations", []),
        "error": result.get("error", ""),
        "mutation_rationale": result.get("mutation_rationale"),
        "target_threats": result.get("target_threats", []),
        "replacement_code_sha256": result.get("replacement_code_sha256"),
    }


def _call_main_with_patched_root(
    tmp_path: Path,
    patch_data: dict,
    validate_result: dict | None = None,
    extra_argv: list[str] | None = None,
) -> tuple[int, Path]:
    """Call main() with _DEFAULT_OUTPUT_ROOT patched to tmp_path.

    Returns (return_code, report_path).
    """
    patch_path = _write_patch(tmp_path, patch_data)
    base_path = _write_base(tmp_path)
    out_path = tmp_path / "candidate_detector.py"
    report_path = tmp_path / "apply_report.json"

    argv = [
        "--patch", str(patch_path),
        "--base", str(base_path),
        "--out", str(out_path),
        "--report", str(report_path),
    ]
    if extra_argv:
        argv.extend(extra_argv)

    ctx = [patch("scripts.apply_mutation._DEFAULT_OUTPUT_ROOT", tmp_path)]
    if validate_result is not None:
        ctx.append(patch("scripts.apply_mutation.validate", return_value=validate_result))

    from contextlib import ExitStack
    with ExitStack() as stack:
        for c in ctx:
            stack.enter_context(c)
        rc = main(argv)

    return rc, report_path


# ===========================================================================
# A. Malformed / missing-field patch → report generated
# ===========================================================================


class TestMalformedPatchReport:
    """Malformed or incomplete patches must still produce a report."""

    def test_malformed_json_generates_report(self, tmp_path: Path) -> None:
        """A non-JSON patch file must produce apply_report.json with success=false."""
        rc, report_path = _call_main_with_patched_root(
            tmp_path,
            {},  # will be overwritten below
        )
        # Override with a truly broken patch
        (tmp_path / "patch.json").write_text("NOT JSON {{{", encoding="utf-8")
        report_path = tmp_path / "apply_report.json"
        rc = main([
            "--patch", str(tmp_path / "patch.json"),
            "--base", str(tmp_path / "detector.py"),
            "--out", str(tmp_path / "candidate_detector.py"),
            "--report", str(report_path),
        ])

        assert rc != 0
        assert report_path.exists(), "apply_report.json must be created for malformed JSON"
        report = json.loads(report_path.read_text())
        assert report["stage"] == "apply_mutation"
        assert report["success"] is False
        assert report["exit_code"] == 1

    def test_missing_required_field_generates_report(self, tmp_path: Path) -> None:
        """A patch missing a required field must produce apply_report.json."""
        bad_patch = {k: v for k, v in _VALID_PATCH.items() if k != "replacement_code"}
        rc, report_path = _call_main_with_patched_root(tmp_path, bad_patch)

        assert rc != 0
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["success"] is False
        assert "replacement_code" in report.get("error", "")

    def test_missing_patch_file_generates_report(self, tmp_path: Path) -> None:
        """A non-existent patch file must produce apply_report.json."""
        report_path = tmp_path / "apply_report.json"
        _write_base(tmp_path)
        rc = main([
            "--patch", str(tmp_path / "does_not_exist.json"),
            "--base", str(tmp_path / "detector.py"),
            "--out", str(tmp_path / "candidate_detector.py"),
            "--report", str(report_path),
        ])

        assert rc != 0
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["success"] is False

    def test_patch_not_an_object_generates_report(self, tmp_path: Path) -> None:
        """A JSON array patch must produce apply_report.json with success=false."""
        patch_path = tmp_path / "patch.json"
        patch_path.write_text("[1, 2, 3]", encoding="utf-8")
        report_path = tmp_path / "apply_report.json"
        _write_base(tmp_path)
        rc = main([
            "--patch", str(patch_path),
            "--base", str(tmp_path / "detector.py"),
            "--out", str(tmp_path / "candidate_detector.py"),
            "--report", str(report_path),
        ])

        assert rc != 0
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["success"] is False


# ===========================================================================
# B. Policy violation → report generated, replacement_code absent
# ===========================================================================


class TestPolicyViolationReport:
    """A policy-violating candidate must produce a report without full replacement_code."""

    def test_ast_violation_report_has_no_replacement_code(self, tmp_path: Path) -> None:
        """Policy violation must produce a result without replacement_code full text."""
        bad_code = "    import os; os.system('id')  # violates policy"
        bad_patch = dict(_VALID_PATCH, replacement_code=bad_code)
        fake_val = {"valid": False, "violations": ["forbidden import: os"]}

        result = _apply_via_function(tmp_path, bad_patch, validate_result=fake_val)
        payload = _build_report_payload(result)
        report_path = tmp_path / "report.json"
        _write_apply_report_atomic(report_path, payload)

        report_text = report_path.read_text()
        report = json.loads(report_text)
        assert report["success"] is False
        assert "replacement_code" not in report, (
            "Full replacement_code text must never appear as a key in the report"
        )
        assert bad_code not in report_text, (
            "Raw replacement_code content must not appear anywhere in the report file"
        )

    def test_report_contains_replacement_code_sha256_not_full_code(
        self, tmp_path: Path
    ) -> None:
        """Report must contain replacement_code_sha256, not the full code string."""
        replacement = "    return DetectionResult(flagged=False, reasons=[])"
        patch_data = dict(_VALID_PATCH, replacement_code=replacement)
        fake_val = {"valid": False, "violations": ["simulated violation"]}

        result = _apply_via_function(tmp_path, patch_data, validate_result=fake_val)
        payload = _build_report_payload(result)
        report_path = tmp_path / "report.json"
        _write_apply_report_atomic(report_path, payload)

        report = json.loads(report_path.read_text())
        expected_sha = hashlib.sha256(replacement.encode()).hexdigest()
        assert report.get("replacement_code_sha256") == expected_sha
        assert replacement not in report_path.read_text(), (
            "Full replacement_code must not appear in the report"
        )

    def test_report_violations_list_populated_on_ast_failure(
        self, tmp_path: Path
    ) -> None:
        """Violations list must be populated on AST validation failure."""
        violations = ["forbidden import: subprocess", "dunder access denied"]
        fake_val = {"valid": False, "violations": violations}

        result = _apply_via_function(tmp_path, _VALID_PATCH, validate_result=fake_val)

        assert result["success"] is False
        assert result["violations"] == violations

    def test_mutation_rationale_present_after_parse_success(
        self, tmp_path: Path
    ) -> None:
        """mutation_rationale must be present in result even when AST validation fails."""
        fake_val = {"valid": False, "violations": ["bad"]}
        result = _apply_via_function(tmp_path, _VALID_PATCH, validate_result=fake_val)

        assert result.get("mutation_rationale") == _VALID_PATCH["mutation_rationale"]
        assert result.get("target_threats") == _VALID_PATCH["target_threats"]

    def test_replacement_code_sha256_present_after_parse_success(
        self, tmp_path: Path
    ) -> None:
        """replacement_code_sha256 must be present when patch parsed successfully."""
        fake_val = {"valid": False, "violations": ["bad"]}
        result = _apply_via_function(tmp_path, _VALID_PATCH, validate_result=fake_val)

        sha = result.get("replacement_code_sha256")
        assert sha is not None
        expected = hashlib.sha256(_VALID_PATCH["replacement_code"].encode()).hexdigest()
        assert sha == expected


# ===========================================================================
# C. Success path → report has success=true and candidate_path
# ===========================================================================


class TestSuccessPathReport:
    """On successful apply, report must have success=true and candidate_path."""

    def test_success_result_has_correct_fields(self, tmp_path: Path) -> None:
        """Successful apply must return success=true with candidate_path."""
        fake_val = {"valid": True, "violations": []}
        result = _apply_via_function(tmp_path, _VALID_PATCH, validate_result=fake_val)

        assert result["success"] is True
        assert result["candidate_path"] is not None
        assert result["candidate_path"].endswith(".py")
        assert result["violations"] == []

    def test_success_result_has_mutation_rationale(self, tmp_path: Path) -> None:
        """Successful result must include mutation_rationale from the patch."""
        fake_val = {"valid": True, "violations": []}
        result = _apply_via_function(tmp_path, _VALID_PATCH, validate_result=fake_val)

        assert result["mutation_rationale"] == _VALID_PATCH["mutation_rationale"]
        assert result["target_threats"] == _VALID_PATCH["target_threats"]

    def test_success_report_via_cli(self, tmp_path: Path) -> None:
        """CLI --report must write success=true and exit_code=0 on success."""
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, _VALID_PATCH, validate_result=fake_val
        )

        assert rc == 0
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["stage"] == "apply_mutation"
        assert report["success"] is True
        assert report["exit_code"] == 0
        assert report["candidate_path"] is not None


# ===========================================================================
# D. Report schema validation
# ===========================================================================


class TestReportSchema:
    """apply_report.json must always contain the required schema fields."""

    def _get_failure_report(self, tmp_path: Path) -> dict:
        """Helper: get report for a patch missing required fields (always fails)."""
        bad_patch = {k: v for k, v in _VALID_PATCH.items() if k != "replacement_code"}
        rc, report_path = _call_main_with_patched_root(tmp_path, bad_patch)
        return json.loads(report_path.read_text())

    def test_stage_field_present(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert "stage" in report
        assert report["stage"] == "apply_mutation"

    def test_success_field_present(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert "success" in report
        assert isinstance(report["success"], bool)

    def test_exit_code_field_present(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert "exit_code" in report
        assert report["exit_code"] in (0, 1)

    def test_violations_is_list(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert isinstance(report["violations"], list)

    def test_error_is_string(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert isinstance(report["error"], str)

    def test_target_threats_is_list(self, tmp_path: Path) -> None:
        report = self._get_failure_report(tmp_path)
        assert isinstance(report["target_threats"], list)

    def test_replacement_code_not_in_report(self, tmp_path: Path) -> None:
        """replacement_code must never appear as a key in the report."""
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, _VALID_PATCH, validate_result=fake_val
        )
        report = json.loads(report_path.read_text())
        assert "replacement_code" not in report

    def test_sha256_is_64_hex_chars_on_success(self, tmp_path: Path) -> None:
        """replacement_code_sha256 must be a 64-char hex string on success."""
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, _VALID_PATCH, validate_result=fake_val
        )
        report = json.loads(report_path.read_text())
        sha = report.get("replacement_code_sha256")
        assert sha is not None
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_sha256_is_null_when_patch_parse_fails(self, tmp_path: Path) -> None:
        """replacement_code_sha256 must be null when patch cannot be parsed."""
        patch_path = tmp_path / "bad.json"
        patch_path.write_text("BROKEN", encoding="utf-8")
        report_path = tmp_path / "apply_report.json"
        _write_base(tmp_path)
        main([
            "--patch", str(patch_path),
            "--base", str(tmp_path / "detector.py"),
            "--out", str(tmp_path / "candidate_detector.py"),
            "--report", str(report_path),
        ])
        report = json.loads(report_path.read_text())
        assert report["replacement_code_sha256"] is None


# ===========================================================================
# E. --report write failure is fail-closed
# ===========================================================================


class TestReportWriteFailClosed:
    """If --report write fails, main() must return non-zero (fail-closed)."""

    def test_report_write_failure_returns_nonzero(self, tmp_path: Path) -> None:
        """OSError on report write must cause main() to return non-zero."""
        fake_val = {"valid": True, "violations": []}
        with patch("scripts.apply_mutation._DEFAULT_OUTPUT_ROOT", tmp_path):
            with patch("scripts.apply_mutation.validate", return_value=fake_val):
                with patch(
                    "scripts.apply_mutation._write_apply_report_atomic",
                    return_value=(False, "simulated disk full"),
                ):
                    patch_path = _write_patch(tmp_path, _VALID_PATCH)
                    base_path = _write_base(tmp_path)
                    rc = main([
                        "--patch", str(patch_path),
                        "--base", str(base_path),
                        "--out", str(tmp_path / "candidate_detector.py"),
                        "--report", str(tmp_path / "report.json"),
                    ])

        assert rc != 0, "main() must return non-zero when --report write fails"

    def test_apply_succeeds_but_report_write_fails_is_nonzero(
        self, tmp_path: Path
    ) -> None:
        """Even when apply succeeded, a report write failure must cause non-zero exit."""
        fake_val = {"valid": True, "violations": []}
        with patch("scripts.apply_mutation._DEFAULT_OUTPUT_ROOT", tmp_path):
            with patch("scripts.apply_mutation.validate", return_value=fake_val):
                with patch(
                    "scripts.apply_mutation._write_apply_report_atomic",
                    return_value=(False, "simulated write error"),
                ):
                    patch_path = _write_patch(tmp_path, _VALID_PATCH)
                    base_path = _write_base(tmp_path)
                    rc = main([
                        "--patch", str(patch_path),
                        "--base", str(base_path),
                        "--out", str(tmp_path / "candidate_detector.py"),
                        "--report", str(tmp_path / "report.json"),
                    ])

        assert rc != 0


# ===========================================================================
# F. No --report → no report file written
# ===========================================================================


class TestNoReportFlag:
    """Without --report, no report file should be written."""

    def test_no_report_flag_no_file_on_failure(self, tmp_path: Path) -> None:
        """Without --report, apply_mutation must not write any report file on failure."""
        patch_path = tmp_path / "bad.json"
        patch_path.write_text("BROKEN", encoding="utf-8")
        report_candidate = tmp_path / "apply_report.json"
        _write_base(tmp_path)

        main([
            "--patch", str(patch_path),
            "--base", str(tmp_path / "detector.py"),
            "--out", str(tmp_path / "candidate_detector.py"),
            # no --report
        ])

        assert not report_candidate.exists(), (
            "No report file should be written when --report is not specified"
        )


# ===========================================================================
# G. _write_apply_report_atomic unit tests
# ===========================================================================


class TestWriteApplyReportAtomic:
    """Unit tests for the atomic report writer."""

    def test_atomic_write_creates_file(self, tmp_path: Path) -> None:
        report_path = tmp_path / "report.json"
        ok, err = _write_apply_report_atomic(report_path, {"key": "value"})
        assert ok is True
        assert err == ""
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert data == {"key": "value"}

    def test_atomic_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        report_path = tmp_path / "deep" / "nested" / "report.json"
        ok, err = _write_apply_report_atomic(report_path, {"a": 1})
        assert ok is True
        assert report_path.exists()

    def test_atomic_write_returns_false_on_oserror(self, tmp_path: Path) -> None:
        report_path = tmp_path / "report.json"
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("disk full")):
            ok, err = _write_apply_report_atomic(report_path, {})
        assert ok is False
        assert "failed to write apply report" in err

    def test_atomic_write_idempotent_on_overwrite(self, tmp_path: Path) -> None:
        """Repeated writes to the same path must produce the latest content."""
        report_path = tmp_path / "report.json"
        _write_apply_report_atomic(report_path, {"v": 1})
        _write_apply_report_atomic(report_path, {"v": 2})
        data = json.loads(report_path.read_text())
        assert data == {"v": 2}


# ===========================================================================
# H. Sanitization helpers
# ===========================================================================


class TestSanitizeReportString:
    """_sanitize_report_string() redacts secret markers and truncates long strings."""

    def test_clean_string_returned_unchanged(self) -> None:
        """A benign string is returned as-is (up to max_len)."""
        assert _sanitize_report_string("detects path traversal") == "detects path traversal"

    def test_string_truncated_to_max_len(self) -> None:
        """Strings longer than max_len are truncated."""
        long_val = "x" * (_SANITIZE_MAX_STRING_LEN + 100)
        result = _sanitize_report_string(long_val)
        assert len(result) == _SANITIZE_MAX_STRING_LEN

    def test_non_string_returns_invalid(self) -> None:
        """Non-string values return '[invalid]' — no str() coercion to avoid dict/list leakage."""
        result = _sanitize_report_string(42)
        assert result == "[invalid]"

    def test_none_returns_invalid(self) -> None:
        """None returns '[invalid]', not the string 'None'."""
        result = _sanitize_report_string(None)
        assert result == "[invalid]"

    def test_secret_marker_causes_redaction(self) -> None:
        """A string containing a secret marker returns '[REDACTED]'."""
        for marker in _SECRET_MARKERS:
            val = f"the GEMINI_{marker} is abc123"
            result = _sanitize_report_string(val)
            assert result == "[REDACTED]", f"marker {marker!r} must trigger redaction"

    def test_secret_marker_case_insensitive(self) -> None:
        """Marker detection is case-insensitive."""
        assert _sanitize_report_string("my api_key is here") == "[REDACTED]"
        assert _sanitize_report_string("MY API_KEY IS HERE") == "[REDACTED]"
        assert _sanitize_report_string("My Api_Key Is Here") == "[REDACTED]"

    def test_custom_max_len_respected(self) -> None:
        """Custom max_len parameter overrides the default."""
        result = _sanitize_report_string("hello world", max_len=5)
        assert result == "hello"

    def test_empty_string_returned_unchanged(self) -> None:
        assert _sanitize_report_string("") == ""


class TestSanitizeReportStringCodeLike:
    """_sanitize_report_string() redacts code-like and replacement-like content."""

    def test_return_statement_redacted(self) -> None:
        """'return DetectionResult(flagged=False, reasons=[])' must be [REDACTED]."""
        val = "return DetectionResult(flagged=False, reasons=[])"
        assert _sanitize_report_string(val) == "[REDACTED]"

    def test_import_statement_redacted(self) -> None:
        """'import os' must be [REDACTED]."""
        assert _sanitize_report_string("import os") == "[REDACTED]"

    def test_def_statement_redacted(self) -> None:
        """'def inspect_request(request):' must be [REDACTED]."""
        assert _sanitize_report_string("def inspect_request(request):") == "[REDACTED]"

    def test_subprocess_call_redacted(self) -> None:
        """'subprocess.run(...)' must be [REDACTED]."""
        assert _sanitize_report_string("subprocess.run(['id'])") == "[REDACTED]"

    def test_eval_call_redacted(self) -> None:
        """'eval(...)' must be [REDACTED]."""
        assert _sanitize_report_string("uses eval(code) to run it") == "[REDACTED]"

    def test_exec_call_redacted(self) -> None:
        """'exec(...)' must be [REDACTED]."""
        assert _sanitize_report_string("exec(payload)") == "[REDACTED]"

    def test_flagged_keyword_redacted(self) -> None:
        """'flagged=' must be [REDACTED]."""
        assert _sanitize_report_string("sets flagged=True") == "[REDACTED]"

    def test_detectionresult_call_redacted(self) -> None:
        """'DetectionResult(' must be [REDACTED]."""
        assert _sanitize_report_string("wraps DetectionResult(blocked=True)") == "[REDACTED]"

    def test_inspect_request_redacted(self) -> None:
        """'inspect_request' must be [REDACTED]."""
        assert _sanitize_report_string("modifies inspect_request to block") == "[REDACTED]"

    def test_from_import_redacted(self) -> None:
        """'from core.types import ...' must be [REDACTED]."""
        assert _sanitize_report_string("from core.types import Request") == "[REDACTED]"

    def test_codelike_case_insensitive(self) -> None:
        """Code-like detection is case-insensitive."""
        assert _sanitize_report_string("IMPORT os") == "[REDACTED]"
        assert _sanitize_report_string("RETURN DetectionResult()") == "[REDACTED]"

    def test_dict_value_returns_invalid_not_leaked(self) -> None:
        """A dict value returns '[invalid]', not its str() representation."""
        d = {"secret": "abc123"}
        result = _sanitize_report_string(d)
        assert result == "[invalid]"
        assert "abc123" not in result
        assert "secret" not in result

    def test_list_value_returns_invalid_not_leaked(self) -> None:
        """A list value returns '[invalid]', not its str() representation."""
        lst = ["import os", "flagged=True"]
        result = _sanitize_report_string(lst)
        assert result == "[invalid]"
        assert "import" not in result

    def test_codelike_markers_tuple_is_non_empty(self) -> None:
        """_CODELIKE_MARKERS must exist and contain expected entries."""
        assert "return " in _CODELIKE_MARKERS
        assert "import " in _CODELIKE_MARKERS
        assert "subprocess" in _CODELIKE_MARKERS


class TestSanitizeTargetThreats:
    """_sanitize_target_threats() sanitizes each item and limits list length."""

    def test_clean_list_returned_as_is(self) -> None:
        threats = ["path_traversal", "sqli", "xss"]
        result = _sanitize_target_threats(threats)
        assert result == threats

    def test_non_list_returns_empty(self) -> None:
        assert _sanitize_target_threats("not a list") == []
        assert _sanitize_target_threats(None) == []
        assert _sanitize_target_threats(42) == []

    def test_list_truncated_to_max_threats(self) -> None:
        threats = [f"threat_{i}" for i in range(_SANITIZE_MAX_THREATS + 5)]
        result = _sanitize_target_threats(threats)
        assert len(result) == _SANITIZE_MAX_THREATS

    def test_secret_marker_in_item_causes_redaction(self) -> None:
        threats = ["path_traversal", "api_key exfiltration", "xss"]
        result = _sanitize_target_threats(threats)
        assert result[0] == "path_traversal"
        assert result[1] == "[REDACTED]"
        assert result[2] == "xss"

    def test_long_item_truncated(self) -> None:
        long_item = "x" * (_SANITIZE_MAX_STRING_LEN + 100)
        result = _sanitize_target_threats([long_item])
        assert len(result[0]) == _SANITIZE_MAX_STRING_LEN

    def test_dict_item_becomes_invalid(self) -> None:
        """A dict item in target_threats must become '[invalid]', not str(dict)."""
        threats = [{"key": "value"}, "path_traversal"]
        result = _sanitize_target_threats(threats)
        assert result[0] == "[invalid]"
        assert "key" not in result[0]
        assert "value" not in result[0]
        assert result[1] == "path_traversal"

    def test_list_item_becomes_invalid(self) -> None:
        """A list item in target_threats must become '[invalid]', not str(list)."""
        threats = [["import os", "exec()"], "sqli"]
        result = _sanitize_target_threats(threats)
        assert result[0] == "[invalid]"
        assert "import" not in result[0]
        assert result[1] == "sqli"

    def test_dict_contents_not_in_result(self) -> None:
        """Dict contents with secret-like values must not appear anywhere in result."""
        threats = [{"api_key": "secret_value_xyz"}]
        result = _sanitize_target_threats(threats)
        assert "secret_value_xyz" not in str(result)
        assert "api_key" not in str(result)

    def test_codelike_threat_redacted(self) -> None:
        """A threat item containing 'import os' must be [REDACTED]."""
        threats = ["import os; os.system('id')"]
        result = _sanitize_target_threats(threats)
        assert result[0] == "[REDACTED]"


class TestSanitizationAppliedInReport:
    """Sanitization must be applied to mutation_rationale and target_threats in the report."""

    def test_secret_in_rationale_is_redacted_in_report(self, tmp_path: Path) -> None:
        """mutation_rationale containing a secret marker must be redacted in apply_report.json."""
        bad_patch = dict(
            _VALID_PATCH,
            mutation_rationale="uses GEMINI_API_KEY to enhance detection",
        )
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["mutation_rationale"] == "[REDACTED]", (
            "mutation_rationale containing a secret marker must be redacted"
        )
        assert "GEMINI_API_KEY" not in report_path.read_text()

    def test_secret_in_target_threat_is_redacted_in_report(self, tmp_path: Path) -> None:
        """A target_threat item containing a secret marker must be redacted."""
        bad_patch = dict(
            _VALID_PATCH,
            target_threats=["path_traversal", "token exfiltration via response"],
        )
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        threats = report["target_threats"]
        assert threats[0] == "path_traversal"
        assert threats[1] == "[REDACTED]", "Threat item containing 'token' must be redacted"

    def test_clean_rationale_preserved_in_report(self, tmp_path: Path) -> None:
        """A clean mutation_rationale is preserved unchanged in apply_report.json."""
        clean_patch = dict(_VALID_PATCH, mutation_rationale="improve path traversal detection")
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, clean_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert report["mutation_rationale"] == "improve path traversal detection"

    def test_long_rationale_truncated_in_report(self, tmp_path: Path) -> None:
        """A mutation_rationale exceeding max_len is truncated in apply_report.json."""
        long_rationale = "x" * (_SANITIZE_MAX_STRING_LEN + 500)
        long_patch = dict(_VALID_PATCH, mutation_rationale=long_rationale)
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, long_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert len(report["mutation_rationale"]) == _SANITIZE_MAX_STRING_LEN

    def test_oversized_target_threats_truncated_in_report(self, tmp_path: Path) -> None:
        """A target_threats list exceeding max items is truncated in apply_report.json."""
        many_threats = [f"threat_{i}" for i in range(_SANITIZE_MAX_THREATS + 5)]
        long_patch = dict(_VALID_PATCH, target_threats=many_threats)
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, long_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert len(report["target_threats"]) == _SANITIZE_MAX_THREATS

    def test_rationale_with_exact_replacement_code_redacted(self, tmp_path: Path) -> None:
        """mutation_rationale containing the exact replacement_code must not write it to report."""
        exact_code = _VALID_PATCH["replacement_code"]
        bad_patch = dict(_VALID_PATCH, mutation_rationale=exact_code)
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert exact_code not in report_path.read_text(), (
            "Exact replacement_code must not appear in apply_report.json via mutation_rationale"
        )
        assert report["mutation_rationale"] == "[REDACTED]"

    def test_rationale_with_return_detectionresult_redacted(self, tmp_path: Path) -> None:
        """mutation_rationale with 'return DetectionResult(...)' is [REDACTED] in report."""
        bad_patch = dict(
            _VALID_PATCH,
            mutation_rationale="adds return DetectionResult(flagged=True, reasons=['xss'])",
        )
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert report["mutation_rationale"] == "[REDACTED]"

    def test_target_threats_with_import_os_redacted(self, tmp_path: Path) -> None:
        """target_threats item containing 'import os' is [REDACTED] in apply_report.json."""
        bad_patch = dict(_VALID_PATCH, target_threats=["import os; os.system('id')"])
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert report["target_threats"][0] == "[REDACTED]"
        assert "os.system" not in report_path.read_text()

    def test_target_threats_with_dict_does_not_leak(self, tmp_path: Path) -> None:
        """target_threats containing a dict must not leak dict contents into report."""
        bad_patch = dict(_VALID_PATCH, target_threats=[{"injected": "payload_xyz"}])
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, bad_patch, validate_result=fake_val
        )

        report_text = report_path.read_text()
        assert "payload_xyz" not in report_text
        assert "injected" not in report_text

    def test_replacement_code_sha256_preserved_after_hardening(self, tmp_path: Path) -> None:
        """replacement_code_sha256 must still be present after sanitization hardening."""
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, _VALID_PATCH, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        sha = report.get("replacement_code_sha256")
        assert sha is not None
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_raw_replacement_code_never_in_report(self, tmp_path: Path) -> None:
        """replacement_code must never appear as a key or value in apply_report.json."""
        fake_val = {"valid": True, "violations": []}
        rc, report_path = _call_main_with_patched_root(
            tmp_path, _VALID_PATCH, validate_result=fake_val
        )

        report = json.loads(report_path.read_text())
        assert "replacement_code" not in report
        assert _VALID_PATCH["replacement_code"] not in report_path.read_text()

# Offline pre-paid-credit mutation-boundary hardening
from scripts.apply_mutation import _apply_replacement, _parse_patch


def test_pre_paid_credit_mutation_marker_missing():
    source = "def inspect_request(request):\n    return None\n"
    new_source, err, issues = _apply_replacement(source, "    return None")
    assert new_source is None
    assert issues[0].code == "mutation_marker_missing"


def test_pre_paid_credit_mutation_marker_duplicated():
    source = "# === MUTATION_START ===\n# === MUTATION_START ===\n# === MUTATION_END ===\n"
    new_source, err, issues = _apply_replacement(source, "    return None")
    assert new_source is None
    assert issues[0].code == "mutation_marker_duplicate"


def test_pre_paid_credit_mutation_marker_order_invalid():
    source = "# === MUTATION_END ===\nbody\n# === MUTATION_START ===\n"
    new_source, err, issues = _apply_replacement(source, "    return None")
    assert new_source is None
    assert issues[0].code == "mutation_marker_order_invalid"


def test_pre_paid_credit_mutation_region_escape(tmp_path):
    patch = tmp_path / "patch.json"
    patch.write_text('{"mutation_rationale":"r","target_threats":[],"expected_improvement":"e","risk":"r","replacement_code":"    # === MUTATION_START ===\\n    return None"}')
    parsed, err, issues = _parse_patch(patch)
    assert parsed is None
    assert issues[0].code == "mutation_region_escape"


def test_pre_paid_credit_candidate_hash_mismatch_helper():
    from scripts.offline_validation import hash_consistency_issues
    issues = hash_consistency_issues("candidate", "0" * 64)
    assert issues[0].code == "candidate_hash_mismatch"


def test_pre_paid_credit_projected_source_too_large(monkeypatch):
    from scripts import apply_mutation as apply_mod
    monkeypatch.setattr(apply_mod, "MAX_POLICY_SOURCE_CHARS", 10)
    new_source, err, issues = apply_mod._apply_replacement(
        f"{_MUTATION_START}\nold\n{_MUTATION_END}\n", "    return None"
    )
    assert new_source is None
    assert issues[0].code == "candidate_materialization_failed"


def test_pre_paid_credit_outside_region_mismatch_helper():
    from scripts.offline_validation import outside_region_issues
    base = f"before\n{_MUTATION_START}\nold\n{_MUTATION_END}\nafter\n"
    candidate = f"CHANGED\n{_MUTATION_START}\nnew\n{_MUTATION_END}\nafter\n"
    issues = outside_region_issues(candidate_source=candidate, base_source=base)
    assert issues[0].code == "mutation_region_escape"


def test_pre_paid_credit_unsafe_output_path(tmp_path):
    base = _write_base(tmp_path)
    patch_path = _write_patch(tmp_path, _VALID_PATCH)
    result = apply_mutation(
        patch_path=patch_path,
        base_path=base,
        out_path=tmp_path / "outside.py",
        output_root=tmp_path / "allowed",
    )
    assert result["success"] is False
    assert any(r.startswith("candidate_output_path_unsafe:") for r in result["rejection_reasons"])


def test_pre_paid_credit_candidate_hash_present_on_success(tmp_path):
    base = _write_base(tmp_path)
    patch_path = _write_patch(tmp_path, _VALID_PATCH)
    with patch("scripts.apply_mutation.validate", return_value={"valid": True, "violations": []}):
        result = apply_mutation(
            patch_path=patch_path,
            base_path=base,
            out_path=tmp_path / "allowed" / "candidate.py",
            output_root=tmp_path / "allowed",
        )
    assert result["success"] is True
    assert len(result["candidate_hash"]) == 64


def test_pre_paid_credit_candidate_hash_present_in_apply_report(tmp_path):
    fake_val = {"valid": True, "violations": []}
    rc, report_path = _call_main_with_patched_root(
        tmp_path, _VALID_PATCH, validate_result=fake_val
    )
    report = json.loads(report_path.read_text())
    assert rc == 0
    assert len(report["candidate_hash"]) == 64
    assert "replacement_code" not in report
    assert _VALID_PATCH["replacement_code"] not in report_path.read_text()
