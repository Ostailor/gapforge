from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaSearchController, IdeaStore, TopicPortfolioGenerator
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_idea_search_no_portfolio_generates_portfolio(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    result = IdeaSearchController(config).run(project_id, max_iterations=1)
    state = IdeaStore(config).load_state(project_id)
    portfolios = TopicPortfolioGenerator(config).list_project_portfolios(project_id)

    assert result.decisions[0].decision_type == "generate_portfolio"
    assert portfolios
    assert state.search_decisions[0].decision_type == "generate_portfolio"
    assert state.search_decisions[0].status == "complete"


def test_idea_search_weak_ideas_mutate(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    idea_store = IdeaStore(config)
    idea_store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    weak = idea_store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-generic",
        title="Research idea",
        summary="A generic monitor idea without decisive evidence.",
        contribution_type="method",
        novelty_status="weak",
        idea_yield_score=0.0,
        likely_failure_mode="generic and likely already covered",
    )

    result = IdeaSearchController(config).run(project_id, max_iterations=1)
    state = IdeaStore(config).load_state(project_id)

    assert result.decisions[0].decision_type == "mutate_ideas"
    assert any(record.source_idea_id == weak.id for record in state.mutations)
    assert any(candidate.id != weak.id for candidate in state.candidates)
    assert state.constructive_gaps


def test_idea_search_no_surviving_candidates_creates_agenda(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    IdeaStore(config).create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    result = IdeaSearchController(config).run(project_id, max_iterations=1)
    state = IdeaStore(config).load_state(project_id)
    program = ProjectMemoryManager(config).load_project(project_id)

    assert result.decisions[0].decision_type == "create_agenda"
    assert state.idea_bank is not None
    assert state.idea_bank.agenda_id
    assert any(
        direction.id == state.idea_bank.agenda_id and direction.maturity == "agenda_item" for direction in program.research_directions
    )


def test_idea_search_surviving_candidates_run_tournament(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    idea_store = IdeaStore(config)
    idea_store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    for index in range(2):
        idea_store.add_candidate(
            project_id=project_id,
            source_topic_id=f"topic-survivor-{index}",
            title=f"Low false-positive audit protocol candidate {index}",
            summary="Specificity-first collusion auditing candidate with closest prior work anchors.",
            contribution_type="evaluation_protocol",
            evidence_score=0.4,
            novelty_status="plausible",
            reviewer_risk_score=0.4,
            idea_yield_score=0.6,
            maturity="candidate",
        )

    result = IdeaSearchController(config).run(project_id, max_iterations=1)
    state = IdeaStore(config).load_state(project_id)

    assert result.decisions[0].decision_type == "run_tournament"
    assert state.tournaments
    assert state.tournaments[-1].selected_candidate_id


def test_idea_search_decisions_persist_and_cli_renders(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    IdeaSearchController(config).run(project_id, max_iterations=1)
    state = IdeaStore(config).load_state(project_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    assert len(state.search_decisions) == 1
    path = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "search_decisions.json"
    assert json.loads(path.read_text(encoding="utf-8"))[0]["decision_type"] == "generate_portfolio"

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-search-status", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert "# Idea Search Status" in status.stdout

    decisions = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-search-decisions", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert decisions.returncode == 0, decisions.stderr
    assert "generate_portfolio" in decisions.stdout


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Search Controller Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for active idea search.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
