"""BibTeX helpers for manuscript citation entries."""

from __future__ import annotations

import re

from gapforge.manuscript.models import CitationEntry
from gapforge.models import Paper


def stable_citation_key(paper: Paper, existing: set[str] | None = None) -> str:
    existing = existing if existing is not None else set()
    first_author = paper.authors[0].split()[-1] if paper.authors else "unknown"
    title_word = next((word for word in re.findall(r"[A-Za-z0-9]+", paper.title) if len(word) > 3), "paper")
    year = str(paper.year) if paper.year else "nd"
    base = _clean_key(f"{first_author}{year}{title_word}").lower()
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def bibtex_from_paper(paper: Paper, citation_key: str) -> str:
    entry_type = "article" if paper.venue else "misc"
    fields = [
        ("title", paper.title),
        ("author", " and ".join(paper.authors)),
        ("year", str(paper.year) if paper.year else ""),
        ("journal", paper.venue if entry_type == "article" else ""),
        ("venue", paper.venue if entry_type != "article" else ""),
        ("doi", paper.doi),
        ("archivePrefix", "arXiv" if paper.arxiv_id else ""),
        ("eprint", paper.arxiv_id),
        ("url", paper.url or paper.pdf_url),
    ]
    lines = [f"@{entry_type}{{{citation_key},"]
    for name, value in fields:
        if value:
            lines.append(f"  {name} = {{{_escape_bibtex(value)}}},")
    lines.append(f"  note = {{GapForge paper id: {paper.id}}}")
    lines.append("}")
    return "\n".join(lines)


def render_bibliography_bibtex(entries: list[CitationEntry]) -> str:
    return "\n\n".join(entry.bibtex for entry in entries if entry.bibtex).rstrip() + ("\n" if entries else "")


def _clean_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_:-]", "", value) or "gapforgepaper"


def _escape_bibtex(value: str) -> str:
    return value.replace("{", "\\{").replace("}", "\\}")
