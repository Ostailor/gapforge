from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_completion import (
    RelatedWorkCompletionManager,
    render_related_work_completion_status,
)
from gapforge.state import ResearchStateManager, utc_now_iso


def test_related_work_completion_detects_missing_categories(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    status = RelatedWorkCompletionManager(config).complete(benchmark_id)

    assert set(status.missing_categories) == set(REQUIRED_RELATED_WORK_CATEGORIES)
    assert status.real_paper_count == 0
    assert status.novelty_status == "unknown"
    assert any("Missing real paper records" in blocker for blocker in status.blockers)


def test_real_paper_records_complete_category(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(
        config,
        project_id,
        [
            Paper(
                id="real-low-fpr",
                title="Low false positive specificity evaluation for detectors",
                authors=["A. Researcher"],
                abstract="Evaluates false alarm specificity and low false positive detector behavior.",
                year=2025,
                source="arxiv",
                arxiv_id="2501.00001",
            )
        ],
    )

    status = RelatedWorkCompletionManager(config).complete(benchmark_id)
    category = status.category_statuses["low-FPR detection/evaluation"]

    assert category.status == "complete"
    assert category.real_paper_ids == ["real-low-fpr"]
    assert "low-FPR detection/evaluation" not in status.missing_categories
    assert status.real_paper_count == 1
    assert status.novelty_status == "unknown"


def test_fallback_only_category_remains_partial(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(
        config,
        project_id,
        [
            Paper(
                id="fallback-low-fpr",
                title="Low false positive specificity evaluation fallback",
                authors=[],
                abstract="false alarm specificity",
                year=2025,
                source="fixture",
                raw_metadata={"fallback": True},
                provenance=Provenance(
                    created_by_skill="fixture",
                    timestamp=utc_now_iso(),
                    reasoning_summary="deterministic fallback paper record",
                ),
            )
        ],
    )

    status = RelatedWorkCompletionManager(config).complete(benchmark_id)
    category = status.category_statuses["low-FPR detection/evaluation"]

    assert category.status == "partial"
    assert category.real_paper_ids == []
    assert category.fallback_paper_ids == ["fallback-low-fpr"]
    assert "low-FPR detection/evaluation" in status.missing_categories
    assert status.fallback_paper_count == 1


def test_novelty_not_unknown_after_all_required_categories_have_real_records(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, _complete_real_papers())

    status = RelatedWorkCompletionManager(config).complete(benchmark_id)

    assert status.missing_categories == []
    assert all(category.status == "complete" for category in status.category_statuses.values())
    assert status.novelty_status == "coverage_complete_review_required"
    assert status.blockers == []


def test_related_work_completion_report_renders_and_cli_next_searches(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    manager = RelatedWorkCompletionManager(config)
    status = manager.complete(benchmark_id)

    rendered = render_related_work_completion_status(status, manager.next_searches(benchmark_id))

    assert "# Related-Work Completion Status" in rendered
    assert "Novelty status: `unknown`" in rendered
    assert "selected-related-work-next-searches" not in rendered
    assert "gapforge search" in rendered

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-related-work-next-searches", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "gapforge search" in cli.stdout
    assert "low false-positive" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _attach_papers(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("selected benchmark related work completion")
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _complete_real_papers() -> list[Paper]:
    records = [
        ("real-low-fpr", "Low false positive specificity evaluation", "false alarm specificity low false positive"),
        ("real-collusion", "Multi-agent collusion and covert coordination", "multi-agent collusion covert coordination"),
        ("real-evasion", "Monitor evasion by adversarial agents", "monitor evasion adversarial audit detector"),
        ("real-sequential", "Sequential testing and change-point detection", "sequential change-point repeated alarm"),
        ("real-benchmark", "Benchmark evaluation protocol design", "benchmark evaluation protocol dataset baselines"),
        ("real-anomaly", "Anomaly detection specificity", "anomaly specificity false-positive rare event"),
        ("real-medical", "Medical screening specificity", "medical screening diagnostic sensitivity specificity"),
        ("real-cartel", "Cartel and covert-channel analogies", "cartel covert channel price fixing"),
    ]
    return [
        Paper(
            id=paper_id,
            title=title,
            authors=["A. Researcher"],
            abstract=abstract,
            year=2024,
            source="semantic-scholar",
            url=f"https://example.test/{paper_id}",
        )
        for paper_id, title, abstract in records
    ]
