"""tests/test_self_healing.py — Auto-rollback + post-promote health check (M2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.rollback_to_legacy_detector as rollback
import scripts.post_promote_healthcheck as hc

_ROOT = Path(__file__).parent.parent
_REALISTIC_RULES = "fixtures/structured_rules/realistic_baseline.json"


def _write_genome(tmp_path: Path, **fields) -> Path:
    p = tmp_path / "genome.json"
    base = {"generation": 4, "best_score": 948.04, "current_detector_hash": "abc"}
    base.update(fields)
    p.write_text(json.dumps(base), encoding="utf-8")
    return p


# --- rollback ---------------------------------------------------------------

class TestRollback:
    def test_structured_genome_reverts_to_legacy(self, tmp_path: Path) -> None:
        g = _write_genome(
            tmp_path, detector_mode="structured_rules",
            active_structured_rules_path="data/active_structured_rules.json",
            active_structured_rules_hash="h", active_structured_rules_score=902.0,
            active_structured_rules_promoted_at="t",
        )
        assert rollback.rollback_to_legacy(g) == 0
        out = json.loads(g.read_text())
        assert out["detector_mode"] == "legacy"
        assert not any(k.startswith("active_structured_rules") for k in out)
        # legacy lineage preserved
        assert out["generation"] == 4 and out["best_score"] == 948.04

    def test_idempotent_on_legacy(self, tmp_path: Path) -> None:
        g = _write_genome(tmp_path, detector_mode="legacy")
        assert rollback.rollback_to_legacy(g) == 0
        assert json.loads(g.read_text())["detector_mode"] == "legacy"

    def test_malformed_genome_refuses(self, tmp_path: Path) -> None:
        g = tmp_path / "genome.json"
        g.write_text("{not json", encoding="utf-8")
        assert rollback.rollback_to_legacy(g) == 1


# --- post-promote health check ---------------------------------------------

class TestHealthcheck:
    def _run(self, genome: Path) -> tuple[dict, bool]:
        return hc.run_healthcheck(
            genome_path=genome,
            corpus_path=_ROOT / "fixtures" / "realistic_corpus" / "all_cases.json",
            min_tp_rate=0.5,
        )

    def test_legacy_mode_is_skipped_healthy(self, tmp_path: Path) -> None:
        report, healthy = self._run(_write_genome(tmp_path, detector_mode="legacy"))
        assert healthy is True and report.get("skipped") is True

    def test_effective_structured_rules_healthy(self, tmp_path: Path) -> None:
        g = _write_genome(
            tmp_path, detector_mode="structured_rules",
            active_structured_rules_path=_REALISTIC_RULES, max_fp_rate=0.05,
        )
        report, healthy = self._run(g)
        assert healthy is True
        assert report["tp_rate"] == 1.0 and report["fp_rate"] == 0.0

    def test_missing_active_rules_unhealthy(self, tmp_path: Path) -> None:
        """Silent fallback to legacy (active rules unreadable) => detects 0 realistic
        threats => unhealthy => caller rolls back."""
        g = _write_genome(
            tmp_path, detector_mode="structured_rules",
            active_structured_rules_path="data/does_not_exist.json", max_fp_rate=0.05,
        )
        report, healthy = self._run(g)
        assert healthy is False
        assert report["tp_rate"] == 0.0

    def test_main_exit_codes(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        corpus = str(_ROOT / "fixtures" / "realistic_corpus" / "all_cases.json")
        g_ok = _write_genome(tmp_path, detector_mode="structured_rules",
                             active_structured_rules_path=_REALISTIC_RULES)
        assert hc.main(["--genome", str(g_ok), "--corpus", corpus, "--json"]) == 0
        g_bad = _write_genome(tmp_path, detector_mode="structured_rules",
                              active_structured_rules_path="data/nope.json")
        assert hc.main(["--genome", str(g_bad), "--corpus", corpus, "--json"]) == 1


# --- workflow wiring --------------------------------------------------------

def test_workflow_has_post_promote_autorollback() -> None:
    wf = (_ROOT / ".github" / "workflows" / "immunization_loop.yml").read_text(encoding="utf-8")
    assert "post_promote_healthcheck.py" in wf
    assert "rollback_to_legacy_detector.py" in wf
    assert "Post-promote health check" in wf
