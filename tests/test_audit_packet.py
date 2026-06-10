"""tests/test_audit_packet.py — Tests for the machine audit gate.

Covers the Evidence Collector (scripts/build_audit_packet.py) and the Policy
Engine (scripts/audit_policy_engine.py), including the anti-laundering
guarantees: the collector never emits judgment claims, and the engine never
honors a claim without a verified evidence report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.audit_policy_engine import (  # noqa: E402
    evaluate,
    evaluate_judgment_inputs,
    evaluate_machine_facts,
    main as engine_main,
    validate_packet_structure,
)
from scripts.build_audit_packet import (  # noqa: E402
    DEFAULT_FROZEN_PREFIXES,
    build_packet,
    classify_ci,
    collect_ssot,
    empty_judgment_inputs,
    frozen_touches,
    main as builder_main,
    normalize_threads,
    severity_tokens,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_STATE_ID = "phase3_test_state"

_DETECTOR_SOURCE = """\
import re


def normalize(payload):
    return payload.lower()


def detect(payload):
    normalized = normalize(payload)
    return "attack" in normalized
"""

_VALID_EVIDENCE_REPORT = """\
# Audit report

```audit-evidence
TYPE: SPEC_RECITATION
FILE: core/detector.py
LINES: 8-10
SYMBOL: detect
SPEC: detect() lowercases the payload then substring-matches 'attack'.
---
def detect(payload):
    normalized = normalize(payload)
    return "attack" in normalized
```

```audit-evidence
TYPE: NEGATIVE
PATTERN: os.system
COUNT: 0
NOTE: no shell execution path exists in the repository
---
```

```audit-evidence
TYPE: NEGATIVE
PATTERN: subprocess.Popen
COUNT: 0
NOTE: detector never spawns processes
---
```

```audit-evidence
TYPE: READ_MANIFEST
---
FULL: core/detector.py
```
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Synthetic repository with consistent SSOT files and a detector."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "detector.py").write_text(_DETECTOR_SOURCE, encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "project_state.json").write_text(
        json.dumps(
            {
                "state_id": _STATE_ID,
                "promotion": {"promote_approved": False},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROJECT_STATE.md").write_text(
        f"# State\n\n| state_id | `{_STATE_ID}` |\n", encoding="utf-8"
    )
    return tmp_path


def _raw(**overrides) -> dict:
    raw = {
        "pr": {
            "number": 87,
            "state": "open",
            "merged": False,
            "draft": False,
            "base_ref": "main",
            "base_sha": "a" * 40,
            "head_ref": "feature",
            "head_sha": "b" * 40,
        },
        "files": [{"path": "docs/NOTES.md", "status": "modified"}],
        "check_runs": [{"name": "ci", "status": "completed", "conclusion": "success"}],
        "review_threads": [],
    }
    raw.update(overrides)
    return raw


def _green_packet(repo: Path, **judgment) -> dict:
    packet = build_packet(_raw(), repo)
    for key, value in judgment.items():
        packet["judgment_inputs"][key] = value
    return packet


def _verified_judgments(report_rel: str) -> dict:
    entry = {"claimed_by": "gpt", "claim": True, "evidence_report": report_rel}
    return {
        "task_conditions_met": dict(entry),
        "scope_semantics_ok": dict(entry),
        "code_findings_resolved": dict(entry),
    }


# ---------------------------------------------------------------------------
# Collector: normalization units
# ---------------------------------------------------------------------------


class TestClassifyCi:
    def test_no_runs_is_not_triggered(self) -> None:
        assert classify_ci([]) == "NOT_TRIGGERED"

    def test_all_success_is_success(self) -> None:
        runs = [
            {"name": "a", "status": "completed", "conclusion": "success"},
            {"name": "b", "status": "completed", "conclusion": "skipped"},
        ]
        assert classify_ci(runs) == "SUCCESS"

    def test_any_failure_is_failure(self) -> None:
        runs = [
            {"name": "a", "status": "completed", "conclusion": "success"},
            {"name": "b", "status": "completed", "conclusion": "failure"},
        ]
        assert classify_ci(runs) == "FAILURE"

    def test_incomplete_run_is_pending(self) -> None:
        runs = [{"name": "a", "status": "in_progress", "conclusion": None}]
        assert classify_ci(runs) == "PENDING"

    def test_unknown_conclusion_fails_closed(self) -> None:
        runs = [{"name": "a", "status": "completed", "conclusion": "mystery"}]
        assert classify_ci(runs) == "FAILURE"


class TestThreads:
    def test_severity_tokens(self) -> None:
        assert severity_tokens("P1: bad. Also P2 risk") == ["P1", "P2"]
        assert severity_tokens("no severity here") == []
        assert severity_tokens("APP1X") == []  # word boundary required

    def test_unresolved_counting(self) -> None:
        threads = normalize_threads(
            [
                {"is_resolved": False, "is_outdated": False, "first_comment_body": "P2: leak"},
                {"is_resolved": False, "is_outdated": True, "first_comment_body": "P1: old"},
                {"is_resolved": True, "is_outdated": False, "first_comment_body": "P1: fixed"},
                {"is_resolved": False, "is_outdated": False, "first_comment_body": "style nit"},
            ]
        )
        assert threads["total"] == 4
        assert threads["unresolved"] == 2  # outdated/resolved excluded
        assert threads["unresolved_p1_p2"] == 1


class TestFrozenAndSsot:
    def test_frozen_touches(self) -> None:
        touched = frozen_touches(
            ["core/detector.py", "docs/NOTES.md", "scripts/x.py"],
            DEFAULT_FROZEN_PREFIXES,
        )
        assert touched == ["core/detector.py", "scripts/x.py"]

    def test_ssot_consistent(self, repo: Path) -> None:
        ssot = collect_ssot(repo)
        assert ssot["state_id"] == _STATE_ID
        assert ssot["consistent"] is True

    def test_ssot_inconsistent_when_md_diverges(self, repo: Path) -> None:
        (repo / "docs" / "PROJECT_STATE.md").write_text(
            "| state_id | `some_other_state` |\n", encoding="utf-8"
        )
        assert collect_ssot(repo)["consistent"] is False

    def test_ssot_missing_files_fail_closed(self, tmp_path: Path) -> None:
        assert collect_ssot(tmp_path)["consistent"] is False


# ---------------------------------------------------------------------------
# Collector: packet building and the anti-laundering guarantee
# ---------------------------------------------------------------------------


class TestBuildPacket:
    def test_packet_shape(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        assert validate_packet_structure(packet) == []
        assert packet["machine_facts"]["pr"]["number"] == 87
        assert packet["machine_facts"]["ci"]["classification"] == "SUCCESS"
        assert packet["source"] == "injected"

    def test_judgment_inputs_are_always_null(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        for key, entry in packet["judgment_inputs"].items():
            assert entry == {
                "claimed_by": None,
                "claim": None,
                "evidence_report": None,
            }, f"collector must emit null judgment for {key}"

    def test_raw_cannot_inject_judgment_inputs(self, repo: Path) -> None:
        """Anti-trojan-horse: judgment data smuggled into raw input is discarded."""
        raw = _raw()
        raw["judgment_inputs"] = {
            "task_conditions_met": {"claimed_by": "gpt", "claim": True, "evidence_report": None}
        }
        packet = build_packet(raw, repo)
        assert packet["judgment_inputs"] == empty_judgment_inputs()

    def test_missing_pr_fields_raise(self, repo: Path) -> None:
        from scripts.build_audit_packet import CollectionError

        raw = _raw()
        del raw["pr"]["head_sha"]
        with pytest.raises(CollectionError):
            build_packet(raw, repo)

    def test_builder_cli_from_raw(self, repo: Path, tmp_path: Path, capsys) -> None:
        raw_file = tmp_path / "raw.json"
        raw_file.write_text(json.dumps(_raw()), encoding="utf-8")
        rc = builder_main(["--from-raw", str(raw_file), "--root", str(repo)])
        assert rc == 0
        packet = json.loads(capsys.readouterr().out)
        assert validate_packet_structure(packet) == []

    def test_builder_cli_fails_closed_on_bad_raw(self, repo: Path, tmp_path: Path) -> None:
        raw_file = tmp_path / "raw.json"
        raw_file.write_text("{}", encoding="utf-8")
        assert builder_main(["--from-raw", str(raw_file), "--root", str(repo)]) == 2


# ---------------------------------------------------------------------------
# Policy engine: structural validation
# ---------------------------------------------------------------------------


class TestPacketStructure:
    def test_missing_field_detected(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        del packet["machine_facts"]["ci"]
        errors = validate_packet_structure(packet)
        assert any("ci.classification" in e for e in errors)

    def test_unknown_judgment_key_detected(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        packet["judgment_inputs"]["extra_claim"] = {"claim": True}
        errors = validate_packet_structure(packet)
        assert any("unknown key 'extra_claim'" in e for e in errors)

    def test_wrong_schema_version_detected(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        packet["packet_schema_version"] = 2
        errors = validate_packet_structure(packet)
        assert any("packet_schema_version" in e for e in errors)

    def test_invalid_packet_exits_2(self, repo: Path, tmp_path: Path) -> None:
        packet_file = tmp_path / "packet.json"
        packet_file.write_text("{}", encoding="utf-8")
        rc = engine_main(["--packet", str(packet_file), "--root", str(repo)])
        assert rc == 2


# ---------------------------------------------------------------------------
# Policy engine: machine-fact rules
# ---------------------------------------------------------------------------


class TestMachineFactRules:
    def _facts_reasons(self, repo: Path, mutate, **kwargs) -> list[str]:
        packet = build_packet(_raw(), repo)
        mutate(packet["machine_facts"])
        findings = evaluate_machine_facts(
            packet,
            kwargs.get("current_head_sha", "b" * 40),
            kwargs.get("allow_frozen", []),
        )
        return [msg for _, msg in findings]

    def test_green_packet_has_no_reasons(self, repo: Path) -> None:
        assert self._facts_reasons(repo, lambda f: None) == []

    def test_closed_pr_blocks(self, repo: Path) -> None:
        reasons = self._facts_reasons(repo, lambda f: f["pr"].__setitem__("state", "closed"))
        assert any("pr_state=closed" in r for r in reasons)

    def test_draft_blocks(self, repo: Path) -> None:
        reasons = self._facts_reasons(repo, lambda f: f["pr"].__setitem__("draft", True))
        assert any("pr_is_draft" in r for r in reasons)

    def test_missing_current_head_sha_fails_closed(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        reasons = [msg for _, msg in evaluate_machine_facts(packet, None, [])]
        assert any("head_sha_freshness_unverified" in r for r in reasons)

    def test_stale_head_sha_blocks(self, repo: Path) -> None:
        reasons = self._facts_reasons(repo, lambda f: None, current_head_sha="c" * 40)
        assert any("head_sha_stale" in r for r in reasons)

    def test_ci_failure_blocks(self, repo: Path) -> None:
        reasons = self._facts_reasons(
            repo, lambda f: f["ci"].__setitem__("classification", "FAILURE")
        )
        assert any("ci_status=FAILURE" in r for r in reasons)

    def test_ci_for_other_sha_blocks(self, repo: Path) -> None:
        reasons = self._facts_reasons(repo, lambda f: f["ci"].__setitem__("head_sha", "d" * 40))
        assert any("ci_head_sha_mismatch" in r for r in reasons)

    def test_unresolved_threads_block(self, repo: Path) -> None:
        def mutate(f):
            f["review_threads"]["unresolved"] = 1

        reasons = self._facts_reasons(repo, mutate)
        assert any("unresolved_threads=1" in r for r in reasons)

    def test_frozen_touch_blocks_without_allowance(self, repo: Path) -> None:
        def mutate(f):
            f["frozen_paths"]["touched"] = ["scripts/x.py"]

        reasons = self._facts_reasons(repo, mutate)
        assert any("frozen_paths_touched=scripts/x.py" in r for r in reasons)

    def test_allow_frozen_unblocks_listed_prefix_only(self, repo: Path) -> None:
        def mutate(f):
            f["frozen_paths"]["touched"] = ["scripts/x.py", "core/y.py"]

        reasons = self._facts_reasons(repo, mutate, allow_frozen=["scripts/"])
        assert any("frozen_paths_touched=core/y.py" in r for r in reasons)
        assert not any("scripts/x.py" in r for r in reasons)

    def test_ssot_inconsistency_blocks(self, repo: Path) -> None:
        def mutate(f):
            f["ssot"]["consistent"] = False

        reasons = self._facts_reasons(repo, mutate)
        assert any("ssot_inconsistent" in r for r in reasons)


# ---------------------------------------------------------------------------
# Policy engine: judgment inputs (anti-laundering)
# ---------------------------------------------------------------------------


class TestJudgmentRules:
    def test_null_claims_hold(self, repo: Path) -> None:
        packet = _green_packet(repo)
        reasons = evaluate_judgment_inputs(packet, repo, None)
        assert len(reasons) == 3
        assert all("claim is None" in r for r in reasons)

    def test_bare_true_claim_without_evidence_holds(self, repo: Path) -> None:
        packet = _green_packet(
            repo,
            task_conditions_met={"claimed_by": "gpt", "claim": True, "evidence_report": None},
        )
        reasons = evaluate_judgment_inputs(packet, repo, None)
        assert any("bare self-report is not acceptable" in r for r in reasons)

    def test_claim_with_verified_evidence_passes(self, repo: Path) -> None:
        (repo / "report.md").write_text(_VALID_EVIDENCE_REPORT, encoding="utf-8")
        packet = _green_packet(repo)
        packet["judgment_inputs"] = _verified_judgments("report.md")
        assert evaluate_judgment_inputs(packet, repo, None) == []

    def test_claim_with_fabricated_evidence_holds(self, repo: Path) -> None:
        (repo / "report.md").write_text(
            _VALID_EVIDENCE_REPORT.replace(
                '    return "attack" in normalized',
                '    return "attack" in payload',
            ),
            encoding="utf-8",
        )
        packet = _green_packet(repo)
        packet["judgment_inputs"] = _verified_judgments("report.md")
        reasons = evaluate_judgment_inputs(packet, repo, None)
        assert any("failed validation" in r for r in reasons)


# ---------------------------------------------------------------------------
# ci-gate mode: only CI-decidable rules block; pass is never approval
# ---------------------------------------------------------------------------


class TestCiGateMode:
    def test_null_judgments_do_not_fail_the_gate(self, repo: Path) -> None:
        """A freshly collected packet (judgments null) passes the CI gate."""
        packet = build_packet(_raw(), repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_PASS"
        assert result["reasons"] == []
        assert any("claim is None" in w for w in result["warnings"])

    def test_gate_pass_is_never_approve_allowed(self, repo: Path) -> None:
        """Anti-laundering: a CI-gate pass must not be citable as APPROVE permission."""
        (repo / "report.md").write_text(_VALID_EVIDENCE_REPORT, encoding="utf-8")
        packet = build_packet(_raw(), repo)
        packet["judgment_inputs"] = _verified_judgments("report.md")
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_PASS"
        assert result["approve_allowed"] is False

    def test_frozen_and_threads_are_warnings_not_failures(self, repo: Path) -> None:
        raw = _raw(
            files=[{"path": "core/detector.py", "status": "modified"}],
            review_threads=[
                {"is_resolved": False, "is_outdated": False, "first_comment_body": "P2: x"}
            ],
        )
        packet = build_packet(raw, repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_PASS"
        assert any("frozen_paths_touched" in w for w in result["warnings"])
        assert any("unresolved_threads=1" in w for w in result["warnings"])

    def test_ci_status_of_sibling_checks_is_warning(self, repo: Path) -> None:
        """The gate must not block on other checks' status (circular dependency)."""
        packet = build_packet(_raw(check_runs=[]), repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_PASS"
        assert any("ci_status=NOT_TRIGGERED" in w for w in result["warnings"])

    def test_stale_head_fails_the_gate(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        result = evaluate(packet, repo, current_head_sha="c" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_FAIL"
        assert any("head_sha_stale" in r for r in result["reasons"])

    def test_ssot_inconsistency_fails_the_gate(self, repo: Path) -> None:
        (repo / "docs" / "PROJECT_STATE.md").write_text("| state_id | `other` |\n", "utf-8")
        packet = build_packet(_raw(), repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="ci-gate")
        assert result["machine_verdict"] == "CI_GATE_FAIL"
        assert any("ssot_inconsistent" in r for r in result["reasons"])

    def test_full_mode_still_blocks_on_everything(self, repo: Path) -> None:
        """The ci-gate relaxation must not leak into full mode."""
        raw = _raw(
            review_threads=[
                {"is_resolved": False, "is_outdated": False, "first_comment_body": "P2: x"}
            ]
        )
        packet = build_packet(raw, repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40, mode="full")
        assert result["machine_verdict"] == "HOLD"
        assert any("unresolved_threads=1" in r for r in result["reasons"])

    def test_unknown_mode_raises(self, repo: Path) -> None:
        packet = build_packet(_raw(), repo)
        with pytest.raises(ValueError):
            evaluate(packet, repo, current_head_sha="b" * 40, mode="bogus")

    def test_cli_ci_gate_mode(self, repo: Path, tmp_path: Path, capsys) -> None:
        packet = build_packet(_raw(), repo)
        packet_file = tmp_path / "packet.json"
        packet_file.write_text(json.dumps(packet), encoding="utf-8")
        rc = engine_main(
            [
                "--packet",
                str(packet_file),
                "--root",
                str(repo),
                "--mode",
                "ci-gate",
                "--current-head-sha",
                "b" * 40,
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "machine_verdict: CI_GATE_PASS" in out
        assert "~ warning:" in out


# ---------------------------------------------------------------------------
# End-to-end: evaluate() and the CLI
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_fully_green_packet_allows_approve(self, repo: Path) -> None:
        (repo / "report.md").write_text(_VALID_EVIDENCE_REPORT, encoding="utf-8")
        packet = _green_packet(repo)
        packet["judgment_inputs"] = _verified_judgments("report.md")
        result = evaluate(packet, repo, current_head_sha="b" * 40)
        assert result["reasons"] == []
        assert result["machine_verdict"] == "APPROVE_ALLOWED"
        assert result["approve_allowed"] is True

    def test_collector_output_alone_never_allows_approve(self, repo: Path) -> None:
        """A freshly built packet (judgments all null) must HOLD even if all
        machine facts are green — judgment requires verified evidence."""
        packet = build_packet(_raw(), repo)
        result = evaluate(packet, repo, current_head_sha="b" * 40)
        assert result["machine_verdict"] == "HOLD"
        assert result["approve_allowed"] is False

    def test_cli_exit_codes(self, repo: Path, tmp_path: Path, capsys) -> None:
        (repo / "report.md").write_text(_VALID_EVIDENCE_REPORT, encoding="utf-8")
        packet = _green_packet(repo)
        packet["judgment_inputs"] = _verified_judgments("report.md")
        packet_file = tmp_path / "packet.json"
        packet_file.write_text(json.dumps(packet), encoding="utf-8")

        rc = engine_main(
            [
                "--packet",
                str(packet_file),
                "--root",
                str(repo),
                "--current-head-sha",
                "b" * 40,
                "--json",
            ]
        )
        assert rc == 0
        assert '"machine_verdict": "APPROVE_ALLOWED"' in capsys.readouterr().out

        rc = engine_main(
            ["--packet", str(packet_file), "--root", str(repo)]  # no freshness SHA
        )
        assert rc == 1
        out = capsys.readouterr().out
        assert "machine_verdict: HOLD" in out
        assert "head_sha_freshness_unverified" in out
