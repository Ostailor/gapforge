"""Coordinator for v0.3 full-text structure extraction."""

from __future__ import annotations

from gapforge.fulltext.captions import parse_captions_from_state
from gapforge.fulltext.equations import parse_equations_from_state
from gapforge.fulltext.ocr import record_ocr_recommendations
from gapforge.fulltext.references import parse_references_from_state, resolve_references
from gapforge.fulltext.tables import parse_tables_from_state
from gapforge.models import ResearchRunState


class FullTextStructureParser:
    """Extract references, tables, equations, captions, and OCR recommendations."""

    def parse_all(self, state: ResearchRunState) -> ResearchRunState:
        self.parse_references(state)
        self.parse_tables(state)
        self.parse_equations(state)
        self.parse_captions(state)
        self.record_ocr_status(state)
        return state

    def parse_references(self, state: ResearchRunState) -> ResearchRunState:
        parse_references_from_state(state)
        resolve_references(state)
        return state

    def parse_tables(self, state: ResearchRunState) -> ResearchRunState:
        parse_tables_from_state(state)
        parse_captions_from_state(state)
        return state

    def parse_equations(self, state: ResearchRunState) -> ResearchRunState:
        parse_equations_from_state(state)
        return state

    def parse_captions(self, state: ResearchRunState) -> ResearchRunState:
        parse_captions_from_state(state)
        return state

    def record_ocr_status(self, state: ResearchRunState) -> ResearchRunState:
        record_ocr_recommendations(state)
        return state
