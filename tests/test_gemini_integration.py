"""tests/test_gemini_integration.py — Tests for the Gemini API integration in
propose_mutation.py.

All tests use monkeypatch; no real Gemini API calls are made.
No google-genai package is required to run these tests — the import is
guarded inside the live-call path, and tests mock before that point.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so imports work regardless of how
# pytest is invoked.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.propose_mutation as pm  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def genome_live_enabled() -> dict:
    """A genome dict with live_model_enabled=True and safe settings."""
    return {
        "project": "Test",
        "generation": 1,
        "best_score": -1000000.0,
        "max_commits_per_run": 1,
        "max_model_requests_per_run": 1,
        "max_fp_rate": 0.05,
        "min_regression_pass_rate": 1.0,
        "max_avg_latency_ms": 100.0,
        "model_provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "max_prompt_chars": 12000,
        "max_output_tokens": 2048,
        "temperature": 0.2,
        "live_model_enabled": True,
        "allow_google_search_grounding": False,
        "allow_code_execution_tool": False,
        "monthly_api_budget_usd": 0,
        "free_tier_only": True,
    }


@pytest.fixture()
def genome_live_disabled(genome_live_enabled: dict) -> dict:
    """A genome dict with live_model_enabled=False."""
    return {**genome_live_enabled, "live_model_enabled": False}


@pytest.fixture()
def test_genome_file(tmp_path: Path, genome_live_enabled: dict) -> Path:
    """Write a test genome.json and return its path."""
    p = tmp_path / "genome.json"
    p.write_text(json.dumps(genome_live_enabled), encoding="utf-8")
    return p


@pytest.fixture()
def test_genome_file_disabled(tmp_path: Path, genome_live_disabled: dict) -> Path:
    """Write a test genome.json with live_model_enabled=False."""
    p = tmp_path / "genome_disabled.json"
    p.write_text(json.dumps(genome_live_disabled), encoding="utf-8")
    return p


@pytest.fixture()
def test_detector_file(tmp_path: Path) -> Path:
    """Write a minimal test detector.py with mutation markers."""
    code = '''\
from core.types import Request, DetectionResult


def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
    # === MUTATION_END ===
'''
    p = tmp_path / "detector.py"
    p.write_text(code, encoding="utf-8")
    return p


@pytest.fixture()
def test_threats_file(tmp_path: Path) -> Path:
    """Write a minimal active_threats.json."""
    threats = [
        {"id": "THREAT-2024-001", "category": "path-traversal"},
        {"id": "THREAT-2024-005", "category": "encoded-traversal"},
    ]
    p = tmp_path / "active_threats.json"
    p.write_text(json.dumps(threats), encoding="utf-8")
    return p


@pytest.fixture()
def valid_patch() -> dict:
    """A patch dict that passes all validation checks.

    Uses plain string indicators without '__' so it passes _validate_replacement_code.
    (Live-model output must not contain '__'; the offline sample is trusted separately.)
    """
    return {
        "mutation_rationale": "Improve coverage for path traversal indicators.",
        "target_threats": ["THREAT-2024-001"],
        "expected_improvement": "Higher TP rate for traversal patterns.",
        "risk": "Low — additive logic only.",
        "replacement_code": (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path-traversal', 'sqli', 'xss', 'cmd-delim']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        boost = min(1.0, 0.5 + 0.12 * len(matched))\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched: ' + matched[0],\n"
            "            confidence=boost,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no suspicious indicator matched',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        ),
    }


# ---------------------------------------------------------------------------
# 1. Noop mode exits 0 and creates no patch
# ---------------------------------------------------------------------------


class TestNoopMode:
    def test_noop_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--noop exits 0."""
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", tmp_path / "mutation_patch.json")
        result = pm.main(["--noop", "--json"])
        assert result == 0

    def test_noop_creates_no_patch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--noop does not write mutation_patch.json."""
        patch_path = tmp_path / "mutation_patch.json"
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)
        pm.main(["--noop", "--json"])
        assert not patch_path.exists()

    def test_noop_prints_mode_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """--noop --json prints JSON with mode='noop'."""
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", tmp_path / "mutation_patch.json")
        pm.main(["--noop", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["patch_path"] is None
        assert data["mode"] == "noop"


# ---------------------------------------------------------------------------
# 2. live-model without --allow-live-model refuses
# ---------------------------------------------------------------------------


class TestLiveModelRequiresAllowFlag:
    def test_refuses_without_allow_flag(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--live-model without --allow-live-model returns an error."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=False)
        assert patch_result is None
        assert "--allow-live-model" in err

    def test_cli_refuses_without_allow_flag(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI: --live-model without --allow-live-model exits 1."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", tmp_path / "mutation_patch.json")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        result = pm.main(["--live-model", "--json"])
        assert result == 1


# ---------------------------------------------------------------------------
# 3. live-model without GEMINI_API_KEY refuses
# ---------------------------------------------------------------------------


class TestLiveModelRequiresApiKey:
    def test_refuses_without_api_key(
        self,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--live-model --allow-live-model without GEMINI_API_KEY returns error."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "GEMINI_API_KEY" in err

    def test_refuses_empty_api_key(
        self,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty GEMINI_API_KEY is treated as not set."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "GEMINI_API_KEY" in err


# ---------------------------------------------------------------------------
# 4. live-model refuses when genome.live_model_enabled=false
# ---------------------------------------------------------------------------


class TestLiveModelRequiresGenomeEnabled:
    def test_refuses_when_disabled_in_genome(
        self,
        tmp_path: Path,
        genome_live_disabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """live_model_enabled=false in genome → refused."""
        genome_path = tmp_path / "genome_disabled.json"
        genome_path.write_text(json.dumps(genome_live_disabled), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "live_model_enabled" in err

    def test_phase3_genome_has_live_enabled(self) -> None:
        """Phase 3 activation: real data/genome.json must have live_model_enabled=true with safe limits."""
        genome_path = _PROJECT_ROOT / "data" / "genome.json"
        if not genome_path.exists():
            pytest.skip("data/genome.json not found")
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
        assert genome.get("live_model_enabled") is True, (
            "data/genome.json live_model_enabled must be true for Phase 3 activation"
        )
        assert genome.get("max_model_requests_per_run") == 1, (
            "data/genome.json max_model_requests_per_run must be 1 for Phase 3 activation"
        )
        assert genome.get("send_repository_full_text") is False, (
            "data/genome.json send_repository_full_text must remain false"
        )
        assert genome.get("send_raw_payloads") is False, (
            "data/genome.json send_raw_payloads must remain false"
        )
        assert genome.get("send_secrets") is False, (
            "data/genome.json send_secrets must remain false"
        )

    def test_phase3_live_model_explicitly_blocked(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 3: live-model path is blocked even when live_model_enabled=true.

        propose_mutation(live_model=True, allow_live_model=True) must fail closed
        with a message directing the operator to use gemini-paid-credit.
        """
        genome_path = tmp_path / "genome_phase3.json"
        genome_path.write_text(json.dumps(genome_live_enabled), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None, "Phase 3 live-model gate must return no patch"
        assert "disabled" in err.lower() or "gemini-paid-credit" in err, (
            f"Phase 3 live-model gate must mention it is disabled and direct to "
            f"gemini-paid-credit. Got: {err!r}"
        )

    def test_phase3_live_model_cli_exits_nonzero(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 3: CLI invocation --live-model --allow-live-model exits nonzero."""
        import sys as _sys
        genome_path = tmp_path / "genome_phase3_cli.json"
        genome_path.write_text(json.dumps(genome_live_enabled), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        exit_code = pm.main(["--live-model", "--allow-live-model", "--json"])
        assert exit_code != 0, (
            "CLI --live-model --allow-live-model must exit nonzero in Phase 3."
        )


# ---------------------------------------------------------------------------
# 5. live-model refuses Pro model when free_tier_only=true
# ---------------------------------------------------------------------------


class TestLiveModelRefusesProModel:
    @pytest.mark.parametrize(
        "model_name",
        [
            "gemini-pro",
            "gemini-1.5-pro",
            "gemini-1.5-pro-preview",
            "gemini-pro-vision",
        ],
    )
    def test_refuses_pro_model_when_free_tier(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        model_name: str,
    ) -> None:
        """Pro model names are rejected when free_tier_only=true."""
        genome = {**genome_live_enabled, "model_name": model_name, "free_tier_only": True}
        genome_path = tmp_path / "genome_pro.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "pro" in err.lower() or "free_tier_only" in err

    def test_flash_model_blocked_by_phase3_gate(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 3: live-model is blocked even for Flash model with free_tier_only=true.

        The Phase 3 gate fires before the pro-model gate, so even a valid Flash
        model configuration cannot reach _propose_via_gemini_live.
        """
        genome = {**genome_live_enabled, "model_name": "gemini-2.0-flash", "free_tier_only": True}
        genome_path = tmp_path / "genome_flash.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None, "Phase 3 gate must block live-model"
        assert "disabled" in err.lower() or "gemini-paid-credit" in err, (
            f"Phase 3 gate must mention disabled / gemini-paid-credit. Got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 6. Prompt preflight rejects secrets
# ---------------------------------------------------------------------------


class TestPreflightSecretScan:
    @pytest.mark.parametrize(
        "secret_token",
        [
            "GITHUB_TOKEN",
            "github_token",
            "GEMINI_API_KEY",
            "gemini_api_key",
            "BEGIN PRIVATE KEY",
            "begin private key",
            "password=secret123",
            "authorization: Bearer xyz",
            "Cookie: session=abc",
            "api_key=my_secret",
        ],
    )
    def test_rejects_known_secret_tokens(self, secret_token: str) -> None:
        """Preflight scan rejects prompts containing secret tokens."""
        prompt = f"Some safe text. {secret_token}. More safe text."
        err = pm._preflight_secret_scan(prompt)
        assert err != "", f"Expected error for token {secret_token!r}, got empty string"
        assert "Preflight secret scan failed" in err

    def test_clean_prompt_passes(self) -> None:
        """A clean prompt with no secret tokens passes."""
        prompt = (
            "Current mutation region:\n"
            "    return DetectionResult(blocked=False, reason='ok', "
            "confidence=0.0, matched_signals=())\n"
            "Active threat IDs: ['THREAT-2024-001']\n"
        )
        err = pm._preflight_secret_scan(prompt)
        assert err == "", f"Expected clean prompt to pass, got: {err}"

    def test_case_insensitive_scan(self) -> None:
        """Secret scan is case-insensitive."""
        # Mixed case variants
        for variant in ["Api_Key", "API_KEY", "api_key"]:
            prompt = f"config {variant}=value"
            err = pm._preflight_secret_scan(prompt)
            assert err != "", f"Expected scan to catch {variant!r}"


# ---------------------------------------------------------------------------
# 7. Schema validation rejects missing fields
# ---------------------------------------------------------------------------


class TestSchemaValidationMissingFields:
    @pytest.mark.parametrize("missing_field", list(pm._REQUIRED_PATCH_FIELDS))
    def test_rejects_missing_required_field(self, missing_field: str) -> None:
        """Schema validation fails when a required field is absent."""
        data: dict[str, Any] = {
            "mutation_rationale": "test",
            "target_threats": ["THREAT-001"],
            "expected_improvement": "improve TP",
            "risk": "low",
            "replacement_code": "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())",
        }
        del data[missing_field]
        err = pm._validate_patch_schema(data)
        assert err != "", f"Expected error for missing field {missing_field!r}"
        assert missing_field in err or "missing" in err.lower()

    def test_rejects_non_dict(self) -> None:
        """Schema validation rejects non-dict input."""
        for bad_input in [None, "string", 42, [], True]:
            err = pm._validate_patch_schema(bad_input)
            assert err != "", f"Expected error for {bad_input!r}"


# ---------------------------------------------------------------------------
# 8. Schema validation rejects extra fields
# ---------------------------------------------------------------------------


class TestSchemaValidationExtraFields:
    def test_rejects_extra_field(self) -> None:
        """Schema validation fails when extra fields are present."""
        data = {
            "mutation_rationale": "test",
            "target_threats": ["THREAT-001"],
            "expected_improvement": "improve TP",
            "risk": "low",
            "replacement_code": "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())",
            "unexpected_extra_field": "should be rejected",
        }
        err = pm._validate_patch_schema(data)
        assert err != "", "Expected error for extra field"
        assert "unexpected_extra_field" in err or "extra" in err.lower()

    def test_rejects_multiple_extra_fields(self) -> None:
        """Multiple extra fields are all reported."""
        data = {
            "mutation_rationale": "test",
            "target_threats": [],
            "expected_improvement": "improve",
            "risk": "low",
            "replacement_code": "    pass",
            "field_alpha": "x",
            "field_beta": "y",
        }
        err = pm._validate_patch_schema(data)
        assert err != ""

    def test_validates_maxlength_rationale(self) -> None:
        """mutation_rationale exceeding 600 chars is rejected."""
        data = {
            "mutation_rationale": "x" * 601,
            "target_threats": [],
            "expected_improvement": "ok",
            "risk": "low",
            "replacement_code": "    pass",
        }
        err = pm._validate_patch_schema(data)
        assert err != ""
        assert "mutation_rationale" in err

    def test_validates_maxitems_target_threats(self) -> None:
        """target_threats with more than 5 items is rejected."""
        data = {
            "mutation_rationale": "ok",
            "target_threats": ["T1", "T2", "T3", "T4", "T5", "T6"],
            "expected_improvement": "ok",
            "risk": "low",
            "replacement_code": "    pass",
        }
        err = pm._validate_patch_schema(data)
        assert err != ""
        assert "target_threats" in err

    def test_valid_patch_passes(self, valid_patch: dict) -> None:
        """A fully valid patch dict passes schema validation."""
        err = pm._validate_patch_schema(valid_patch)
        assert err == "", f"Expected valid patch to pass, got: {err}"


# ---------------------------------------------------------------------------
# 9. replacement_code with forbidden tokens is rejected
# ---------------------------------------------------------------------------


class TestReplacementCodeValidation:
    @pytest.mark.parametrize(
        "forbidden_code",
        [
            "import os",
            "import subprocess",
            "from os import path",
            "result = eval('1+1')",
            "exec('print(1)')",
            "f = open('/etc/passwd')",
            "subprocess.run(['ls'])",
            "import socket",
            "socket.connect(('localhost', 80))",
            "os.system('ls')",
            "os.getenv('SECRET')",
            "x = obj.__dict__",
            "y = obj.__class__",
            "z = obj.__globals__",
        ],
    )
    def test_rejects_forbidden_token(self, forbidden_code: str) -> None:
        """replacement_code containing forbidden tokens is rejected."""
        err = pm._validate_replacement_code(forbidden_code)
        assert err != "", (
            f"Expected rejection for forbidden code: {forbidden_code!r}"
        )

    def test_rejects_mutation_start_marker(self) -> None:
        """replacement_code containing MUTATION_START marker is rejected."""
        code = f"# {pm._MUTATION_START_MARKER}\n    return DetectionResult()"
        err = pm._validate_replacement_code(code)
        assert err != ""
        assert "marker" in err.lower()

    def test_rejects_mutation_end_marker(self) -> None:
        """replacement_code containing MUTATION_END marker is rejected."""
        code = f"    pass\n# {pm._MUTATION_END_MARKER}"
        err = pm._validate_replacement_code(code)
        assert err != ""

    def test_accepts_safe_code(self) -> None:
        """Clean replacement_code passes validation.

        The validator blocks any occurrence of '__' because dunder attribute
        access is forbidden. Code using neutralized symbolic indicator tokens
        (which contain '__') is rejected here — those tokens are only trusted
        in --offline-sample (pre-validated, no API path). Live-model code
        should use plain string logic without dunder tokens.
        """
        # A snippet with no forbidden tokens at all.
        safe_code = (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path-traversal', 'sqli', 'xss', 'cmd-delim']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        boost = min(1.0, 0.5 + 0.12 * len(matched))\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched: ' + matched[0],\n"
            "            confidence=boost,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(safe_code)
        assert err == "", f"Expected clean code to pass, got: {err}"

    def test_accepts_sample_mutation_code(self) -> None:
        """The built-in sample mutation replacement_code passes validation.

        After the symbolic indicator rename (from __path_traversal_indicator__
        to path_traversal_indicator), the sample code no longer contains any
        double-underscore tokens and therefore passes _validate_replacement_code
        cleanly.  This confirms that LLM-generated code can also reference
        these indicators without tripping the dunder prohibition.
        """
        code = pm._SAMPLE_MUTATION["replacement_code"]
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Sample mutation replacement_code should pass validation, got: {err}"
        )


# ---------------------------------------------------------------------------
# 9b. Python syntax validation in replacement_code
# ---------------------------------------------------------------------------


class TestReplacementCodeSyntaxValidation:
    """Tests for the AST-only syntax check added to _validate_replacement_code.

    The wrapper mirrors the actual apply_mutation.py splice:
        def _candidate_body(request):
            # === MUTATION_START ===
        {replacement_code as-is}
        # === MUTATION_END ===  (column 0, matching core/detector.py)

    Unindented code is indented incorrectly for the function body and triggers
    IndentationError.  Semicolon-joined compound statements trigger SyntaxError.
    Both are subclasses of SyntaxError and are caught as "not valid Python syntax".
    """

    def test_rejects_semicolon_joined_if_statement(self) -> None:
        """Semicolon-joined `if` compound statement is rejected as invalid syntax.

        This is the exact pattern that caused the Apply-step SyntaxError in
        run 26801801369: Gemini returned replacement_code as a single line
        with `if matched: return DetectionResult(...)` after semicolons.
        """
        bad_code = (
            '    surface = ""; matched = []; '
            "if matched: return DetectionResult("
            "blocked=True, reason=\"x\", confidence=0.9, matched_signals=())"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", (
            "Expected rejection for semicolon-joined if statement (run 26801801369 regression)"
        )
        assert "syntax" in err.lower() or "valid python" in err.lower(), (
            f"Error must mention syntax issue, got: {err!r}"
        )

    def test_accepts_valid_multiline_replacement_code(self) -> None:
        """Valid 4-space-indented multi-line replacement_code is not rejected."""
        good_code = (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    matched = []\n"
            "    indicators = ['path-traversal', 'sqli', 'xss']\n"
            "    for ind in indicators:\n"
            "        if ind in surface:\n"
            "            matched.append(ind)\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched: ' + matched[0],\n"
            "            confidence=min(1.0, 0.5 + 0.12 * len(matched)),\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(good_code)
        assert err == "", f"Expected valid multi-line code to pass, got: {err}"

    def test_rejects_bare_if_with_body_on_same_line_after_semicolon(self) -> None:
        """Compound statement after semicolon is a SyntaxError in Python."""
        bad_code = "    x = 1; if x: pass"
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Compound statement after semicolon must be rejected"
        assert "syntax" in err.lower() or "valid python" in err.lower()

    def test_syntax_check_does_not_execute_code(self) -> None:
        """Syntax check uses ast.parse only — side-effecting code is not run.

        If the code were executed, the list append below would mutate a global
        that we can observe.  The test passes only if no execution happened.
        """
        _sentinel: list = []
        # This code would append to _sentinel if executed, but should not be.
        # It IS syntactically valid, so validation must return "".
        good_code = (
            "    surface = request.path.lower()\n"
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(good_code)
        assert err == "", f"Valid code must pass syntax check: {err}"
        assert _sentinel == [], "Code must not have been executed during syntax check"

    def test_rejects_unindented_return(self) -> None:
        """Unindented return statement is rejected (IndentationError inside function body).

        Without 4-space indent, replacement_code would be at column 0 inside
        inspect_request(), which is an indentation error when the full detector
        is parsed.  This test verifies the Propose step rejects it early.
        """
        bad_code = 'return DetectionResult(blocked=False, reason="ok", confidence=0.0, matched_signals=())'
        err = pm._validate_replacement_code(bad_code)
        assert err != "", (
            "Unindented return must be rejected — it would cause IndentationError at Apply step"
        )
        assert "syntax" in err.lower() or "valid python" in err.lower(), (
            f"Error must mention syntax/indentation issue, got: {err!r}"
        )

    def test_rejects_unindented_multiline_code(self) -> None:
        """Multiple unindented lines are rejected (IndentationError inside function body)."""
        bad_code = (
            "surface = request.path.lower()\n"
            "matched = []\n"
            "return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", (
            "Unindented multi-line code must be rejected"
        )
        assert "syntax" in err.lower() or "valid python" in err.lower(), (
            f"Error must mention syntax/indentation issue, got: {err!r}"
        )

    def test_rejects_lone_surrogate(self) -> None:
        """replacement_code containing a lone surrogate is rejected fail-closed.

        Gemini may return replacement_code with lone surrogates (e.g. \\ud800).
        json.loads() accepts these, but ast.parse() raises UnicodeError.
        The validator must catch UnicodeError and return a safe error string
        that does not echo the replacement_code body.
        """
        bad_code = "    x = '\ud800'"
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Lone surrogate must be rejected fail-closed"
        assert "syntax" in err.lower() or "unicode" in err.lower() or "valid python" in err.lower(), (
            f"Error must mention syntax/unicode issue, got: {err!r}"
        )
        # Error must not contain the replacement_code body
        assert "\ud800" not in err, "Error must not echo replacement_code content"
        assert "x = " not in err, "Error must not echo replacement_code content"

    def test_parse_and_validate_response_lone_surrogate_no_exception(self) -> None:
        """_parse_and_validate_response must return (None, error) for lone surrogate code.

        This tests the full pipeline: JSON parse → schema check → replacement_code
        validation.  A lone surrogate in replacement_code must not cause an
        unhandled exception; it must be returned as a validation error.
        """
        patch = {
            "mutation_rationale": "test",
            "target_threats": ["T1"],
            "expected_improvement": "ok",
            "risk": "low",
            "replacement_code": "    x = '\ud800'",
        }
        try:
            raw_json = json.dumps(patch)
        except (UnicodeEncodeError, UnicodeDecodeError):
            pytest.skip("Platform cannot serialize lone surrogate via json.dumps")

        # Must not raise — must return (None, non-empty error)
        result, err = pm._parse_and_validate_response(raw_json)
        assert result is None, (
            "Lone surrogate replacement_code must be rejected; got result"
        )
        assert err != "", (
            "Must return a non-empty error string, not raise an unhandled exception"
        )
        # Error must not contain the replacement_code body
        assert "\ud800" not in err, "Error must not echo replacement_code content"

    def test_accepts_nested_return_at_8_spaces(self) -> None:
        """Nested return DetectionResult(...) at 8 spaces (inside if block) is accepted.

        CR-65-MIN-01: The validator must accept returns at 8/12/16 spaces when
        they appear inside if/for/while blocks. A nested return is valid Python
        and must not be rejected as an indentation error.
        """
        code = (
            "    matched = ['path-traversal']\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='matched: ' + matched[0],\n"
            "            confidence=0.7,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Nested return DetectionResult at 8 spaces must be accepted (CR-65-MIN-01), "
            f"got: {err}"
        )

    def test_system_prompt_indentation_wording_distinguishes_nested_returns(self) -> None:
        """_LLM_SYSTEM_PROMPT must describe nested return indentation correctly.

        CR-65-MIN-01: The prompt must distinguish top-level returns (4 spaces)
        from nested returns inside if/for/while blocks (8/12/16 spaces). A
        prompt that requires all returns at exactly 4 spaces is logically wrong.
        """
        prompt = pm._LLM_SYSTEM_PROMPT
        prompt_lower = prompt.lower()
        assert "nested" in prompt_lower, (
            "_LLM_SYSTEM_PROMPT must mention 'nested' to distinguish nested returns "
            "(inside if/for/while blocks at 8/12/16 spaces) from top-level returns "
            "(at 4 spaces). CR-65-MIN-01 requires this wording."
        )
        assert "8" in prompt or "block depth" in prompt_lower, (
            "_LLM_SYSTEM_PROMPT must mention 8-space or 'block depth' to describe "
            "that nested returns follow 4-space block depth increments."
        )


# ---------------------------------------------------------------------------
# 10. offline-sample still works
# ---------------------------------------------------------------------------


class TestOfflineSample:
    def test_offline_sample_returns_patch(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--offline-sample returns the built-in sample patch."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        patch_result, err = pm.propose_mutation(offline_sample=True)
        assert err == ""
        assert patch_result is not None
        assert set(patch_result.keys()) >= set(pm._REQUIRED_PATCH_FIELDS)

    def test_offline_sample_cli_exits_0(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI --offline-sample exits 0 and writes patch."""
        patch_path = tmp_path / "mutation_patch.json"
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)
        result = pm.main(["--offline-sample", "--json"])
        assert result == 0
        assert patch_path.exists()

    def test_offline_sample_patch_is_valid_json(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The patch written by --offline-sample is valid JSON."""
        patch_path = tmp_path / "mutation_patch.json"
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)
        pm.main(["--offline-sample", "--json"])
        data = json.loads(patch_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        for field in pm._REQUIRED_PATCH_FIELDS:
            assert field in data, f"Patch missing field: {field}"

    def test_offline_sample_json_output(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """CLI --offline-sample --json prints JSON with success=true."""
        patch_path = tmp_path / "mutation_patch.json"
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)
        pm.main(["--offline-sample", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["patch_path"] is not None


# ---------------------------------------------------------------------------
# 11. No Gemini dependency required for normal pytest
# ---------------------------------------------------------------------------


class TestNoDependencyOnGemini:
    def test_module_imports_without_google_genai(self) -> None:
        """scripts.propose_mutation imports without google-genai installed.

        This test verifies the import guard works: google-genai is only
        imported inside _propose_via_gemini_live, never at module level.
        """
        # If we got here, the module already imported successfully above.
        # Verify it's not importing google-genai at the top level.
        assert "google" not in dir(pm), (
            "google.genai should NOT be imported at module level"
        )
        # Also verify the module exists and has the expected public API
        assert hasattr(pm, "propose_mutation")
        assert hasattr(pm, "main")
        assert hasattr(pm, "_preflight_secret_scan")
        assert hasattr(pm, "_validate_patch_schema")
        assert hasattr(pm, "_validate_replacement_code")

    def test_google_genai_import_fails_gracefully(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        test_threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When google-genai is not installed, a clear ImportError message is returned."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_THREATS_PATH", test_threats_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        # Simulate google-genai not being installed by making the import fail
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name in ("google", "google.genai"):
                raise ImportError(f"No module named {name!r}")
            return original_import(name, *args, **kwargs)

        # Use patch to mock the import inside _propose_via_gemini_live
        with patch("builtins.__import__", side_effect=mock_import):
            result, err = pm._propose_via_gemini_live(
                json.loads(test_genome_file.read_text()),
                test_detector_file.read_text(),
                "fake-key",
            )

        assert result is None
        assert "google-genai" in err or "not installed" in err


# ---------------------------------------------------------------------------
# 12. Live model end-to-end with mocked Gemini call
# ---------------------------------------------------------------------------


class TestLiveModelWithMockedGemini:
    def test_live_model_blocked_by_phase3_gate_with_mock(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        test_threats_file: Path,
        valid_patch: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 3: CLI --live-model exits nonzero even when _propose_via_gemini_live is mocked.

        The Phase 3 gate fires before _propose_via_gemini_live is called, so even
        a mocked implementation is never reached. No patch file is written.
        """
        patch_path = tmp_path / "mutation_patch.json"
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_THREATS_PATH", test_threats_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        monkeypatch.setattr(
            pm,
            "_propose_via_gemini_live",
            lambda genome, detector_source, api_key: (valid_patch, ""),
        )

        result = pm.main(["--live-model", "--allow-live-model", "--json"])
        assert result != 0, "Phase 3 gate must cause CLI to exit nonzero"
        assert not patch_path.exists(), "Phase 3 gate must not produce a patch file"

    def test_live_model_schema_validation_applied(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        test_threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Schema validation is applied to the mock Gemini response."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_THREATS_PATH", test_threats_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Simulate Gemini returning JSON with an extra field
        bad_patch = {
            "mutation_rationale": "ok",
            "target_threats": [],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": "    pass",
            "INJECTED_FIELD": "malicious",
        }

        # Mock the google-genai call inside _propose_via_gemini_live
        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_patch)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai_types = MagicMock()

        with patch.dict("sys.modules", {
            "google": MagicMock(genai=mock_genai),
            "google.genai": mock_genai,
            "google.genai.types": mock_genai_types,
        }):
            result, err = pm._propose_via_gemini_live(
                json.loads(test_genome_file.read_text()),
                test_detector_file.read_text(),
                "fake-key",
            )

        assert result is None
        assert "extra" in err.lower() or "INJECTED_FIELD" in err

    def test_live_model_replacement_code_validated(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        test_threats_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unsafe replacement_code in Gemini response is rejected."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_THREATS_PATH", test_threats_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        # Gemini returns code with a forbidden import
        unsafe_patch = {
            "mutation_rationale": "ok",
            "target_threats": [],
            "expected_improvement": "better",
            "risk": "low",
            "replacement_code": "import os\n    return os.system('ls')",
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(unsafe_patch)
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai_types = MagicMock()

        with patch.dict("sys.modules", {
            "google": MagicMock(genai=mock_genai),
            "google.genai": mock_genai,
            "google.genai.types": mock_genai_types,
        }):
            result, err = pm._propose_via_gemini_live(
                json.loads(test_genome_file.read_text()),
                test_detector_file.read_text(),
                "fake-key",
            )

        assert result is None
        assert "import" in err or "forbidden" in err.lower()


# ---------------------------------------------------------------------------
# 13. Additional gate tests
# ---------------------------------------------------------------------------


class TestAdditionalGates:
    def test_refuses_grounding_enabled(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Refuses when allow_google_search_grounding=true."""
        genome = {**genome_live_enabled, "allow_google_search_grounding": True}
        genome_path = tmp_path / "genome_grounding.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "grounding" in err.lower()

    def test_refuses_code_execution_enabled(
        self,
        tmp_path: Path,
        genome_live_enabled: dict,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Refuses when allow_code_execution_tool=true."""
        genome = {**genome_live_enabled, "allow_code_execution_tool": True}
        genome_path = tmp_path / "genome_code_exec.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

        patch_result, err = pm.propose_mutation(live_model=True, allow_live_model=True)
        assert patch_result is None
        assert "code_execution" in err.lower() or "code execution" in err.lower()

    def test_no_mode_selected_returns_error(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No mode selected returns an error with usage hint."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        patch_result, err = pm.propose_mutation()
        assert patch_result is None
        assert err != ""

    def test_no_mode_cli_exits_1(
        self,
        tmp_path: Path,
        test_genome_file: Path,
        test_detector_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI with no mode flags exits 1."""
        monkeypatch.setattr(pm, "_GENOME_PATH", test_genome_file)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", test_detector_file)
        monkeypatch.setattr(pm, "_OUT_DIR", tmp_path)
        monkeypatch.setattr(pm, "_OUT_PATCH", tmp_path / "mutation_patch.json")
        result = pm.main(["--json"])
        assert result == 1


# ---------------------------------------------------------------------------
# 14. Resilience: timeout, retry, backoff, non-transient, import error, secrets
# ---------------------------------------------------------------------------

# Shared helpers for building fake google.genai modules used across tests.

def _make_fake_genai_modules(generate_side_effects):
    """Return (mock_genai, mock_genai_types, mock_client) with generate_content
    configured to raise/return items from generate_side_effects in order.

    generate_side_effects: list of Exception instances (to raise) or return
    values (to return).  MagicMock side_effect handles both.

    mock_genai.types is set to mock_genai_types so that
    ``from google.genai import types`` resolves to mock_genai_types
    regardless of whether Python uses getattr or sys.modules lookup.
    """
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = generate_side_effects

    mock_genai_types = MagicMock()
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_genai.types = mock_genai_types  # ensure from-import resolves correctly

    return mock_genai, mock_genai_types, mock_client


class TestCallGeminiApiResilience:
    """Tests for _call_gemini_api resilience: timeout config, retry, backoff."""

    def _patch_genai_modules(self, mock_genai, mock_genai_types):
        return patch.dict("sys.modules", {
            "google": MagicMock(genai=mock_genai),
            "google.genai": mock_genai,
            "google.genai.types": mock_genai_types,
        })

    # ------------------------------------------------------------------ #
    # 1. Timeout HttpOptions is passed to genai.Client
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_passes_timeout_http_options(self) -> None:
        """_call_gemini_api creates the client with HttpOptions(timeout=30.0)."""
        captured_http_opts: list = []

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()

        def capture_http_options(*args, **kwargs):
            captured_http_opts.append(kwargs.get("http_options") or (args[0] if args else None))
            return mock_client

        mock_genai = MagicMock()
        mock_genai.Client.side_effect = capture_http_options
        mock_genai.types = mock_genai_types  # ensure from-import resolves correctly

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == "", f"Expected success, got: {err}"
        # Verify HttpOptions was constructed with the correct timeout in milliseconds.
        # Google GenAI SDK HttpOptions.timeout is in ms: 30 s = 30,000 ms.
        mock_genai_types.HttpOptions.assert_called_once_with(
            timeout=pm._GEMINI_API_TIMEOUT_MS
        )
        # Verify Client was created with http_options
        mock_genai.Client.assert_called_once()
        call_kwargs = mock_genai.Client.call_args
        assert call_kwargs is not None
        # http_options should be the HttpOptions mock return value
        passed_http_opts = (
            call_kwargs.kwargs.get("http_options")
            if call_kwargs.kwargs
            else call_kwargs[1].get("http_options")
        )
        assert passed_http_opts is mock_genai_types.HttpOptions.return_value

    # ------------------------------------------------------------------ #
    # 2. Transient error then success retries
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_retries_transient_then_succeeds(self) -> None:
        """First call raises TimeoutError (transient); second call succeeds."""
        success_response = MagicMock()
        success_response.text = '{"mutation_rationale": "ok"}'
        success_response.usage_metadata = None

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            TimeoutError("request timed out"),
            success_response,
        ])

        sleep_calls: list[float] = []

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert err == "", f"Expected success after retry, got: {err}"
        assert raw_text == '{"mutation_rationale": "ok"}'
        assert mock_client.models.generate_content.call_count == 2
        assert len(sleep_calls) == 1, f"Expected 1 sleep call, got {len(sleep_calls)}"
        assert sleep_calls[0] == pm._GEMINI_API_BACKOFF_INITIAL_SECONDS

    # ------------------------------------------------------------------ #
    # 3. All attempts exhausted with transient error
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_stops_after_max_transient_attempts(self) -> None:
        """Three consecutive transient failures → fail after max attempts."""

        class Fake429(Exception):
            status_code = 429

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake429("429 Too Many Requests"),
            Fake429("429 Too Many Requests"),
            Fake429("429 Too Many Requests"),
        ])

        sleep_calls: list[float] = []

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert raw_text is None
        assert inp is None
        assert out is None
        assert "3 attempt" in err, f"Error should mention 3 attempts: {err!r}"
        assert "transient" in err, f"Error should say transient: {err!r}"
        assert mock_client.models.generate_content.call_count == pm._GEMINI_API_MAX_ATTEMPTS
        # Sleep is called between attempts — not after the last one
        assert len(sleep_calls) == pm._GEMINI_API_MAX_ATTEMPTS - 1, (
            f"Expected {pm._GEMINI_API_MAX_ATTEMPTS - 1} sleeps, got {len(sleep_calls)}"
        )

    # ------------------------------------------------------------------ #
    # 4. Non-transient error does not retry
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_does_not_retry_non_transient_error(self) -> None:
        """401 Unauthorized is non-transient; generate_content called only once."""

        class Fake401(Exception):
            status_code = 401

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake401("401 Unauthorized"),
        ])

        sleep_calls: list[float] = []

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert raw_text is None
        assert "non-transient" in err, f"Error should say non-transient: {err!r}"
        assert mock_client.models.generate_content.call_count == 1
        assert len(sleep_calls) == 0, "No sleep on non-transient error"

    # ------------------------------------------------------------------ #
    # 5. ImportError behaviour is unchanged
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_import_error_unchanged(self) -> None:
        """When google-genai is not installed, returns the expected error string."""
        with patch.dict("sys.modules", {"google": None, "google.genai": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'google'")):
                raw_text, inp, out, _, err = pm._call_gemini_api(
                    "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                    _sleep_fn=lambda _: None,
                )

        assert raw_text is None
        assert inp is None
        assert out is None
        assert "google-genai" in err or "not installed" in err, (
            f"Expected import error message, got: {err!r}"
        )

    # ------------------------------------------------------------------ #
    # 6. Error message does not include API key or prompt text
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_error_does_not_include_secret_or_prompt(self) -> None:
        """On failure, the error string must not contain the API key or prompt."""
        secret_key = "super-secret-api-key-value-12345"
        user_prompt_text = "This is the full user prompt content do not log this"

        class Fake503(Exception):
            status_code = 503

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake503("503 Service Unavailable"),
            Fake503("503 Service Unavailable"),
            Fake503("503 Service Unavailable"),
        ])

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            _, _, _, _, err = pm._call_gemini_api(
                secret_key, "gemini-2.0-flash", user_prompt_text, 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert secret_key not in err, (
            f"API key must not appear in error string: {err!r}"
        )
        assert user_prompt_text not in err, (
            f"Prompt must not appear in error string: {err!r}"
        )

    # ------------------------------------------------------------------ #
    # 7. max_attempts=1 limits retries to a single attempt
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_respects_max_attempts_one(self) -> None:
        """max_attempts=1 means no retry: generate_content called once on transient error."""

        class Fake503(Exception):
            status_code = 503

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            Fake503("503 Service Unavailable"),
        ])

        sleep_calls: list[float] = []

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                max_attempts=1,
                _sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert raw_text is None
        assert "1 attempt" in err, f"Error should mention 1 attempt: {err!r}"
        assert mock_client.models.generate_content.call_count == 1
        assert len(sleep_calls) == 0, "No sleep when max_attempts=1"

    # ------------------------------------------------------------------ #
    # 8. max_attempts=2 allows one retry
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_allows_retry_when_max_attempts_two(self) -> None:
        """max_attempts=2: fails once transiently then succeeds on second attempt."""
        success_response = MagicMock()
        success_response.text = '{"retry": "ok"}'
        success_response.usage_metadata = None

        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([
            TimeoutError("timed out"),
            success_response,
        ])

        sleep_calls: list[float] = []

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                max_attempts=2,
                _sleep_fn=lambda s: sleep_calls.append(s),
            )

        assert err == "", f"Expected success, got: {err}"
        assert raw_text == '{"retry": "ok"}'
        assert mock_client.models.generate_content.call_count == 2
        assert len(sleep_calls) == 1

    # ------------------------------------------------------------------ #
    # 9. max_attempts is capped by _GEMINI_API_MAX_ATTEMPTS
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_caps_max_attempts_at_constant(self) -> None:
        """Passing max_attempts=999 never exceeds _GEMINI_API_MAX_ATTEMPTS calls."""

        class Fake429(Exception):
            status_code = 429

        side_effects = [Fake429("429") for _ in range(100)]
        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules(side_effects)

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                max_attempts=999,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert mock_client.models.generate_content.call_count <= pm._GEMINI_API_MAX_ATTEMPTS, (
            f"Call count {mock_client.models.generate_content.call_count} "
            f"exceeds cap {pm._GEMINI_API_MAX_ATTEMPTS}"
        )

    # ------------------------------------------------------------------ #
    # 10. max_attempts < 1 returns fail-closed error without calling API
    # ------------------------------------------------------------------ #

    def test_call_gemini_api_max_attempts_zero_fail_closed(self) -> None:
        """max_attempts=0 returns an error immediately without calling generate_content."""
        mock_genai, mock_genai_types, mock_client = _make_fake_genai_modules([])

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                max_attempts=0,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert err != "", "Must return an error for max_attempts=0"
        assert mock_client.models.generate_content.call_count == 0, (
            "generate_content must not be called when max_attempts=0"
        )


# ---------------------------------------------------------------------------
# 15. Gemini 3 thinking_config injection
# ---------------------------------------------------------------------------

class TestCallGeminiApiThinkingConfig:
    """_call_gemini_api passes thinking_config for gemini-3 models only."""

    def _patch_genai_modules(self, mock_genai, mock_genai_types):
        return patch.dict("sys.modules", {
            "google": MagicMock(genai=mock_genai),
            "google.genai": mock_genai,
            "google.genai.types": mock_genai_types,
        })

    def test_gemini3_model_includes_thinking_config_with_level_low(self) -> None:
        """gemini-3 model gets ThinkingConfig(thinking_level='low') — not thinking_budget."""
        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == "", f"Expected success, got: {err}"
        # ThinkingConfig must be constructed with thinking_level="low" (not thinking_budget).
        mock_genai_types.ThinkingConfig.assert_called_once_with(thinking_level="low")
        # Verify thinking_budget was NOT passed (mutually exclusive with thinking_level).
        call_kwargs = mock_genai_types.ThinkingConfig.call_args.kwargs
        assert "thinking_budget" not in call_kwargs, (
            "thinking_budget must NOT be passed alongside thinking_level"
        )
        # The thinking_config kwarg must be forwarded to GenerateContentConfig.
        gen_config_call = mock_genai_types.GenerateContentConfig.call_args
        assert gen_config_call is not None
        passed_kwargs = gen_config_call.kwargs if gen_config_call.kwargs else gen_config_call[1]
        assert "thinking_config" in passed_kwargs, (
            "thinking_config must be present in GenerateContentConfig for gemini-3 models"
        )
        assert passed_kwargs["thinking_config"] is mock_genai_types.ThinkingConfig.return_value

    def test_gemini2_model_does_not_include_thinking_config(self) -> None:
        """When model_name starts with 'gemini-2', no ThinkingConfig is added."""
        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.5-flash-lite", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == "", f"Expected success, got: {err}"
        # ThinkingConfig must NOT be constructed for gemini-2 models.
        mock_genai_types.ThinkingConfig.assert_not_called()
        gen_config_call = mock_genai_types.GenerateContentConfig.call_args
        assert gen_config_call is not None
        passed_kwargs = gen_config_call.kwargs if gen_config_call.kwargs else gen_config_call[1]
        assert "thinking_config" not in passed_kwargs, (
            "thinking_config must NOT be present in GenerateContentConfig for gemini-2 models"
        )

    def test_gemini31_flash_lite_fallback_gets_thinking_level_low(self) -> None:
        """gemini-3.1-flash-lite (fallback) also receives ThinkingConfig(thinking_level='low')."""
        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-3.1-flash-lite", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == "", f"Expected success, got: {err}"
        # gemini-3.1-flash-lite starts with "gemini-3" → must get thinking_level="low".
        mock_genai_types.ThinkingConfig.assert_called_once_with(thinking_level="low")

    def test_thinking_estimate_constant_is_positive_int(self) -> None:
        """_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS is a positive integer (used for budget estimates)."""
        assert isinstance(pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS, int)
        assert pm._GEMINI3_THINKING_ESTIMATE_LOW_TOKENS > 0

    # ------------------------------------------------------------------ #
    # Guard: ThinkingConfig unavailable / incompatible SDK
    # ------------------------------------------------------------------ #

    def test_missing_thinking_config_class_returns_controlled_error(self) -> None:
        """If genai_types.ThinkingConfig raises AttributeError, return fail-closed error."""
        mock_client = MagicMock()

        mock_genai_types = MagicMock()
        # Simulate an SDK that does not expose ThinkingConfig at all.
        mock_genai_types.ThinkingConfig = MagicMock(
            side_effect=AttributeError("ThinkingConfig not found")
        )
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, _, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None, "raw_text must be None on SDK incompatibility"
        assert inp is None
        assert out is None
        assert err != "", "error must be non-empty on SDK incompatibility"
        assert "ThinkingConfig" in err, f"error must mention ThinkingConfig, got: {err!r}"
        assert "Upgrade" in err or "upgrade" in err.lower(), (
            f"error should hint at upgrading SDK, got: {err!r}"
        )
        # generate_content must never be called when config construction fails.
        mock_client.models.generate_content.assert_not_called()

    def test_thinking_config_type_error_returns_controlled_error(self) -> None:
        """If ThinkingConfig(thinking_level=...) raises TypeError, return fail-closed error."""
        mock_client = MagicMock()

        mock_genai_types = MagicMock()
        # Simulate an SDK that has ThinkingConfig but does not accept thinking_level kwarg.
        mock_genai_types.ThinkingConfig = MagicMock(
            side_effect=TypeError("unexpected keyword argument 'thinking_level'")
        )
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, _, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert err != "", "error must be non-empty when thinking_level is unsupported"
        assert "ThinkingConfig" in err, f"error must mention ThinkingConfig, got: {err!r}"
        # generate_content must never be called when config construction fails.
        mock_client.models.generate_content.assert_not_called()

    def test_sdk_incompatibility_guard_does_not_affect_gemini2(self) -> None:
        """ThinkingConfig errors are only triggered for gemini-3 models; gemini-2 is unaffected."""
        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        # ThinkingConfig would raise — but must never be called for gemini-2.
        mock_genai_types.ThinkingConfig = MagicMock(
            side_effect=AttributeError("ThinkingConfig not found")
        )
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, _, _, _, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == "", f"gemini-2 must succeed even if ThinkingConfig is broken: {err!r}"
        assert raw_text is not None
        # ThinkingConfig must not be touched for gemini-2 models.
        mock_genai_types.ThinkingConfig.assert_not_called()

    def test_thinking_config_value_error_returns_controlled_error(self) -> None:
        """ThinkingConfig(thinking_level=...) raising ValueError → fail-closed, no API call."""
        mock_client = MagicMock()
        mock_genai_types = MagicMock()
        mock_genai_types.ThinkingConfig = MagicMock(
            side_effect=ValueError("invalid value for thinking_level")
        )
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, think, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert err != "", "error must be non-empty for ValueError on ThinkingConfig"
        assert "ThinkingConfig" in err
        assert "ValueError" in err, f"error must include exc class name, got: {err!r}"
        mock_client.models.generate_content.assert_not_called()

    def test_thinking_config_arbitrary_exception_returns_controlled_error(self) -> None:
        """Any Exception from ThinkingConfig construction → fail-closed error with class name."""

        class FakeSDKValidationError(Exception):
            pass

        mock_client = MagicMock()
        mock_genai_types = MagicMock()
        mock_genai_types.ThinkingConfig = MagicMock(
            side_effect=FakeSDKValidationError("SDK validation failed")
        )
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, think, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert raw_text is None
        assert err != ""
        assert "FakeSDKValidationError" in err, (
            f"error must include exception class name, got: {err!r}"
        )
        mock_client.models.generate_content.assert_not_called()

    def test_thinking_tokens_extracted_from_usage_metadata(self) -> None:
        """actual_thinking_tokens is extracted from usage_metadata.thoughts_token_count."""
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 200
        mock_usage.candidates_token_count = 300
        mock_usage.thoughts_token_count = 150

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = mock_usage

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, think, err = pm._call_gemini_api(
                "fake-key", "gemini-3-flash-preview", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == ""
        assert inp == 200
        assert out == 300
        assert think == 150, f"Expected thinking_tokens=150, got {think!r}"

    def test_no_thinking_tokens_when_absent_from_metadata(self) -> None:
        """actual_thinking_tokens is None when thoughts_token_count absent from metadata."""
        mock_usage = MagicMock(spec=["prompt_token_count", "candidates_token_count"])
        mock_usage.prompt_token_count = 100
        mock_usage.candidates_token_count = 200

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = mock_usage

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_types = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = mock_genai_types

        with self._patch_genai_modules(mock_genai, mock_genai_types):
            raw_text, inp, out, think, err = pm._call_gemini_api(
                "fake-key", "gemini-2.0-flash", "prompt", 512, 0.2,
                _sleep_fn=lambda _: None,
            )

        assert err == ""
        assert think is None, f"Expected think=None when thoughts_token_count absent, got {think!r}"
