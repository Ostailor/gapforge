"""Manual paper and artifact ingestion for GapForge runs."""

from __future__ import annotations

import difflib
import os
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.fulltext.artifact_store import ArtifactStore
from gapforge.fulltext.downloader import infer_pdf_url, update_source_coverage
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.models import Paper, PaperArtifact, Provenance, ResearchRunState
from gapforge.sources.arxiv_source import ArxivSource
from gapforge.sources.base import normalize_doi, stable_paper_id
from gapforge.sources.coverage import add_search_query_record
from gapforge.sources.crossref_source import CrossrefSource
from gapforge.sources.http_client import CachedHttpClient
from gapforge.state import utc_now_iso


class ManualIngestor:
    """Add known papers and local files to an existing research run."""

    def __init__(
        self,
        config: GapForgeConfig,
        *,
        parser: FullTextParser | None = None,
        arxiv_source: ArxivSource | None = None,
        crossref_source: CrossrefSource | None = None,
    ) -> None:
        self.config = config
        http = CachedHttpClient(config.cache_dir)
        self.parser = parser or FullTextParser()
        self.arxiv_source = arxiv_source or ArxivSource(http)
        self.crossref_source = crossref_source or CrossrefSource(http)

    def add_paper(
        self,
        state: ResearchRunState,
        *,
        title: str,
        authors: list[str] | None = None,
        year: int = 0,
        url: str = "",
        pdf_url: str = "",
        doi: str = "",
        arxiv_id: str = "",
        source: str = "manual",
        raw_metadata: dict[str, object] | None = None,
    ) -> Paper:
        paper = Paper(
            id=_manual_paper_id(title=title, doi=doi, arxiv_id=arxiv_id, url=url),
            title=title,
            authors=authors or [],
            abstract="",
            year=year,
            source=source,
            url=url,
            pdf_url=pdf_url,
            doi=normalize_doi(doi),
            arxiv_id=arxiv_id,
            raw_metadata=raw_metadata or {"manual_ingest": True},
            provenance=_manual_provenance([doi or arxiv_id or url or title], f"Manually ingested {source} paper metadata."),
        )
        merged = _merge_paper(state, paper)
        add_search_query_record(
            state,
            query=title,
            source_names=[source],
            purpose="manual",
            max_results=1,
            date_from=None,
            date_to=None,
            result_paper_ids=[merged.id],
            failure_messages=[],
        )
        update_source_coverage(state)
        return merged

    def add_arxiv(self, state: ResearchRunState, arxiv_id: str) -> Paper:
        partial = _partial_arxiv_paper(arxiv_id)
        if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
            merged = _merge_paper(state, partial)
            add_search_query_record(
                state,
                query=arxiv_id,
                source_names=["arXiv"],
                purpose="manual",
                max_results=1,
                date_from=None,
                date_to=None,
                result_paper_ids=[merged.id],
                failure_messages=[f"arXiv lookup skipped for {arxiv_id}: network disabled."],
            )
            update_source_coverage(state, [f"{arxiv_id}: network disabled; recorded partial arXiv metadata only."])
            return merged
        try:
            matches = self.arxiv_source.search(f"id:{arxiv_id}", max_results=3, sort="newest", date_from=None, date_to=None)
            exact = next((paper for paper in matches if paper.arxiv_id == arxiv_id), None)
            merged = _merge_paper(state, exact or partial)
            add_search_query_record(
                state,
                query=f"id:{arxiv_id}",
                source_names=["arXiv"],
                purpose="manual",
                max_results=3,
                date_from=None,
                date_to=None,
                result_paper_ids=[paper.id for paper in matches],
                failure_messages=[] if exact else [f"arXiv lookup did not return exact metadata for {arxiv_id}."],
            )
            if not exact:
                update_source_coverage(state, [f"{arxiv_id}: arXiv lookup did not return exact metadata; recorded partial paper."])
            else:
                update_source_coverage(state)
            return merged
        except Exception as exc:
            merged = _merge_paper(state, partial)
            add_search_query_record(
                state,
                query=arxiv_id,
                source_names=["arXiv"],
                purpose="manual",
                max_results=3,
                date_from=None,
                date_to=None,
                result_paper_ids=[merged.id],
                failure_messages=[f"arXiv lookup failed for {arxiv_id}: {exc}"],
            )
            update_source_coverage(state, [f"{arxiv_id}: arXiv lookup failed; recorded partial metadata: {exc}"])
            return merged

    def add_doi(self, state: ResearchRunState, doi: str) -> Paper:
        normalized = normalize_doi(doi)
        partial = _partial_doi_paper(normalized)
        if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
            merged = _merge_paper(state, partial)
            add_search_query_record(
                state,
                query=normalized,
                source_names=["Crossref"],
                purpose="manual",
                max_results=1,
                date_from=None,
                date_to=None,
                result_paper_ids=[merged.id],
                failure_messages=[f"CrossRef lookup skipped for {normalized}: network disabled."],
            )
            update_source_coverage(state, [f"{normalized}: network disabled; recorded partial DOI metadata only."])
            return merged
        try:
            matches = self.crossref_source.search(normalized, max_results=3, sort="newest", date_from=None, date_to=None)
            exact = next((paper for paper in matches if paper.doi == normalized), None)
            merged = _merge_paper(state, exact or partial)
            add_search_query_record(
                state,
                query=normalized,
                source_names=["Crossref"],
                purpose="manual",
                max_results=3,
                date_from=None,
                date_to=None,
                result_paper_ids=[paper.id for paper in matches],
                failure_messages=[] if exact else [f"CrossRef lookup did not return exact metadata for {normalized}."],
            )
            if not exact:
                update_source_coverage(state, [f"{normalized}: CrossRef lookup did not return exact metadata; recorded partial paper."])
            else:
                update_source_coverage(state)
            return merged
        except Exception as exc:
            merged = _merge_paper(state, partial)
            add_search_query_record(
                state,
                query=normalized,
                source_names=["Crossref"],
                purpose="manual",
                max_results=3,
                date_from=None,
                date_to=None,
                result_paper_ids=[merged.id],
                failure_messages=[f"CrossRef lookup failed for {normalized}: {exc}"],
            )
            update_source_coverage(state, [f"{normalized}: CrossRef lookup failed; recorded partial metadata: {exc}"])
            return merged

    def add_pdf(
        self,
        state: ResearchRunState,
        pdf_path: Path,
        *,
        title: str,
        authors: list[str] | None = None,
        year: int = 0,
        parse: bool = False,
    ) -> tuple[Paper, PaperArtifact]:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        data = pdf_path.read_bytes()
        if not data.lstrip().startswith(b"%PDF"):
            raise ValueError(f"Local file does not look like a PDF: {pdf_path}")
        paper = self.add_paper(
            state,
            title=title or pdf_path.stem,
            authors=authors or [],
            year=year,
            url=str(pdf_path.resolve()),
            source="manual-pdf",
            raw_metadata={"manual_ingest": True, "local_pdf": str(pdf_path.resolve())},
        )
        artifact = ArtifactStore(Path(state.run_dir)).store_bytes(
            paper,
            data,
            source_url=str(pdf_path.resolve()),
            artifact_type="pdf",
            mime_type="application/pdf",
            existing_artifacts=state.paper_artifacts,
        )
        state.paper_artifacts = _merge_artifact(state.paper_artifacts, artifact)
        if parse:
            self.parser.parse_for_state(state, paper_id=paper.id)
        else:
            update_source_coverage(state)
        return paper, artifact

    def add_url(self, state: ResearchRunState, url: str) -> Paper:
        title = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ") or url
        paper = Paper(
            id=stable_paper_id("manual-url", url),
            title=title,
            authors=[],
            abstract="",
            year=0,
            source="manual-url",
            url=url,
            raw_metadata={"manual_ingest": True, "peer_review_status": "unknown"},
            provenance=_manual_provenance([url], "Manually ingested URL metadata; peer-review status is unknown."),
        )
        merged = _merge_paper(state, paper)
        add_search_query_record(
            state,
            query=url,
            source_names=["manual-url"],
            purpose="manual",
            max_results=1,
            date_from=None,
            date_to=None,
            result_paper_ids=[merged.id],
            failure_messages=[],
        )
        update_source_coverage(state)
        return merged


def parse_authors(raw: str) -> list[str]:
    return [author.strip() for author in raw.split(";") if author.strip()]


def _manual_paper_id(*, title: str, doi: str = "", arxiv_id: str = "", url: str = "") -> str:
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return f"doi:{normalized_doi}"
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    return stable_paper_id("manual", title, url)


def _partial_arxiv_paper(arxiv_id: str) -> Paper:
    pdf_url = infer_pdf_url(Paper(id=f"arxiv:{arxiv_id}", title=f"arXiv {arxiv_id}", authors=[], abstract="", year=0, arxiv_id=arxiv_id))
    return Paper(
        id=f"arxiv:{arxiv_id}",
        title=f"arXiv {arxiv_id}",
        authors=[],
        abstract="",
        year=0,
        venue="arXiv",
        source="arXiv",
        url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=pdf_url,
        arxiv_id=arxiv_id,
        raw_metadata={"manual_ingest": True, "metadata_status": "partial"},
        provenance=_manual_provenance([arxiv_id], "Recorded partial arXiv metadata from a user-provided arXiv ID."),
    )


def _partial_doi_paper(doi: str) -> Paper:
    return Paper(
        id=f"doi:{doi}",
        title=f"DOI {doi}",
        authors=[],
        abstract="",
        year=0,
        source="DOI",
        url=f"https://doi.org/{doi}",
        doi=doi,
        raw_metadata={"manual_ingest": True, "metadata_status": "partial"},
        provenance=_manual_provenance([doi], "Recorded partial DOI metadata from a user-provided DOI."),
    )


def _merge_paper(state: ResearchRunState, incoming: Paper) -> Paper:
    existing = _find_duplicate(state.papers, incoming)
    if existing is None:
        state.papers.append(incoming)
        return incoming
    _merge_into(existing, incoming)
    return existing


def _find_duplicate(existing: list[Paper], candidate: Paper) -> Paper | None:
    for paper in existing:
        if candidate.doi and paper.doi and candidate.doi.lower() == paper.doi.lower():
            return paper
        if candidate.arxiv_id and paper.arxiv_id and candidate.arxiv_id == paper.arxiv_id:
            return paper
        if candidate.title and paper.title and _title_similarity(candidate.title, paper.title) >= 0.94:
            return paper
    return None


def _merge_into(target: Paper, source: Paper) -> None:
    target.title = _better_text(target.title, source.title)
    target.authors = target.authors or source.authors
    target.abstract = _better_text(target.abstract, source.abstract)
    target.year = target.year or source.year
    target.published_date = target.published_date or source.published_date
    target.venue = target.venue or source.venue
    target.source = target.source if target.source != "DOI" else source.source
    target.url = target.url or source.url
    target.pdf_url = target.pdf_url or source.pdf_url
    target.doi = target.doi or source.doi
    target.arxiv_id = target.arxiv_id or source.arxiv_id
    target.openreview_id = target.openreview_id or source.openreview_id
    target.semantic_scholar_id = target.semantic_scholar_id or source.semantic_scholar_id
    target.citation_count = max(target.citation_count, source.citation_count)
    target.keywords = sorted(set(target.keywords + source.keywords))
    target.raw_metadata.setdefault("merged_from", [])
    target.raw_metadata["merged_from"].append({"source": source.source, "id": source.id, "raw_metadata": source.raw_metadata})
    target.provenance.source_ids = sorted(set(target.provenance.source_ids + source.provenance.source_ids))


def _merge_artifact(existing: list[PaperArtifact], incoming: PaperArtifact) -> list[PaperArtifact]:
    by_id = {artifact.id: artifact for artifact in existing}
    for artifact in existing:
        if artifact.paper_id == incoming.paper_id and artifact.sha256 and artifact.sha256 == incoming.sha256:
            by_id[artifact.id] = artifact
            return list(by_id.values())
    by_id[incoming.id] = incoming
    return list(by_id.values())


def _better_text(current: str, incoming: str) -> str:
    if not current:
        return incoming
    if incoming and current.lower().startswith(("doi ", "arxiv ")) and not incoming.lower().startswith(("doi ", "arxiv ")):
        return incoming
    return incoming if len(incoming) > len(current) * 1.5 else current


def _title_similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, _norm_title(left), _norm_title(right)).ratio()


def _norm_title(title: str) -> str:
    return " ".join(title.lower().split())


def _manual_provenance(source_ids: list[str], reasoning_summary: str) -> Provenance:
    return Provenance(
        created_by_skill="manual-ingest",
        source_ids=[source_id for source_id in source_ids if source_id],
        timestamp=utc_now_iso(),
        reasoning_summary=reasoning_summary,
    )
