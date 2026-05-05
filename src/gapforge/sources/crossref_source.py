"""Crossref source connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.models import Paper
from gapforge.sources.base import (
    FakeSourceMixin,
    ResearchSource,
    clean_text,
    date_parts_to_iso,
    normalize_doi,
    parse_year,
    source_provenance,
    stable_paper_id,
)
from gapforge.sources.http_client import CachedHttpClient, HttpClientError


class CrossrefSource(FakeSourceMixin, ResearchSource):
    name = "Crossref"
    endpoint = "https://api.crossref.org/works"

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
        filters = []
        if date_from:
            filters.append(f"from-pub-date:{date_from}")
        if date_to:
            filters.append(f"until-pub-date:{date_to}")
        params = {
            "query.bibliographic": query,
            "rows": max_results,
            "sort": "published" if sort in {"newest", "oldest"} else "relevance",
            "order": "asc" if sort == "oldest" else "desc",
            "filter": ",".join(filters),
        }
        try:
            payload = self.http.get_json(self.endpoint, params, namespace="crossref")
            return [self._normalize(item) for item in payload.get("message", {}).get("items", [])][:max_results]
        except (HttpClientError, ValueError, KeyError, TypeError):
            return [self._fake_paper(query, 1, "Measurement validity studies")][:max_results]

    def _normalize(self, item: dict[str, Any]) -> Paper:
        doi = normalize_doi(item.get("DOI", ""))
        title = clean_text(item.get("title", [""]))
        abstract = clean_text(item.get("abstract", ""))
        published_date = (
            date_parts_to_iso(item.get("published-print", {}).get("date-parts"))
            or date_parts_to_iso(item.get("published-online", {}).get("date-parts"))
            or date_parts_to_iso(item.get("issued", {}).get("date-parts"))
        )
        authors = [_author_name(author) for author in item.get("author", []) if isinstance(author, dict)]
        venue = clean_text(item.get("container-title", [""])) or clean_text(item.get("publisher", ""))
        url = clean_text(item.get("URL", ""))
        paper_id = doi or stable_paper_id(self.name, title, url)
        return Paper(
            id=f"doi:{doi}" if doi else paper_id,
            title=title,
            authors=[author for author in authors if author],
            abstract=abstract,
            year=parse_year(published_date),
            published_date=published_date,
            venue=venue,
            source=self.name,
            url=url,
            doi=doi,
            citation_count=int(item.get("is-referenced-by-count") or 0),
            keywords=[clean_text(subject) for subject in item.get("subject", [])],
            raw_metadata=item,
            provenance=source_provenance(self.name, [paper_id], "Normalized Crossref Works metadata from the public REST API."),
        )


def _author_name(author: dict[str, Any]) -> str:
    given = clean_text(author.get("given", ""))
    family = clean_text(author.get("family", ""))
    literal = clean_text(author.get("name", ""))
    return " ".join(part for part in [given, family] if part) or literal
