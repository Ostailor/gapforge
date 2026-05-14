"""Safe TeX/source style corpus ingestion."""

from gapforge.style_corpus.analyzer import (
    StyleRecommendation,
    VenueStyleAnalyzer,
    VenueStyleProfile,
    render_style_recommendations,
    render_venue_style_profile,
)
from gapforge.style_corpus.ingest import StyleCorpusIngestRecord, StyleCorpusManager
from gapforge.style_corpus.license_check import LicenseCheckResult, check_tex_license
from gapforge.style_corpus.style_features import StyleCorpusPaper, render_style_corpus_report
from gapforge.style_corpus.tex_parser import parse_tex_file

__all__ = [
    "LicenseCheckResult",
    "StyleRecommendation",
    "StyleCorpusIngestRecord",
    "StyleCorpusManager",
    "StyleCorpusPaper",
    "VenueStyleAnalyzer",
    "VenueStyleProfile",
    "check_tex_license",
    "parse_tex_file",
    "render_style_corpus_report",
    "render_style_recommendations",
    "render_venue_style_profile",
]
