from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaStore, TopicPortfolioGenerator
from gapforge.ideas.models import ConstructiveGapCandidate, IdeaNoveltyAssessment, IdeaScoreRecord, IdeaTournament, IdeaTransferCandidate
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_idea_discovery_dashboard_and_report_cli(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    _idea_state(config, project_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    dashboard = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dashboard", "--project-id", project_id, "--include-ideas"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-discovery-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    dashboard_root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "dashboard"
    report_path = (
        Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "ideas" / "reports" / "idea_discovery_report.md"
    )

    assert dashboard.returncode == 0, dashboard.stderr
    for name in [
        "topic_portfolio.html",
        "idea_bank.html",
        "idea_candidates.html",
        "mutations.html",
        "constructive_gaps.html",
        "cross_domain_transfers.html",
        "idea_novelty.html",
        "idea_tournament.html",
        "human_feedback.html",
        "research_agenda.html",
        "idea_yield.html",
        "v2_release_gate.html",
    ]:
        assert (dashboard_root / name).exists()
    assert "human accepted candidate" in (dashboard_root / "idea_bank.html").read_text(encoding="utf-8").lower()
    assert "fatal prior work already solves" in (dashboard_root / "idea_candidates.html").read_text(encoding="utf-8")
    assert "Selected candidate" in (dashboard_root / "idea_tournament.html").read_text(encoding="utf-8")
    assert report.returncode == 0, report.stderr
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "## Selected Idea" in report_text
    assert "## Rejected Ideas" in report_text
    assert "fatal prior work already solves" in report_text
    assert "## Human Feedback" in report_text


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Dashboard Project", description=LOW_FPR_TOPIC)
    manager.use_project(program.project.id)
    manager.save_project(program)
    return config, program.project.id


def _idea_state(config: GapForgeConfig, project_id: str) -> None:
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    rejected = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-rejected",
        title="Duplicate low-FPR collusion monitor",
        summary="Rejected duplicate seed.",
        contribution_type="method",
        novelty_status="likely_duplicate",
        maturity="candidate",
    )
    store.reject_candidate(rejected.id, "fatal prior work already solves the method idea")
    accepted = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-selected",
        title="Sequential specificity benchmark for low-FPR collusion audits",
        summary="Human accepted candidate benchmark.",
        contribution_type="benchmark",
        core_claim="A specificity-first benchmark can inspect monitor false positives.",
        proposed_experiment="Run LLM judge and rule monitors at fixed false-positive budgets.",
        expected_baselines=["LLM judge", "rule monitor"],
        expected_metrics=["false positive rate", "specificity"],
        novelty_status="plausible",
        evidence_score=0.7,
        idea_yield_score=0.9,
        maturity="candidate",
    )
    store.add_mutation_record(
        source_idea_id=rejected.id,
        mutated_idea_id=accepted.id,
        strategy="method_to_benchmark",
        what_changed="Changed method novelty into benchmark contribution.",
        why_it_may_help="Avoids the fatal prior-work overlap.",
        inherited_risks=["fatal prior work already solves method idea"],
        required_new_searches=["low-FPR benchmark collusion auditing"],
    )
    store.link_evidence(idea_id=accepted.id, link_type="supports", paper_id="paper-known", note="Known benchmark anchor.")
    store.add_novelty_assessment(
        IdeaNoveltyAssessment(
            id="novelty-accepted",
            idea_id=accepted.id,
            closest_prior_work_ids=["paper-known"],
            similarity_summary="Prior work has monitors but not specificity-first benchmark framing.",
            counterevidence=["Some monitor benchmarks are adjacent."],
            verdict="pursue",
            novelty_strength="medium",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    state = store.load_state(project_id)
    state.constructive_gaps.append(
        ConstructiveGapCandidate(
            id="gap-benchmark",
            project_id=project_id,
            title="Benchmark for low-FPR collusion auditing",
            contribution_type="benchmark",
            problem="No specificity-first benchmark is recorded.",
            why_existing_work_makes_this_useful="Prior monitors need low-FPR stress tests.",
            minimum_artifact="Honest and collusive trace benchmark.",
            minimum_experiment="Run baseline monitors at fixed FPR.",
            required_baselines=["LLM judge"],
            closest_prior_work_ids=["paper-known"],
        )
    )
    state.transfer_candidates.append(
        IdeaTransferCandidate(
            id="transfer-specificity",
            source_field="medicine screening/specificity",
            source_concept="specificity",
            target_problem=LOW_FPR_TOPIC,
            transfer_mechanism="Set thresholds by specificity before recall.",
            target_idea_id=accepted.id,
            required_adaptation="Map clinical labels to collusion labels.",
            what_breaks="Collusion labels are noisier.",
            supporting_source_papers=["paper-known"],
            confidence="medium",
        )
    )
    state.tournaments.append(
        IdeaTournament(
            id="tournament-dashboard",
            project_id=project_id,
            candidate_ids=[accepted.id, rejected.id],
            score_records=[
                IdeaScoreRecord(idea_id=accepted.id, total_score=0.85, evidence_score=0.7, novelty_score=0.65, blockers=[]),
                IdeaScoreRecord(idea_id=rejected.id, total_score=0.0, blockers=["fatal novelty blocker"]),
            ],
            selected_candidate_id=accepted.id,
            rejected_candidate_ids=[rejected.id],
            selection_reason="Selected candidate after benchmark mutation.",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    assert state.idea_bank is not None
    state.idea_bank.selected_candidate_id = accepted.id
    store._save_state(project_id, state)
    IdeaFeedbackManager(config).add_feedback(
        idea_id=accepted.id,
        action="accept",
        reviewer="fixture",
        rationale="Human accepted candidate for dashboard inspection.",
    )
