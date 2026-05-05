"""Deterministic query planning for closest-prior-work dossiers."""

from __future__ import annotations

import re

from gapforge.models import Gap, Paper, ResearchRunState


class NoveltyQueryPlanner:
    def plan(self, state: ResearchRunState, target_id: str, summary: str, gap: Gap | None = None) -> list[str]:
        queries: list[str] = []
        title = _target_title(target_id, summary, gap)
        terms = _keywords(summary, limit=7)
        method_terms = [term for term in terms if term in METHOD_HINTS]
        metric_terms = [term for term in terms if term in METRIC_HINTS]
        dataset_terms = [term for term in terms if term in DATASET_HINTS]
        if title:
            queries.extend([f'"{title}"', f'"{title}" benchmark', f'"{title}" limitations'])
        if method_terms or metric_terms:
            queries.append(" ".join(method_terms + metric_terms + ["prior work"]).strip())
        if dataset_terms:
            queries.append(" ".join(dataset_terms + ["benchmark dataset evaluation"]).strip())
        if gap is not None:
            if gap.minimum_experiment_needed:
                queries.append(f"{gap.minimum_experiment_needed} closest prior work")
            if gap.type:
                queries.append(f"{state.topic.text} {gap.type} failure mode")
            queries.append(f"{state.topic.text} {gap.title} limitations")
        for analogy in state.cross_domain_analogies:
            if gap is None or analogy.target_gap_id == gap.id:
                queries.extend(analogy.papers_or_sources_to_search[:2])
        if state.citation_graph is not None:
            for reference in state.citation_graph.unresolved_references[:5]:
                queries.append(f"{_reference_query(reference)} prior work")
            for edge in state.citation_graph.edges[:8]:
                queries.append(f"{edge.source_paper_id} {edge.edge_type} {edge.target_paper_id} closest prior work")
        for paper in _close_identifier_papers(state, summary):
            if paper.doi:
                queries.append(paper.doi)
            if paper.arxiv_id:
                queries.append(paper.arxiv_id)
        queries.extend([f"{state.topic.text} survey", f"{state.topic.text} systematic review"])
        return _dedupe([query for query in queries if query.strip()])


METHOD_HINTS = {
    "calibration",
    "abstention",
    "graph",
    "neural",
    "detector",
    "detection",
    "classification",
    "benchmark",
    "measurement",
    "provenance",
}
METRIC_HINTS = {"precision", "recall", "false", "positive", "fpr", "auc", "specificity", "calibration"}
DATASET_HINTS = {"dataset", "benchmark", "corpus", "labels", "ground", "truth", "deployment"}
STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "under", "work", "paper"}


def _target_title(target_id: str, summary: str, gap: Gap | None) -> str:
    if gap is not None and gap.title:
        return gap.title
    return " ".join(_keywords(summary, limit=8)) or target_id


def _close_identifier_papers(state: ResearchRunState, summary: str) -> list[Paper]:
    summary_tokens = set(_keywords(summary, limit=20))
    close = []
    for paper in state.papers:
        paper_tokens = set(_keywords(" ".join([paper.title, paper.abstract]), limit=40))
        if summary_tokens and len(summary_tokens & paper_tokens) / len(summary_tokens) >= 0.4:
            close.append(paper)
    return close[:5]


def _keywords(text: str, *, limit: int) -> list[str]:
    result: list[str] = []
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token not in STOP_WORDS and len(token) > 2 and token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result


def _reference_query(reference: str) -> str:
    return reference.split(":", 1)[-1].split("|", 1)[0].strip()[:160]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result
