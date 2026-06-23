"""scripts/promote_structured_candidate.py — Promote a structured rules candidate.

This is the structured-rules counterpart to ``scripts/promote_candidate.py``.
It promotes a validated structured rules document to become the **active
detector** by writing the rules document to a canonical location and switching
``data/genome.json`` to ``detector_mode == "structured_rules"``.

Usage:
    python scripts/promote_structured_candidate.py \\
        --rules path/to/structured_rules.json \\
        --corpus-dir path/to/realistic_corpus_dir \\
        --owner-approved \\
        [--genome PATH] [--history PATH] [--active-rules-out PATH] \\
        [--baseline] [--json]

Fail-closed design:
    Unlike the Docker-attested autonomous Python path, structured-rules
    evaluation runs in-process. To avoid trusting a separately produced (and
    therefore forgeable) fitness report, this script **re-evaluates the rules
    document itself** through the same gate as
    ``scripts/evaluate_structured_rules_candidate.py`` (score + adoption gate +
    adaptive floor + parity guard) and promotes only if that live evaluation
    passes. Promotion also requires the explicit ``--owner-approved`` flag,
    because switching the active detector is an Owner-gated decision.

SAFETY:
    No network calls. No Gemini API. No workflow dispatch. No paid-credit run.
    No ledger edits. Writes only the active rules document, data/genome.json,
    and data/evolution_history.json. The realistic corpus is a read-only input
    supplied from outside the repository; its contents are never committed here.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.structured_validator import validate_rules_schema  # noqa: E402
from scripts.evaluate_structured_rules_candidate import (  # noqa: E402
    _CORPUS_TIER_FILENAMES,
    _resolve_corpus_paths,
    evaluate_structured_rules,
)

_DEFAULT_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_DEFAULT_HISTORY_PATH = _PROJECT_ROOT / "data" / "evolution_history.json"
_DEFAULT_ACTIVE_RULES_PATH = _PROJECT_ROOT / "data" / "active_structured_rules.json"
_MAX_RULES_FILE_BYTES = 1_048_576


def _refuse(reason: str, as_json: bool) -> int:
    payload = {"success": False, "promoted": False, "reason": reason}
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"REFUSED: {reason}", file=sys.stderr)
    return 1


def _atomic_write(path: Path, text: str) -> None:
    """Write text to path atomically via a temp file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _load_history_strict(path: Path) -> tuple[list | None, str]:
    """Load evolution_history.json fail-closed. Returns (history, error)."""
    if not path.exists():
        return None, f"evolution_history.json not found at {path} — promote is fail-closed"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"evolution_history.json unreadable: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"evolution_history.json malformed JSON: {exc}"
    if not isinstance(data, list):
        return None, f"evolution_history.json top-level must be a list, got {type(data).__name__}"
    return data, ""


def _relative_active_path(active_rules_out: Path) -> str:
    """Record the active rules path in genome as repo-relative posix when possible."""
    try:
        return active_rules_out.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(active_rules_out)


def promote_structured_candidate(
    *,
    rules_path: Path,
    corpus_dir: Path | None,
    corpus_overrides: dict[str, Path | None],
    owner_approved: bool,
    genome_path: Path,
    history_path: Path,
    active_rules_out: Path,
    baseline_mode: bool,
    as_json: bool,
) -> int:
    # --- 1. Owner gate (explicit) ---
    if not owner_approved:
        return _refuse(
            "promotion requires --owner-approved (switching the active detector is Owner-gated)",
            as_json,
        )

    # --- 2. Read + schema-validate the rules document (fail-closed) ---
    try:
        st = rules_path.stat()
    except OSError as exc:
        return _refuse(f"could not stat rules file: {exc}", as_json)
    if st.st_size > _MAX_RULES_FILE_BYTES:
        return _refuse(f"rules file exceeds size limit: {st.st_size} bytes", as_json)
    try:
        raw_text = rules_path.read_text(encoding="utf-8")
        rules_doc = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _refuse(f"could not read/parse rules file: {exc}", as_json)
    if not isinstance(rules_doc, dict) or validate_rules_schema(rules_doc).get("success") is not True:
        return _refuse("rules document failed schema validation", as_json)

    # --- 3. Pre-load evolution_history BEFORE any writes (fail-closed) ---
    history, history_error = _load_history_strict(history_path)
    if history is None:
        return _refuse(history_error, as_json)

    # --- 4. Re-evaluate the candidate live through the real gate (fail-closed) ---
    corpus_paths = _resolve_corpus_paths(corpus_dir, corpus_overrides)
    report, is_tool_failure = evaluate_structured_rules(
        rules_path,
        genome_path=genome_path,
        baseline_mode=baseline_mode,
        corpus_paths=corpus_paths,
    )
    if is_tool_failure:
        return _refuse(
            f"evaluation tool failure: {report.get('error') or report.get('rejection_reasons')}",
            as_json,
        )
    if report.get("passed_adoption_gate") is not True:
        return _refuse(
            f"candidate did not pass the adoption gate: {report.get('rejection_reasons')}",
            as_json,
        )

    candidate_score = report.get("score")
    if not isinstance(candidate_score, (int, float)) or isinstance(candidate_score, bool):
        return _refuse(f"evaluation returned a non-numeric score: {candidate_score!r}", as_json)
    candidate_score = float(candidate_score)

    # --- 5. Load genome (fail-closed) ---
    try:
        genome_data = json.loads(genome_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _refuse(f"could not read genome file: {exc}", as_json)
    if not isinstance(genome_data, dict):
        return _refuse("genome.json top-level must be an object", as_json)

    # --- 6. Compute the canonical active-rules bytes + hash ---
    active_rules_text = json.dumps(rules_doc, indent=2, sort_keys=True) + "\n"
    rules_hash = hashlib.sha256(active_rules_text.encode("utf-8")).hexdigest()

    new_generation = int(genome_data.get("generation", 0)) + 1
    timestamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

    # --- 7. Writes (active rules, then genome, then history) ---
    _atomic_write(active_rules_out, active_rules_text)

    genome_data["detector_mode"] = "structured_rules"
    genome_data["active_structured_rules_path"] = _relative_active_path(active_rules_out)
    genome_data["current_detector_hash"] = rules_hash
    genome_data["best_score"] = candidate_score
    genome_data["generation"] = new_generation
    genome_data["last_updated"] = timestamp
    _atomic_write(genome_path, json.dumps(genome_data, indent=2) + "\n")

    history.append({
        "generation": new_generation,
        "detector_hash": rules_hash,
        "mode": "structured_rules",
        "score": candidate_score,
        "passed_adoption_gate": True,
        "tp_rate": report.get("tp_rate"),
        "fp_rate": report.get("fp_rate"),
        "fn_rate": report.get("fn_rate"),
        "avg_latency_ms": report.get("avg_latency_ms"),
        "promoted_at": timestamp,
    })
    _atomic_write(history_path, json.dumps(history, indent=2) + "\n")

    result = {
        "success": True,
        "promoted": True,
        "mode": "structured_rules",
        "generation": new_generation,
        "detector_hash": rules_hash,
        "score": candidate_score,
        "active_rules_path": str(active_rules_out),
    }
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"PROMOTED: structured rules → active detector "
            f"(generation {new_generation}, score {candidate_score:.2f}, hash {rules_hash[:12]}…)"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote a structured rules candidate to the active detector."
    )
    parser.add_argument("--rules", required=True, help="Path to the structured rules JSON document.")
    parser.add_argument(
        "--corpus-dir", default=None, dest="corpus_dir", metavar="DIR",
        help="Directory of Owner-supplied corpus files for the re-evaluation gate. "
             "Defaults to the repository data/ corpus.",
    )
    for _tier in _CORPUS_TIER_FILENAMES:
        parser.add_argument(
            f"--{_tier}-path", default=None, dest=f"{_tier}_path", metavar="PATH",
            help=f"Explicit path to the {_tier} corpus file (overrides --corpus-dir for this tier).",
        )
    parser.add_argument(
        "--owner-approved", action="store_true", dest="owner_approved",
        help="Required. Explicit Owner approval to switch the active detector.",
    )
    parser.add_argument("--genome", default=None, metavar="PATH", help="Override genome.json path.")
    parser.add_argument("--history", default=None, metavar="PATH", help="Override evolution_history.json path.")
    parser.add_argument(
        "--active-rules-out", default=None, dest="active_rules_out", metavar="PATH",
        help="Override the active structured rules output path.",
    )
    parser.add_argument(
        "--baseline", action="store_true",
        help="Establish a baseline (bypass score-improvement and parity-guard). Owner approval still required.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else None
    corpus_overrides: dict[str, Path | None] = {
        tier: (Path(getattr(args, f"{tier}_path")) if getattr(args, f"{tier}_path") else None)
        for tier in _CORPUS_TIER_FILENAMES
    }

    return promote_structured_candidate(
        rules_path=Path(args.rules),
        corpus_dir=corpus_dir,
        corpus_overrides=corpus_overrides,
        owner_approved=args.owner_approved,
        genome_path=Path(args.genome) if args.genome else _DEFAULT_GENOME_PATH,
        history_path=Path(args.history) if args.history else _DEFAULT_HISTORY_PATH,
        active_rules_out=Path(args.active_rules_out) if args.active_rules_out else _DEFAULT_ACTIVE_RULES_PATH,
        baseline_mode=args.baseline,
        as_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
