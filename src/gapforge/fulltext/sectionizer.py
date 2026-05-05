"""Deterministic section parsing for extracted paper text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from gapforge.fulltext.artifact_store import safe_filename
from gapforge.fulltext.section_types import classify_section_title, normalize_heading
from gapforge.models import EvidenceSpan, PaperSection, Provenance
from gapforge.state import utc_now_iso

if TYPE_CHECKING:
    from gapforge.fulltext.pdf_parser import ParsedPage

_HEADING_LINE = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])\.?\s+)?"
    r"(Abstract|Introduction|Background|Related Work|Prior Work|Literature Review|Method|Methods|Methodology|Approach|"
    r"Experiments|Experimental Setup|Evaluation|Results|Discussion|Limitations|Threats to Validity|Conclusion|Conclusions|"
    r"Future Work|Appendix|Supplementary Material)\s*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _LineRecord:
    text: str
    page_number: int
    char_start: int
    char_end: int
    title: str = ""


class Sectionizer:
    """Split parsed pages into PaperSection records using common academic headings."""

    def sectionize(self, paper_id: str, pages: list[ParsedPage]) -> list[PaperSection]:
        text_pages = [page for page in pages if page.text.strip()]
        if not text_pages:
            return []

        combined_text, line_records = _line_records(text_pages)
        headings = _find_headings(line_records)
        if not headings:
            return [_fallback_section(paper_id, combined_text, text_pages)]

        sections: list[PaperSection] = []
        for index, heading in enumerate(headings):
            next_start = headings[index + 1].char_start if index + 1 < len(headings) else len(combined_text)
            content_start = heading.char_end
            content = combined_text[content_start:next_start].strip()
            if not content:
                continue
            title = heading.title
            section_id = _section_id(paper_id, index + 1, title)
            pages_for_section = _pages_for_range(line_records, content_start, next_start)
            now = utc_now_iso()
            sections.append(
                PaperSection(
                    id=section_id,
                    paper_id=paper_id,
                    title=title,
                    normalized_title=normalize_heading(title),
                    section_type=classify_section_title(title),
                    text=content,
                    page_start=min(pages_for_section) if pages_for_section else heading.page_number,
                    page_end=max(pages_for_section) if pages_for_section else heading.page_number,
                    char_start=content_start,
                    char_end=next_start,
                    confidence="medium",
                    provenance=Provenance(
                        created_by_skill="sectionizer",
                        source_ids=[paper_id],
                        timestamp=now,
                        reasoning_summary="Detected a common academic section heading in extracted page text.",
                    ),
                )
            )
        return sections or [_fallback_section(paper_id, combined_text, text_pages)]


def create_evidence_span_from_quote(
    section: PaperSection,
    quote: str,
    *,
    evidence_type: str = "claim",
    confidence: str = "medium",
) -> EvidenceSpan:
    quote = quote.strip()
    start = section.text.find(quote) if quote else -1
    absolute_start = section.char_start + start if start >= 0 else section.char_start
    absolute_end = absolute_start + len(quote) if start >= 0 else section.char_start
    page = section.page_start
    locator = f"{section.paper_id}:{section.normalized_title or safe_filename(section.title)}:p{page or 'unknown'}"
    now = utc_now_iso()
    digest = sha256(f"{section.id}:{quote}:{absolute_start}".encode()).hexdigest()[:10]
    return EvidenceSpan(
        id=f"{safe_filename(section.id)}-span-{digest}",
        paper_id=section.paper_id,
        section_id=section.id,
        quote=quote,
        page_start=section.page_start,
        page_end=section.page_end,
        char_start=absolute_start,
        char_end=absolute_end,
        locator=locator,
        evidence_type=evidence_type,
        confidence=confidence if start >= 0 else "low",
        provenance=Provenance(
            created_by_skill="evidence-span-helper",
            source_ids=[section.paper_id, section.id],
            timestamp=now,
            reasoning_summary="Located the requested quote inside a parsed paper section when possible.",
        ),
    )


def _line_records(pages: list[ParsedPage]) -> tuple[str, list[_LineRecord]]:
    parts: list[str] = []
    records: list[_LineRecord] = []
    char_offset = 0
    for page in pages:
        for line in page.text.splitlines():
            text = line.strip()
            if not text:
                continue
            start = char_offset
            parts.append(text)
            char_offset += len(text)
            records.append(_LineRecord(text=text, page_number=page.page_number, char_start=start, char_end=char_offset))
            parts.append("\n")
            char_offset += 1
    return "".join(parts).strip(), records


def _find_headings(line_records: list[_LineRecord]) -> list[_LineRecord]:
    headings: list[_LineRecord] = []
    for record in line_records:
        text = record.text.strip()
        if _HEADING_LINE.match(text):
            headings.append(
                _LineRecord(
                    text=record.text,
                    page_number=record.page_number,
                    char_start=record.char_start,
                    char_end=record.char_end,
                    title=_strip_heading_number(text),
                )
            )
    return headings


def _strip_heading_number(text: str) -> str:
    return re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])\.?\s+", "", text.strip(), flags=re.IGNORECASE)


def _pages_for_range(line_records: list[_LineRecord], start: int, end: int) -> list[int]:
    return [record.page_number for record in line_records if record.char_start >= start and record.char_start < end]


def _fallback_section(paper_id: str, combined_text: str, pages: list[ParsedPage]) -> PaperSection:
    now = utc_now_iso()
    return PaperSection(
        id=f"{safe_filename(paper_id)}-section-full-text",
        paper_id=paper_id,
        title="Full Text",
        normalized_title="full text",
        section_type="unknown",
        text=combined_text,
        page_start=min(page.page_number for page in pages),
        page_end=max(page.page_number for page in pages),
        char_start=0,
        char_end=len(combined_text),
        confidence="low",
        provenance=Provenance(
            created_by_skill="sectionizer",
            source_ids=[paper_id],
            timestamp=now,
            reasoning_summary="No common section headings were detected; stored extracted text as one fallback section.",
        ),
    )


def _section_id(paper_id: str, index: int, title: str) -> str:
    return f"{safe_filename(paper_id)}-section-{index:02d}-{safe_filename(normalize_heading(title))}"
