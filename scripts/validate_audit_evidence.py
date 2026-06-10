"""scripts/validate_audit_evidence.py — Mechanical verification of PR-audit evidence.

Verifies the "Audit Evidence Ledger" blocks that `docs/audit_gate/PR_AUDIT_PROTOCOL.md`
requires every PR-audit report to carry. The ledger exists to prove the auditor read
beyond the diff; this script proves the ledger itself is real (quotes match the
repository, counts match reality) so that a diff-only or fabricated audit fails closed.

Usage:
    python scripts/validate_audit_evidence.py --report <audit_report.md> [--base-ref origin/main] [--json]

Exit codes:
    0  Evidence verified
    1  Verification failed (see output for reasons)

Evidence block grammar (fenced markdown block with info string `audit-evidence`):

    ```audit-evidence
    TYPE: SPEC_RECITATION
    FILE: core/detector.py
    LINES: 40-44
    SYMBOL: detect
    SPEC: detect() normalizes the payload and runs each signature regex against it.
    ---
    <verbatim lines 40-44 of core/detector.py>
    ```

Supported TYPE values and their required fields:

    SPEC_RECITATION  FILE, LINES, SPEC (SYMBOL required for .py files);
                     body = verbatim file lines; with --base-ref the quoted
                     range must lie OUTSIDE the diff hunks of that file.
    CALLSITE         SYMBOL, COUNT (optional SCOPE: comma-separated path prefixes);
                     body = `path:lineno:content` lines; COUNT must equal both the
                     number of body lines and the validator's own recount.
    NEGATIVE         PATTERN, COUNT, NOTE (optional SCOPE); body empty; the
                     validator recounts PATTERN occurrences and compares.
    READ_MANIFEST    body lines: `FULL: <path>` or `DIFF_ONLY: <path> reason: <text>`.

Searches are literal substring matches over tracked files (no regex), so results
are deterministic and reproducible by the receiving side.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_FENCE_OPEN = "```audit-evidence"
_FENCE_CLOSE = "```"
_HEADER_SEPARATOR = "---"

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "SPEC_RECITATION": ("FILE", "LINES", "SPEC"),
    "CALLSITE": ("SYMBOL", "COUNT"),
    "NEGATIVE": ("PATTERN", "COUNT", "NOTE"),
    "READ_MANIFEST": (),
}

# Minimum number of NEGATIVE blocks a ledger must carry.
_MIN_NEGATIVE_BLOCKS = 2

# Skip files larger than this when recounting (binary blobs, large data dumps).
_MAX_SEARCH_FILE_BYTES = 1_000_000

# A SPEC / NOTE shorter than this is treated as an assertion, not an explanation.
_MIN_EXPLANATION_CHARS = 10


@dataclass
class EvidenceBlock:
    """One parsed ```audit-evidence``` block."""

    type: str
    fields: dict[str, str]
    body: list[str]
    report_line: int  # 1-based line of the opening fence, for error messages


@dataclass
class FileDiff:
    """Changed-line information for one file in the base..head diff."""

    status: str  # "A" (added), "M" (modified), "D" (deleted), ...
    new_ranges: list[tuple[int, int]] = field(default_factory=list)  # inclusive, head side


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_report(text: str) -> tuple[list[EvidenceBlock], list[str]]:
    """Extract all audit-evidence blocks from a markdown report.

    Returns (blocks, parse_errors).
    """
    blocks: list[EvidenceBlock] = []
    errors: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() != _FENCE_OPEN:
            i += 1
            continue
        open_line = i + 1  # 1-based
        i += 1
        raw: list[str] = []
        closed = False
        while i < len(lines):
            if lines[i].strip() == _FENCE_CLOSE:
                closed = True
                i += 1
                break
            raw.append(lines[i])
            i += 1
        if not closed:
            errors.append(f"report line {open_line}: audit-evidence block is not closed")
            break

        if _HEADER_SEPARATOR not in [ln.strip() for ln in raw]:
            errors.append(
                f"report line {open_line}: audit-evidence block has no '---' separator "
                "between header and body"
            )
            continue
        sep_idx = next(idx for idx, ln in enumerate(raw) if ln.strip() == _HEADER_SEPARATOR)
        header_lines = raw[:sep_idx]
        body = raw[sep_idx + 1:]

        fields_: dict[str, str] = {}
        header_ok = True
        for ln in header_lines:
            if not ln.strip():
                continue
            m = re.match(r"^([A-Z_]+):\s*(.*)$", ln.strip())
            if not m:
                errors.append(
                    f"report line {open_line}: malformed header line {ln.strip()!r} "
                    "(expected 'KEY: value')"
                )
                header_ok = False
                break
            fields_[m.group(1)] = m.group(2).strip()
        if not header_ok:
            continue

        block_type = fields_.pop("TYPE", "")
        if block_type not in _REQUIRED_FIELDS:
            errors.append(
                f"report line {open_line}: unknown or missing TYPE {block_type!r} "
                f"(expected one of {sorted(_REQUIRED_FIELDS)})"
            )
            continue
        missing = [k for k in _REQUIRED_FIELDS[block_type] if not fields_.get(k)]
        if missing:
            errors.append(
                f"report line {open_line}: {block_type} block is missing required "
                f"field(s): {', '.join(missing)}"
            )
            continue
        blocks.append(EvidenceBlock(block_type, fields_, body, open_line))
    return blocks, errors


def parse_line_range(spec: str) -> tuple[int, int] | None:
    """Parse '40' or '40-44' into an inclusive 1-based (start, end), or None."""
    m = re.match(r"^(\d+)(?:-(\d+))?$", spec.strip())
    if not m:
        return None
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    if start < 1 or end < start:
        return None
    return (start, end)


def parse_name_status(text: str) -> dict[str, str]:
    """Parse `git diff --name-status` output into {path: status}."""
    result: dict[str, str] = {}
    for ln in text.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()
        # Renames/copies (R100\told\tnew) — record the new path.
        path = parts[-1].strip()
        if status and path:
            result[path] = status[0]
    return result


def parse_unified_diff_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Parse `git diff -U0` output into {new_path: [(start, end), ...]} head-side ranges.

    A pure-deletion hunk (+c,0) is recorded as the zero-length position (c, c)
    so quotes immediately at the deletion point still count as diff-adjacent.
    """
    ranges: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    for ln in diff_text.splitlines():
        if ln.startswith("+++ "):
            target = ln[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith("b/") else target
            continue
        if current is None or not ln.startswith("@@"):
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", ln)
        if not m:
            continue
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        end = start + count - 1 if count > 0 else start
        ranges.setdefault(current, []).append((max(start, 1), max(end, 1)))
    return ranges


# ---------------------------------------------------------------------------
# Repository search (literal substring, deterministic)
# ---------------------------------------------------------------------------


def list_searchable_files(root: Path) -> list[Path]:
    """Tracked files via `git ls-files`, falling back to a filesystem walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [root / p for p in out.splitlines() if p.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts
        ]


def count_occurrences(
    root: Path,
    needle: str,
    scope_prefixes: list[str] | None = None,
    exclude: set[Path] | None = None,
    files: list[Path] | None = None,
) -> tuple[int, dict[str, list[int]]]:
    """Count lines containing `needle` (literal substring) across repository files.

    Returns (total_line_count, {relative_path: [line_numbers]}).
    """
    matches: dict[str, list[int]] = {}
    total = 0
    for path in files if files is not None else list_searchable_files(root):
        if exclude and path.resolve() in exclude:
            continue
        rel = path.relative_to(root).as_posix()
        if scope_prefixes and not any(rel.startswith(pfx) for pfx in scope_prefixes):
            continue
        try:
            if path.stat().st_size > _MAX_SEARCH_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hit_lines = [n for n, ln in enumerate(text.splitlines(), start=1) if needle in ln]
        if hit_lines:
            matches[rel] = hit_lines
            total += len(hit_lines)
    return total, matches


def _parse_scope(block: EvidenceBlock) -> list[str] | None:
    raw = block.fields.get("SCOPE", "").strip()
    if not raw:
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


# ---------------------------------------------------------------------------
# Per-block verification
# ---------------------------------------------------------------------------


def verify_spec_recitation(
    block: EvidenceBlock,
    root: Path,
    diff_ranges: dict[str, list[tuple[int, int]]] | None = None,
) -> list[str]:
    errors: list[str] = []
    where = f"report line {block.report_line} (SPEC_RECITATION)"
    rel = block.fields["FILE"].strip()
    target = root / rel
    if not target.is_file():
        return [f"{where}: FILE {rel!r} does not exist in the repository"]

    rng = parse_line_range(block.fields["LINES"])
    if rng is None:
        return [f"{where}: LINES {block.fields['LINES']!r} is not 'N' or 'N-M'"]
    start, end = rng

    spec = block.fields["SPEC"]
    if len(spec) < _MIN_EXPLANATION_CHARS:
        errors.append(f"{where}: SPEC is too short to be an explanation: {spec!r}")

    symbol = block.fields.get("SYMBOL", "").strip()
    if rel.endswith(".py") and not symbol:
        errors.append(f"{where}: SYMBOL (function/class name) is required for .py files")

    file_lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    if end > len(file_lines):
        return errors + [
            f"{where}: LINES {start}-{end} exceeds {rel} length ({len(file_lines)} lines)"
        ]

    expected = file_lines[start - 1:end]
    quoted = block.body
    # Trailing blank lines in the fenced body are not significant.
    while quoted and not quoted[-1].strip():
        quoted = quoted[:-1]
    if len(quoted) != len(expected):
        errors.append(
            f"{where}: quoted {len(quoted)} line(s) but LINES {start}-{end} covers "
            f"{len(expected)} line(s)"
        )
    else:
        for offset, (got, want) in enumerate(zip(quoted, expected)):
            if got.rstrip() != want.rstrip():
                errors.append(
                    f"{where}: quote does not match {rel}:{start + offset} — "
                    f"quoted {got.rstrip()!r}, file has {want.rstrip()!r}"
                )
                break
    if symbol and not any(symbol in ln for ln in quoted):
        errors.append(
            f"{where}: SYMBOL {symbol!r} does not appear in the quoted lines — "
            "quote must include the function/class signature"
        )

    if diff_ranges is not None:
        for (c_start, c_end) in diff_ranges.get(rel, []):
            if start <= c_end and c_start <= end:
                errors.append(
                    f"{where}: quoted range {rel}:{start}-{end} overlaps diff hunk "
                    f"{c_start}-{c_end} — the recitation must quote code OUTSIDE the diff"
                )
                break
    return errors


def verify_callsite(
    block: EvidenceBlock,
    root: Path,
    exclude: set[Path] | None = None,
) -> list[str]:
    errors: list[str] = []
    where = f"report line {block.report_line} (CALLSITE)"
    symbol = block.fields["SYMBOL"]
    try:
        count = int(block.fields["COUNT"])
    except ValueError:
        return [f"{where}: COUNT {block.fields['COUNT']!r} is not an integer"]

    body = [ln for ln in block.body if ln.strip()]
    if len(body) != count:
        errors.append(f"{where}: COUNT is {count} but {len(body)} match line(s) are listed")

    for ln in body:
        m = re.match(r"^([^:]+):(\d+):(.*)$", ln.strip())
        if not m:
            errors.append(f"{where}: malformed match line {ln.strip()!r} (expected path:lineno:content)")
            continue
        rel, lineno, content = m.group(1), int(m.group(2)), m.group(3)
        target = root / rel
        if not target.is_file():
            errors.append(f"{where}: cited file {rel!r} does not exist")
            continue
        file_lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        if lineno < 1 or lineno > len(file_lines):
            errors.append(f"{where}: {rel}:{lineno} is out of range ({len(file_lines)} lines)")
            continue
        if file_lines[lineno - 1].strip() != content.strip():
            errors.append(
                f"{where}: content mismatch at {rel}:{lineno} — "
                f"cited {content.strip()!r}, file has {file_lines[lineno - 1].strip()!r}"
            )

    actual, matches = count_occurrences(root, symbol, _parse_scope(block), exclude)
    if actual != count:
        sample = "; ".join(
            f"{p}:{ns[:3]}" for p, ns in list(matches.items())[:5]
        )
        errors.append(
            f"{where}: COUNT is {count} but the validator found {actual} line(s) "
            f"containing {symbol!r}"
            + (f" (e.g. {sample})" if sample else "")
            + " — call-site evidence is incomplete or stale"
        )
    return errors


def verify_negative(
    block: EvidenceBlock,
    root: Path,
    exclude: set[Path] | None = None,
) -> list[str]:
    errors: list[str] = []
    where = f"report line {block.report_line} (NEGATIVE)"
    pattern = block.fields["PATTERN"]
    try:
        count = int(block.fields["COUNT"])
    except ValueError:
        return [f"{where}: COUNT {block.fields['COUNT']!r} is not an integer"]
    if len(block.fields["NOTE"]) < _MIN_EXPLANATION_CHARS:
        errors.append(f"{where}: NOTE is too short to explain what this absence proves")

    actual, matches = count_occurrences(root, pattern, _parse_scope(block), exclude)
    if actual != count:
        sample = "; ".join(f"{p}:{ns[:3]}" for p, ns in list(matches.items())[:5])
        errors.append(
            f"{where}: claimed {count} occurrence(s) of {pattern!r} but the validator "
            f"found {actual}" + (f" (e.g. {sample})" if sample else "")
        )
    return errors


def verify_read_manifest(block: EvidenceBlock, root: Path) -> list[str]:
    errors: list[str] = []
    where = f"report line {block.report_line} (READ_MANIFEST)"
    body = [ln for ln in block.body if ln.strip()]
    if not body:
        return [f"{where}: manifest body is empty"]
    for ln in body:
        stripped = ln.strip()
        if stripped.startswith("FULL:"):
            rel = stripped[len("FULL:"):].strip()
            if not (root / rel).is_file():
                errors.append(f"{where}: FULL entry {rel!r} does not exist")
        elif stripped.startswith("DIFF_ONLY:"):
            rest = stripped[len("DIFF_ONLY:"):].strip()
            if "reason:" not in rest:
                errors.append(
                    f"{where}: DIFF_ONLY entry must carry 'reason: <text>': {stripped!r}"
                )
                continue
            path_part, _, reason = rest.partition("reason:")
            rel = path_part.split()[0] if path_part.split() else ""
            if not rel or not (root / rel).is_file():
                errors.append(f"{where}: DIFF_ONLY entry {rel!r} does not exist")
            if len(reason.strip()) < _MIN_EXPLANATION_CHARS:
                errors.append(f"{where}: DIFF_ONLY reason is too short: {reason.strip()!r}")
        else:
            errors.append(
                f"{where}: manifest line must start with 'FULL:' or 'DIFF_ONLY:': {stripped!r}"
            )
    return errors


def manifest_paths(blocks: list[EvidenceBlock]) -> set[str]:
    paths: set[str] = set()
    for block in blocks:
        if block.type != "READ_MANIFEST":
            continue
        for ln in block.body:
            stripped = ln.strip()
            for prefix in ("FULL:", "DIFF_ONLY:"):
                if stripped.startswith(prefix):
                    rest = stripped[len(prefix):].strip()
                    if rest.split():
                        paths.add(rest.split()[0])
    return paths


# ---------------------------------------------------------------------------
# Diff context (--base-ref)
# ---------------------------------------------------------------------------


def load_diff_context(root: Path, base_ref: str) -> tuple[dict[str, FileDiff], list[str]]:
    """Collect changed files and head-side changed line ranges for base_ref...HEAD."""
    errors: list[str] = []
    try:
        name_status = subprocess.run(
            ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        unified = subprocess.run(
            ["git", "diff", "-U0", f"{base_ref}...HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {}, [f"--base-ref: failed to compute git diff against {base_ref!r}: {exc}"]

    statuses = parse_name_status(name_status)
    ranges = parse_unified_diff_ranges(unified)
    diffs = {
        path: FileDiff(status=status, new_ranges=ranges.get(path, []))
        for path, status in statuses.items()
    }
    if not diffs:
        errors.append(f"--base-ref: no changed files found against {base_ref!r}")
    return diffs, errors


def verify_diff_coverage(
    blocks: list[EvidenceBlock],
    diffs: dict[str, FileDiff],
) -> list[str]:
    """Every modified file needs a recitation + manifest entry; .py changes need CALLSITE."""
    errors: list[str] = []
    recited = {b.fields.get("FILE", "").strip() for b in blocks if b.type == "SPEC_RECITATION"}
    listed = manifest_paths(blocks)
    has_callsite = any(b.type == "CALLSITE" for b in blocks)

    needs_callsite = False
    for path, fd in diffs.items():
        if fd.status == "D":
            continue  # deleted files cannot be recited or read
        if path.endswith(".py"):
            needs_callsite = True
        if path not in listed:
            errors.append(f"diff coverage: changed file {path!r} is missing from READ_MANIFEST")
        if fd.status == "A":
            continue  # new files are entirely diff; recitation outside the diff is impossible
        if path not in recited:
            errors.append(
                f"diff coverage: changed file {path!r} has no SPEC_RECITATION block "
                "(pre-diff recitation is mandatory for every modified file)"
            )
    if needs_callsite and not has_callsite:
        errors.append(
            "diff coverage: .py files changed but no CALLSITE block is present"
        )
    return errors


# ---------------------------------------------------------------------------
# Top-level validation
# ---------------------------------------------------------------------------


def validate_report(
    report_path: Path,
    root: Path,
    base_ref: str | None = None,
) -> dict:
    """Validate an audit report's evidence ledger.

    Returns {"valid": bool, "errors": [str], "blocks": int}.
    """
    errors: list[str] = []
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"valid": False, "errors": [f"cannot read report: {exc}"], "blocks": 0}

    blocks, parse_errors = parse_report(text)
    errors.extend(parse_errors)

    by_type: dict[str, list[EvidenceBlock]] = {}
    for b in blocks:
        by_type.setdefault(b.type, []).append(b)

    if not by_type.get("SPEC_RECITATION"):
        errors.append("ledger: at least one SPEC_RECITATION block is required")
    if not by_type.get("READ_MANIFEST"):
        errors.append("ledger: a READ_MANIFEST block is required")
    if len(by_type.get("NEGATIVE", [])) < _MIN_NEGATIVE_BLOCKS:
        errors.append(
            f"ledger: at least {_MIN_NEGATIVE_BLOCKS} NEGATIVE blocks are required "
            f"(found {len(by_type.get('NEGATIVE', []))})"
        )

    diff_ranges: dict[str, list[tuple[int, int]]] | None = None
    diffs: dict[str, FileDiff] | None = None
    if base_ref:
        diffs, diff_errors = load_diff_context(root, base_ref)
        errors.extend(diff_errors)
        if diffs:
            diff_ranges = {p: fd.new_ranges for p, fd in diffs.items()}

    # Exclude the report itself from recounts so the ledger's own text
    # (which necessarily contains the patterns) does not skew results.
    exclude: set[Path] = set()
    try:
        report_resolved = report_path.resolve()
        report_resolved.relative_to(root.resolve())
        exclude.add(report_resolved)
    except ValueError:
        pass

    for b in blocks:
        if b.type == "SPEC_RECITATION":
            errors.extend(verify_spec_recitation(b, root, diff_ranges))
        elif b.type == "CALLSITE":
            errors.extend(verify_callsite(b, root, exclude))
        elif b.type == "NEGATIVE":
            errors.extend(verify_negative(b, root, exclude))
        elif b.type == "READ_MANIFEST":
            errors.extend(verify_read_manifest(b, root))

    if diffs:
        errors.extend(verify_diff_coverage(blocks, diffs))

    return {"valid": not errors, "errors": errors, "blocks": len(blocks)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cyber-Immunizer audit-evidence ledger validator"
    )
    parser.add_argument("--report", required=True, help="Path to the audit report markdown")
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Base git ref of the audited PR (e.g. origin/main); enables diff-coverage checks",
    )
    parser.add_argument(
        "--root",
        default=str(_PROJECT_ROOT),
        help="Repository root (default: this repository)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    result = validate_report(Path(args.report), Path(args.root), args.base_ref)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["valid"]:
            print(f"VALID: audit evidence ledger verified ({result['blocks']} block(s))")
        else:
            print(f"INVALID: {len(result['errors'])} problem(s)")
            for e in result["errors"]:
                print(f"  - {e}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
