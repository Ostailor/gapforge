"""PDF text extraction for GapForge full-text artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from gapforge.fulltext.artifact_store import safe_filename
from gapforge.fulltext.downloader import update_source_coverage
from gapforge.fulltext.sectionizer import Sectionizer
from gapforge.models import PaperArtifact, PaperSection, ResearchRunState


@dataclass(slots=True)
class ParsedPage:
    paper_id: str
    artifact_id: str
    page_number: int
    text: str
    extraction_confidence: str = "medium"
    warnings: list[str] = field(default_factory=list)


class PdfTextExtractor:
    """Extract page-level text while preserving failure details as warnings."""

    def extract(self, run_dir: Path, artifact: PaperArtifact) -> list[ParsedPage]:
        if artifact.artifact_type != "pdf":
            return [
                ParsedPage(
                    paper_id=artifact.paper_id,
                    artifact_id=artifact.id,
                    page_number=0,
                    text="",
                    extraction_confidence="low",
                    warnings=[f"Artifact {artifact.id} is not a PDF artifact."],
                )
            ]
        if artifact.status != "available":
            return [
                ParsedPage(
                    paper_id=artifact.paper_id,
                    artifact_id=artifact.id,
                    page_number=0,
                    text="",
                    extraction_confidence="low",
                    warnings=[f"Artifact {artifact.id} is not available for parsing: {artifact.status}."],
                )
            ]

        pdf_path = _artifact_path(run_dir, artifact)
        try:
            reader = PdfReader(str(pdf_path))
            if reader.is_encrypted:
                try:
                    decrypted = reader.decrypt("")
                except Exception as exc:  # pypdf surfaces varied decrypt errors by PDF version.
                    return [_failed_page(artifact, f"PDF is encrypted and could not be decrypted: {exc}")]
                if not decrypted:
                    return [_failed_page(artifact, "PDF is encrypted and could not be decrypted.")]

            pages: list[ParsedPage] = []
            for index, page in enumerate(reader.pages, start=1):
                warnings: list[str] = []
                try:
                    text = page.extract_text() or ""
                except Exception as exc:  # Keep one bad page from losing the whole artifact.
                    text = ""
                    warnings.append(f"Text extraction failed on page {index}: {exc}")
                pages.append(
                    ParsedPage(
                        paper_id=artifact.paper_id,
                        artifact_id=artifact.id,
                        page_number=index,
                        text=_clean_page_text(text),
                        extraction_confidence="medium" if text.strip() else "low",
                        warnings=warnings,
                    )
                )
            return pages or [_failed_page(artifact, "PDF contained no pages.")]
        except Exception as exc:
            return [_failed_page(artifact, f"PDF extraction failed: {exc}")]


class FullTextParser:
    """Parse available PDF artifacts into persisted paper sections."""

    def __init__(self, extractor: PdfTextExtractor | None = None, sectionizer: Sectionizer | None = None) -> None:
        self.extractor = extractor or PdfTextExtractor()
        self.sectionizer = sectionizer or Sectionizer()

    def parse_for_state(self, state: ResearchRunState, *, paper_id: str | None = None) -> list[PaperSection]:
        run_dir = Path(state.run_dir)
        artifacts = _select_pdf_artifacts(state, paper_id=paper_id)
        selected_paper_ids = {artifact.paper_id for artifact in artifacts}
        warnings: list[str] = []
        parsed_sections: list[PaperSection] = []

        for artifact in artifacts:
            pages = self.extractor.extract(run_dir, artifact)
            artifact_warnings = [warning for page in pages for warning in page.warnings]
            warnings.extend(f"{artifact.paper_id}: {warning}" for warning in artifact_warnings)
            if not any(page.text.strip() for page in pages):
                continue
            sections = self.sectionizer.sectionize(artifact.paper_id, pages)
            parsed_sections.extend(sections)
            _write_section_text_artifacts(run_dir, artifact.paper_id, sections)

        state.paper_sections = [section for section in state.paper_sections if section.paper_id not in selected_paper_ids] + parsed_sections
        update_source_coverage(state, warnings)
        return parsed_sections


def _artifact_path(run_dir: Path, artifact: PaperArtifact) -> Path:
    path = Path(artifact.local_path)
    return path if path.is_absolute() else run_dir / path


def _failed_page(artifact: PaperArtifact, warning: str) -> ParsedPage:
    return ParsedPage(
        paper_id=artifact.paper_id,
        artifact_id=artifact.id,
        page_number=0,
        text="",
        extraction_confidence="low",
        warnings=[warning],
    )


def _clean_page_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\x00", "").splitlines()]
    return "\n".join(line for line in lines if line.strip()).strip()


def _select_pdf_artifacts(state: ResearchRunState, *, paper_id: str | None) -> list[PaperArtifact]:
    artifacts = [
        artifact
        for artifact in state.paper_artifacts
        if artifact.artifact_type == "pdf" and artifact.status == "available" and artifact.local_path
    ]
    if paper_id is not None:
        if not any(paper.id == paper_id for paper in state.papers):
            raise ValueError(f"No paper found for paper id {paper_id}")
        artifacts = [artifact for artifact in artifacts if artifact.paper_id == paper_id]
    return artifacts


def _write_section_text_artifacts(run_dir: Path, paper_id: str, sections: list[PaperSection]) -> None:
    section_dir = run_dir / "artifacts" / "papers" / safe_filename(paper_id) / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    for section in sections:
        path = section_dir / f"{safe_filename(section.id)}.txt"
        path.write_text(section.text.rstrip() + "\n", encoding="utf-8")
