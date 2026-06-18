import json

from scripts.propose_mutation import _SAMPLE_MUTATION, validate_proposal_output


def _proposal(replacement):
    data = dict(_SAMPLE_MUTATION)
    data["replacement_code"] = replacement
    return json.dumps(data)


def test_proposal_output_unparseable():
    result = validate_proposal_output("not-json")
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_output_unparseable"


def test_proposal_replacement_missing():
    data = dict(_SAMPLE_MUTATION)
    del data["replacement_code"]
    result = validate_proposal_output(json.dumps(data))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_missing"


def test_proposal_duplicate_replacement_key():
    valid_replacement = "    return DetectionResult(blocked=False, reason=\"no suspicious indicator matched\", confidence=0.0, matched_signals=())"
    raw = (
        '{"mutation_rationale":"r","target_threats":[],"expected_improvement":"e","risk":"r",'
        f'"replacement_code":{json.dumps(valid_replacement)},'
        f'"replacement_code":{json.dumps(valid_replacement)}}}'
    )
    result = validate_proposal_output(raw)
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_duplicate"


def test_proposal_list_valued_replacement_duplicate():
    data = dict(_SAMPLE_MUTATION)
    data["replacement_code"] = ["    return None"]
    result = validate_proposal_output(json.dumps(data))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_duplicate"


def test_proposal_replacement_like_extra_key_duplicate():
    data = dict(_SAMPLE_MUTATION)
    data["full_file"] = "module text"
    result = validate_proposal_output(json.dumps(data))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_duplicate"


def test_proposal_replacement_too_broad_function_def():
    result = validate_proposal_output(_proposal("def inspect_request(request):\n    return None"))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_too_broad"


def test_proposal_replacement_too_broad_class_def():
    result = validate_proposal_output(_proposal("class Replacement:\n    pass"))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_replacement_too_broad"


def test_proposal_boundary_tampering():
    result = validate_proposal_output(_proposal("    # === MUTATION_START ===\n    return None"))
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_mutation_boundary_tampering"


def test_proposal_validation_external_call_not_allowed():
    result = validate_proposal_output(json.dumps(_SAMPLE_MUTATION), offline_only=False)
    assert result["valid"] is False
    assert result["rejection_reasons"][0]["code"] == "proposal_external_call_not_allowed"


def test_proposal_validation_success_uses_local_sample_only():
    result = validate_proposal_output(json.dumps(_SAMPLE_MUTATION))
    assert result == {"valid": True, "rejection_reasons": []}
