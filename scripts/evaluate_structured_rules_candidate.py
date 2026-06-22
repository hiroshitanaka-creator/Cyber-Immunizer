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
    1  Tool failure (malformed JSON, unreadable file) OR adoption gate failed

Exit codes with --soft-reject:
    0  Evaluation completed (regardless of gate outcome)
    1  Tool failure only (malformed JSON, unreadable file, test-case load failure)

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
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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


def _load_genome(genome_path: Path) -> dict:
    try:
        return json.loads(genome_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


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

    Tool failures (unreadable file, malformed JSON, test-case load failure):
        success=False, is_tool_failure=True

    Candidate rejections (invalid schema, gate failed):
        success=True (or False for gate), is_tool_failure=False

    Returns a JSON-serializable report dict.
    """
    # Load and parse the rules file strictly.
    try:
        raw_text = rules_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _tool_failure(f"failed to read rules file: {exc}", rules_path)

    try:
        rules_doc = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return _tool_failure(f"malformed JSON in rules file: {exc}", rules_path)

    # Schema validation — failure is candidate rejection, not a tool failure.
    validation = validate_rules_schema(rules_doc)
    if not validation.get("success"):
        violations = validation.get("violations", [])
        rejection_reasons = [f"schema validation failed: {v}" for v in violations]
        return {
            "success": True,
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
            "rejection_reasons": rejection_reasons,
            "adaptive_floor_passed": False,
            "holdout_pass_rate": 0.0,
            "counterfactual_pass_rate": 0.0,
            "drift_pass_rate": 0.0,
            "mode": "structured_rules",
            "rules_path": str(rules_path),
        }, False

    # Load genome for gate thresholds.
    genome = _load_genome(genome_path)
    max_fp_rate: float = float(genome.get("max_fp_rate", 0.05))
    min_regression_pass_rate: float = float(genome.get("min_regression_pass_rate", 1.0))
    previous_best_score: float = float(genome.get("best_score", -1e9))
    max_avg_latency_ms: float = float(genome.get("max_avg_latency_ms", 100.0))
    min_holdout_pass_rate: float = float(genome.get("min_holdout_pass_rate", 1.0))
    min_cf_pass_rate: float = float(genome.get("min_counterfactual_pass_rate", 1.0))
    min_drift_pass_rate: float = float(genome.get("min_drift_pass_rate", 1.0))

    # Build the detector callable via runtime selector.
    detector_fn = _make_detector_callable(rules_doc)

    # Load test cases. Silently skip missing adaptive tier files (require_adaptive_tiers=False)
    # so the script works in environments where only core tiers exist.
    try:
        cases = load_test_cases(require_adaptive_tiers=False)
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

    # Score using the same formula as core.fitness; code_chars=0 (no Python code).
    score = _compute_score(
        tp_rate=tp_rate,
        fp_rate=fp_rate,
        fn_rate=fn_rate,
        exception_count=exception_count,
        code_chars=0,
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

    all_reasons = gate_reasons + floor_reasons
    overall_passed = gate_passed and floor_passed

    report = {
        "success": overall_passed,
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
        "rejection_reasons": all_reasons,
        "adaptive_floor_passed": floor_passed,
        "holdout_pass_rate": holdout_rate if holdout_rate is not None else 1.0,
        "counterfactual_pass_rate": cf_rate if cf_rate is not None else 1.0,
        "drift_pass_rate": drift_rate if drift_rate is not None else 1.0,
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
        help="Optional. Bypass score-improvement requirement (baseline mode).",
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
