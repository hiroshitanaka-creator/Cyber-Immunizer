"""scripts/post_promote_healthcheck.py — Verify the live active detector after promotion.

This is the self-healing safety net for the autonomous loop (M2). After a
structured promotion flips ``genome.detector_mode`` to ``structured_rules``, this
checks that the detector is actually live and effective AT THE RUNTIME ENTRY
POINT (``core.active_detector.inspect_active``), not merely recorded in the
genome. It catches silent failures — e.g. the active rules path being unreadable
so ``inspect_active`` falls back to legacy (which detects 0 realistic threats).

Health criteria (against the SAME per-tier corpus the promotion grades against —
``--corpus-dir``, so the health check never validates against stale data from a
separately maintained combined file):
  - false-positive rate <= genome.max_fp_rate (default 0.05)
  - detection (tp) rate >= --min-tp-rate (default 0.5)

Exit 0 = healthy (or detector_mode is legacy → nothing to verify).
Exit 1 = unhealthy → the caller should roll back to legacy.

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

from core.active_detector import inspect_active  # noqa: E402
from core.types import Request  # noqa: E402
# Reuse the EXACT per-tier corpus filenames the promotion grades against, so a
# health check sourced from --corpus-dir reads the same files and cannot drift
# from a separately maintained combined file (Codex finding).
from scripts.evaluate_structured_rules_candidate import _CORPUS_TIER_FILENAMES  # noqa: E402,PLC2701

_DEFAULT_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DEFAULT_CORPUS_PATH = _PROJECT_ROOT / "fixtures" / "realistic_corpus" / "all_cases.json"


def _load_corpus_from_dir(corpus_dir: Path) -> list[dict]:
    """Concatenate the per-tier corpus files in ``corpus_dir`` — the SAME source
    the promotion grades against (``--corpus-dir``) — so the health check never
    validates against stale data from a separately maintained combined file.
    Tier files that are absent are skipped (the promotion likewise leaves absent
    tiers to their ``data/`` defaults)."""
    cases: list[dict] = []
    for filename in _CORPUS_TIER_FILENAMES.values():
        path = corpus_dir / filename
        if not path.exists():
            continue
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"corpus tier file {path} must be a JSON array")
        cases.extend(loaded)
    return cases


def _request(entry: dict) -> Request:
    req = entry.get("request", {})
    return Request(
        method=req.get("method", "GET"), path=req.get("path", "/"),
        query=dict(req.get("query") or {}), headers=dict(req.get("headers") or {}),
        body=req.get("body", ""), source_ip=req.get("source_ip"),
    )


def run_healthcheck(
    *,
    genome_path: Path,
    min_tp_rate: float,
    corpus_path: Path | None = None,
    corpus_dir: Path | None = None,
) -> tuple[dict, bool]:
    """Return (report, healthy).

    Corpus source precedence: ``corpus_dir`` (per-tier files, matching the
    promotion's ``--corpus-dir``) wins over ``corpus_path`` (a single combined
    file). When neither is given, the default combined corpus is used.
    """
    try:
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"healthy": False, "reason": f"could not read genome: {exc}"}, False
    if not isinstance(genome, dict):
        return {"healthy": False, "reason": "genome must be an object"}, False

    if genome.get("detector_mode") != "structured_rules":
        return {"healthy": True, "skipped": True, "reason": "detector_mode is not structured_rules"}, True

    max_fp_rate = float(genome.get("max_fp_rate", 0.05))

    try:
        if corpus_dir is not None:
            corpus = _load_corpus_from_dir(corpus_dir)
        else:
            corpus = json.loads((corpus_path or _DEFAULT_CORPUS_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"healthy": False, "reason": f"could not read corpus: {exc}"}, False
    if not isinstance(corpus, list) or not corpus:
        return {"healthy": False, "reason": "corpus must be a non-empty list"}, False

    tp = fp = tn = fn = 0
    for entry in corpus:
        if not isinstance(entry, dict) or "expected_blocked" not in entry:
            continue
        expected = bool(entry["expected_blocked"])
        # Exercise the real runtime dispatch for the genome under check, including
        # any silent fallback to legacy (active rules path resolved from genome).
        blocked = inspect_active(_request(entry), genome_path=genome_path).blocked
        if expected and blocked:
            tp += 1
        elif expected and not blocked:
            fn += 1
        elif not expected and blocked:
            fp += 1
        else:
            tn += 1

    attack_total = tp + fn
    benign_total = tn + fp
    tp_rate = tp / attack_total if attack_total else 0.0
    fp_rate = fp / benign_total if benign_total else 0.0

    healthy = (fp_rate <= max_fp_rate) and (tp_rate >= min_tp_rate)
    report = {
        "healthy": healthy,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "tp_rate": tp_rate, "fp_rate": fp_rate,
        "max_fp_rate": max_fp_rate, "min_tp_rate": min_tp_rate,
    }
    if not healthy:
        report["reason"] = (
            f"active detector unhealthy: tp_rate={tp_rate:.3f} (min {min_tp_rate}), "
            f"fp_rate={fp_rate:.3f} (max {max_fp_rate}) — promotion may have silently "
            "fallen back to legacy or the active rules are ineffective"
        )
    return report, healthy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the live active detector after promotion.")
    parser.add_argument("--genome", default=None, metavar="PATH")
    parser.add_argument("--corpus", default=None, metavar="PATH")
    parser.add_argument(
        "--corpus-dir", default=None, metavar="DIR", dest="corpus_dir",
        help="Per-tier corpus directory (matches the promotion's --corpus-dir); "
             "takes precedence over --corpus.",
    )
    parser.add_argument("--min-tp-rate", type=float, default=0.5, dest="min_tp_rate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report, healthy = run_healthcheck(
        genome_path=Path(args.genome) if args.genome else _DEFAULT_GENOME_PATH,
        corpus_dir=Path(args.corpus_dir) if args.corpus_dir else None,
        corpus_path=Path(args.corpus) if args.corpus else None,
        min_tp_rate=args.min_tp_rate,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    elif healthy:
        print(f"Post-promote health check PASSED ({report})")
    else:
        print(f"Post-promote health check FAILED: {report.get('reason')}", file=sys.stderr)
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
