from scripts import pre_paid_credit_readiness as readiness


def test_readiness_success_path_current_generation3_state():
    result = readiness.run_readiness()
    assert result["ready"] is True
    assert result["checks"]["state_consistency"] == "pass"
    assert result["checks"]["detector_hash"] == "pass"
    assert result["metadata"]["phase"] == 3
    assert result["metadata"]["generation"] == 3
    assert result["metadata"]["best_score"] == 947.66


def test_readiness_detector_hash_mismatch_rejection(monkeypatch):
    monkeypatch.setattr(readiness, "EXPECTED_DETECTOR_HASH", "0" * 64)
    result = readiness.run_readiness()
    assert result["ready"] is False
    assert result["checks"]["detector_hash"] == "fail"
    assert any(r["code"] == "detector_hash_mismatch" for r in result["rejection_reasons"])


def test_readiness_missing_candidate_contract_checker_rejection(monkeypatch):
    import scripts.candidate_contract as candidate_contract
    monkeypatch.delattr(candidate_contract, "run_candidate_contract_checks")
    result = readiness.run_readiness()
    assert result["ready"] is False
    assert result["checks"]["candidate_contract_available"] == "fail"
    assert any(r["code"] == "candidate_contract_checker_missing" for r in result["rejection_reasons"])


def test_readiness_no_candidate_artifacts_not_applicable():
    result = readiness.run_readiness()
    assert result["checks"]["candidate_artifacts"] == "not_applicable"
    assert all(r["code"] != "candidate_materialization_failed" for r in result["rejection_reasons"])
