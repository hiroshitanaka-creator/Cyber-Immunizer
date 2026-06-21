"""Focused tests for the read-only Owner/auditor report CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import report


# Generation 1 and Generation 2 carry pre-migration scores (older fitness
# formula). Generation 3 and Generation 4 are post-migration / same-schema.
_FULL_HISTORY = [
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
        "generation": 2,
        "score": 729.34,
        "passed_adoption_gate": True,
        "promoted_at": "2026-05-26T07:28:45.915954Z",
        "tp_rate": 1.0,
        "fp_rate": 0.0,
        "fn_rate": 0.0,
        "total_cases": 15,
    },
    {
        "generation": 3,
        "score": 947.66,
        "passed_adoption_gate": True,
        "promoted_at": "2026-06-18T02:13:36.244423Z",
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
]


def _write_history(repo_root: Path, entries: list[dict] | None = None) -> Path:
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True)
    history_path = data_dir / "evolution_history.json"
    history_path.write_text(
        json.dumps(entries if entries is not None else _FULL_HISTORY, indent=2),
        encoding="utf-8",
    )
    return history_path


def test_generation_zero_placeholder_not_used_as_measured_score_delta(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    assert "unevaluated placeholder" in markdown
    # Generation 0 sentinel score must never appear in a measured delta.
    assert "-1000000.0000" not in markdown
    assert "+1000948.0400" not in markdown
    # The measured-delta baseline is a post-migration generation, not gen0.
    assert "Gen 0 measured baseline" not in markdown


def test_default_measured_comparison_uses_same_schema_generation_three_to_four(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    # Default measured comparison is same-schema gen3 -> gen4.
    assert "Gen 3 measured baseline" in markdown
    assert "Gen 4 current" in markdown
    assert "| Fitness score | 947.6600 | 948.0400 | +0.3800 |" in markdown
    assert "| Generation | 3 | 4 | +1.0000 |" in markdown


def _fitness_row(before_score: float, after_score: float) -> str:
    """Construct a measured Fitness-score row exactly as build_markdown would.

    Built at runtime so forbidden cross-schema literals never appear verbatim in
    this source file (which keeps repo scans clean) while still proving the
    report does not emit them.
    """
    return (
        f"| Fitness score | {before_score:.4f} | {after_score:.4f} | "
        f"{after_score - before_score:+.4f} |"
    )


def test_cross_schema_generation_one_to_four_delta_is_not_displayed(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    gen0_score = _FULL_HISTORY[0]["score"]
    gen1_score = _FULL_HISTORY[1]["score"]
    gen2_score = _FULL_HISTORY[2]["score"]
    gen4_score = _FULL_HISTORY[4]["score"]

    # The pre-migration -> post-migration delta must not be presented as measured.
    assert _fitness_row(gen1_score, gen4_score) not in markdown
    assert _fitness_row(gen2_score, gen4_score) not in markdown
    assert "Gen 1 measured baseline" not in markdown
    assert "Gen 2 measured baseline" not in markdown
    # No measured delta should originate from the gen0 sentinel either.
    assert _fitness_row(gen0_score, gen4_score) not in markdown


def test_pre_migration_generations_remain_visible_as_lineage_only(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    # Gen1 and Gen2 stay visible in the evidence table as historical lineage.
    assert f"{_FULL_HISTORY[1]['score']:.4f}" in markdown
    assert f"{_FULL_HISTORY[2]['score']:.4f}" in markdown
    assert "pre-migration lineage" in markdown
    assert "post-migration (same-schema)" in markdown


def test_report_includes_score_schema_migration_note(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)

    markdown = report.build_markdown(repo_root=repo_root)

    assert (
        "Scores before the Generation 3 score-schema migration are historical"
        in markdown
    )
    assert "Cross-schema score deltas are not measured improvement." in markdown
    assert (
        "Current internal symbolic-corpus evidence still does not prove "
        "real-world defensive value." in markdown
    )


def test_score_delta_suppressed_when_no_same_schema_pair(tmp_path: Path):
    repo_root = tmp_path / "repo"
    # Only gen0 placeholder + pre-migration gen1/gen2 + a single post-migration
    # gen3 → fewer than two same-schema records → delta must be suppressed.
    _write_history(repo_root, entries=_FULL_HISTORY[:4])

    markdown = report.build_markdown(repo_root=repo_root)

    assert "Score delta suppressed: score schema changed before Generation 3." in markdown
    # No silent fallback to a cross-schema measured delta.
    assert "measured baseline | Gen" not in markdown
    gen1_score = _FULL_HISTORY[1]["score"]
    gen3_score = _FULL_HISTORY[3]["score"]
    assert _fitness_row(gen1_score, gen3_score) not in markdown
    # Pre-migration scores still visible as lineage.
    assert f"{gen1_score:.4f}" in markdown
    assert "pre-migration lineage" in markdown


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


@pytest.mark.parametrize(
    "protected_relative",
    [
        "docs/AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md",
        "docs/PROJECT_STATE.md",
        "docs/DEFINITION_OF_DONE.md",
        "docs/VALUE_DELIVERY_BLUEPRINT.md",
        "docs/audit_gate/PR_AUDIT_PROTOCOL.md",
    ],
)
def test_export_to_protected_docs_paths_is_rejected(tmp_path: Path, protected_relative: str):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)
    export_path = repo_root / protected_relative
    # Seed an existing canonical doc to prove it is not overwritten.
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text("# canonical doc — must not be overwritten\n", encoding="utf-8")

    with pytest.raises(report.ReportError, match="protected repository path"):
        report._write_export(export_path, "# report\n", repo_root)

    # Original canonical content is untouched.
    assert export_path.read_text(encoding="utf-8") == "# canonical doc — must not be overwritten\n"


def test_export_into_docs_subdirectory_is_rejected(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)
    # Any path under docs/** is protected, even files that do not exist yet.
    export_path = repo_root / "docs" / "task_reports" / "new_report.md"

    with pytest.raises(report.ReportError, match="protected repository path"):
        report._write_export(export_path, "# report\n", repo_root)

    assert not export_path.exists()


@pytest.mark.parametrize(
    "tracked_relative",
    ["AGENTS.md", "CLAUDE.md", "cli/report.py", "tests/test_report_cli.py", "intelligence/x.py"],
)
def test_export_to_any_tracked_repo_file_is_rejected(tmp_path: Path, tracked_relative: str):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)
    export_path = repo_root / tracked_relative
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text("ORIGINAL REPO CONTENT — must not be overwritten\n", encoding="utf-8")

    with pytest.raises(report.ReportError, match="protected repository path"):
        report._write_export(export_path, "# report\n", repo_root)

    # Any file inside the repository checkout is protected; content is untouched.
    assert export_path.read_text(encoding="utf-8") == "ORIGINAL REPO CONTENT — must not be overwritten\n"


def test_export_outside_repo_is_allowed(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_history(repo_root)
    # A path outside the repository checkout is the intended export target.
    outside = tmp_path / "exports" / "report.md"

    report._write_export(outside, "# report\n", repo_root)

    assert outside.read_text(encoding="utf-8") == "# report\n"


def test_history_path_outside_data_dir_is_usable(tmp_path: Path):
    # A standalone history file outside the canonical data/ layout must be usable
    # with --history-path alone (the CLI forbids also passing --repo-root), and
    # must not raise an unsatisfiable "repo-root required" error.
    loose_history = tmp_path / "loose" / "evolution_history.json"
    loose_history.parent.mkdir(parents=True)
    loose_history.write_text(json.dumps(_FULL_HISTORY, indent=2), encoding="utf-8")

    repo_root = report._resolve_repo_root(None, loose_history)
    assert repo_root == loose_history.parent.resolve()

    markdown = report.build_markdown(history_path=loose_history)
    assert "Gen 3 measured baseline" in markdown
    assert "Gen 4 current" in markdown


def test_history_path_outside_data_dir_cli_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    loose_history = tmp_path / "loose" / "evolution_history.json"
    loose_history.parent.mkdir(parents=True)
    loose_history.write_text(json.dumps(_FULL_HISTORY, indent=2), encoding="utf-8")

    result = report.main(["--history-path", str(loose_history)])

    captured = capsys.readouterr()
    assert result == 0
    assert "Owner/Auditor Evolution Validation Report" in captured.out


def test_evidence_table_preserves_append_order(tmp_path: Path):
    repo_root = tmp_path / "repo"
    # Append a rollback/backtrack record whose generation legitimately decreases
    # (docs/EVOLUTION_HISTORY_AUDIT.md). The evidence table must keep append
    # order, not re-sort by generation.
    rollback_record = {
        "generation": 3,
        "score": 900.55,
        "passed_adoption_gate": False,
        "promoted_at": "2026-06-19T00:00:00Z",
        "note": "rollback audit record",
    }
    entries = _FULL_HISTORY + [rollback_record]
    _write_history(repo_root, entries=entries)

    markdown = report.build_markdown(repo_root=repo_root)

    # The rollback record (score 900.5500) was appended last, so its evidence
    # row must appear after the Generation 4 evidence row — order is not
    # re-sorted. Match evidence-table rows specifically ("| <gen> | <score> |").
    gen4_row_pos = markdown.index("| 4 | 948.0400 |")
    rollback_row_pos = markdown.index("| 3 | 900.5500 |")
    assert rollback_row_pos > gen4_row_pos

    # Measured comparison still uses same-schema gen3 -> gen4 regardless of order.
    assert "Gen 3 measured baseline" in markdown
    assert "Gen 4 current" in markdown
    # The rejected rollback record (passed_adoption_gate=False) must not be used
    # as the current measured generation.
    assert _fitness_row(947.66, 900.55) not in markdown
    assert _fitness_row(900.55, 948.04) not in markdown


def test_rejected_highest_generation_is_not_current(tmp_path: Path):
    repo_root = tmp_path / "repo"
    # A later, higher-numbered but rejected post-migration attempt must not be
    # presented as the current generation; the measured comparison stays on the
    # promoted gen3 -> gen4 pair.
    rejected_record = {
        "generation": 5,
        "score": 10.0,
        "passed_adoption_gate": False,
        "promoted_at": "2026-06-20T00:00:00Z",
        "note": "rejected attempt",
    }
    _write_history(repo_root, entries=_FULL_HISTORY + [rejected_record])

    markdown = report.build_markdown(repo_root=repo_root)

    assert "Gen 3 measured baseline" in markdown
    assert "Gen 4 current" in markdown
    assert "Gen 5 current" not in markdown
    # Rejected record is still visible in the evidence table as lineage.
    assert "| 5 | 10.0000 |" in markdown


def test_explicit_history_path_works(tmp_path: Path):
    repo_root = tmp_path / "repo"
    history_path = _write_history(repo_root)

    markdown = report.build_markdown(history_path=history_path)

    assert "Source: `data/evolution_history.json`" in markdown
    assert "Gen 3 measured baseline" in markdown


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
