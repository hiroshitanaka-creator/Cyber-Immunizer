"""scripts/propose_mutation.py — Propose a mutation patch via LLM or local sample.

Usage:
    python scripts/propose_mutation.py [--noop] [--offline-sample]
                                       [--live-model --allow-live-model] [--json]

Modes:
    --noop
        Exit 0, produce no mutation_patch.json, print status JSON.
        Use this for dry-run / scheduled runs that should never spend API quota.

    --offline-sample
        Return the built-in sample patch without any API call.
        Safe for local development and CI smoke-tests.

    --live-model --allow-live-model
        Call the Gemini API to propose a mutation.  Both flags must be given
        together; requiring --allow-live-model prevents accidental API calls.
        Additional pre-flight gates apply (see below).

Live-model pre-flight gates (all must pass):
    1. --allow-live-model flag present
    2. GEMINI_API_KEY env var set
    3. genome.live_model_enabled == true
    4. genome.max_model_requests_per_run <= 1
    5. Prompt length <= genome.max_prompt_chars
    6. genome.model_name must not contain "pro" when genome.free_tier_only == true
    7. genome.allow_google_search_grounding == false
    8. genome.allow_code_execution_tool == false
    9. Prompt preflight secret scan passes

SAFETY NOTE:
    The LLM is never asked to generate exploit payloads, attack code, or
    anything outside the internal logic of inspect_request().
    Live model calls are disabled by default (genome.live_model_enabled=false)
    to prevent accidental API usage without explicit opt-in.

    Sensitive data (secrets, env vars, full repo, raw exploit strings,
    real user logs) is never included in the prompt.
    A preflight scan rejects prompts that inadvertently contain secret tokens.

    The model output is validated against a strict JSON schema before the
    patch file is written. Unsafe replacement_code (imports, eval, exec, open,
    subprocess, socket, os., dunder access) is rejected before writing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DETECTOR_PATH = _PROJECT_ROOT / "core" / "detector.py"
_THREATS_PATH = _PROJECT_ROOT / "data" / "active_threats.json"
_OUT_DIR = _PROJECT_ROOT / ".cyber_immunizer"
_OUT_PATCH = _OUT_DIR / "mutation_patch.json"

# ---------------------------------------------------------------------------
# Required patch schema fields
# ---------------------------------------------------------------------------
_REQUIRED_PATCH_FIELDS: tuple[str, ...] = (
    "mutation_rationale",
    "target_threats",
    "expected_improvement",
    "risk",
    "replacement_code",
)

_MAX_RATIONALE_CHARS = 600
_MAX_IMPROVEMENT_CHARS = 600
_MAX_RISK_CHARS = 600
_MAX_REPLACEMENT_CHARS = 8000
_MAX_TARGET_THREATS = 5

# ---------------------------------------------------------------------------
# Preflight: tokens that must never appear in prompts sent to Gemini.
# Checked case-insensitively.
# ---------------------------------------------------------------------------
_BLOCKED_PROMPT_TOKENS: tuple[str, ...] = (
    "github_token",
    "gemini_api_key",
    "begin private key",
    "password=",
    "authorization:",
    "cookie:",
    "api_key",
)

# ---------------------------------------------------------------------------
# Post-flight: tokens that must never appear in replacement_code.
# Checked case-sensitively (Python keywords are case-sensitive).
# ---------------------------------------------------------------------------
_BLOCKED_CODE_TOKENS: tuple[str, ...] = (
    "import",
    "eval",
    "exec",
    "open(",
    "subprocess",
    "socket",
    "os.",
    "__",
)

# ---------------------------------------------------------------------------
# Mutation markers (must appear in replacement_code check)
# ---------------------------------------------------------------------------
_MUTATION_START_MARKER = "# === MUTATION_START ==="
_MUTATION_END_MARKER = "# === MUTATION_END ==="

# ---------------------------------------------------------------------------
# Gemini structured-output schema (subset that Gemini accepts).
# Additional constraints (maxLength, maxItems) are validated post-response.
# ---------------------------------------------------------------------------
_PATCH_SCHEMA_FOR_GEMINI: dict = {
    "type": "object",
    "properties": {
        "mutation_rationale": {"type": "string"},
        "target_threats": {
            "type": "array",
            "items": {"type": "string"},
        },
        "expected_improvement": {"type": "string"},
        "risk": {"type": "string"},
        "replacement_code": {"type": "string"},
    },
    "required": list(_REQUIRED_PATCH_FIELDS),
}

# ---------------------------------------------------------------------------
# Offline sample mutation (no API call)
# Uses neutralized symbolic indicators — not real exploit strings.
# Test data in data/attack_requests.json uses the same indicators.
# ---------------------------------------------------------------------------

_SAMPLE_MUTATION: dict = {
    "mutation_rationale": (
        "Tighten confidence scoring for multi-signal matches of the symbolic "
        "indicator set and add detection for the encoded-traversal category."
    ),
    "target_threats": ["THREAT-2024-001", "THREAT-2024-005"],
    "expected_improvement": (
        "Higher confidence scores when multiple symbolic indicators appear "
        "in the same request, reducing both false negatives on combined attacks "
        "and false positives on single-token benign edge cases."
    ),
    "risk": (
        "Minimal — only changes confidence scaling; detection logic is additive "
        "and uses the same neutralized symbolic indicator set."
    ),
    "replacement_code": '''\
    # Normalise all textual fields into one lowercase inspection surface.
    surface_parts = [
        request.method.lower(),
        request.path.lower(),
        " ".join(f"{k}={v}" for k, v in request.query.items()).lower(),
        " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower(),
        request.body.lower(),
    ]
    surface = " ".join(surface_parts)

    # Neutralized symbolic indicators — not real exploit strings.
    # Test data in data/attack_requests.json and data/regression_cases.json
    # uses the same indicators (lowercased at match time).
    _SUSPICIOUS_TOKENS: tuple[str, ...] = (
        "__path_traversal_indicator__",
        "__script_injection_indicator__",
        "__sqli_indicator__",
        "__command_delimiter_indicator__",
        "__encoded_traversal_indicator__",
    )

    matched: list[str] = []
    for token in _SUSPICIOUS_TOKENS:
        if token in surface:
            matched.append(token)

    if matched:
        # Multi-signal matches get progressively higher confidence.
        base_confidence = 0.5
        per_signal_boost = 0.12
        confidence = min(1.0, base_confidence + per_signal_boost * len(matched))
        return DetectionResult(
            blocked=True,
            reason=f"suspicious indicator matched: {matched[0]!r}",
            confidence=confidence,
            matched_signals=tuple(matched),
        )

    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
''',
}

# ---------------------------------------------------------------------------
# LLM prompt templates
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are a defensive security code assistant for Project Cyber-Immunizer.

STRICT RULES — YOU MUST FOLLOW ALL OF THEM:
1. Defensive detector improvement only. Your sole purpose is improving
   the inspect_request() detection logic defensively.
2. Return JSON only. No explanatory text outside the JSON object.
3. Do NOT produce exploit payloads. Never generate attack code,
   scanner code, credential theft logic, or offensive security tooling.
4. Do NOT produce scanner code. No port scanning, service enumeration,
   or network reconnaissance logic.
5. Do NOT produce network code. No socket, requests, urllib, httpx,
   or any other network I/O.
6. Do NOT use imports. The replacement_code field must contain ONLY
   Python logic — no import statements of any kind.
7. Do NOT use file I/O. No open(), pathlib, io, or file operations.
8. Do NOT use subprocess. No subprocess, os.system, os.popen, or
   shell execution of any kind.
9. Do NOT use eval, exec, compile, reflection, dunder access.
   No eval(), exec(), compile(), getattr(), setattr(), dir(), globals(),
   locals(), __class__, __dict__, __globals__, or any dunder attribute.
10. Preserve DetectionResult return. The function must return
    DetectionResult(blocked, reason, confidence, matched_signals) exactly.
11. Modify only logic inside inspect_request. Do not change the function
    signature, do not add new top-level definitions.
12. Prefer low false positives. Maximize true positive rate while keeping
    false positive rate at or below 5%.
13. Use only neutralized symbolic indicators from the local test corpus.
    Tokens like __path_traversal_indicator__, __script_injection_indicator__,
    __sqli_indicator__, __command_delimiter_indicator__,
    __encoded_traversal_indicator__ are the only detection signals.
14. Do not include real CVE exploit details. No actual vulnerability
    payloads, shellcode, or real attack strings.
15. Do not include raw offensive payloads. Use only the neutralized
    symbolic indicator tokens defined in the test corpus.

Return a JSON object with these exact fields (no others):
{
  "mutation_rationale": "short explanation (max 600 chars)",
  "target_threats": ["threat-id-or-category"],
  "expected_improvement": "what metric is expected to improve (max 600 chars)",
  "risk": "brief risk summary (max 600 chars)",
  "replacement_code": "Python code string for the function body only (no def statement)"
}
"""

_LLM_USER_PROMPT_TEMPLATE = """\
Current mutation region (code between markers in inspect_request):

{mutation_region}

Detector interface summary:
  Function: inspect_request(request: Request) -> DetectionResult
  Request fields (read-only): method (str), path (str),
    query (MappingProxyType[str, str]), headers (MappingProxyType[str, str]),
    body (str)
  DetectionResult fields: blocked (bool), reason (str),
    confidence (float 0.0–1.0), matched_signals (tuple[str, ...])

Neutralized active threat IDs (safe identifiers only):
{threat_ids}

Propose a mutation that improves defensive coverage while maintaining
low false positives. Use only neutralized symbolic indicators —
never raw exploit strings. Return JSON only.
"""


# ---------------------------------------------------------------------------
# Helper: extract mutation region from detector source
# ---------------------------------------------------------------------------


def _extract_mutation_region(source: str) -> str:
    """Extract code between mutation markers."""
    s = source.find(_MUTATION_START_MARKER)
    e = source.find(_MUTATION_END_MARKER)
    if s == -1 or e == -1 or e <= s:
        return ""
    return source[s + len(_MUTATION_START_MARKER) : e].strip()


# ---------------------------------------------------------------------------
# Helper: preflight scan for secret tokens in prompt
# ---------------------------------------------------------------------------


def _preflight_secret_scan(prompt: str) -> str:
    """Return an error message if any blocked token is found in the prompt.

    Matching is case-insensitive to catch varied casing.
    Returns empty string if the prompt is clean.
    """
    lowered = prompt.lower()
    for token in _BLOCKED_PROMPT_TOKENS:
        if token.lower() in lowered:
            return (
                f"Preflight secret scan failed: blocked token {token!r} found "
                "in prompt. Refusing to send this prompt to Gemini."
            )
    return ""


# ---------------------------------------------------------------------------
# Helper: validate replacement_code for forbidden patterns
# ---------------------------------------------------------------------------


def _validate_replacement_code(code: str) -> str:
    """Return an error message if replacement_code contains forbidden tokens.

    Also rejects mutation markers (which would break apply_mutation.py).
    Returns empty string if the code is clean.
    """
    # Reject mutation markers in replacement code
    if _MUTATION_START_MARKER in code or _MUTATION_END_MARKER in code:
        return (
            "replacement_code contains mutation marker(s). "
            "Markers are forbidden inside replacement_code."
        )
    # Reject forbidden code patterns
    for token in _BLOCKED_CODE_TOKENS:
        if token in code:
            return (
                f"replacement_code contains forbidden token {token!r}. "
                "Unsafe replacement_code rejected before writing patch."
            )
    return ""


# ---------------------------------------------------------------------------
# Helper: validate patch dict against the full schema
# ---------------------------------------------------------------------------


def _validate_patch_schema(data: object) -> str:
    """Return an error message if data does not conform to the patch schema.

    Checks:
    - data is a dict
    - all required fields are present
    - no extra fields (additionalProperties: false)
    - string fields have the correct type and length
    - target_threats is a list of strings with at most _MAX_TARGET_THREATS items
    Returns empty string if data is valid.
    """
    if not isinstance(data, dict):
        return f"patch must be a JSON object, got {type(data).__name__}"

    # Required fields check
    missing = [f for f in _REQUIRED_PATCH_FIELDS if f not in data]
    if missing:
        return f"patch is missing required fields: {missing}"

    # No extra fields
    extra = [k for k in data if k not in _REQUIRED_PATCH_FIELDS]
    if extra:
        return f"patch contains unexpected extra fields: {extra}"

    # Type and length checks for string fields
    str_limits = {
        "mutation_rationale": _MAX_RATIONALE_CHARS,
        "expected_improvement": _MAX_IMPROVEMENT_CHARS,
        "risk": _MAX_RISK_CHARS,
        "replacement_code": _MAX_REPLACEMENT_CHARS,
    }
    for field, max_len in str_limits.items():
        val = data[field]
        if not isinstance(val, str):
            return f"field {field!r} must be a string, got {type(val).__name__}"
        if len(val) > max_len:
            return (
                f"field {field!r} exceeds max length {max_len} "
                f"(got {len(val)} chars)"
            )

    # target_threats checks
    threats = data["target_threats"]
    if not isinstance(threats, list):
        return (
            f"field 'target_threats' must be an array, got {type(threats).__name__}"
        )
    if len(threats) > _MAX_TARGET_THREATS:
        return (
            f"field 'target_threats' has {len(threats)} items; "
            f"max is {_MAX_TARGET_THREATS}"
        )
    for i, t in enumerate(threats):
        if not isinstance(t, str):
            return f"target_threats[{i}] must be a string, got {type(t).__name__}"

    return ""


# ---------------------------------------------------------------------------
# Build user prompt (safe — never includes secrets or raw exploits)
# ---------------------------------------------------------------------------


def _build_user_prompt(genome: dict, detector_source: str) -> str:
    """Build the user-facing prompt for Gemini.

    Includes only:
    - current mutation region (function body code, no secrets)
    - detector interface summary (structural, no sensitive data)
    - neutralized active threat IDs (safe identifiers only)

    Never includes: secrets, env vars, full repo, exploit strings,
    real user logs, private vulnerability details.
    """
    mutation_region = _extract_mutation_region(detector_source)

    # Load neutralized threat IDs (safe identifiers only)
    try:
        threats_raw = json.loads(_THREATS_PATH.read_text(encoding="utf-8"))
        # Extract only the 'id' field — never payloads or raw signatures
        threat_ids = [
            str(t.get("id", ""))
            for t in threats_raw
            if isinstance(t, dict) and t.get("id")
        ]
    except Exception:
        threat_ids = []

    return _LLM_USER_PROMPT_TEMPLATE.format(
        mutation_region=mutation_region or "(empty — no mutation region found)",
        threat_ids=json.dumps(threat_ids),
    )


# ---------------------------------------------------------------------------
# Live Gemini API call (only called when all gates pass)
# ---------------------------------------------------------------------------


def _propose_via_gemini_live(
    genome: dict,
    detector_source: str,
    api_key: str,
) -> tuple[dict | None, str]:
    """Call the Gemini API and return (patch, error).

    This function is only reached after all safety gates have passed.
    It does NOT check allow_live_model or live_model_enabled — callers do that.
    """
    model_name: str = genome.get("model_name", "gemini-2.0-flash")
    max_output_tokens: int = int(genome.get("max_output_tokens", 2048))
    temperature: float = float(genome.get("temperature", 0.2))
    max_prompt_chars: int = int(genome.get("max_prompt_chars", 12000))

    # Build user prompt (never includes secrets)
    user_prompt = _build_user_prompt(genome, detector_source)
    full_prompt_for_scan = _LLM_SYSTEM_PROMPT + "\n" + user_prompt

    # Prompt length gate
    if len(full_prompt_for_scan) > max_prompt_chars:
        return None, (
            f"Prompt too long: {len(full_prompt_for_scan)} chars "
            f"exceeds max_prompt_chars={max_prompt_chars}. "
            "Refusing to call Gemini."
        )

    # Preflight secret scan — last line of defence before sending to Gemini
    scan_err = _preflight_secret_scan(full_prompt_for_scan)
    if scan_err:
        return None, scan_err

    # Import google-genai (optional dependency)
    try:
        from google import genai  # type: ignore[import]
        from google.genai import types as genai_types  # type: ignore[import]
    except ImportError:
        return None, (
            "google-genai is not installed. "
            "Install the gemini extra: pip install 'cyber-immunizer[gemini]' "
            "or: pip install 'google-genai>=1.0.0'"
        )

    # Single API call (max_model_requests_per_run enforced by caller)
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_LLM_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_PATCH_SCHEMA_FOR_GEMINI,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            ),
        )
        raw_text: str = response.text
    except Exception as exc:
        return None, f"Gemini API call failed: {exc}"

    # Parse JSON response
    try:
        patch = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, f"Gemini response is not valid JSON: {exc}"

    # Validate against the full schema (including maxLength / maxItems)
    schema_err = _validate_patch_schema(patch)
    if schema_err:
        return None, f"Gemini response failed schema validation: {schema_err}"

    # Validate replacement_code for forbidden patterns
    code_err = _validate_replacement_code(patch["replacement_code"])
    if code_err:
        return None, f"Gemini replacement_code validation failed: {code_err}"

    return patch, ""


# ---------------------------------------------------------------------------
# Main proposal logic
# ---------------------------------------------------------------------------


def propose_mutation(
    *,
    offline_sample: bool = False,
    live_model: bool = False,
    allow_live_model: bool = False,
) -> tuple[dict | None, str]:
    """Propose a mutation patch. Returns (patch, error).

    Args:
        offline_sample: Return the built-in sample patch immediately.
        live_model: Call the Gemini API (requires allow_live_model=True and
                    all pre-flight gates).
        allow_live_model: Explicit opt-in flag; live_model is silently
                         refused without it.
    """
    # Load genome for configuration and rate-limit checks
    try:
        genome = json.loads(_GENOME_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"could not read genome.json: {exc}"

    # Load detector source
    try:
        detector_source = _DETECTOR_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"could not read detector: {exc}"

    # ---- Offline sample mode ----
    if offline_sample:
        return _SAMPLE_MUTATION, ""

    # ---- Live model mode ----
    if live_model:
        # Gate 1: explicit opt-in flag
        if not allow_live_model:
            return None, (
                "--live-model requires --allow-live-model. "
                "Pass both flags together to explicitly opt in to API calls."
            )

        # Gate 2: API key
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return None, (
                "GEMINI_API_KEY environment variable is not set. "
                "Set GEMINI_API_KEY or use --offline-sample."
            )

        # Gate 3: genome.live_model_enabled
        if not genome.get("live_model_enabled", False):
            return None, (
                "genome.live_model_enabled is false. "
                "Set live_model_enabled=true in data/genome.json to enable "
                "live API calls."
            )

        # Gate 4: max_model_requests_per_run
        max_requests = int(genome.get("max_model_requests_per_run", 1))
        if max_requests > 1:
            return None, (
                f"genome.max_model_requests_per_run is {max_requests}; "
                "must be <= 1 for safety. Reduce it in data/genome.json."
            )

        # Gate 5: model safety — reject "pro" models when free_tier_only=true
        model_name: str = genome.get("model_name", "gemini-2.0-flash")
        if genome.get("free_tier_only", True) and "pro" in model_name.lower():
            return None, (
                f"model_name {model_name!r} contains 'pro' but "
                "genome.free_tier_only=true. "
                "Use a Flash/Flash-Lite model, or set free_tier_only=false "
                "with explicit budget approval."
            )

        # Gate 6: no Google Search grounding
        if genome.get("allow_google_search_grounding", False):
            return None, (
                "genome.allow_google_search_grounding is true. "
                "Grounding is disabled for safety; set it to false."
            )

        # Gate 7: no code execution tool
        if genome.get("allow_code_execution_tool", False):
            return None, (
                "genome.allow_code_execution_tool is true. "
                "Code execution tool is disabled for safety; set it to false."
            )

        return _propose_via_gemini_live(genome, detector_source, api_key)

    # ---- No mode selected ----
    return None, (
        "No mutation mode selected. "
        "Use --noop, --offline-sample, or --live-model --allow-live-model."
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cyber-Immunizer mutation proposer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--noop",
        action="store_true",
        help=(
            "Exit 0 immediately without producing a patch. "
            "Use for scheduled runs that should never call the API."
        ),
    )
    parser.add_argument(
        "--offline-sample",
        action="store_true",
        help="Generate a local sample patch without calling any API.",
    )
    parser.add_argument(
        "--live-model",
        action="store_true",
        help=(
            "Call the Gemini API to propose a mutation. "
            "Requires --allow-live-model and all pre-flight gates."
        ),
    )
    parser.add_argument(
        "--allow-live-model",
        action="store_true",
        help=(
            "Explicit opt-in to live API calls. "
            "Must be combined with --live-model. "
            "Without this flag, --live-model is refused."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a JSON summary (always on for --noop).",
    )
    args = parser.parse_args(argv)

    # ---- Noop mode: exit immediately, no patch ----
    if args.noop:
        output = {"success": True, "patch_path": None, "mode": "noop"}
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print("Mode: noop — no patch produced.")
        return 0

    patch, err = propose_mutation(
        offline_sample=args.offline_sample,
        live_model=args.live_model,
        allow_live_model=args.allow_live_model,
    )

    if err:
        output = {"success": False, "error": err, "patch_path": None}
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # Write patch to .cyber_immunizer/mutation_patch.json
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_PATCH.write_text(json.dumps(patch, indent=2), encoding="utf-8")

    mode = "live-model" if args.live_model else "offline-sample"
    output = {
        "success": True,
        "patch_path": str(_OUT_PATCH),
        "mode": mode,
        "mutation_rationale": patch.get("mutation_rationale", ""),
        "target_threats": patch.get("target_threats", []),
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Patch written to: {_OUT_PATCH}")
        print(f"Mode: {mode}")
        print(f"Rationale: {patch.get('mutation_rationale', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
