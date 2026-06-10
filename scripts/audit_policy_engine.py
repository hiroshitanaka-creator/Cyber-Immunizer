"""scripts/audit_policy_engine.py — Policy Engine for the machine audit gate.

Evaluates an Audit Packet (built by ``scripts/build_audit_packet.py``) against
fixed, fail-closed policy rules and computes whether an APPROVE verdict is even
allowed. The LLM auditor does not decide this; it may only emit APPROVE when
this engine exits 0.

Trust model:

* Only ``machine_facts`` are trusted directly (they were collected by script).
* ``judgment_inputs`` are LLM claims. A claim counts ONLY when ``claim`` is
  true, ``claimed_by`` is set, and the referenced ``evidence_report`` passes
  ``scripts/validate_audit_evidence.py`` re-run by THIS engine at evaluation
  time. A bare ``"claim": true`` with no verifiable evidence is a HOLD reason,
  not an approval input — self-reports cannot be laundered through the packet.
* head-SHA freshness is verified against ``--current-head-sha``; omitting the
  flag is itself a HOLD reason (fail closed), because an unverified packet may
  describe an outdated head.

Usage:
    python scripts/audit_policy_engine.py --packet packet.json \
        --current-head-sha <sha> [--base-ref origin/main] \
        [--allow-frozen scripts/] [--root <repo>] [--json]

Exit codes:
    0  APPROVE allowed (machine_verdict=APPROVE_ALLOWED)
    1  HOLD (machine_verdict=HOLD; see reasons)
    2  Packet invalid (machine_verdict=PACKET_INVALID; audit cannot proceed)

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.validate_audit_evidence import validate_report  # noqa: E402

PACKET_SCHEMA_VERSION = 1

_JUDGMENT_KEYS = ("task_conditions_met", "scope_semantics_ok", "code_findings_resolved")


# ---------------------------------------------------------------------------
# Structural validation (stdlib mirror of schemas/gpt_audit_packet.schema.json)
# ---------------------------------------------------------------------------


def _get(packet: dict, dotted: str):
    node = packet
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


_REQUIRED_PATHS: list[tuple[str, type | tuple[type, ...]]] = [
    ("packet_schema_version", int),
    ("generated_by", str),
    ("source", str),
    ("machine_facts.pr.number", int),
    ("machine_facts.pr.state", str),
    ("machine_facts.pr.merged", bool),
    ("machine_facts.pr.draft", bool),
    ("machine_facts.pr.base_ref", str),
    ("machine_facts.pr.base_sha", str),
    ("machine_facts.pr.head_ref", str),
    ("machine_facts.pr.head_sha", str),
    ("machine_facts.pr.changed_files", list),
    ("machine_facts.ci.classification", str),
    ("machine_facts.ci.head_sha", str),
    ("machine_facts.ci.check_runs", list),
    ("machine_facts.review_threads.total", int),
    ("machine_facts.review_threads.unresolved", int),
    ("machine_facts.review_threads.unresolved_p1_p2", int),
    ("machine_facts.review_threads.threads", list),
    ("machine_facts.frozen_paths.frozen_prefixes", list),
    ("machine_facts.frozen_paths.touched", list),
    ("machine_facts.ssot.consistent", bool),
    ("judgment_inputs", dict),
]


def validate_packet_structure(packet: dict) -> list[str]:
    errors: list[str] = []
    for path, expected in _REQUIRED_PATHS:
        value = _get(packet, path)
        if value is None:
            errors.append(f"packet: missing required field {path!r}")
            continue
        # bool is a subclass of int — require exact bool where bool is expected
        if expected is int and isinstance(value, bool):
            errors.append(f"packet: field {path!r} must be int, got bool")
        elif not isinstance(value, expected):
            errors.append(f"packet: field {path!r} has wrong type {type(value).__name__}")
    if packet.get("packet_schema_version") != PACKET_SCHEMA_VERSION:
        errors.append(
            f"packet: packet_schema_version must be {PACKET_SCHEMA_VERSION}, "
            f"got {packet.get('packet_schema_version')!r}"
        )
    judgment = packet.get("judgment_inputs")
    if isinstance(judgment, dict):
        for key in _JUDGMENT_KEYS:
            if key not in judgment:
                errors.append(f"packet: judgment_inputs missing key {key!r}")
        for key in judgment:
            if key not in _JUDGMENT_KEYS:
                errors.append(f"packet: judgment_inputs has unknown key {key!r}")
    return errors


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


def evaluate_machine_facts(
    packet: dict,
    current_head_sha: str | None,
    allow_frozen: list[str],
) -> list[str]:
    """Apply the fixed APPROVE preconditions to machine_facts. Returns HOLD reasons."""
    reasons: list[str] = []
    facts = packet["machine_facts"]
    pr = facts["pr"]

    if pr["state"] != "open":
        reasons.append(f"pr_state={pr['state']} (must be open)")
    if pr["merged"]:
        reasons.append("pr_already_merged")
    if pr["draft"]:
        reasons.append("pr_is_draft")

    if current_head_sha is None:
        reasons.append(
            "head_sha_freshness_unverified (--current-head-sha not supplied; fail closed)"
        )
    elif current_head_sha != pr["head_sha"]:
        reasons.append(
            f"head_sha_stale (packet={pr['head_sha']}, current={current_head_sha})"
        )

    ci = facts["ci"]
    if ci["classification"] != "SUCCESS":
        reasons.append(f"ci_status={ci['classification']} (must be SUCCESS)")
    if ci["head_sha"] != pr["head_sha"]:
        reasons.append("ci_head_sha_mismatch (CI result is not for the packet head SHA)")

    threads = facts["review_threads"]
    if threads["unresolved"] > 0:
        reasons.append(f"unresolved_threads={threads['unresolved']} (must be 0)")
    if threads["unresolved_p1_p2"] > 0:
        reasons.append(f"unresolved_p1_p2={threads['unresolved_p1_p2']} (must be 0)")

    blocked = [
        p
        for p in facts["frozen_paths"]["touched"]
        if not any(p.startswith(pfx) for pfx in allow_frozen)
    ]
    if blocked:
        reasons.append(
            "frozen_paths_touched="
            + ",".join(blocked)
            + " (requires explicit Project Owner allowance via --allow-frozen)"
        )

    if not facts["ssot"]["consistent"]:
        reasons.append("ssot_inconsistent (data/project_state.json vs docs/PROJECT_STATE.md)")

    return reasons


def evaluate_judgment_inputs(
    packet: dict,
    root: Path,
    base_ref: str | None,
) -> list[str]:
    """Honor a judgment claim only if its evidence report verifies. Returns HOLD reasons.

    The engine re-runs scripts/validate_audit_evidence.py itself; it never
    trusts a recorded "validation passed" assertion.
    """
    reasons: list[str] = []
    verified_reports: dict[str, dict] = {}
    for key in _JUDGMENT_KEYS:
        entry = packet["judgment_inputs"].get(key) or {}
        claim = entry.get("claim")
        claimed_by = entry.get("claimed_by")
        report = entry.get("evidence_report")
        if claim is not True:
            reasons.append(f"judgment:{key} claim is {claim!r} (must be true with evidence)")
            continue
        if not claimed_by:
            reasons.append(f"judgment:{key} has no claimed_by")
            continue
        if not report:
            reasons.append(
                f"judgment:{key} claim=true but no evidence_report — "
                "bare self-report is not acceptable"
            )
            continue
        report_path = Path(report)
        if not report_path.is_absolute():
            report_path = root / report_path
        if report not in verified_reports:
            verified_reports[report] = validate_report(report_path, root, base_ref)
        result = verified_reports[report]
        if not result["valid"]:
            head = "; ".join(result["errors"][:3])
            reasons.append(
                f"judgment:{key} evidence_report failed validation "
                f"({len(result['errors'])} error(s): {head})"
            )
    return reasons


def evaluate(
    packet: dict,
    root: Path,
    current_head_sha: str | None = None,
    base_ref: str | None = None,
    allow_frozen: list[str] | None = None,
) -> dict:
    """Full evaluation. Returns the machine verdict document."""
    structural = validate_packet_structure(packet)
    if structural:
        return {
            "machine_verdict": "PACKET_INVALID",
            "approve_allowed": False,
            "reasons": structural,
        }
    reasons = evaluate_machine_facts(packet, current_head_sha, allow_frozen or [])
    reasons += evaluate_judgment_inputs(packet, root, base_ref)
    return {
        "machine_verdict": "APPROVE_ALLOWED" if not reasons else "HOLD",
        "approve_allowed": not reasons,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer audit policy engine")
    parser.add_argument("--packet", required=True, help="Path to the audit packet JSON")
    parser.add_argument(
        "--current-head-sha",
        default=None,
        help="Current PR head SHA for the freshness lock (omitting it is a HOLD reason)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Base git ref passed through to evidence-report validation",
    )
    parser.add_argument(
        "--allow-frozen",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Frozen path prefix explicitly allowed by the Project Owner (repeatable)",
    )
    parser.add_argument("--root", default=str(_PROJECT_ROOT), help="Repository root")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "machine_verdict": "PACKET_INVALID",
            "approve_allowed": False,
            "reasons": [f"cannot read packet: {exc}"],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2

    result = evaluate(
        packet,
        Path(args.root),
        current_head_sha=args.current_head_sha,
        base_ref=args.base_ref,
        allow_frozen=args.allow_frozen,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"machine_verdict: {result['machine_verdict']}")
        for r in result["reasons"]:
            print(f"  - {r}")

    if result["machine_verdict"] == "PACKET_INVALID":
        return 2
    return 0 if result["approve_allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
