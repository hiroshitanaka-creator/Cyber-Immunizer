"""scripts/apply_mutation.py — Apply a mutation patch to a detector file.

Usage:
    python scripts/apply_mutation.py \\
        --patch mutation_patch.json \\
        --base core/detector.py \\
        --out .cyber_immunizer/candidate_detector.py \\
        [--json]

Exit codes:
    0  Mutation applied and candidate passed validation
    1  Mutation rejected (see output)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_mutation import validate  # noqa: E402

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="

_REQUIRED_PATCH_FIELDS = (
    "mutation_rationale",
    "target_threats",
    "expected_improvement",
    "risk",
    "replacement_code",
)


def _parse_patch(patch_path: Path) -> tuple[dict | None, str]:
    """Parse and validate the mutation patch JSON.

    Returns (patch_dict, error_message).  error_message is empty on success.
    """
    if not patch_path.exists():
        return None, f"patch file not found: {patch_path}"

    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in patch: {exc}"

    if not isinstance(patch, dict):
        return None, "patch must be a JSON object"

    for field in _REQUIRED_PATCH_FIELDS:
        if field not in patch:
            return None, f"missing required field in patch: {field!r}"

    replacement = patch["replacement_code"]
    if not isinstance(replacement, str):
        return None, "replacement_code must be a string"

    # Reject if replacement contains mutation markers (prevents nested markers)
    if _MUTATION_START in replacement or _MUTATION_END in replacement:
        return None, (
            "replacement_code must not contain mutation markers "
            f"({_MUTATION_START!r} or {_MUTATION_END!r})"
        )

    return patch, ""


def _apply_replacement(base_source: str, replacement_code: str) -> tuple[str | None, str]:
    """Replace the mutation region in base_source with replacement_code.

    Returns (new_source, error).
    """
    start_idx = base_source.find(_MUTATION_START)
    end_idx = base_source.find(_MUTATION_END)

    if start_idx == -1:
        return None, f"base file missing {_MUTATION_START!r}"
    if end_idx == -1:
        return None, f"base file missing {_MUTATION_END!r}"
    if end_idx <= start_idx:
        return None, "MUTATION_END appears before MUTATION_START in base file"

    # Preserve everything up to and including MUTATION_START line
    before = base_source[: start_idx + len(_MUTATION_START)]
    # Preserve everything from MUTATION_END onwards
    after = base_source[end_idx:]

    # Build new source: before + newline + replacement + newline + after
    new_source = before + "\n" + replacement_code.rstrip("\n") + "\n" + after

    return new_source, ""


def apply_mutation(
    patch_path: Path,
    base_path: Path,
    out_path: Path,
) -> dict:
    """Apply mutation patch and validate the resulting candidate.

    Returns a result dict with keys: success, candidate_path, violations, error.
    """
    # --- Parse patch ---
    patch, err = _parse_patch(patch_path)
    if err:
        return {"success": False, "candidate_path": None, "violations": [], "error": err}

    # --- Read base ---
    if not base_path.exists():
        return {
            "success": False,
            "candidate_path": None,
            "violations": [],
            "error": f"base file not found: {base_path}",
        }
    base_source = base_path.read_text(encoding="utf-8")

    # --- Apply replacement ---
    new_source, err = _apply_replacement(base_source, patch["replacement_code"])
    if err:
        return {"success": False, "candidate_path": None, "violations": [], "error": err}

    # --- Write candidate ---
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_source, encoding="utf-8")

    # --- Validate candidate ---
    val_result = validate(out_path)
    if not val_result["valid"]:
        # Remove invalid candidate
        out_path.unlink(missing_ok=True)
        return {
            "success": False,
            "candidate_path": None,
            "violations": val_result["violations"],
            "error": "candidate failed AST validation",
        }

    return {
        "success": True,
        "candidate_path": str(out_path),
        "violations": [],
        "error": "",
        "mutation_rationale": patch.get("mutation_rationale", ""),
        "target_threats": patch.get("target_threats", []),
        "expected_improvement": patch.get("expected_improvement", ""),
        "risk": patch.get("risk", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer mutation applier")
    parser.add_argument("--patch", required=True, help="Path to mutation_patch.json")
    parser.add_argument("--base", required=True, help="Path to base detector (e.g. core/detector.py)")
    parser.add_argument("--out", required=True, help="Output path for candidate detector")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    result = apply_mutation(
        patch_path=Path(args.patch),
        base_path=Path(args.base),
        out_path=Path(args.out),
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"SUCCESS: candidate written to {result['candidate_path']}")
        else:
            print(f"FAILURE: {result['error']}")
            for v in result.get("violations", []):
                print(f"  - {v}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
