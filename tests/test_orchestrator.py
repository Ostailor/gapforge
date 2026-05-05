from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.evals.benchmark import evaluate_run
from gapforge.models import Paper
from gapforge.orchestrator import Orchestrator


def test_orchestrator_run_is_deterministic_enough(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state = Orchestrator(config).run("low false positive collusion detection")
    result = evaluate_run(state)

    assert result.passed
    assert result.metrics.paper_count >= 6
    assert state.completed_skills == [
        "literature-cartographer",
        "paper-triage",
        "deep-reading",
        "gap-mining",
        "cross-domain-analogy",
        "novelty-gate",
        "experiment-designer",
        "reviewer-simulation",
    ]
    assert state.orchestrator_plan is not None
    assert state.orchestrator_result is not None
    assert state.orchestrator_result.status == "complete"
    assert state.run_log


def test_orchestrator_resume_continues_pending_steps(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    interrupted = Orchestrator(config).run(
        "low false positive collusion detection",
        max_papers=12,
        stop_after="triage-papers",
    )

    assert interrupted.orchestrator_result is not None
    assert interrupted.orchestrator_result.status == "interrupted"
    assert interrupted.paper_triage is not None
    assert not interrupted.experiments

    resumed = Orchestrator(config).resume(run_id=interrupted.run_id)

    assert resumed.orchestrator_result is not None
    assert resumed.orchestrator_result.status == "complete"
    assert resumed.experiments
    assert resumed.reviewer_objections
    statuses = {step.status for step in resumed.orchestrator_plan.steps} if resumed.orchestrator_plan else set()
    assert "pending" not in statuses
    assert "running" not in statuses


def test_orchestrator_source_failure_does_not_kill_run(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = Orchestrator(config, sources=[FailingSource(), FixtureSource()]).run(
        "low false positive collusion detection",
        max_papers=8,
    )

    assert state.orchestrator_result is not None
    assert state.orchestrator_result.status == "complete"
    assert state.papers
    assert any("Failing" in entry.message for entry in state.run_log)


def test_init_topic_handles_same_second_collisions(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    orchestrator = Orchestrator(config)

    first = orchestrator.init_topic("low false positive collusion detection")
    second = orchestrator.init_topic("low false positive collusion detection")

    assert first.run_id != second.run_id
    assert Path(first.run_dir).exists()
    assert Path(second.run_dir).exists()


class FailingSource:
    name = "Failing"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("fixture source failure")


class FixtureSource:
    name = "Fixture"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id=f"fixture-{index}-{query.replace(' ', '-')[:30]}",
                title=f"Fixture paper {index} for {query}",
                authors=["Fixture Author"],
                abstract=(
                    f"We study {query}. This paper proposes a benchmark dataset and reports false positive "
                    "limitations, future work, and calibration evaluation for collusion detection."
                ),
                year=2025 - index,
                source=self.name,
                venue="FixtureConf",
                citation_count=10 + index,
            )
            for index in range(1, max_results + 1)
        ]
