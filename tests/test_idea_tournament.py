from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaStore, IdeaTournamentRunner
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_best_viable_candidate_selected(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _attach_run(config, project_id, [Paper(id="paper-prior", title="Prior monitor benchmark", authors=[], abstract="", year=2025)])
    store = IdeaStore(config)
    weak = _candidate(config, project_id, title="Lower impact measurement", impact=0.45, yield_score=0.45)
    best = _candidate(
        config,
        project_id,
        title="Specificity-first benchmark for collusion auditing",
        contribution_type="benchmark",
        evidence=0.7,
        tractability=0.8,
        impact=0.85,
        yield_score=0.9,
        closest_prior_work_ids=["paper-prior"],
    )
    store.link_evidence(idea_id=best.id, link_type="supports", paper_id="paper-prior", note="Known prior-work anchor.")

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    state = IdeaStore(config).load_state(project_id)

    assert tournament.selected_candidate_id == best.id
    assert weak.id in tournament.candidate_ids
    assert state.idea_bank is not None
    assert state.idea_bank.selected_candidate_id == best.id
    selected = next(candidate for candidate in state.candidates if candidate.id == best.id)
    assert selected.human_feedback_ids


def test_fake_citation_candidate_disqualified(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _attach_run(config, project_id, [Paper(id="paper-real", title="Real prior", authors=[], abstract="", year=2025)])
    fake = _candidate(
        config,
        project_id,
        title="High scoring fake citation idea",
        evidence=1.0,
        tractability=1.0,
        impact=1.0,
        yield_score=1.0,
        closest_prior_work_ids=["paper-fake"],
    )
    viable = _candidate(
        config,
        project_id,
        title="Viable low-FPR evaluation protocol",
        contribution_type="evaluation_protocol",
        evidence=0.55,
        tractability=0.7,
        impact=0.65,
        yield_score=0.7,
        closest_prior_work_ids=["paper-real"],
    )

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    fake_record = next(record for record in tournament.score_records if record.idea_id == fake.id)

    assert tournament.selected_candidate_id == viable.id
    assert fake.id in tournament.rejected_candidate_ids
    assert any("fake citation" in blocker or "unresolved" in blocker for blocker in fake_record.blockers)


def test_fatal_novelty_candidate_disqualified(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _attach_run(config, project_id, [Paper(id="paper-prior", title="Real prior", authors=[], abstract="", year=2025)])
    fatal = _candidate(
        config,
        project_id,
        title="Likely duplicate low-FPR benchmark",
        evidence=1.0,
        tractability=1.0,
        impact=1.0,
        yield_score=1.0,
        novelty_status="likely_duplicate",
        closest_prior_work_ids=["paper-prior"],
    )
    viable = _candidate(
        config,
        project_id,
        title="Measurement study of honest multi-agent false positives",
        contribution_type="measurement",
        evidence=0.5,
        tractability=0.75,
        impact=0.7,
        yield_score=0.72,
        closest_prior_work_ids=["paper-prior"],
    )

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    fatal_record = next(record for record in tournament.score_records if record.idea_id == fatal.id)

    assert tournament.selected_candidate_id == viable.id
    assert fatal.id in tournament.rejected_candidate_ids
    assert "fatal novelty blocker" in fatal_record.blockers


def test_no_viable_idea_creates_agenda(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _candidate(config, project_id, title="Research idea", closest_prior_work_ids=["paper-missing"], yield_score=0.9)

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    state = IdeaStore(config).load_state(project_id)
    program = ProjectMemoryManager(config).load_project(project_id)

    assert tournament.selected_candidate_id == ""
    assert tournament.agenda_id
    assert state.idea_bank is not None
    assert state.idea_bank.agenda_id == tournament.agenda_id
    assert any(direction.id == tournament.agenda_id and direction.maturity == "agenda_item" for direction in program.research_directions)


def test_idea_tournament_report_and_cli_render(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _attach_run(config, project_id, [Paper(id="paper-prior", title="Real prior", authors=[], abstract="", year=2025)])
    selected = _candidate(config, project_id, title="Benchmark availability candidate", closest_prior_work_ids=["paper-prior"])

    report = IdeaTournamentRunner(config).run(project_id, top_k=5)
    rendered = IdeaTournamentRunner(config).write_report(project_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    selected_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-idea", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    score_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-score-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.selected_candidate_id == selected.id
    assert "# Idea Tournament Report" in rendered
    assert "Benchmark availability candidate" not in rendered
    assert selected_cli.returncode == 0, selected_cli.stderr
    assert json.loads(selected_cli.stdout)["id"] == selected.id
    assert score_cli.returncode == 0, score_cli.stderr
    assert "Idea Tournament Report" in score_cli.stdout


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Tournament Project")
    program.provenance.append(
        Provenance(created_by_skill="test", timestamp=utc_now_iso(), reasoning_summary="Test fixture project for tournament.")
    )
    manager.save_project(program)
    return config, program.project.id


def _candidate(
    config: GapForgeConfig,
    project_id: str,
    *,
    title: str,
    contribution_type: str = "benchmark",
    evidence: float = 0.45,
    tractability: float = 0.6,
    impact: float = 0.6,
    yield_score: float = 0.6,
    novelty_status: str = "plausible",
    closest_prior_work_ids: list[str] | None = None,
):
    store = IdeaStore(config)
    if store.load_state(project_id).idea_bank is None:
        store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    return store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-low-fpr",
        title=title,
        summary="A scoped idea for low false-positive collusion detection that does not claim experimental results.",
        contribution_type=contribution_type,
        core_claim="The contribution is plausible but still requires evidence-gated validation.",
        proposed_experiment="Compare monitor baselines on benign and collusive multi-agent traces.",
        expected_baselines=["LLM judge", "rule monitor"],
        expected_metrics=["false positive rate", "recall"],
        closest_prior_work_ids=closest_prior_work_ids or [],
        novelty_status=novelty_status,
        tractability_score=tractability,
        impact_score=impact,
        evidence_score=evidence,
        reviewer_risk_score=0.25,
        idea_yield_score=yield_score,
        maturity="candidate",
    )


def _attach_run(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)
