"""scripts/propose_mutation.py — Propose a mutation patch via LLM or local sample.

Usage:
    python scripts/propose_mutation.py [--noop] [--offline-sample]
                                       [--live-model --allow-live-model]
                                       [--gemini-paid-credit --allow-live-model]
                                       [--gemini-paid-credit-preflight]
                                       [--json]

Modes:
    --noop
        Exit 0, produce no mutation_patch.json, print status JSON.
        Use this for dry-run / scheduled runs that should never spend API quota.

    --offline-sample
        Return the built-in sample patch without any API call.
        Safe for local development and CI smoke-tests.

    --live-model --allow-live-model
        Call the Gemini API (free-tier / basic paid) to propose a mutation.
        Both flags must be given together; requiring --allow-live-model prevents
        accidental API calls.  Additional pre-flight gates apply (see below).

    --gemini-paid-credit --allow-live-model
        Call the Gemini API specifically for the Google AI Pro $10/month
        GenAI & Cloud developer credit.  Enforces additional budget gates:
        require_paid_tier, free_tier_only==false, monthly_api_budget_usd > 0,
        daily_api_budget_usd > 0, and hard budget caps via api_budget.py.
        Appends a usage record to data/api_usage_ledger.json after each call.

    --gemini-paid-credit-preflight
        Verify the preparation state for gemini-paid-credit without making
        any Gemini API call.  No patch is generated and the ledger is not
        written.  Checks: genome settings, GEMINI_API_KEY existence (value
        never logged), ledger readability, prompt length, secret scan, and
        budget availability.  live_model_enabled=false is the expected state
        for this preflight — if it is true, the check fails.

SAFETY CONSTRAINTS (all modes):
    - No secrets, env vars, full repo text, raw exploit strings, real user logs,
      or private vulnerability details are ever sent to Gemini.
    - The model output is validated against a strict JSON schema before the
      patch file is written.
    - Unsafe replacement_code is rejected before writing.
    - Generated code is never executed in this script.
    - raw GEMINI_API_KEY is injected only at step-level env in mode-specific
      propose job steps (live-model, gemini-paid-credit); noop, offline-sample,
      and gemini-paid-credit-preflight steps receive no raw GEMINI_API_KEY.
    - The schedule forces noop; live API calls are always manual opt-in.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DETECTOR_PATH = _PROJECT_ROOT / "core" / "detector.py"
_THREATS_PATH = _PROJECT_ROOT / "data" / "active_threats.json"
_LEDGER_PATH = _PROJECT_ROOT / "data" / "api_usage_ledger.json"
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
# This is a conservative content-level filter; the AST policy in
# core/policy.py provides the authoritative structural check.
# ---------------------------------------------------------------------------
_BLOCKED_CODE_TOKENS: tuple[str, ...] = (
    "import",
    "eval",
    "exec",
    "open(",
    "subprocess",
    "socket",
    "os.",
    "pathlib",
    "shutil",
    "urllib",
    "requests",
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
    # These tokens appear in the JSON test corpus (uppercase) and are
    # lowercased at match time. No double-underscore prefix/suffix.
    _SUSPICIOUS_TOKENS: tuple[str, ...] = (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
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
7. Do NOT use file I/O. No open(), pathlib, io, shutil, or file operations.
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
    Tokens like path_traversal_indicator, script_injection_indicator,
    sqli_indicator, command_delimiter_indicator,
    encoded_traversal_indicator are the only detection signals.
    These tokens appear as uppercase in the JSON test corpus
    (PATH_TRAVERSAL_INDICATOR etc.) but the detector lowercases all input
    before matching, so use the lowercase forms in replacement_code.
    Do NOT add double-underscore prefix/suffix to these tokens.
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
    confidence (float 0.0-1.0), matched_signals (tuple[str, ...])

Neutralized active threat IDs (safe identifiers only):
{threat_ids}

Propose a mutation that improves defensive coverage while maintaining
low false positives. Use only neutralized symbolic indicators --
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
    Also rejects code that is not valid Python syntax (AST parse only — never executed).
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
    # Validate Python syntax by splicing replacement_code into the same
    # indentation context that apply_mutation.py uses: inserted as-is between
    # the mutation markers inside a function body.  The MUTATION_END marker is
    # at column 0 (matching core/detector.py).  Code is never executed —
    # ast.parse() only builds the parse tree.
    # Unindented code (e.g. bare `return`) triggers IndentationError.
    # Semicolon-joined compound statements trigger SyntaxError.
    # Lone surrogates or other ill-formed Unicode may trigger UnicodeError;
    # caught separately so the class name (not the message, which could echo
    # replacement_code content) is returned as the validation error.
    wrapped = (
        "def _candidate_body(request):\n"
        "    " + _MUTATION_START_MARKER + "\n"
        + code
        + "\n" + _MUTATION_END_MARKER + "\n"
    )
    try:
        ast.parse(wrapped)
    except SyntaxError as exc:
        return f"replacement_code is not valid Python syntax: {exc}"
    except UnicodeError as exc:
        return f"replacement_code is not valid Python source text: {type(exc).__name__}"
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

    # No extra fields (additionalProperties: false)
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
# Gemini API resilience constants
# ---------------------------------------------------------------------------

_GEMINI_API_TIMEOUT_SECONDS = 30.0
# Google GenAI SDK HttpOptions.timeout is in milliseconds.
_GEMINI_API_TIMEOUT_MS = int(_GEMINI_API_TIMEOUT_SECONDS * 1000)  # 30,000 ms = 30 s
_GEMINI_API_MAX_ATTEMPTS = 3
_GEMINI_API_BACKOFF_INITIAL_SECONDS = 1.0
_GEMINI_API_BACKOFF_MULTIPLIER = 2.0
_GEMINI_API_BACKOFF_MAX_SECONDS = 8.0
# Gemini 3 models support dynamic thinking; cap it at "low" for initial deployment
# to keep token costs predictable.  thinking_budget maps to the thinking token cap.
_GEMINI3_THINKING_BUDGET_LOW = 1024

# Status codes that indicate a transient failure worth retrying.
_TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
# Status codes that indicate a permanent failure; do not retry.
_NON_TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({400, 401, 403})
# Message substrings that indicate a transient failure when no status code is available.
_TRANSIENT_MESSAGE_FRAGMENTS: tuple[str, ...] = (
    "429",
    "rate limit",
    "resource exhausted",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "deadline",
    "connection reset",
    "503",
    "500",
    "502",
    "504",
)


def _is_transient_gemini_error(exc: BaseException) -> bool:
    """Return True if exc represents a transient Gemini API error worth retrying.

    Uses status_code / code attribute inspection and message substring matching
    so that this helper works even when the google-genai SDK is not installed
    and exception classes are not importable.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int):
        if status in _NON_TRANSIENT_STATUS_CODES:
            return False
        if status in _TRANSIENT_STATUS_CODES:
            return True
    msg = str(exc).lower()
    return any(frag in msg for frag in _TRANSIENT_MESSAGE_FRAGMENTS)


_GEMINI_ERROR_MAX_MSG_LEN = 500

# Allowlisted, non-secret API error codes that may be surfaced verbatim in
# diagnostics. These are a fixed, enumerated set of uppercase tokens — they are
# never request/prompt payload, so it is safe to include them even when the
# surrounding message is redacted.
_SAFE_GEMINI_ERROR_CODES = (
    "PERMISSION_DENIED",
    "INVALID_ARGUMENT",
    "API_KEY_INVALID",
    "UNAUTHENTICATED",
    "NOT_FOUND",
    "RESOURCE_EXHAUSTED",
    "FAILED_PRECONDITION",
    "QUOTA_EXCEEDED",
)

# If any of these substrings appears (case-insensitively) in a raw exception
# message, the message is assumed to potentially carry request/prompt payload
# and is NOT surfaced raw. Only the exception class, the integer status, and any
# allowlisted error code are returned. This is a deliberate fail-closed guard:
# rather than chasing every new SDK payload-echo encoding with more sanitiser
# regexes, any payload indicator forces a generic redaction so prompt/request
# text can never reach logs or the paid-credit ledger.
_GEMINI_PAYLOAD_INDICATORS = (
    "contents",
    "system_instruction",
    "parts",
    "text=",
    '"text"',
    "'text'",
    "prompt",
    "user_prompt",
    "request",
    "payload",
    "body",
    "current mutation region",
    "mutation_start",
    "mutation_end",
)

# Fixed marker used when payload indicators are detected in a raw message.
_GEMINI_PAYLOAD_REDACTED_DETAIL = (
    "message redacted because request payload was present"
)


def _sanitize_gemini_error_message(
    raw_msg: str,
    forbidden_substrings: tuple[str, ...] = (),
) -> str:
    """Strip secret-like and prompt/request-payload material from a raw exception message.

    Applied in order:
    1. Exact forbidden substrings (caller-supplied: user prompt, system prompt).
    2. Exact GEMINI_API_KEY env value.
    3. Authorization: Bearer <token> header patterns.
    4. api_key= / apikey= long value patterns.
    5. JSON/repr/assignment-style prompt-carrying fields:
       system_instruction, user_prompt, prompt, text (JSON only), parts (JSON only).
       Handles "key": "value", 'key': 'value', key="value", key='value'.
       Value patterns cover JSON escape sequences (\\n, \\", etc.).
    6. "contents" request-payload array sections.
    7. Indexed request field path forms — SDK/API diagnostic echoes may carry
       submitted prompt as dotted/indexed paths ending in .text:
         contents[0].parts[0].text = "..."
         request.contents[0].parts[0].text: "..."
         system_instruction.parts[0].text = "..."
         parts[0].text = "..."
       Both bracket ([N]) and dot-numeric (.N) index notations are covered.
    8. Mutation-region markers and trailing content.
    """
    # 1. Caller-supplied forbidden strings (user prompt text, system prompt).
    #    Verbatim str.replace handles the raw Python string form.
    #    JSON-encoded forms (e.g. "system_instruction": "...\n...") are handled
    #    separately in step 5 via structural regex, because json.dumps converts
    #    \n to \\n and adds surrounding quotes, making the encoded string
    #    non-identical to the raw Python value and therefore unmatchable here.
    for forbidden in forbidden_substrings:
        if forbidden and forbidden in raw_msg:
            raw_msg = raw_msg.replace(forbidden, "[REDACTED]")  # raw form; see step 5 for JSON-encoded form

    # 2. Exact GEMINI_API_KEY env value.
    api_key_val = os.environ.get("GEMINI_API_KEY", "")
    if api_key_val and api_key_val in raw_msg:
        raw_msg = raw_msg.replace(api_key_val, "[REDACTED]")

    # 3. Authorization: Bearer <token> header values.
    raw_msg = re.sub(
        r"(?i)(Authorization:\s*Bearer\s+)\S+",
        r"\1[REDACTED]",
        raw_msg,
    )

    # 4. api_key= / apikey= style long value assignments.
    raw_msg = re.sub(
        r"(?i)(api[_-]?key\s*[=:]\s*)[A-Za-z0-9\-_]{20,}",
        r"\1[REDACTED]",
        raw_msg,
    )

    # 5. JSON/repr/assignment-style prompt-carrying fields.
    #    Conservative fail-closed: if a known prompt-carrying key appears in any
    #    common encoding, replace the entire quoted value with a safe marker.
    #    The JSON string pattern handles escape sequences (\\n, \\", etc.) so
    #    JSON-encoded system prompts are caught even when verbatim match (step 1)
    #    cannot find them due to encoding differences.
    _dbl_str = r'"(?:[^"\\]|\\.)*"'           # JSON double-quoted string value
    _sgl_str = r"'(?:[^'\\]|\\.)*'"           # Python single-quoted string value
    _any_str = "(?:" + _dbl_str + "|" + _sgl_str + ")"  # either form

    for _fk, _fl in (
        ("system_instruction", "[system instruction redacted]"),
        ("user_prompt",        "[user prompt redacted]"),
        ("prompt",             "[prompt redacted]"),
    ):
        # Key forms: "key", 'key', bare key (for assignment-style)
        _kp = '(?:"' + _fk + '"|' + "'" + _fk + "'|" + _fk + ')'
        raw_msg = re.sub(
            _kp + r"\s*[:=]\s*" + _any_str,
            '"' + _fk + '": "' + _fl + '"',
            raw_msg,
            flags=re.IGNORECASE,
        )

    # "text" and "parts" carry per-part prompt content in the request body.
    # Covers JSON-quoted key forms ("text": / 'text':) and bare assignment
    # forms (text=, parts=) used in Python repr such as Part(text='...').
    # Negative lookbehind (?<![.\w]) prevents matching words like "context"
    # and avoids colliding with dotted-path forms handled in step 7.
    raw_msg = re.sub(
        r'(?:"text"|\'text\'|(?<![.\w])text)\s*[:=]\s*' + _any_str,
        '"text": "[text redacted]"',  # covers "text":, 'text':, text= repr forms
        raw_msg,
        flags=re.IGNORECASE | re.DOTALL,
    )
    raw_msg = re.sub(
        r'(?:"parts"|\'parts\'|(?<![.\w])parts)\s*[:=]\s*\[.*?\]',
        '"parts": "[parts redacted]"',  # covers "parts":, 'parts':, parts= repr forms
        raw_msg,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 6. "contents" key — array value OR scalar quoted string value.
    #    Covers contents=[...], "contents": [...], contents="prompt text",
    #    "contents": "prompt text", 'contents': 'prompt text', etc.
    #    Scalar form catches SDK echoes where contents is passed as a string
    #    (e.g. contents=user_prompt in _call_gemini_api) rather than a list.
    raw_msg = re.sub(
        r"(?:'?\"?contents\"?'?)\s*[:=]\s*(?:\[.*?\]|" + _any_str + ")",
        "[contents redacted]",
        raw_msg,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 7. Indexed request field path forms — SDK/API error diagnostics may echo the
    #    submitted request as dotted/indexed paths (e.g. contents[0].parts[0].text).
    #    Both bracket ([N]) and dot-numeric (.N) index notations are supported.
    #    A single regex pass with a callable replacement avoids the case where
    #    the bare "parts[N].text" sub-pattern would re-match inside a replacement
    #    string that still contains "system_instruction.parts[N].text".
    _idx_seg = r"(?:\[\d+\]|\.\d+)?"  # optional [N] or .N index segment
    _indexed_path_pat = (
        r"((?:system_instruction|(?:request\.)?contents" + _idx_seg + r")"
        + r"\.parts" + _idx_seg + r"\.text"
        + r"|parts" + _idx_seg + r"\.text"
        + r")\s*[:=]\s*" + _any_str
    )

    def _replace_indexed_text_path(m: re.Match) -> str:  # type: ignore[type-arg]
        path = m.group(1)
        if path.lower().startswith("system_instruction"):
            return path + ' = "[system instruction redacted]"'
        return path + ' = "[text redacted]"'

    raw_msg = re.sub(
        _indexed_path_pat,
        _replace_indexed_text_path,
        raw_msg,
        flags=re.IGNORECASE,
    )

    # 8. Mutation-region markers and everything that follows — prevents detector
    # source code from leaking out if the SDK echoes back the request payload.
    raw_msg = re.sub(
        r"(?is)(Current\s+mutation\s+region|===\s*MUTATION_START\s*===|===\s*MUTATION_END\s*===).*",
        "[mutation region redacted]",
        raw_msg,
    )

    return raw_msg


def _format_gemini_error_detail(
    exc: BaseException,
    max_len: int = _GEMINI_ERROR_MAX_MSG_LEN,
    *,
    forbidden_substrings: tuple[str, ...] = (),
) -> str:
    """Return an allowlisted, payload-safe diagnostic string for a Gemini exception.

    The output contains only:
      - the exception class name,
      - the integer status_code / code attribute (if present),
      - any allowlisted API error code extracted from the message
        (PERMISSION_DENIED, INVALID_ARGUMENT, API_KEY_INVALID, …), and
      - otherwise a sanitized, length-bounded excerpt — but ONLY when the raw
        message shows no request/prompt payload indicators.

    The raw str(exc) is never returned verbatim once a payload indicator is
    detected; a fixed redaction marker is used instead. This is a deliberate
    move away from regex-sanitizing arbitrary payload echoes (which proved
    fragile against new encodings — JSON, repr, indexed paths, scalar contents)
    toward a fail-closed allowlist. Allowlisted error codes are still surfaced
    because they are a fixed, non-secret enumeration.

    forbidden_substrings are still applied (in the payload-free branch) as
    defense-in-depth so caller-known prompt/system strings are stripped.

    The excerpt is truncated to max_len characters to bound ledger/log size.
    """
    cls_name = type(exc).__name__
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    status_part = f" (status={status})" if isinstance(status, int) else ""

    raw_msg = str(exc)
    lowered = raw_msg.lower()

    # Allowlisted, non-secret error codes may always be surfaced — but ONLY the
    # code tokens themselves, never the surrounding text (which could be payload).
    found_codes = [code for code in _SAFE_GEMINI_ERROR_CODES if code in raw_msg]
    if found_codes:
        detail = ", ".join(dict.fromkeys(found_codes))  # de-dup, preserve order
        return f"{cls_name}{status_part}: {detail}"

    # No allowlisted code. If the message looks like it carries request/prompt
    # payload, do not surface it at all — return a fixed redaction marker.
    if any(indicator in lowered for indicator in _GEMINI_PAYLOAD_INDICATORS):
        return f"{cls_name}{status_part}: {_GEMINI_PAYLOAD_REDACTED_DETAIL}"

    # Payload-free and no recognized code: surface a sanitized, bounded excerpt
    # as defense-in-depth (strips GEMINI_API_KEY, bearer tokens, api_key=, and
    # any caller-supplied forbidden substrings).
    sanitized_msg = _sanitize_gemini_error_message(raw_msg, forbidden_substrings)
    if len(sanitized_msg) > max_len:
        sanitized_msg = sanitized_msg[:max_len] + "…"
    if not sanitized_msg:
        return f"{cls_name}{status_part}"
    return f"{cls_name}{status_part}: {sanitized_msg}"


# ---------------------------------------------------------------------------
# Raw Gemini API call (shared by both live-model and gemini-paid-credit)
# ---------------------------------------------------------------------------


def _call_gemini_api(
    api_key: str,
    model_name: str,
    user_prompt: str,
    max_output_tokens: int,
    temperature: float,
    *,
    max_attempts: int = _GEMINI_API_MAX_ATTEMPTS,
    _sleep_fn=None,
) -> tuple[str | None, int | None, int | None, str]:
    """Issue a Gemini API call with explicit timeout and bounded transient retry.

    Returns (raw_text, actual_input_tokens, actual_output_tokens, error).
    On error, raw_text is None and error is non-empty.
    actual_input_tokens / actual_output_tokens may be None if the API
    does not return usage metadata.

    Retry behaviour:
      - Transient errors (429, 5xx, timeout, network interruption) are retried
        with exponential backoff up to effective_attempts times, where
        effective_attempts = min(max_attempts, _GEMINI_API_MAX_ATTEMPTS).
      - Non-transient errors (400, 401, 403, schema failures, etc.) are not
        retried; the function returns immediately.
      - The retry loop is fully contained here; callers see a single result.

    max_attempts should be set by callers to genome["max_model_requests_per_run"]
    so that the number of actual generate_content calls never exceeds the budget
    allowed for this run.  _GEMINI_API_MAX_ATTEMPTS acts as a hard upper cap.

    _sleep_fn is injectable for tests (default: time.sleep).
    """
    if _sleep_fn is None:
        _sleep_fn = time.sleep

    # Enforce caller-supplied attempt budget capped by the hard constant.
    effective_attempts = min(max_attempts, _GEMINI_API_MAX_ATTEMPTS)
    if effective_attempts < 1:
        return None, None, None, (
            f"Gemini API call failed: invalid max_attempts={max_attempts!r} — "
            "request budget must be >= 1."
        )

    try:
        from google import genai  # type: ignore[import]
        from google.genai import types as genai_types  # type: ignore[import]
    except ImportError:
        return None, None, None, (
            "google-genai is not installed. "
            "Install the gemini extra: pip install 'cyber-immunizer[gemini]' "
            "or: pip install 'google-genai>=1.0.0'"
        )

    # Build client with explicit timeout.  Google GenAI SDK HttpOptions.timeout
    # is in milliseconds, so pass _GEMINI_API_TIMEOUT_MS (30,000 ms = 30 s).
    # Fail closed if HttpOptions is not supported by the installed SDK version
    # rather than silently omitting the timeout.
    try:
        http_opts = genai_types.HttpOptions(timeout=_GEMINI_API_TIMEOUT_MS)
        client = genai.Client(api_key=api_key, http_options=http_opts)
    except (TypeError, AttributeError) as http_exc:
        return None, None, None, (
            "Gemini API call failed: could not configure explicit timeout — "
            "HttpOptions(timeout=...) is not supported by the installed "
            f"google-genai SDK version ({type(http_exc).__name__}). "
            "Upgrade to google-genai>=1.0.0."
        )

    last_exc_type_name = "UnknownError"
    last_exc_detail = "UnknownError"
    last_is_transient = False
    attempt = 0
    backoff = _GEMINI_API_BACKOFF_INITIAL_SECONDS

    # Gemini 3 models support dynamic thinking; pass thinking_config explicitly
    # to use a "low" budget and prevent unbounded thinking token spend.
    # Gemini 2.x models do not accept this field, so only include it for gemini-3.
    _generate_config_kwargs: dict = dict(
        system_instruction=_LLM_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_PATCH_SCHEMA_FOR_GEMINI,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    if model_name.startswith("gemini-3"):
        _generate_config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=_GEMINI3_THINKING_BUDGET_LOW
        )

    for attempt in range(1, effective_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(**_generate_config_kwargs),
            )
            raw_text: str = response.text

            # Extract actual token counts if available in response metadata.
            actual_input_tokens: int | None = None
            actual_output_tokens: int | None = None
            try:
                usage = response.usage_metadata
                if usage is not None:
                    actual_input_tokens = getattr(usage, "prompt_token_count", None)
                    actual_output_tokens = getattr(usage, "candidates_token_count", None)
            except Exception:
                pass

            return raw_text, actual_input_tokens, actual_output_tokens, ""

        except Exception as exc:
            last_exc_type_name = type(exc).__name__
            last_exc_detail = _format_gemini_error_detail(
                exc,
                forbidden_substrings=(user_prompt, _LLM_SYSTEM_PROMPT),
            )
            last_is_transient = _is_transient_gemini_error(exc)

            if not last_is_transient:
                # Non-transient: fail immediately, do not retry.
                break

            if attempt < effective_attempts:
                _sleep_fn(backoff)
                backoff = min(
                    backoff * _GEMINI_API_BACKOFF_MULTIPLIER,
                    _GEMINI_API_BACKOFF_MAX_SECONDS,
                )

    classification = "transient" if last_is_transient else "non-transient"
    plural = "s" if attempt != 1 else ""
    return None, None, None, (
        f"Gemini API call failed after {attempt} attempt{plural}: "
        f"{classification} error {last_exc_detail}"
    )


# ---------------------------------------------------------------------------
# Parse and validate Gemini response
# ---------------------------------------------------------------------------


def _parse_and_validate_response(raw_text: str) -> tuple[dict | None, str]:
    """Parse JSON, validate schema, and check replacement_code safety.

    Returns (patch, error).
    """
    try:
        patch = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, f"Gemini response is not valid JSON: {exc}"

    schema_err = _validate_patch_schema(patch)
    if schema_err:
        return None, f"Gemini response failed schema validation: {schema_err}"

    code_err = _validate_replacement_code(patch["replacement_code"])
    if code_err:
        return None, f"Gemini replacement_code validation failed: {code_err}"

    return patch, ""


# ---------------------------------------------------------------------------
# Live Gemini API call — free-tier / --live-model path
# ---------------------------------------------------------------------------


def _propose_via_gemini_live(
    genome: dict,
    detector_source: str,
    api_key: str,
) -> tuple[dict | None, str]:
    """Call the Gemini API for the --live-model path. Returns (patch, error).

    This function is only reached after all --live-model safety gates pass.
    Does NOT check allow_live_model or live_model_enabled — callers do that.
    Does NOT track budget (use _propose_via_gemini_paid_credit for that).
    """
    model_name: str = genome.get("model_name", "gemini-2.0-flash")
    max_output_tokens: int = int(genome.get("max_output_tokens", 2048))
    temperature: float = float(genome.get("temperature", 0.2))
    max_prompt_chars: int = int(genome.get("max_prompt_chars", 12000))
    # Pass genome's request budget so that retries never exceed the allowed
    # number of generate_content calls for this run.
    request_attempt_budget: int = int(genome.get("max_model_requests_per_run", 1))

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

    # Preflight secret scan
    scan_err = _preflight_secret_scan(full_prompt_for_scan)
    if scan_err:
        return None, scan_err

    raw_text, _inp_tok, _out_tok, api_err = _call_gemini_api(
        api_key, model_name, user_prompt, max_output_tokens, temperature,
        max_attempts=request_attempt_budget,
    )
    if api_err:
        return None, api_err

    return _parse_and_validate_response(raw_text)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Paid-credit Gemini API call — --gemini-paid-credit path
# ---------------------------------------------------------------------------


def _propose_via_gemini_paid_credit(
    genome: dict,
    detector_source: str,
    api_key: str,
    ledger_path: Path,
) -> tuple[dict | None, str]:
    """Call Gemini with full budget enforcement and ledger tracking.

    Returns (patch, error).
    All safety gates have been validated by the caller (propose_mutation).
    This function:
      1. Builds and secret-scans the prompt
      2. Estimates cost and asserts budget availability
      3. Calls Gemini once
      4. Appends a usage record (success or failure) to the ledger
      5. Validates the response
    """
    # Import budget module (standard library only)
    from scripts import api_budget as budget  # type: ignore[import]

    model_name: str = genome.get("model_name", "gemini-2.0-flash")
    max_output_tokens: int = int(genome.get("max_output_tokens", 2048))
    temperature: float = float(genome.get("temperature", 0.2))
    max_prompt_chars: int = int(genome.get("max_prompt_chars", 12000))
    api_mode: str = genome.get("api_mode", "gemini_paid_credit")
    # Pass genome's request budget so that retries never exceed the allowed
    # number of generate_content calls for this run.  With the current default
    # of max_model_requests_per_run=1 the effective retry count is 1 (no retry),
    # keeping actual API calls in lockstep with the budget estimate.
    request_attempt_budget: int = int(genome.get("max_model_requests_per_run", 1))

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

    # Preflight secret scan — must pass before cost estimation
    scan_err = _preflight_secret_scan(full_prompt_for_scan)
    if scan_err:
        return None, scan_err

    # Cost estimation
    input_chars = len(full_prompt_for_scan)
    # estimated_output_chars is kept for the ledger diagnostic record only.
    # max_output_tokens is already a token cap — NOT a character count.
    # Passing it through estimate_tokens_from_chars() would multiply the token
    # cap by the char-to-token multiplier and make valid budgets fail.
    # The conservative estimator applies only to character-counted inputs.
    #
    # For Gemini 3 models, thinking tokens (capped at _GEMINI3_THINKING_BUDGET_LOW)
    # are billed alongside output tokens per Google pricing docs; include them.
    effective_output_token_budget = max_output_tokens
    if model_name.startswith("gemini-3"):
        effective_output_token_budget += _GEMINI3_THINKING_BUDGET_LOW
    estimated_output_chars = effective_output_token_budget * 4  # ledger diagnostic only
    est_input_tokens = budget.estimate_tokens_from_chars(input_chars)
    est_output_tokens = effective_output_token_budget
    est_cost = budget.estimate_cost_usd(est_input_tokens, est_output_tokens, model_name)

    # Load ledger and assert budget — FAIL CLOSED for missing/malformed ledger.
    # Use strict_load_ledger so that a missing ledger is treated as
    # "budget state unknown" and the API call is refused, not silently
    # permitted as if no prior spend existed.
    try:
        ledger = budget.strict_load_ledger(ledger_path)
    except ValueError as exc:
        return None, f"API usage ledger is not usable; refusing call: {exc}"

    budget_ok, budget_err = budget.assert_budget_available(genome, ledger, est_cost)
    if not budget_ok:
        return None, budget_err

    # Single Gemini API call (retries up to request_attempt_budget attempts for
    # transient errors, keeping total generate_content calls within budget).
    raw_text, actual_input_tokens, actual_output_tokens, api_err = _call_gemini_api(
        api_key, model_name, user_prompt, max_output_tokens, temperature,
        max_attempts=request_attempt_budget,
    )

    # Append usage record — HARD ERROR if ledger write fails.
    # An API call whose cost cannot be recorded into the ledger must NOT be
    # treated as a success: it would leave the budget cap in a fail-open
    # state for future calls.  We try to record success or failure; if
    # either record write fails, we return an error regardless of whether
    # the API call itself succeeded.
    try:
        budget.append_usage_record(
            ledger_path,
            provider="gemini",
            api_mode=api_mode,
            model=model_name,
            estimated_input_chars=input_chars,
            estimated_output_chars=estimated_output_chars,
            estimated_input_tokens=est_input_tokens,
            estimated_output_tokens=est_output_tokens,
            actual_input_tokens=actual_input_tokens,
            actual_output_tokens=actual_output_tokens,
            success=(api_err == ""),
            error=api_err,
        )
    except (ValueError, OSError) as ledger_exc:
        ledger_err = (
            f"API usage ledger write failed: {ledger_exc}. "
            "Cannot confirm budget was recorded; refusing to return patch."
        )
        if api_err:
            # Both API call and ledger write failed: report both
            return None, f"{api_err} — additionally, {ledger_err}"
        return None, ledger_err

    if api_err:
        return None, api_err

    return _parse_and_validate_response(raw_text)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Preflight: verify gemini-paid-credit readiness without calling the API
# ---------------------------------------------------------------------------


def run_gemini_paid_credit_preflight() -> tuple[dict, str]:
    """Verify readiness for gemini-paid-credit without calling the Gemini API.

    All configuration gates (genome settings, API key existence, ledger state,
    prompt length, secret scan, budget availability) are verified in sequence.
    No API call is performed, no patch is written, and the ledger is not modified.

    GEMINI_API_KEY is checked only for existence — its value is never included
    in the returned dict, printed to stdout, or written to any log.

    Returns:
        (result_dict, error)  where:
          - On success: result_dict has success=True, error is "".
          - On failure: result_dict has success=False and an "error" field;
            error string contains the reason (no API key values).

    Expected genome state for this preflight:
        live_model_enabled == false   (real API calls are NOT yet enabled)
        api_mode == "gemini_paid_credit"
        model_provider == "gemini"
        require_paid_tier == true
        free_tier_only == false
        monthly_api_budget_usd > 0
        daily_api_budget_usd > 0
        max_model_requests_per_run <= 1
        allow_google_search_grounding == false
        allow_code_execution_tool == false
        allow_url_context == false
        send_repository_full_text == false
        send_raw_payloads == false
        send_secrets == false
    """
    from scripts import api_budget as budget  # standard-library-only module

    warnings: list[str] = []

    # --- Step 1: Read genome ---
    try:
        genome = json.loads(_GENOME_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        err = f"could not read genome.json: {exc}"
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "error": err}, err

    # --- Step 2: Read detector ---
    try:
        detector_source = _DETECTOR_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        err = f"could not read detector: {exc}"
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "error": err}, err

    # --- Step 3: GEMINI_API_KEY existence (value NEVER logged) ---
    # Accept either the raw key (local / live-model / gemini-paid-credit steps)
    # or the boolean signal GEMINI_API_KEY_PRESENT=true injected by the
    # gemini-paid-credit-preflight workflow step (PR-D: step-level secret
    # scoping — the raw key is intentionally withheld from the preflight step).
    api_key_present = (
        os.environ.get("GEMINI_API_KEY_PRESENT") == "true"
        or bool(os.environ.get("GEMINI_API_KEY", ""))
    )
    if not api_key_present:
        err = (
            "GEMINI_API_KEY environment variable is not set. "
            "Set GEMINI_API_KEY in GitHub Secrets (value is never logged by "
            "this preflight)."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": False,
                "error": err}, err

    # --- Step 4: api_mode check ---
    api_mode = genome.get("api_mode", "")
    if api_mode != "gemini_paid_credit":
        err = (
            f"genome.api_mode is {api_mode!r}; "
            "expected 'gemini_paid_credit' for this preflight."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "error": err}, err

    # --- Step 5: model_provider check ---
    model_provider = genome.get("model_provider", "")
    if model_provider != "gemini":
        err = (
            f"genome.model_provider is {model_provider!r}; "
            "expected 'gemini' for this preflight."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "error": err}, err

    # --- Step 6: live_model_enabled must be false ---
    # This preflight checks readiness BEFORE enabling live API calls.
    # If live_model_enabled is already true, the operator may have enabled it
    # prematurely; this preflight gate rejects that state to enforce the
    # review-before-enablement workflow.
    live_model_enabled = bool(genome.get("live_model_enabled", False))
    if live_model_enabled:
        err = (
            "genome.live_model_enabled is true. "
            "This preflight verifies the pre-API-call state; "
            "live_model_enabled must remain false until the human owner "
            "confirms Billing and Secret configuration are complete. "
            "After passing this preflight, set live_model_enabled=true "
            "in a reviewed commit to enable actual API calls."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": True, "error": err}, err

    # --- Step 7: require_paid_tier ---
    if not genome.get("require_paid_tier", False):
        err = (
            "genome.require_paid_tier is false. "
            "Set require_paid_tier=true to confirm you are using paid API quota."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 8: free_tier_only must be false ---
    if genome.get("free_tier_only", True):
        err = (
            "genome.free_tier_only is true. "
            "Set free_tier_only=false for paid-credit mode "
            "(requires billing-linked project)."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 9: monthly budget > 0 ---
    monthly_budget = float(genome.get("monthly_api_budget_usd", 0.0))
    if monthly_budget <= 0:
        err = (
            "genome.monthly_api_budget_usd is 0 or negative. "
            "Set a positive monthly budget to allow paid API calls."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 10: daily budget > 0 ---
    daily_budget = float(genome.get("daily_api_budget_usd", 0.0))
    if daily_budget <= 0:
        err = (
            "genome.daily_api_budget_usd is 0 or negative. "
            "Set a positive daily budget to allow paid API calls."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 11: max_model_requests_per_run <= 1 ---
    max_requests = int(genome.get("max_model_requests_per_run", 1))
    if max_requests > 1:
        err = (
            f"genome.max_model_requests_per_run is {max_requests}; "
            "must be <= 1 for safety. Reduce it in data/genome.json."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 12: safety flags ---
    if genome.get("allow_google_search_grounding", False):
        err = (
            "genome.allow_google_search_grounding is true. "
            "Grounding is disabled for safety; set it to false."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    if genome.get("allow_code_execution_tool", False):
        err = (
            "genome.allow_code_execution_tool is true. "
            "Code execution tool is disabled for safety; set it to false."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    if genome.get("allow_url_context", False):
        err = (
            "genome.allow_url_context is true. "
            "URL context is disabled for safety; set it to false."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    if genome.get("send_repository_full_text", False):
        err = (
            "genome.send_repository_full_text is true. "
            "Full repository text must never be sent to Gemini."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    if genome.get("send_raw_payloads", False):
        err = (
            "genome.send_raw_payloads is true. "
            "Raw payloads must never be sent to Gemini."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    if genome.get("send_secrets", False):
        err = (
            "genome.send_secrets is true. "
            "Secrets must never be sent to Gemini."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 13: Load and validate ledger (fail-closed) ---
    # Use strict_load_ledger so that a missing ledger is treated as
    # "budget state unknown" and preflight fails rather than continuing
    # with an assumed-empty spend history.
    try:
        ledger = budget.strict_load_ledger(_LEDGER_PATH)
    except ValueError as exc:
        err = f"API usage ledger is not usable; preflight fails (fail closed): {exc}"
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 14: Build prompt and check length ---
    model_name: str = genome.get("model_name", "gemini-2.0-flash")
    max_prompt_chars: int = int(genome.get("max_prompt_chars", 12000))
    max_output_tokens: int = int(genome.get("max_output_tokens", 2048))

    user_prompt = _build_user_prompt(genome, detector_source)
    full_prompt = _LLM_SYSTEM_PROMPT + "\n" + user_prompt

    if len(full_prompt) > max_prompt_chars:
        err = (
            f"Prompt too long: {len(full_prompt)} chars "
            f"exceeds max_prompt_chars={max_prompt_chars}. "
            "Preflight fails."
        )
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": err}, err

    # --- Step 15: Preflight secret scan ---
    scan_err = _preflight_secret_scan(full_prompt)
    if scan_err:
        return {"success": False, "mode": "gemini-paid-credit-preflight",
                "api_call_performed": False, "gemini_api_key_present": True,
                "live_model_enabled": False, "error": scan_err}, scan_err

    # --- Step 16: Cost estimation ---
    input_chars = len(full_prompt)
    # max_output_tokens is already a token cap — NOT a character count.
    # The conservative char-to-token estimator applies only to character-counted
    # inputs (like the prompt).  Re-estimating the token cap via
    # estimate_tokens_from_chars would multiply it by the char multiplier,
    # making valid budgets fail.
    est_input_tokens = budget.estimate_tokens_from_chars(input_chars)
    # For Gemini 3 models, thinking tokens are billed alongside output tokens.
    effective_output_token_budget = max_output_tokens
    if model_name.startswith("gemini-3"):
        effective_output_token_budget += _GEMINI3_THINKING_BUDGET_LOW
    est_output_tokens = effective_output_token_budget
    est_cost = budget.estimate_cost_usd(est_input_tokens, est_output_tokens, model_name)

    # --- Step 17: Budget availability check ---
    budget_ok, budget_err_msg = budget.assert_budget_available(genome, ledger, est_cost)

    result: dict = {
        "success": budget_ok,
        "mode": "gemini-paid-credit-preflight",
        "api_call_performed": False,
        "patch_path": None,
        "ledger_written": False,
        "live_model_enabled": False,
        "gemini_api_key_present": True,  # confirmed present — value never included
        "monthly_api_budget_usd": monthly_budget,
        "daily_api_budget_usd": daily_budget,
        "estimated_next_cost_usd": est_cost,
        "budget_available": budget_ok,
        "warnings": warnings,
    }

    if not budget_ok:
        result["error"] = budget_err_msg
        return result, budget_err_msg

    return result, ""


# ---------------------------------------------------------------------------
# Main proposal logic
# ---------------------------------------------------------------------------


def propose_mutation(
    *,
    offline_sample: bool = False,
    live_model: bool = False,
    allow_live_model: bool = False,
    gemini_paid_credit: bool = False,
) -> tuple[dict | None, str]:
    """Propose a mutation patch. Returns (patch, error).

    Args:
        offline_sample:      Return the built-in sample patch immediately.
        live_model:          Call Gemini (free-tier path).
        allow_live_model:    Explicit opt-in flag required by both live modes.
        gemini_paid_credit:  Call Gemini with budget enforcement and ledger.
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

    # ---- Paid-credit mode ----
    if gemini_paid_credit:
        # Gate: explicit opt-in flag
        if not allow_live_model:
            return None, (
                "--gemini-paid-credit requires --allow-live-model. "
                "Pass both flags together to explicitly opt in to paid API calls."
            )

        # Gate: API key
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return None, (
                "GEMINI_API_KEY environment variable is not set. "
                "Set GEMINI_API_KEY or use --offline-sample."
            )

        # Gate: live_model_enabled
        if not genome.get("live_model_enabled", False):
            return None, (
                "genome.live_model_enabled is false. "
                "Set live_model_enabled=true in data/genome.json to enable "
                "live API calls."
            )

        # Gate: require_paid_tier
        if not genome.get("require_paid_tier", False):
            return None, (
                "genome.require_paid_tier is false. "
                "Set require_paid_tier=true in data/genome.json to confirm "
                "you are using paid API quota."
            )

        # Gate: free_tier_only must be false
        if genome.get("free_tier_only", True):
            return None, (
                "genome.free_tier_only is true. "
                "Set free_tier_only=false in data/genome.json to enable "
                "paid-credit mode (requires billing-linked project)."
            )

        # Gate: monthly budget must be > 0
        if float(genome.get("monthly_api_budget_usd", 0.0)) <= 0:
            return None, (
                "genome.monthly_api_budget_usd is 0 or negative. "
                "Set a positive monthly budget to allow paid API calls."
            )

        # Gate: daily budget must be > 0
        if float(genome.get("daily_api_budget_usd", 0.0)) <= 0:
            return None, (
                "genome.daily_api_budget_usd is 0 or negative. "
                "Set a positive daily budget to allow paid API calls."
            )

        # Gate: max_model_requests_per_run
        max_requests = int(genome.get("max_model_requests_per_run", 1))
        if max_requests > 1:
            return None, (
                f"genome.max_model_requests_per_run is {max_requests}; "
                "must be <= 1 for safety. Reduce it in data/genome.json."
            )

        # Gate: no Google Search grounding
        if genome.get("allow_google_search_grounding", False):
            return None, (
                "genome.allow_google_search_grounding is true. "
                "Grounding is disabled for safety; set it to false."
            )

        # Gate: no code execution tool
        if genome.get("allow_code_execution_tool", False):
            return None, (
                "genome.allow_code_execution_tool is true. "
                "Code execution tool is disabled for safety; set it to false."
            )

        # Gate: no URL context
        if genome.get("allow_url_context", False):
            return None, (
                "genome.allow_url_context is true. "
                "URL context is disabled for safety; set it to false."
            )

        # Gate: must not send full repository
        if genome.get("send_repository_full_text", False):
            return None, (
                "genome.send_repository_full_text is true. "
                "Full repository text must never be sent to Gemini."
            )

        # Gate: must not send raw payloads
        if genome.get("send_raw_payloads", False):
            return None, (
                "genome.send_raw_payloads is true. "
                "Raw payloads must never be sent to Gemini."
            )

        # Gate: must not send secrets
        if genome.get("send_secrets", False):
            return None, (
                "genome.send_secrets is true. "
                "Secrets must never be sent to Gemini."
            )

        return _propose_via_gemini_paid_credit(
            genome, detector_source, api_key, _LEDGER_PATH
        )

    # ---- Live model mode (free-tier / backward-compat path) ----
    if live_model:
        # Gate: explicit opt-in flag
        if not allow_live_model:
            return None, (
                "--live-model requires --allow-live-model. "
                "Pass both flags together to explicitly opt in to API calls."
            )

        # Gate: API key
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return None, (
                "GEMINI_API_KEY environment variable is not set. "
                "Set GEMINI_API_KEY or use --offline-sample."
            )

        # Gate: genome.live_model_enabled
        if not genome.get("live_model_enabled", False):
            return None, (
                "genome.live_model_enabled is false. "
                "Set live_model_enabled=true in data/genome.json to enable "
                "live API calls."
            )

        # Gate: max_model_requests_per_run
        max_requests = int(genome.get("max_model_requests_per_run", 1))
        if max_requests > 1:
            return None, (
                f"genome.max_model_requests_per_run is {max_requests}; "
                "must be <= 1 for safety. Reduce it in data/genome.json."
            )

        # Gate: model safety — reject "pro" models when free_tier_only=true
        model_name: str = genome.get("model_name", "gemini-2.0-flash")
        if genome.get("free_tier_only", True) and "pro" in model_name.lower():
            return None, (
                f"model_name {model_name!r} contains 'pro' but "
                "genome.free_tier_only=true. "
                "Use a Flash/Flash-Lite model, or set free_tier_only=false "
                "with explicit budget approval."
            )

        # Gate: no Google Search grounding
        if genome.get("allow_google_search_grounding", False):
            return None, (
                "genome.allow_google_search_grounding is true. "
                "Grounding is disabled for safety; set it to false."
            )

        # Gate: no code execution tool
        if genome.get("allow_code_execution_tool", False):
            return None, (
                "genome.allow_code_execution_tool is true. "
                "Code execution tool is disabled for safety; set it to false."
            )

        # Phase 3 gate: legacy live-model path is disabled.
        # gemini-paid-credit is the only allowed live API path because it
        # enforces budget caps and ledger tracking on every call.
        return None, (
            "live-model mode is disabled for Phase 3. "
            "Use gemini-paid-credit so budget and ledger enforcement are applied."
        )

    # ---- No mode selected ----
    return None, (
        "No mutation mode selected. "
        "Use --noop, --offline-sample, --live-model --allow-live-model, "
        "or --gemini-paid-credit --allow-live-model."
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
            "Call the Gemini API (free-tier path) to propose a mutation. "
            "Requires --allow-live-model and all pre-flight gates."
        ),
    )
    parser.add_argument(
        "--gemini-paid-credit",
        action="store_true",
        help=(
            "Call the Gemini API with budget enforcement and ledger tracking "
            "(Google AI Pro $10/month GenAI & Cloud credit path). "
            "Requires --allow-live-model and all paid-tier gates."
        ),
    )
    parser.add_argument(
        "--gemini-paid-credit-preflight",
        action="store_true",
        help=(
            "Verify readiness for gemini-paid-credit without making any API call. "
            "No patch is generated and the ledger is not written. "
            "Checks genome settings, GEMINI_API_KEY existence (value never logged), "
            "ledger readability, prompt length, secret scan, and budget availability. "
            "live_model_enabled=false is the expected state for this preflight."
        ),
    )
    parser.add_argument(
        "--allow-live-model",
        action="store_true",
        help=(
            "Explicit opt-in to live API calls. "
            "Must be combined with --live-model or --gemini-paid-credit. "
            "Without this flag, live API calls are refused."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a JSON summary.",
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

    # ---- Preflight mode: verify readiness, no API call, no patch ----
    if args.gemini_paid_credit_preflight:
        result, err = run_gemini_paid_credit_preflight()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print("Preflight: gemini-paid-credit-preflight PASSED")
                print(f"  GEMINI_API_KEY present: {result.get('gemini_api_key_present')}")
                print(f"  live_model_enabled: {result.get('live_model_enabled')}")
                print(f"  monthly_api_budget_usd: {result.get('monthly_api_budget_usd')}")
                print(f"  daily_api_budget_usd: {result.get('daily_api_budget_usd')}")
                print(f"  estimated_next_cost_usd: {result.get('estimated_next_cost_usd'):.6f}")
                print(f"  budget_available: {result.get('budget_available')}")
                if result.get("warnings"):
                    for w in result["warnings"]:
                        print(f"  WARNING: {w}")
            else:
                print(f"Preflight FAILED: {err}", file=sys.stderr)
        return 0 if result.get("success") else 1

    patch, err = propose_mutation(
        offline_sample=args.offline_sample,
        live_model=args.live_model,
        allow_live_model=args.allow_live_model,
        gemini_paid_credit=args.gemini_paid_credit,
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

    if args.gemini_paid_credit:
        mode = "gemini-paid-credit"
    elif args.live_model:
        mode = "live-model"
    else:
        mode = "offline-sample"

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
