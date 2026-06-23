"""scripts/generalization_report.py — Measure detection generalization to unknown threats.

The mission requires detecting "不特定の脅威" — threats the system was not built
around. This makes that measurable: it grades a ruleset on an IN-DISTRIBUTION
corpus (threat classes/variants the proposer is built for) and on a HELD-OUT
corpus (evasive variants + new threat classes the proposer was never shown), and
reports the generalization gap honestly.

Generalization is the held-out attack detection rate. A large gap between
in-distribution and held-out detection is the gap the autonomous loop must close
by proposing detection for newly-surfaced threats. False positives on held-out
benign requests are also reported (must stay low).

SAFETY: read-only. No network, no Gemini API, no candidate code execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from cli.structured_eval import load_corpus, load_rules, run_evaluation  # noqa: E402

_DEFAULT_RULES = _PROJECT_ROOT / "fixtures" / "structured_rules" / "realistic_baseline.json"
_DEFAULT_IN = _PROJECT_ROOT / "fixtures" / "realistic_corpus" / "all_cases.json"
_DEFAULT_HELDOUT = _PROJECT_ROOT / "fixtures" / "generalization_corpus" / "heldout_threats.json"


def _rates(overall: dict) -> tuple[float, float]:
    attack_total = overall["TP"] + overall["FN"]
    benign_total = overall["TN"] + overall["FP"]
    tp_rate = overall["TP"] / attack_total if attack_total else 0.0
    fp_rate = overall["FP"] / benign_total if benign_total else 0.0
    return tp_rate, fp_rate


def build_report(rules_path: Path, in_corpus: Path, heldout_corpus: Path) -> dict:
    rules = load_rules(rules_path)
    in_res = run_evaluation(rules, load_corpus(in_corpus))["overall"]
    ho_res = run_evaluation(rules, load_corpus(heldout_corpus))["overall"]
    in_tp, in_fp = _rates(in_res)
    ho_tp, ho_fp = _rates(ho_res)
    return {
        "rules_path": str(rules_path),
        "in_distribution": {"tp_rate": in_tp, "fp_rate": in_fp,
                            "TP": in_res["TP"], "FN": in_res["FN"]},
        "held_out": {"tp_rate": ho_tp, "fp_rate": ho_fp,
                     "TP": ho_res["TP"], "FN": ho_res["FN"]},
        "generalization_gap": round(in_tp - ho_tp, 4),
        "held_out_false_positive_rate": ho_fp,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure generalization to unknown threats.")
    parser.add_argument("--rules", default=None)
    parser.add_argument("--in-corpus", default=None, dest="in_corpus")
    parser.add_argument("--heldout-corpus", default=None, dest="heldout_corpus")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(
        Path(args.rules) if args.rules else _DEFAULT_RULES,
        Path(args.in_corpus) if args.in_corpus else _DEFAULT_IN,
        Path(args.heldout_corpus) if args.heldout_corpus else _DEFAULT_HELDOUT,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        idd, ho = report["in_distribution"], report["held_out"]
        print(f"In-distribution detection: {idd['tp_rate']*100:.0f}% (FP {idd['fp_rate']*100:.0f}%)")
        print(f"Held-out (unknown) detection: {ho['tp_rate']*100:.0f}% (FP {ho['fp_rate']*100:.0f}%)")
        print(f"Generalization gap: {report['generalization_gap']*100:.0f} points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
