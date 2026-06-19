"""scripts/validate_state.py — Strict schema validation for project state files.

Usage:
    python scripts/validate_state.py [--json]

Exit codes:
    0  All files pass validation
    1  One or more violations found

Validates:
    data/genome.json             — numeric thresholds and safety booleans
    data/evolution_history.json  — list structure, generation/hash/gate types
    data/project_state.json      — well-formed JSON (schema is intentionally open)
    data/active_threats.json     — via intelligence.threat_feeds strict loader
    data/benign_requests.json    — corpus schema via core.test_attacker
    data/attack_requests.json    — corpus schema via core.test_attacker
    data/regression_cases.json   — corpus schema via core.test_attacker

This script is for local and future CI use.  It does NOT trigger any paid-credit
workflow, Gemini API call, or workflow_dispatch.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DATA_DIR = _PROJECT_ROOT / "data"

_HEX_RE = re.compile(r"^[0-9a-f]+$")


# ---------------------------------------------------------------------------
# Individual file validators
# ---------------------------------------------------------------------------

def _check_genome(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        genome = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"genome.json: malformed JSON: {exc}"]
    except OSError as exc:
        return [f"genome.json: read error: {exc}"]

    if not isinstance(genome, dict):
        return [f"genome.json: top-level must be dict, got {type(genome).__name__!r}"]

    # best_score must be a finite number
    bs = genome.get("best_score")
    if not isinstance(bs, (int, float)) or isinstance(bs, bool) or not math.isfinite(bs):
        violations.append(
            f"genome.json: best_score must be a finite number, got {bs!r}"
        )

    # generation must be a strict int >= 0
    gen = genome.get("generation")
    if not isinstance(gen, int) or isinstance(gen, bool) or gen < 0:
        violations.append(
            f"genome.json: generation must be int >= 0, got {gen!r}"
        )

    # max_fp_rate in [0.0, 1.0]
    mfp = genome.get("max_fp_rate")
    if not isinstance(mfp, (int, float)) or isinstance(mfp, bool) or not (0.0 <= mfp <= 1.0):
        violations.append(
            f"genome.json: max_fp_rate must be in [0.0, 1.0], got {mfp!r}"
        )

    # min_regression_pass_rate in [0.0, 1.0]
    mrpr = genome.get("min_regression_pass_rate")
    if not isinstance(mrpr, (int, float)) or isinstance(mrpr, bool) or not (0.0 <= mrpr <= 1.0):
        violations.append(
            f"genome.json: min_regression_pass_rate must be in [0.0, 1.0], got {mrpr!r}"
        )

    # max_model_requests_per_run must be exactly 1
    mmrr = genome.get("max_model_requests_per_run")
    if mmrr != 1:
        violations.append(
            f"genome.json: max_model_requests_per_run must be 1, got {mmrr!r}"
        )

    # Safety booleans must be False
    for field in ("send_repository_full_text", "send_raw_payloads", "send_secrets"):
        val = genome.get(field)
        if val is not False:
            violations.append(
                f"genome.json: {field} must be false, got {val!r}"
            )

    return violations


def _check_evolution_history(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"evolution_history.json: malformed JSON: {exc}"]
    except OSError as exc:
        return [f"evolution_history.json: read error: {exc}"]

    if not isinstance(history, list):
        return [f"evolution_history.json: top-level must be list, got {type(history).__name__!r}"]

    for i, entry in enumerate(history):
        if not isinstance(entry, dict):
            violations.append(
                f"evolution_history.json[{i}]: must be dict, got {type(entry).__name__!r}"
            )
            continue

        gen = entry.get("generation")
        if not isinstance(gen, int) or isinstance(gen, bool):
            violations.append(
                f"evolution_history.json[{i}]: 'generation' must be int, got {gen!r}"
            )

        dh = entry.get("detector_hash")
        if dh is not None:
            if not isinstance(dh, str) or not dh or not _HEX_RE.match(dh):
                violations.append(
                    f"evolution_history.json[{i}]: 'detector_hash' must be "
                    f"non-empty hex string when present, got {dh!r}"
                )

        pag = entry.get("passed_adoption_gate")
        if pag is not None and type(pag) is not bool:
            violations.append(
                f"evolution_history.json[{i}]: 'passed_adoption_gate' must be "
                f"bool when present, got {type(pag).__name__!r} {pag!r}"
            )

    return violations


def _check_project_state(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"project_state.json: malformed JSON: {exc}"]
    except OSError as exc:
        return [f"project_state.json: read error: {exc}"]
    if not isinstance(data, dict):
        return [f"project_state.json: top-level must be dict, got {type(data).__name__!r}"]
    return []


def _check_active_threats(path: Path) -> list[str]:
    from intelligence.threat_feeds import load_active_threats
    try:
        load_active_threats(path, strict=True)
        return []
    except ValueError as exc:
        return [f"active_threats.json: {exc}"]


def _check_corpus_file(
    path: Path,
    default_kind: str | None,
    default_blocked: bool | None,
    seen_ids: set[str],
) -> list[str]:
    from core.test_attacker import _load_corpus_file
    try:
        _load_corpus_file(path, default_kind, default_blocked, seen_ids)
        return []
    except ValueError as exc:
        return [f"{path.name}: {exc}"]


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------

def validate_all(data_dir: Path = _DATA_DIR) -> dict:
    """Run all state validation checks and return a result dict."""
    violations: list[str] = []
    checked: list[str] = []

    checks = [
        (data_dir / "genome.json",           _check_genome),
        (data_dir / "evolution_history.json", _check_evolution_history),
        (data_dir / "project_state.json",     _check_project_state),
        (data_dir / "active_threats.json",    _check_active_threats),
    ]
    for path, checker in checks:
        checked.append(str(path.name))
        violations.extend(checker(path))

    corpus_seen_ids: set[str] = set()
    for fname, kind, blocked in [
        ("benign_requests.json",  "benign",     False),
        ("attack_requests.json",  "attack",     True),
        ("regression_cases.json", None,         None),
    ]:
        p = data_dir / fname
        checked.append(fname)
        violations.extend(_check_corpus_file(p, kind, blocked, corpus_seen_ids))

    return {
        "success": len(violations) == 0,
        "checked_files": checked,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cyber-Immunizer state / corpus schema validator"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    result = validate_all()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"PASS: {len(result['checked_files'])} files validated successfully")
        else:
            print(f"FAIL: {len(result['violations'])} violation(s) found")
            for v in result["violations"]:
                print(f"  - {v}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
