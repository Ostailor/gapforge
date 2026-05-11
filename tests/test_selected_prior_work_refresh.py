from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.prior_work_refresh import (
    SelectedBenchmarkPriorWorkRefreshManager,
    render_selected_prior_work_dossier,
)
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager
from gapforge.state import ResearchStateManager


def test_duplicate_prior_work_rejects_novelty(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_duplicate_prior_paper()])
    _curate_all_categories(config, benchmark_id, "duplicate-prior", relationship="closest_prior_work")

    dossier = SelectedBenchmarkPriorWorkRefreshManager(config).refresh(benchmark_id)

    assert dossier.novelty_status == "duplicate"
    assert "duplicate-prior" in dossier.closest_prior_work_ids
    assert any("already covers" in item.lower() for item in dossier.what_is_not_new)
    assert dossier.decisive_difference_needed


def test_adjacent_prior_work_produces_plausible_novelty(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_adjacent_prior_paper(), *_category_background_papers()])
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category="low-FPR detection/evaluation",
        paper_id="adjacent-prior",
        relationship="closest_prior_work",
    )
    for category, paper in zip(REQUIRED_RELATED_WORK_CATEGORIES[1:], _category_background_papers(), strict=True):
        RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=category, paper_id=paper.id)

    dossier = SelectedBenchmarkPriorWorkRefreshManager(config).refresh(benchmark_id)

    assert dossier.novelty_status == "plausible"
    assert any("sequential low-FPR" in item for item in dossier.what_is_new)
    assert any(row["dimension"] == "multi-agent collusion/covert coordination" for row in dossier.comparison_table)


def test_missing_categories_keep_novelty_unknown(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_adjacent_prior_paper()])
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category="low-FPR detection/evaluation",
        paper_id="adjacent-prior",
        relationship="closest_prior_work",
    )

    dossier = SelectedBenchmarkPriorWorkRefreshManager(config).refresh(benchmark_id)

    assert dossier.novelty_status == "unknown"
    assert dossier.confidence == "low"
    assert "multi-agent collusion/covert coordination" in dossier.decisive_difference_needed[0]


def test_comparison_table_renders_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_duplicate_prior_paper()])
    _curate_all_categories(config, benchmark_id, "duplicate-prior", relationship="closest_prior_work")
    dossier = SelectedBenchmarkPriorWorkRefreshManager(config).refresh(benchmark_id)

    rendered = render_selected_prior_work_dossier(dossier)

    assert "# Selected Benchmark Prior-Work Dossier" in rendered
    assert "problem setting" in rendered
    assert "low-FPR/specificity focus" in rendered

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-prior-work-dossier", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Selected Benchmark Prior-Work Dossier" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _attach_papers(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("selected benchmark prior-work refresh")
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _curate_all_categories(config: GapForgeConfig, benchmark_id: str, paper_id: str, *, relationship: str) -> None:
    manager = RelatedWorkCurationManager(config)
    for index, category in enumerate(REQUIRED_RELATED_WORK_CATEGORIES):
        manager.attach_paper(
            benchmark_id,
            category=category,
            paper_id=paper_id,
            relationship=relationship if index == 0 else "background",
        )


def _duplicate_prior_paper() -> Paper:
    return Paper(
        id="duplicate-prior",
        title="Sequential low-FPR benchmark for multi-agent collusion audits",
        authors=["A. Researcher"],
        abstract=(
            "This benchmark covers a sequential low-FPR specificity evaluation for multi-agent collusion and covert coordination. "
            "It includes observability modes, honest null distribution, collusive alternatives, baselines, metrics, and statistics."
        ),
        year=2025,
        source="arxiv",
        arxiv_id="2501.00003",
    )


def _adjacent_prior_paper() -> Paper:
    return Paper(
        id="adjacent-prior",
        title="Sequential false alarm control for anomaly detection",
        authors=["A. Researcher"],
        abstract=(
            "This method studies low false-positive specificity and sequential change-point evaluation for anomaly detectors. "
            "It does not solve multi-agent collusion, covert coordination, observability modes, or benchmark protocol design."
        ),
        year=2025,
        source="arxiv",
        arxiv_id="2501.00004",
    )


def _category_background_papers() -> list[Paper]:
    return [
        Paper(
            id=f"background-{index}",
            title=f"{category} background paper",
            authors=["A. Researcher"],
            abstract=f"Background coverage for {category}.",
            year=2025,
            source="semantic-scholar",
            url=f"https://example.test/background-{index}",
        )
        for index, category in enumerate(REQUIRED_RELATED_WORK_CATEGORIES[1:], start=1)
    ]
