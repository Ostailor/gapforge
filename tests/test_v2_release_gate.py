from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import (
    ConstructiveGapGenerator,
    IdeaFeedbackManager,
    IdeaMutationEngine,
    IdeaStore,
    ResearchAgendaManager,
    TopicPortfolioGenerator,
)
from gapforge.ideas.models import IdeaNoveltyAssessment, IdeaScoreRecord, IdeaTournament, IdeaTransferCandidate
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v2 import V2ReleaseGateEnforcer
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_v2_release_gate_no_portfolio_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    _discovery_state(config, project_id, include_portfolio=False, include_tournament=True, accept_selected=True)

    result = V2ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["topic_portfolio_exists"] is False
    assert any("topic_portfolio_exists" in blocker for blocker in result.blockers)


def test_v2_release_gate_no_tournament_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    _discovery_state(config, project_id, include_portfolio=True, include_tournament=False, accept_selected=True)

    result = V2ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["idea_tournament_ran"] is False
    assert any("idea_tournament_ran" in blocker for blocker in result.blockers)


def test_v2_release_gate_accepted_idea_passes_and_cli_json(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    selected_id = _discovery_state(config, project_id, include_portfolio=True, include_tournament=True, accept_selected=True)

    result = V2ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.status == "pass"
    assert result.selected_idea_id == selected_id
    assert result.requirements["human_accepted_candidate_exists"] is True
    assert result.requirements["idea_yield_metrics_generated"] is True

    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v2-release-gate", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    payload = json.loads(cli.stdout)
    assert payload["passed"] is True
    assert payload["selected_idea_id"] == selected_id


def test_v2_release_gate_agenda_only_without_flag_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    _agenda_only_state(config, project_id)

    result = V2ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["agenda_fallback_exists"] is True
    assert result.requirements["human_accepted_candidate_exists"] is False
    assert any("--allow-agenda-only" in blocker for blocker in result.blockers)


def test_v2_release_gate_agenda_only_with_flag_warning_passes(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    _agenda_only_state(config, project_id)

    result = V2ReleaseGateEnforcer(config).evaluate(allow_agenda_only=True)
    report = V2ReleaseGateEnforcer(config).write_outputs(result)[1]
    rendered = report.read_text(encoding="utf-8")

    assert result.passed is True
    assert result.status == "warning_pass"
    assert any("idea_discovery_incomplete" in warning for warning in result.warnings)
    assert "did not produce a human-accepted candidate idea" in rendered


def test_v2_release_gate_fake_citation_selected_idea_fails(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _write_v1_pass(config)
    _discovery_state(
        config,
        project_id,
        include_portfolio=True,
        include_tournament=True,
        accept_selected=True,
        selected_prior_work_ids=["paper-does-not-exist"],
    )

    result = V2ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["selected_idea_has_no_fake_citations"] is False
    assert any("selected_idea_has_no_fake_citations" in blocker for blocker in result.blockers)


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("v2 release gate fixture", description=LOW_FPR_TOPIC)
    manager.use_project(program.project.id)
    manager.save_project(program)
    return config, program.project.id


def _write_v1_pass(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "v1_readiness_latest.json").write_text(
        json.dumps({"passed": True, "status": "pass", "recommended_next_version": "v1"}, indent=2) + "\n",
        encoding="utf-8",
    )


def _discovery_state(
    config: GapForgeConfig,
    project_id: str,
    *,
    include_portfolio: bool,
    include_tournament: bool,
    accept_selected: bool,
    selected_prior_work_ids: list[str] | None = None,
) -> str:
    if include_portfolio:
        TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store = _base_search_state(config, project_id)
    selected = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-selected",
        title="Sequential specificity benchmark for low-FPR collusion audits",
        summary="Specific benchmark candidate that still requires evidence-gated experiments.",
        contribution_type="benchmark",
        proposed_experiment="Compare LLM judge and rule monitor baselines on benign and collusive multi-agent traces.",
        expected_baselines=["LLM judge", "rule monitor"],
        expected_metrics=["false positive rate", "specificity"],
        closest_prior_work_ids=selected_prior_work_ids or [],
        novelty_status="plausible",
        evidence_score=0.7,
        idea_yield_score=0.9,
        maturity="candidate",
    )
    store.add_novelty_assessment(
        IdeaNoveltyAssessment(
            id=f"novelty-{selected.id}",
            idea_id=selected.id,
            verdict="pursue",
            novelty_strength="medium",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    if include_tournament:
        store.add_tournament(
            IdeaTournament(
                id=f"tournament-{selected.id}",
                project_id=project_id,
                candidate_ids=[selected.id],
                score_records=[IdeaScoreRecord(idea_id=selected.id, total_score=0.85, blockers=[])],
                selected_candidate_id=selected.id,
                selection_reason="fixture selected idea",
                provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
            )
        )
    if accept_selected:
        IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="fixture", rationale="Accept candidate.")
    return selected.id


def _agenda_only_state(config: GapForgeConfig, project_id: str) -> None:
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store = _base_search_state(config, project_id)
    rejected = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-rejected",
        title="Specific but duplicated collusion monitor",
        summary="Candidate rejected after closest prior work solved the core idea.",
        contribution_type="method",
        novelty_status="likely_duplicate",
        maturity="candidate",
    )
    store.reject_candidate(rejected.id, "fatal prior work already solves the core idea")
    store.add_review(idea_id=rejected.id, reviewer="fixture", status="rejected", notes="Reject after active search.")
    store.add_novelty_assessment(
        IdeaNoveltyAssessment(
            id=f"novelty-{rejected.id}",
            idea_id=rejected.id,
            verdict="reject",
            novelty_strength="low",
            required_mutation="Change decisive overlapping dimension.",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    agenda = ResearchAgendaManager(config).generate(project_id, blocker_summary="All candidates failed after active search.")
    store.add_tournament(
        IdeaTournament(
            id="tournament-agenda-only",
            project_id=project_id,
            candidate_ids=[rejected.id],
            score_records=[IdeaScoreRecord(idea_id=rejected.id, total_score=0.0, blockers=["fatal novelty blocker"])],
            selected_candidate_id="",
            rejected_candidate_ids=[rejected.id],
            agenda_id=agenda.id,
            selection_reason="No viable idea; agenda fallback.",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )


def _base_search_state(config: GapForgeConfig, project_id: str) -> IdeaStore:
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
    _write_codex_task_marker(config, project_id)
    state = store.load_state(project_id)
    state.transfer_candidates = state.transfer_candidates or [
        IdeaTransferCandidate(
            id="transfer-fixture",
            source_field="medicine screening/specificity",
            source_concept="specificity",
            target_problem=LOW_FPR_TOPIC,
            transfer_mechanism="Use screening specificity as an audit threshold mechanism.",
            what_breaks="Collusion labels are noisier.",
            confidence="medium",
        )
    ]
    store._save_state(project_id, state)
    return store


def _write_codex_task_marker(config: GapForgeConfig, project_id: str) -> None:
    program = ProjectMemoryManager(config).load_project(project_id)
    task_dir = Path(program.project.root_dir) / "ideas" / "codex_tasks" / "idea-codex-task-fixture"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(
        json.dumps({"id": "idea-codex-task-fixture", "project_id": project_id, "task_type": "idea_seed_expansion"}, indent=2) + "\n",
        encoding="utf-8",
    )
