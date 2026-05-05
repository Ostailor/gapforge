"""Caption extraction from parsed paper sections."""

from __future__ import annotations

import re

from gapforge.models import CaptionRecord, PaperSection, Provenance, ResearchRunState
from gapforge.state import utc_now_iso

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.|Table|Algorithm)\s+([A-Z]?\d+(?:\.\d+)?)[\.:]\s+(.+)$", re.IGNORECASE)


def parse_captions_from_state(state: ResearchRunState) -> list[CaptionRecord]:
    records: list[CaptionRecord] = []
    for section in state.paper_sections:
        records.extend(parse_captions(section))
    state.captions = _dedupe(records)
    return state.captions


def parse_captions(section: PaperSection) -> list[CaptionRecord]:
    records = []
    for index, line in enumerate(section.text.splitlines(), start=1):
        match = CAPTION_RE.match(line.strip())
        if not match:
            continue
        caption_type = _caption_type(match.group(1))
        caption = match.group(3).strip()
        records.append(
            CaptionRecord(
                id=f"caption-{section.paper_id}-{section.id}-{index}",
                paper_id=section.paper_id,
                section_id=section.id,
                caption_type=caption_type,
                caption=caption,
                page=section.page_start,
                locator=f"{section.paper_id}:{caption_type}:{match.group(2)}:p{section.page_start or '?'}",
                confidence="high",
                provenance=Provenance(
                    created_by_skill="caption-parser",
                    source_ids=[section.paper_id, section.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Detected a figure, table, or algorithm caption from a line prefix.",
                ),
            )
        )
    return records


def _caption_type(label: str) -> str:
    lowered = label.lower()
    if lowered.startswith("fig"):
        return "figure"
    if lowered.startswith("table"):
        return "table"
    if lowered.startswith("algorithm"):
        return "algorithm"
    return "unknown"


def _dedupe(records: list[CaptionRecord]) -> list[CaptionRecord]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for record in records:
        key = (record.paper_id, record.caption_type, record.caption)
        if key not in seen:
            result.append(record)
            seen.add(key)
    return result
