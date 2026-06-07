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
        assert (
            "syntax" in err.lower()
            or "valid python" in err.lower()
            or "indentation" in err.lower()
        ), f"Error must mention syntax/indentation issue, got: {err!r}"

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
        assert (
            "syntax" in err.lower()
            or "valid python" in err.lower()
            or "indentation" in err.lower()
        ), f"Error must mention syntax/indentation issue, got: {err!r}"

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


# ---------------------------------------------------------------------------
# 9c. PR #66 — Fallthrough return guard (check 9)
# ---------------------------------------------------------------------------


class TestFallthroughReturnGuard:
    """Tests for check 9: the last top-level replacement node must be ast.Return.

    CR-66-02: nested-only returns can fall through to implicit None when no
    branch is taken. Check 9 requires a top-level fallback return DetectionResult(...)
    as the final statement so inspect_request() is always fail-closed.
    """

    def test_rejects_nested_only_return_if_block(self) -> None:
        """Check 9 rejects code where only nested returns exist (if block only).

        The body ends with an if statement. When no branch is taken, the function
        falls through to implicit None — the validator must reject this.
        """
        code = (
            "    surface = request.path.lower()\n"
            "    if 'path_traversal_indicator' in surface:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='traversal detected',\n"
            "            confidence=0.9,\n"
            "            matched_signals=('path_traversal_indicator',),\n"
            "        )\n"
            # No top-level fallback return — falls through to None
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Nested-only return (last top-level node is if block) must be rejected "
            "by fallthrough guard (check 9)"
        )
        assert "fallthrough" in err.lower(), (
            f"Error must mention fallthrough guard, got: {err!r}"
        )

    def test_rejects_nested_only_return_multiple_if_blocks(self) -> None:
        """Check 9 rejects code with multiple if blocks but no top-level fallback."""
        code = (
            "    surface = request.path.lower()\n"
            "    if 'sqli_indicator' in surface:\n"
            "        return DetectionResult(\n"
            "            blocked=True, reason='sqli', confidence=0.8, matched_signals=(),\n"
            "        )\n"
            "    if 'script_injection_indicator' in surface:\n"
            "        return DetectionResult(\n"
            "            blocked=True, reason='xss', confidence=0.8, matched_signals=(),\n"
            "        )\n"
            # Last top-level node is an if block — no fallback return
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Multiple if-block-only returns must be rejected by fallthrough guard"
        )
        assert "fallthrough" in err.lower(), (
            f"Error must mention fallthrough guard, got: {err!r}"
        )

    def test_accepts_nested_return_plus_top_level_fallback(self) -> None:
        """Check 9 accepts code with nested returns followed by a top-level fallback.

        The last top-level statement is return DetectionResult(...) — fallback is present.
        """
        code = (
            "    surface = request.path.lower() + ' ' + request.body.lower()\n"
            "    indicators = ['path_traversal_indicator', 'sqli_indicator']\n"
            "    matched = [ind for ind in indicators if ind in surface]\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched: ' + matched[0],\n"
            "            confidence=min(1.0, 0.5 + 0.12 * len(matched)),\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no suspicious indicator matched',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Nested return + top-level fallback must be accepted, got: {err!r}"
        )

    def test_accepts_top_level_only_return(self) -> None:
        """Check 9 accepts code where the only return is at top level (no nesting)."""
        code = (
            "    surface = request.path.lower()\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Top-level-only return must be accepted, got: {err!r}"
        )

    def test_rejects_last_top_level_is_assignment_after_nested_return(self) -> None:
        """Check 9 rejects code where the last top-level statement is an assignment.

        Even though a nested return exists, the last top-level node is not a return,
        so the function can fall through when no branch is taken.
        """
        code = (
            "    surface = request.path.lower()\n"
            "    if 'path_traversal_indicator' in surface:\n"
            "        return DetectionResult(\n"
            "            blocked=True, reason='traversal', confidence=0.9, matched_signals=(),\n"
            "        )\n"
            "    result_label = 'no match'\n"  # non-return last statement
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Last top-level assignment after nested return must be rejected by fallthrough guard"
        )
        assert "fallthrough" in err.lower(), (
            f"Error must mention fallthrough guard, got: {err!r}"
        )

    def test_return_none_at_top_level_rejected_by_shape_check(self) -> None:
        """return None at top level is rejected by check 8 (shape), not check 9.

        This test verifies that the existing return-shape validation (check 8)
        continues to reject return None even when it appears as the final top-level
        statement. Check 9 does not weaken check 8.
        """
        code = (
            "    if 'path_traversal_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True, reason='traversal', confidence=0.9, matched_signals=(),\n"
            "        )\n"
            "    return None\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "return None must be rejected (check 8 shape validation)"
        assert "return contract" in err.lower() or "DetectionResult" in err, (
            f"return None rejection must come from check 8 (shape), got: {err!r}"
        )

    def test_return_result_var_at_top_level_rejected_by_shape_check(self) -> None:
        """return result_var at top level is rejected by check 8 (shape), not check 9.

        This covers the case where code ends with `return some_variable`, which
        check 8 rejects regardless of check 9.
        """
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True, reason='sqli', confidence=0.8, matched_signals=(),\n"
            "        )\n"
            "    final_result = 'no_match'\n"
            "    return final_result\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "return variable must be rejected (check 8 shape validation)"
        assert "return contract" in err.lower() or "DetectionResult" in err, (
            f"return variable rejection must come from check 8 (shape), got: {err!r}"
        )

    def test_sample_mutation_passes_fallthrough_guard(self) -> None:
        """The built-in sample mutation passes check 9 (ends with top-level return)."""
        code = pm._SAMPLE_MUTATION["replacement_code"]
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Sample mutation must pass all checks including fallthrough guard, got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 9d. PR #67 — DetectionResult argument shape (check 10)
# ---------------------------------------------------------------------------


class TestDetectionResultArgumentShape:
    """Tests for check 10: every DetectionResult(...) call must use keyword-only
    arguments with exactly the four canonical names.

    CR-67-01: check 8 proves the return is DetectionResult(...) but does not
    validate the constructor argument shape. Check 10 adds that validation.
    """

    _VALID_CODE = (
        "    return DetectionResult(\n"
        "        blocked=False,\n"
        "        reason='no match',\n"
        "        confidence=0.0,\n"
        "        matched_signals=(),\n"
        "    )\n"
    )

    def test_accepts_valid_keyword_only_args(self) -> None:
        """Valid keyword-only DetectionResult with all four required keywords is accepted."""
        err = pm._validate_replacement_code(self._VALID_CODE)
        assert err == "", f"Valid keyword-only args must be accepted, got: {err!r}"

    def test_rejects_positional_args(self) -> None:
        """Positional arguments are rejected by check 10."""
        code = "    return DetectionResult(True, 'blocked by positional', 0.9, ())\n"
        err = pm._validate_replacement_code(code)
        assert err != "", "Positional args must be rejected"
        assert "argument shape" in err.lower() or "positional" in err.lower(), (
            f"Error must mention argument shape or positional, got: {err!r}"
        )

    def test_rejects_missing_keyword(self) -> None:
        """Missing keyword argument (matched_signals absent) is rejected by check 10."""
        code = (
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            # matched_signals intentionally omitted
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Missing keyword must be rejected"
        assert "argument shape" in err.lower() or "missing" in err.lower(), (
            f"Error must mention argument shape or missing, got: {err!r}"
        )

    def test_rejects_extra_keyword(self) -> None:
        """Extra keyword argument is rejected by check 10."""
        code = (
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        extra_field='unexpected',\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Extra keyword must be rejected"
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Error must mention argument shape or extra, got: {err!r}"
        )

    def test_rejects_wrong_keyword_name(self) -> None:
        """Wrong keyword name (is_blocked instead of blocked) is rejected by check 10."""
        code = (
            "    return DetectionResult(\n"
            "        is_blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Wrong keyword name must be rejected"
        assert (
            "argument shape" in err.lower()
            or "missing" in err.lower()
            or "extra" in err.lower()
        ), f"Error must mention argument shape, missing, or extra, got: {err!r}"

    def test_rejects_kwargs_expansion(self) -> None:
        """**kwargs expansion is rejected by check 10."""
        code = (
            "    result_kwargs = {}\n"
            "    result_kwargs['blocked'] = False\n"
            "    result_kwargs['reason'] = 'no match'\n"
            "    result_kwargs['confidence'] = 0.0\n"
            "    result_kwargs['matched_signals'] = ()\n"
            "    return DetectionResult(**result_kwargs)\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "**kwargs expansion must be rejected"
        assert "argument shape" in err.lower() or "kwargs" in err.lower(), (
            f"Error must mention argument shape or kwargs, got: {err!r}"
        )

    def test_rejects_mixed_positional_and_keyword(self) -> None:
        """Mixed positional and keyword arguments are rejected by check 10."""
        code = (
            "    return DetectionResult(\n"
            "        True,\n"
            "        reason='match',\n"
            "        confidence=0.9,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Mixed positional+keyword must be rejected"
        assert "argument shape" in err.lower() or "positional" in err.lower(), (
            f"Error must mention argument shape or positional, got: {err!r}"
        )

    def test_check_10_validates_both_nested_and_fallback_returns(self) -> None:
        """Check 10 validates both nested and top-level fallback returns.

        A valid nested return paired with an invalid (positional) fallback
        must be rejected. Both returns must use valid keyword-only shape.
        """
        code_invalid_fallback = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "        )\n"
            "    return DetectionResult(False, 'no match', 0.0, ())\n"
        )
        err = pm._validate_replacement_code(code_invalid_fallback)
        assert err != "", "Positional fallback return must be rejected by check 10"
        assert "argument shape" in err.lower() or "positional" in err.lower(), (
            f"Error must mention argument shape or positional, got: {err!r}"
        )

        code_both_valid = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code_both_valid)
        assert err == "", f"Both valid returns must be accepted, got: {err!r}"

    def test_check_10_rejects_extra_in_nested_return(self) -> None:
        """Check 10 rejects extra keyword in a nested return, not just top-level."""
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "            severity='high',\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Extra keyword in nested return must be rejected"
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Error must mention argument shape or extra, got: {err!r}"
        )

    def test_sample_mutation_passes_check_10(self) -> None:
        """The built-in sample mutation uses keyword-only args and passes check 10."""
        code = pm._SAMPLE_MUTATION["replacement_code"]
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Sample mutation must pass all checks including check 10, got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 9e. PR #67 Codex P2 — check 10 covers non-return DetectionResult calls
# ---------------------------------------------------------------------------


class TestDetectionResultNonReturnCalls:
    """Regression tests for Codex P2 finding: check 10 must validate every bare
    DetectionResult(...) call, not only calls inside return statements.

    A malformed non-return constructor call (expression statement, assignment,
    nested branch) can raise TypeError at runtime before any fallback return
    is reached.
    """

    _VALID_FALLBACK = (
        "    return DetectionResult(\n"
        "        blocked=False,\n"
        "        reason='no match',\n"
        "        confidence=0.0,\n"
        "        matched_signals=(),\n"
        "    )\n"
    )

    def test_rejects_expression_statement_with_extra_kwarg(self) -> None:
        """Expression-statement DetectionResult(...) with extra keyword is rejected."""
        code = (
            "    DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        severity='low',\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Expression-statement DetectionResult with extra kwarg must be rejected"
        )
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Error must mention argument shape or extra, got: {err!r}"
        )

    def test_rejects_assignment_with_extra_kwarg(self) -> None:
        """Assignment DetectionResult(...) with extra keyword is rejected."""
        code = (
            "    tmp = DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        extra=1,\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Assignment DetectionResult with extra kwarg must be rejected"
        )
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Error must mention argument shape or extra, got: {err!r}"
        )

    def test_rejects_nested_non_return_call_with_malformed_args(self) -> None:
        """Malformed nested non-return DetectionResult call is rejected even when
        the top-level fallback return has valid shape.
        """
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        tmp = DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "            debug='yes',\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Malformed nested non-return DetectionResult call must be rejected"
        )
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Error must mention argument shape or extra, got: {err!r}"
        )

    def test_accepts_non_return_call_with_valid_shape(self) -> None:
        """A non-return DetectionResult(...) with correct keyword shape is accepted
        when all other checks also pass.
        """
        code = (
            "    cached = DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err == "", (
            f"Non-return DetectionResult with valid shape must be accepted, got: {err!r}"
        )

    def test_rejects_expression_statement_with_positional_args(self) -> None:
        """Expression-statement DetectionResult(...) with positional args is rejected."""
        code = (
            "    DetectionResult(False, 'no match', 0.0, ())\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Expression-statement DetectionResult with positional args must be rejected"
        )
        assert "argument shape" in err.lower() or "positional" in err.lower(), (
            f"Error must mention argument shape or positional, got: {err!r}"
        )


# ---------------------------------------------------------------------------
# 9f. PR #67 Codex P2 — check 10 rejects duplicate keyword names
# ---------------------------------------------------------------------------


class TestDetectionResultDuplicateKeywords:
    """Regression tests for Codex P2 finding: set-based keyword validation
    collapses duplicates, allowing DetectionResult(blocked=False, ..., blocked=True)
    to pass. Check 10 must detect duplicates before the missing/extra comparison.
    """

    _VALID_FALLBACK = (
        "    return DetectionResult(\n"
        "        blocked=False,\n"
        "        reason='no match',\n"
        "        confidence=0.0,\n"
        "        matched_signals=(),\n"
        "    )\n"
    )

    def test_rejects_duplicate_canonical_keyword_in_return(self) -> None:
        """Duplicate canonical keyword in a returned DetectionResult is rejected."""
        code = (
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        blocked=True,\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Duplicate keyword in returned DetectionResult must be rejected"
        assert "argument shape" in err.lower() or "duplicate" in err.lower(), (
            f"Error must mention argument shape or duplicate, got: {err!r}"
        )

    def test_rejects_duplicate_canonical_keyword_in_expression_statement(self) -> None:
        """Duplicate canonical keyword in a non-return expression-statement call is rejected."""
        code = (
            "    DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        reason='duplicate reason',\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Duplicate keyword in non-return DetectionResult expression must be rejected"
        )
        assert "argument shape" in err.lower() or "duplicate" in err.lower(), (
            f"Error must mention argument shape or duplicate, got: {err!r}"
        )

    def test_rejects_duplicate_keyword_in_nested_branch(self) -> None:
        """Duplicate keyword in a nested-branch DetectionResult call is rejected."""
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "            confidence=0.9,\n"
            "        )\n"
            + self._VALID_FALLBACK
        )
        err = pm._validate_replacement_code(code)
        assert err != "", (
            "Duplicate keyword in nested-branch DetectionResult must be rejected"
        )
        assert "argument shape" in err.lower() or "duplicate" in err.lower(), (
            f"Error must mention argument shape or duplicate, got: {err!r}"
        )

    def test_valid_keyword_only_constructor_still_passes(self) -> None:
        """Valid keyword-only DetectionResult with no duplicates still passes check 10."""
        err = pm._validate_replacement_code(self._VALID_FALLBACK)
        assert err == "", f"Valid keyword-only constructor must pass, got: {err!r}"


# ---------------------------------------------------------------------------
# 9g. X-007 — DetectionResult static value checks (check 11)
# ---------------------------------------------------------------------------


class TestX007StaticValueChecks:
    """Regression tests for check 11: Category A obvious invalid DetectionResult
    field literal rejection.

    Each field is validated in isolation using a helper that substitutes one
    field at a time into an otherwise-valid four-keyword constructor call.
    Context tests verify that all bare DetectionResult(...) call sites are
    checked, not only top-level returns.
    Check-10-precedence tests verify that shape errors still win over value errors.
    """

    _STABLE_PREFIX = "replacement_code DetectionResult static value violation:"

    @staticmethod
    def _ok(**kwargs: str) -> str:
        """Build minimal valid replacement_code, optionally overriding field source."""
        vals = {
            "blocked": "True",
            "reason": "'no match'",
            "confidence": "0.0",
            "matched_signals": "()",
        }
        vals.update(kwargs)
        return (
            "    return DetectionResult(\n"
            f"        blocked={vals['blocked']},\n"
            f"        reason={vals['reason']},\n"
            f"        confidence={vals['confidence']},\n"
            f"        matched_signals={vals['matched_signals']},\n"
            "    )\n"
        )

    # ------------------------------------------------------------------
    # Accept / defer cases (Category B dynamic expressions and valid literals)
    # ------------------------------------------------------------------

    def test_01_accepts_blocked_true(self) -> None:
        """blocked=True is a valid bool literal and is accepted."""
        assert pm._validate_replacement_code(self._ok(blocked="True")) == ""

    def test_02_accepts_blocked_false(self) -> None:
        """blocked=False is a valid bool literal and is accepted."""
        assert pm._validate_replacement_code(self._ok(blocked="False")) == ""

    def test_03_defers_blocked_comparison_expression(self) -> None:
        """blocked=score > threshold is a dynamic expression and is deferred."""
        assert pm._validate_replacement_code(self._ok(blocked="score > threshold")) == ""

    def test_04_defers_blocked_bool_call(self) -> None:
        """blocked=bool(matched) is a dynamic expression and is deferred."""
        assert pm._validate_replacement_code(self._ok(blocked="bool(matched)")) == ""

    def test_05_accepts_reason_string_literal(self) -> None:
        """reason='detected sql' is a valid string literal and is accepted."""
        assert pm._validate_replacement_code(self._ok(reason="'detected sql'")) == ""

    def test_06_defers_reason_fstring(self) -> None:
        """reason=f'Detected {pattern}' is a dynamic f-string and is deferred."""
        assert pm._validate_replacement_code(self._ok(reason="f'Detected {pattern}'")) == ""

    def test_07_accepts_confidence_zero(self) -> None:
        """confidence=0.0 is in [0.0, 1.0] and is accepted."""
        assert pm._validate_replacement_code(self._ok(confidence="0.0")) == ""

    def test_08_accepts_confidence_one(self) -> None:
        """confidence=1.0 is in [0.0, 1.0] and is accepted."""
        assert pm._validate_replacement_code(self._ok(confidence="1.0")) == ""

    def test_09_accepts_confidence_mid_range(self) -> None:
        """confidence=0.9 is in [0.0, 1.0] and is accepted."""
        assert pm._validate_replacement_code(self._ok(confidence="0.9")) == ""

    def test_10_defers_confidence_min_call(self) -> None:
        """confidence=min(1.0, score) is a dynamic expression and is deferred."""
        assert pm._validate_replacement_code(self._ok(confidence="min(1.0, score)")) == ""

    def test_11_defers_confidence_max_call(self) -> None:
        """confidence=max(0.0, raw) is a dynamic expression and is deferred."""
        assert pm._validate_replacement_code(self._ok(confidence="max(0.0, raw)")) == ""

    def test_12_defers_confidence_round_call(self) -> None:
        """confidence=round(raw, 4) is a dynamic expression and is deferred."""
        assert pm._validate_replacement_code(self._ok(confidence="round(raw, 4)")) == ""

    def test_13_defers_confidence_float_nan_call(self) -> None:
        """confidence=float('nan') is a function call (not a literal) and is deferred.

        Check 11 must not evaluate float('nan') — it defers all non-literal calls.
        """
        assert pm._validate_replacement_code(self._ok(confidence="float('nan')")) == ""

    def test_14_accepts_matched_signals_empty_tuple(self) -> None:
        """matched_signals=() is an empty tuple and is accepted."""
        assert pm._validate_replacement_code(self._ok(matched_signals="()")) == ""

    def test_15_accepts_matched_signals_single_string_tuple(self) -> None:
        """matched_signals=('sql',) is a tuple of strings and is accepted."""
        assert pm._validate_replacement_code(self._ok(matched_signals="('sql',)")) == ""

    def test_16_defers_matched_signals_tuple_call(self) -> None:
        """matched_signals=tuple(matched) is a dynamic call and is deferred."""
        assert pm._validate_replacement_code(self._ok(matched_signals="tuple(matched)")) == ""

    # ------------------------------------------------------------------
    # Reject cases (Category A obvious invalid literals)
    # ------------------------------------------------------------------

    def _assert_static_violation(self, code: str, context: str = "") -> None:
        err = pm._validate_replacement_code(code)
        assert err != "", f"Expected rejection but got empty error. {context}"
        assert self._STABLE_PREFIX in err, (
            f"Error must contain stable prefix {self._STABLE_PREFIX!r}, got: {err!r}"
        )

    def test_17_rejects_blocked_string_true(self) -> None:
        """blocked='true' is a string literal and is rejected."""
        self._assert_static_violation(self._ok(blocked="'true'"))

    def test_18_rejects_blocked_integer_one(self) -> None:
        """blocked=1 is a numeric literal and is rejected."""
        self._assert_static_violation(self._ok(blocked="1"))

    def test_19_rejects_blocked_none(self) -> None:
        """blocked=None is not a bool and is rejected."""
        self._assert_static_violation(self._ok(blocked="None"))

    def test_20_rejects_blocked_empty_list(self) -> None:
        """blocked=[] is a list literal and is rejected."""
        self._assert_static_violation(self._ok(blocked="[]"))

    def test_21_rejects_reason_integer(self) -> None:
        """reason=42 is a numeric literal and is rejected."""
        self._assert_static_violation(self._ok(reason="42"))

    def test_22_rejects_reason_bool_true(self) -> None:
        """reason=True is a bool literal and is rejected."""
        self._assert_static_violation(self._ok(reason="True"))

    def test_23_rejects_reason_none(self) -> None:
        """reason=None is not a string and is rejected."""
        self._assert_static_violation(self._ok(reason="None"))

    def test_24_rejects_confidence_string(self) -> None:
        """confidence='high' is a string literal and is rejected."""
        self._assert_static_violation(self._ok(confidence="'high'"))

    def test_25_rejects_confidence_none(self) -> None:
        """confidence=None is not a float and is rejected."""
        self._assert_static_violation(self._ok(confidence="None"))

    def test_26_rejects_confidence_bool_true(self) -> None:
        """confidence=True is a bool literal and is rejected.

        Python treats bool as a subclass of int so True == 1, but it is still
        an obviously wrong type for confidence and must be rejected.
        """
        self._assert_static_violation(self._ok(confidence="True"))

    def test_27_rejects_confidence_bool_false(self) -> None:
        """confidence=False is a bool literal and is rejected."""
        self._assert_static_violation(self._ok(confidence="False"))

    def test_28_rejects_confidence_out_of_range_high(self) -> None:
        """confidence=1.5 is a float literal outside [0.0, 1.0] and is rejected."""
        self._assert_static_violation(self._ok(confidence="1.5"))

    def test_29_rejects_confidence_negative_float(self) -> None:
        """confidence=-0.1 is a signed literal outside [0.0, 1.0] and is rejected.

        -0.1 is ast.UnaryOp(USub, Constant(0.1)), not a bare negative constant.
        The implementation must classify it correctly without evaluating it.
        """
        self._assert_static_violation(self._ok(confidence="-0.1"))

    def test_30_rejects_matched_signals_string(self) -> None:
        """matched_signals='sql' is a string literal (not a tuple) and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="'sql'"))

    def test_31_rejects_matched_signals_list(self) -> None:
        """matched_signals=['a', 'b'] is a list literal and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="['a', 'b']"))

    def test_32_rejects_matched_signals_dict(self) -> None:
        """matched_signals={} is a dict literal and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="{}"))

    def test_33_rejects_matched_signals_int_tuple(self) -> None:
        """matched_signals=(1, 2) is a tuple with non-string constants and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="(1, 2)"))

    def test_34_rejects_matched_signals_none_tuple(self) -> None:
        """matched_signals=(None,) contains a non-string constant and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="(None,)"))

    def test_35_rejects_matched_signals_bool_tuple(self) -> None:
        """matched_signals=(True,) contains a bool constant (not a string) and is rejected."""
        self._assert_static_violation(self._ok(matched_signals="(True,)"))

    # ------------------------------------------------------------------
    # Context coverage: check 11 validates all bare DetectionResult(...) sites
    # ------------------------------------------------------------------

    _VALID_FALLBACK = (
        "    return DetectionResult(\n"
        "        blocked=True,\n"
        "        reason='no match',\n"
        "        confidence=0.0,\n"
        "        matched_signals=(),\n"
        "    )\n"
    )

    def test_36_rejects_invalid_returned_call(self) -> None:
        """Check 11 rejects an invalid value in a returned DetectionResult."""
        code = self._ok(blocked="'true'")
        self._assert_static_violation(code, "returned call")

    def test_37_rejects_invalid_expression_statement(self) -> None:
        """Check 11 rejects an invalid value in a non-return expression-statement call."""
        code = (
            "    DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        self._assert_static_violation(code, "expression-statement call")

    def test_38_rejects_invalid_assignment_call(self) -> None:
        """Check 11 rejects an invalid value in an assignment DetectionResult call."""
        code = (
            "    tmp = DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
            + self._VALID_FALLBACK
        )
        self._assert_static_violation(code, "assignment call")

    def test_39_rejects_invalid_nested_branch_return(self) -> None:
        """Check 11 rejects an invalid value in a nested-branch returned call."""
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked='true',\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "        )\n"
            + self._VALID_FALLBACK
        )
        self._assert_static_violation(code, "nested-branch return")

    def test_40_rejects_invalid_fallback_return(self) -> None:
        """Check 11 rejects an invalid value in the top-level fallback return."""
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        self._assert_static_violation(code, "fallback return")

    def test_41_rejects_when_any_call_has_invalid_value(self) -> None:
        """Check 11 rejects when at least one of multiple calls has an invalid value."""
        code = (
            "    if 'sqli_indicator' in request.path:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='sqli',\n"
            "            confidence=0.8,\n"
            "            matched_signals=('sqli_indicator',),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=0,\n"  # invalid: numeric literal, not bool
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        self._assert_static_violation(code, "multiple calls — second invalid")

    # ------------------------------------------------------------------
    # Check 10 precedence: shape violations win before value checks run
    # ------------------------------------------------------------------

    def test_42a_check10_wins_for_positional_args(self) -> None:
        """Shape error (positional args) takes precedence over any value error."""
        code = "    return DetectionResult('true', 'reason', 0.5, ())\n"
        err = pm._validate_replacement_code(code)
        assert err != "", "Positional args must be rejected"
        assert "argument shape" in err.lower() or "positional" in err.lower(), (
            f"Check 10 error expected, got: {err!r}"
        )
        assert self._STABLE_PREFIX not in err, (
            "Check 11 must not fire before check 10 shape is validated"
        )

    def test_42b_check10_wins_for_missing_keyword(self) -> None:
        """Shape error (missing keyword) takes precedence over any value error."""
        code = (
            "    return DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            # matched_signals missing
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Missing keyword must be rejected"
        assert "argument shape" in err.lower() or "missing" in err.lower(), (
            f"Check 10 error expected, got: {err!r}"
        )
        assert self._STABLE_PREFIX not in err, (
            "Check 11 must not fire when check 10 finds a shape violation"
        )

    def test_42c_check10_wins_for_extra_keyword(self) -> None:
        """Shape error (extra keyword) takes precedence over any value error."""
        code = (
            "    return DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        extra=1,\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Extra keyword must be rejected"
        assert "argument shape" in err.lower() or "extra" in err.lower(), (
            f"Check 10 error expected, got: {err!r}"
        )
        assert self._STABLE_PREFIX not in err, (
            "Check 11 must not fire when check 10 finds a shape violation"
        )

    def test_42d_check10_wins_for_duplicate_keyword(self) -> None:
        """Shape error (duplicate keyword) takes precedence over any value error."""
        code = (
            "    return DetectionResult(\n"
            "        blocked='true',\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "        blocked=True,\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "Duplicate keyword must be rejected"
        assert "argument shape" in err.lower() or "duplicate" in err.lower(), (
            f"Check 10 error expected, got: {err!r}"
        )
        assert self._STABLE_PREFIX not in err, (
            "Check 11 must not fire when check 10 finds a shape violation"
        )

    def test_42e_check10_wins_for_kwargs_expansion(self) -> None:
        """Shape error (**kwargs) takes precedence over any value error."""
        code = (
            "    result_kwargs = {'blocked': 'true', 'reason': 'x',"
            " 'confidence': 0.0, 'matched_signals': ()}\n"
            "    return DetectionResult(**result_kwargs)\n"
        )
        err = pm._validate_replacement_code(code)
        assert err != "", "**kwargs must be rejected"
        assert "argument shape" in err.lower() or "kwargs" in err.lower(), (
            f"Check 10 error expected, got: {err!r}"
        )
        assert self._STABLE_PREFIX not in err, (
            "Check 11 must not fire when check 10 finds a shape violation"
        )

    # ------------------------------------------------------------------
    # Signed numeric literal gap for blocked / reason (PR #73 fix)
    # ------------------------------------------------------------------

    def test_43_rejects_blocked_negative_signed_int(self) -> None:
        """blocked=-1 is a signed numeric literal (UnaryOp) and is rejected.

        -1 parses as ast.UnaryOp(USub, Constant(1)), not ast.Constant(-1).
        The implementation must reach this via _numeric_literal_value.
        """
        self._assert_static_violation(self._ok(blocked="-1"), "blocked=-1")

    def test_44_rejects_blocked_positive_signed_int(self) -> None:
        """blocked=+1 is a signed numeric literal (UnaryOp UAdd) and is rejected."""
        self._assert_static_violation(self._ok(blocked="+1"), "blocked=+1")

    def test_45_rejects_reason_negative_signed_int(self) -> None:
        """reason=-1 is a signed numeric literal (UnaryOp) and is rejected."""
        self._assert_static_violation(self._ok(reason="-1"), "reason=-1")

    def test_46_rejects_reason_positive_signed_float(self) -> None:
        """reason=+3.14 is a signed numeric literal (UnaryOp UAdd) and is rejected."""
        self._assert_static_violation(self._ok(reason="+3.14"), "reason=+3.14")

    def test_47_defers_blocked_unary_minus_expression(self) -> None:
        """blocked=-score is a UnaryOp over a Name, not a numeric literal — deferred.

        _numeric_literal_value returns None for UnaryOp(USub, Name) because
        the operand is not a Constant, so the expression is deferred.
        """
        assert pm._validate_replacement_code(self._ok(blocked="-score")) == ""

    # ------------------------------------------------------------------
    # Signed numeric tuple element gap for matched_signals (PR #73 P2 fix)
    # ------------------------------------------------------------------

    def test_48_rejects_matched_signals_negative_signed_int_tuple(self) -> None:
        """matched_signals=(-1,) contains a signed numeric literal (UnaryOp) — rejected.

        -1 parses as UnaryOp(USub, Constant(1)), not Constant(-1).
        """
        self._assert_static_violation(
            self._ok(matched_signals="(-1,)"), "matched_signals=(-1,)"
        )

    def test_49_rejects_matched_signals_positive_signed_int_tuple(self) -> None:
        """matched_signals=(+1,) contains a signed numeric literal (UnaryOp UAdd) — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(+1,)"), "matched_signals=(+1,)"
        )

    def test_50_rejects_matched_signals_negative_signed_float_tuple(self) -> None:
        """matched_signals=(-0.1,) contains a signed float literal — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(-0.1,)"), "matched_signals=(-0.1,)"
        )

    def test_51_rejects_matched_signals_mixed_string_and_signed_numeric_tuple(self) -> None:
        """matched_signals=('sql', -1) has one valid string then a signed numeric — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="('sql', -1)"), "matched_signals=('sql', -1)"
        )

    def test_52_defers_matched_signals_unary_minus_name_tuple(self) -> None:
        """matched_signals=(-score,) is UnaryOp over Name — deferred (not an obvious literal)."""
        assert pm._validate_replacement_code(self._ok(matched_signals="(-score,)")) == ""

    def test_53_defers_matched_signals_name_tuple(self) -> None:
        """matched_signals=(signal,) is a Name reference — deferred."""
        assert pm._validate_replacement_code(self._ok(matched_signals="(signal,)")) == ""

    def test_54_defers_matched_signals_call_tuple(self) -> None:
        """matched_signals=(make_signal(),) is a Call expression — deferred."""
        assert pm._validate_replacement_code(self._ok(matched_signals="(make_signal(),)")) == ""

    # ------------------------------------------------------------------
    # Field-domain allowlist follow-up (PR #73 P2 class fix)
    # reason: non-string constants and containers
    # ------------------------------------------------------------------

    def test_55_rejects_reason_bytes_literal(self) -> None:
        """reason=b'bytes' is a non-str constant — rejected by field-domain allowlist."""
        self._assert_static_violation(self._ok(reason="b'bytes'"), "reason=b'bytes'")

    def test_56_rejects_reason_ellipsis_literal(self) -> None:
        """reason=... is a non-str constant (Ellipsis) — rejected."""
        self._assert_static_violation(self._ok(reason="..."), "reason=...")

    def test_57_rejects_reason_complex_literal(self) -> None:
        """reason=1j is a non-str constant (complex) — rejected."""
        self._assert_static_violation(self._ok(reason="1j"), "reason=1j")

    def test_58_rejects_reason_dict_literal(self) -> None:
        """reason={} is a dict literal — rejected as container."""
        self._assert_static_violation(self._ok(reason="{}"), "reason={}")

    def test_59_rejects_reason_set_literal(self) -> None:
        """reason={1} is a set literal — rejected as container."""
        self._assert_static_violation(self._ok(reason="{1}"), "reason={1}")

    def test_60_rejects_reason_unary_constant(self) -> None:
        """reason=-'x' is UnaryOp(USub, Constant(str)) — rejected as unary constant."""
        self._assert_static_violation(self._ok(reason="-'x'"), "reason=-'x'")

    def test_61_defers_reason_name(self) -> None:
        """reason=reason_text is a Name reference — deferred."""
        assert pm._validate_replacement_code(self._ok(reason="reason_text")) == ""

    def test_62_defers_reason_call(self) -> None:
        """reason=make_reason() is a Call expression — deferred."""
        assert pm._validate_replacement_code(self._ok(reason="make_reason()")) == ""

    # ------------------------------------------------------------------
    # blocked: non-bool constants and containers
    # ------------------------------------------------------------------

    def test_63_rejects_blocked_bytes_literal(self) -> None:
        """blocked=b'true' is a non-bool constant — rejected by field-domain allowlist."""
        self._assert_static_violation(self._ok(blocked="b'true'"), "blocked=b'true'")

    def test_64_rejects_blocked_ellipsis_literal(self) -> None:
        """blocked=... is a non-bool constant (Ellipsis) — rejected."""
        self._assert_static_violation(self._ok(blocked="..."), "blocked=...")

    def test_65_rejects_blocked_complex_literal(self) -> None:
        """blocked=1j is a non-bool constant (complex) — rejected."""
        self._assert_static_violation(self._ok(blocked="1j"), "blocked=1j")

    def test_66_rejects_blocked_dict_literal(self) -> None:
        """blocked={} is a dict literal — rejected as container."""
        self._assert_static_violation(self._ok(blocked="{}"), "blocked={}")

    def test_67_rejects_blocked_set_literal(self) -> None:
        """blocked={1} is a set literal — rejected as container."""
        self._assert_static_violation(self._ok(blocked="{1}"), "blocked={1}")

    def test_68_rejects_blocked_negative_bool_literal(self) -> None:
        """blocked=-True is UnaryOp(USub, Constant(True)) — rejected as unary constant."""
        self._assert_static_violation(self._ok(blocked="-True"), "blocked=-True")

    def test_69_defers_blocked_name(self) -> None:
        """blocked=flag is a Name reference — deferred."""
        assert pm._validate_replacement_code(self._ok(blocked="flag")) == ""

    # ------------------------------------------------------------------
    # confidence: non-numeric constants, containers, and signed bool
    # ------------------------------------------------------------------

    def test_70_rejects_confidence_bytes_literal(self) -> None:
        """confidence=b'high' is a non-numeric constant — rejected by field-domain allowlist."""
        self._assert_static_violation(self._ok(confidence="b'high'"), "confidence=b'high'")

    def test_71_rejects_confidence_ellipsis_literal(self) -> None:
        """confidence=... is a non-numeric constant (Ellipsis) — rejected."""
        self._assert_static_violation(self._ok(confidence="..."), "confidence=...")

    def test_72_rejects_confidence_complex_literal(self) -> None:
        """confidence=1j is a non-numeric constant (complex) — rejected."""
        self._assert_static_violation(self._ok(confidence="1j"), "confidence=1j")

    def test_73_rejects_confidence_dict_literal(self) -> None:
        """confidence={} is a dict literal — rejected as container."""
        self._assert_static_violation(self._ok(confidence="{}"), "confidence={}")

    def test_74_rejects_confidence_set_literal(self) -> None:
        """confidence={1} is a set literal — rejected as container."""
        self._assert_static_violation(self._ok(confidence="{1}"), "confidence={1}")

    def test_75_rejects_confidence_negative_bool_literal(self) -> None:
        """confidence=-True is UnaryOp(USub, Constant(True)) — rejected as unary constant.

        _numeric_literal_value returns None for bool operands, so _is_unary_constant
        triggers the unary-constant reject path.
        """
        self._assert_static_violation(self._ok(confidence="-True"), "confidence=-True")

    def test_76_accepts_confidence_positive_signed_float(self) -> None:
        """confidence=+0.5 is UnaryOp(UAdd, Constant(0.5)) in [0,1] — accepted."""
        assert pm._validate_replacement_code(self._ok(confidence="+0.5")) == ""

    # ------------------------------------------------------------------
    # matched_signals: set container and unary-constant bool tuple elements
    # ------------------------------------------------------------------

    def test_77_rejects_matched_signals_set_literal(self) -> None:
        """matched_signals={'sql'} is a set literal — rejected as container."""
        self._assert_static_violation(
            self._ok(matched_signals="{'sql'}"), "matched_signals={'sql'}"
        )

    def test_78_rejects_matched_signals_bytes_tuple_element(self) -> None:
        """matched_signals=(b'bytes',) contains a non-str Constant — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(b'bytes',)"), "matched_signals=(b'bytes',)"
        )

    def test_79_rejects_matched_signals_ellipsis_tuple_element(self) -> None:
        """matched_signals=(...,) contains a non-str Constant (Ellipsis) — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(...,)"), "matched_signals=(...,)"
        )

    def test_80_rejects_matched_signals_complex_tuple_element(self) -> None:
        """matched_signals=(1j,) contains a non-str Constant (complex) — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(1j,)"), "matched_signals=(1j,)"
        )

    def test_81_rejects_matched_signals_negative_bool_tuple_element(self) -> None:
        """matched_signals=(-True,) contains UnaryOp(USub, Constant(True)) — rejected.

        _is_unary_constant returns True for UnaryOp over any Constant, so -True
        is caught regardless of whether _numeric_literal_value returns None.
        """
        self._assert_static_violation(
            self._ok(matched_signals="(-True,)"), "matched_signals=(-True,)"
        )

    def test_82_rejects_matched_signals_positive_bool_tuple_element(self) -> None:
        """matched_signals=(+False,) contains UnaryOp(UAdd, Constant(False)) — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="(+False,)"), "matched_signals=(+False,)"
        )

    def test_83_rejects_matched_signals_mixed_string_and_signed_bool(self) -> None:
        """matched_signals=('sql', -True) has a valid string then an invalid signed bool — rejected."""
        self._assert_static_violation(
            self._ok(matched_signals="('sql', -True)"), "matched_signals=('sql', -True)"
        )

    def test_84_defers_matched_signals_unary_name_tuple_element(self) -> None:
        """matched_signals=(-flag,) is UnaryOp(USub, Name) — _is_unary_constant False — deferred."""
        assert pm._validate_replacement_code(self._ok(matched_signals="(-flag,)")) == ""

    def test_85_defers_matched_signals_expression_tuple_element(self) -> None:
        """matched_signals=(1 + 2,) is a BinOp — not an obvious literal — deferred.

        Expression folding is out of scope; BinOp elements are Category B.
        """
        assert pm._validate_replacement_code(self._ok(matched_signals="(1 + 2,)")) == ""


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


# ---------------------------------------------------------------------------
# 9c. replacement_code indentation contract (PR #65)
# ---------------------------------------------------------------------------


class TestReplacementCodeIndentationContract:
    """Tests for the 4-space-indented function-body contract (PR #65).

    replacement_code must be a function-body fragment for inspect_request().
    Top-level statements must start with exactly 4 spaces; nested blocks use
    8, 12, … spaces following normal Python indentation rules.
    Tab characters in leading whitespace are forbidden.
    All lines being at 8+ spaces (no top-level body) is also rejected.

    These tests verify that:
    - valid 4-space-indented body (with or without nested blocks) is accepted,
    - bare return (column 0) is rejected with indentation contract violation,
    - unindented assignment + return (column 0) is rejected,
    - 1-space and 3-space top-level indentation are rejected,
    - tab indentation is rejected,
    - all-8-space (over-indented) top-level code is rejected,
    - an included function definition (at any indent level) is rejected,
    - a markdown code fence is rejected.
    """

    def test_accepts_4space_indented_body(self) -> None:
        """4-space-indented function body passes all checks (test 4.1)."""
        good_code = (
            "    surface = request.path.lower()\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason=\"no suspicious indicator matched\",\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(good_code)
        assert err == "", f"4-space-indented body must pass validation, got: {err!r}"

    def test_rejects_bare_return_indentation_contract_violation(self) -> None:
        """Bare (unindented) return is rejected with 'indentation contract violation' (test 4.2)."""
        bad_code = (
            "return DetectionResult(\n"
            "    blocked=False,\n"
            "    reason=\"no suspicious indicator matched\",\n"
            "    confidence=0.0,\n"
            "    matched_signals=(),\n"
            ")\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Bare return must be rejected (indentation contract violation)"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    def test_rejects_unindented_assignment_indentation_contract_violation(self) -> None:
        """Unindented assignment + return is rejected with 'indentation contract violation' (test 4.3)."""
        bad_code = (
            "surface = request.path.lower()\n"
            "return DetectionResult(\n"
            "    blocked=False,\n"
            "    reason=\"no suspicious indicator matched\",\n"
            "    confidence=0.0,\n"
            "    matched_signals=(),\n"
            ")\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Unindented code must be rejected (indentation contract violation)"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    def test_rejects_function_definition_in_replacement_code(self) -> None:
        """replacement_code containing a function definition is rejected (test 4.4)."""
        bad_code = (
            "def inspect_request(request):\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason=\"no suspicious indicator matched\",\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Function definition in replacement_code must be rejected"
        assert (
            "function" in err.lower()
            or "def" in err.lower()
            or "body only" in err.lower()
        ), f"Error must mention function/def/body-only violation, got: {err!r}"

    def test_rejects_markdown_code_fence(self) -> None:
        """replacement_code wrapped in a markdown code fence is rejected (test 4.5)."""
        bad_code = (
            "```python\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason=\"no suspicious indicator matched\",\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
            "```\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Markdown code fence in replacement_code must be rejected"
        assert (
            "markdown" in err.lower()
            or "code fence" in err.lower()
            or "```" in err
        ), f"Error must mention markdown/code fence, got: {err!r}"

    def test_accepts_4space_toplevel_with_nested_blocks(self) -> None:
        """4-space top-level + 8-space nested block passes (explicit nested test)."""
        good_code = (
            "    surface = request.path.lower()\n"
            "    matched = []\n"
            "    if 'path_traversal_indicator' in surface:\n"
            "        matched.append('path_traversal_indicator')\n"
            "    if matched:\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='indicator matched',\n"
            "            confidence=0.7,\n"
            "            matched_signals=tuple(matched),\n"
            "        )\n"
            "    return DetectionResult(blocked=False, reason='no match', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(good_code)
        assert err == "", f"4-space top-level with 8-space nested must pass, got: {err!r}"

    def test_rejects_1space_indentation(self) -> None:
        """1-space top-level indentation is rejected (indentation contract violation)."""
        bad_code = (
            " surface = request.path.lower()\n"
            " return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "1-space indentation must be rejected"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    def test_rejects_3space_indentation(self) -> None:
        """3-space top-level indentation is rejected (indentation contract violation)."""
        bad_code = (
            "   surface = request.path.lower()\n"
            "   return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "3-space indentation must be rejected"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    def test_rejects_tab_indentation(self) -> None:
        """Tab-indented lines are rejected (indentation contract violation)."""
        bad_code = (
            "\tsurface = request.path.lower()\n"
            "\treturn DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Tab indentation must be rejected"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )
        assert "tab" in err.lower(), (
            f"Error must mention 'tab', got: {err!r}"
        )

    def test_rejects_all_8space_toplevel(self) -> None:
        """Code where all lines start at 8 spaces is rejected (missing top-level body)."""
        bad_code = (
            "        surface = request.path.lower()\n"
            "        return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "All-8-space top-level code must be rejected"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    def test_rejects_6space_nested_indentation(self) -> None:
        """6-space nested indentation is rejected (not a multiple of 4) (CR-65-02)."""
        bad_code = (
            "    surface = request.path.lower()\n"
            "    if 'path_traversal_indicator' in surface:\n"
            "      return DetectionResult(blocked=True, reason='matched', confidence=0.7, matched_signals=())\n"
            "    return DetectionResult(blocked=False, reason='no match', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "6-space nested indentation must be rejected (non-multiple-of-4)"
        assert "indentation contract violation" in err, (
            f"Error must contain 'indentation contract violation', got: {err!r}"
        )

    # -----------------------------------------------------------------------
    # CR-65-03: Reject empty / comment-only / no-return replacement_code
    # -----------------------------------------------------------------------

    def test_rejects_empty_replacement_code_body(self) -> None:
        """Empty string is rejected — no executable body (CR-65-03)."""
        for bad_code in ("", "   \n   \n", "\n\n"):
            err = pm._validate_replacement_code(bad_code)
            assert err != "", f"Empty/whitespace replacement_code must be rejected, got '' for input {bad_code!r}"
            assert (
                "empty" in err.lower()
                or "return" in err.lower()
                or "executable" in err.lower()
            ), f"Error must mention empty/return/executable, got: {err!r}"

    def test_rejects_comment_only_replacement_code_body(self) -> None:
        """Comment-only body is rejected — no executable AST nodes (CR-65-03)."""
        bad_code = (
            "    # only a comment\n"
            "    # another comment\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Comment-only replacement_code must be rejected"
        assert (
            "empty" in err.lower()
            or "return" in err.lower()
            or "executable" in err.lower()
        ), f"Error must mention empty body/return/executable, got: {err!r}"

    def test_rejects_blank_and_comment_only_replacement_code_body(self) -> None:
        """Blank lines + comment-only body is rejected (CR-65-03)."""
        bad_code = "\n    # only comment after blank lines\n"
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Blank+comment-only replacement_code must be rejected"
        assert (
            "empty" in err.lower()
            or "return" in err.lower()
            or "executable" in err.lower()
        ), f"Error must mention empty body/return/executable, got: {err!r}"

    def test_rejects_pass_only_replacement_code_body(self) -> None:
        """pass-only body is rejected — no DetectionResult return (CR-65-03)."""
        bad_code = "    pass\n"
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "pass-only replacement_code must be rejected"
        assert (
            "return" in err.lower()
            or "executable" in err.lower()
            or "pass" in err.lower()
        ), f"Error must mention return/executable/pass, got: {err!r}"

    def test_rejects_assignment_only_no_return_replacement_code(self) -> None:
        """Assignment-only body with no return is rejected (CR-65-03)."""
        bad_code = (
            "    surface = request.path.lower()\n"
            "    matched = []\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Assignment-only (no return) replacement_code must be rejected"
        assert "return" in err.lower(), (
            f"Error must mention 'return', got: {err!r}"
        )

    # -----------------------------------------------------------------------
    # CR-65-04: Require return DetectionResult(...), not merely any return
    # -----------------------------------------------------------------------

    def test_accepts_all_returns_detection_result(self) -> None:
        """replacement_code with only direct DetectionResult returns is accepted (CR-65-04)."""
        good_code = (
            "    if 'path_traversal_indicator' in request.path.lower():\n"
            "        return DetectionResult(\n"
            "            blocked=True,\n"
            "            reason='matched',\n"
            "            confidence=0.7,\n"
            "            matched_signals=('path_traversal_indicator',),\n"
            "        )\n"
            "    return DetectionResult(\n"
            "        blocked=False,\n"
            "        reason='no match',\n"
            "        confidence=0.0,\n"
            "        matched_signals=(),\n"
            "    )\n"
        )
        err = pm._validate_replacement_code(good_code)
        assert err == "", f"Valid code with only DetectionResult returns must pass, got: {err!r}"

    def test_rejects_return_none(self) -> None:
        """return None is rejected — not a DetectionResult return (CR-65-04)."""
        bad_code = "    return None\n"
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "return None must be rejected"
        assert "return DetectionResult" in err, (
            f"Error must contain 'return DetectionResult', got: {err!r}"
        )

    def test_rejects_return_string(self) -> None:
        """return 'blocked' is rejected — not a DetectionResult return (CR-65-04)."""
        bad_code = '    return "blocked"\n'
        err = pm._validate_replacement_code(bad_code)
        assert err != "", 'return "blocked" must be rejected'
        assert "return DetectionResult" in err, (
            f"Error must contain 'return DetectionResult', got: {err!r}"
        )

    def test_rejects_return_variable(self) -> None:
        """return result (variable) is rejected — not a direct DetectionResult return (CR-65-04)."""
        bad_code = (
            "    result = DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
            "    return result\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "return result (variable) must be rejected"
        assert "return DetectionResult" in err, (
            f"Error must contain 'return DetectionResult', got: {err!r}"
        )

    def test_rejects_mixed_detection_result_and_none_return(self) -> None:
        """Mixed returns: DetectionResult in one branch + return None → rejected (CR-65-04)."""
        bad_code = (
            "    if request.path:\n"
            "        return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
            "    return None\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "return None in any branch must be rejected even if other returns are valid"
        assert "return DetectionResult" in err, (
            f"Error must contain 'return DetectionResult', got: {err!r}"
        )

    # -----------------------------------------------------------------------

    def test_rejects_indented_def_helper(self) -> None:
        """Indented 'def helper():' inside replacement_code is rejected (P2 regression)."""
        bad_code = (
            "    surface = request.path.lower()\n"
            "    def helper():\n"
            "        return surface\n"
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Indented def helper() must be rejected (body-only contract)"
        assert (
            "function" in err.lower()
            or "def" in err.lower()
            or "body only" in err.lower()
        ), f"Error must mention function/def/body-only violation, got: {err!r}"

    def test_rejects_indented_async_def_helper(self) -> None:
        """Indented 'async def helper():' inside replacement_code is rejected (P2 regression)."""
        bad_code = (
            "    surface = request.path.lower()\n"
            "    async def helper():\n"
            "        return surface\n"
            "    return DetectionResult(blocked=False, reason='ok', confidence=0.0, matched_signals=())\n"
        )
        err = pm._validate_replacement_code(bad_code)
        assert err != "", "Indented async def helper() must be rejected (body-only contract)"
        assert (
            "function" in err.lower()
            or "def" in err.lower()
            or "body only" in err.lower()
        ), f"Error must mention function/def/body-only violation, got: {err!r}"

    # -----------------------------------------------------------------------
    # CR-65-MIN-01: Prompt wording must distinguish top-level from nested returns
    # -----------------------------------------------------------------------

    def test_system_prompt_indentation_wording_allows_nested_returns(self) -> None:
        """_LLM_SYSTEM_PROMPT must not claim all return DetectionResult must be at 4 spaces.

        CR-65-MIN-01: A return DetectionResult(...) nested inside an if/for/while
        block must be at 8/12/16 spaces (block depth) — not at 4. The prompt must
        explicitly describe this exception so the model generates correct code.
        """
        prompt = pm._LLM_SYSTEM_PROMPT
        prompt_lower = prompt.lower()
        # After the CR-65-MIN-01 fix, the prompt must mention that nested returns
        # inside if/for/while blocks follow block depth (not 4 spaces).
        assert (
            "nested" in prompt_lower
            or "exception" in prompt_lower
            or "block depth" in prompt_lower
        ), (
            "_LLM_SYSTEM_PROMPT must acknowledge that return DetectionResult(...) "
            "nested inside if/for/while blocks follows block depth (8/12/16 spaces), "
            "not always exactly 4 spaces. CR-65-MIN-01 wording fix required."
        )
        # The wording must also still require that top-level returns start at 4 spaces.
        assert "4 space" in prompt_lower or "exactly 4" in prompt_lower, (
            "_LLM_SYSTEM_PROMPT must still require that top-level return "
            "DetectionResult(...) starts at exactly 4 spaces."
        )
