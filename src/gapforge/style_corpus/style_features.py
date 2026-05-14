"""Style feature models and rendering for TeX source corpora."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance

LICENSE_STATUSES = {"allowed", "unknown", "restricted", "rejected"}


@dataclass(slots=True)
class StyleCorpusPaper:
    id: str
    title: str
    venue: str
    year: int
    source_url: str
    local_source_path: str
    license_status: str
    section_titles: list[str] = field(default_factory=list)
    macro_summary: dict[str, int] = field(default_factory=dict)
    environment_summary: dict[str, int] = field(default_factory=dict)
    citation_density: float = 0.0
    figure_table_counts: dict[str, int] = field(default_factory=dict)
    abstract_length: int = 0
    contribution_statement_patterns: list[str] = field(default_factory=list)
    limitations_presence: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="style-corpus"))


def normalize_license_status(value: str) -> str:
    status = (value or "unknown").strip().lower().replace("-", "_")
    return status if status in LICENSE_STATUSES else "unknown"


def render_style_corpus_report(papers: list[StyleCorpusPaper], ingest_sections: list[str]) -> str:
    lines = [
        "# Style Corpus Report",
        "",
        "## Safety Boundary",
        "",
        (
            "This corpus stores structural and stylistic features only. It does not store paper prose, and generated manuscripts "
            "may use structure or rhetoric patterns but must not copy source text."
        ),
        "",
        f"- Papers with extracted features: {len(papers)}",
        "",
        "## Papers",
        "",
    ]
    if not papers:
        lines.append("No style corpus papers are ingested.")
    for paper in papers:
        lines.extend(
            [
                f"### `{paper.id}`",
                "",
                f"- Title: {paper.title or 'unknown'}",
                f"- Venue profile: `{paper.venue}`",
                f"- Year: {paper.year or 'unknown'}",
                f"- License status: `{paper.license_status}`",
                f"- Source path: {paper.local_source_path}",
                f"- Sections: {_fmt(paper.section_titles)}",
                f"- Citation density: {paper.citation_density:.4f}",
                f"- Abstract length: {paper.abstract_length} words",
                f"- Figure/table counts: {paper.figure_table_counts}",
                f"- Contribution patterns: {_fmt(paper.contribution_statement_patterns)}",
                f"- Limitations present: {paper.limitations_presence}",
                "",
            ]
        )
    if ingest_sections:
        lines.extend(["## Ingest Records", "", *ingest_sections])
    return "\n".join(lines).rstrip() + "\n"


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
