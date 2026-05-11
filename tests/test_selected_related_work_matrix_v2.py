from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project
from test_selected_prior_work_refresh import _attach_papers

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager
from gapforge.selected_benchmark.related_work_matrix_v2 import (
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    render_related_work_matrix_v2,
)
from gapforge.selected_benchmark.reviewer import SelectedBenchmarkReviewerPanelBuilder


def test_matrix_v2_created_from_curated_related_work(tmp_path: Path) -> None:
    config, benchmark_id = _complete_curated_benchmark(tmp_path)

    matrix = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    assert matrix.id == f"selected-related-work-matrix-v2-{benchmark_id}"
    assert matrix.entries
    assert matrix.category_coverage["low-FPR detection/evaluation"]["status"] == "complete"
    assert any(entry.relationship == "low-FPR/statistical source" for entry in matrix.entries)
    assert not matrix.missing_categories


def test_must_cite_list_generated(tmp_path: Path) -> None:
    config, benchmark_id = _complete_curated_benchmark(tmp_path)

    matrix = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    must_cite = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).must_cite_report(benchmark_id)

    assert "closest-prior" in matrix.must_cite_ids
    assert "baseline-source" in matrix.baseline_source_ids
    assert "baseline-source" in matrix.must_cite_ids
    assert "closest-prior" in must_cite
    assert "baseline-source" in must_cite


def test_directly_solving_paper_triggers_blocker(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(selected_project_id).id
    _attach_papers(config, selected_project_id, [_paper("direct-solver", "Directly solves the selected benchmark core contribution.")])
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category="benchmark/evaluation protocol papers",
        paper_id="direct-solver",
        relationship="closest_prior_work",
        notes="directly solves selected benchmark",
    )

    matrix = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    assert matrix.entries[0].relationship == "directly solves"
    assert "direct-solver" in matrix.must_cite_ids
    assert any("no-go/revise" in risk.lower() for risk in matrix.reviewer_omission_risks)

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)

    assert any("directly-solving" in blocker.lower() for blocker in review.fatal_blockers)


def test_missing_category_preserved(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(selected_project_id).id
    _attach_papers(config, selected_project_id, [_paper("closest-prior", "Adjacent benchmark for false alarm evaluation.")])
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category="low-FPR detection/evaluation",
        paper_id="closest-prior",
        relationship="closest_prior_work",
    )

    matrix = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    assert "multi-agent collusion/covert coordination" in matrix.missing_categories
    assert matrix.category_coverage["multi-agent collusion/covert coordination"]["status"] == "missing"
    assert any("blocks publication readiness" in risk.lower() for risk in matrix.reviewer_omission_risks)


def test_matrix_v2_report_renders_and_cli(tmp_path: Path) -> None:
    config, benchmark_id = _complete_curated_benchmark(tmp_path)
    matrix = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    rendered = render_related_work_matrix_v2(matrix)

    assert "# Selected Benchmark Related-Work Matrix V2" in rendered
    assert "Reviewer Omission Risks" in rendered
    assert "Must-cite IDs" in rendered

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-related-work-matrix-v2", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Selected Benchmark Related-Work Matrix V2" in cli.stdout


def _complete_curated_benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(selected_project_id).id
    papers = [
        _paper("closest-prior", "Adjacent benchmark for sequential low-FPR specificity evaluation."),
        _paper("baseline-source", "Baseline source for benchmark monitor comparisons."),
        *[
            _paper(f"category-{index}", f"Background source for {category}.")
            for index, category in enumerate(REQUIRED_RELATED_WORK_CATEGORIES)
        ],
    ]
    _attach_papers(config, selected_project_id, papers)
    manager = RelatedWorkCurationManager(config)
    manager.attach_paper(
        benchmark_id,
        category="low-FPR detection/evaluation",
        paper_id="closest-prior",
        relationship="closest_prior_work",
    )
    manager.attach_paper(
        benchmark_id,
        category="benchmark/evaluation protocol papers",
        paper_id="baseline-source",
        relationship="baseline_source",
    )
    for index, category in enumerate(REQUIRED_RELATED_WORK_CATEGORIES):
        if category in {"low-FPR detection/evaluation", "benchmark/evaluation protocol papers"}:
            continue
        manager.attach_paper(benchmark_id, category=category, paper_id=f"category-{index}")
    return config, benchmark_id


def _paper(paper_id: str, abstract: str) -> Paper:
    return Paper(
        id=paper_id,
        title=f"{paper_id} paper",
        authors=["A. Researcher"],
        abstract=abstract,
        year=2025,
        source="arxiv",
        arxiv_id=f"2501.{abs(hash(paper_id)) % 100000:05d}",
    )
