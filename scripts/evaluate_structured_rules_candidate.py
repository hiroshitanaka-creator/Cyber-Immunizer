"""scripts/evaluate_structured_rules_candidate.py — Explicit structured-rules candidate evaluation.

Usage:
    python scripts/evaluate_structured_rules_candidate.py \\
        --rules path/to/structured_rules.json \\
        [--genome path/to/genome.json] \\
        [--json] \\
        [--soft-reject] \\
        [--baseline] \\
        [--report-path PATH]

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

# Frozen project paths that --report-path must not target.
_FORBIDDEN_REPORT_PREFIXES: frozenset[str] = frozenset([
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
    """Load genome.json strictly. Raises OSError or json.JSONDecodeError on failure.

    Fail-closed: callers must handle the exception as a tool failure rather than
    substituting defaults, so that a missing or malformed genome cannot silently
    lower gate thresholds (e.g. previous_best_score=-1e9) and promote a candidate.
    """
    raw = genome_path.read_text(encoding="utf-8")
    return json.loads(raw)


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


def _validate_genome_thresholds(genome: dict) -> str | None:
    """Validate genome threshold fields. Return error string if invalid, else None.

    Rejects bool, non-number, and non-finite values.
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
        val = genome[field]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"genome threshold {field!r} is not a number: {val!r}"
        if not math.isfinite(float(val)):
            return f"genome threshold {field!r} is non-finite: {val!r}"
        if not (0.0 <= float(val) <= 1.0):
            return f"genome threshold {field!r} out of range [0.0, 1.0]: {val}"

    if "max_avg_latency_ms" in genome:
        val = genome["max_avg_latency_ms"]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"genome threshold 'max_avg_latency_ms' is not a number: {val!r}"
        fval = float(val)
        if not math.isfinite(fval) or fval <= 0:
            return f"genome threshold 'max_avg_latency_ms' must be finite and > 0: {val!r}"

    if "best_score" in genome:
        val = genome["best_score"]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"genome threshold 'best_score' is not a number: {val!r}"
        if not math.isfinite(float(val)):
            return f"genome threshold 'best_score' is non-finite: {val!r}"

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
) -> tuple[dict, bool]:
    """Evaluate a structured rules document and return (report, is_tool_failure).

    Tool failures (unreadable/oversized file, malformed/duplicate-key JSON, genome load
    failure, invalid genome thresholds, test-case load failure):
        success=False, evaluation_completed=False, is_tool_failure=True

    Candidate rejections (invalid schema, gate failed, parity guard):
        success=False, evaluation_completed=True, is_tool_failure=False

    Returns a JSON-serializable report dict.
    """
    # Bound file size before reading to prevent memory pressure from huge inputs.
    try:
        file_size = rules_path.stat().st_size
    except OSError as exc:
        return _tool_failure(f"failed to stat rules file: {exc}", rules_path)
    if file_size > _MAX_RULES_FILE_BYTES:
        return _tool_failure(
            f"rules file exceeds size limit: {file_size} bytes > {_MAX_RULES_FILE_BYTES} bytes",
            rules_path,
        )

    # Read rules file.
    try:
        raw_text = rules_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _tool_failure(f"failed to read rules file: {exc}", rules_path)

    # Parse JSON with duplicate-key rejection. Duplicate keys are a tool failure
    # because canonical static validation rejects them; the evaluator must not accept
    # artifacts that static validation would reject.
    try:
        rules_doc = json.loads(raw_text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        return _tool_failure(f"malformed JSON in rules file: {exc}", rules_path)

    # Schema validation — failure is candidate rejection, not a tool failure.
    validation = validate_rules_schema(rules_doc)
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
    except (OSError, json.JSONDecodeError, ValueError) as exc:
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
    try:
        cases = load_test_cases()
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
        legacy_outcomes = {
            r["id"]: r["actual_blocked"]
            for r in legacy_results_raw
            if r.get("kind") in _MAIN_EVAL_KINDS
        }
        structured_outcomes = {r["id"]: r["actual_blocked"] for r in main_results}
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
        "--report-path",
        default=None,
        dest="report_path",
        metavar="PATH",
        help="Optional. Write report JSON to this explicit path only. No default path.",
    )
    args = parser.parse_args(argv)

    rules_path = Path(args.rules)
    genome_path = Path(args.genome) if args.genome else _GENOME_PATH

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

    report, is_tool_failure = evaluate_structured_rules(
        rules_path,
        genome_path=genome_path,
        baseline_mode=args.baseline,
    )

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

    if args.report_path:
        report_file = Path(args.report_path)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.soft_reject:
        return 1 if is_tool_failure else 0
    return 0 if report.get("passed_adoption_gate") else 1


if __name__ == "__main__":
    sys.exit(main())
