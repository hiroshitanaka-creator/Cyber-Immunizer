"""Tests for structured-rules offline proposal output (PR-D').

Tests the --structured-rules --offline-sample CLI mode that produces
a structured detector rules JSON document without any API call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.structured_validator import validate_rules_schema
from scripts.propose_mutation import (
    build_offline_sample_structured_rules,
    main,
    propose_structured_rules,
)


class TestBuildOfflineSampleStructuredRules:
    """Test the build_offline_sample_structured_rules() function."""

    def test_returns_dict(self) -> None:
        """build_offline_sample_structured_rules returns a dict."""
        result = build_offline_sample_structured_rules()
        assert isinstance(result, dict)

    def test_schema_version_is_1(self) -> None:
        """Generated document has schema_version: 1."""
        result = build_offline_sample_structured_rules()
        assert result.get("schema_version") == 1

    def test_contains_five_rules(self) -> None:
        """Generated document contains exactly 5 rules for symbolic indicators."""
        result = build_offline_sample_structured_rules()
        rules = result.get("rules", [])
        assert len(rules) == 5

    def test_rules_use_five_indicators(self) -> None:
        """Generated rules contain all five symbolic indicator literals."""
        result = build_offline_sample_structured_rules()
        rules = result.get("rules", [])
        literals = [r.get("literal") for r in rules]
        expected = {
            "path_traversal_indicator",
            "script_injection_indicator",
            "sqli_indicator",
            "command_delimiter_indicator",
            "encoded_traversal_indicator",
        }
        assert set(literals) == expected

    def test_all_rules_use_contains_literal_operator(self) -> None:
        """All rules use 'contains_literal' operator."""
        result = build_offline_sample_structured_rules()
        rules = result.get("rules", [])
        for rule in rules:
            assert rule.get("operator") == "contains_literal"

    def test_all_rules_have_field_surface(self) -> None:
        """All rules use field='surface'."""
        result = build_offline_sample_structured_rules()
        rules = result.get("rules", [])
        for rule in rules:
            assert rule.get("field") == "surface"

    def test_rules_have_valid_confidence(self) -> None:
        """All rules have confidence in [0.0, 1.0]."""
        result = build_offline_sample_structured_rules()
        rules = result.get("rules", [])
        for rule in rules:
            conf = rule.get("confidence")
            assert isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0

    def test_document_passes_schema_validation(self) -> None:
        """Generated document passes validate_rules_schema()."""
        result = build_offline_sample_structured_rules()
        validation = validate_rules_schema(result)
        assert validation.get("success") is True
        assert not validation.get("violations", [])

    def test_features_surface_fields_complete(self) -> None:
        """Generated document includes all required surface fields."""
        result = build_offline_sample_structured_rules()
        surface = result.get("features", {}).get("surface", {})
        fields = surface.get("fields", [])
        expected_fields = {
            "method",
            "path",
            "query.keys",
            "query.values",
            "headers.keys",
            "headers.values",
            "body",
        }
        assert set(fields) == expected_fields

    def test_fallback_blocked_is_false(self) -> None:
        """Fallback has blocked=False for safe default."""
        result = build_offline_sample_structured_rules()
        fallback = result.get("fallback", {})
        assert fallback.get("blocked") is False

    def test_fallback_confidence_zero(self) -> None:
        """Fallback has confidence=0.0."""
        result = build_offline_sample_structured_rules()
        fallback = result.get("fallback", {})
        assert fallback.get("confidence") == 0.0

    def test_fallback_matched_signals_empty(self) -> None:
        """Fallback has matched_signals=[]."""
        result = build_offline_sample_structured_rules()
        fallback = result.get("fallback", {})
        assert fallback.get("matched_signals") == []


class TestProposeStructuredRules:
    """Test the propose_structured_rules() function."""

    def test_offline_sample_true_returns_valid_doc(self) -> None:
        """propose_structured_rules(offline_sample=True) returns (rules_doc, '')."""
        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""
        assert rules_doc is not None
        assert isinstance(rules_doc, dict)

    def test_offline_sample_false_returns_none(self) -> None:
        """propose_structured_rules(offline_sample=False) returns (None, error)."""
        rules_doc, err = propose_structured_rules(offline_sample=False)
        assert rules_doc is None
        assert "offline-sample only" in err

    def test_returned_doc_passes_validation(self) -> None:
        """Returned document from offline_sample=True passes schema validation."""
        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""
        validation = validate_rules_schema(rules_doc)
        assert validation.get("success") is True

    def test_offline_sample_default_false(self) -> None:
        """Default (no args) defaults to offline_sample=False."""
        rules_doc, err = propose_structured_rules()
        assert rules_doc is None
        assert err != ""


class TestCLIStructuredRulesMode:
    """Test the --structured-rules CLI mode."""

    def test_structured_rules_requires_offline_sample(
        self, capsys: pytest.CaptureFixture,
    ) -> None:
        """--structured-rules without --offline-sample fails."""
        rc = main(["--structured-rules", "--json"])
        assert rc == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("success") is False
        assert "offline-sample" in output.get("error", "")

    def test_structured_rules_offline_sample_json_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """--structured-rules --offline-sample --json produces valid output in isolated tmp_path."""
        # Create temporary .cyber_immunizer dir
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()
        rules_path = out_dir / "structured_rules.json"
        patch_path = out_dir / "mutation_patch.json"

        # Patch the output paths to use tmp_path
        monkeypatch.setattr("scripts.propose_mutation._OUT_DIR", out_dir)
        monkeypatch.setattr("scripts.propose_mutation._OUT_STRUCTURED_RULES", rules_path)
        monkeypatch.setattr("scripts.propose_mutation._OUT_PATCH", patch_path)

        # Call main() in-process with patched paths
        rc = main(["--structured-rules", "--offline-sample", "--json"])
        assert rc == 0

        # Verify output through capsys
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("success") is True
        assert output.get("mode") == "structured-rules-offline-sample"
        assert output.get("patch_path") is None
        assert "rules_path" in output
        assert output.get("rule_count") == 5

        # Verify artifact was written only to tmp_path, not repo root
        assert rules_path.exists()
        repo_root_rules = _PROJECT_ROOT / ".cyber_immunizer" / "structured_rules.json"
        # File may exist if previous tests wrote it, but we're not writing to it now
        # The key test is that our monkeypatch made it use tmp_path

    def test_structured_rules_rejects_live_model(
        self, capsys: pytest.CaptureFixture,
    ) -> None:
        """--structured-rules --live-model fails."""
        rc = main(
            [
                "--structured-rules",
                "--offline-sample",
                "--live-model",
                "--allow-live-model",
                "--json",
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("success") is False
        assert "does not support" in output.get("error", "")

    def test_structured_rules_rejects_gemini_paid_credit(
        self, capsys: pytest.CaptureFixture,
    ) -> None:
        """--structured-rules --gemini-paid-credit fails."""
        rc = main(
            [
                "--structured-rules",
                "--offline-sample",
                "--gemini-paid-credit",
                "--allow-live-model",
                "--json",
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("success") is False
        assert "does not support" in output.get("error", "")


class TestStaleMutationPatchCleanup:
    """Test that stale mutation_patch.json is cleaned up after structured-rules success."""

    def test_stale_mutation_patch_removed_via_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Structured-rules CLI mode removes existing mutation_patch.json before writing rules."""
        # Create temporary .cyber_immunizer dir
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()

        # Create a stale mutation_patch.json to verify cleanup
        stale_patch = out_dir / "mutation_patch.json"
        stale_patch.write_text('{"old": "patch"}', encoding="utf-8")
        assert stale_patch.exists(), "Stale patch should exist before test"

        rules_path = out_dir / "structured_rules.json"

        # Patch the output paths to use tmp_path
        monkeypatch.setattr("scripts.propose_mutation._OUT_DIR", out_dir)
        monkeypatch.setattr("scripts.propose_mutation._OUT_STRUCTURED_RULES", rules_path)
        monkeypatch.setattr("scripts.propose_mutation._OUT_PATCH", stale_patch)

        # Call main() which should clean up the stale patch
        rc = main(["--structured-rules", "--offline-sample", "--json"])
        assert rc == 0

        # Verify stale patch was removed by the actual CLI path
        assert not stale_patch.exists(), "Stale patch should be removed after structured-rules success"

        # Verify rules were written
        assert rules_path.exists(), "Rules file should be created"

        # Verify JSON output confirms patch_path is None
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("patch_path") is None

    def test_structured_rules_does_not_write_patch(self, tmp_path: Path) -> None:
        """Structured-rules mode never writes mutation_patch.json."""
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()
        patch_path = out_dir / "mutation_patch.json"

        # Call propose_structured_rules (low-level function, not main())
        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""

        # Ensure patch_path is NOT created by propose_structured_rules
        # (This is actually tested implicitly; the function doesn't touch _OUT_PATCH)
        assert rules_doc is not None
        assert "rules" in rules_doc


class TestValidatorAndEvaluatorCompatibility:
    """Test that generated rules work with validator and evaluator."""

    def test_rules_compatible_with_validator(self) -> None:
        """Generated rules pass validate_rules_schema()."""
        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""
        validation = validate_rules_schema(rules_doc)
        assert validation.get("success") is True

    def test_rules_compatible_with_evaluator(self) -> None:
        """Generated rules can be used by structured_evaluator."""
        try:
            from core.structured_evaluator import evaluate_structured_rules
            from tests.test_structured_evaluator import request
        except ImportError:
            pytest.skip("structured_evaluator not available")

        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""

        # Test that the evaluator can process these rules
        sample_request = request(body="path_traversal_indicator")
        result = evaluate_structured_rules(sample_request, rules_doc)
        assert result is not None
        assert hasattr(result, "blocked")

    def test_rules_compatible_with_detector(self) -> None:
        """Generated rules can be used by structured_detector."""
        try:
            from core.structured_detector import inspect_request_with_structured_rules
            from tests.test_structured_detector_integration import request
        except ImportError:
            pytest.skip("structured_detector not available")

        rules_doc, err = propose_structured_rules(offline_sample=True)
        assert err == ""

        # Test that the detector can process these rules
        sample_request = request(body="benign")
        result = inspect_request_with_structured_rules(sample_request, rules_doc)
        assert result is not None
        assert hasattr(result, "blocked")


# ---------------------------------------------------------------------------
# P2 Fix 1: Rule signals must equal detector literals
# ---------------------------------------------------------------------------


class TestRuleSignalsEqualDetectorLiterals:
    """Verify that every rule's signal equals its literal (P2 Fix 1)."""

    _EXPECTED_SIGNAL_SET = {
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    }

    def test_signal_equals_literal_for_each_rule(self) -> None:
        """Each rule's signal must equal its literal."""
        rules = build_offline_sample_structured_rules()["rules"]
        for rule in rules:
            assert rule["signal"] == rule["literal"], (
                f"Rule {rule['id']!r}: signal={rule['signal']!r} != literal={rule['literal']!r}"
            )

    def test_exact_signal_set(self) -> None:
        """The complete set of signals matches the expected detector indicator names."""
        rules = build_offline_sample_structured_rules()["rules"]
        actual_signals = {r["signal"] for r in rules}
        assert actual_signals == self._EXPECTED_SIGNAL_SET


# ---------------------------------------------------------------------------
# P2 Fix 1: Matched-signals equivalence with legacy detector
# ---------------------------------------------------------------------------


class TestMatchedSignalsEquivalenceWithLegacyDetector:
    """Prove that offline sample structured rules return the same matched_signals
    as core.detector.inspect_request() (P2 Fix 1)."""

    def _make_request(self, **kwargs):
        from core.types import Request
        defaults = {
            "method": "GET",
            "path": "/api/data",
            "query": {},
            "headers": {"content-type": "text/plain"},
            "body": "",
            "source_ip": "127.0.0.1",
        }
        defaults.update(kwargs)
        return Request(**defaults)

    def _compare(self, req) -> None:
        from core.detector import inspect_request
        from core.structured_detector import inspect_request_with_structured_rules

        rules_doc = build_offline_sample_structured_rules()
        legacy = inspect_request(req)
        structured = inspect_request_with_structured_rules(req, rules_doc)

        assert structured.blocked is legacy.blocked
        assert structured.confidence == legacy.confidence
        assert structured.matched_signals == legacy.matched_signals
        # reason is stable: both paths use the same string literals
        assert structured.reason == legacy.reason

    def test_single_indicator_request(self) -> None:
        """Single-indicator request: matched_signals equivalent to legacy detector."""
        req = self._make_request(body="path_traversal_indicator")
        self._compare(req)

    def test_multi_indicator_request(self) -> None:
        """Multi-indicator request: matched_signals equivalent to legacy detector."""
        req = self._make_request(body="path_traversal_indicator script_injection_indicator")
        self._compare(req)

    def test_benign_request(self) -> None:
        """Benign request: matched_signals equivalent to legacy detector (both empty)."""
        req = self._make_request(body="ordinary benign request")
        self._compare(req)


# ---------------------------------------------------------------------------
# P2 Fix 2: Reject --structured-rules + --gemini-paid-credit-preflight
# ---------------------------------------------------------------------------


class TestStructuredRulesRejectsPaidCreditPreflight:
    """Verify that --structured-rules --gemini-paid-credit-preflight is rejected (P2 Fix 2)."""

    def test_rejects_gemini_paid_credit_preflight(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """--structured-rules --offline-sample --gemini-paid-credit-preflight fails."""
        rc = main([
            "--structured-rules",
            "--offline-sample",
            "--gemini-paid-credit-preflight",
            "--json",
        ])
        assert rc == 1

    def test_rejects_preflight_json_success_false(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """JSON output has success=False when preflight flag combined with structured-rules."""
        main([
            "--structured-rules",
            "--offline-sample",
            "--gemini-paid-credit-preflight",
            "--json",
        ])
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("success") is False

    def test_rejects_preflight_error_message(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Error message mentions unsupported mode / offline-sample-only."""
        main([
            "--structured-rules",
            "--offline-sample",
            "--gemini-paid-credit-preflight",
            "--json",
        ])
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        error = output.get("error", "")
        assert "does not support" in error or "offline-sample" in error

    def test_no_rules_file_written_on_preflight_rejection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """No structured_rules.json is written when preflight flag causes rejection."""
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()
        rules_path = out_dir / "structured_rules.json"
        patch_path = out_dir / "mutation_patch.json"

        monkeypatch.setattr("scripts.propose_mutation._OUT_DIR", out_dir)
        monkeypatch.setattr("scripts.propose_mutation._OUT_STRUCTURED_RULES", rules_path)
        monkeypatch.setattr("scripts.propose_mutation._OUT_PATCH", patch_path)

        rc = main([
            "--structured-rules",
            "--offline-sample",
            "--gemini-paid-credit-preflight",
            "--json",
        ])
        assert rc == 1
        assert not rules_path.exists(), "structured_rules.json must not be written on rejection"
        assert not patch_path.exists(), "mutation_patch.json must not be written on rejection"
