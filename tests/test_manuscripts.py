from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.models import ManuscriptClaimUse, ManuscriptSection
from gapforge.models import Claim, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso


def test_create_manuscript_persists_project_artifact(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ManuscriptManager(config)

    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Traceable Manuscript",
    )

    manuscript = state.manuscript
    root = Path(manager.manuscript_root(manuscript.id))

    assert manuscript.project_id == project_id
    assert manuscript.status == "planned"
    assert root == config.project_root / project_id / "manuscripts" / manuscript.id
    assert (root / "manuscript.json").exists()
    assert (root / "sections").is_dir()
    assert (root / "artifact_evaluation").is_dir()
    assert "Created first-class manuscript project state" in manuscript.provenance.reasoning_summary


def test_load_manuscript_state_round_trips(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ManuscriptManager(config)
    created = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Durable Draft",
        campaign_id="campaign-1",
        target_venue="ICLR",
    )

    loaded = manager.load_state(created.manuscript.id)

    assert loaded.manuscript.id == created.manuscript.id
    assert loaded.manuscript.campaign_id == "campaign-1"
    assert loaded.manuscript.target_venue == "ICLR"
    assert loaded.sections == []
    assert loaded.claim_uses == []


def test_create_section_links_claims_results_and_artifacts(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Traceable Draft",
    )

    section = manager.create_section(
        manuscript_id=state.manuscript.id,
        section_type="experiments",
        title="Experiments",
        source_claim_ids=["claim-1"],
        source_paper_ids=["paper-1"],
        source_result_ids=["result-1"],
        source_artifact_ids=["artifact-1"],
        warnings=["Pilot result only."],
    )
    reloaded = manager.load_state(state.manuscript.id)

    assert isinstance(section, ManuscriptSection)
    assert section.content_path == f"sections/{section.id}.md"
    assert section.source_claim_ids == ["claim-1"]
    assert section.source_paper_ids == ["paper-1"]
    assert section.source_result_ids == ["result-1"]
    assert section.source_artifact_ids == ["artifact-1"]
    assert reloaded.sections[0].id == section.id
    assert (Path(manager.manuscript_root(state.manuscript.id)) / section.content_path).exists()


def test_link_claim_use_updates_section_without_replacing_evidence_state(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(project_id)
    claim = Claim(
        id="claim-1",
        text="The method reduces unsupported manuscript claims.",
        type="method",
        status="supported",
        source_paper_ids=["paper-1"],
    )
    program.claim_graph = None
    project_manager.save_project(program)
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Evidence Boundary",
    )
    section = manager.create_section(manuscript_id=state.manuscript.id, section_type="method", title="Method")

    use = manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section.id,
        claim_id=claim.id,
        claim_text=claim.text,
        use_type="method",
        support_status=claim.status,
        evidence_locators=["paper-1:p3"],
        citation_keys=["paper1"],
        requires_softening=False,
    )
    reloaded = manager.load_state(state.manuscript.id)
    loaded_project = project_manager.load_project(project_id)

    assert isinstance(use, ManuscriptClaimUse)
    assert reloaded.claim_uses[0].claim_id == "claim-1"
    assert reloaded.sections[0].source_claim_ids == ["claim-1"]
    assert reloaded.sections[0].source_paper_ids == ["paper-1"]
    assert loaded_project.claim_graph is None


def test_manuscript_report_renders(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Reportable Draft",
    )
    section = manager.create_section(manuscript_id=state.manuscript.id, section_type="abstract", title="Abstract")
    manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section.id,
        claim_id="claim-1",
        claim_text="A cautiously stated result claim.",
        use_type="result",
        support_status="unsupported",
        requires_softening=True,
    )

    report = manager.write_report(state.manuscript.id)

    assert "# Manuscript `manuscript-reportable-draft`" in report
    assert "Sections: 1" in report
    assert "Claim uses: 1" in report
    assert "requires softening" in report
    assert "does not replace evidence state" in report


def test_manuscript_cli_create_status_sections_report(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-create",
            "--project-id",
            project_id,
            "--direction-id",
            "direction-1",
            "--workspace-id",
            "workspace-1",
            "--title",
            "CLI Draft",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    manuscript_id = json.loads(created.stdout)["manuscript"]["id"]

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-status", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    sections = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-sections", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-report", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status.returncode == 0, status.stderr
    assert sections.returncode == 0, sections.stderr
    assert report.returncode == 0, report.stderr
    assert "CLI Draft" in status.stdout
    assert json.loads(sections.stdout) == []
    assert "# Manuscript `manuscript-cli-draft`" in report.stdout


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Manuscript Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for manuscript state.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
