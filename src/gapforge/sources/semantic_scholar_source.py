"""Semantic Scholar source connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.models import Paper
from gapforge.sources.base import (
    FakeSourceMixin,
    ResearchSource,
    clean_text,
    format_semantic_year_filter,
    normalize_doi,
    parse_year,
    source_provenance,
    stable_paper_id,
)
from gapforge.sources.http_client import CachedHttpClient, HttpClientError


class SemanticScholarSource(FakeSourceMixin, ResearchSource):
    name = "Semantic Scholar"
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"

    def __init__(self, http_client: CachedHttpClient | None = None) -> None:
        self.http = http_client or CachedHttpClient(Path.cwd() / ".gapforge_cache")

    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        # The search endpoints reject nested reference/citation fields on many
        # queries. Keep the live search request small and let citation expansion
        # use dedicated resolvers instead of turning source health into fallback
        # metadata.
        params = {
            "query": query,
            "fields": (
                "title,abstract,year,venue,url,authors,citationCount,influentialCitationCount,publicationDate,"
                "openAccessPdf,externalIds,fieldsOfStudy"
            ),
            "sort": _semantic_sort(sort),
            "year": format_semantic_year_filter(date_from, date_to),
        }
        try:
            payload = self.http.get_json(self.endpoint, params, namespace="semantic-scholar")
            return [self._normalize(item) for item in payload.get("data", [])][:max_results]
        except (HttpClientError, ValueError, KeyError, TypeError):
            return [self._fake_paper(query, 1, "Closest prior work retrieval")][:max_results]

    def _normalize(self, item: dict[str, Any]) -> Paper:
        external_ids = item.get("externalIds") or {}
        doi = normalize_doi(external_ids.get("DOI", ""))
        arxiv_id = clean_text(external_ids.get("ArXiv", ""))
        paper_id = (
            clean_text(item.get("paperId", "")) or doi or arxiv_id or stable_paper_id(self.name, item.get("title", ""), item.get("url", ""))
        )
        pdf = item.get("openAccessPdf") or {}
        return Paper(
            id=f"s2:{paper_id}",
            title=clean_text(item.get("title", "")),
            authors=[clean_text(author.get("name", "")) for author in item.get("authors", []) if isinstance(author, dict)],
            abstract=clean_text(item.get("abstract", "")),
            year=int(item.get("year") or parse_year(item.get("publicationDate", "")) or 0),
            published_date=clean_text(item.get("publicationDate", "")),
            venue=clean_text(item.get("venue", "")),
            source=self.name,
            url=clean_text(item.get("url", "")),
            pdf_url=clean_text(pdf.get("url", "")) if isinstance(pdf, dict) else "",
            doi=doi,
            arxiv_id=arxiv_id,
            semantic_scholar_id=clean_text(item.get("paperId", "")),
            citation_count=int(item.get("citationCount") or 0),
            keywords=[clean_text(field) for field in (item.get("fieldsOfStudy") or [])],
            raw_metadata=item,
            provenance=source_provenance(self.name, [paper_id], "Normalized Semantic Scholar Graph API metadata."),
        )


def _semantic_sort(sort: str) -> str:
    if sort == "oldest":
        return "publicationDate:asc"
    if sort in {"newest", "submittedDate"}:
        return "publicationDate:desc"
    if sort == "citations":
        return "citationCount:desc"
    return ""
