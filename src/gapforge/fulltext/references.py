"""Reference extraction from parsed full-text sections."""

from __future__ import annotations

import re

from gapforge.models import PaperSection, Provenance, ReferenceRecord, ResearchRunState
from gapforge.state import utc_now_iso

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
ARXIV_RE = re.compile(r"\barXiv[:\s]+([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z-]+/[0-9]{7}(?:v\d+)?)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def parse_references_from_state(state: ResearchRunState) -> list[ReferenceRecord]:
    records: list[ReferenceRecord] = []
    for section in _reference_sections(state.paper_sections):
        for index, raw in enumerate(split_references(section.text), start=1):
            records.append(parse_reference(section.paper_id, raw, index=index, section_id=section.id))
    state.references = _dedupe_references(records)
    return state.references


def split_references(text: str) -> list[str]:
    """Split a references section into citation strings using common numbering styles."""

    cleaned = text.strip()
    if not cleaned:
        return []
    normalized = re.sub(r"\n\s*\[(\d+)\]\s+", r"\n[\1] ", cleaned)
    parts = re.split(r"\n(?=(?:\[\d+\]|\d+\.|\d+\)|[A-Z][A-Za-z-]+,\s+[A-Z]))", normalized)
    if len(parts) == 1:
        parts = re.split(r"(?<=\.)\s+(?=\[\d+\]|\d+\.|\d+\))", normalized)
    refs = [re.sub(r"\s+", " ", part).strip() for part in parts]
    return [ref for ref in refs if len(ref) >= 20]


def parse_reference(paper_id: str, raw_reference: str, *, index: int, section_id: str = "") -> ReferenceRecord:
    doi = _first(DOI_RE.findall(raw_reference))
    arxiv = _first(ARXIV_RE.findall(raw_reference))
    year_match = YEAR_RE.search(raw_reference)
    year = int(year_match.group(0)) if year_match else 0
    title = _parse_title(raw_reference)
    authors = _parse_authors(raw_reference)
    venue = _parse_venue(raw_reference, title)
    return ReferenceRecord(
        id=f"ref-{paper_id}-{index}",
        paper_id=paper_id,
        raw_reference=raw_reference,
        parsed_title=title,
        parsed_authors=authors,
        parsed_year=year,
        parsed_venue=venue,
        doi=doi,
        arxiv_id=arxiv,
        confidence="medium" if title or doi or arxiv else "low",
        provenance=Provenance(
            created_by_skill="reference-parser",
            source_ids=[paper_id, section_id] if section_id else [paper_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Parsed reference text deterministically from a detected references section.",
        ),
    )


def resolve_references(state: ResearchRunState) -> None:
    papers_by_doi = {paper.doi.lower(): paper.id for paper in state.papers if paper.doi}
    papers_by_arxiv = {paper.arxiv_id.lower(): paper.id for paper in state.papers if paper.arxiv_id}
    title_index = {_norm(paper.title): paper.id for paper in state.papers if paper.title}
    for record in state.references:
        if record.doi and record.doi.lower() in papers_by_doi:
            record.resolved_paper_id = papers_by_doi[record.doi.lower()]
        elif record.arxiv_id and record.arxiv_id.lower() in papers_by_arxiv:
            record.resolved_paper_id = papers_by_arxiv[record.arxiv_id.lower()]
        elif record.parsed_title and _norm(record.parsed_title) in title_index:
            record.resolved_paper_id = title_index[_norm(record.parsed_title)]


def _reference_sections(sections: list[PaperSection]) -> list[PaperSection]:
    return [
        section
        for section in sections
        if section.section_type in {"references", "unknown", "appendix"}
        and (section.normalized_title.lower() in {"references", "bibliography"} or section.title.lower() in {"references", "bibliography"})
    ]


def _parse_title(raw: str) -> str:
    quoted = re.search(r"[\"“](.*?)[\"”]", raw)
    if quoted:
        return quoted.group(1).strip(" .")
    parts = [part.strip() for part in re.split(r"\.\s+", raw) if part.strip()]
    for part in parts[1:3]:
        if len(part.split()) >= 3 and not YEAR_RE.fullmatch(part):
            return re.sub(r"^\[\d+\]\s*", "", part).strip(" .")
    return ""


def _parse_authors(raw: str) -> list[str]:
    first = re.split(r"\.\s+", raw, maxsplit=1)[0]
    first = re.sub(r"^\[\d+\]\s*", "", first).strip()
    if YEAR_RE.search(first):
        first = first[: YEAR_RE.search(first).start()].strip(" ,(")  # type: ignore[union-attr]
    authors = re.split(r"\s+and\s+|,\s+(?=[A-Z][A-Za-z-]+(?:\s+[A-Z]\.)?)", first)
    return [author.strip(" ,") for author in authors if len(author.strip(" ,")) >= 2][:12]


def _parse_venue(raw: str, title: str) -> str:
    if title and title in raw:
        tail = raw.split(title, 1)[1]
        parts = [part.strip(" .") for part in tail.split(".") if part.strip(" .")]
        if parts:
            return parts[0][:160]
    return ""


def _dedupe_references(records: list[ReferenceRecord]) -> list[ReferenceRecord]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[ReferenceRecord] = []
    for record in records:
        key = (record.paper_id, record.doi.lower(), record.arxiv_id.lower(), _norm(record.raw_reference[:120]))
        if key not in seen:
            deduped.append(record)
            seen.add(key)
    return deduped


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _first(values: list[str]) -> str:
    return values[0].rstrip(".") if values else ""
