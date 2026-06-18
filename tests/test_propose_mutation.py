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


def test_proposal_replacement_too_broad():
    result = validate_proposal_output(_proposal("def inspect_request(request):\n    return None"))
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
