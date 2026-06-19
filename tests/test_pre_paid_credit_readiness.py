import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import pre_paid_credit_readiness as readiness
from scripts.offline_validation import sha256_text

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pre_paid_credit_readiness.py"


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "core").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    shutil.copy(ROOT / "core" / "detector.py", repo / "core" / "detector.py")
    shutil.copy(ROOT / "data" / "genome.json", repo / "data" / "genome.json")
    shutil.copy(ROOT / "data" / "project_state.json", repo / "data" / "project_state.json")
    (repo / "README.md").write_text("fixture\n")
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "base"], repo)
    return repo


def _cli(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(repo), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_readiness_cli_success_returns_zero_and_generation4_json(fixture_repo: Path):
    result = _cli(fixture_repo)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ready"] is True
    assert payload["checks"]["state_consistency"] == "pass"
    assert payload["checks"]["detector_hash"] == "pass"
    assert payload["checks"]["frozen_committed_drift"] == "not_applicable"
    assert payload["metadata"]["generation"] == 4
    assert payload["metadata"]["best_score"] == 948.04
    assert payload["metadata"]["detector_hash"] == (
        "ebb8799db748ed3c3b38eec0c11cdc423b0e43ca04a374ba7e26a48059c30d3f"
    )


def test_readiness_fails_if_fixture_regresses_to_generation3(fixture_repo: Path):
    genome = json.loads((fixture_repo / "data" / "genome.json").read_text())
    genome["generation"] = 3
    genome["best_score"] = 947.66
    genome["current_detector_hash"] = (
        "c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6"
    )
    (fixture_repo / "data" / "genome.json").write_text(json.dumps(genome))
    result = _cli(fixture_repo)
    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["ready"] is False
    codes = {r["code"] for r in payload["rejection_reasons"]}
    assert "state_consistency_mismatch" in codes or "detector_hash_mismatch" in codes


def test_readiness_cli_failure_returns_nonzero_with_precise_code(fixture_repo: Path):
    genome = json.loads((fixture_repo / "data" / "genome.json").read_text())
    genome["current_detector_hash"] = "0" * 64
    (fixture_repo / "data" / "genome.json").write_text(json.dumps(genome))
    result = _cli(fixture_repo)
    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["ready"] is False
    assert any(r["code"] == "detector_hash_mismatch" for r in payload["rejection_reasons"])


def test_readiness_structured_failure_for_unparseable_state(fixture_repo: Path):
    (fixture_repo / "data" / "genome.json").write_text("{")
    result = readiness.run_readiness(fixture_repo)
    assert result["ready"] is False
    assert any(r["code"] == "state_file_unparseable" for r in result["rejection_reasons"])


def test_readiness_phase_parse_failed(fixture_repo: Path):
    state = json.loads((fixture_repo / "data" / "project_state.json").read_text())
    state["current_phase"] = "phase_three"
    (fixture_repo / "data" / "project_state.json").write_text(json.dumps(state))
    result = readiness.run_readiness(fixture_repo)
    assert any(r["code"] == "phase_parse_failed" for r in result["rejection_reasons"])


def test_frozen_worktree_drift(fixture_repo: Path):
    (fixture_repo / "core" / "detector.py").write_text("changed")
    result = readiness.run_readiness(fixture_repo)
    assert result["checks"]["frozen_worktree_drift"] == "fail"
    assert any(r["code"] == "frozen_worktree_drift" for r in result["rejection_reasons"])


def test_frozen_index_drift(fixture_repo: Path):
    (fixture_repo / "data" / "genome.json").write_text("{}")
    _run(["git", "add", "data/genome.json"], fixture_repo)
    result = readiness.run_readiness(fixture_repo)
    assert result["checks"]["frozen_index_drift"] == "fail"
    assert any(r["code"] == "frozen_index_drift" for r in result["rejection_reasons"])


def test_frozen_committed_drift_with_base_ref(fixture_repo: Path):
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo, text=True).strip()
    (fixture_repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    _run(["git", "add", ".github/workflows/ci.yml"], fixture_repo)
    _run(["git", "commit", "-m", "workflow drift"], fixture_repo)
    result = readiness.run_readiness(fixture_repo, base_ref=base)
    assert result["checks"]["frozen_committed_drift"] == "fail"
    assert any(r["code"] == "frozen_committed_drift" for r in result["rejection_reasons"])


def test_non_frozen_committed_change_does_not_fail(fixture_repo: Path):
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture_repo, text=True).strip()
    (fixture_repo / "README.md").write_text("changed\n")
    _run(["git", "add", "README.md"], fixture_repo)
    _run(["git", "commit", "-m", "docs"], fixture_repo)
    result = readiness.run_readiness(fixture_repo, base_ref=base)
    assert result["checks"]["frozen_committed_drift"] == "pass"


def test_invalid_base_ref_fails_closed(fixture_repo: Path):
    result = readiness.run_readiness(fixture_repo, base_ref="missing-ref")
    assert result["checks"]["frozen_committed_drift"] == "fail"
    assert any(r["code"] == "git_diff_failed" for r in result["rejection_reasons"])


def test_candidate_absent_is_not_applicable(fixture_repo: Path):
    result = readiness.run_readiness(fixture_repo)
    assert result["checks"]["candidate_artifacts"] == "not_applicable"


def _write_candidate(repo: Path, report_hash: str | None | object) -> str:
    cand_dir = repo / ".cyber_immunizer"
    cand_dir.mkdir()
    source = (repo / "core" / "detector.py").read_text()
    (cand_dir / "candidate_detector.py").write_text(source)
    actual = sha256_text(source)
    report = {"success": True}
    if report_hash is not ...:
        report["candidate_hash"] = actual if report_hash is None else report_hash
    (cand_dir / "apply_report.json").write_text(json.dumps(report))
    return actual


def test_candidate_matching_report_hash_passes(fixture_repo: Path):
    _write_candidate(fixture_repo, None)
    result = readiness.run_readiness(fixture_repo)
    assert result["checks"]["candidate_artifacts"] == "pass"


def test_candidate_mismatched_report_hash_fails(fixture_repo: Path):
    _write_candidate(fixture_repo, "0" * 64)
    result = readiness.run_readiness(fixture_repo)
    assert result["checks"]["candidate_artifacts"] == "fail"
    assert any(r["code"] == "candidate_report_hash_mismatch" for r in result["rejection_reasons"])


def test_candidate_missing_report_fails(fixture_repo: Path):
    cand_dir = fixture_repo / ".cyber_immunizer"
    cand_dir.mkdir()
    shutil.copy(fixture_repo / "core" / "detector.py", cand_dir / "candidate_detector.py")
    result = readiness.run_readiness(fixture_repo)
    assert any(r["code"] == "candidate_report_missing" for r in result["rejection_reasons"])


def test_candidate_malformed_report_fails(fixture_repo: Path):
    _write_candidate(fixture_repo, None)
    (fixture_repo / ".cyber_immunizer" / "apply_report.json").write_text("{")
    result = readiness.run_readiness(fixture_repo)
    assert any(r["code"] == "candidate_materialization_failed" for r in result["rejection_reasons"])


def test_candidate_report_missing_hash_fails(fixture_repo: Path):
    _write_candidate(fixture_repo, ...)
    result = readiness.run_readiness(fixture_repo)
    assert any(r["code"] == "candidate_report_hash_missing" for r in result["rejection_reasons"])
