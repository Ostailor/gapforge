from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager
from gapforge.manuscript.revisions import ManuscriptRevisionManager
from gapforge.models import NoveltyDossier, Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_objection_creates_rebuttal_item(tmp_path: Path) -> None:
    config, manuscript_id = _revision_fixture(tmp_path, missing_related_work=True)

    revision = ManuscriptRebuttalManager(config).build(manuscript_id)

    assert revision.rebuttal_items
    assert any(item.reviewer_id == "R4" for item in revision.rebuttal_items)
    assert all(item.status == "open" for item in revision.rebuttal_items)


def test_missing_citation_creates_search_request(tmp_path: Path) -> None:
    config, manuscript_id = _revision_fixture(tmp_path, missing_related_work=True)

    revision = ManuscriptRevisionManager(config).build(manuscript_id)
    program = ProjectMemoryManager(config).load_project(ManuscriptManager(config).load_state(manuscript_id).manuscript.project_id)

    assert revision.required_searches
    assert program.revision_search_requests
    assert program.revision_search_requests[0].purpose == "manuscript_revision"


def test_missing_experiment_creates_experiment_request(tmp_path: Path) -> None:
    config, manuscript_id = _revision_fixture(tmp_path, result_claim_without_artifact=True)

    revision = ManuscriptRevisionManager(config).build(manuscript_id)
    program = ProjectMemoryManager(config).load_project(ManuscriptManager(config).load_state(manuscript_id).manuscript.project_id)

    assert revision.required_experiments
    assert any(task.task_type == "manuscript_revision_experiment" for task in program.experiment_code_tasks)


def test_softened_claim_suggestion_generated(tmp_path: Path) -> None:
    config, manuscript_id = _revision_fixture(tmp_path, unsupported_claim=True)

    revision = ManuscriptRebuttalManager(config).build(manuscript_id)

    assert any(item.claim_softening_needed for item in revision.rebuttal_items)
    assert any("soften" in " ".join(item.claim_softening_needed).lower() for item in revision.rebuttal_items)


def test_open_items_block_camera_ready(tmp_path: Path) -> None:
    config, manuscript_id = _revision_fixture(tmp_path, unsupported_claim=True)
    ManuscriptRevisionManager(config).build(manuscript_id)
    manager = ManuscriptManager(config)
    state = manager.load_state(manuscript_id)
    state.manuscript.status = "camera_ready"
    manager._save_state(state)

    status = ManuscriptRevisionManager(config).status(manuscript_id)
    reloaded = manager.load_state(manuscript_id)

    assert "Camera-ready allowed: false" in status
    assert reloaded.manuscript.status == "review_ready"


def test_rebuttal_revision_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id = _revision_fixture(tmp_path, unsupported_claim=True)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    rebuttal = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "rebuttal-plan", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rebuttal.returncode == 0, rebuttal.stderr
    item_id = json.loads(next((tmp_path / "projects").glob("*/manuscripts/*/reviews/rebuttal_items.json")).read_text(encoding="utf-8"))[0][
        "id"
    ]
    marked = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "mark-rebuttal-item", "--item-id", item_id, "--status", "addressed"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    revision = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "revision-plan", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "revision-status", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert marked.returncode == 0, marked.stderr
    assert revision.returncode == 0, revision.stderr
    assert status.returncode == 0, status.stderr
    assert "Rebuttal Plan" in rebuttal.stdout
    assert json.loads(marked.stdout)["status"] == "addressed"
    assert "Revision Plan" in revision.stdout
    assert "Revision Status" in status.stdout


def _revision_fixture(
    tmp_path: Path,
    *,
    missing_related_work: bool = False,
    result_claim_without_artifact: bool = False,
    unsupported_claim: bool = False,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    run = ResearchStateManager(config).create_run("revision fixture")
    run.papers = [
        Paper(
            id="paper-1",
            title="Revision Evidence",
            authors=["Ada Lovelace"],
            abstract="Revision evidence.",
            year=2025,
            venue="ICLR",
            doi="10.1000/revision",
        )
    ]
    run.novelty_dossiers.append(
        NoveltyDossier(
            target_id="direction-revision",
            idea_summary="Revision workflow.",
            top_prior_work=["paper-1"],
            verdict="pursue",
            novelty_strength="moderate",
        )
    )
    ResearchStateManager(config).save_run(run)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Revision Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-revision")
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-revision",
        workspace_id=workspace.id,
        title="Revision Draft",
    )
    section_ids: dict[str, str] = {}
    for section_type in ["abstract", "introduction", "method", "results", "limitations", "ethics", "conclusion"]:
        section = manager.create_section(manuscript_id=state.manuscript.id, section_type=section_type, title=section_type.title())
        section_ids[section_type] = section.id
    if not missing_related_work:
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
            claim_text="Prior work motivates revision planning.",
            use_type="background",
            support_status="supported",
            evidence_locators=["paper-1:p1"],
        )
    if result_claim_without_artifact:
        manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=section_ids["results"],
            claim_id="claim-result",
            claim_text="The method improves accuracy.",
            use_type="result",
            support_status="supported",
            evidence_locators=["paper-1:p2"],
        )
    if unsupported_claim:
        manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=section_ids["method"],
            claim_id="claim-unsupported",
            claim_text="The method definitively solves rebuttal writing.",
            use_type="method",
            support_status="unsupported",
        )
    return config, state.manuscript.id
