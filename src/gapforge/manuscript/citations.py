"""Citation validation and known-paper lookup for manuscript projects."""

from __future__ import annotations

import re

from gapforge.config import GapForgeConfig
from gapforge.manuscript.models import CitationEntry, CitationUse, ManuscriptSection, ManuscriptState
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso


def known_papers_for_manuscript(config: GapForgeConfig, state: ManuscriptState) -> dict[str, Paper]:
    project_manager = ProjectMemoryManager(config)
    run_manager = ResearchStateManager(config)
    program = project_manager.load_project(state.manuscript.project_id)
    papers: dict[str, Paper] = {}
    for run_id in program.run_ids or program.project.run_ids:
        try:
            run_state = run_manager.load_run(run_id)
        except FileNotFoundError:
            continue
        for paper in run_state.papers:
            papers.setdefault(paper.id, paper)
    for corpus_record in program.corpus_papers:
        papers.setdefault(
            corpus_record.paper_id,
            Paper(
                id=corpus_record.paper_id,
                title=corpus_record.canonical_title,
                authors=[],
                abstract="",
                year=0,
                doi=corpus_record.canonical_doi,
                arxiv_id=corpus_record.canonical_arxiv_id,
            ),
        )
    return papers


def required_paper_ids(state: ManuscriptState) -> list[str]:
    paper_ids: list[str] = []
    for section in state.sections:
        paper_ids.extend(section.source_paper_ids)
    for claim_use in state.claim_uses:
        paper_ids.extend(_paper_ids_from_locators(claim_use.evidence_locators))
    return _unique(paper_ids)


def citation_uses_from_sections(
    *,
    manuscript_id: str,
    sections: list[ManuscriptSection],
    entries_by_paper_id: dict[str, CitationEntry],
) -> list[CitationUse]:
    now = utc_now_iso()
    uses: list[CitationUse] = []
    seen: set[tuple[str, str]] = set()
    for section in sections:
        for paper_id in section.source_paper_ids:
            entry = entries_by_paper_id.get(paper_id)
            if entry is None:
                continue
            key = (section.id, entry.paper_id)
            if key in seen:
                continue
            seen.add(key)
            uses.append(
                CitationUse(
                    id=f"citation-use-{section.id}-{entry.citation_key}",
                    manuscript_id=manuscript_id,
                    section_id=section.id,
                    paper_id=entry.paper_id,
                    citation_key=entry.citation_key,
                    use_context=section.section_type,
                    required=True,
                    provenance=Provenance(
                        created_by_skill="manuscript-citation-use",
                        source_ids=[manuscript_id, section.id, entry.paper_id],
                        timestamp=now,
                        reasoning_summary="Derived a manuscript citation use from section-linked known paper IDs.",
                    ),
                )
            )
    return uses


def unresolved_citation_keys(state: ManuscriptState, entries: list[CitationEntry]) -> list[str]:
    known_keys = {entry.citation_key for entry in entries}
    unresolved: list[str] = []
    for claim_use in state.claim_uses:
        for citation_key in claim_use.citation_keys:
            if citation_key not in known_keys:
                unresolved.append(citation_key)
    return _unique(unresolved)


def suspicious_citation_string(value: str) -> bool:
    return bool(re.search(r"\s", value.strip())) or bool(re.search(r"\b(19|20)\d{2}\b", value))


def _paper_ids_from_locators(locators: list[str]) -> list[str]:
    paper_ids: list[str] = []
    for locator in locators:
        if ":" in locator:
            paper_ids.append(locator.split(":", 1)[0])
    return paper_ids


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
