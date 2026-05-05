"""Equation-like line extraction from parsed paper sections."""

from __future__ import annotations

import re

from gapforge.models import EquationRecord, PaperSection, Provenance, ResearchRunState
from gapforge.state import utc_now_iso

EQUATION_SYMBOLS = {"=", "≤", "≥", "\\sum", "\\frac", "\\arg", "\\min", "\\max", "∑", "∫"}


def parse_equations_from_state(state: ResearchRunState) -> list[EquationRecord]:
    records: list[EquationRecord] = []
    for section in state.paper_sections:
        records.extend(parse_equations(section))
    state.equations = _dedupe(records)
    return state.equations


def parse_equations(section: PaperSection) -> list[EquationRecord]:
    lines = section.text.splitlines()
    records = []
    for index, line in enumerate(lines):
        text = line.strip()
        if not _looks_equation(text):
            continue
        surrounding = " ".join(item.strip() for item in lines[max(0, index - 1) : min(len(lines), index + 2)] if item.strip())
        records.append(
            EquationRecord(
                id=f"eq-{section.paper_id}-{section.id}-{index + 1}",
                paper_id=section.paper_id,
                section_id=section.id,
                text=text,
                page=section.page_start,
                locator=f"{section.paper_id}:eq:{index + 1}:p{section.page_start or '?'}",
                surrounding_text=surrounding[:700],
                confidence="medium",
                provenance=Provenance(
                    created_by_skill="equation-parser",
                    source_ids=[section.paper_id, section.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Detected an equation-like line from mathematical symbols and compact syntax.",
                ),
            )
        )
    return records


def _looks_equation(text: str) -> bool:
    if len(text) < 3 or len(text) > 240:
        return False
    if text.lower().startswith(("table ", "figure ", "fig. ")):
        return False
    symbol_hit = any(symbol in text for symbol in EQUATION_SYMBOLS)
    variable_pattern = bool(re.search(r"\b[a-zA-Z]\s*[=<>]\s*[-+a-zA-Z0-9({\\]", text))
    math_density = len(re.findall(r"[=+\-*/^_{}()]", text)) >= 3
    return symbol_hit and (variable_pattern or math_density)


def _dedupe(records: list[EquationRecord]) -> list[EquationRecord]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for record in records:
        key = (record.paper_id, record.section_id, record.text)
        if key not in seen:
            result.append(record)
            seen.add(key)
    return result
