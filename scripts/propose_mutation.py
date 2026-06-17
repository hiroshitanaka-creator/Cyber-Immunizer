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
# DetectionResult canonical keyword-argument names (check 10)
# ---------------------------------------------------------------------------
_REQUIRED_DR_KWARGS: frozenset[str] = frozenset(
    {"blocked", "reason", "confidence", "matched_signals"}
)

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
        # Branch-based thresholds avoid runtime allocation risk from
        # multiplier expressions (e.g. float * len(matched)).
        confidence = 0.5
        if len(matched) > 1:
            confidence = 0.7
        if len(matched) > 2:
            confidence = 0.9
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
10. Preserve DetectionResult return. Every return must use exactly:
    return DetectionResult(
        blocked=<bool>,
        reason=<str>,
        confidence=<float>,
        matched_signals=<tuple>,
    )
    Keyword-only, all four names required, no extra names, no positional args,
    no **kwargs expansion.
11. DetectionResult field literals (dynamic expressions are always deferred):
    blocked: True/False — NOT "true", 0, 1, None, [], ()
    reason: str — NOT 42, True, False, None, [], ()
    confidence: float[0.0,1.0] — NOT "high", True, False, None, 1.5, -0.1
    matched_signals: tuple[str,...] — NOT "sql", [], {}, (1,2), (None,)
12. Modify only logic inside inspect_request. Do not change the function
    signature, do not add new top-level definitions.
    replacement_code is inserted as-is between # === MUTATION_START === and
    # === MUTATION_END === inside inspect_request() — it is a function body
    fragment, NOT a complete function definition.
    Do NOT include def inspect_request(...) or any def statement.
    Do NOT include # === MUTATION_START === or # === MUTATION_END === markers.
    Do NOT wrap code in markdown fences (```python ... ```).
13. Prefer low false positives. Maximize true positive rate while keeping
    false positive rate at or below 5%.
14. Use only neutralized symbolic indicators from the local test corpus.
    Tokens like path_traversal_indicator, script_injection_indicator,
    sqli_indicator, command_delimiter_indicator,
    encoded_traversal_indicator are the only detection signals.
    These tokens appear as uppercase in the JSON test corpus
    (PATH_TRAVERSAL_INDICATOR etc.) but the detector lowercases all input
    before matching, so use the lowercase forms in replacement_code.
    Do NOT add double-underscore prefix/suffix to these tokens.
15. Do not include real CVE exploit details. No actual vulnerability
    payloads, shellcode, or real attack strings.
16. Do not include raw offensive payloads. Use only the neutralized
    symbolic indicator tokens defined in the test corpus.
17. Avoid runtime allocation risk: non-constant repeat multiplier is rejected (e.g. 0.3 * count; use constant float 0.7).
18. Do not use list/set/dict comprehensions or generator expressions in replacement_code. Use explicit for-loop + append.

REPLACEMENT_CODE FORMAT CONTRACT:
replacement_code is inserted as-is as the body of inspect_request().
Every line must be a function-body fragment with correct indentation.

REQUIRED:
- Top-level replacement statements must start with EXACTLY 4 spaces.
- Nested blocks (inside if/for/while) must use exactly 8 spaces.
- Deeper nesting uses 12, 16, … spaces (always a multiple of 4).
- ALL indentation must be a multiple of 4 — never 1, 2, 3, 5, 6 spaces.
- Leading tabs are forbidden; use spaces only.
- Comment lines must also start with at least 4 spaces.
- Top-level return DetectionResult(...) must be at exactly 4-space
  indentation; a return nested inside an if/for/while block follows
  block depth (8, 12, … spaces).
- replacement_code must be syntactically valid Python as a function body —
  it is checked with ast.parse() and ANY SyntaxError is rejected fail-closed
  (no patch is written).
- replacement_code must contain executable detector logic.
- replacement_code must contain at least one return DetectionResult(...).
- replacement_code must end with a top-level (4-space) fallback return
  DetectionResult(...) after all conditional branches. Nested-only returns
  (inside if/for/while) leave an implicit-None fallthrough when no branch
  is taken. Always close the body with a top-level default, e.g.:
      return DetectionResult(blocked=False, reason="no match", confidence=0.0, matched_signals=())
- Empty lines are allowed.

FORBIDDEN:
- Do NOT return an empty body (only blank lines or only comments).
- Do NOT produce a pass-only body.
- Do NOT use placeholder ellipsis: a body whose only statement is ... is rejected.
- Do NOT omit return DetectionResult(...) — a return statement is mandatory.
- Do NOT end replacement_code without the top-level (4-space) fallback
  return DetectionResult(...) required above.
- Do NOT use any return shape other than: return DetectionResult(blocked=<bool>, reason=<str>, confidence=<float>, matched_signals=<tuple>) — keyword-only, all four names required, no extras, no positional args, no **kwargs.
- Do NOT start any line at column 0 (no top-level / unindented code).
- Do NOT use non-multiple-of-4 indentation (e.g. 6 spaces is rejected).
- Do NOT include def inspect_request(...) or any def / async def statement.
- Do NOT include mutation markers (# === MUTATION_START === etc.).
- Do NOT wrap in markdown fences (```python ... ```).

GOOD example — 4-space-indented function body (this WILL be accepted):
{
  "replacement_code": "    surface = request.path.lower() + \" \" + request.body.lower()\\n    matched = []\\n    if \"path_traversal_indicator\" in surface:\\n        matched.append(\"path_traversal_indicator\")\\n    if matched:\\n        return DetectionResult(blocked=True, reason=\"suspicious indicator matched\", confidence=0.7, matched_signals=tuple(matched))\\n    return DetectionResult(blocked=False, reason=\"no suspicious indicator matched\", confidence=0.0, matched_signals=())"
}

BAD example 1 — unindented body (will be REJECTED with indentation contract violation):
{
  "replacement_code": "surface = request.path.lower()\\nreturn DetectionResult(blocked=False, reason=\"no suspicious indicator matched\", confidence=0.0, matched_signals=())"
}

BAD example 2 — function definition included (will be REJECTED):
{
  "replacement_code": "def inspect_request(request):\\n    return DetectionResult(blocked=False, reason=\"no suspicious indicator matched\", confidence=0.0, matched_signals=())"
}

BAD example 3 — markdown fence included (will be REJECTED):
{
  "replacement_code": "```python\\n    return DetectionResult(blocked=False, reason=\"no suspicious indicator matched\", confidence=0.0, matched_signals=())\\n```"
}

BAD example 4 — nested-only return, no top-level fallback (will be REJECTED with fallthrough guard violation):
{
  "replacement_code": "    surface = request.path.lower()\\n    if \"path_traversal_indicator\" in surface:\\n        return DetectionResult(blocked=True, reason=\"traversal detected\", confidence=0.9, matched_signals=(\"path_traversal_indicator\",))\\n    # Implicit None fallthrough — MISSING top-level fallback return!"
}

Return a JSON object with these exact fields (no others):
{
  "mutation_rationale": "short explanation (max 600 chars)",
  "target_threats": ["threat-id-or-category"],
  "expected_improvement": "what metric is expected to improve (max 600 chars)",
  "risk": "brief risk summary (max 600 chars)",
  "replacement_code": "4-space-indented Python function body fragment for inspect_request() — no def statement, no markers, no markdown fences"
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

{scoring_guidance}
Propose a mutation that improves defensive coverage, keeps false positives low,
and scores strictly higher than previous_best. Use only neutralized symbolic
indicators -- never raw exploit strings. Return JSON only.
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
# Helpers: DetectionResult static value checks (check 11)
# ---------------------------------------------------------------------------


def _numeric_literal_value(node: ast.expr) -> int | float | None:
    """Return the numeric value of a bare or unary-signed numeric literal, or None.

    Accepts bare ast.Constant(int|float) nodes and ast.UnaryOp(USub|UAdd) nodes
    whose operand is an int or float constant.  bool is treated separately
    (bool is a subclass of int but is never a valid numeric literal here).
    Must not call eval, compile, exec, import, or ast.literal_eval.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = node.operand
        if isinstance(operand, ast.Constant):
            val = operand.value
            if isinstance(val, bool):
                return None  # bool is subclass of int; exclude
            if isinstance(val, (int, float)):
                return -val if isinstance(node.op, ast.USub) else val
        return None
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, bool):
            return None  # must check bool before int (bool is subclass of int)
        if isinstance(val, (int, float)):
            return val
    return None


def _is_unary_constant(node: ast.expr) -> bool:
    """Return True if node is UnaryOp(USub|UAdd, Constant(...)), False otherwise."""
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
    )


def _detection_result_static_value_violation(
    field_name: str, value: ast.expr
) -> str:
    """Return an error if value is a Category A obvious invalid literal for field_name.

    Uses field-domain allowlists: for each field only the literal AST forms that
    are unambiguously valid for that field's type domain are accepted; all other
    obvious literal forms (including unary-constant expressions) are rejected;
    non-literal dynamic expressions are deferred per Category B.
    Must not call eval, compile, exec, import, or ast.literal_eval.
    """
    _P = "replacement_code DetectionResult static value violation:"

    if field_name == "blocked":
        # Domain: bool only. Accept True/False; reject all other constants,
        # container literals, and UnaryOp over Constant; defer dynamic expressions.
        if isinstance(value, ast.Constant):
            if isinstance(value.value, bool):
                return ""  # True / False — valid
            return (
                f"{_P} blocked={value.value!r} is not a valid literal; "
                "blocked must be bool (True or False)"
            )
        if isinstance(value, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return (
                f"{_P} blocked=container literal is not valid; "
                "blocked must be bool (True or False)"
            )
        if _is_unary_constant(value):
            return (
                f"{_P} blocked=unary constant expression is not valid; "
                "blocked must be bool (True or False)"
            )
        return ""  # dynamic expression — defer

    if field_name == "reason":
        # Domain: str only. Accept str constants; reject all other constants,
        # container literals, and UnaryOp over Constant; defer dynamic expressions.
        if isinstance(value, ast.Constant):
            if isinstance(value.value, str):
                return ""  # string constant — valid
            return (
                f"{_P} reason={value.value!r} is not a valid literal; "
                "reason must be str"
            )
        if isinstance(value, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return (
                f"{_P} reason=container literal is not valid; "
                "reason must be str"
            )
        if _is_unary_constant(value):
            return (
                f"{_P} reason=unary constant expression is not valid; "
                "reason must be str"
            )
        return ""  # f-string, concatenation, variable, conditional — defer

    if field_name == "confidence":
        # Domain: float in [0.0, 1.0]. Accept float literals in range (bare or
        # signed UnaryOp over a float Constant); reject int literals even when in range.
        # Reject all other constants and container literals; defer dynamic expressions.
        if isinstance(value, ast.Constant):
            val = value.value
            if isinstance(val, bool):
                return (
                    f"{_P} confidence={val!r} is a bool literal; "
                    "confidence must be float in [0.0, 1.0]"
                )
            if isinstance(val, float):
                if val < 0.0 or val > 1.0:
                    return (
                        f"{_P} confidence={val!r} is out of range [0.0, 1.0]; "
                        "confidence must be float in [0.0, 1.0]"
                    )
                return ""
            return (
                f"{_P} confidence={val!r} is not a valid literal; "
                "confidence must be float in [0.0, 1.0]"
            )
        if isinstance(value, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return (
                f"{_P} confidence=container literal is not valid; "
                "confidence must be float in [0.0, 1.0]"
            )
        if _is_unary_constant(value):
            num_val = _numeric_literal_value(value)
            if num_val is not None:
                if not isinstance(value.operand.value, float):
                    return (
                        f"{_P} confidence=unary constant expression is not valid; "
                        "confidence must be float in [0.0, 1.0]"
                    )
                if num_val < 0.0 or num_val > 1.0:
                    return (
                        f"{_P} confidence={num_val!r} is out of range [0.0, 1.0]; "
                        "confidence must be float in [0.0, 1.0]"
                    )
                return ""
            return (
                f"{_P} confidence=unary constant expression is not valid; "
                "confidence must be float in [0.0, 1.0]"
            )
        return ""  # dynamic expression — defer

    if field_name == "matched_signals":
        # Domain: tuple[str, ...]. Accept tuple literal whose elements are all str
        # constants or dynamic expressions; reject all non-tuple top-level literals;
        # reject non-string and unary-constant tuple elements; defer dynamic.
        if isinstance(value, ast.Constant):
            val = value.value
            if isinstance(val, str):
                return (
                    f"{_P} matched_signals={val!r} is a string literal; "
                    "matched_signals must be tuple[str, ...]"
                )
            return (
                f"{_P} matched_signals constant {val!r} is not valid; "
                "matched_signals must be tuple[str, ...]"
            )
        if isinstance(value, (ast.List, ast.Dict, ast.Set)):
            return (
                f"{_P} matched_signals=container literal is not valid; "
                "matched_signals must be tuple[str, ...]"
            )
        if isinstance(value, ast.Tuple):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and not isinstance(elt.value, str):
                    return (
                        f"{_P} matched_signals=(...) contains a "
                        f"non-string constant element {elt.value!r}; "
                        "matched_signals must be tuple[str, ...]"
                    )
                if _is_unary_constant(elt):
                    return (
                        f"{_P} matched_signals=(...) contains an "
                        f"obvious invalid literal element; "
                        "matched_signals must be tuple[str, ...]"
                    )
                if isinstance(elt, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
                    return (
                        f"{_P} matched_signals=(...) contains a "
                        f"container literal element; "
                        "matched_signals must be tuple[str, ...]"
                    )
            return ""
        if _is_unary_constant(value):
            return (
                f"{_P} matched_signals=unary constant expression is not valid; "
                "matched_signals must be tuple[str, ...]"
            )
        return ""  # variable, Call, conditional — defer

    return ""  # unknown field — should not occur after check 10 passed


def _validate_detection_result_static_values(call: ast.Call) -> str:
    """Check Category A static value constraints for a DetectionResult(...) call.

    Called only after check 10 has validated keyword-only shape with exactly the
    four canonical keywords.  Returns the first violation message, or empty string.
    """
    kw_map = {kw.arg: kw.value for kw in call.keywords}
    for field_name in ("blocked", "reason", "confidence", "matched_signals"):
        value = kw_map.get(field_name)
        if value is None:
            continue  # defensive; check 10 guarantees all four are present
        err = _detection_result_static_value_violation(field_name, value)
        if err:
            return err
    return ""


# ---------------------------------------------------------------------------
# G1 repeat-multiplier helpers — used by check 6.5 in _validate_replacement_code
# ---------------------------------------------------------------------------


def _g1_is_repeat_const(node: ast.expr) -> bool:
    """Return True if node is an int, float, or string literal constant.

    All three types are repeat-multiplier bases that apply-side
    core/policy.py _check_repeat_mult() rejects when the other operand is
    runtime-derived: int/float are numeric multipliers; str is a string
    repetition base (``"a" * n`` where n is runtime-derived).
    """
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str))


def _g1_is_runtime_derived(node: ast.expr) -> bool:
    """Return True if node is a runtime-derived expression that apply-side
    core.policy._looks_like_int_expr treats as potentially integer-typed.

    Covers: bare variable names (ast.Name), attribute accesses (ast.Attribute,
    e.g. request.score), function/method calls (ast.Call, e.g. len(matched)),
    and arithmetic BinOp expressions that contain at least one runtime-derived
    sub-node (e.g. indicator_count + 1) — mirroring apply-side treatment of
    BinOp as integer-like.  Pure constant-only BinOps (e.g. 0.5 + 0.1) are
    not considered runtime-derived.
    """
    if isinstance(node, (ast.Name, ast.Attribute, ast.Call)):
        return True
    if isinstance(node, ast.BinOp):
        return any(
            isinstance(n, (ast.Name, ast.Attribute, ast.Call))
            for n in ast.walk(node)
        )
    return False


# ---------------------------------------------------------------------------
# Helper: validate replacement_code for forbidden patterns
# ---------------------------------------------------------------------------


def _validate_replacement_code(code: str) -> str:
    """Return an error message if replacement_code violates safety or format rules.

    Checks (in order):
    1. Mutation markers forbidden (would break apply_mutation.py).
    2. Markdown code fences forbidden (```) — Gemini must not wrap in fences.
    3. Function definition forbidden — replacement_code is a body fragment only.
    4. Forbidden security tokens (import, eval, exec, os., etc.).
    5. Indentation contract (all three must pass):
       a. No tab characters in leading whitespace.
       b. Minimum indentation of non-empty lines must be exactly 4 spaces
          (top-level body at 4; nested blocks at 8, 12, … per Python rules).
          min < 4: unindented or under-indented.
          min > 4: all lines over-indented (no top-level body present).
       c. All indentation counts must be multiples of 4; non-multiples
          (e.g. 6 spaces) indicate misaligned indentation and are rejected.
    6. Python syntax (AST parse only — code is never executed).
    6.5 Runtime allocation risk check — repeat-multiplier (G1 gap closure).
       Rejects BinOp(Mult) where one operand is a literal constant (int, float,
       or str) and the other is a runtime-derived expression (Name, Call,
       Attribute, or BinOp containing any of those), fail-closed before the
       patch is written.  Mirrors apply-side core/policy.py _check_repeat_mult().
       Covers 3 constant kinds × 4 runtime-derived kinds × 2 operand orders =
       up to 24 explicit shape combinations; does not claim full equivalence to
       core.policy.check_runtime_allocation_risks().
    6.6 Comprehension and unsafe generator expression rejection.
       Calls core.policy.check_runtime_allocation_risks() on the wrapped tree
       to reject ast.ListComp, ast.SetComp, ast.DictComp, and unsafe
       ast.GeneratorExp (any GeneratorExp not used as the sole argument to
       str.join() over request.query.items() or request.headers.items()).
       Re-uses core.policy to prevent policy drift between propose and apply
       stages. Run 7 failure root cause: list comprehension in replacement_code
       passed propose-stage but was rejected at apply-stage; this check closes
       that gap by failing closed at propose time. ImportError from core.policy
       also fails closed — the check must not be skipped silently.
    7. Semantic body validation (after successful AST parse):
       - replacement body (function body past _mutation_anchor) must not be empty.
       - replacement body must not contain only pass / comments.
       - replacement body must contain at least one ast.Return statement.
    8. Return shape validation: every return statement must return DetectionResult(...)
       directly (ast.Return → ast.Call → ast.Name(id="DetectionResult")).
       return None, return result, return True/False, and helper calls are rejected.
    9. Fallthrough guard: the last top-level replacement node must be a direct
       ast.Return (return DetectionResult(...)). A body that ends with a conditional
       block (if/for/while) containing only nested returns falls through to implicit
       None when no branch is taken. The top-level fallback return DetectionResult(...)
       at the end of the body prevents inspect_request() from returning None.
    10. DetectionResult argument shape: every bare DetectionResult(...) ast.Call
        in the replacement body — including returned calls, expression
        statements, assignments, and nested contexts — must use keyword-only
        arguments with exactly the four canonical keyword names:
        blocked, reason, confidence, matched_signals.
        Rejected: positional arguments, **kwargs expansion, duplicate keyword
        names, missing keyword names, extra keyword names, wrong keyword names.
    11. DetectionResult static value checks: every bare DetectionResult(...) call
        in the replacement body must use AST-literal values that are valid for
        each field (Category A rejection only; dynamic expressions defer).
        Rejected: blocked="true"/blocked=0/blocked=None (must be bool literal),
        reason=42/reason=True/reason=None (must be str), confidence="high"/
        confidence=True/confidence=1.5/confidence=-0.1 (must be float in
        [0.0, 1.0]), matched_signals="sql"/matched_signals=["a"]/
        matched_signals=(1, 2) (must be tuple[str, ...]).
        Allowed/deferred: True/False for blocked; string literals/f-strings for
        reason; float in [0.0, 1.0] for confidence; empty or string-element
        tuples for matched_signals; all dynamic expressions for all fields.

    Returns empty string if the code passes all checks.
    """
    # 1. Reject mutation markers in replacement code
    if _MUTATION_START_MARKER in code or _MUTATION_END_MARKER in code:
        return (
            "replacement_code contains mutation marker(s). "
            "Markers are forbidden inside replacement_code."
        )
    # 2. Reject markdown code fences
    if "```" in code:
        return (
            "replacement_code contains a markdown code fence (```). "
            "Markdown formatting is forbidden in replacement_code."
        )
    # 3. Reject function definitions at any indentation level
    # (replacement_code must be a body fragment — no nested helpers, no wrapper)
    if re.search(r"(?m)^\s*(?:async\s+def|def)\s+\w+\s*\(", code):
        return (
            "replacement_code must not include a function definition. "
            "Provide the function body only — no def statement, "
            "no inspect_request wrapper."
        )
    # 4. Reject forbidden security tokens
    for token in _BLOCKED_CODE_TOKENS:
        if token in code:
            return (
                f"replacement_code contains forbidden token {token!r}. "
                "Unsafe replacement_code rejected before writing patch."
            )
    # 5. Indentation contract: tab-free; top-level lines at exactly 4 spaces;
    # all indentation must be a multiple of 4.
    # replacement_code is inserted inside inspect_request() as-is.
    # Top-level body lines must start with exactly 4 spaces.
    # Nested blocks use 8, 12, 16, … spaces (multiples of 4).
    # Collecting non-empty lines (blank lines and whitespace-only lines are OK).
    non_empty = [ln for ln in code.splitlines() if ln.strip()]
    if non_empty:
        # 5a. No tabs in leading whitespace (TabError at runtime)
        for ln in non_empty:
            leading = ln[: len(ln) - len(ln.lstrip())]
            if "\t" in leading:
                return (
                    "replacement_code indentation contract violation: "
                    "tab indentation is forbidden; use 4-space indentation"
                )
        # 5b. Minimum indentation must be exactly 4 spaces.
        min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
        if min_indent < 4:
            return (
                "replacement_code indentation contract violation: "
                "replacement_code must be a 4-space-indented function body "
                "for inspect_request()"
            )
        if min_indent > 4:
            return (
                "replacement_code indentation contract violation: "
                "top-level statements must start with exactly 4 spaces; "
                f"minimum indentation found is {min_indent} "
                "(all lines are over-indented — missing top-level body)"
            )
        # 5c. All indentation must be a multiple of 4 spaces.
        # Nested blocks use 8, 12, 16, … spaces; non-multiples (e.g. 6) are
        # invalid and indicate misaligned indentation.
        for ln in non_empty:
            indent = len(ln) - len(ln.lstrip())
            if indent % 4 != 0:
                return (
                    "replacement_code indentation contract violation: "
                    "all indentation must be a multiple of 4 spaces; "
                    f"line has {indent}-space indentation"
                )
    # 6 & 7. Validate Python syntax and then check semantic body requirements.
    # The wrapper establishes a function body with _mutation_anchor so the
    # suite is valid even for empty replacement_code; semantic validation
    # (check 7) then enforces that there is actual detector logic.
    # Code is never executed — ast.parse() only builds the parse tree.
    # IndentationError (subclass of SyntaxError) signals residual indentation
    # problems not caught by the pre-checks above.
    # Lone surrogates or other ill-formed Unicode may trigger UnicodeError;
    # caught separately so the class name (not the message, which could echo
    # replacement_code content) is returned as the validation error.
    wrapped = (
        "def _candidate_body(request):\n"
        "    _mutation_anchor = None\n"
        "    " + _MUTATION_START_MARKER + "\n"
        + code
        + "\n" + _MUTATION_END_MARKER + "\n"
    )
    try:
        tree = ast.parse(wrapped)
    except IndentationError:
        return (
            "replacement_code indentation contract violation: "
            "replacement_code must be a 4-space-indented function body "
            "for inspect_request()"
        )
    except SyntaxError as exc:
        return f"replacement_code is not valid Python syntax: {exc}"
    except UnicodeError as exc:
        return f"replacement_code is not valid Python source text: {type(exc).__name__}"
    else:
        # 6.5 Runtime allocation risk check — repeat-multiplier (G1 gap closure).
        # Rejects BinOp(Mult) where one operand is a literal constant (int,
        # float, or str) and the other is a runtime-derived expression (Name,
        # Call, Attribute, or arithmetic BinOp containing any of those) —
        # mirrors apply-side core/policy.py _check_repeat_mult().
        # Constant kinds: int, float, str.
        # Runtime-derived kinds: Name, Call, Attribute, BinOp(runtime).
        # Both operand orders rejected.
        # Violation string matches core/policy.py exactly for consistent errors.
        for _g1_node in ast.walk(tree):
            if isinstance(_g1_node, ast.BinOp) and isinstance(_g1_node.op, ast.Mult):
                _g1_l, _g1_r = _g1_node.left, _g1_node.right
                if (
                    (_g1_is_repeat_const(_g1_l) and _g1_is_runtime_derived(_g1_r))
                    or (_g1_is_repeat_const(_g1_r) and _g1_is_runtime_derived(_g1_l))
                ):
                    return (
                        "replacement_code runtime allocation risk violation: "
                        "runtime allocation risk: repeat multiplier is non-constant "
                        "(cannot bound statically) — fail-closed"
                    )
        # 6.6 Comprehension and unsafe generator expression rejection.
        # Rejects ast.ListComp, ast.SetComp, ast.DictComp, and unsafe
        # ast.GeneratorExp by calling core.policy.check_runtime_allocation_risks().
        # Mirrors apply-stage policy so candidates with comprehensions are
        # rejected at propose time before any patch is written (fail-closed).
        # Re-using core.policy avoids policy drift between propose and apply stages.
        # ImportError is also fail-closed: if core.policy is unavailable the safety
        # check cannot run, so the candidate is rejected rather than silently allowed.
        try:
            from core import policy as _core_policy  # type: ignore[import]
            _alloc_violations = _core_policy.check_runtime_allocation_risks(tree)
            if _alloc_violations:
                return (
                    "replacement_code runtime allocation risk violation: "
                    + _alloc_violations[0]
                )
        except ImportError as exc:
            return (
                "replacement_code runtime allocation risk violation: "
                f"core.policy unavailable for check 6.6 ({type(exc).__name__}) — fail-closed"
            )

        # 7. Semantic body validation.
        # Find _candidate_body in the parsed tree and inspect its body.
        # body[0] is always _mutation_anchor = None (the anchor statement).
        # body[1:] is the replacement region — it must not be empty, must not
        # consist solely of pass statements, and must contain at least one
        # return statement anywhere (guaranteeing a DetectionResult return path).
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_candidate_body":
                func_body = node.body
                replacement_nodes = func_body[1:]  # skip _mutation_anchor
                if not replacement_nodes:
                    return (
                        "replacement_code body is empty: replacement_code must "
                        "contain executable detector logic and at least one "
                        "return DetectionResult(...) statement"
                    )
                if all(isinstance(n, ast.Pass) for n in replacement_nodes):
                    return (
                        "replacement_code must contain executable detector logic; "
                        "pass-only body is not valid — at least one "
                        "return DetectionResult(...) is required"
                    )
                has_return = any(
                    isinstance(n, ast.Return)
                    for stmt in replacement_nodes
                    for n in ast.walk(stmt)
                )
                if not has_return:
                    return (
                        "replacement_code must contain at least one return "
                        "statement; a DetectionResult return is required"
                    )
                # 8. Every return statement must return DetectionResult(...).
                # Accepted shape: ast.Return → ast.Call → ast.Name(id="DetectionResult").
                # return None, return result, return True/False, qualified names,
                # and helper function calls are all rejected (intentionally strict).
                for stmt in replacement_nodes:
                    for n in ast.walk(stmt):
                        if isinstance(n, ast.Return):
                            val = n.value
                            if not (
                                isinstance(val, ast.Call)
                                and isinstance(val.func, ast.Name)
                                and val.func.id == "DetectionResult"
                            ):
                                return (
                                    "replacement_code return contract violation: "
                                    "every return statement must return "
                                    "DetectionResult(...)"
                                )
                # 9. Fallthrough guard: the last top-level replacement node must
                # be a direct ast.Return.  A body ending with a conditional block
                # (if/for/while) that contains only nested returns can fall through
                # to implicit None when no conditional branch is taken.
                # Requiring a top-level fallback return DetectionResult(...) at
                # the end of the body prevents inspect_request() from returning None.
                # Check 8 above already validated every return is DetectionResult(...),
                # so this check only needs to verify the node type is ast.Return.
                last_node = replacement_nodes[-1]
                if not isinstance(last_node, ast.Return):
                    return (
                        "replacement_code fallthrough guard violation: "
                        "the last top-level statement must be a direct "
                        "return DetectionResult(...) fallback; "
                        "nested-only return paths can fall through to implicit None"
                    )
                # 10. DetectionResult argument shape.
                # Walk every ast.Call whose func is bare DetectionResult —
                # returned calls, expression statements, assignments, and any
                # other executable context. A malformed non-return constructor
                # call can raise before the fallback return is reached.
                for stmt in replacement_nodes:
                    for n in ast.walk(stmt):
                        if not (
                            isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == "DetectionResult"
                        ):
                            continue
                        if n.args:
                            return (
                                "replacement_code DetectionResult argument "
                                "shape violation: DetectionResult(...) must "
                                "use keyword-only arguments; positional "
                                "arguments are not allowed"
                            )
                        for kw in n.keywords:
                            if kw.arg is None:
                                return (
                                    "replacement_code DetectionResult argument "
                                    "shape violation: DetectionResult(...) must "
                                    "not use **kwargs expansion"
                                )
                        # Duplicate keyword names collapse under set conversion;
                        # detect them before the missing/extra comparison.
                        kw_names_list = [kw.arg for kw in n.keywords]
                        seen_kw: set[str] = set()
                        for kw_name in kw_names_list:
                            if kw_name in seen_kw:
                                return (
                                    "replacement_code DetectionResult argument "
                                    "shape violation: DetectionResult(...) has "
                                    f"duplicate keyword argument: {kw_name!r}"
                                )
                            seen_kw.add(kw_name)
                        provided = seen_kw
                        missing_kw = _REQUIRED_DR_KWARGS - provided
                        extra_kw = provided - _REQUIRED_DR_KWARGS
                        if missing_kw:
                            return (
                                "replacement_code DetectionResult argument "
                                "shape violation: DetectionResult(...) is "
                                "missing required keyword argument(s): "
                                f"{sorted(missing_kw)}"
                            )
                        if extra_kw:
                            return (
                                "replacement_code DetectionResult argument "
                                "shape violation: DetectionResult(...) has "
                                "extra keyword argument(s): "
                                f"{sorted(extra_kw)}"
                            )
                # 11. DetectionResult static value checks (Category A).
                # Runs after check 10 has confirmed every DetectionResult call
                # has correct keyword-only shape.  Only obvious invalid AST
                # literals are rejected; dynamic expressions defer.
                for stmt in replacement_nodes:
                    for n in ast.walk(stmt):
                        if not (
                            isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == "DetectionResult"
                        ):
                            continue
                        val_err = _validate_detection_result_static_values(n)
                        if val_err:
                            return val_err
                break
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
# Helper: build score-aware optimization guidance for the user prompt
# ---------------------------------------------------------------------------


def _build_scoring_guidance(genome: dict) -> str:
    """Build score-aware guidance text for the Gemini user prompt.

    Teaches the model the deterministic adoption-gate score formula and the
    previous-best target so a proposed mutation aims to *beat* the current
    detector rather than merely producing a structurally valid patch. Also
    states a baseline-preservation contract (keep all five symbolic indicators,
    the full request inspection surface, and the final non-blocking fallback)
    so candidates extend rather than regress current coverage. Uses only
    non-secret numeric genome settings; never includes secrets, env vars, full
    repo text, raw payloads, or private vulnerability details.

    A missing or non-numeric genome field falls back to the literal text
    ``unknown`` rather than inventing a value (fail-safe — never fabricate).
    """

    def _num(key: str) -> str:
        val = genome.get(key)
        # bool is a subclass of int; exclude it so True/False never leak in as
        # a numeric value. Only real int/float settings are surfaced verbatim.
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return "unknown"
        return f"{val}"

    best_score = _num("best_score")
    max_fp_rate = _num("max_fp_rate")
    min_regression_pass_rate = _num("min_regression_pass_rate")
    max_avg_latency_ms = _num("max_avg_latency_ms")

    return (
        "SCORING-AWARE GUIDANCE:\n"
        f"- previous_best (current best detector score): {best_score}. A valid patch is NOT\n"
        "  enough; it must score STRICTLY GREATER THAN previous_best or the gate rejects.\n"
        "- score = 1000*tp_rate - 2000*fp_rate - 1500*fn_rate - 50*exception_count\n"
        "  - 0.02*code_chars (avg_latency and changed_lines excluded from score).\n"
        "- changed_lines is diagnostic-only and is NOT part of the adoption gate score.\n"
        f"- Hard gates: fp_rate<=max_fp_rate ({max_fp_rate}); regression_pass_rate>="
        f"min_regression_pass_rate ({min_regression_pass_rate}); "
        f"avg_latency_ms<=max_avg_latency_ms ({max_avg_latency_ms}).\n"
        "BASELINE CONTRACT (do NOT regress coverage):\n"
        "- Keep five indicators: path_traversal_indicator, script_injection_indicator,\n"
        "  sqli_indicator, command_delimiter_indicator, encoded_traversal_indicator.\n"
        "- Keep the full surface: request.method, request.path, request.query, request.headers,\n"
        "  request.body.\n"
        "- Keep a blocked=False fallback so false positives stay low.\n"
        "- Make a minimal additive edit; do NOT replace or narrow it. Keep code size small\n"
        "  and logic deterministic; prefer branch-constant confidence over a multiplier\n"
        "  like 0.3*count.\n"
        "- Lesson: recent candidates were REJECTED for scoring below best despite a valid patch.\n"
        "- NO-COMPREHENSION: list/set/dict comprehensions and generator expressions rejected; use for-loop + append."
    )


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
        scoring_guidance=_build_scoring_guidance(genome),
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
# Conservative thinking token allowance for Gemini 3 "low" thinking_level mode.
# Used only for budget estimation — not a hard cap sent to the API.
# Gemini 3 API receives ThinkingConfig(thinking_level="low") instead.
_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS = 1024

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
) -> tuple[str | None, int | None, int | None, int | None, str]:
    """Issue a Gemini API call with explicit timeout and bounded transient retry.

    Returns (raw_text, actual_input_tokens, actual_output_tokens,
             actual_thinking_tokens, error).
    On error, raw_text is None and error is non-empty.
    actual_input_tokens / actual_output_tokens / actual_thinking_tokens may be
    None if the API does not return usage metadata.

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
        return None, None, None, None, (
            f"Gemini API call failed: invalid max_attempts={max_attempts!r} — "
            "request budget must be >= 1."
        )

    try:
        from google import genai  # type: ignore[import]
        from google.genai import types as genai_types  # type: ignore[import]
    except ImportError:
        return None, None, None, None, (
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
        return None, None, None, None, (
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

    # Gemini 3 models support dynamic thinking.  Pass thinking_config with
    # thinking_level="low" to request the lowest thinking mode.
    # Gemini 2.x models do not accept this field, so only include it for gemini-3.
    # thinking_level and thinking_budget must not be specified together.
    #
    # Guard: older google-genai SDKs may not expose ThinkingConfig or may not
    # accept thinking_level.  Fail closed with a controlled error rather than
    # raising an unhandled exception before generate_content is even called.
    _generate_config_kwargs: dict = dict(
        system_instruction=_LLM_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_PATCH_SCHEMA_FOR_GEMINI,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    if model_name.startswith("gemini-3"):
        try:
            _generate_config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_level="low"
            )
        except Exception as exc:
            return None, None, None, None, (
                "Gemini API call failed: installed google-genai SDK does not support "
                f"ThinkingConfig(thinking_level=...) ({type(exc).__name__}). "
                "Upgrade google-genai before using gemini-3 models."
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
            actual_thinking_tokens: int | None = None
            try:
                usage = response.usage_metadata
                if usage is not None:
                    actual_input_tokens = getattr(usage, "prompt_token_count", None)
                    actual_output_tokens = getattr(usage, "candidates_token_count", None)
                    actual_thinking_tokens = getattr(usage, "thoughts_token_count", None)
            except Exception:
                pass

            return raw_text, actual_input_tokens, actual_output_tokens, actual_thinking_tokens, ""

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
    return None, None, None, None, (
        f"Gemini API call failed after {attempt} attempt{plural}: "
        f"{classification} error {last_exc_detail}"
    )


# ---------------------------------------------------------------------------
# Parse and validate Gemini response
# ---------------------------------------------------------------------------

# Stage marker appended to every model-output rejection so run logs and the
# ledger error field cannot be misread as an API/transport failure.  The three
# paid-credit runs of 2026-06-03/04 recorded success=true (HTTP 200 + tokens)
# while propose failed here — at the output-contract boundary, after the call.
_OUTPUT_CONTRACT_STAGE = (
    "propose/output-contract failure — the Gemini API call succeeded; "
    "the model output was rejected before any patch was written"
)


def _parse_and_validate_response(raw_text: str) -> tuple[dict | None, str]:
    """Parse JSON, validate schema, and check replacement_code safety.

    Returns (patch, error).
    Only reached when the API call itself succeeded (callers check api_err
    first), so every error returned here is an output-contract failure,
    never an API failure.
    """
    try:
        patch = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, (
            f"Gemini response is not valid JSON ({_OUTPUT_CONTRACT_STAGE}): {exc}"
        )

    schema_err = _validate_patch_schema(patch)
    if schema_err:
        return None, (
            f"Gemini response failed schema validation ({_OUTPUT_CONTRACT_STAGE}): "
            f"{schema_err}"
        )

    code_err = _validate_replacement_code(patch["replacement_code"])
    if code_err:
        return None, (
            f"Gemini replacement_code validation failed ({_OUTPUT_CONTRACT_STAGE}): "
            f"{code_err}"
        )

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

    raw_text, _inp_tok, _out_tok, _think_tok, api_err = _call_gemini_api(
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
    # For Gemini 3 models running with thinking_level="low", thinking tokens are
    # billed alongside output tokens per Google pricing docs.  Add a conservative
    # allowance (_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS) — not a hard cap, but a
    # prudent worst-case estimate for the pre-call budget gate.
    effective_output_token_budget = max_output_tokens
    if model_name.startswith("gemini-3"):
        effective_output_token_budget += _GEMINI3_THINKING_ESTIMATE_LOW_TOKENS
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
    raw_text, actual_input_tokens, actual_output_tokens, actual_thinking_tokens, api_err = (
        _call_gemini_api(
            api_key, model_name, user_prompt, max_output_tokens, temperature,
            max_attempts=request_attempt_budget,
        )
    )

    # Compute actual billable response tokens for Gemini 3 thinking models.
    # thinking_level="low" is not a hard cap; actual thoughts_token_count can
    # exceed the conservative pre-call allowance.  Use the larger of the
    # pre-call estimate and the actual billed tokens to avoid under-recording.
    actual_billable_response_tokens: int | None = None
    if actual_output_tokens is not None and actual_thinking_tokens is not None:
        actual_billable_response_tokens = actual_output_tokens + actual_thinking_tokens
    elif actual_output_tokens is not None:
        actual_billable_response_tokens = actual_output_tokens

    # If actual billable tokens exceeded the pre-call estimate, flag it.
    # We still record usage so the ledger reflects the real cost, then fail.
    overrun_err = ""
    if (
        api_err == ""
        and actual_billable_response_tokens is not None
        and actual_billable_response_tokens > est_output_tokens
    ):
        overrun_err = (
            "actual billable response tokens exceeded pre-call estimate; "
            "refusing to return patch after recording usage."
        )

    # Append usage record — HARD ERROR if ledger write fails.
    # An API call whose cost cannot be recorded into the ledger must NOT be
    # treated as a success: it would leave the budget cap in a fail-open
    # state for future calls.  We try to record success or failure; if
    # either record write fails, we return an error regardless of whether
    # the API call itself succeeded.
    effective_error = api_err or overrun_err
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
            actual_thinking_tokens=actual_thinking_tokens,
            actual_billable_response_tokens=actual_billable_response_tokens,
            success=(effective_error == ""),
            error=effective_error,
        )
    except (ValueError, OSError) as ledger_exc:
        ledger_err = (
            f"API usage ledger write failed: {ledger_exc}. "
            "Cannot confirm budget was recorded; refusing to return patch."
        )
        if effective_error:
            return None, f"{effective_error} — additionally, {ledger_err}"
        return None, ledger_err

    if effective_error:
        return None, effective_error

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
    # For Gemini 3 models running with thinking_level="low", add a conservative
    # thinking token allowance to the preflight budget estimate.
    effective_output_token_budget = max_output_tokens
    if model_name.startswith("gemini-3"):
        effective_output_token_budget += _GEMINI3_THINKING_ESTIMATE_LOW_TOKENS
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
