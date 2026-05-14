from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.drastic_rebuttal import DrasticRevisionManager
from gapforge.models import Paper, RelatedWorkMatrix
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_fatal_review_creates_fatal_fix(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_revision_fixture(tmp_path, missing_related_work=True)

    plan = DrasticRevisionManager(config).build(manuscript_id)

    assert plan.fatal_fixes
    assert any("missing:related_work" in fix for fix in plan.fatal_fixes)
    assert plan.status == "fatal_blockers_open"


def test_missing_experiment_creates_experiment_request(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_revision_fixture(tmp_path)

    plan = DrasticRevisionManager(config).build(manuscript_id)
    state = ManuscriptManager(config).load_state(manuscript_id)
    program = ProjectMemoryManager(config).load_project(state.manuscript.project_id)

    assert plan.new_experiments_required
    assert any(task.task_type == "drastic_revision_experiment" for task in program.experiment_code_tasks)
    assert all("invent" not in task.instructions.lower() for task in program.experiment_code_tasks)


def test_missing_related_work_creates_search_request(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_revision_fixture(tmp_path, missing_related_work=True)

    plan = DrasticRevisionManager(config).build(manuscript_id)
    state = ManuscriptManager(config).load_state(manuscript_id)
    program = ProjectMemoryManager(config).load_project(state.manuscript.project_id)

    assert plan.new_related_work_required
    assert program.revision_search_requests
    assert program.revision_search_requests[0].purpose == "drastic_revision_related_work"


def test_claim_softening_generated(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_revision_fixture(tmp_path, unsupported_claim=True)

    plan = DrasticRevisionManager(config).build(manuscript_id)
    state = ManuscriptManager(config).load_state(manuscript_id)

    assert plan.claim_softening_required
    assert any(claim.requires_softening for claim in state.claim_uses)


def test_publication_status_downgraded_if_blockers_remain(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_revision_fixture(tmp_path, missing_related_work=True)
    manager = ManuscriptManager(config)
    state = manager.load_state(manuscript_id)
    state.manuscript.status = "submission_ready"
    manager._save_state(state)

    DrasticRevisionManager(config).build(manuscript_id)
    reloaded = manager.load_state(manuscript_id)

    assert reloaded.manuscript.status == "review_ready"


def test_drastic_revision_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id = _drastic_revision_fixture(tmp_path, unsupported_claim=True)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    plan = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "drastic-revision-plan", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    dry_run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "apply-drastic-revision", "--manuscript-id", manuscript_id, "--dry-run"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "drastic-revision-status", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    root = next((tmp_path / "projects").glob("*/manuscripts/*"))

    assert plan.returncode == 0, plan.stderr
    assert dry_run.returncode == 0, dry_run.stderr
    assert status.returncode == 0, status.stderr
    assert "Drastic Revision Plan" in plan.stdout
    assert "Drastic Revision Plan" in dry_run.stdout
    assert "Drastic Revision Status" in status.stdout
    assert (root / "reviews" / "drastic" / "drastic_revision_plan.json").exists()
    assert (root / "reviews" / "drastic" / "drastic_revision_status.md").exists()


def _drastic_revision_fixture(
    tmp_path: Path,
    *,
    missing_related_work: bool = False,
    unsupported_claim: bool = False,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("drastic revision fixture")
    run.papers = [
        Paper(
            id="paper-drastic-revision",
            title="Drastic Revision Evidence",
            authors=["Ada Lovelace"],
            abstract="Revision fixture.",
            year=2025,
            venue="FixtureConf",
        )
    ]
    if not missing_related_work:
        run.related_work_matrices.append(
            RelatedWorkMatrix(
                direction_id="direction-drastic-revision",
                coverage_summary="Closest prior work is tracked.",
                must_read_paper_ids=["paper-drastic-revision"],
                baseline_paper_ids=["paper-drastic-revision"],
            )
        )
    state_manager.save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Drastic Revision Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-drastic-revision",
    )
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-drastic-revision",
        workspace_id=workspace.id,
        title="Drastic Revision Draft",
    )
    root = manager.manuscript_root(state.manuscript.id)
    section_ids: dict[str, str] = {}
    section_text = {
        "abstract": "We study sequential specificity for low-FPR collusion audits.",
        "introduction": "This paper contribution is a benchmark protocol for sequential specificity.",
        "method": "The method uses vetted benchmark adapters and synthetic protocol scaffolding.",
        "results": "Results report specificity, uncertainty, power, ablation evidence, and baseline monitors.",
        "limitations": "Limitations include synthetic data validity and benchmark adaptation boundaries.",
        "ethics": "Safety risks and misuse boundaries are discussed.",
        "conclusion": "The protocol is positioned as measurement evidence, not deployment validation.",
    }
    if not missing_related_work:
        section_text["related_work"] = "Closest prior work and benchmark baselines are compared."

    for section_type, text in section_text.items():
        section = manager.create_section(manuscript_id=state.manuscript.id, section_type=section_type, title=section_type.title())
        section_ids[section_type] = section.id
        (root / section.content_path).write_text(f"# {section.title}\n\n{text}\n", encoding="utf-8")

    manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_ids["introduction"],
        claim_id="claim-contribution",
        claim_text="The manuscript contributes a traceable drastic revision workflow.",
        use_type="novelty",
        support_status="supported",
        evidence_locators=["paper-drastic-revision:p1"] if not missing_related_work else [],
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
