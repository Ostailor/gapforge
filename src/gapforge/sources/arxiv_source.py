"""arXiv source connector."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from gapforge.models import Paper
from gapforge.sources.base import FakeSourceMixin, ResearchSource, clean_text, parse_year, source_provenance, stable_paper_id
from gapforge.sources.http_client import CachedHttpClient, HttpClientError


class ArxivSource(FakeSourceMixin, ResearchSource):
    name = "arXiv"
    endpoint = "https://export.arxiv.org/api/query"

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
        search_query = f"all:{query}"
        date_clause = _arxiv_date_clause(date_from, date_to)
        if date_clause:
            search_query = f"{search_query} AND {date_clause}"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate" if sort in {"newest", "oldest", "submittedDate"} else "relevance",
            "sortOrder": "ascending" if sort == "oldest" else "descending",
        }
        try:
            xml_text = self.http.get_text(self.endpoint, params, namespace="arxiv")
            return self._parse(xml_text)[:max_results]
        except (HttpClientError, ET.ParseError, ValueError):
            return [self._fake_paper(query, 1, "Representation learning baselines")][:max_results]

    def _parse(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ns):
            url = clean_text(entry.findtext("atom:id", namespaces=ns))
            arxiv_id = url.rstrip("/").split("/")[-1]
            title = clean_text(entry.findtext("atom:title", namespaces=ns))
            abstract = clean_text(entry.findtext("atom:summary", namespaces=ns))
            published_date = clean_text(entry.findtext("atom:published", namespaces=ns))[:10]
            authors = [clean_text(author.findtext("atom:name", namespaces=ns)) for author in entry.findall("atom:author", ns)]
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href", "")
            doi = clean_text(entry.findtext("arxiv:doi", namespaces=ns))
            categories = [category.attrib.get("term", "") for category in entry.findall("atom:category", ns)]
            paper_id = arxiv_id or stable_paper_id(self.name, title, url)
            papers.append(
                Paper(
                    id=f"arxiv:{paper_id}",
                    title=title,
                    authors=[author for author in authors if author],
                    abstract=abstract,
                    year=parse_year(published_date),
                    published_date=published_date,
                    venue="arXiv",
                    source=self.name,
                    url=url,
                    pdf_url=pdf_url,
                    doi=doi,
                    arxiv_id=arxiv_id,
                    keywords=[item for item in categories if item],
                    raw_metadata={"arxiv_categories": categories},
                    provenance=source_provenance(self.name, [paper_id], "Normalized arXiv Atom entry from the public API."),
                )
            )
        return papers


def _arxiv_date_clause(date_from: str | None, date_to: str | None) -> str:
    if not date_from and not date_to:
        return ""
    start = (date_from or "1900-01-01").replace("-", "") + "000000"
    end = (date_to or "2999-12-31").replace("-", "") + "235959"
    return f"submittedDate:[{start} TO {end}]"
