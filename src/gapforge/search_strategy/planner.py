"""Plan and execute multi-round live literature search strategies."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, SearchRound, SearchStrategy, from_dict, to_plain
from gapforge.search_strategy.coverage_targets import coverage_targets_for_profile
from gapforge.search_strategy.query_sets import (
    adjacent_field_queries,
    benchmark_queries,
    closest_prior_work_queries,
    dataset_queries,
    exclusion_queries,
    method_queries,
    primary_queries,
    recency_queries,
    survey_queries,
)
from gapforge.sources.base import ResearchSource
from gapforge.sources.coverage import add_search_query_record, refresh_source_coverage
from gapforge.sources.health import source_name_key
from gapforge.sources.policies import get_source_policy_profile
from gapforge.state import ResearchStateManager, slugify, utc_now_compact, utc_now_iso


def plan_search_strategy(config: GapForgeConfig, topic: str, *, source_profile: str = "generic") -> SearchStrategy:
    profile = get_source_policy_profile(source_profile)
    expected_sources = _dedupe([*profile.required_sources, *profile.recommended_sources])
    return SearchStrategy(
        id=f"strategy-{slugify(source_profile)}-{slugify(topic)[:48]}-{utc_now_compact()}",
        topic=topic,
        source_profile=profile.id,
        primary_queries=primary_queries(topic),
        recency_queries=recency_queries(topic),
        survey_queries=survey_queries(topic, profile),
        benchmark_queries=benchmark_queries(topic),
        dataset_queries=dataset_queries(topic),
        method_queries=method_queries(topic),
        closest_prior_work_queries=closest_prior_work_queries(topic),
        adjacent_field_queries=adjacent_field_queries(topic, profile),
        exclusion_queries=exclusion_queries(topic),
        expected_sources=expected_sources,
        coverage_targets=coverage_targets_for_profile(profile),
        provenance=Provenance(
            created_by_skill="search-strategy-planner",
            source_ids=[profile.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Planned multi-round search strategy before synthesis or novelty claims.",
        ),
    )


def save_strategy(config: GapForgeConfig, strategy: SearchStrategy) -> tuple[Path, Path]:
    out_dir = config.data_dir / "search_strategies"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{strategy.id}.json"
    md_path = out_dir / f"{strategy.id}.md"
    json_path.write_text(json.dumps(to_plain(strategy), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_search_strategy_markdown(strategy), encoding="utf-8")
    return json_path, md_path


def load_strategy(config: GapForgeConfig, strategy_id: str) -> SearchStrategy:
    path = config.data_dir / "search_strategies" / f"{strategy_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No search strategy found for {strategy_id}")
    return from_dict(SearchStrategy, json.loads(path.read_text(encoding="utf-8")))


def execute_search_strategy(
    config: GapForgeConfig,
    run_id: str,
    strategy_id: str,
    *,
    sources: Iterable[ResearchSource] | None = None,
) -> list[SearchRound]:
    manager = ResearchStateManager(config)
    state = manager.load_run(run_id)
    strategy = _strategy_for_state(config, state.search_strategies, strategy_id)
    if strategy.id not in {item.id for item in state.search_strategies}:
        state.search_strategies.append(strategy)
    planned_rounds = _rounds_for_strategy(strategy)
    existing = {round_item.id: round_item for round_item in state.search_rounds}
    source_map = _source_map(sources if sources is not None else _default_sources(config))
    executed_rounds: list[SearchRound] = []
    all_new_papers: list[Paper] = []
    for round_item in planned_rounds:
        current = existing.get(round_item.id, round_item)
        if current.status == "complete":
            executed_rounds.append(current)
            continue
        all_new_papers.extend(_execute_round(state, current, source_map))
        existing[current.id] = current
        executed_rounds.append(current)
    state.search_rounds = list(existing.values())
    state.papers = _merge_papers(state.papers, all_new_papers)
    refresh_source_coverage(state)
    manager.save_run(state)
    return executed_rounds


def render_search_strategy_markdown(strategy: SearchStrategy) -> str:
    lines = [
        f"# Search Strategy: {strategy.topic}",
        "",
        f"- Strategy ID: `{strategy.id}`",
        f"- Source profile: `{strategy.source_profile}`",
        f"- Expected sources: {', '.join(strategy.expected_sources) or 'none'}",
        "",
    ]
    for label, queries in [
        ("Primary", strategy.primary_queries),
        ("Recency", strategy.recency_queries),
        ("Survey/Canonical", strategy.survey_queries),
        ("Benchmark", strategy.benchmark_queries),
        ("Dataset", strategy.dataset_queries),
        ("Method", strategy.method_queries),
        ("Closest Prior Work", strategy.closest_prior_work_queries),
        ("Adjacent Field", strategy.adjacent_field_queries),
        ("Exclusion/Counterevidence", strategy.exclusion_queries),
    ]:
        lines.extend([f"## {label} Queries", ""])
        lines.extend([f"- {query}" for query in queries] or ["- none"])
        lines.append("")
    lines.extend(["## Coverage Targets", ""])
    for key, value in strategy.coverage_targets.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def render_search_rounds_markdown(rounds: list[SearchRound]) -> str:
    lines = ["# Search Rounds", ""]
    if not rounds:
        lines.append("No search rounds recorded.")
        return "\n".join(lines) + "\n"
    for round_item in rounds:
        lines.extend(
            [
                f"## {round_item.id}",
                "",
                f"- Type: {round_item.round_type}",
                f"- Status: {round_item.status}",
                f"- Sources: {', '.join(round_item.sources) or 'none'}",
                f"- Max results: {round_item.max_results}",
                f"- Results: {len(round_item.result_paper_ids)}",
                f"- Failures: {len(round_item.failures)}",
                "",
                "Queries:",
                "",
            ]
        )
        lines.extend(f"- {query}" for query in round_item.queries)
        if round_item.failures:
            lines.extend(["", "Failures:", ""])
            lines.extend(f"- {failure}" for failure in round_item.failures)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def closest_prior_work_round_complete(rounds: list[SearchRound]) -> bool:
    return any(round_item.round_type in {"novelty", "counterevidence"} and round_item.status == "complete" for round_item in rounds)


def search_round_requirement_status(rounds: list[SearchRound]) -> dict[str, bool]:
    completed = {round_item.round_type for round_item in rounds if round_item.status == "complete"}
    return {
        "exact_phrase_search": "initial" in completed,
        "method_metric_search": "novelty" in completed,
        "benchmark_dataset_search": "benchmark" in completed,
        "survey_search": "survey" in completed,
        "citation_neighborhood_search": any(
            round_item.status == "complete" and "citation" in round_item.round_type for round_item in rounds
        ),
        "adjacent_field_search": "adjacent_field" in completed,
        "counterevidence_search": "counterevidence" in completed,
    }


def _rounds_for_strategy(strategy: SearchStrategy) -> list[SearchRound]:
    sources = list(strategy.expected_sources)
    return [
        _round(strategy, "initial", strategy.primary_queries + strategy.recency_queries, sources, 12),
        _round(strategy, "survey", strategy.survey_queries, sources, 8),
        _round(strategy, "benchmark", strategy.benchmark_queries + strategy.dataset_queries, sources, 8),
        _round(strategy, "novelty", strategy.closest_prior_work_queries, sources, 12),
        _round(strategy, "adjacent_field", strategy.adjacent_field_queries, sources, 8),
        _round(strategy, "counterevidence", strategy.exclusion_queries, sources, 8),
    ]


def _round(strategy: SearchStrategy, round_type: str, queries: list[str], sources: list[str], max_results: int) -> SearchRound:
    return SearchRound(
        id=f"{strategy.id}-{round_type}",
        strategy_id=strategy.id,
        round_type=round_type,
        queries=_dedupe(queries),
        sources=sources,
        max_results=max_results,
        status="planned",
        provenance=Provenance(
            created_by_skill="search-strategy-planner",
            source_ids=[strategy.id],
            timestamp=utc_now_iso(),
            reasoning_summary=f"Planned {round_type} search round.",
        ),
    )


def _execute_round(state, round_item: SearchRound, source_map: dict[str, ResearchSource]) -> list[Paper]:
    if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
        round_item.status = "skipped"
        round_item.failures = ["Network disabled by GAPFORGE_DISABLE_NETWORK=1; search round was planned but not executed."]
        for query in round_item.queries:
            add_search_query_record(
                state,
                query=query,
                source_names=round_item.sources,
                purpose=f"strategy_{round_item.round_type}",
                max_results=round_item.max_results,
                date_from=None,
                date_to=None,
                result_paper_ids=[],
                failure_messages=round_item.failures,
            )
        return []
    selected = [source_map[key] for key in [source_name_key(source) for source in round_item.sources] if key in source_map]
    if not selected:
        round_item.status = "failed"
        round_item.failures = [f"No configured sources matched: {', '.join(round_item.sources)}"]
        for query in round_item.queries:
            add_search_query_record(
                state,
                query=query,
                source_names=[],
                purpose=f"strategy_{round_item.round_type}",
                max_results=round_item.max_results,
                date_from=None,
                date_to=None,
                result_paper_ids=[],
                failure_messages=round_item.failures,
            )
        return []
    result_ids: list[str] = []
    failures: list[str] = []
    new_papers: list[Paper] = []
    per_source = max(1, round_item.max_results // max(1, len(selected)))
    for query in round_item.queries:
        if len(_dedupe(result_ids)) >= round_item.max_results:
            break
        query_papers: list[Paper] = []
        query_failures: list[str] = []
        for source in selected:
            if len(_dedupe(result_ids)) >= round_item.max_results:
                break
            try:
                found = source.search(query, max_results=per_source, sort="newest", date_from=None, date_to=None)
                query_papers.extend(found)
                result_ids.extend(paper.id for paper in found)
            except Exception as exc:
                query_failures.append(f"{source.name} failed for {query!r}: {exc}")
        new_papers.extend(query_papers)
        failures.extend(query_failures)
        add_search_query_record(
            state,
            query=query,
            source_names=[source.name for source in selected],
            purpose=f"strategy_{round_item.round_type}",
            max_results=round_item.max_results,
            date_from=None,
            date_to=None,
            result_paper_ids=[paper.id for paper in query_papers],
            failure_messages=query_failures,
        )
    round_item.result_paper_ids = _dedupe(result_ids)
    round_item.failures = failures
    round_item.status = "complete" if result_ids else "failed"
    return new_papers


def _strategy_for_state(config: GapForgeConfig, strategies: list[SearchStrategy], strategy_id: str) -> SearchStrategy:
    for strategy in strategies:
        if strategy.id == strategy_id:
            return strategy
    return load_strategy(config, strategy_id)


def _source_map(sources: Iterable[ResearchSource]) -> dict[str, ResearchSource]:
    return {source_name_key(source.name): source for source in sources}


def _default_sources(config: GapForgeConfig):
    from gapforge.skill_registry import default_sources

    return default_sources(config)


def _merge_papers(existing: list[Paper], incoming: list[Paper]) -> list[Paper]:
    by_id = {paper.id: paper for paper in existing}
    for paper in incoming:
        by_id.setdefault(paper.id, paper)
    return list(by_id.values())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
