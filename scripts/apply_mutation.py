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
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_mutation import validate  # noqa: E402
from core.policy import MAX_POLICY_SOURCE_CHARS  # noqa: E402

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="

_REQUIRED_PATCH_FIELDS = (
    "mutation_rationale",
    "target_threats",
    "expected_improvement",
    "risk",
    "replacement_code",
)

# Safe output root: candidate files may only be written under this directory.
_DEFAULT_OUTPUT_ROOT = _PROJECT_ROOT / ".cyber_immunizer"


def _resolve_safe_output_path(
    out_path: Path,
    output_root: Path | None = None,
) -> tuple[Path | None, str]:
    """Validate that out_path resolves to a safe location under output_root.

    Returns (resolved_path, error_message).  On error, resolved_path is None
    and the candidate file must NOT be created.

    Security invariants enforced:
    - output_root itself must not be a symlink (prevents root-redirect attacks).
    - output_root must be a real directory (created only if absent).
    - out_path must resolve inside output_root after symlink expansion.
    - Only .py files are permitted; directory targets are rejected.

    Residual constraint: parent directories of output_root are not
    exhaustively checked for intermediate symlinks.  Callers should ensure
    that the parent tree of output_root is trustworthy (the default
    _DEFAULT_OUTPUT_ROOT parent is _PROJECT_ROOT, which is controlled by the
    repo checkout).
    """
    if output_root is None:
        output_root = _DEFAULT_OUTPUT_ROOT

    # --- Validate output_root itself before mkdir ---
    # If output_root already exists (or is a dangling/live symlink), inspect it.
    if output_root.exists() or output_root.is_symlink():
        if output_root.is_symlink():
            return None, (
                "unsafe output root: output root must not be a symlink"
            )
        if not output_root.is_dir():
            return None, (
                "unsafe output root: output root exists but is not a directory"
            )
    else:
        # output_root does not exist — create it as a real directory.
        output_root.mkdir(parents=True, exist_ok=True)
        # Post-mkdir safety check: confirm it is a real directory (not a symlink
        # that appeared between the existence check and the mkdir call).
        if output_root.is_symlink() or not output_root.is_dir():
            return None, (
                "unsafe output root: output root became a symlink or non-directory after creation"
            )

    # Interpret relative out_path relative to project root.
    if not out_path.is_absolute():
        out_path = _PROJECT_ROOT / out_path

    # Resolve symlinks / ".." components in both paths before comparing.
    resolved_output = out_path.resolve()
    resolved_root = output_root.resolve()

    # Only .py files are permitted as candidate output.
    if resolved_output.suffix != ".py":
        return None, (
            "unsafe output path: only .py files are allowed as candidate output "
            f"(got suffix {resolved_output.suffix!r})"
        )

    # Directories must not be used as the output target.
    if resolved_output.is_dir():
        return None, "unsafe output path: output path resolves to a directory"

    # Containment check: resolved output must be strictly inside output_root.
    # Path.is_relative_to() is available from Python 3.9; use try/except for
    # broader compatibility.
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError:
        return None, (
            "unsafe output path: resolved path is outside allowed output root "
            f"(allowed root: {resolved_root})"
        )

    return resolved_output, ""


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
    # Require exactly one occurrence of each marker — prevents double-apply attacks
    start_count = base_source.count(_MUTATION_START)
    end_count = base_source.count(_MUTATION_END)
    if start_count == 0:
        return None, f"base file missing {_MUTATION_START!r}"
    if start_count > 1:
        return None, (
            f"base file has {start_count} occurrences of {_MUTATION_START!r}; "
            "expected exactly 1 — possible double-apply detected"
        )
    if end_count == 0:
        return None, f"base file missing {_MUTATION_END!r}"
    if end_count > 1:
        return None, (
            f"base file has {end_count} occurrences of {_MUTATION_END!r}; "
            "expected exactly 1 — possible double-apply detected"
        )

    start_idx = base_source.find(_MUTATION_START)
    end_idx = base_source.find(_MUTATION_END)

    if end_idx <= start_idx:
        return None, "MUTATION_END appears before MUTATION_START in base file"

    # Preserve everything up to and including MUTATION_START line
    before = base_source[: start_idx + len(_MUTATION_START)]
    # Preserve everything from MUTATION_END onwards
    after = base_source[end_idx:]

    # Reject before constructing the full string if projected size exceeds limit
    replacement_stripped = replacement_code.rstrip("\n")
    projected_len = len(before) + 1 + len(replacement_stripped) + 1 + len(after)
    if projected_len > MAX_POLICY_SOURCE_CHARS:
        return None, (
            f"candidate source too large: projected {projected_len} chars "
            f"(limit MAX_POLICY_SOURCE_CHARS={MAX_POLICY_SOURCE_CHARS})"
        )

    # Build new source: before + newline + replacement + newline + after
    new_source = before + "\n" + replacement_stripped + "\n" + after

    return new_source, ""


def _write_text_atomic(path: Path, content: str) -> tuple[Path | None, str]:
    """Write content to a same-directory temp file; flush and fsync before returning.

    Returns (temp_path, error).  On any OSError the temp file is cleaned up
    and (None, error_message) is returned.  The caller must atomically replace
    the final target with os.replace() after validation succeeds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp.py",
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        return None, f"failed to write temp candidate: {exc}"
    return tmp_path, ""


def apply_mutation(
    patch_path: Path,
    base_path: Path,
    out_path: Path,
    *,
    output_root: Path | None = None,
) -> dict:
    """Apply mutation patch and validate the resulting candidate.

    Returns a result dict with keys: success, candidate_path, violations, error.

    The output_root parameter (default: _DEFAULT_OUTPUT_ROOT) constrains where
    candidate files may be written.  Paths that resolve outside this root are
    rejected fail-closed before any file is created.
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

    # --- Apply replacement (includes source-size projection guard) ---
    new_source, err = _apply_replacement(base_source, patch["replacement_code"])
    if err:
        return {"success": False, "candidate_path": None, "violations": [], "error": err}

    # --- Validate output path (fail-closed before any write) ---
    resolved_out, path_err = _resolve_safe_output_path(out_path, output_root)
    if path_err:
        return {"success": False, "candidate_path": None, "violations": [], "error": path_err}

    # --- Write candidate to a same-directory temp file ---
    tmp_path, write_err = _write_text_atomic(resolved_out, new_source)
    if write_err:
        return {
            "success": False,
            "candidate_path": None,
            "violations": [],
            "error": write_err,
        }

    # --- Validate the temp candidate before replacing the final target ---
    # Wrap in try/except so any unexpected parser exception (MemoryError,
    # RecursionError, etc.) is handled fail-closed here as well.
    # KeyboardInterrupt / SystemExit are not caught and propagate normally.
    try:
        val_result = validate(tmp_path)
    except Exception as exc:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        return {
            "success": False,
            "candidate_path": None,
            "violations": [f"parser failed (fail-closed): {type(exc).__name__}"],
            "error": "validation raised an unexpected exception; candidate removed",
        }
    if not val_result["valid"]:
        tmp_path.unlink(missing_ok=True)
        return {
            "success": False,
            "candidate_path": None,
            "violations": val_result["violations"],
            "error": "candidate failed AST validation",
        }

    # --- Atomically replace final path only after successful validation ---
    try:
        os.replace(tmp_path, resolved_out)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        return {
            "success": False,
            "candidate_path": None,
            "violations": [],
            "error": f"atomic replace of candidate failed: {exc}",
        }

    return {
        "success": True,
        "candidate_path": str(resolved_out),
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
        # output_root defaults to _DEFAULT_OUTPUT_ROOT (.cyber_immunizer/)
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
