"""DBLP source connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.models import Paper
from gapforge.sources.base import FakeSourceMixin, ResearchSource, clean_text, parse_year, source_provenance, stable_paper_id
from gapforge.sources.http_client import CachedHttpClient, HttpClientError


class DblpSource(FakeSourceMixin, ResearchSource):
    name = "DBLP"
    endpoint = "https://dblp.org/search/publ/api"

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
        params = {"q": query, "format": "json", "h": max_results, "c": 0}
        try:
            payload = self.http.get_json(self.endpoint, params, namespace="dblp")
            hits = payload.get("result", {}).get("hits", {}).get("hit", [])
            papers = [self._normalize(hit) for hit in hits]
            return _filter_dates(papers, date_from, date_to)[:max_results]
        except (HttpClientError, ValueError, KeyError, TypeError):
            return [self._fake_paper(query, 1, "Graph mining systems")][:max_results]

    def _normalize(self, hit: dict[str, Any]) -> Paper:
        info = hit.get("info", {})
        title = clean_text(info.get("title", ""))
        url = clean_text(info.get("url", ""))
        doi = clean_text(info.get("doi", ""))
        year = parse_year(info.get("year", ""))
        authors = _dblp_authors(info.get("authors", {}).get("author", []))
        venue = clean_text(info.get("venue", ""))
        paper_id = doi or clean_text(info.get("key", "")) or stable_paper_id(self.name, title, url)
        return Paper(
            id=f"dblp:{paper_id}",
            title=title,
            authors=authors,
            abstract="",
            year=year,
            published_date=str(year) if year else "",
            venue=venue,
            source=self.name,
            url=url,
            doi=doi,
            raw_metadata=hit,
            provenance=source_provenance(self.name, [paper_id], "Normalized DBLP publication search metadata."),
        )


def _dblp_authors(raw_authors: object) -> list[str]:
    if isinstance(raw_authors, dict):
        return [clean_text(raw_authors.get("text", ""))]
    if isinstance(raw_authors, list):
        return [clean_text(author.get("text", author)) if isinstance(author, dict) else clean_text(author) for author in raw_authors]
    return []


def _filter_dates(papers: list[Paper], date_from: str | None, date_to: str | None) -> list[Paper]:
    if not date_from and not date_to:
        return papers
    start_year = parse_year(date_from) if date_from else 0
    end_year = parse_year(date_to) if date_to else 9999
    return [paper for paper in papers if start_year <= paper.year <= end_year]
