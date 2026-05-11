from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project
from test_selected_prior_work_refresh import _adjacent_prior_paper, _attach_papers, _category_background_papers

from gapforge.config import GapForgeConfig
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.positioning import SelectedBenchmarkPositioningManager, render_positioning_report
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager


def test_overstrong_claim_is_softened(tmp_path: Path) -> None:
    config, benchmark_id = _plausible_benchmark(tmp_path)

    report = SelectedBenchmarkPositioningManager(config).build(benchmark_id)

    positioning = report.recommended_claims[0]
    assert positioning.claim_softening_required is True
    assert "first" in positioning.original_claim.lower()
    assert "first" not in positioning.revised_claim.lower()
    assert "novel" not in positioning.revised_claim.lower()
    assert "deployment-valid" not in positioning.revised_claim.lower()
    assert positioning.contribution_type == "evaluation protocol/measurement benchmark"
    assert positioning.novelty_strength == "plausible"


def test_missing_novelty_blocks_first_language(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(selected_project_id).id

    report = SelectedBenchmarkPositioningManager(config).build(benchmark_id)

    assert all("first" not in claim.revised_claim.lower() for claim in report.recommended_claims)
    assert any("first" in avoid.lower() for avoid in report.claims_to_avoid)
    assert any("novelty is unknown" in risk.lower() for risk in report.reviewer_risks)


def test_synthetic_limitation_is_added(tmp_path: Path) -> None:
    config, benchmark_id = _plausible_benchmark(tmp_path)

    report = SelectedBenchmarkPositioningManager(config).build(benchmark_id)

    assert any("synthetic" in risk.lower() for risk in report.reviewer_risks)
    assert any(
        "synthetic" in claim.revised_claim.lower() or any("synthetic" in reason.lower() for reason in claim.reasons)
        for claim in report.recommended_claims
    )


def test_positioning_report_renders_and_cli(tmp_path: Path) -> None:
    config, benchmark_id = _plausible_benchmark(tmp_path)
    report = SelectedBenchmarkPositioningManager(config).build(benchmark_id)

    rendered = render_positioning_report(report)

    assert "# Selected Benchmark Positioning Report" in rendered
    assert "Claims To Avoid" in rendered
    assert "Closest prior work" in rendered

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-positioning-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Selected Benchmark Positioning Report" in cli.stdout


def _plausible_benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(selected_project_id).id
    _attach_papers(config, selected_project_id, [_adjacent_prior_paper(), *_category_background_papers()])
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category="low-FPR detection/evaluation",
        paper_id="adjacent-prior",
        relationship="closest_prior_work",
    )
    for category, paper in zip(REQUIRED_RELATED_WORK_CATEGORIES[1:], _category_background_papers(), strict=True):
        RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=category, paper_id=paper.id)
    return config, benchmark_id
