from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.models import Paper, RelatedWorkMatrix
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.drastic_panel import DrasticReviewPanelBuilder, validate_review_text_no_fake_citations
from gapforge.state import ResearchStateManager


def test_missing_related_work_triggers_novelty_skeptic(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, related_work=False)

    panel = DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)
    novelty = next(review for review in panel.reviewer_reports if review.reviewer_id == "R1")

    assert "novelty skeptic" in novelty.role
    assert any("missing:related_work" in flaw for flaw in novelty.fatal_flaws)
    assert any("missing:related_work_matrix" in flaw for flaw in novelty.fatal_flaws)
    assert panel.likely_decision == "reject_likely"


def test_weak_baseline_triggers_empirical_reviewer(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, baseline=False)

    panel = DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)
    empirical = next(review for review in panel.reviewer_reports if review.reviewer_id == "R2")

    assert "empirical rigor" in empirical.role
    assert any("missing:baseline" in weakness for weakness in empirical.weaknesses)
    assert any("baseline" in fix for fix in empirical.required_fixes)


def test_synthetic_only_benchmark_triggers_benchmark_reviewer(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)

    panel = DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)
    benchmark = next(review for review in panel.reviewer_reports if review.reviewer_id == "R3")

    assert "benchmark validity" in benchmark.role
    assert any("synthetic-only" in flaw for flaw in benchmark.fatal_flaws)
    assert any("protocol scaffolding" in fix for fix in benchmark.required_fixes)


def test_fake_citation_in_review_blocked() -> None:
    with pytest.raises(ValueError, match="citation-shaped"):
        validate_review_text_no_fake_citations("This appears to follow Smith et al. 2024 without evidence.")


def test_drastic_review_report_renders_and_cli_outputs(tmp_path: Path) -> None:
    _config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    review = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "drastic-review", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "drastic-review-report", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    root = next((tmp_path / "projects").glob("*/manuscripts/*"))

    assert review.returncode == 0, review.stderr
    assert report.returncode == 0, report.stderr
    assert "Drastic Review Panel" in review.stdout
    assert "Likely decision" in report.stdout
    assert (root / "reviews" / "drastic" / "drastic_review_panel.json").exists()
    assert (root / "reviews" / "drastic" / "fatal_flaws.md").exists()
    assert (root / "reviews" / "drastic" / "borderline_decision_analysis.md").exists()
    assert (root / "reviews" / "drastic" / "required_revision_plan.md").exists()
    assert (root / "reviews" / "drastic" / "likely_scores.json").exists()


def _drastic_manuscript_fixture(
    tmp_path: Path,
    *,
    related_work: bool = True,
    baseline: bool = True,
    synthetic_only: bool = False,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("drastic reviewer fixture")
    run.papers = [
        Paper(
            id="paper-drastic",
            title="Calibration Fixture",
            authors=["Ada Lovelace"],
            abstract="Review calibration fixture.",
            year=2025,
            venue="FixtureConf",
        )
    ]
    if related_work:
        run.related_work_matrices.append(
            RelatedWorkMatrix(
                direction_id="direction-drastic",
                coverage_summary="Closest prior work is tracked.",
                must_read_paper_ids=["paper-drastic"],
                baseline_paper_ids=["paper-drastic"] if baseline else [],
            )
        )
    state_manager.save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Drastic Review Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-drastic")

    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-drastic",
        workspace_id=workspace.id,
        title="Drastic Review Draft",
    )
    root = manager.manuscript_root(state.manuscript.id)
    section_text = {
        "abstract": "We study sequential specificity for low-FPR collusion audits.",
        "introduction": "This paper contribution is a benchmark protocol for sequential specificity.",
        "method": (
            "The method uses synthetic benchmark traces for sequential false-positive evaluation."
            if synthetic_only
            else "The method uses vetted benchmark adapters and synthetic protocol scaffolding."
        ),
        "results": "Results report specificity, uncertainty, power, and ablation evidence.",
        "limitations": "Limitations include synthetic data validity and benchmark adaptation boundaries.",
        "ethics": "Safety risks and misuse boundaries are discussed.",
        "conclusion": "The protocol is positioned as measurement evidence, not deployment validation.",
    }
    if baseline:
        section_text["results"] += " Baseline monitors are compared."
    if related_work:
        section_text["related_work"] = (
            "Closest prior work and benchmark baselines are compared."
            if baseline
            else "Closest prior work is discussed, but no comparator methods are enumerated."
        )

    for section_type, text in section_text.items():
        section = manager.create_section(manuscript_id=state.manuscript.id, section_type=section_type, title=section_type.title())
        path = root / section.content_path
        path.write_text(f"# {section.title}\n\n{text}\n", encoding="utf-8")

    return config, state.manuscript.id
