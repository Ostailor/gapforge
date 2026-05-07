"""Bibliography management for manuscript projects."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.bibtex import bibtex_from_paper, render_bibliography_bibtex, stable_citation_key
from gapforge.manuscript.citations import (
    citation_uses_from_sections,
    known_papers_for_manuscript,
    required_paper_ids,
    suspicious_citation_string,
    unresolved_citation_keys,
)
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import BibliographyRecord, CitationEntry
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.state import utc_now_iso


class ManuscriptBibliographyManager:
    """Build auditable bibliography records from known paper metadata."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)

    def build(self, manuscript_id: str) -> BibliographyRecord:
        state = self.manuscript_manager.load_state(manuscript_id)
        known_papers = known_papers_for_manuscript(self.config, state)
        requested_ids = required_paper_ids(state)
        unknown_ids = [paper_id for paper_id in requested_ids if paper_id not in known_papers]
        if unknown_ids:
            raise ValueError(f"Manuscript citations reference unknown paper IDs: {', '.join(unknown_ids)}")
        papers = [known_papers[paper_id] for paper_id in requested_ids]
        entries, duplicates = _entries_from_papers(manuscript_id, papers)
        unresolved = unresolved_citation_keys(state, entries)
        if unresolved:
            fake_like = [key for key in unresolved if suspicious_citation_string(key)]
            detail = f" Unresolved fake-looking citation strings: {', '.join(fake_like)}." if fake_like else ""
            raise ValueError(f"Unresolved citation keys: {', '.join(unresolved)}.{detail}")
        missing = {entry.paper_id: _missing_metadata(entry) for entry in entries}
        missing = {paper_id: fields for paper_id, fields in missing.items() if fields}
        now = utc_now_iso()
        bibliography = BibliographyRecord(
            id=f"bibliography-{manuscript_id}",
            manuscript_id=manuscript_id,
            entries=entries,
            missing_metadata=missing,
            duplicate_entries=duplicates,
            generated_at=now,
            provenance=Provenance(
                created_by_skill="manuscript-bibliography",
                source_ids=[manuscript_id, *requested_ids],
                timestamp=now,
                reasoning_summary="Generated bibliography from known GapForge paper records with deduplication and metadata warnings.",
            ),
        )
        state.bibliography_id = bibliography.id
        state.citation_uses = citation_uses_from_sections(
            manuscript_id=manuscript_id,
            sections=state.sections,
            entries_by_paper_id={entry.paper_id: entry for entry in entries},
        )
        self.manuscript_manager._save_state(state)
        self._write_bibliography(manuscript_id, bibliography)
        return bibliography

    def load(self, manuscript_id: str) -> BibliographyRecord:
        path = self._bibliography_path(manuscript_id)
        if not path.exists():
            raise FileNotFoundError(f"No bibliography has been built for {manuscript_id}")
        return from_dict(BibliographyRecord, json.loads(path.read_text(encoding="utf-8")))

    def export(self, manuscript_id: str, *, export_format: str = "bibtex") -> str:
        if export_format != "bibtex":
            raise ValueError("Only bibtex bibliography export is supported.")
        bibliography = self.load(manuscript_id)
        return render_bibliography_bibtex(bibliography.entries)

    def citation_list_json(self, manuscript_id: str) -> str:
        bibliography = self.load(manuscript_id)
        return json.dumps(to_plain(bibliography.entries), indent=2) + "\n"

    def check_markdown(self, manuscript_id: str) -> str:
        bibliography = self.load(manuscript_id)
        state = self.manuscript_manager.load_state(manuscript_id)
        unresolved = unresolved_citation_keys(state, bibliography.entries)
        blockers: list[str] = []
        if unresolved:
            blockers.append(f"Unresolved citation keys: {', '.join(unresolved)}")
        if state.manuscript.status == "submission_ready" and (unresolved or bibliography.missing_metadata):
            blockers.append("Manuscript is submission_ready with unresolved or incomplete citation metadata.")
        lines = [
            f"# Citation Check `{manuscript_id}`",
            "",
            f"- Entries: {len(bibliography.entries)}",
            f"- Missing metadata records: {len(bibliography.missing_metadata)}",
            f"- Duplicate records deduped: {len(bibliography.duplicate_entries)}",
            "",
        ]
        if blockers:
            lines.append("Citation check failed.")
            lines.extend(f"- {blocker}" for blocker in blockers)
        else:
            lines.append("Citation check passed.")
        if bibliography.missing_metadata:
            lines.extend(["", "## Metadata Warnings", ""])
            for paper_id, fields in bibliography.missing_metadata.items():
                lines.append(f"- `{paper_id}` missing: {', '.join(fields)}")
        return "\n".join(lines).rstrip() + "\n"

    def _write_bibliography(self, manuscript_id: str, bibliography: BibliographyRecord) -> None:
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        bibliography_dir = root / "bibliography"
        bibliography_dir.mkdir(parents=True, exist_ok=True)
        self._bibliography_path(manuscript_id).write_text(json.dumps(to_plain(bibliography), indent=2) + "\n", encoding="utf-8")
        (bibliography_dir / "references.bib").write_text(render_bibliography_bibtex(bibliography.entries), encoding="utf-8")
        (bibliography_dir / "citation_check.md").write_text(self.check_markdown(manuscript_id), encoding="utf-8")

    def _bibliography_path(self, manuscript_id: str) -> Path:
        return self.manuscript_manager.manuscript_root(manuscript_id) / "bibliography" / "bibliography.json"


def _entries_from_papers(manuscript_id: str, papers: list[Paper]) -> tuple[list[CitationEntry], dict[str, str]]:
    entries: list[CitationEntry] = []
    duplicates: dict[str, str] = {}
    seen_identity: dict[str, str] = {}
    keys: set[str] = set()
    now = utc_now_iso()
    for paper in papers:
        identity = _dedupe_identity(paper)
        if identity in seen_identity:
            duplicates[paper.id] = seen_identity[identity]
            continue
        citation_key = stable_citation_key(paper, keys)
        keys.add(citation_key)
        entry = CitationEntry(
            id=f"citation-{citation_key}",
            paper_id=paper.id,
            citation_key=citation_key,
            title=paper.title,
            authors=list(paper.authors),
            year=paper.year,
            venue=paper.venue,
            doi=paper.doi,
            arxiv_id=paper.arxiv_id,
            url=paper.url or paper.pdf_url,
            metadata_completeness=_metadata_completeness(paper),
            provenance=Provenance(
                created_by_skill="manuscript-citation",
                source_ids=[manuscript_id, paper.id],
                timestamp=now,
                reasoning_summary="Created citation entry from known GapForge paper metadata.",
            ),
        )
        entry.bibtex = bibtex_from_paper(paper, citation_key)
        entries.append(entry)
        seen_identity[identity] = paper.id
    return entries, duplicates


def _dedupe_identity(paper: Paper) -> str:
    if paper.doi:
        return f"doi:{paper.doi.strip().lower()}"
    if paper.arxiv_id:
        return f"arxiv:{paper.arxiv_id.strip().lower()}"
    return f"title:{' '.join(paper.title.lower().split())}"


def _metadata_completeness(paper: Paper) -> dict[str, str]:
    return {
        "title": "present" if paper.title else "missing",
        "authors": "present" if paper.authors else "missing",
        "year": "present" if paper.year else "missing",
        "venue": "present" if paper.venue else "missing",
        "doi_or_arxiv": "present" if paper.doi or paper.arxiv_id else "missing",
        "url": "present" if paper.url or paper.pdf_url else "missing",
    }


def _missing_metadata(entry: CitationEntry) -> list[str]:
    return [field for field in ["authors", "venue", "doi_or_arxiv"] if entry.metadata_completeness.get(field) == "missing"]
