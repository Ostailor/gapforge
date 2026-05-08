from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaStore, IdeaTournamentRunner, SelectedIdeaProjectManager
from gapforge.ideas.models import IdeaScoreRecord, IdeaTournament
from gapforge.models import Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"
SELECTED_IDEA_ID = "idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits"
SELECTED_TITLE = "Sequential specificity benchmark for low-FPR collusion audits"
CANONICAL_QUESTION = "Can a sequential benchmark evaluate collusion monitors at operationally meaningful low false-positive rates?"


def test_selected_idea_lock_created(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    selected = _selected_candidate(config, project_id)
    IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="human", rationale="Advance to v2.1.")
    IdeaTournamentRunner(config).run(project_id, top_k=5)

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-idea-lock",
            "--idea-id",
            selected.id,
            "--locked-by",
            "release-manager",
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    lock = json.loads(cli.stdout)
    lock_path = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "selected_idea_lock.json"
    snapshot_path = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "selected_idea_snapshot.json"

    assert cli.returncode == 0, cli.stderr
    assert lock["idea_id"] == SELECTED_IDEA_ID
    assert lock["locked_by"] == "release-manager"
    assert lock["accepted_review_ids"]
    assert lock_path.exists()
    assert snapshot_path.exists()
    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["selected_score"]["idea_id"] == SELECTED_IDEA_ID


def test_locked_idea_cannot_be_overwritten_without_force(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    selected = _selected_candidate(config, project_id)
    other = _candidate(config, project_id, title="Alternative measurement idea", idea_id="idea-alternative-measurement")
    manager = SelectedIdeaProjectManager(config)

    manager.lock_selected_idea(selected.id)

    with pytest.raises(ValueError, match="already locked"):
        manager.lock_selected_idea(other.id)

    forced = manager.lock_selected_idea(other.id, force=True, lock_reason="Recorded pivot for test.")

    assert forced.idea_id == other.id


def test_selected_project_created(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    selected = _selected_candidate(config, project_id)
    rejected = _candidate(config, project_id, title="Rejected broader collusion detector", idea_id="idea-rejected-broader")
    store = IdeaStore(config)
    store.reject_candidate(rejected.id, "Too broad for v2.1 selected execution.")
    IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="human", rationale="Accepted candidate.")
    IdeaTournamentRunner(config).run(project_id, top_k=5)

    selected_project = SelectedIdeaProjectManager(config).create_selected_project(selected.id)
    program = ProjectMemoryManager(config).load_project(selected_project.project_id)
    record_path = Path(program.project.root_dir) / "ideas" / "selected_idea_project.json"
    lock_path = Path(program.project.root_dir) / "ideas" / "selected_idea_lock.json"
    snapshot = json.loads((Path(program.project.root_dir) / "ideas" / "selected_idea_snapshot.json").read_text(encoding="utf-8"))

    assert selected_project.source_idea_id == SELECTED_IDEA_ID
    assert selected_project.research_question == CANONICAL_QUESTION
    assert selected_project.target_contribution_type == "benchmark"
    assert selected_project.status == "locked"
    assert record_path.exists()
    assert lock_path.exists()
    assert any(record.record_type == "decision" and SELECTED_IDEA_ID in record.linked_object_ids for record in program.memory_records)
    assert any(direction.title == SELECTED_TITLE for direction in program.research_directions)
    assert snapshot["rejected_ideas"][0]["id"] == rejected.id


def test_selected_idea_status_report_renders_and_cli(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    selected = _selected_candidate(config, project_id)
    IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="human", rationale="Accepted candidate.")
    IdeaTournamentRunner(config).run(project_id, top_k=5)
    create_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-idea-project-create", "--idea-id", selected.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    selected_project_id = json.loads(create_cli.stdout)["project_id"]
    report = SelectedIdeaProjectManager(config).render_status(selected_project_id)

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-idea-status", "--project-id", selected_project_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert create_cli.returncode == 0, create_cli.stderr
    assert "# Selected Idea Project Status" in report
    assert SELECTED_IDEA_ID in report
    assert CANONICAL_QUESTION in report
    assert "Tournament Snapshot" in report
    assert "Benchmark artifacts" in report
    assert cli.returncode == 0, cli.stderr
    assert "# Selected Idea Project Status" in cli.stdout
    assert (
        Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)
        / "ideas"
        / "reports"
        / "selected_idea_status.md"
    ).exists()


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("v2 low-FPR collusion idea pilot", description=LOW_FPR_TOPIC)
    manager.save_project(program)
    _attach_run(config, program.project.id, [Paper(id="paper-prior", title="Prior low-FPR monitor", authors=[], abstract="", year=2025)])
    return config, program.project.id


def _selected_candidate(config: GapForgeConfig, project_id: str):
    return _candidate(config, project_id, title=SELECTED_TITLE, idea_id=SELECTED_IDEA_ID)


def _candidate(config: GapForgeConfig, project_id: str, *, title: str, idea_id: str):
    store = IdeaStore(config)
    if store.load_state(project_id).idea_bank is None:
        store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-low-fpr",
        title=title,
        summary="A scoped candidate for low false-positive collusion audit execution.",
        contribution_type="benchmark",
        core_claim="Sequential audit specificity should be benchmarked before operational monitor claims.",
        proposed_experiment="Run baseline monitors on honest and collusive multi-agent traces.",
        expected_baselines=["rule monitor", "sequential threshold monitor"],
        expected_metrics=["specificity", "family-wise false-alarm probability"],
        closest_prior_work_ids=["paper-prior"],
        novelty_status="plausible",
        tractability_score=0.8,
        impact_score=0.85,
        evidence_score=0.7,
        reviewer_risk_score=0.2,
        idea_yield_score=0.9,
        maturity="candidate",
    )
    generated_id = candidate.id
    state = store.load_state(project_id)
    candidate.id = idea_id
    state.idea_bank.candidate_ids = [idea_id if item == generated_id else item for item in state.idea_bank.candidate_ids]
    state.candidates[-1] = candidate
    state.tournaments.append(
        IdeaTournament(
            id=f"tournament-{idea_id}",
            project_id=project_id,
            candidate_ids=[candidate.id],
            score_records=[
                IdeaScoreRecord(
                    idea_id=candidate.id,
                    evidence_score=0.7,
                    novelty_score=0.65,
                    experimentability_score=0.8,
                    total_score=0.82,
                    blockers=[],
                )
            ],
            selected_candidate_id=candidate.id,
            provenance=candidate.provenance,
        )
    )
    state.idea_bank.selected_candidate_id = candidate.id
    store._save_state(project_id, state)
    return candidate


def _attach_run(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
