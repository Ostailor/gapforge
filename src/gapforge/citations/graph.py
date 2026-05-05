"""Citation graph construction from available paper metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gapforge.citations.resolvers import MetadataReferenceResolver, reference_label
from gapforge.models import CitationEdge, CitationGraph, Paper, Provenance, ReferenceRecord, ResearchRunState


class CitationGraphBuilder:
    """Build a graph only from explicit metadata; unresolved items stay unresolved."""

    def build(self, state: ResearchRunState) -> CitationGraph:
        resolver = MetadataReferenceResolver(state.papers)
        edges: list[CitationEdge] = []
        unresolved: list[str] = []
        for paper in state.papers:
            references = _metadata_list(paper, "references")
            citations = _metadata_list(paper, "citations")
            related = _metadata_list(paper, "relatedPapers") or _metadata_list(paper, "related_papers")
            influential = paper.raw_metadata.get("influentialCitationCount")
            if influential is not None:
                paper.raw_metadata.setdefault("citation_graph", {})["influentialCitationCount"] = influential
            for reference in references:
                target = resolver.resolve(reference)
                if target is None:
                    unresolved.append(f"{paper.id} cites unresolved reference: {reference_label(reference)}")
                    continue
                edges.append(_edge(paper.id, target.id, "cites", "Semantic Scholar", 0.85, [paper.id, target.id]))
            for citation in citations:
                citing = resolver.resolve(citation)
                if citing is None:
                    unresolved.append(f"{paper.id} has unresolved citing paper: {reference_label(citation)}")
                    continue
                edges.append(_edge(paper.id, citing.id, "cited_by", "Semantic Scholar", 0.75, [paper.id, citing.id]))
            for item in related:
                target = resolver.resolve(item)
                if target is None:
                    unresolved.append(f"{paper.id} has unresolved related paper: {reference_label(item)}")
                    continue
                edges.append(_edge(paper.id, target.id, "related", "Semantic Scholar", 0.65, [paper.id, target.id]))
            if paper.doi:
                _add_identifier_edges(edges, paper, state.papers, attr="doi", edge_type="same_doi")
            if paper.arxiv_id:
                _add_identifier_edges(edges, paper, state.papers, attr="arxiv_id", edge_type="same_arxiv")
        for record in state.references:
            if record.resolved_paper_id:
                edges.append(
                    _edge(record.paper_id, record.resolved_paper_id, "cites", "parsed references", 0.7, [record.paper_id, record.id])
                )
            else:
                unresolved.append(f"{record.paper_id} cites unresolved parsed reference: {_reference_record_label(record)}")
        graph = CitationGraph(
            paper_ids=[paper.id for paper in state.papers],
            edges=_dedupe_edges(edges),
            unresolved_references=_dedupe_strings(unresolved),
            provenance=Provenance(
                created_by_skill="citation-graph-builder",
                source_ids=[paper.id for paper in state.papers],
                timestamp=_utc_now_iso(),
                reasoning_summary="Built citation graph from explicit paper metadata; unresolved references were not fabricated.",
            ),
        )
        state.citation_graph = graph
        return graph


def _metadata_list(paper: Paper, key: str) -> list[dict[str, Any]]:
    value = paper.raw_metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _reference_record_label(record: ReferenceRecord) -> str:
    return record.parsed_title or record.doi or record.arxiv_id or record.raw_reference[:120]


def _edge(
    source_paper_id: str,
    target_paper_id: str,
    edge_type: str,
    source: str,
    confidence: float,
    source_ids: list[str],
) -> CitationEdge:
    return CitationEdge(
        source_paper_id=source_paper_id,
        target_paper_id=target_paper_id,
        edge_type=edge_type,
        source=source,
        confidence=f"{confidence:.2f}",
        provenance=Provenance(
            created_by_skill="citation-graph-builder",
            source_ids=source_ids,
            timestamp=_utc_now_iso(),
            reasoning_summary=f"Created {edge_type} edge from explicit citation or identifier metadata.",
        ),
    )


def _add_identifier_edges(edges: list[CitationEdge], paper: Paper, papers: list[Paper], *, attr: str, edge_type: str) -> None:
    value = getattr(paper, attr)
    for other in papers:
        if other.id != paper.id and getattr(other, attr) and getattr(other, attr) == value:
            edges.append(_edge(paper.id, other.id, edge_type, "metadata", 1.0, [paper.id, other.id]))


def _dedupe_edges(edges: list[CitationEdge]) -> list[CitationEdge]:
    seen: set[tuple[str, str, str]] = set()
    result: list[CitationEdge] = []
    for edge in edges:
        key = (edge.source_paper_id, edge.target_paper_id, edge.edge_type)
        if key not in seen:
            result.append(edge)
            seen.add(key)
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
