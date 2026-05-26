"""scripts/propose_mutation.py — Propose a mutation patch via LLM or local sample.

Usage:
    python scripts/propose_mutation.py [--offline-sample] [--json]

Behavior:
    - If --offline-sample is set, produce a safe local sample mutation_patch.json.
    - If GEMINI_API_KEY is present, use the Gemini API (stub for MVP).
    - The script NEVER executes model-generated code.
    - Enforces max_model_requests_per_run from genome.json.
    - All prompts request DEFENSIVE logic only.

SAFETY NOTE:
    The LLM is never asked to generate exploit payloads, attack code,
    or anything outside the internal logic of inspect_request().
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
_OUT_DIR = _PROJECT_ROOT / ".cyber_immunizer"
_OUT_PATCH = _OUT_DIR / "mutation_patch.json"

# ---------------------------------------------------------------------------
# Offline sample mutation (no API call)
# ---------------------------------------------------------------------------

_SAMPLE_MUTATION: dict = {
    "mutation_rationale": (
        "Extend the suspicious-token list with additional SQL injection indicators "
        "and tighten confidence scoring for multi-signal matches."
    ),
    "target_threats": ["THREAT-2024-002"],
    "expected_improvement": (
        "Improved true-positive rate for SQL injection patterns "
        "without increasing false positives on benign traffic."
    ),
    "risk": (
        "Minor risk of increased false positives if legitimate queries "
        "contain SQL-like keywords (e.g. product descriptions)."
    ),
    "replacement_code": '''\
    # --- mutated detector logic (sample) ---
    surface_parts = [
        request.method.lower(),
        request.path.lower(),
        " ".join(f"{k}={v}" for k, v in request.query.items()).lower(),
        " ".join(f"{k}:{v}" for k, v in request.headers.items()).lower(),
        request.body.lower(),
    ]
    surface = " ".join(surface_parts)

    _SUSPICIOUS_TOKENS: tuple[str, ...] = (
        # path-traversal
        "../", "..\\\\", "%2e%2e%2f", "%2e%2e/",
        # script-injection
        "<script", "javascript:", "onerror=", "onload=",
        # SQL-like
        "\\' or \\'1\\'=\\'1", "union select", "drop table", "\\'; --",
        "insert into", "select * from", "delete from",
        # command-like
        "; ls ", "| cat ", "`id`", "$(id)",
        # encoded
        "%00", "%0d%0a",
    )

    matched: list[str] = []
    for token in _SUSPICIOUS_TOKENS:
        if token in surface:
            matched.append(token)

    if matched:
        confidence = min(1.0, 0.4 + 0.15 * len(matched))
        return DetectionResult(
            blocked=True,
            reason=f"suspicious pattern(s) matched: {matched[0]!r}",
            confidence=confidence,
            matched_signals=tuple(matched),
        )

    return DetectionResult(
        blocked=False,
        reason="no suspicious pattern matched",
        confidence=0.0,
        matched_signals=(),
    )
''',
}

# ---------------------------------------------------------------------------
# LLM prompt template (Gemini stub)
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are a defensive security code assistant for Project Cyber-Immunizer.

STRICT RULES — YOU MUST FOLLOW ALL OF THEM:
1. Return JSON only. No explanatory text outside the JSON object.
2. Mutate ONLY the internal logic of inspect_request(). Do not change its signature.
3. Do NOT add imports. The only allowed imports are already present in the file.
4. Do NOT use I/O, file access, network calls, or subprocess.
5. Do NOT use eval(), exec(), compile(), getattr(), setattr(), or reflection.
6. Do NOT generate exploit payloads, attack code, or credential theft logic.
7. Preserve the DetectionResult return type exactly.
8. Prefer low false positives over high true positives.
9. The replacement_code field must contain ONLY Python code for the function body
   (no def statement, no function wrapper).

Return a JSON object with these exact fields:
{
  "mutation_rationale": "short explanation",
  "target_threats": ["threat-id-or-pattern"],
  "expected_improvement": "what metric is expected to improve",
  "risk": "brief risk summary",
  "replacement_code": "Python code string for the function body only"
}
"""

_LLM_USER_PROMPT_TEMPLATE = """Current detector body (between mutation markers):

{mutation_region}

Active threat IDs to address: {threat_ids}

Propose a mutation that improves defensive coverage while maintaining low false positives.
Return JSON only.
"""


def _extract_mutation_region(source: str) -> str:
    """Extract code between mutation markers."""
    start = "# === MUTATION_START ==="
    end = "# === MUTATION_END ==="
    s = source.find(start)
    e = source.find(end)
    if s == -1 or e == -1 or e <= s:
        return ""
    return source[s + len(start) : e].strip()


def _propose_via_gemini(genome: dict, detector_source: str) -> tuple[dict | None, str]:
    """Stub Gemini API call for MVP.  Returns (patch, error)."""
    try:
        import urllib.request  # noqa: F401 — checking availability only
    except ImportError:
        return None, "urllib not available"

    max_requests = int(genome.get("max_model_requests_per_run", 1))
    if max_requests < 1:
        return None, "max_model_requests_per_run is 0; no API calls allowed"

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None, "GEMINI_API_KEY not set"

    threat_ids_path = _PROJECT_ROOT / "data" / "active_threats.json"
    try:
        threats = json.loads(threat_ids_path.read_text(encoding="utf-8"))
        threat_ids = [t.get("id", "") for t in threats]
    except Exception:
        threat_ids = []

    mutation_region = _extract_mutation_region(detector_source)
    user_prompt = _LLM_USER_PROMPT_TEMPLATE.format(
        mutation_region=mutation_region,
        threat_ids=json.dumps(threat_ids),
    )

    # MVP stub — real Gemini API integration left for future sprint.
    # Implementing a live call here would require:
    #   1. Secret management review
    #   2. Rate limiting
    #   3. Response sanitisation
    #   4. Content policy enforcement
    # For now, return an error directing the user to use --offline-sample.
    return None, (
        "Live Gemini API integration is not yet implemented in this MVP. "
        "Use --offline-sample to generate a local sample patch, or implement "
        "the Gemini call in a future sprint after security review."
    )


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def propose_mutation(*, offline_sample: bool = False) -> tuple[dict | None, str]:
    """Propose a mutation patch. Returns (patch, error)."""
    # Load genome for rate-limit checks
    try:
        genome = json.loads(_GENOME_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"could not read genome.json: {exc}"

    # Load detector source
    try:
        detector_source = _DETECTOR_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return None, f"could not read detector: {exc}"

    if offline_sample:
        return _SAMPLE_MUTATION, ""

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None, (
            "GEMINI_API_KEY is not set and --offline-sample was not specified. "
            "Set GEMINI_API_KEY or use --offline-sample to generate a local patch."
        )

    return _propose_via_gemini(genome, detector_source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer mutation proposer")
    parser.add_argument(
        "--offline-sample",
        action="store_true",
        help="Generate a local sample patch without calling any API",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args(argv)

    patch, err = propose_mutation(offline_sample=args.offline_sample)

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

    output = {
        "success": True,
        "patch_path": str(_OUT_PATCH),
        "mutation_rationale": patch.get("mutation_rationale", ""),
        "target_threats": patch.get("target_threats", []),
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Patch written to: {_OUT_PATCH}")
        print(f"Rationale: {patch.get('mutation_rationale', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
