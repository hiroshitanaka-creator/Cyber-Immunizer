"""core/fitness.py — Deterministic fitness evaluation for candidate detectors.

Usage (CLI):
    python -m core.fitness --candidate core/detector.py [--json] [--baseline]

SAFETY NOTICE
=============
Candidate code is loaded via importlib only after strict policy validation.
The subprocess boundary is enforced by scripts/evaluate_candidate.py, which
passes no secrets or write credentials to this process.

SCORE DETERMINISM
=================
avg_latency_ms is EXCLUDED from the ranking score to ensure the score is
identical across repeated runs for the same candidate and same test data.
Latency is still measured and reported; it is enforced as a hard adoption gate
via genome.json::max_avg_latency_ms.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from core.policy import run_full_policy
from core.test_attacker import (
    evaluate_detector,
    load_test_cases,
    summarize_results,
)
from core.types import DetectionResult, FitnessReport, Request

_DATA_DIR = Path(__file__).parent.parent / "data"
_GENOME_PATH = _DATA_DIR / "genome.json"


# ---------------------------------------------------------------------------
# Score formula  (deterministic — no timing component)
# ---------------------------------------------------------------------------

def _compute_score(
    tp_rate: float,
    fp_rate: float,
    fn_rate: float,
    exception_count: int,
    code_chars: int,
    changed_lines: int,
) -> float:
    """Deterministic fitness score.

    avg_latency_ms is intentionally excluded so the score is identical
    across repeated evaluations of the same candidate on the same data.
    """
    return (
        1000.0 * tp_rate
        - 2000.0 * fp_rate
        - 1500.0 * fn_rate
        - 50.0 * exception_count
        - 0.02 * code_chars
        - 10.0 * changed_lines
    )


# ---------------------------------------------------------------------------
# Adoption gate
# ---------------------------------------------------------------------------

def _adoption_gate(
    *,
    syntax_ok: bool,
    ast_policy_ok: bool,
    contract_ok: bool,
    timed_out: bool,
    exception_count: int,
    regression_pass_rate: float,
    fp_rate: float,
    avg_latency_ms: float,
    score: float,
    previous_best_score: float,
    baseline_mode: bool,
    max_fp_rate: float,
    min_regression_pass_rate: float,
    max_avg_latency_ms: float,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if not syntax_ok:
        reasons.append("syntax_ok is False")
    if not ast_policy_ok:
        reasons.append("ast_policy_ok is False")
    if not contract_ok:
        reasons.append("contract_ok is False")
    if timed_out:
        reasons.append("evaluation timed out")
    if exception_count > 0:
        reasons.append(f"exception_count={exception_count} > 0")
    if regression_pass_rate < min_regression_pass_rate:
        reasons.append(
            f"regression_pass_rate={regression_pass_rate:.3f} < "
            f"{min_regression_pass_rate:.3f}"
        )
    if fp_rate > max_fp_rate:
        reasons.append(f"fp_rate={fp_rate:.3f} > max_fp_rate={max_fp_rate:.3f}")
    if avg_latency_ms > max_avg_latency_ms:
        reasons.append(
            f"avg_latency_ms={avg_latency_ms:.2f} > "
            f"max_avg_latency_ms={max_avg_latency_ms:.2f}"
        )
    if not baseline_mode and score <= previous_best_score:
        reasons.append(
            f"score={score:.4f} <= previous_best={previous_best_score:.4f}"
        )

    return len(reasons) == 0, reasons


# ---------------------------------------------------------------------------
# Changed-line diff helper
# ---------------------------------------------------------------------------

def _count_changed_lines(candidate_source: str, base_path: Path) -> int:
    """Count lines that differ between candidate and the current base detector."""
    if not base_path.exists():
        return 0
    base_lines = base_path.read_text(encoding="utf-8").splitlines()
    cand_lines = candidate_source.splitlines()
    max_len = max(len(base_lines), len(cand_lines))
    return sum(
        1
        for i in range(max_len)
        if (base_lines[i] if i < len(base_lines) else "")
        != (cand_lines[i] if i < len(cand_lines) else "")
    )


# ---------------------------------------------------------------------------
# Contract check
# ---------------------------------------------------------------------------

def _contract_ok(module: Any) -> tuple[bool, str]:
    """Verify the candidate module exposes the correct interface."""
    if not hasattr(module, "inspect_request"):
        return False, "inspect_request not found"
    fn = module.inspect_request
    if not callable(fn):
        return False, "inspect_request is not callable"
    dummy = Request(method="GET", path="/", query={}, headers={}, body="")
    try:
        result = fn(dummy)
    except Exception as exc:
        return False, f"inspect_request raised on smoke test: {exc}"
    if not isinstance(result, DetectionResult):
        return False, f"inspect_request returned {type(result)!r}, not DetectionResult"
    if not (0.0 <= result.confidence <= 1.0):
        return False, f"confidence={result.confidence} out of [0.0, 1.0]"
    return True, ""


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------

def evaluate(
    candidate_path: Path,
    *,
    baseline_mode: bool = False,
    genome_path: Path | None = None,
) -> FitnessReport:
    """Evaluate a candidate detector and return a FitnessReport.

    The strict AST policy from core.policy is applied before any import.
    """
    genome_path = genome_path or _GENOME_PATH
    genome = json.loads(genome_path.read_text(encoding="utf-8"))
    max_fp_rate: float = float(genome.get("max_fp_rate", 0.05))
    min_regression_pass_rate: float = float(genome.get("min_regression_pass_rate", 1.0))
    previous_best_score: float = float(genome.get("best_score", -1e9))
    max_avg_latency_ms: float = float(genome.get("max_avg_latency_ms", 100.0))

    source = candidate_path.read_text(encoding="utf-8")
    code_chars = len(source)

    # --- Strict policy check (identical to scripts/validate_mutation.py) ---
    policy_result = run_full_policy(candidate_path)
    syntax_ok = not any("SyntaxError" in v for v in policy_result.get("violations", []))
    policy_ok = policy_result["valid"]

    if not policy_ok:
        return FitnessReport(
            syntax_ok=syntax_ok,
            ast_policy_ok=False,
            contract_ok=False,
            timed_out=False,
            exception_count=0,
            true_positive=0,
            false_positive=0,
            true_negative=0,
            false_negative=0,
            total_cases=0,
            tp_rate=0.0,
            fp_rate=0.0,
            fn_rate=0.0,
            avg_latency_ms=0.0,
            code_chars=code_chars,
            changed_lines=0,
            score=-1e9,
            passed_adoption_gate=False,
            rejection_reasons=tuple(policy_result["violations"]),
        )

    # --- Load module ---
    spec = importlib.util.spec_from_file_location("_candidate_detector", candidate_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:
        return FitnessReport(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=False,
            timed_out=False,
            exception_count=1,
            true_positive=0,
            false_positive=0,
            true_negative=0,
            false_negative=0,
            total_cases=0,
            tp_rate=0.0,
            fp_rate=0.0,
            fn_rate=0.0,
            avg_latency_ms=0.0,
            code_chars=code_chars,
            changed_lines=0,
            score=-1e9,
            passed_adoption_gate=False,
            rejection_reasons=(f"module load failed: {exc}",),
        )

    # --- Contract check ---
    c_ok, c_reason = _contract_ok(module)

    # --- Load test cases ---
    try:
        cases = load_test_cases()
    except Exception as exc:
        return FitnessReport(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=c_ok,
            timed_out=False,
            exception_count=1,
            true_positive=0,
            false_positive=0,
            true_negative=0,
            false_negative=0,
            total_cases=0,
            tp_rate=0.0,
            fp_rate=0.0,
            fn_rate=0.0,
            avg_latency_ms=0.0,
            code_chars=code_chars,
            changed_lines=0,
            score=-1e9,
            passed_adoption_gate=False,
            rejection_reasons=(f"test case load failed: {exc}",),
        )

    if not c_ok:
        return FitnessReport(
            syntax_ok=True,
            ast_policy_ok=True,
            contract_ok=False,
            timed_out=False,
            exception_count=0,
            true_positive=0,
            false_positive=0,
            true_negative=0,
            false_negative=0,
            total_cases=len(cases),
            tp_rate=0.0,
            fp_rate=0.0,
            fn_rate=0.0,
            avg_latency_ms=0.0,
            code_chars=code_chars,
            changed_lines=0,
            score=-1e9,
            passed_adoption_gate=False,
            rejection_reasons=(c_reason,),
        )

    # --- Run evaluation ---
    results = evaluate_detector(module.inspect_request, cases)
    summary = summarize_results(results)

    tp = summary["true_positive"]
    fp = summary["false_positive"]
    tn = summary["true_negative"]
    fn = summary["false_negative"]
    total = summary["total_cases"]
    exception_count = summary["exception_count"]
    avg_latency_ms = summary["avg_latency_ms"]

    # Regression pass rate
    regression_results = [r for r in results if r.get("kind") == "regression"]
    reg_pass = sum(
        1
        for r in regression_results
        if r["actual_blocked"] == r["expected_blocked"] and not r["exception"]
    )
    regression_pass_rate = (
        reg_pass / len(regression_results) if regression_results else 1.0
    )

    # Rates
    attack_total = tp + fn
    benign_total = tn + fp
    tp_rate = tp / attack_total if attack_total else 0.0
    fp_rate = fp / benign_total if benign_total else 0.0
    fn_rate = fn / attack_total if attack_total else 0.0

    changed_lines = _count_changed_lines(
        source, Path(__file__).parent / "detector.py"
    )

    # Deterministic score (latency excluded)
    score = _compute_score(
        tp_rate=tp_rate,
        fp_rate=fp_rate,
        fn_rate=fn_rate,
        exception_count=exception_count,
        code_chars=code_chars,
        changed_lines=changed_lines,
    )

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

    return FitnessReport(
        syntax_ok=True,
        ast_policy_ok=True,
        contract_ok=True,
        timed_out=False,
        exception_count=exception_count,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        total_cases=total,
        tp_rate=tp_rate,
        fp_rate=fp_rate,
        fn_rate=fn_rate,
        avg_latency_ms=avg_latency_ms,
        code_chars=code_chars,
        changed_lines=changed_lines,
        score=score,
        passed_adoption_gate=gate_passed,
        rejection_reasons=tuple(gate_reasons),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _report_to_dict(report: FitnessReport) -> dict:
    return {
        "syntax_ok": report.syntax_ok,
        "ast_policy_ok": report.ast_policy_ok,
        "contract_ok": report.contract_ok,
        "timed_out": report.timed_out,
        "exception_count": report.exception_count,
        "true_positive": report.true_positive,
        "false_positive": report.false_positive,
        "true_negative": report.true_negative,
        "false_negative": report.false_negative,
        "total_cases": report.total_cases,
        "tp_rate": report.tp_rate,
        "fp_rate": report.fp_rate,
        "fn_rate": report.fn_rate,
        "avg_latency_ms": report.avg_latency_ms,
        "code_chars": report.code_chars,
        "changed_lines": report.changed_lines,
        "score": report.score,
        "passed_adoption_gate": report.passed_adoption_gate,
        "rejection_reasons": list(report.rejection_reasons),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer fitness evaluator")
    parser.add_argument("--candidate", required=True, help="Path to candidate detector")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Baseline mode: skip score-improvement gate",
    )
    args = parser.parse_args(argv)

    candidate_path = Path(args.candidate)
    if not candidate_path.exists():
        print(json.dumps({"error": f"Candidate not found: {candidate_path}"}))
        return 1

    report = evaluate(candidate_path, baseline_mode=args.baseline)
    d = _report_to_dict(report)

    if args.json:
        print(json.dumps(d, indent=2))
    else:
        for k, v in d.items():
            print(f"  {k}: {v}")

    return 0 if report.passed_adoption_gate else 1


if __name__ == "__main__":
    sys.exit(main())
