from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.reviewer_panel import ManuscriptReviewPanelBuilder, render_manuscript_review_panel_markdown
from gapforge.models import NoveltyDossier, Paper, RelatedWorkMatrix
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_missing_related_work_flagged(tmp_path: Path) -> None:
    config, manuscript_id = _review_fixture(tmp_path, related_work=False)

    panel = ManuscriptReviewPanelBuilder(config).review(manuscript_id)
    related = next(review for review in panel.reviewer_reports if review.role == "related-work reviewer")

    assert any("Related-work section is missing" in flaw for flaw in related.fatal_flaws)
    assert any("related-work section" in fix for fix in related.required_fixes)
    assert related.evidence_or_prior_work == []


def test_unsupported_claim_is_fatal(tmp_path: Path) -> None:
    config, manuscript_id = _review_fixture(tmp_path, unsupported_claim=True)

    panel = ManuscriptReviewPanelBuilder(config).review(manuscript_id)

    assert any("Soften the claim" in fix or "Add evidence" in fix for fix in panel.required_fixes)
    assert panel.fatal_flaws
    assert "unsupported" in render_manuscript_review_panel_markdown(panel).lower()


def test_missing_artifact_package_major_or_fatal(tmp_path: Path) -> None:
    config, manuscript_id = _review_fixture(tmp_path)

    panel = ManuscriptReviewPanelBuilder(config).review(manuscript_id)
    reproducibility = next(review for review in panel.reviewer_reports if review.role == "reproducibility/artifact reviewer")

    assert any("No artifact evaluation package" in flaw for flaw in reproducibility.fatal_flaws)
    assert any("Export an artifact evaluation package" in fix for fix in reproducibility.required_fixes)


def test_rebuttal_plan_generated_without_fake_answers(tmp_path: Path) -> None:
    config, manuscript_id = _review_fixture(tmp_path, unsupported_claim=True)

    panel = ManuscriptReviewPanelBuilder(config).review(manuscript_id)

    assert panel.rebuttal_plan
    assert any("do not invent results" in plan.response_strategy for plan in panel.rebuttal_plan)
    assert all("claim" not in " ".join(plan.experiments_to_add).lower() for plan in panel.rebuttal_plan)


def test_review_report_renders_and_cli_outputs(tmp_path: Path) -> None:
    _config, manuscript_id = _review_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    review = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-review", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    meta = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-meta-review", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    fixes = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-fix-list", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    root = next((tmp_path / "projects").glob("*/manuscripts/*"))

    assert review.returncode == 0, review.stderr
    assert meta.returncode == 0, meta.stderr
    assert fixes.returncode == 0, fixes.stderr
    assert "Manuscript Review Panel" in review.stdout
    assert "should not be submitted" in meta.stdout
    assert "Manuscript Fix List" in fixes.stdout
    assert (root / "reviews" / "manuscript_review_panel.json").exists()
    assert json.loads((root / "reviews" / "manuscript_review_panel.json").read_text(encoding="utf-8"))["rebuttal_plan"]


def _review_fixture(
    tmp_path: Path,
    *,
    related_work: bool = True,
    unsupported_claim: bool = False,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("manuscript reviewer fixture")
    run.papers = [
        Paper(
            id="paper-1",
            title="Traceable Manuscript Review",
            authors=["Ada Lovelace"],
            abstract="Reviewer evidence.",
            year=2025,
            venue="ICLR",
            doi="10.1000/review",
        )
    ]
    run.novelty_dossiers.append(
        NoveltyDossier(
            target_id="direction-review",
            idea_summary="Traceable manuscript reviewer panel.",
            top_prior_work=["paper-1"],
            verdict="pursue",
            novelty_strength="moderate",
        )
    )
    if related_work:
        run.related_work_matrices.append(
            RelatedWorkMatrix(
                direction_id="direction-review",
                coverage_summary="Closest prior work covered.",
                must_read_paper_ids=["paper-1"],
                baseline_paper_ids=["paper-1"],
            )
        )
    state_manager.save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Manuscript Review Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-review")
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-review",
        workspace_id=workspace.id,
        title="Manuscript Review Draft",
    )
    section_ids: dict[str, str] = {}
    for section_type in ["abstract", "introduction", "method", "results", "limitations", "ethics", "conclusion"]:
        section = manager.create_section(manuscript_id=state.manuscript.id, section_type=section_type, title=section_type.title())
        section_ids[section_type] = section.id
    if related_work:
        section = manager.create_section(
            manuscript_id=state.manuscript.id,
            section_type="related_work",
            title="Related Work",
            source_paper_ids=["paper-1"],
        )
        section_ids["related_work"] = section.id
        manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=section.id,
            claim_id="claim-background",
            claim_text="Prior work motivates reviewer simulation.",
            use_type="background",
            support_status="supported",
            evidence_locators=["paper-1:p1"],
        )
        ManuscriptBibliographyManager(config).build(state.manuscript.id)
    manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_ids["introduction"],
        claim_id="claim-novelty",
        claim_text="The manuscript contributes a traceable reviewer panel.",
        use_type="novelty",
        support_status="supported",
        evidence_locators=["paper-1:p2"] if related_work else [],
    )
    if unsupported_claim:
        manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=section_ids["method"],
            claim_id="claim-unsupported",
            claim_text="The manuscript definitively solves reviewer rebuttals.",
            use_type="method",
            support_status="unsupported",
        )
    return config, state.manuscript.id
