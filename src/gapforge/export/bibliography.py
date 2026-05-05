"""Best-effort BibTeX generation from GapForge paper metadata."""

from __future__ import annotations

import re

from gapforge.models import Paper


def render_bibtex(papers: list[Paper]) -> str:
    entries = [_bibtex_entry(paper) for paper in _dedupe_papers(papers)]
    return "\n\n".join(entries).rstrip() + ("\n" if entries else "")


def citation_key(paper: Paper) -> str:
    first_author = paper.authors[0].split()[-1] if paper.authors else "unknown"
    title_word = next((word for word in re.findall(r"[A-Za-z0-9]+", paper.title) if len(word) > 3), "paper")
    return _clean_key(f"{first_author}{paper.year or 'nd'}{title_word}")


def _bibtex_entry(paper: Paper) -> str:
    key = citation_key(paper)
    entry_type = "article" if paper.venue else "misc"
    fields = [
        ("title", paper.title),
        ("author", " and ".join(paper.authors)),
        ("year", str(paper.year) if paper.year else ""),
        ("venue", paper.venue),
        ("doi", paper.doi),
        ("archivePrefix", "arXiv" if paper.arxiv_id else ""),
        ("eprint", paper.arxiv_id),
        ("url", paper.url or paper.pdf_url),
    ]
    lines = [f"@{entry_type}{{{key},"]
    for name, value in fields:
        if value:
            lines.append(f"  {name} = {{{_escape_bibtex(value)}}},")
    lines.append(f"  note = {{GapForge paper id: {paper.id}}}")
    lines.append("}")
    return "\n".join(lines)


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        key = (paper.doi or paper.arxiv_id or paper.id or paper.title).lower()
        if key not in seen:
            result.append(paper)
            seen.add(key)
    return result


def _clean_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_:-]", "", value) or "gapforgePaper"


def _escape_bibtex(value: str) -> str:
    return value.replace("{", "\\{").replace("}", "\\}")
