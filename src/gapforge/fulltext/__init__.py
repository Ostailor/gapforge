"""Full-text artifact download and storage support."""

from gapforge.fulltext.artifact_store import ArtifactStore
from gapforge.fulltext.downloader import PdfDownloader, infer_pdf_url
from gapforge.fulltext.pdf_parser import FullTextParser, ParsedPage, PdfTextExtractor
from gapforge.fulltext.sectionizer import Sectionizer, create_evidence_span_from_quote

__all__ = [
    "ArtifactStore",
    "FullTextParser",
    "ParsedPage",
    "PdfDownloader",
    "PdfTextExtractor",
    "Sectionizer",
    "create_evidence_span_from_quote",
    "infer_pdf_url",
]
