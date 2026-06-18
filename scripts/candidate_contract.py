"""scripts/candidate_contract.py — Offline contract checks for candidate detectors.

Deterministic, offline, network-free checks that fail closed when a candidate:
  - drops baseline symbolic detection coverage
  - fails to inspect the full request surface
  - alters code outside the allowed mutation region
  - produces inconsistent candidate/report hashes

Static checks (1–4) are offline, network-free, no subprocess.
The behavioral surface check (run_behavioral_surface_check_subprocess) uses an
isolated subprocess with stripped environment and POSIX resource limits.
No Gemini, no external API, no network.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASELINE_SYMBOLIC_INDICATORS: tuple[str, ...] = (
    "path_traversal_indicator",
    "script_injection_indicator",
    "sqli_indicator",
    "command_delimiter_indicator",
    "encoded_traversal_indicator",
)

REQUEST_SURFACE_FIELDS: tuple[str, ...] = (
    "method",
    "path",
    "query_keys",
    "query_values",
    "header_keys",
    "header_values",
    "body",
)

_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="

_PROJECT_ROOT = Path(__file__).parent.parent
_BASE_DETECTOR_PATH = _PROJECT_ROOT / "core" / "detector.py"


# ---------------------------------------------------------------------------
# ContractCheckResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContractCheckResult:
    """Result of a single offline contract check."""

    name: str
    passed: bool
    details: dict
    rejection_reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# 1. Baseline symbolic signal preservation (static)
# ---------------------------------------------------------------------------

def check_baseline_symbolic_indicators(candidate_source: str) -> ContractCheckResult:
    """All five baseline symbolic indicators must appear in candidate source text."""
    lowered = candidate_source.lower()
    missing = [ind for ind in BASELINE_SYMBOLIC_INDICATORS if ind not in lowered]
    present = [ind for ind in BASELINE_SYMBOLIC_INDICATORS if ind in lowered]
    return ContractCheckResult(
        name="baseline_symbolic_indicators",
        passed=len(missing) == 0,
        details={"present": present, "missing": missing},
        rejection_reasons=tuple(
            f"missing_baseline_symbolic_indicator:{ind}" for ind in missing
        ),
    )


# ---------------------------------------------------------------------------
# 2. Request surface coverage — static AST
# ---------------------------------------------------------------------------

def check_request_surface_coverage(candidate_source: str) -> ContractCheckResult:
    """Static AST check: candidate must reference all request surface attributes.

    Detects missing access to request.method, request.path, request.query
    (keys and values), request.headers (keys and values), and request.body.

    For query and headers, bare attribute access, .get(), str(), indexing, and
    f-string interpolation do NOT satisfy coverage. Coverage requires:
      - .items()  — satisfies both keys and values
      - .keys()   — satisfies keys only
      - .values() — satisfies values only
    Both .keys() and .values() together satisfy full coverage.
    """
    try:
        tree = ast.parse(candidate_source)
    except SyntaxError:
        return ContractCheckResult(
            name="request_surface_coverage",
            passed=False,
            details={"error": "syntax error preventing AST parse"},
            rejection_reasons=tuple(
                f"missing_request_surface:{f}" for f in REQUEST_SURFACE_FIELDS
            ),
        )

    # Direct: request.X  → collected in `accessed` (used for method, path, body)
    # Chained: request.X.items() / .keys() / .values() → collected in `method_calls`
    # method_calls keys: "{attr}" for .items(), "{attr}_keys_only" for .keys(),
    #                    "{attr}_values_only" for .values()
    # For query and headers, only method_calls entries count — not bare accessed.
    accessed: set[str] = set()
    method_calls: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        # Direct attribute: request.X
        if isinstance(node.value, ast.Name) and node.value.id == "request":
            accessed.add(node.attr)
        # Chained: request.X.method_name  (where method_name in items/keys/values)
        if (
            node.attr in ("items", "keys", "values")
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "request"
        ):
            parent_attr = node.value.attr
            if node.attr == "items":
                method_calls.add(parent_attr)
            elif node.attr == "keys":
                method_calls.add(f"{parent_attr}_keys_only")
            elif node.attr == "values":
                method_calls.add(f"{parent_attr}_values_only")

    missing: list[str] = []

    if "method" not in accessed:
        missing.append("method")
    if "path" not in accessed:
        missing.append("path")

    # query: bare access / .get() / str() / indexing do NOT count.
    # Keys require .items() or .keys(); values require .items() or .values().
    q_items = "query" in method_calls
    q_keys = "query_keys_only" in method_calls
    q_values = "query_values_only" in method_calls
    if not (q_items or q_keys):
        missing.append("query_keys")
    if not (q_items or q_values):
        missing.append("query_values")

    # headers: same rule
    h_items = "headers" in method_calls
    h_keys = "headers_keys_only" in method_calls
    h_values = "headers_values_only" in method_calls
    if not (h_items or h_keys):
        missing.append("header_keys")
    if not (h_items or h_values):
        missing.append("header_values")

    if "body" not in accessed:
        missing.append("body")

    return ContractCheckResult(
        name="request_surface_coverage",
        passed=len(missing) == 0,
        details={
            "accessed_request_attrs": sorted(accessed),
            "missing_surface_fields": missing,
        },
        rejection_reasons=tuple(f"missing_request_surface:{f}" for f in missing),
    )


# ---------------------------------------------------------------------------
# 2b. Request surface coverage — behavioral (callable interface)
# ---------------------------------------------------------------------------

def check_request_surface_coverage_behavioral(inspect_fn) -> ContractCheckResult:
    """Behavioral check: run synthetic requests against each surface field.

    Takes an already-loaded, AST-validated inspect_request callable.
    Uses only neutralized symbolic indicators — no real exploit payloads.
    Suitable for test use; callers are responsible for AST validation before import.
    """
    from core.types import Request  # local import: avoids circular at module load

    indicator = BASELINE_SYMBOLIC_INDICATORS[0]  # path_traversal_indicator

    test_cases: dict[str, Request] = {
        "method": Request(method=indicator, path="/safe", query={}, headers={}, body=""),
        "path": Request(method="GET", path=f"/{indicator}", query={}, headers={}, body=""),
        "query_keys": Request(
            method="GET", path="/safe", query={indicator: "safe"}, headers={}, body=""
        ),
        "query_values": Request(
            method="GET", path="/safe", query={"safe": indicator}, headers={}, body=""
        ),
        "header_keys": Request(
            method="GET", path="/safe", query={}, headers={indicator: "safe"}, body=""
        ),
        "header_values": Request(
            method="GET", path="/safe", query={}, headers={"safe": indicator}, body=""
        ),
        "body": Request(method="GET", path="/safe", query={}, headers={}, body=indicator),
    }

    missing: list[str] = []
    field_results: dict[str, bool] = {}

    for field, request in test_cases.items():
        try:
            result = inspect_fn(request)
            detected = bool(getattr(result, "blocked", False))
        except Exception:
            detected = False
        field_results[field] = detected
        if not detected:
            missing.append(field)

    return ContractCheckResult(
        name="request_surface_coverage_behavioral",
        passed=len(missing) == 0,
        details={"field_results": field_results, "missing_surface_fields": missing},
        rejection_reasons=tuple(f"missing_request_surface:{f}" for f in missing),
    )


# ---------------------------------------------------------------------------
# 3. Mutation-region integrity (static)
# ---------------------------------------------------------------------------

def check_mutation_region_integrity(
    candidate_source: str,
    base_source: str | None = None,
) -> ContractCheckResult:
    """Verify mutation markers exist exactly once and outside-region code is unchanged.

    When base_source is provided, compares the pre-marker and post-marker regions
    to detect changes outside the mutation region.
    """
    start_count = candidate_source.count(_MUTATION_START)
    end_count = candidate_source.count(_MUTATION_END)

    if start_count == 0 or end_count == 0:
        return ContractCheckResult(
            name="mutation_region_integrity",
            passed=False,
            details={"start_count": start_count, "end_count": end_count},
            rejection_reasons=("mutation_region_missing",),
        )

    if start_count > 1 or end_count > 1:
        return ContractCheckResult(
            name="mutation_region_integrity",
            passed=False,
            details={"start_count": start_count, "end_count": end_count},
            rejection_reasons=("mutation_region_ambiguous",),
        )

    start_idx = candidate_source.find(_MUTATION_START)
    end_idx = candidate_source.find(_MUTATION_END)

    if end_idx <= start_idx:
        return ContractCheckResult(
            name="mutation_region_integrity",
            passed=False,
            details={"error": "MUTATION_END appears at or before MUTATION_START"},
            rejection_reasons=("mutation_region_boundary_violation",),
        )

    rejection_reasons: list[str] = []

    if base_source is not None:
        b_start_count = base_source.count(_MUTATION_START)
        b_end_count = base_source.count(_MUTATION_END)
        if b_start_count == 1 and b_end_count == 1:
            b_start = base_source.find(_MUTATION_START)
            b_end = base_source.find(_MUTATION_END)
            cand_before = candidate_source[: start_idx + len(_MUTATION_START)]
            cand_after = candidate_source[end_idx:]
            base_before = base_source[: b_start + len(_MUTATION_START)]
            base_after = base_source[b_end:]
            if cand_before != base_before or cand_after != base_after:
                rejection_reasons.append("outside_mutation_region_changed")

    if rejection_reasons:
        return ContractCheckResult(
            name="mutation_region_integrity",
            passed=False,
            details={"rejection_reasons": rejection_reasons},
            rejection_reasons=tuple(rejection_reasons),
        )

    return ContractCheckResult(
        name="mutation_region_integrity",
        passed=True,
        details={"start_count": 1, "end_count": 1},
        rejection_reasons=(),
    )


# ---------------------------------------------------------------------------
# 4. Candidate / report hash consistency
# ---------------------------------------------------------------------------

def check_candidate_hash_consistency(
    candidate_path: Path,
    reported_hash: str | None,
) -> ContractCheckResult:
    """Verify the SHA-256 of the candidate file matches reported_hash.

    When reported_hash is None no comparison is performed; the check passes
    with the actual hash recorded in details for downstream use.
    """
    if not candidate_path.exists():
        return ContractCheckResult(
            name="candidate_hash_consistency",
            passed=False,
            details={"error": f"candidate file not found: {candidate_path}"},
            rejection_reasons=("candidate_hash_mismatch",),
        )

    try:
        actual_hash = hashlib.sha256(
            candidate_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
    except OSError as exc:
        return ContractCheckResult(
            name="candidate_hash_consistency",
            passed=False,
            details={"error": f"could not read file: {exc}"},
            rejection_reasons=("candidate_hash_mismatch",),
        )

    if reported_hash is None:
        return ContractCheckResult(
            name="candidate_hash_consistency",
            passed=True,
            details={"actual_hash": actual_hash, "reported_hash": None},
            rejection_reasons=(),
        )

    if actual_hash != reported_hash:
        return ContractCheckResult(
            name="candidate_hash_consistency",
            passed=False,
            details={"actual_hash": actual_hash, "reported_hash": reported_hash},
            rejection_reasons=("candidate_hash_mismatch",),
        )

    return ContractCheckResult(
        name="candidate_hash_consistency",
        passed=True,
        details={"actual_hash": actual_hash, "reported_hash": reported_hash},
        rejection_reasons=(),
    )


# ---------------------------------------------------------------------------
# 5. Combined offline check runner
# ---------------------------------------------------------------------------

def run_candidate_contract_checks(
    candidate_path: Path,
    reported_hash: str | None = None,
    base_source: str | None = None,
) -> dict:
    """Run all static offline contract checks on a candidate file.

    Returns:
        passed: bool                    — True only if every check passed
        rejection_reasons: list[str]    — all rejection reasons collected
        contract_checks: list[dict]     — per-check results
        candidate_hash: str | None      — SHA-256 of the candidate file
    """
    if not candidate_path.exists():
        return {
            "passed": False,
            "rejection_reasons": [f"candidate not found: {candidate_path}"],
            "contract_checks": [],
            "candidate_hash": None,
        }

    try:
        source = candidate_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "passed": False,
            "rejection_reasons": [f"could not read candidate: {exc}"],
            "contract_checks": [],
            "candidate_hash": None,
        }

    actual_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    # base_source must be explicitly provided to enable outside-region comparison.
    # Auto-loading is intentionally avoided: callers who want boundary checks must
    # pass the base explicitly (evaluate_candidate.py does this).

    checks = [
        check_baseline_symbolic_indicators(source),
        check_request_surface_coverage(source),
        check_mutation_region_integrity(source, base_source),
        check_candidate_hash_consistency(candidate_path, reported_hash),
    ]

    all_reasons: list[str] = []
    for c in checks:
        all_reasons.extend(c.rejection_reasons)

    return {
        "passed": all(c.passed for c in checks),
        "rejection_reasons": all_reasons,
        "contract_checks": [
            {
                "name": c.name,
                "passed": c.passed,
                "details": c.details,
                "rejection_reasons": list(c.rejection_reasons),
            }
            for c in checks
        ],
        "candidate_hash": actual_hash,
    }


# ---------------------------------------------------------------------------
# 6. Behavioral request-surface coverage check — isolated subprocess
# ---------------------------------------------------------------------------

_BEHAVIORAL_CHECK_SCRIPT = """\
import sys
import json
import importlib.util

_SURFACE_FIELDS = (
    "method", "path", "query_keys", "query_values",
    "header_keys", "header_values", "body",
)
_INDICATOR = "path_traversal_indicator"


def _run(project_root, candidate_path_str):
    sys.path.insert(0, project_root)
    from core.types import Request  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("_cand_behavioral_check", candidate_path_str)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {candidate_path_str!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    inspect_fn = getattr(module, "inspect_request", None)
    if inspect_fn is None:
        raise AttributeError("candidate missing inspect_request function")

    test_cases = {
        "method": Request(method=_INDICATOR, path="/safe", query={}, headers={}, body=""),
        "path": Request(method="GET", path=f"/{_INDICATOR}", query={}, headers={}, body=""),
        "query_keys": Request(
            method="GET", path="/safe", query={_INDICATOR: "safe"}, headers={}, body=""
        ),
        "query_values": Request(
            method="GET", path="/safe", query={"safe": _INDICATOR}, headers={}, body=""
        ),
        "header_keys": Request(
            method="GET", path="/safe", query={}, headers={_INDICATOR: "safe"}, body=""
        ),
        "header_values": Request(
            method="GET", path="/safe", query={}, headers={"safe": _INDICATOR}, body=""
        ),
        "body": Request(method="GET", path="/safe", query={}, headers={}, body=_INDICATOR),
    }

    field_results = {}
    for field, req in test_cases.items():
        try:
            result = inspect_fn(req)
            field_results[field] = bool(getattr(result, "blocked", False))
        except Exception:
            field_results[field] = False

    missing = [f for f in _SURFACE_FIELDS if not field_results.get(f, False)]
    return field_results, missing


try:
    _project_root = sys.argv[1]
    _candidate_path = sys.argv[2]
    _field_results, _missing = _run(_project_root, _candidate_path)
    print(json.dumps({
        "success": True,
        "field_results": _field_results,
        "missing": _missing,
    }))
except Exception as _exc:
    _all_false = {
        f: False for f in (
            "method", "path", "query_keys", "query_values",
            "header_keys", "header_values", "body",
        )
    }
    print(json.dumps({
        "success": False,
        "error": str(_exc),
        "field_results": _all_false,
        "missing": list(_all_false),
    }))
"""


def run_behavioral_surface_check_subprocess(
    candidate_path: Path,
    timeout_seconds: float = 30.0,
    project_root: Path | None = None,
) -> dict:
    """Run behavioral request-surface coverage check in an isolated subprocess.

    The candidate is loaded and executed against synthetic Request objects in a
    subprocess with stripped environment (no API keys, no secrets) and conservative
    POSIX resource limits. No candidate code runs in the parent process.

    Returns a dict:
        passed: bool
        field_results: dict[str, bool]
        missing: list[str]
        rejection_reasons: list[str]
        harness_error: bool  — True if subprocess itself failed (is_tool_failure=True)
        error: str | None
    """
    _root = str(project_root or _PROJECT_ROOT)
    _all_fields = list(REQUEST_SURFACE_FIELDS)
    _all_missing = {
        "passed": False,
        "field_results": {f: False for f in _all_fields},
        "missing": _all_fields,
        "rejection_reasons": [f"missing_request_surface:{f}" for f in _all_fields],
    }

    # Stripped environment — no API keys, no secrets, no write tokens
    allowed_keys = {
        "PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE",
        "TMPDIR", "TMP", "TEMP",
    }
    safe_env = {k: v for k, v in os.environ.items() if k in allowed_keys}

    # Conservative POSIX resource limits applied in child process only
    def _preexec() -> None:
        try:
            import resource as _r  # noqa: PLC0415
            _r.setrlimit(_r.RLIMIT_CPU, (10, 10))
            _r.setrlimit(_r.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except Exception:
            pass

    preexec_fn = _preexec if os.name == "posix" else None

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _BEHAVIORAL_CHECK_SCRIPT, _root, str(candidate_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=safe_env,
            preexec_fn=preexec_fn,
        )
    except subprocess.TimeoutExpired:
        return {
            **_all_missing,
            "harness_error": True,
            "error": "behavioral surface check subprocess timed out",
        }
    except Exception as exc:
        return {
            **_all_missing,
            "harness_error": True,
            "error": f"behavioral surface check failed to launch: {exc}",
        }

    if proc.returncode != 0:
        excerpt = (proc.stderr or proc.stdout)[:300]
        return {
            **_all_missing,
            "harness_error": True,
            "error": f"behavioral check subprocess exited {proc.returncode}: {excerpt}",
        }

    try:
        data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {
            **_all_missing,
            "harness_error": True,
            "error": f"behavioral check returned non-JSON output: {proc.stdout[:200]}",
        }

    if not data.get("success", False):
        # Candidate failed to load or raised during detection — soft reject
        return {
            "passed": False,
            "field_results": data.get("field_results", {f: False for f in _all_fields}),
            "missing": _all_fields,
            "rejection_reasons": [f"missing_request_surface:{f}" for f in _all_fields],
            "harness_error": False,
            "error": data.get("error", "candidate failed during behavioral surface check"),
        }

    field_results = data.get("field_results", {})
    missing = data.get("missing", [])

    return {
        "passed": len(missing) == 0,
        "field_results": field_results,
        "missing": missing,
        "rejection_reasons": [f"missing_request_surface:{f}" for f in missing],
        "harness_error": False,
        "error": None,
    }
