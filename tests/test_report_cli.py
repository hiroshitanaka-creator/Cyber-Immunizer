"""Focused tests for the read-only Owner/auditor report CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import report


def _write_history(repo_root: Path) -> Path:
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True)
    history_path = data_dir / "evolution_history.json"
    history_path.write_text(
        json.dumps(
            [
                {
                    "generation": 0,
                    "score": -1000000.0,
                    "passed_adoption_gate": False,
                    "promoted_at": "2026-05-26T00:00:00Z",
                    "note": "Initial baseline generation",
                },
                {
                    "generation": 1,
                    "score": 383.67051093329087,
                    "passed_adoption_gate": True,
                    "promoted_at": "2026-05-26T01:09:22.857101Z",
                    "tp_rate": 1.0,
                    "fp_rate": 0.0,
                    "fn_rate": 0.0,
                    "total_cases": 15,
                },
                {
                    "generation": 4,
                    "score": 948.04,
                    "passed_adoption_gate": True,
                    "promoted_at": "2026-06-18T09:26:32.863814Z",
                    "tp_rate": 1.0,
                    "fp_rate": 0.0,
                    "fn_rate": 0.0,
                    "total_cases": 15,
                },
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return history_path


def test_generation_zero_placeholder_not_used_as_measured_score_delta(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    assert "Gen 1 measured baseline" in markdown
    assert "Gen 4 current" in markdown
    assert "unevaluated placeholder" in markdown
    assert "-1000000.0000" not in markdown
    assert "+1000948.0400" not in markdown


def test_default_scored_comparison_uses_generation_one_to_current(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    assert "| Fitness score | 383.6705 | 948.0400 | +564.3695 |" in markdown
    assert "| Generation | 1 | 4 | +3.0000 |" in markdown
    assert "| Fitness score | -1000000.0000 | 948.0400 |" not in markdown


@pytest.mark.parametrize("protected_relative", ["data/genome.json", "data/evolution_history.json"])
def test_export_to_protected_data_paths_is_rejected(tmp_path: Path, protected_relative: str):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)
    export_path = repo_root / protected_relative

    with pytest.raises(report.ReportError, match="protected repository path"):
        report._write_export(export_path, "# report\n", repo_root)

    if protected_relative == "data/genome.json":
        assert not export_path.exists()
    else:
        assert json.loads(export_path.read_text(encoding="utf-8"))[0]["generation"] == 0


def test_explicit_history_path_works(tmp_path: Path):
    repo_root = tmp_path / "repo"
    history_path = _write_history(repo_root)

    markdown = report.build_markdown(history_path=history_path)

    assert "Source: `data/evolution_history.json`" in markdown
    assert "Gen 1 measured baseline" in markdown


def test_explicit_repo_root_works(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    assert "Source: `data/evolution_history.json`" in markdown
    assert "Gen 4 current" in markdown


def test_cli_output_states_symbolic_corpus_and_real_world_limitations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    result = report.main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    assert result == 0
    assert "symbolic-corpus evolution evidence" in captured.out
    assert "does not prove real-world defensive value" in captured.out
    assert "does not connect to real traffic" in captured.out
    assert "does not validate production WAF suitability" in captured.out
    assert "Externalization remains blocked until Layer 2 value validation is satisfied" in captured.out
