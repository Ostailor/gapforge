from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from test_selected_benchmark import _env, _selected_project

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work_curation import (
    RelatedWorkCurationManager,
    render_related_work_curation_report,
)
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_CATEGORY = "low-FPR detection/evaluation"


def test_attach_real_paper_to_category(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_real_paper("real-low-fpr")])

    attachment = RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category=LOW_FPR_CATEGORY,
        paper_id="real-low-fpr",
        relationship="closest_prior_work",
        curator="human-reviewer",
    )
    report = RelatedWorkCurationManager(config).report(benchmark_id)

    assert attachment.status == "accepted"
    assert attachment.relationship == "closest_prior_work"
    assert report.category_statuses[LOW_FPR_CATEGORY]["status"] == "complete"
    assert report.closest_prior_work_ids == ["real-low-fpr"]
    assert report.accepted_paper_count == 1


def test_reject_irrelevant_paper(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_real_paper("real-low-fpr")])
    manager = RelatedWorkCurationManager(config)
    manager.attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="real-low-fpr")

    rejected = manager.reject_paper(benchmark_id, paper_id="real-low-fpr", reason="not actually about specificity")
    report = manager.report(benchmark_id)

    assert rejected[0].status == "rejected"
    assert "not actually" in rejected[0].notes
    assert report.rejected_paper_count == 1
    assert LOW_FPR_CATEGORY in report.missing_categories


def test_fallback_paper_does_not_complete_category(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_fallback_paper("fallback-low-fpr")])

    attachment = RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="fallback-low-fpr")
    report = RelatedWorkCurationManager(config).report(benchmark_id)

    assert attachment.status == "needs_review"
    assert "fallback" in attachment.notes.lower()
    assert report.category_statuses[LOW_FPR_CATEGORY]["status"] == "missing"
    assert LOW_FPR_CATEGORY in report.missing_categories


def test_unknown_paper_id_is_rejected_as_fake_citation(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    with pytest.raises(ValueError, match="fake citations"):
        RelatedWorkCurationManager(config).attach_paper(
            benchmark_id,
            category=LOW_FPR_CATEGORY,
            paper_id="invented-paper",
        )


def test_waiver_requires_human_reason(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    manager = RelatedWorkCurationManager(config)

    with pytest.raises(ValueError, match="waiver reason"):
        manager.waive_category(benchmark_id, category=LOW_FPR_CATEGORY, reason="", curator="human-reviewer")

    report = manager.waive_category(
        benchmark_id,
        category=LOW_FPR_CATEGORY,
        reason="medical analogy dropped from the manuscript scope",
        curator="human-reviewer",
    )

    assert report.category_statuses[LOW_FPR_CATEGORY]["status"] == "waived"
    assert LOW_FPR_CATEGORY not in report.missing_categories


def test_curation_report_renders_and_cli_attach(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_real_paper("real-low-fpr")])
    manager = RelatedWorkCurationManager(config)
    manager.attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="real-low-fpr")

    rendered = render_related_work_curation_report(manager.report(benchmark_id))

    assert "# Related-Work Curation Report" in rendered
    assert "low-FPR detection/evaluation" in rendered
    assert "real-low-fpr" in rendered

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "related-work-curation-report",
            "--benchmark-id",
            benchmark_id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Related-Work Curation Report" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _attach_papers(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("selected benchmark related work curation")
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _real_paper(paper_id: str) -> Paper:
    return Paper(
        id=paper_id,
        title="Low false positive specificity evaluation for detectors",
        authors=["A. Researcher"],
        abstract="Evaluates false alarm specificity and low false positive detector behavior.",
        year=2025,
        source="arxiv",
        arxiv_id="2501.00001",
    )


def _fallback_paper(paper_id: str) -> Paper:
    return Paper(
        id=paper_id,
        title="Fallback low false positive specificity evaluation",
        authors=[],
        abstract="Fallback metadata for false alarm specificity.",
        year=2025,
        source="fixture",
        raw_metadata={"fallback": True},
        provenance=Provenance(
            created_by_skill="fixture",
            timestamp=utc_now_iso(),
            reasoning_summary="deterministic fallback paper record",
        ),
    )
