"""scripts/evaluate_structured_rules_candidate.py — Explicit structured-rules candidate evaluation.

Usage:
    python scripts/evaluate_structured_rules_candidate.py \\
        --rules path/to/structured_rules.json \\
        [--genome path/to/genome.json] \\
        [--json] \\
        [--soft-reject] \\
        [--baseline] \\
        [--report-path PATH] \\
        [--corpus-dir DIR] \\
        [--benign-path PATH] [--attack-path PATH] [--regression-path PATH] \\
        [--holdout-path PATH] [--counterfactual-path PATH] [--drift-path PATH]

Corpus selection:
    By default the repository data/ corpus (symbolic indicators) is used.
    --corpus-dir points at a directory of Owner-supplied corpus files and the
    per-tier --*-path options override individual tier files. These let an Owner
    grade a structured-rules candidate against a realistic but safely neutralized
    corpus supplied from OUTSIDE the repository, through the same score / adoption
    gate / adaptive floor / parity guard path. Supplied corpus files are read-only.

Exit codes (default mode):
    0  Candidate passed adoption gate
    1  Tool failure (malformed JSON, unreadable file, genome load failure, test-case load
       failure, oversized rules file, duplicate keys in rules JSON, invalid genome
       thresholds, forbidden --report-path) OR adoption gate failed

Exit codes with --soft-reject:
    0  Evaluation completed (regardless of gate outcome)
    1  Tool failure only

This script intentionally reuses current core.fitness scoring/adoption helper
semantics to avoid creating a second score formula.

SAFETY:
    No network calls. No environment variables. No subprocess calls. No Gemini API.
    No workflow dispatch. No promotion. No data edits. No .cyber_immunizer/** writes.
    Evaluation is performed in-process using local test cases only.
"""
from __future__ import annotations

import argparse
import json
import math
import stat
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.detector import inspect_request as _legacy_inspect_request
from core.runtime_selector import inspect_request_with_runtime_selector
from core.structured_validator import validate_rules_schema
from core.test_attacker import evaluate_detector, load_test_cases, summarize_results

# These helpers are imported from core.fitness to reuse the exact scoring and
# adoption-gate semantics without duplicating or drifting the formula.
from core.fitness import (  # noqa: PLC2701
    _MAIN_EVAL_KINDS,
    _adaptive_floor_gate,
    _adoption_gate,
    _compute_score,
    _compute_tier_pass_rate,
)

_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"

# Reject rules files larger than 1 MiB before reading/parsing.
_MAX_RULES_FILE_BYTES = 1_048_576

# Reject genome files larger than 1 MiB before reading/parsing.
_MAX_GENOME_FILE_BYTES = 1_048_576

# Frozen project paths that --report-path must not target.
_FORBIDDEN_REPORT_PREFIXES: frozenset[str] = frozenset([
    ".cyber_immunizer",
    ".git",
    ".grok",
    "data",
    "core",
    ".github",
    "scripts",
    "docs/audit_gate",
])

_FORBIDDEN_REPORT_EXACT: frozenset[str] = frozenset([
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/PROJECT_STATE.md",
])


def _load_genome(genome_path: Path) -> dict:
    """Load genome.json strictly. Raises OSError, json.JSONDecodeError, or ValueError on failure.

    Fail-closed: callers must handle the exception as a tool failure rather than
    substituting defaults, so that a missing or malformed genome cannot silently
    lower gate thresholds (e.g. previous_best_score=-1e9) and promote a candidate.

    Also validates that the genome path is a regular file and within the size limit before
    reading, to prevent blocking on FIFOs or exhausting memory on huge files.
    Uses duplicate-key rejecting parser and validates that the top-level value is a dict.
    """
    gst = genome_path.stat()  # raises OSError if missing
    if not stat.S_ISREG(gst.st_mode):
        raise OSError(
            f"genome path is not a regular file (mode={stat.filemode(gst.st_mode)!r})"
        )
    if gst.st_size > _MAX_GENOME_FILE_BYTES:
        raise OSError(
            f"genome file exceeds size limit: {gst.st_size} bytes > {_MAX_GENOME_FILE_BYTES} bytes"
        )
    raw = genome_path.read_text(encoding="utf-8")
    data = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(data, dict):
        raise ValueError(f"genome JSON must be an object, got {type(data).__name__!r}")
    return data


def _reject_duplicate_keys(pairs: list) -> dict:
    """object_pairs_hook that raises ValueError on duplicate keys in a JSON object."""
    seen: set = set()
    result: dict = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key {k!r} in JSON object")
        seen.add(k)
        result[k] = v
    return result


def _to_finite_float(val: object) -> tuple[float | None, str | None]:
    """Convert val to a finite float. Returns (float_val, None) on success, (None, error) on failure.

    Rejects bool, non-numeric types, values that overflow float, and non-finite results.
    Huge Python integers (from JSON integer literals) raise OverflowError in float(), which
    this function catches and converts to an error string.
    """
    if isinstance(val, bool):
        return None, f"expected a number, got bool: {val!r}"
    if not isinstance(val, (int, float)):
        return None, f"expected a number, got {type(val).__name__!r}: {val!r}"
    try:
        fval = float(val)
    except OverflowError:
        return None, f"value overflows float (too large): {val!r}"
    if not math.isfinite(fval):
        return None, f"value is non-finite: {val!r}"
    return fval, None


def _validate_genome_thresholds(genome: dict) -> str | None:
    """Validate genome threshold fields. Return error string if invalid, else None.

    Rejects bool, non-number, non-finite, and overflow values.
    Rate fields must be in [0.0, 1.0]. max_avg_latency_ms must be > 0.
    """
    _rate_fields = (
        "max_fp_rate",
        "min_regression_pass_rate",
        "min_holdout_pass_rate",
        "min_counterfactual_pass_rate",
        "min_drift_pass_rate",
    )
    for field in _rate_fields:
        if field not in genome:
            continue
        fval, err = _to_finite_float(genome[field])
        if err:
            return f"genome threshold {field!r}: {err}"
        if not (0.0 <= fval <= 1.0):  # type: ignore[operator]
            return f"genome threshold {field!r} out of range [0.0, 1.0]: {genome[field]}"

    if "max_avg_latency_ms" in genome:
        fval, err = _to_finite_float(genome["max_avg_latency_ms"])
        if err:
            return f"genome threshold 'max_avg_latency_ms': {err}"
        if fval <= 0:  # type: ignore[operator]
            return f"genome threshold 'max_avg_latency_ms' must be > 0: {genome['max_avg_latency_ms']!r}"

    if "best_score" in genome:
        fval, err = _to_finite_float(genome["best_score"])
        if err:
            return f"genome threshold 'best_score': {err}"

    return None


def _is_forbidden_report_path(report_path: Path) -> bool:
    """Return True if report_path resolves inside a frozen project path."""
    try:
        resolved = report_path.resolve()
        root = _PROJECT_ROOT.resolve()
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        return False  # Outside project root or unresolvable — allowed

    rel = relative.as_posix()

    if rel in _FORBIDDEN_REPORT_EXACT:
        return True
    for prefix in _FORBIDDEN_REPORT_PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return True
    return False


# Tier name -> standard corpus filename used inside a --corpus-dir directory.
_CORPUS_TIER_FILENAMES: dict[str, str] = {
    "benign": "benign_requests.json",
    "attack": "attack_requests.json",
    "regression": "regression_cases.json",
    "holdout": "holdout_requests.json",
    "counterfactual": "counterfactual_requests.json",
    "drift": "drift_requests.json",
}


def _resolve_corpus_paths(
    corpus_dir: Path | None,
    overrides: dict[str, Path | None],
) -> dict[str, Path] | None:
    """Resolve per-tier corpus paths from an optional directory plus per-tier overrides.

    Returns None when neither a directory nor any override is supplied, so the
    caller falls back to the repository ``data/`` corpus (backward compatible).
    A per-tier override always wins over the directory-derived path. Tiers that
    are neither overridden nor present in ``corpus_dir`` are left unset so
    ``load_test_cases`` uses its ``data/`` default for them.
    """
    if corpus_dir is None and not any(overrides.values()):
        return None
    resolved: dict[str, Path] = {}
    for tier, filename in _CORPUS_TIER_FILENAMES.items():
        override = overrides.get(tier)
        if override is not None:
            resolved[tier] = override
        elif corpus_dir is not None:
            resolved[tier] = corpus_dir / filename
    return resolved


def _load_test_cases_kwargs(corpus_paths: dict[str, Path] | None) -> dict[str, Path]:
    """Translate a tier->Path mapping into load_test_cases keyword arguments."""
    if not corpus_paths:
        return {}
    return {
        f"{tier}_path": path
        for tier, path in corpus_paths.items()
        if path is not None
    }


# Owner-supplied corpus files are user-controlled CLI inputs; bound their size
# before load_test_cases reads them with Path.read_text() (no size/type guard).
_MAX_CORPUS_FILE_BYTES = 5_242_880  # 5 MiB
_ADAPTIVE_TIERS: frozenset[str] = frozenset({"holdout", "counterfactual", "drift"})


def _validate_external_corpus_files(corpus_paths: dict[str, Path] | None) -> str | None:
    """Validate Owner-supplied corpus paths before load_test_cases reads them.

    Returns an error string (tool failure) or None. Checks, for each provided path:
      - the path is a regular file (rejects FIFO/device/dir that could block reads)
      - the file is within the size bound
    For adaptive-tier files (holdout/counterfactual/drift) it additionally rejects
    records whose explicit ``kind`` does not match the tier, because the adaptive
    floor counts tier membership by ``kind`` — a mismatch can let a failing
    holdout/drift/counterfactual case be scored as a main case and inflate the
    tier pass rate to a false green.
    """
    if not corpus_paths:
        return None
    for tier, path in corpus_paths.items():
        if path is None:
            continue
        try:
            st = path.stat()
        except OSError as exc:
            return f"corpus file for tier {tier!r} could not be stat'd: {exc}"
        if not stat.S_ISREG(st.st_mode):
            return (
                f"corpus path for tier {tier!r} is not a regular file "
                f"(mode={stat.filemode(st.st_mode)!r}): {path}"
            )
        if st.st_size > _MAX_CORPUS_FILE_BYTES:
            return (
                f"corpus file for tier {tier!r} exceeds size limit: "
                f"{st.st_size} bytes > {_MAX_CORPUS_FILE_BYTES} bytes"
            )
        # Enforce kind matching for EVERY per-tier file (main and adaptive). A
        # main file carrying a mismatched explicit kind (e.g. an
        # expected_blocked=false record with kind="attack" inside
        # attack_requests.json) could otherwise satisfy the empty-main-tier guard
        # for a different tier and recreate a false-green gate result.
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            return f"corpus file for tier {tier!r} is not readable JSON: {exc}"
        if not isinstance(records, list):
            return f"corpus file for tier {tier!r} must be a JSON array"
        for i, rec in enumerate(records):
            if isinstance(rec, dict) and "kind" in rec and rec.get("kind") != tier:
                return (
                    f"corpus file for tier {tier!r} entry {i} has kind="
                    f"{rec.get('kind')!r}; per-tier files must use kind={tier!r} "
                    f"(or omit kind) so each tier is counted correctly"
                )
    return None


def _make_detector_callable(rules_doc: dict):
    """Return a detector callable that invokes the runtime selector in structured_rules mode."""
    def _detector(request):
        return inspect_request_with_runtime_selector(
            request,
            mode="structured_rules",
            structured_rules_doc=rules_doc,
        )
    return _detector


def _tool_failure(error: str, rules_path: Path) -> tuple[dict, bool]:
    return {
        "success": False,
        "evaluation_completed": False,
        "schema_valid": False,
        "passed_adoption_gate": False,
        "error": error,
        "rejection_reasons": [error],
        "mode": "structured_rules",
        "rules_path": str(rules_path),
    }, True


def evaluate_structured_rules(
    rules_path: Path,
    *,
    genome_path: Path,
    baseline_mode: bool = False,
    corpus_paths: dict[str, Path] | None = None,
) -> tuple[dict, bool]:
    """Evaluate a structured rules document and return (report, is_tool_failure).

    Tool failures (unreadable/oversized file, malformed/duplicate-key JSON, genome load
    failure, invalid genome thresholds, test-case load failure):
        success=False, evaluation_completed=False, is_tool_failure=True

    Candidate rejections (invalid schema, gate failed, parity guard):
        success=False, evaluation_completed=True, is_tool_failure=False

    Args:
        corpus_paths: Optional mapping of tier name
            (``benign`` / ``attack`` / ``regression`` / ``holdout`` /
            ``counterfactual`` / ``drift``) to an explicit corpus file Path. When
            omitted (or for tiers left out), the repository ``data/`` corpus is
            used, preserving the previous default behavior. This lets an Owner
            evaluate a structured-rules candidate against a realistic but safely
            neutralized corpus supplied from **outside** the repository, through
            the same score / adoption-gate / adaptive-floor / parity-guard path.
            Supplied corpus files are read-only inputs; this script never writes
            to them and never commits their contents.

    Returns a JSON-serializable report dict.
    """
    # Bound file size before reading to prevent memory pressure from huge inputs.
    # Also reject non-regular files (FIFOs, directories, device nodes) before any
    # read attempt, as those can block indefinitely or behave unexpectedly.
    try:
        st = rules_path.stat()
    except OSError as exc:
        return _tool_failure(f"failed to stat rules file: {exc}", rules_path)
    if not stat.S_ISREG(st.st_mode):
        return _tool_failure(
            f"rules path is not a regular file (mode={stat.filemode(st.st_mode)!r})",
            rules_path,
        )
    file_size = st.st_size
    if file_size > _MAX_RULES_FILE_BYTES:
        return _tool_failure(
            f"rules file exceeds size limit: {file_size} bytes > {_MAX_RULES_FILE_BYTES} bytes",
            rules_path,
        )

    # Read rules file. Non-UTF-8 content is a tool failure (not a candidate rejection).
    try:
        raw_text = rules_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _tool_failure(f"failed to read rules file: {exc}", rules_path)

    # Parse JSON with duplicate-key rejection. Duplicate keys are a tool failure
    # because canonical static validation rejects them; the evaluator must not accept
    # artifacts that static validation would reject.
    try:
        rules_doc = json.loads(raw_text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        return _tool_failure(f"malformed JSON in rules file: {exc}", rules_path)

    # Schema validation — failure is candidate rejection, not a tool failure.
    # Wrap in try/except so unexpected exceptions from the validator (OverflowError from
    # extreme numeric values, RecursionError from deeply nested structures, TypeError or
    # ValueError from unexpected input types) become structured tool failures rather than
    # tracebacks.
    try:
        validation = validate_rules_schema(rules_doc)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        return _tool_failure(
            f"schema validation raised an unexpected error: {exc}", rules_path
        )
    if not validation.get("success"):
        violations = validation.get("violations", [])
        rejection_reasons = [f"schema validation failed: {v}" for v in violations]
        return {
            "success": False,           # success matches passed_adoption_gate
            "evaluation_completed": True,  # evaluation ran; candidate was rejected
            "schema_valid": False,
            "passed_adoption_gate": False,
            "true_positive": 0,
            "false_positive": 0,
            "true_negative": 0,
            "false_negative": 0,
            "exception_count": 0,
            "total_cases": 0,
            "tp_rate": 0.0,
            "fp_rate": 0.0,
            "fn_rate": 0.0,
            "avg_latency_ms": 0.0,
            "score": -1e9,
            "code_chars": len(raw_text),
            "rejection_reasons": rejection_reasons,
            "adaptive_floor_passed": False,
            "holdout_pass_rate": 0.0,
            "counterfactual_pass_rate": 0.0,
            "drift_pass_rate": 0.0,
            "score_comparison_mode": "structured_rules_parity_guard",
            "mode": "structured_rules",
            "rules_path": str(rules_path),
        }, False

    # Load genome for gate thresholds — fail closed on load error.
    # A missing or malformed genome must not silently substitute defaults
    # (e.g. previous_best_score=-1e9) and thereby allow an under-performing
    # candidate to pass the adoption gate.
    try:
        genome = _load_genome(genome_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        return _tool_failure(f"failed to load genome: {exc}", rules_path)

    # Validate genome thresholds before use. Non-finite or wrong-type values
    # silently break comparisons (e.g. score <= NaN is always False).
    threshold_error = _validate_genome_thresholds(genome)
    if threshold_error:
        return _tool_failure(f"invalid genome threshold — {threshold_error}", rules_path)

    max_fp_rate: float = float(genome.get("max_fp_rate", 0.05))
    min_regression_pass_rate: float = float(genome.get("min_regression_pass_rate", 1.0))
    previous_best_score: float = float(genome.get("best_score", -1e9))
    max_avg_latency_ms: float = float(genome.get("max_avg_latency_ms", 100.0))
    min_holdout_pass_rate: float = float(genome.get("min_holdout_pass_rate", 1.0))
    min_cf_pass_rate: float = float(genome.get("min_counterfactual_pass_rate", 1.0))
    min_drift_pass_rate: float = float(genome.get("min_drift_pass_rate", 1.0))

    # Build the detector callable via runtime selector.
    detector_fn = _make_detector_callable(rules_doc)

    # Load test cases with fail-closed adaptive-tier behavior (require_adaptive_tiers=True,
    # the default). Missing adaptive tier files are treated as tool failures so the floor
    # gate cannot be silently bypassed by absent holdout/counterfactual/drift corpora.
    corpus_validation_error = _validate_external_corpus_files(corpus_paths)
    if corpus_validation_error:
        return _tool_failure(corpus_validation_error, rules_path)
    try:
        cases = load_test_cases(**_load_test_cases_kwargs(corpus_paths))
    except Exception as exc:
        return _tool_failure(f"test case load failed: {exc}", rules_path)

    # Run evaluation.
    results = evaluate_detector(detector_fn, cases)

    # Partition: main tiers (benign/attack/regression) drive the score.
    main_results = [r for r in results if r.get("kind") in _MAIN_EVAL_KINDS]
    summary = summarize_results(main_results)

    tp: int = summary["true_positive"]
    fp: int = summary["false_positive"]
    tn: int = summary["true_negative"]
    fn: int = summary["false_negative"]
    total: int = summary["total_cases"]
    exception_count: int = summary["exception_count"]
    avg_latency_ms: float = summary["avg_latency_ms"]

    attack_total = tp + fn
    benign_total = tn + fp
    tp_rate = tp / attack_total if attack_total else 0.0
    fp_rate = fp / benign_total if benign_total else 0.0
    fn_rate = fn / attack_total if attack_total else 0.0

    regression_results = [r for r in main_results if r.get("kind") == "regression"]

    # Reject incomplete external corpora: an Owner-supplied corpus with an empty
    # main tier could otherwise pass in --baseline mode with total_cases=0
    # (score/parity bypassed, regression pass rate defaults to 1.0).
    # Count tier presence by KIND (not by outcome): a record with
    # expected_blocked=false but kind="attack" must not stand in for an empty
    # benign tier, which would recreate the false-green this guard closes.
    if corpus_paths is not None:
        _main_kinds = [r.get("kind") for r in main_results]
        if (
            _main_kinds.count("attack") == 0
            or _main_kinds.count("benign") == 0
            or _main_kinds.count("regression") == 0
        ):
            return _tool_failure(
                "external corpus has an empty main tier (attack/benign/regression); "
                "refusing to report a gate result on an incomplete corpus",
                rules_path,
            )

    reg_pass = sum(
        1
        for r in regression_results
        if r["actual_blocked"] == r["expected_blocked"] and not r["exception"]
    )
    regression_pass_rate = reg_pass / len(regression_results) if regression_results else 1.0

    # Score using the same formula as core.fitness.
    # code_chars = len(raw_text): use the JSON doc character count so that
    # structured-rules scores are directly comparable to Python-detector scores
    # and not artificially inflated by a zero code-size penalty.
    code_chars = len(raw_text)
    score = _compute_score(
        tp_rate=tp_rate,
        fp_rate=fp_rate,
        fn_rate=fn_rate,
        exception_count=exception_count,
        code_chars=code_chars,
    )

    # Adaptive floor gate.
    holdout_rate = _compute_tier_pass_rate(results, "holdout")
    cf_rate = _compute_tier_pass_rate(results, "counterfactual")
    drift_rate = _compute_tier_pass_rate(results, "drift")

    floor_passed, floor_reasons = _adaptive_floor_gate(
        holdout_rate=holdout_rate,
        counterfactual_rate=cf_rate,
        drift_rate=drift_rate,
        min_holdout_pass_rate=min_holdout_pass_rate,
        min_counterfactual_pass_rate=min_cf_pass_rate,
        min_drift_pass_rate=min_drift_pass_rate,
    )

    # Adoption gate — syntax_ok/ast_policy_ok/contract_ok/timed_out are always
    # True/False for structured rules (no Python code to validate).
    gate_passed, gate_reasons = _adoption_gate(
        syntax_ok=True,
        ast_policy_ok=True,
        contract_ok=True,
        timed_out=False,
        exception_count=exception_count,
        regression_pass_rate=regression_pass_rate,
        fp_rate=fp_rate,
        avg_latency_ms=avg_latency_ms,
        score=score,
        previous_best_score=previous_best_score,
        baseline_mode=baseline_mode,
        max_fp_rate=max_fp_rate,
        min_regression_pass_rate=min_regression_pass_rate,
        max_avg_latency_ms=max_avg_latency_ms,
    )

    # Parity guard: structured rules that produce identical per-case outcomes to the
    # current legacy detector cannot represent a behavioral improvement. Reject in
    # non-baseline mode so a behavior-equivalent candidate cannot pass the adoption gate
    # merely by having a lower code_chars count than the live Python detector.
    parity_reasons: list[str] = []
    parity_rejected = False
    if not baseline_mode:
        legacy_results_raw = evaluate_detector(_legacy_inspect_request, cases)
        legacy_outcomes = {r["id"]: r["actual_blocked"] for r in legacy_results_raw}
        structured_outcomes = {r["id"]: r["actual_blocked"] for r in results}
        if legacy_outcomes == structured_outcomes:
            parity_rejected = True
            parity_reasons.append(
                "no_behavior_improvement_against_current_detector: "
                "structured rules produce identical per-case outcomes to the legacy detector"
            )

    all_reasons = gate_reasons + floor_reasons + parity_reasons
    overall_passed = gate_passed and floor_passed and not parity_rejected

    report = {
        "success": overall_passed,          # matches passed_adoption_gate
        "evaluation_completed": True,
        "schema_valid": True,
        "passed_adoption_gate": overall_passed,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "exception_count": exception_count,
        "total_cases": total,
        "tp_rate": tp_rate,
        "fp_rate": fp_rate,
        "fn_rate": fn_rate,
        "avg_latency_ms": avg_latency_ms,
        "score": score,
        "code_chars": code_chars,
        "rejection_reasons": all_reasons,
        "adaptive_floor_passed": floor_passed,
        "holdout_pass_rate": holdout_rate if holdout_rate is not None else 1.0,
        "counterfactual_pass_rate": cf_rate if cf_rate is not None else 1.0,
        "drift_pass_rate": drift_rate if drift_rate is not None else 1.0,
        "score_comparison_mode": "structured_rules_parity_guard",
        "mode": "structured_rules",
        "rules_path": str(rules_path),
    }
    return report, False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a structured rules document as a candidate"
    )
    parser.add_argument(
        "--rules",
        required=True,
        help="Required. Explicit path to structured rules JSON.",
    )
    parser.add_argument(
        "--genome",
        default=None,
        metavar="PATH",
        help="Optional. Path to genome.json. Defaults to data/genome.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Optional. Print JSON output.",
    )
    parser.add_argument(
        "--soft-reject",
        action="store_true",
        dest="soft_reject",
        help=(
            "Optional. Exit 0 when evaluation completed even if candidate failed gate. "
            "Tool failures still exit 1."
        ),
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Optional. Bypass score-improvement and parity-guard requirements (baseline mode).",
    )
    parser.add_argument(
        "--corpus-dir",
        default=None,
        dest="corpus_dir",
        metavar="DIR",
        help=(
            "Optional. Directory containing Owner-supplied corpus files "
            "(benign_requests.json, attack_requests.json, regression_cases.json, "
            "holdout_requests.json, counterfactual_requests.json, drift_requests.json). "
            "Read-only inputs; use realistic but safely neutralized, defensive-only "
            "data from OUTSIDE the repository. Defaults to the repository data/ corpus."
        ),
    )
    for _tier in _CORPUS_TIER_FILENAMES:
        parser.add_argument(
            f"--{_tier}-path",
            default=None,
            dest=f"{_tier}_path",
            metavar="PATH",
            help=(
                f"Optional. Explicit path to the {_tier} corpus file. "
                f"Overrides --corpus-dir for this tier."
            ),
        )
    parser.add_argument(
        "--report-path",
        default=None,
        dest="report_path",
        metavar="PATH",
        help="Optional. Write report JSON to this explicit path only. No default path.",
    )
    args = parser.parse_args(argv)

    rules_path = Path(args.rules)
    genome_path = Path(args.genome) if args.genome else _GENOME_PATH

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else None
    corpus_overrides: dict[str, Path | None] = {
        tier: (Path(getattr(args, f"{tier}_path")) if getattr(args, f"{tier}_path") else None)
        for tier in _CORPUS_TIER_FILENAMES
    }
    corpus_paths = _resolve_corpus_paths(corpus_dir, corpus_overrides)

    # Reject --report-path targets inside frozen project paths before evaluating.
    if args.report_path and _is_forbidden_report_path(Path(args.report_path)):
        error_msg = f"--report-path target is in a frozen project path: {args.report_path}"
        if args.json:
            print(json.dumps({
                "success": False,
                "evaluation_completed": False,
                "passed_adoption_gate": False,
                "error": error_msg,
                "rejection_reasons": [error_msg],
                "mode": "structured_rules",
            }, indent=2))
        else:
            print(f"ERROR: {error_msg}")
        return 1

    # Reject --report-path targets that exist but are not regular files (FIFOs, device
    # nodes, etc.) BEFORE evaluation. write_text() to a FIFO blocks indefinitely;
    # failing early provides a clear error without running any evaluation.
    if args.report_path:
        _rp = Path(args.report_path)
        try:
            _rp_st = _rp.stat()
            if not stat.S_ISREG(_rp_st.st_mode):
                error_msg = (
                    f"--report-path target exists but is not a regular file "
                    f"(mode={stat.filemode(_rp_st.st_mode)!r}): {args.report_path}"
                )
                if args.json:
                    print(json.dumps({
                        "success": False,
                        "evaluation_completed": False,
                        "passed_adoption_gate": False,
                        "error": error_msg,
                        "rejection_reasons": [error_msg],
                        "mode": "structured_rules",
                    }, indent=2))
                else:
                    print(f"ERROR: {error_msg}")
                return 1
        except OSError:
            pass  # Path does not exist yet — mkdir+write_text will handle creation

    report, is_tool_failure = evaluate_structured_rules(
        rules_path,
        genome_path=genome_path,
        baseline_mode=args.baseline,
        corpus_paths=corpus_paths,
    )

    if args.report_path:
        report_file = Path(args.report_path)
        try:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError as exc:
            write_error = f"failed to write report file: {exc}"
            if args.json:
                print(json.dumps({
                    "success": False,
                    "evaluation_completed": False,
                    "passed_adoption_gate": False,
                    "error": write_error,
                    "rejection_reasons": [write_error],
                    "mode": "structured_rules",
                    "rules_path": str(rules_path),
                }, indent=2))
            else:
                print(f"ERROR: {write_error}")
            return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report.get("passed_adoption_gate"):
            print("SUCCESS: structured rules candidate passed adoption gate")
        else:
            error = report.get("error", "adoption gate not passed")
            reasons = report.get("rejection_reasons", [])
            print(f"RESULT: {error}")
            for r in reasons:
                print(f"  reason: {r}")

    if args.soft_reject:
        return 1 if is_tool_failure else 0
    return 0 if report.get("passed_adoption_gate") else 1


if __name__ == "__main__":
    sys.exit(main())
