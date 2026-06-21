"""Tests for the Owner/auditor-facing read-only evolution report CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import report


_HISTORY = [
    {
        "generation": 0,
        "score": -1000000.0,
        "passed_adoption_gate": False,
        "promoted_at": "2026-05-26T00:00:00Z",
    },
    {
        "generation": 1,
        "score": 10.0,
        "tp_rate": 0.5,
        "fp_rate": 0.2,
        "fn_rate": 0.5,
        "total_cases": 4,
        "passed_adoption_gate": True,
        "promoted_at": "2026-05-26T01:00:00Z",
    },
    {
        "generation": 4,
        "score": 25.0,
        "tp_rate": 0.75,
        "fp_rate": 0.1,
        "fn_rate": 0.25,
        "total_cases": 4,
        "passed_adoption_gate": True,
        "promoted_at": "2026-06-18T09:00:00Z",
    },
]


def _write_history(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_HISTORY), encoding="utf-8")
    return path


def test_generation_zero_placeholder_not_used_as_score_delta(tmp_path: Path):
    history_path = _write_history(tmp_path / "data" / "evolution_history.json")

    markdown = report.build_markdown(history_path, tmp_path)

    assert "Generation 0 is an unevaluated baseline placeholder" in markdown
    assert "| 0 | placeholder" in markdown
    assert "+1000025.0000" not in markdown


def test_default_scored_comparison_uses_generation_one_to_current(tmp_path: Path):
    history_path = _write_history(tmp_path / "data" / "evolution_history.json")

    markdown = report.build_markdown(history_path, tmp_path)

    assert "## Measured Score Comparison: Gen 1 → Gen 4" in markdown
    assert "| Fitness score | 10.0000 | 25.0000 | +15.0000 |" in markdown


def test_export_to_data_genome_json_is_rejected(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        report.main(["report", "--repo-root", ".", "--export", "data/genome.json"])

    assert exc.value.code == 2
    assert "refusing to overwrite protected repository path" in capsys.readouterr().err


def test_export_to_data_evolution_history_json_is_rejected(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        report.main(["report", "--repo-root", ".", "--export", "data/evolution_history.json"])

    assert exc.value.code == 2
    assert "refusing to overwrite protected repository path" in capsys.readouterr().err


def test_explicit_history_path_works(tmp_path: Path):
    history_path = _write_history(tmp_path / "history.json")
    export_path = tmp_path / "report.md"

    assert report.main(["report", "--history-path", str(history_path), "--export", str(export_path)]) == 0

    assert export_path.read_text(encoding="utf-8").startswith(
        "# Cyber-Immunizer Owner/Auditor Evolution Validation Report"
    )


def test_explicit_repo_root_works(tmp_path: Path):
    _write_history(tmp_path / "data" / "evolution_history.json")
    export_path = tmp_path / "out" / "report.md"

    assert report.main(["report", "--repo-root", str(tmp_path), "--export", str(export_path)]) == 0

    assert "Source: `data/evolution_history.json`" in export_path.read_text(encoding="utf-8")


def test_cli_output_states_symbolic_corpus_and_real_world_value_limitation(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _write_history(tmp_path / "data" / "evolution_history.json")

    assert report.main(["report", "--repo-root", str(tmp_path)]) == 0

    output = capsys.readouterr().out
    assert "symbolic-corpus evolution evidence" in output
    assert "does not prove real-world defensive usefulness" in output
    assert "does not connect to real traffic" in output
    assert "does not validate production WAF suitability" in output
