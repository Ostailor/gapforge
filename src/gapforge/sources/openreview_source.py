"""OpenReview source connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.models import Paper
from gapforge.sources.base import FakeSourceMixin, ResearchSource, clean_text, parse_year, source_provenance, stable_paper_id
from gapforge.sources.http_client import CachedHttpClient, HttpClientError


class OpenReviewSource(FakeSourceMixin, ResearchSource):
    name = "OpenReview"
    endpoint = "https://api2.openreview.net/notes/search"

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
        params = {"query": query, "content": "all", "source": "forum", "limit": max_results}
        try:
            payload = self.http.get_json(self.endpoint, params, namespace="openreview")
            notes = payload.get("notes") or payload.get("results") or []
            return [_normalize_note(note) for note in notes][:max_results]
        except (HttpClientError, ValueError, KeyError, TypeError):
            return [self._fake_paper(query, 1, "Reviewer concern analysis")][:max_results]


def _normalize_note(note: dict[str, Any]) -> Paper:
    content = note.get("content") or {}
    title = _content_value(content.get("title"))
    abstract = _content_value(content.get("abstract"))
    authors = _content_list(content.get("authors"))
    venue = _content_value(content.get("venue")) or _content_value(content.get("venueid")) or clean_text(note.get("domain", "OpenReview"))
    openreview_id = clean_text(note.get("id", ""))
    year = parse_year(note.get("pdate") or note.get("cdate") or venue)
    url = f"https://openreview.net/forum?id={openreview_id}" if openreview_id else ""
    paper_id = openreview_id or stable_paper_id("OpenReview", title, url)
    return Paper(
        id=f"openreview:{paper_id}",
        title=title,
        authors=authors,
        abstract=abstract,
        year=year,
        published_date=str(year) if year else "",
        venue=venue,
        source="OpenReview",
        url=url,
        openreview_id=openreview_id,
        keywords=_content_list(content.get("keywords") or content.get("subject_areas")),
        raw_metadata=note,
        provenance=source_provenance("OpenReview", [paper_id], "Normalized OpenReview note search metadata."),
    )


def _content_value(value: object) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("value", ""))
    return clean_text(value)


def _content_list(value: object) -> list[str]:
    if isinstance(value, dict):
        value = value.get("value", [])
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    text = clean_text(value)
    return [text] if text else []
