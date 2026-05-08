from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import (
    ConstructiveGapGenerator,
    CrossDomainIdeaTransferEngine,
    IdeaFeedbackManager,
    IdeaMutationEngine,
    IdeaStore,
    ResearchAgendaManager,
)
from gapforge.ideas.models import IdeaNoveltyAssessment, IdeaScoreRecord, IdeaTournament, IdeaTransferCandidate
from gapforge.models import PilotRunRecord, Provenance
from gapforge.pilots.v2 import (
    V2_LOW_FPR_COLLUSION,
    V2_REQUIRED_SEARCH_ARTIFACTS,
    build_v2_pilot_acceptance,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_v2_pilot_fixture_accepted_idea_passes(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = _active_search_state(config, project_id)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="fixture",
        title="Sequential specificity benchmark for low-FPR collusion audits",
        summary="Specific benchmark candidate with visible evidence gates.",
        contribution_type="benchmark",
        proposed_experiment="Compare monitor baselines on benign and collusive traces.",
        expected_baselines=["LLM judge", "rule monitor"],
        expected_metrics=["false positive rate", "specificity"],
        evidence_span_ids=["span-fixture"],
        novelty_status="plausible",
        evidence_score=0.7,
        idea_yield_score=0.9,
    )
    store.add_novelty_assessment(
        IdeaNoveltyAssessment(
            id="assessment-fixture",
            idea_id=candidate.id,
            verdict="pursue",
            novelty_strength="medium",
            provenance=Provenance(created_by_skill="test"),
        )
    )
    store.add_tournament(
        IdeaTournament(
            id="tournament-fixture",
            project_id=project_id,
            candidate_ids=[candidate.id],
            score_records=[IdeaScoreRecord(idea_id=candidate.id, total_score=0.8)],
            selected_candidate_id=candidate.id,
            selection_reason="fixture accepted candidate",
            provenance=Provenance(created_by_skill="test"),
        )
    )
    IdeaFeedbackManager(config).add_feedback(idea_id=candidate.id, action="accept", reviewer="fixture", rationale="Accept as candidate.")
    record = _record(project_id, accepted_idea_id=candidate.id)

    summary = build_v2_pilot_acceptance(config, record)

    assert summary.passed is True
    assert summary.outcome_type == "defensible_direction"
    assert summary.accepted_direction_id == candidate.id


def test_v2_pilot_fixture_agenda_after_exhaustive_search_passes(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = _active_search_state(config, project_id)
    agenda = ResearchAgendaManager(config).generate(
        project_id,
        blocker_summary="All candidates failed tournament blockers after mutation.",
    )
    store.add_tournament(
        IdeaTournament(
            id="tournament-agenda-fixture",
            project_id=project_id,
            candidate_ids=[],
            selected_candidate_id="",
            agenda_id=agenda.id,
            selection_reason="No viable idea.",
            provenance=Provenance(created_by_skill="test"),
        )
    )
    record = _record(project_id, outcome_type="correct_refusal", agenda_id=agenda.id)
    record.artifact_paths["external_review_acceptance"] = "fixture/review.json"
    record.blockers.append("research_refusal: active v2 search exhausted candidates and produced agenda")

    summary = build_v2_pilot_acceptance(
        config,
        record,
    )

    assert summary.passed is False

    # Add the required auditable human review and the same fixture becomes a valid agenda fallback.
    from gapforge.pilots.external_review import ExternalPilotReviewManager
    from gapforge.pilots.status import PilotStore

    PilotStore(config).save_record(record)
    ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="user")
    reviewed = PilotStore(config).load_record(record.id)
    reviewed_summary = build_v2_pilot_acceptance(config, reviewed)

    assert reviewed_summary.passed is True
    assert reviewed_summary.outcome_type == "correct_refusal"


def test_v2_pilot_early_refusal_without_search_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    record = PilotRunRecord(
        id="pilot-v2-early-refusal",
        pilot_id=V2_LOW_FPR_COLLUSION,
        project_id=project_id,
        status="accepted",
        outcome_type="correct_refusal",
        blockers=["research_refusal: no idea found"],
        provenance=Provenance(created_by_skill="test"),
    )

    summary = build_v2_pilot_acceptance(config, record)

    assert summary.passed is False
    assert "active_search_completed" in summary.refusal_reason


def test_v2_pilot_generic_idea_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = _active_search_state(config, project_id)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="fixture",
        title="Research idea",
        summary="Generic idea.",
        contribution_type="method",
        evidence_span_ids=["span-fixture"],
        novelty_status="plausible",
    )
    store.add_tournament(
        IdeaTournament(
            id="tournament-generic",
            project_id=project_id,
            selected_candidate_id=candidate.id,
            provenance=Provenance(created_by_skill="test"),
        )
    )
    IdeaFeedbackManager(config).add_feedback(idea_id=candidate.id, action="accept", reviewer="fixture")
    record = _record(project_id, accepted_idea_id=candidate.id)

    summary = build_v2_pilot_acceptance(config, record)

    assert summary.passed is False
    assert "selected_idea_is_specific" in summary.refusal_reason


def test_v2_pilot_fake_citation_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = _active_search_state(config, project_id)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="fixture",
        title="Specificity-first collusion audit benchmark",
        summary="Specific candidate with an unresolved citation.",
        contribution_type="benchmark",
        closest_prior_work_ids=["paper-does-not-exist"],
        novelty_status="plausible",
    )
    store.add_tournament(
        IdeaTournament(
            id="tournament-fake",
            project_id=project_id,
            selected_candidate_id=candidate.id,
            provenance=Provenance(created_by_skill="test"),
        )
    )
    IdeaFeedbackManager(config).add_feedback(idea_id=candidate.id, action="accept", reviewer="fixture")
    record = _record(project_id, accepted_idea_id=candidate.id)

    summary = build_v2_pilot_acceptance(config, record)

    assert summary.passed is False
    assert "selected_idea_has_no_fake_citation" in summary.refusal_reason


def test_v2_pilot_cli_run_status_report(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v2-pilot-run", "--name", "low_fpr_collusion"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v2-pilot-status", "--name", "low_fpr_collusion"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v2-pilot-report", "--name", "low_fpr_collusion"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["pilot_id"] == V2_LOW_FPR_COLLUSION
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["requirements"]["active_search_completed"] is True
    assert report.returncode == 0, report.stderr
    assert "v2 Low-FPR Collusion Idea Pilot" in report.stdout


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("v2 pilot fixture", description=LOW_FPR_TOPIC)
    manager.save_project(program)
    return config, program.project.id


def _active_search_state(config: GapForgeConfig, project_id: str) -> IdeaStore:
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    weak = store.add_candidate(
        project_id=project_id,
        source_topic_id="weak",
        title="Weak low-FPR collusion monitor seed",
        summary="Weak seed to force mutation.",
        contribution_type="method",
        novelty_status="weak",
    )
    store.reject_candidate(weak.id, "fixture rejection before mutation")
    IdeaMutationEngine(config).mutate_rejected_ideas(project_id)
    ConstructiveGapGenerator(config).generate_for_project(project_id)
    CrossDomainIdeaTransferEngine(config).transfer_for_project(project_id)
    state = store.load_state(project_id)
    state.transfer_candidates = state.transfer_candidates or [
        IdeaTransferCandidate(
            id="transfer-fixture",
            source_field="medicine screening/specificity",
            source_concept="specificity",
            target_problem=LOW_FPR_TOPIC,
            transfer_mechanism="Use screening specificity as an audit threshold mechanism.",
            what_breaks="Labels are noisier.",
        )
    ]
    store._save_state(project_id, state)
    return store


def _record(
    project_id: str,
    *,
    accepted_idea_id: str = "",
    outcome_type: str = "defensible_direction",
    agenda_id: str = "",
) -> PilotRunRecord:
    artifacts = {key: f"fixture/{key}" for key in V2_REQUIRED_SEARCH_ARTIFACTS}
    if accepted_idea_id:
        artifacts["accepted_idea_id"] = accepted_idea_id
        artifacts["accepted_direction_id"] = accepted_idea_id
    if agenda_id:
        artifacts["research_agenda"] = agenda_id
    return PilotRunRecord(
        id=f"pilot-v2-fixture-{accepted_idea_id or agenda_id or outcome_type}",
        pilot_id=V2_LOW_FPR_COLLUSION,
        project_id=project_id,
        status="accepted",
        outcome_type=outcome_type,
        artifact_paths=artifacts,
        provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
    )
