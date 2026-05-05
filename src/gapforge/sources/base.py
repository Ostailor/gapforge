"""Base interfaces and helpers for source connectors."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from datetime import date
from html import unescape

from gapforge.models import Paper, Provenance
from gapforge.state import slugify, utc_now_iso


class SourceError(RuntimeError):
    """Raised when a source cannot return results."""


class ResearchSource(ABC):
    name: str

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        """Return normalized papers for a query."""


class FakeSourceMixin:
    """Deterministic fallback results when a source is unavailable."""

    name: str

    def _fake_paper(self, query: str, index: int, angle: str) -> Paper:
        slug = slugify(query)
        source_slug = slugify(self.name)
        paper_id = f"{source_slug}-{slug}-{index}"
        return Paper(
            id=paper_id,
            title=f"{angle} for {query}",
            authors=[f"{self.name} Research Group"],
            abstract=(
                f"This deterministic fallback studies {query} with emphasis on {angle.lower()}. "
                "It exposes limitations around calibration, transfer, and evaluation realism."
            ),
            year=2021 + index,
            published_date=f"{2021 + index}-01-01",
            venue=self.name,
            source=self.name,
            url=f"https://example.test/{source_slug}/{slug}/{index}",
            pdf_url="",
            citation_count=25 * index,
            keywords=[query],
            raw_metadata={"fallback": True, "angle": angle},
            provenance=source_provenance(self.name, [paper_id], "Deterministic fallback paper generated after source degradation."),
        )


def source_provenance(source_name: str, source_ids: list[str], reasoning_summary: str) -> Provenance:
    return Provenance(
        created_by_skill=f"source:{slugify(source_name)}",
        source_ids=source_ids,
        timestamp=utc_now_iso(),
        reasoning_summary=reasoning_summary,
    )


def stable_paper_id(source: str, *parts: str) -> str:
    joined = "|".join(part for part in parts if part)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(source)}-{digest}"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_doi(value: object) -> str:
    doi = clean_text(value).lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://dx.doi.org/").removeprefix("doi:")
    return doi.strip()


def parse_year(value: object) -> int:
    text = clean_text(value)
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group(0)) if match else 0


def date_parts_to_iso(parts: object) -> str:
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list) or not parts[0]:
        return ""
    year = int(parts[0][0])
    month = int(parts[0][1]) if len(parts[0]) > 1 else 1
    day = int(parts[0][2]) if len(parts[0]) > 2 else 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return str(year)


def format_semantic_year_filter(date_from: str | None, date_to: str | None) -> str:
    start = date_from[:4] if date_from else ""
    end = date_to[:4] if date_to else ""
    if start and end:
        return f"{start}-{end}"
    if start:
        return f"{start}-"
    if end:
        return f"-{end}"
    return ""
