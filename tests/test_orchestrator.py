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


def test_v2_dry_run_creates_full_text_prior_work_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)

    state = Orchestrator(config).run(
        "low false positive collusion detection",
        max_papers=8,
        v2=True,
        dry_run=True,
        deep_novelty=True,
        strict_report=True,
        max_expanded_papers=7,
    )

    assert state.orchestrator_plan is not None
    assert state.config["v2"] is True
    assert state.config["strict_report"] is True
    assert state.config["max_expanded_papers"] == 7
    names = [step.name for step in state.orchestrator_plan.steps]
    assert names == [
        "initialize-topic",
        "search-papers",
        "source-coverage",
        "map-literature",
        "triage-papers",
        "download-pdfs",
        "parse-fulltext",
        "deep-read",
        "mine-gaps",
        "cross-domain-analogies",
        "analogy-search",
        "refresh-after-new-papers",
        "citation-graph",
        "related-work-expansion",
        "refresh-after-expanded-papers",
        "novelty-dossiers",
        "design-experiments",
        "reviewer-simulation",
        "final-report",
    ]
    assert all(step.status == "pending" for step in state.orchestrator_plan.steps)


def test_v2_offline_run_skips_network_steps_and_warns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)

    state = Orchestrator(config).run("low false positive collusion detection", max_papers=8, v2=True)

    assert state.orchestrator_result is not None
    assert state.orchestrator_result.status == "complete"
    assert state.source_coverage is not None
    assert any("Network disabled" in warning for warning in state.source_coverage.coverage_warnings)
    skipped = {step.name for step in state.orchestrator_plan.steps if step.status == "skipped"} if state.orchestrator_plan else set()
    assert {"download-pdfs", "parse-fulltext", "analogy-search", "related-work-expansion"} <= skipped


def test_v2_resume_after_stop_after(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    orchestrator = Orchestrator(config)

    interrupted = orchestrator.run(
        "low false positive collusion detection",
        max_papers=8,
        v2=True,
        stop_after="source-coverage",
    )
    assert interrupted.orchestrator_result is not None
    assert interrupted.orchestrator_result.status == "interrupted"

    resumed = orchestrator.resume(run_id=interrupted.run_id)

    assert resumed.orchestrator_result is not None
    assert resumed.orchestrator_result.status == "complete"
    assert resumed.novelty_dossiers
    statuses = {step.status for step in resumed.orchestrator_plan.steps} if resumed.orchestrator_plan else set()
    assert "pending" not in statuses
    assert "running" not in statuses


def test_v2_plan_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)

    state = Orchestrator(config).run("low false positive collusion detection", max_papers=8, v2=True)
    run_dir = Path(state.run_dir)

    for artifact in [
        "orchestrator_plan.json",
        "source_coverage.md",
        "full_text_coverage.md",
        "citation_graph.md",
        "novelty_dossiers.md",
        "final_report.md",
    ]:
        assert (run_dir / artifact).exists(), artifact


def test_v2_downloader_failure_does_not_kill_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config = GapForgeConfig.from_cwd(tmp_path)

    state = Orchestrator(config, sources=[FixtureSource()], pdf_downloader=FailingDownloader()).run(
        "low false positive collusion detection",
        max_papers=8,
        v2=True,
        max_expanded_papers=0,
        stop_after="download-pdfs",
    )

    assert state.orchestrator_result is not None
    assert state.orchestrator_result.status == "interrupted"
    download_steps = [step for step in state.orchestrator_plan.steps if step.name == "download-pdfs"] if state.orchestrator_plan else []
    assert download_steps and download_steps[0].status == "complete"
    assert any("PDF downloader failed non-fatally" in entry.message for entry in state.run_log)


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


class FailingDownloader:
    def download_for_state(self, *args, **kwargs):
        raise RuntimeError("download fixture failure")
