from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, SearchQueryRecord, SearchStrategy, SourceCoverageReport
from gapforge.novelty.dossier import NoveltyDossierBuilder
from gapforge.search_strategy import execute_search_strategy, plan_search_strategy, save_strategy
from gapforge.state import ResearchStateManager


class FakeLiveSource:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id=f"s2-{abs(hash((query, index))) % 100000}",
                title=f"{query} result {index}",
                authors=["Ada"],
                abstract=f"Live result for {query}.",
                year=2026,
                source=self.name,
            )
            for index in range(min(max_results, 2))
        ]


class FailingSource:
    name = "arXiv"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("source unavailable")


def test_strategy_contains_multiple_query_types(tmp_path: Path) -> None:
    strategy = plan_search_strategy(GapForgeConfig.from_cwd(tmp_path), "low false positive collusion detection", source_profile="ai_safety")

    assert strategy.primary_queries
    assert strategy.recency_queries
    assert strategy.survey_queries
    assert strategy.benchmark_queries
    assert strategy.dataset_queries
    assert strategy.method_queries
    assert strategy.closest_prior_work_queries
    assert strategy.adjacent_field_queries
    assert strategy.exclusion_queries


def test_source_profile_influences_query_sources_and_targets(tmp_path: Path) -> None:
    ai_safety = plan_search_strategy(GapForgeConfig.from_cwd(tmp_path), "monitor evasion", source_profile="ai_safety")
    medicine = plan_search_strategy(GapForgeConfig.from_cwd(tmp_path), "screening specificity", source_profile="medicine")

    assert "openreview" in ai_safety.expected_sources
    assert "pubmed" in medicine.coverage_targets["required_sources"]
    assert ai_safety.coverage_targets["minimum_papers"] != medicine.coverage_targets["minimum_papers"]


def test_search_rounds_record_results_and_failures(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("strategy execution")
    strategy = plan_search_strategy(config, "monitor evasion", source_profile="generic")
    save_strategy(config, strategy)

    rounds = execute_search_strategy(config, state.run_id, strategy.id, sources=[FakeLiveSource(), FailingSource()])
    reloaded = manager.load_run(state.run_id)

    assert rounds
    assert any(round_item.status == "complete" for round_item in rounds)
    assert reloaded.search_rounds
    assert reloaded.search_queries
    assert reloaded.papers


def test_offline_mode_plans_but_does_not_execute(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("offline strategy")
    strategy = plan_search_strategy(config, "offline topic", source_profile="generic")
    save_strategy(config, strategy)

    rounds = execute_search_strategy(config, state.run_id, strategy.id, sources=[FakeLiveSource()])
    reloaded = manager.load_run(state.run_id)

    assert all(round_item.status == "skipped" for round_item in rounds)
    assert reloaded.papers == []
    assert reloaded.search_queries
    assert all(record.result_paper_ids == [] for record in reloaded.search_queries)


def test_novelty_stays_unknown_when_closest_prior_round_missing(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = ResearchStateManager(config).create_run("novelty gate strategy")
    state.search_strategies.append(
        SearchStrategy(
            id="strategy-test",
            topic=state.topic.text,
            source_profile="generic",
            closest_prior_work_queries=["candidate idea closest prior work"],
        )
    )
    state.search_queries.append(
        SearchQueryRecord(
            id="query-1",
            query="candidate idea",
            source_names=["Semantic Scholar"],
            purpose="strategy_initial",
            max_results=5,
            result_paper_ids=["p1"],
        )
    )
    state.source_coverage = SourceCoverageReport(run_id=state.run_id, topic=state.topic.text, confidence="medium")
    candidate = Paper(
        id="p1",
        title="Distant but somewhat related monitoring paper",
        authors=["A"],
        abstract="This paper studies monitoring systems and evaluation.",
        year=2025,
    )

    dossier, assessment = NoveltyDossierBuilder().build(
        state,
        target_id="gap-1",
        idea_summary="low false positive monitoring evaluation",
        query_plan=["low false positive monitoring evaluation"],
        candidates=[candidate],
        source_search_ran=True,
    )

    assert assessment.verdict == "unknown"
    assert "completed closest-prior-work search round" in dossier.missing_searches
