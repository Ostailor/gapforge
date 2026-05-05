"""Related-work expansion planning and execution."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from gapforge.models import Gap, Paper, ResearchRunState
from gapforge.sources.coverage import add_search_query_record, refresh_source_coverage
from gapforge.sources.ranking import rank_papers

METHOD_TERMS = {
    "benchmark",
    "dataset",
    "evaluation",
    "calibration",
    "false positive",
    "graph",
    "anomaly detection",
    "collusion",
    "measurement",
}


class CitationExpansionPlanner:
    """Plan conservative related-work searches from important papers and gaps."""

    def plan(self, state: ResearchRunState, *, paper_id: str | None = None, max_queries: int = 20) -> list[str]:
        papers = _target_papers(state, paper_id=paper_id)
        gaps = state.gaps[:5]
        queries: list[str] = []
        for paper in papers:
            if paper.title:
                queries.append(f'"{paper.title}" benchmark')
                queries.append(f'"{paper.title}" survey')
                queries.append(f'"{paper.title}" systematic review')
            if paper.doi:
                queries.append(paper.doi)
            if paper.arxiv_id:
                queries.append(paper.arxiv_id)
            method_terms = _method_terms(paper)
            if paper.authors and method_terms:
                queries.append(f"{paper.authors[0]} {' '.join(method_terms[:3])}")
            for reference in _unresolved_for_paper(state, paper.id)[:3]:
                queries.append(f"{_reference_query_text(reference)} related work")
        for gap in gaps:
            queries.extend(_gap_queries(state.topic.text, gap))
        for assessment in state.novelty_assessments:
            for prior in assessment.closest_prior_work[:2]:
                title = prior.split(":", 1)[-1].strip()
                if title:
                    queries.append(f"{title} benchmark")
                    queries.append(f"{title} cited by")
        return _dedupe_queries(queries)[:max_queries]


class RelatedWorkExpander:
    """Execute planned expansion queries through existing source connectors."""

    def __init__(self, sources: Iterable[Any]) -> None:
        self.sources = list(sources)
        self.planner = CitationExpansionPlanner()

    def expand(
        self,
        state: ResearchRunState,
        *,
        max_new_papers: int = 30,
        paper_id: str | None = None,
    ) -> list[Paper]:
        queries = self.planner.plan(state, paper_id=paper_id, max_queries=max(4, min(20, max_new_papers)))
        added: list[Paper] = []
        failures: list[str] = []
        seen_before = {paper.id for paper in state.papers}
        for query in queries:
            if len(added) >= max_new_papers:
                break
            found_for_query: list[Paper] = []
            failure_for_query: list[str] = []
            for source in self.sources:
                source_name = str(getattr(source, "name", source.__class__.__name__))
                try:
                    found = source.search(query, max_results=3, sort="newest", date_from=None, date_to=None)
                except Exception as exc:
                    failure = f"{source_name} search failed for {query!r}: {exc}"
                    failure_for_query.append(failure)
                    failures.append(failure)
                    continue
                found_for_query.extend(found)
            add_search_query_record(
                state,
                query=query,
                source_names=[str(getattr(source, "name", source.__class__.__name__)) for source in self.sources],
                purpose="citation_expansion",
                max_results=3 * max(1, len(self.sources)),
                date_from=None,
                date_to=None,
                result_paper_ids=[paper.id for paper in found_for_query],
                failure_messages=failure_for_query,
            )
            merged = rank_papers(state.topic.text, state.papers + found_for_query, newest_first=True)
            new_ids = [paper.id for paper in merged if paper.id not in seen_before]
            state.papers = merged[: max(len(state.papers), len(state.papers) + max_new_papers)]
            newly_added = [paper for paper in state.papers if paper.id in new_ids and paper.id not in {item.id for item in added}]
            added.extend(newly_added[: max_new_papers - len(added)])
            seen_before.update(paper.id for paper in added)
        refresh_source_coverage(state, failures)
        _write_expansion_markdown(state, queries, added, failures)
        return added


def _target_papers(state: ResearchRunState, *, paper_id: str | None) -> list[Paper]:
    if paper_id is not None:
        return [paper for paper in state.papers if paper.id == paper_id]
    if state.paper_triage is None:
        return state.papers[:5]
    tier1_ids = {decision.paper_id for decision in state.paper_triage.decisions if decision.tier == "Tier 1"}
    selected = [paper for paper in state.papers if paper.id in tier1_ids]
    return selected or state.papers[:5]


def _method_terms(paper: Paper) -> list[str]:
    text = " ".join([paper.title, paper.abstract, " ".join(paper.keywords)]).lower()
    return [term for term in METHOD_TERMS if term in text]


def _unresolved_for_paper(state: ResearchRunState, paper_id: str) -> list[str]:
    if state.citation_graph is None:
        return []
    prefix = f"{paper_id} "
    return [item for item in state.citation_graph.unresolved_references if item.startswith(prefix)]


def _reference_query_text(reference: str) -> str:
    text = reference.split(":", 1)[-1]
    text = text.split("|", 1)[0]
    return " ".join(text.split())[:160]


def _gap_queries(topic: str, gap: Gap) -> list[str]:
    parts = " ".join([gap.title, gap.type, gap.minimum_experiment_needed]).strip()
    if not parts:
        parts = gap.description[:120]
    return [
        f"{topic} {parts} survey",
        f"{topic} {parts} benchmark",
    ]


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        key = query.lower().strip()
        if key and key not in seen:
            result.append(query.strip())
            seen.add(key)
    return result


def _write_expansion_markdown(state: ResearchRunState, queries: list[str], added: list[Paper], failures: list[str]) -> None:
    path = Path(state.run_dir) / "related_work_expansion.md"
    lines = [
        f"# Related Work Expansion: {state.topic.text}",
        "",
        f"- Queries planned: {len(queries)}",
        f"- New papers added: {len(added)}",
        f"- Source failures: {len(failures)}",
        "",
        "## Queries",
        "",
    ]
    lines.extend([f"- {query}" for query in queries] or ["- none"])
    lines.extend(["", "## Added Papers", ""])
    lines.extend([f"- `{paper.id}` {paper.title} ({paper.source or 'unknown source'})" for paper in added] or ["- none"])
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in failures] or ["- none"])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
