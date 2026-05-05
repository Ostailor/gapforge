from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    ActiveLoopState,
    Gap,
    NoveltyAssessment,
    Paper,
    PaperTriageDecision,
    PaperTriageResult,
    ResearchBudget,
)
from gapforge.orchestration.decisions import ActiveLoopDecider
from gapforge.orchestrator import Orchestrator
from gapforge.review.edits import HumanReviewEditor
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.stopping import refresh_stopping_assessment


def test_active_loop_small_budget_terminates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[StaticSource()])

    state = orchestrator.run_active("low false positive collusion detection", budget=ResearchBudget(max_iterations=1, max_queries=3))

    assert state.active_loop is not None
    assert state.active_loop.status in {"budget_exhausted", "complete"}
    assert any(decision.decision_type == "stop" for decision in state.active_loop.decisions)
    assert (Path(state.run_dir) / "active_decisions.md").exists()


def test_poor_coverage_triggers_search_more(tmp_path: Path) -> None:
    state = Orchestrator(GapForgeConfig.from_cwd(tmp_path)).init_topic("ai safety monitor evasion")
    state.active_loop = ActiveLoopState(budget=ResearchBudget(max_queries=5))
    refresh_source_coverage(state)
    refresh_stopping_assessment(state, profile="ai_safety")

    decision = ActiveLoopDecider().decide(state, state.active_loop)

    assert decision.decision_type == "search_more"
    assert "insufficient" in decision.reason.lower()


def test_missing_tier1_full_text_triggers_parse_more(tmp_path: Path) -> None:
    state = Orchestrator(GapForgeConfig.from_cwd(tmp_path)).init_topic("coverage enough but missing full text")
    state.papers = [
        Paper(
            id=f"p{i}",
            title=("Survey benchmark paper" if i == 0 else f"Benchmark paper {i}"),
            authors=[],
            abstract="survey",
            year=2025,
            source="Semantic Scholar",
        )
        for i in range(12)
    ]
    state.paper_triage = PaperTriageResult(
        topic=state.topic.text,
        decisions=[
            PaperTriageDecision(paper_id="p0", title="Survey benchmark paper", tier="Tier 1", score=0.9),
            PaperTriageDecision(paper_id="p1", title="Benchmark paper 1", tier="Tier 1", score=0.8),
        ],
    )
    state.search_queries = []
    refresh_source_coverage(state)
    refresh_stopping_assessment(state, profile="generic")
    # Force mapping coverage to be sufficient so the next value is parsing.
    assert state.coverage_stopping_assessment is not None
    state.coverage_stopping_assessment.enough_for_mapping = True
    state.active_loop = ActiveLoopState(budget=ResearchBudget(max_full_text_papers=4))

    decision = ActiveLoopDecider().decide(state, state.active_loop)

    assert decision.decision_type == "parse_more"
    assert "p0" in decision.evidence


def test_rejected_gaps_do_not_trigger_experiment_design(tmp_path: Path) -> None:
    state = Orchestrator(GapForgeConfig.from_cwd(tmp_path)).init_topic("rejected gap")
    state.gaps = [Gap(id="gap-1", title="Rejected gap", description="x", confidence="medium")]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="Rejected gap",
            verdict="pursue",
            novelty_strength="medium",
        )
    ]
    HumanReviewEditor().reject_gap(state, "gap-1", reason="Human rejected duplicate.")
    state.active_loop = ActiveLoopState(budget=ResearchBudget(max_queries=0))
    refresh_source_coverage(state)
    refresh_stopping_assessment(state, profile="generic")

    decision = ActiveLoopDecider().decide(state, state.active_loop)

    assert decision.decision_type != "design_experiment"


def test_no_new_papers_triggers_stop(tmp_path: Path) -> None:
    state = Orchestrator(GapForgeConfig.from_cwd(tmp_path)).init_topic("no new papers")
    state.active_loop = ActiveLoopState(budget=ResearchBudget(stop_when_no_new_papers=True))
    state.active_loop.decisions.append(state_decision(state.run_id, "active-decision-0001", "search_more", ["new_papers=0"]))
    refresh_source_coverage(state)
    refresh_stopping_assessment(state, profile="generic")

    decision = ActiveLoopDecider().decide(state, state.active_loop)

    assert decision.decision_type == "stop"
    assert "no new papers" in decision.reason.lower()


def test_active_loop_is_resumable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[StaticSource()])
    state = orchestrator.run_active("resumable active loop", budget=ResearchBudget(max_iterations=1, max_queries=3))
    assert state.active_loop is not None
    first_count = len(state.active_loop.decisions)
    state.active_loop.status = "paused"
    orchestrator.state_store.save_run(state)

    resumed = orchestrator.resume_active(run_id=state.run_id)

    assert resumed.active_loop is not None
    assert len(resumed.active_loop.decisions) >= first_count
    assert resumed.active_loop.status in {"complete", "budget_exhausted"}


def test_active_loop_cli_status_and_decisions(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "GAPFORGE_DISABLE_NETWORK": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }
    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "run-active", "low false positive collusion detection", "--budget", "small"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    run_id = _run_id_from_stdout(run.stdout)

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "active-status", "--run-id", run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    decisions = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "active-decisions", "--run-id", run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status.returncode == 0, status.stderr
    assert decisions.returncode == 0, decisions.stderr
    assert "decision_count" in status.stdout
    assert "Active Loop Decisions" in decisions.stdout


class StaticSource:
    name = "Fixture"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [Paper(id="fixture-1", title=f"Paper for {query}", authors=[], abstract="abstract", year=2025, source=self.name)]


def state_decision(run_id: str, decision_id: str, decision_type: str, evidence: list[str]):
    from gapforge.models import ActiveLoopDecision

    return ActiveLoopDecision(id=decision_id, run_id=run_id, iteration=1, decision_type=decision_type, evidence=evidence, status="complete")


def _run_id_from_stdout(stdout: str) -> str:
    marker = "run "
    start = stdout.index(marker) + len(marker)
    end = stdout.index(" ", start)
    return stdout[start:end]
