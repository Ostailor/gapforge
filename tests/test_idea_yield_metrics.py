from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaMutationEngine, IdeaStore, IdeaYieldMetricCalculator, ResearchAgendaManager
from gapforge.ideas.models import IdeaScoreRecord, IdeaTournament, IdeaTransferCandidate
from gapforge.ideas.topic_portfolio import TopicPortfolioGenerator
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_idea_yield_metrics_computed(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    accepted = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-accepted",
        title="Sequential specificity benchmark for collusion audits",
        summary="Specific benchmark candidate.",
        contribution_type="benchmark",
        closest_prior_work_ids=["paper-known"],
        novelty_status="plausible",
        evidence_score=0.6,
    )
    duplicate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-duplicate",
        title="Duplicate collusion monitor",
        summary="Duplicate candidate.",
        contribution_type="method",
        novelty_status="likely_duplicate",
    )
    generic = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-generic",
        title="Research idea",
        summary="Generic idea.",
        contribution_type="method",
    )
    store.reject_candidate(duplicate.id, "duplicate: fatal prior work already solves this")
    store.reject_candidate(generic.id, "generic idea")
    IdeaMutationEngine(config).mutate_rejected_ideas(project_id)
    store.link_evidence(idea_id=accepted.id, link_type="supports", paper_id="paper-known")
    state = store.load_state(project_id)
    state.transfer_candidates.append(
        IdeaTransferCandidate(
            id="transfer-yield",
            source_field="medicine screening/specificity",
            source_concept="specificity",
            target_problem=LOW_FPR_TOPIC,
            transfer_mechanism="Use specificity thresholds to control false-positive alerts.",
            what_breaks="Collusion labels are noisier.",
        )
    )
    state.tournaments.append(
        IdeaTournament(
            id="tournament-yield",
            project_id=project_id,
            candidate_ids=[accepted.id, duplicate.id, generic.id],
            score_records=[
                IdeaScoreRecord(idea_id=accepted.id, total_score=0.8, blockers=[]),
                IdeaScoreRecord(idea_id=duplicate.id, total_score=0.0, blockers=["fatal novelty blocker"]),
            ],
            selected_candidate_id=accepted.id,
            rejected_candidate_ids=[duplicate.id],
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    store._save_state(project_id, state)
    IdeaFeedbackManager(config).add_feedback(idea_id=accepted.id, action="accept", reviewer="fixture", rationale="Accept candidate.")

    metrics = IdeaYieldMetricCalculator(config).compute(project_id)

    assert metrics.topic_variant_count > 0
    assert metrics.candidate_count >= 3
    assert metrics.mutation_count >= 2
    assert metrics.cross_domain_transfer_count == 1
    assert metrics.rejected_duplicate_count == 1
    assert metrics.rejected_generic_count == 1
    assert metrics.tournament_survivor_count == 1
    assert metrics.human_accepted_idea_count == 1
    assert metrics.idea_yield_rate > 0
    assert metrics.evidence_per_candidate > 0
    assert metrics.prior_work_per_candidate > 0


def test_zero_accepted_ideas_reported(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store.add_candidate(
        project_id=project_id,
        source_topic_id="topic",
        title="Specific but unsupported collusion audit",
        summary="No human acceptance yet.",
        contribution_type="measurement",
        novelty_status="unknown",
    )

    metrics = IdeaYieldMetricCalculator(config).compute(project_id)
    report = IdeaYieldMetricCalculator(config).render_report(project_id)

    assert metrics.human_accepted_idea_count == 0
    assert metrics.idea_yield_rate == 0.0
    assert "No human-accepted idea is recorded" in report


def test_agenda_fallback_counted(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    ResearchAgendaManager(config).generate(project_id, blocker_summary="No candidate passed the tournament.")

    metrics = IdeaYieldMetricCalculator(config).compute(project_id)

    assert metrics.agenda_generated is True
    assert metrics.agenda_id
    assert metrics.human_accepted_idea_count == 0


def test_idea_yield_report_renders_and_cli(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store.add_candidate(
        project_id=project_id,
        source_topic_id="topic",
        title="Measurement study for low-FPR collusion auditing",
        summary="Specific candidate for report rendering.",
        contribution_type="measurement",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    cli_json = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-yield", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    cli_report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-yield", "--project-id", project_id, "--write-report"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_path = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "reports" / "idea_yield.md"

    assert cli_json.returncode == 0, cli_json.stderr
    assert json.loads(cli_json.stdout)["candidate_count"] == 1
    assert cli_report.returncode == 0, cli_report.stderr
    assert "# Idea Yield Metrics" in cli_report.stdout
    assert report_path.exists()


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Yield Project", description=LOW_FPR_TOPIC)
    manager.save_project(program)
    return config, program.project.id
