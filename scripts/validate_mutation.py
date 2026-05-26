"""scripts/validate_mutation.py — AST and contract validation for candidate detectors.

Usage:
    python scripts/validate_mutation.py --candidate core/detector.py [--json]

Exit codes:
    0  Validation passed
    1  Validation failed (see output for reasons)

POLICY SOURCE OF TRUTH
======================
All AST policy logic lives in core/policy.py.  This module is a thin wrapper
that preserves the historical public API (validate()) while delegating to the
authoritative policy runner.  Do NOT duplicate policy constants here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.policy import run_full_policy  # noqa: E402


# ---------------------------------------------------------------------------
# Public entry point (thin wrapper around core.policy.run_full_policy)
# ---------------------------------------------------------------------------

def validate(candidate_path: Path) -> dict:
    """Validate a candidate detector file.

    Returns a dict with:
        valid: bool
        violations: list[str]

    All policy logic is delegated to core.policy.run_full_policy() — this
    function is kept for backward compatibility with callers such as
    apply_mutation.py and evaluate_candidate.py.
    """
    return run_full_policy(candidate_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer mutation validator")
    parser.add_argument("--candidate", required=True, help="Path to candidate detector")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    result = validate(Path(args.candidate))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["valid"]:
            print("VALID: candidate passes all AST policy checks")
        else:
            print(f"INVALID: {len(result['violations'])} violation(s)")
            for v in result["violations"]:
                print(f"  - {v}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
