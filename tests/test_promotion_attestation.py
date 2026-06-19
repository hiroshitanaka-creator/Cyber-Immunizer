"""Semantic tests for the evaluation-to-promotion attestation gate."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scripts.candidate_contract import DOCKER_IMAGE, DOCKER_IMAGE_REPO_DIGEST, DOCKER_IMAGE_TAG
from scripts.promotion_attestation import build_attestation, verify_attestation

DIGEST = DOCKER_IMAGE_REPO_DIGEST
EVALUATED_SHA = "e" * 40
BASE_MAIN_SHA = "b" * 40


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_allowlist(tmp_path: Path, *, digests: list[str] | None = None) -> Path:
    path = tmp_path / "docker_digest_allowlist.json"
    path.write_text(
        json.dumps({"allowed_images": {DOCKER_IMAGE_TAG: digests or [DIGEST]}}, indent=2)
    )
    return path


def _write_candidate(tmp_path: Path) -> Path:
    path = tmp_path / "candidate_detector.py"
    path.write_text("def detect(request):\n    return {'blocked': False, 'reason': ''}\n", encoding="utf-8")
    return path


def _report_payload(candidate: Path, *, passed: bool = True, backend: str = "docker") -> dict:
    return {
        "stage": "evaluate_candidate",
        "success": passed,
        "passed_adoption_gate": passed,
        "is_tool_failure": False,
        "candidate_hash": _sha(candidate),
        "fitness_report": {"candidate_hash": _sha(candidate), "passed_adoption_gate": passed},
        "metrics": {"candidate_hash": _sha(candidate), "passed_adoption_gate": passed},
        "sandbox_backend": backend,
        "sandbox_image": DOCKER_IMAGE,
        "sandbox_network": "none",
        "sandbox_read_only": True,
        "sandbox_user": "65534:65534",
        "sandbox_cap_drop": "ALL",
        "sandbox_no_new_privileges": True,
        "sandbox_pids_limit": 32,
        "sandbox_memory_limit": "768m",
        "sandbox_cpus": "1",
        "sandbox_tmpfs": "/tmp:rw,noexec,nosuid,nodev,size=64m",
    }


def _write_report(tmp_path: Path, candidate: Path, **kwargs) -> Path:
    path = tmp_path / "fitness_report.json"
    path.write_text(json.dumps(_report_payload(candidate, **kwargs), indent=2), encoding="utf-8")
    return path


def _write_attestation(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "evaluation_promotion_attestation.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _valid_attestation(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict]:
    candidate = _write_candidate(tmp_path)
    report = _write_report(tmp_path, candidate)
    allowlist = _write_allowlist(tmp_path)
    payload = build_attestation(
        candidate_path=candidate,
        report_path=report,
        evaluated_sha=EVALUATED_SHA,
        base_main_sha=BASE_MAIN_SHA,
        run_id="123",
        run_attempt="1",
        docker_image=DOCKER_IMAGE,
        docker_image_digest=DIGEST,
        digest_allowlist_path=allowlist,
    )
    attestation = _write_attestation(tmp_path, payload)
    return candidate, report, allowlist, attestation, payload


def _verify(candidate: Path, report: Path, allowlist: Path, attestation: Path) -> list[str]:
    return verify_attestation(
        attestation_path=attestation,
        candidate_path=candidate,
        report_path=report,
        expected_evaluated_sha=EVALUATED_SHA,
        expected_base_main_sha=BASE_MAIN_SHA,
        digest_allowlist_path=allowlist,
    )


def test_valid_attestation_passes(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    assert _verify(candidate, report, allowlist, attestation) == []


def test_malformed_attestation_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    attestation.write_text("{", encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("malformed JSON" in error for error in errors)


def test_candidate_hash_mismatch_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    candidate.write_text(candidate.read_text(encoding="utf-8") + "# tamper\n", encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("candidate_sha256 mismatch" in error for error in errors)


def test_stale_evaluated_sha_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    stale = copy.deepcopy(payload)
    stale["evaluated_sha"] = "0" * 40
    _write_attestation(tmp_path, stale)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("evaluated_sha" in error for error in errors)


def test_wrong_backend_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["sandbox_backend"] = "legacy-rlimit"
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("sandbox_backend" in error for error in errors)


def test_missing_hardening_flag_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["sandbox_no_new_privileges"] = False
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("sandbox_no_new_privileges" in error for error in errors)


def test_unapproved_docker_digest_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    allowlist.write_text(json.dumps({"allowed_digests": ["python@sha256:" + "b" * 64]}), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("not in the approved allowlist" in error for error in errors)


def test_attestation_adoption_gate_false_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["passed_adoption_gate"] = False
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("passed_adoption_gate" in error for error in errors)


def test_fitness_report_adoption_gate_false_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    report.write_text(json.dumps(_report_payload(candidate, passed=False), indent=2), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("fitness report passed_adoption_gate" in error for error in errors)


def test_fitness_report_candidate_hash_mismatch_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    payload = _report_payload(candidate)
    payload["candidate_hash"] = "0" * 64
    payload["fitness_report"]["candidate_hash"] = "0" * 64
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("fitness report candidate_hash" in error for error in errors)


def test_integer_one_rejected_for_boolean_hardening_flag(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["sandbox_read_only_rootfs"] = 1
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("sandbox_read_only_rootfs" in error and "strict bool" in error for error in errors)


def test_integer_one_rejected_for_attestation_adoption_gate(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["passed_adoption_gate"] = 1
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("passed_adoption_gate" in error and "strict bool" in error for error in errors)


def test_integer_one_rejected_for_report_adoption_gate(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    payload = _report_payload(candidate)
    payload["passed_adoption_gate"] = 1
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("fitness report passed_adoption_gate" in error for error in errors)


def test_docker_image_mismatch_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, payload = _valid_attestation(tmp_path)
    wrong = copy.deepcopy(payload)
    wrong["docker_image"] = "python:3.12-slim"
    _write_attestation(tmp_path, wrong)
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("docker_image" in error for error in errors)


def test_report_sandbox_image_mismatch_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    payload = _report_payload(candidate)
    payload["sandbox_image"] = "python:3.12-slim"
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("sandbox_image does not match" in error for error in errors)


def test_empty_image_allowlist_is_fail_closed_kill_switch(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    allowlist.write_text(
        json.dumps({"allowed_images": {DOCKER_IMAGE_TAG: []}}, indent=2),
        encoding="utf-8",
    )
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("not in the approved allowlist" in error for error in errors)


def test_nested_fitness_report_adoption_gate_contradiction_refused(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    payload = _report_payload(candidate, passed=True)
    payload["fitness_report"]["passed_adoption_gate"] = False
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("fitness_report.passed_adoption_gate" in error for error in errors)


def test_image_scoped_allowlist_rejects_same_digest_under_wrong_image(tmp_path: Path) -> None:
    candidate, report, allowlist, attestation, _payload = _valid_attestation(tmp_path)
    allowlist.write_text(
        json.dumps({"allowed_images": {"python:3.12-slim": [DIGEST]}}, indent=2),
        encoding="utf-8",
    )
    errors = _verify(candidate, report, allowlist, attestation)
    assert any("approved allowlist" in error for error in errors)


def test_committed_production_allowlist_has_approved_python_digest() -> None:
    allowlist_path = Path(__file__).parent.parent / "security" / "docker_digest_allowlist.json"
    data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    allowed_images = data.get("allowed_images")
    assert isinstance(allowed_images, dict)
    python_digests = allowed_images.get(DOCKER_IMAGE_TAG)
    assert isinstance(python_digests, list)
    assert python_digests, "production python:3.11-slim digest allowlist must not be empty"
    import re

    pattern = re.compile(r"^python@sha256:[0-9a-f]{64}$")
    assert all(isinstance(digest, str) and pattern.fullmatch(digest) for digest in python_digests)
