"""scripts/update_readme.py — Update the status block in README.md.

Only the region between:
    <!-- CYBER_IMMUNIZER_STATUS_START -->
    <!-- CYBER_IMMUNIZER_STATUS_END -->
is modified.  Everything outside that block is preserved byte-for-byte.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_README_PATH = _PROJECT_ROOT / "README.md"
_GENOME_PATH = _PROJECT_ROOT / "data" / "genome.json"
_HISTORY_PATH = _PROJECT_ROOT / "data" / "evolution_history.json"
_THREATS_PATH = _PROJECT_ROOT / "data" / "active_threats.json"
_REPORT_PATH = _PROJECT_ROOT / ".cyber_immunizer" / "fitness_report.json"
_LEDGER_PATH = _PROJECT_ROOT / "data" / "api_usage_ledger.json"
_PROJECT_STATE_PATH = _PROJECT_ROOT / "data" / "project_state.json"

# Current-state authority: when data/project_state.json exists, it (not the
# ledger alone) determines the Phase 3 current_phase / next_focus / promote
# wording. See docs/PROJECT_STATE.md. The ledger-derived run-count status
# (Executed / Attempted / Not yet executed) is retained as machine evidence.
_NEXT_ACTION_TEXT = {
    "fix_propose_output_contract_before_new_paid_credit_run": (
        "Fix propose/output-contract root cause before any new paid-credit run"
    ),
    "review_propose_output_contract_fix_before_owner_approved_paid_credit_rerun": (
        "Project Owner review of the propose/output-contract fix (PR #84)"
        " before any owner-approved paid-credit rerun"
    ),
    "prepare_owner_approved_next_s4_rerun_post_g1_gap_closure": (
        "Owner-approved next S4 paid-credit rerun"
        " (G1 repeat-multiplier gap closed; PR #91 merged)"
    ),
    "runs_5_6_artifact_triage_complete_evaluate_rejected_await_owner_decision_on_propose_side_improvement": (
        "Owner decision: runs 5 & 6 reached evaluate but regressed below best=729.34;"
        " decide propose-side improvement before any rerun"
    ),
    "propose_side_baseline_preservation_hardened_await_owner_approved_rerun_review": (
        "Propose-side baseline-preservation hardening implemented (Gemini prompt now"
        " requires preserving all five indicators, the full request surface, and the"
        " non-blocking fallback); awaiting Owner-approved paid-credit rerun review"
    ),
    "owner_audited_candidate_recovery_after_run8_promote_push_failure": (
        "Owner-audited candidate recovery after run 8 promote push failure"
        " — run 8 passed adoption gate; promote was reached; final push failed"
        " (push-race; PR #115 hardened); candidate not promoted to main;"
        " no new paid-credit rerun required as immediate next step"
    ),
}

_STATUS_START = "<!-- CYBER_IMMUNIZER_STATUS_START -->"
_STATUS_END = "<!-- CYBER_IMMUNIZER_STATUS_END -->"


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_bool(value: object, default: bool = False) -> bool:
    """Strict boolean parser that avoids bool("false") == True.

    JSON booleans (Python bool) are returned as-is.
    String "true" / "false" (case-insensitive, stripped) are converted.
    None and any other type fall back to *default*.
    This prevents genome.json string values like "false" from being
    misread as truthy by Python's built-in bool().
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return default


def _bool_str(value: object) -> str:
    """Return 'true' or 'false' string from a bool-like value."""
    return "true" if value else "false"


def _apply_project_state(
    state: object,
    current_phase: str,
    next_focus: str,
    promote_note: str,
) -> tuple[str, str, str]:
    """Override Phase 3 wording from data/project_state.json when present.

    project_state.json is the current-state authority (see docs/PROJECT_STATE.md).
    Only the structured Phase 3 wording is overridden here; the ledger-derived
    run-count status (Executed / Attempted / Not yet executed) is left untouched.
    When *state* is not a usable dict, the inputs are returned unchanged so the
    ledger-derived fallback wording remains in effect.
    """
    if not isinstance(state, dict):
        return current_phase, next_focus, promote_note

    calls = state.get("paid_credit_api_calls")
    patch_not_produced = (
        isinstance(calls, dict)
        and calls.get("valid_mutation_patch_produced") is False
    )
    patch_produced = (
        isinstance(calls, dict)
        and calls.get("valid_mutation_patch_produced") is True
    )
    apply_reached = (
        isinstance(calls, dict)
        and calls.get("apply_reached") is True
    )
    evaluate_reached = (
        isinstance(calls, dict)
        and calls.get("evaluate_reached") is True
    )
    adoption_gate_ever_passed = (
        isinstance(calls, dict)
        and calls.get("adoption_gate_ever_passed") is True
    )
    promote_reached = (
        isinstance(calls, dict)
        and calls.get("promote_reached") is True
    )

    if patch_not_produced:
        current_phase = (
            "Phase 3 — paid-credit API success records exist;"
            " no valid mutation patch produced (propose/output-contract failure)"
        )
    elif patch_produced and apply_reached and not evaluate_reached:
        current_phase = (
            "Phase 3 — valid mutation patch produced (S4 run #47);"
            " apply reached; G1 gap closed (PR #91 merged);"
            " Owner-approved next S4 rerun pending"
        )
    elif patch_produced and apply_reached and evaluate_reached and not adoption_gate_ever_passed:
        current_phase = (
            "Phase 3 — runs 5 & 6 triaged: both reached evaluate,"
            " adoption gate rejected (score regression)"
        )
    elif patch_produced and apply_reached and evaluate_reached and adoption_gate_ever_passed:
        current_phase = (
            "Phase 3 — run 8 passed adoption gate;"
            " promote reached; promote push failed (push-race — PR #115 hardened);"
            " candidate not promoted; owner-audited recovery pending"
        )

    next_action = state.get("next_action")
    if isinstance(next_action, str) and next_action in _NEXT_ACTION_TEXT:
        next_focus = _NEXT_ACTION_TEXT[next_action]

    promo = state.get("promotion")
    if (
        isinstance(promo, dict)
        and _parse_bool(promo.get("promote_approved"), default=False) is False
    ):
        if patch_not_produced:
            promote_note = (
                "false (promotion not approved —"
                " API executed; no valid candidate patch produced)"
            )
        elif patch_produced and apply_reached and not evaluate_reached:
            promote_note = (
                "false (promotion not approved —"
                " apply failed at G1; evaluate/promote not reached)"
            )
        elif patch_produced and apply_reached and evaluate_reached and not adoption_gate_ever_passed:
            promote_note = (
                "false (promotion not approved —"
                " no candidate has passed the adoption gate)"
            )
        elif patch_produced and apply_reached and evaluate_reached and adoption_gate_ever_passed:
            promote_note = (
                "false (promotion not approved —"
                " promote push failed; candidate was not promoted;"
                " owner-audited recovery pending)"
            )

    return current_phase, next_focus, promote_note


def _build_status_block() -> str:
    genome = _load_json(_GENOME_PATH) or {}
    history = _load_json(_HISTORY_PATH) or []
    threats = _load_json(_THREATS_PATH) or []
    ledger = _load_json(_LEDGER_PATH)
    project_state = _load_json(_PROJECT_STATE_PATH)
    fitness: dict | None = None

    raw_report = _load_json(_REPORT_PATH)
    if isinstance(raw_report, dict):
        fitness = raw_report.get("fitness_report") or raw_report

    # --- Legacy fields (preserved) ---
    generation = genome.get("generation", 0)
    best_score = genome.get("best_score", "N/A")
    detector_hash = genome.get("current_detector_hash", "unknown")
    last_updated = genome.get("last_updated", "unknown")

    adoption_status = "⏳ Baseline (not yet evaluated)"
    if history:
        last = history[-1]
        if last.get("passed_adoption_gate"):
            adoption_status = f"✅ Passed (generation {last.get('generation', '?')})"
        else:
            reasons = last.get("rejection_reasons", [])
            adoption_status = f"❌ Failed — {reasons[0]!r}" if reasons else "❌ Failed"

    total_cases = "N/A"
    tp = fp = tn = fn = "N/A"
    if fitness:
        total_cases = fitness.get("total_cases", "N/A")
        tp = fitness.get("true_positive", "N/A")
        fp = fitness.get("false_positive", "N/A")
        tn = fitness.get("true_negative", "N/A")
        fn = fitness.get("false_negative", "N/A")

    threat_ids = " ".join(
        f"`{t.get('id', '?')}`" for t in threats
    ) if threats else "_none_"

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # --- Fields read from genome.json ---
    # Use _parse_bool instead of bool() to correctly handle string "false"
    # (Python's bool("false") == True, which would produce a wrong dashboard)
    live_model_enabled: bool = _parse_bool(genome.get("live_model_enabled"), default=False)
    api_mode: str = genome.get("api_mode", "N/A")
    model_provider: str = genome.get("model_provider", "N/A")
    model_name: str = genome.get("model_name", "N/A")
    fallback_model_name: str = genome.get("fallback_model_name", "N/A")
    max_model_requests: object = genome.get("max_model_requests_per_run", "N/A")
    max_commits: object = genome.get("max_commits_per_run", "N/A")
    monthly_budget: object = genome.get("monthly_api_budget_usd", "N/A")
    daily_budget: object = genome.get("daily_api_budget_usd", "N/A")
    send_repo_text: bool = _parse_bool(genome.get("send_repository_full_text"), default=False)
    send_raw_payloads: bool = _parse_bool(genome.get("send_raw_payloads"), default=False)
    send_secrets: bool = _parse_bool(genome.get("send_secrets"), default=False)

    # --- Phase determination ---
    # Phase 3 when live_model_enabled=true; Phase 2 otherwise.
    if live_model_enabled:
        # Check ledger for paid-credit attempts with the current primary model.
        # Both success=True and success=False records count as "attempted" — a
        # failed run still reached the API and must not be shown as "Not yet executed".
        # Only records with api_mode=="gemini_paid_credit" count; other modes
        # (noop, offline-sample) do not constitute a paid-credit attempt.
        primary_attempts: list[dict] = []
        if isinstance(ledger, list):
            primary_attempts = [
                e for e in ledger
                if isinstance(e, dict)
                and e.get("model") == model_name
                and e.get("api_mode") == "gemini_paid_credit"
            ]
        if not primary_attempts:
            p3_run_status = "Not yet executed"
            current_phase = "Phase 3 — paid-credit path ready; first paid-credit run not yet executed"
            next_focus = (
                "Execute first paid-credit run: workflow_dispatch → gemini-paid-credit,"
                " promote_approved=false"
            )
            promote_note = "false (workflow gate — Project Owner approval required)"
        else:
            n_total = len(primary_attempts)
            n_success = sum(1 for e in primary_attempts if e.get("success") is True)
            if n_success > 0:
                p3_run_status = f"Executed ({n_success} successful / {n_total} attempt(s))"
                current_phase = (
                    "Phase 3 — paid-credit API call success records exist;"
                    " post-run result review pending"
                )
                next_focus = (
                    "Review existing paid-credit run results:"
                    " ledger / candidate / apply / evaluate / promotion decision"
                )
                promote_note = (
                    "false (promotion not approved —"
                    " API call already executed; post-run review pending)"
                )
            else:
                p3_run_status = (
                    f"Attempted but failed ({n_total} attempt(s))"
                    " — inspect ledger before rerun"
                )
                current_phase = (
                    "Phase 3 — paid-credit run attempted (no successful calls);"
                    " inspect ledger"
                )
                next_focus = "Review ledger for failed run; diagnose cause before rerun"
                promote_note = "false (workflow gate — Project Owner approval required)"
        # Current-state SSOT override (data/project_state.json wins for wording).
        current_phase, next_focus, promote_note = _apply_project_state(
            project_state, current_phase, next_focus, promote_note
        )
        phase_rows: list[str] = [
            f"| Phase 3 Activation | Complete (PR #58-#62) |",
            f"| Phase 3 Paid-Credit API Calls | {p3_run_status} |",
            f"| Gemini Primary Model | {model_name} |",
            f"| Gemini Fallback Model | {fallback_model_name} |",
            f"| promote_approved | {promote_note} |",
            f"| Next Focus | {next_focus} |",
        ]
    else:
        current_phase = "Phase 2 — API-disconnected operations"
        phase_rows = [
            f"| API Connection | Not connected |",
        ]

    lines = [
        _STATUS_START,
        "## 🧬 Cyber-Immunizer Status",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Current Phase | {current_phase} |",
        *phase_rows,
        f"| live_model_enabled | {_bool_str(live_model_enabled)} |",
        f"| API Mode | {api_mode} |",
        f"| Model Provider | {model_provider} |",
        f"| Max Model Requests / Run | {max_model_requests} |",
        f"| Max Commits / Run | {max_commits} |",
        f"| Monthly API Budget | {monthly_budget} USD |",
        f"| Daily API Budget | {daily_budget} USD |",
        f"| Send Full Repository Text | {_bool_str(send_repo_text)} |",
        f"| Send Raw Payloads | {_bool_str(send_raw_payloads)} |",
        f"| Send Secrets | {_bool_str(send_secrets)} |",
        "| Schedule Mode | noop only |",
        "| CI Status | Manual check required / see Actions |",
        "| Noop Path | Verified |",
        "| Offline Sample Path | Verified |",
        "| Paid-Credit Preflight | Fail-closed when GEMINI_API_KEY missing |",
        "| Phase 3 Gate | Project Owner explicit decision required |",
        f"| Generation | {generation} |",
        f"| Best Score | {best_score} |",
        f"| Detector Hash | `{detector_hash[:16]}…` |",
        f"| Last Updated | {last_updated} |",
        f"| Total Test Cases | {total_cases} |",
        f"| TP / FP / TN / FN | {tp} / {fp} / {tn} / {fn} |",
        *(
            []
            if fitness is not None
            else ["| Fitness Report | Not available — run baseline fitness to populate TP/FP/TN/FN |"]
        ),
        f"| Adoption Gate | {adoption_status} |",
        f"| Active Threat IDs | {threat_ids} |",
        f"| Status Block Updated | {now} |",
        "",
        _STATUS_END,
    ]
    return "\n".join(lines)


def update_readme(readme_path: Path | None = None) -> bool:
    readme_path = readme_path or _README_PATH
    if not readme_path.exists():
        print(f"README not found: {readme_path}", file=sys.stderr)
        return False

    content = readme_path.read_text(encoding="utf-8")

    start_idx = content.find(_STATUS_START)
    end_idx = content.find(_STATUS_END)

    new_block = _build_status_block()

    if start_idx == -1 or end_idx == -1:
        # Append block at end
        new_content = content.rstrip("\n") + "\n\n" + new_block + "\n"
    else:
        # Replace existing block
        new_content = (
            content[:start_idx]
            + new_block
            + content[end_idx + len(_STATUS_END):]
        )

    readme_path.write_text(new_content, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Update README status block")
    parser.add_argument(
        "--readme",
        default=None,
        help="Override path to README.md (for tests)",
    )
    args = parser.parse_args(argv)

    readme_path = Path(args.readme) if args.readme else None
    success = update_readme(readme_path)
    if success:
        print("README status block updated.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
