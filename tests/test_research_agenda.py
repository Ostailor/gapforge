from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaStore, IdeaTournamentRunner, ResearchAgendaManager
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_agenda_generated_when_no_idea_passes(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    blocked = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-blocked",
        title="Research idea",
        summary="Generic idea without executable evidence.",
        contribution_type="method",
        novelty_status="weak",
        closest_prior_work_ids=["paper-missing"],
        idea_yield_score=0.8,
    )

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    state = IdeaStore(config).load_state(project_id)

    assert tournament.selected_candidate_id == ""
    assert tournament.agenda_id
    assert state.idea_bank is not None
    assert state.idea_bank.agenda_id == tournament.agenda_id
    assert any(agenda.id == tournament.agenda_id for agenda in state.agendas)
    assert blocked.id in state.idea_bank.rejected_candidate_ids


def test_agenda_includes_blockers_and_decision_points(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-rejected",
        title="Duplicate low-FPR monitor",
        summary="Prior work appears to solve the core idea.",
        contribution_type="measurement",
        novelty_status="likely_duplicate",
    )
    store.reject_candidate(candidate.id, "fatal prior work overlaps the decisive measurement claim")

    agenda = ResearchAgendaManager(config).generate(project_id)

    assert "fatal prior work" in agenda.blocker_summary
    assert agenda.decision_points
    assert agenda.stop_conditions
    assert all(step.required_artifact for step in agenda.agenda_steps)
    assert all(step.next_decision for step in agenda.agenda_steps)


def test_agenda_to_campaigns_creates_planned_campaigns(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    agenda = ResearchAgendaManager(config).generate(
        project_id,
        blocker_summary="No candidate passed novelty and evidence gates.",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    campaigns = ResearchAgendaManager(config).agenda_to_campaigns(agenda.id)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agenda-to-campaigns", "--agenda-id", agenda.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    program = ProjectMemoryManager(config).load_project(project_id)

    assert campaigns
    assert all(campaign.campaign.status == "planned" for campaign in campaigns)
    assert {campaign.campaign.id for campaign in campaigns}.issubset({campaign.id for campaign in program.campaigns})
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)


def test_agenda_report_renders_and_cli(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    agenda = ResearchAgendaManager(config).generate(
        project_id,
        blocker_summary="No idea is defensible until baseline and benchmark artifacts exist.",
    )

    rendered = ResearchAgendaManager(config).write_report(agenda.id)
    report_path = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "reports" / "research_agenda.md"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agenda-report", "--agenda-id", agenda.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "# Research Agenda" in rendered
    assert "not a paper idea" in rendered
    assert report_path.exists()
    assert cli.returncode == 0, cli.stderr
    assert "Research Agenda" in cli.stdout


def test_research_agenda_cli_creates_persisted_agenda(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "research-agenda", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    state = IdeaStore(config).load_state(project_id)
    agenda = json.loads(cli.stdout)

    assert cli.returncode == 0, cli.stderr
    assert agenda["id"]
    assert state.agendas
    assert state.agendas[-1].id == agenda["id"]


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Research Agenda Project", description=LOW_FPR_TOPIC)
    program.provenance.append(
        Provenance(created_by_skill="test", timestamp=utc_now_iso(), reasoning_summary="Test fixture project for research agenda.")
    )
    manager.save_project(program)
    return config, program.project.id
