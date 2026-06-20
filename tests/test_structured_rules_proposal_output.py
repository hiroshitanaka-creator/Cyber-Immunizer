from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.propose_mutation as pm
from core.structured_detector import inspect_request_with_structured_rules
from core.structured_evaluator import evaluate_structured_rules
from core.structured_validator import validate_rules_schema
from core.types import DetectionResult, Request

ROOT = Path(__file__).parent.parent
VALIDATOR_CLI = ROOT / "scripts" / "validate_structured_rules.py"


def request(**kwargs) -> Request:
    defaults = {
        "method": "GET",
        "path": "/api/data",
        "query": {},
        "headers": {"content-type": "text/plain"},
        "body": "",
    }
    defaults.update(kwargs)
    return Request(**defaults)


def test_offline_structured_rules_document_is_valid_and_safe_shape() -> None:
    doc, err = pm.propose_structured_rules(offline_sample=True)

    assert err == ""
    assert doc is not None
    assert validate_rules_schema(doc) == {"success": True, "violations": []}
    assert [rule["id"] for rule in doc["rules"]] == [
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
        "command_delimiter_indicator",
        "encoded_traversal_indicator",
    ]
    assert all(rule["operator"] == "contains_literal" for rule in doc["rules"])
    assert all(rule["confidence"] == 0.86 for rule in doc["rules"])
    assert doc["decision"]["block_when"] == "any_rule_matches"
    assert doc["decision"]["confidence_strategy"] == {
        "type": "bounded_match_count",
        "default": 0.86,
        "two_matches": 0.94,
        "three_or_more_matches": 0.99,
    }
    assert doc["fallback"] == {
        "blocked": False,
        "reason": "no suspicious indicator matched",
        "confidence": 0.0,
        "matched_signals": [],
    }
    assert doc["features"]["surface"]["body_scan"]["max_bytes"] >= 524288


def test_structured_rules_cli_writes_rules_not_mutation_patch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    out_dir = tmp_path / ".cyber_immunizer"
    structured_path = out_dir / "structured_rules.json"
    patch_path = out_dir / "mutation_patch.json"
    monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
    monkeypatch.setattr(pm, "_OUT_STRUCTURED_RULES", structured_path)
    monkeypatch.setattr(pm, "_OUT_PATCH", patch_path)

    rc = pm.main(["--structured-rules", "--offline-sample", "--json"])

    assert rc == 0
    assert structured_path.exists()
    assert not patch_path.exists()
    doc = json.loads(structured_path.read_text(encoding="utf-8"))
    assert validate_rules_schema(doc)["success"] is True


def test_structured_rules_output_is_cli_validator_compatible(tmp_path: Path) -> None:
    doc, err = pm.propose_structured_rules(offline_sample=True)
    assert err == ""
    rules_path = tmp_path / "structured_rules.json"
    rules_path.write_text(json.dumps(doc), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_CLI), str(rules_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_generated_rules_evaluate_through_evaluator_and_adapter() -> None:
    doc, err = pm.propose_structured_rules(offline_sample=True)
    assert err == ""
    req = request(
        path="/PATH_TRAVERSAL_INDICATOR",
        body="SCRIPT_INJECTION_INDICATOR SQLI_INDICATOR",
    )

    evaluator_result = evaluate_structured_rules(req, doc)
    adapter_result = inspect_request_with_structured_rules(req, doc)

    assert type(evaluator_result) is DetectionResult
    assert evaluator_result == adapter_result
    assert evaluator_result.blocked is True
    assert evaluator_result.reason == "suspicious indicator matched"
    assert evaluator_result.confidence == 0.99
    assert evaluator_result.matched_signals == (
        "path_traversal_indicator",
        "script_injection_indicator",
        "sqli_indicator",
    )


def test_structured_rules_without_offline_sample_fails_closed() -> None:
    doc, err = pm.propose_structured_rules(offline_sample=False)

    assert doc is None
    assert "requires --offline-sample" in err
