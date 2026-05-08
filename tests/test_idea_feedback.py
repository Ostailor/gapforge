from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaPreferenceManager, IdeaStore, IdeaTournamentRunner
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_preferences_saved(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    profile = IdeaPreferenceManager(config).save_profile(
        project_id=project_id,
        preferred_contribution_types=["benchmark", "measurement"],
        preferred_domains=["collusion"],
        risk_tolerance="low",
        time_budget="week",
        compute_budget="laptop",
        publication_target="workshop",
        avoid_topics=["generic monitor"],
        notes="Prefer scoped empirical artifacts.",
    )
    state = IdeaStore(config).load_state(project_id)

    assert state.preference_profiles[-1].id == profile.id
    assert profile.preferred_contribution_types == ["benchmark", "measurement"]
    assert "Preferences shape search" in IdeaPreferenceManager(config).write_report(project_id)


def test_feedback_affects_score(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    method = _candidate(config, project_id, title="Method idea for collusion monitors", contribution_type="method")
    benchmark = _candidate(config, project_id, title="Benchmark idea for collusion monitors", contribution_type="benchmark")
    IdeaPreferenceManager(config).save_profile(
        project_id=project_id,
        preferred_contribution_types=["benchmark"],
        preferred_domains=["collusion"],
    )
    IdeaFeedbackManager(config).add_feedback(idea_id=benchmark.id, action="upvote", rationale="Fits taste.")

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    scores = {record.idea_id: record for record in tournament.score_records}

    assert scores[benchmark.id].human_preference_score > scores[method.id].human_preference_score
    assert tournament.selected_candidate_id == benchmark.id


def test_human_rejection_blocks_selection_and_persists_memory(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    rejected = _candidate(config, project_id, title="High scoring rejected candidate", evidence=0.9, impact=0.9, yield_score=0.95)
    viable = _candidate(config, project_id, title="Viable alternative candidate", evidence=0.5, impact=0.55, yield_score=0.55)

    IdeaFeedbackManager(config).add_feedback(idea_id=rejected.id, action="reject", rationale="Not aligned with project taste.")
    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    program = ProjectMemoryManager(config).load_project(project_id)

    assert rejected.id in tournament.rejected_candidate_ids
    assert tournament.selected_candidate_id == viable.id
    assert any(record.record_type == "rejected_idea" and rejected.id in record.linked_object_ids for record in program.memory_records)


def test_mutation_request_creates_decision(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(config, project_id, title="Mutation-request candidate")

    feedback = IdeaFeedbackManager(config).add_feedback(
        idea_id=candidate.id,
        action="request_mutation",
        rationale="Shift from method to measurement.",
        preferred_mutations=["method_to_measurement"],
    )
    state = IdeaStore(config).load_state(project_id)

    assert feedback.id in state.search_decisions[-1].evidence
    assert state.search_decisions[-1].decision_type == "mutate_ideas"
    assert state.search_decisions[-1].status == "pending"


def test_acceptance_still_requires_gates_and_cli(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _attach_run(config, project_id, [Paper(id="paper-known", title="Known prior", authors=[], abstract="", year=2025)])
    accepted_without_gates = _candidate(
        config,
        project_id,
        title="Accepted but unsupported candidate",
        evidence=1.0,
        impact=1.0,
        yield_score=1.0,
        closest_prior_work_ids=[],
    )
    viable = _candidate(
        config,
        project_id,
        title="Evidence-gated viable candidate",
        evidence=0.55,
        impact=0.6,
        yield_score=0.6,
        closest_prior_work_ids=["paper-known"],
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "idea-feedback",
            "--idea-id",
            accepted_without_gates.id,
            "--action",
            "accept",
            "--rationale",
            "I like this direction.",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    tournament = IdeaTournamentRunner(config).run(project_id, top_k=5)
    blocked = next(record for record in tournament.score_records if record.idea_id == accepted_without_gates.id)

    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["action"] == "accept"
    assert "human acceptance lacks evidence or novelty gates" in blocked.blockers
    assert tournament.selected_candidate_id == viable.id


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Feedback Project")
    program.provenance.append(
        Provenance(created_by_skill="test", timestamp=utc_now_iso(), reasoning_summary="Test fixture project for feedback.")
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
    impact: float = 0.6,
    yield_score: float = 0.6,
    closest_prior_work_ids: list[str] | None = None,
):
    store = IdeaStore(config)
    if store.load_state(project_id).idea_bank is None:
        store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    return store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-feedback",
        title=title,
        summary="A scoped idea for low false-positive collusion detection without result claims.",
        contribution_type=contribution_type,
        core_claim="This is a candidate direction, not a proven result.",
        proposed_experiment="Compare monitor baselines on benign and collusive traces.",
        expected_baselines=["LLM judge", "rule monitor"],
        expected_metrics=["false positive rate", "recall"],
        closest_prior_work_ids=closest_prior_work_ids or [],
        novelty_status="plausible",
        tractability_score=0.7,
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
