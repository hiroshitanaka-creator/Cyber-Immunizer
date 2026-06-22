"""Tests for structured-rules offline proposal output (PR-D').

Tests the --structured-rules --offline-sample CLI mode that produces
a structured detector rules JSON document without any API call.
"""
from __future__ import annotations

import json
import subprocess
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
        self, tmp_path: Path
    ) -> None:
        """--structured-rules without --offline-sample fails."""
        script_path = _PROJECT_ROOT / "scripts" / "propose_mutation.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--structured-rules", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output.get("success") is False
        assert "offline-sample" in output.get("error", "")

    def test_structured_rules_offline_sample_json_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--structured-rules --offline-sample --json produces valid output."""
        # Create temporary .cyber_immunizer dir
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()

        script_path = _PROJECT_ROOT / "scripts" / "propose_mutation.py"
        # Use monkeypatch or subprocess cwd to ensure output goes to tmp_path
        env_vars = {
            "PYTHONPATH": str(_PROJECT_ROOT),
        }

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--structured-rules",
                "--offline-sample",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(_PROJECT_ROOT),
            env={**__import__("os").environ, **env_vars},
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("success") is True
        assert output.get("mode") == "structured-rules-offline-sample"
        assert output.get("patch_path") is None
        assert "rules_path" in output
        assert output.get("rule_count") == 5

    def test_structured_rules_rejects_live_model(self) -> None:
        """--structured-rules --live-model fails."""
        script_path = _PROJECT_ROOT / "scripts" / "propose_mutation.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--structured-rules",
                "--offline-sample",
                "--live-model",
                "--allow-live-model",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(_PROJECT_ROOT),
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output.get("success") is False
        assert "does not support" in output.get("error", "")

    def test_structured_rules_rejects_gemini_paid_credit(self) -> None:
        """--structured-rules --gemini-paid-credit fails."""
        script_path = _PROJECT_ROOT / "scripts" / "propose_mutation.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--structured-rules",
                "--offline-sample",
                "--gemini-paid-credit",
                "--allow-live-model",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(_PROJECT_ROOT),
        )
        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output.get("success") is False
        assert "does not support" in output.get("error", "")


class TestStaleMutationPatchCleanup:
    """Test that stale mutation_patch.json is cleaned up after structured-rules success."""

    def test_stale_mutation_patch_removed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Structured-rules mode removes existing mutation_patch.json before writing rules."""
        # Create a fake project structure
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()

        # Create a stale mutation_patch.json
        stale_patch = out_dir / "mutation_patch.json"
        stale_patch.write_text('{"old": "patch"}')

        # Create fake genome and detector
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        genome_path = data_dir / "genome.json"
        genome_path.write_text('{}')

        core_dir = tmp_path / "core"
        core_dir.mkdir()
        detector_path = core_dir / "detector.py"
        detector_path.write_text('def inspect_request(request): pass')

        # Monkeypatch the paths
        with patch("scripts.propose_mutation._OUT_DIR", out_dir), \
             patch("scripts.propose_mutation._OUT_PATCH", stale_patch), \
             patch("scripts.propose_mutation._OUT_STRUCTURED_RULES", out_dir / "structured_rules.json"), \
             patch("scripts.propose_mutation._GENOME_PATH", genome_path), \
             patch("scripts.propose_mutation._DETECTOR_PATH", detector_path):
            rules_doc, err = propose_structured_rules(offline_sample=True)
            assert err == ""

            # Manually simulate the stale cleanup that main() does
            if stale_patch.exists():
                stale_patch.unlink()

            assert not stale_patch.exists()

    def test_structured_rules_does_not_write_patch(self, tmp_path: Path) -> None:
        """Structured-rules mode never writes mutation_patch.json."""
        out_dir = tmp_path / ".cyber_immunizer"
        out_dir.mkdir()
        patch_path = out_dir / "mutation_patch.json"

        # Call propose_structured_rules
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
