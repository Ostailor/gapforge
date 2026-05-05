"""Research source connectors."""

from gapforge.sources.arxiv_source import ArxivSource
from gapforge.sources.crossref_source import CrossrefSource
from gapforge.sources.dblp_source import DblpSource
from gapforge.sources.openreview_source import OpenReviewSource
from gapforge.sources.semantic_scholar_source import SemanticScholarSource
from gapforge.sources.web_source import WebSource

__all__ = [
    "ArxivSource",
    "CrossrefSource",
    "DblpSource",
    "OpenReviewSource",
    "SemanticScholarSource",
    "WebSource",
]
