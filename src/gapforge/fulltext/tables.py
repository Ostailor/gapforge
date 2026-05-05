"""Table-like text extraction from parsed paper sections."""

from __future__ import annotations

import re

from gapforge.fulltext.captions import parse_captions
from gapforge.models import PaperSection, Provenance, ResearchRunState, TableRecord
from gapforge.state import utc_now_iso


def parse_tables_from_state(state: ResearchRunState) -> list[TableRecord]:
    records: list[TableRecord] = []
    for section in state.paper_sections:
        records.extend(parse_tables(section))
    state.tables = _dedupe(records)
    return state.tables


def parse_tables(section: PaperSection) -> list[TableRecord]:
    captions = [caption for caption in parse_captions(section) if caption.caption_type == "table"]
    blocks = _table_blocks(section.text)
    records: list[TableRecord] = []
    for index, block in enumerate(blocks or ["" for _ in captions], start=1):
        caption = captions[index - 1].caption if index <= len(captions) else ""
        text = block or caption
        if not text:
            continue
        records.append(
            TableRecord(
                id=f"table-{section.paper_id}-{section.id}-{index}",
                paper_id=section.paper_id,
                section_id=section.id,
                caption=caption,
                text=text,
                page_start=section.page_start,
                page_end=section.page_end,
                locator=f"{section.paper_id}:table:{index}:p{section.page_start or '?'}",
                confidence="medium" if block else "low",
                provenance=Provenance(
                    created_by_skill="table-parser",
                    source_ids=[section.paper_id, section.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Detected table-like aligned text and nearby table captions.",
                ),
            )
        )
    return records


def _table_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _looks_table_line(line):
            current.append(line.rstrip())
        elif current:
            if len(current) >= 2:
                blocks.append(current)
            current = []
    if len(current) >= 2:
        blocks.append(current)
    return ["\n".join(block).strip() for block in blocks]


def _looks_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if "|" in stripped and stripped.count("|") >= 2:
        return True
    if "\t" in stripped:
        return True
    columns = re.split(r"\s{2,}", stripped)
    numeric_columns = sum(1 for column in columns if re.search(r"\d", column))
    return len(columns) >= 3 and numeric_columns >= 1


def _dedupe(records: list[TableRecord]) -> list[TableRecord]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for record in records:
        key = (record.paper_id, record.caption, record.text[:120])
        if key not in seen:
            result.append(record)
            seen.add(key)
    return result
