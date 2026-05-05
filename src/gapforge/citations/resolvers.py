"""Reference resolution helpers for citation metadata."""

from __future__ import annotations

import difflib
import re
from typing import Any

from gapforge.models import Paper
from gapforge.sources.base import normalize_doi


class MetadataReferenceResolver:
    """Resolve reference-like metadata dictionaries to papers already in state."""

    def __init__(self, papers: list[Paper]) -> None:
        self.papers = papers

    def resolve(self, reference: dict[str, Any]) -> Paper | None:
        semantic_id = _clean(reference.get("paperId") or reference.get("paper_id") or reference.get("semantic_scholar_id"))
        doi = normalize_doi(_external_id(reference, "DOI") or reference.get("doi", ""))
        arxiv_id = _clean(_external_id(reference, "ArXiv") or reference.get("arxivId") or reference.get("arxiv_id"))
        title = _clean(reference.get("title", ""))
        for paper in self.papers:
            if semantic_id and paper.semantic_scholar_id == semantic_id:
                return paper
            if doi and paper.doi and paper.doi.lower() == doi.lower():
                return paper
            if arxiv_id and paper.arxiv_id and paper.arxiv_id == arxiv_id:
                return paper
        if title:
            for paper in self.papers:
                if _norm(title) == _norm(paper.title) or _title_similarity(title, paper.title) >= 0.98:
                    return paper
        return None


def reference_label(reference: dict[str, Any]) -> str:
    title = _clean(reference.get("title", ""))
    semantic_id = _clean(reference.get("paperId") or reference.get("paper_id"))
    doi = normalize_doi(_external_id(reference, "DOI") or reference.get("doi", ""))
    arxiv_id = _clean(_external_id(reference, "ArXiv") or reference.get("arxivId") or reference.get("arxiv_id"))
    parts = [
        part
        for part in [
            title,
            f"s2:{semantic_id}" if semantic_id else "",
            f"doi:{doi}" if doi else "",
            f"arxiv:{arxiv_id}" if arxiv_id else "",
        ]
        if part
    ]
    return " | ".join(parts) or str(reference)


def _external_id(reference: dict[str, Any], key: str) -> str:
    external = reference.get("externalIds") or reference.get("external_ids") or {}
    return _clean(external.get(key, "")) if isinstance(external, dict) else ""


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, _norm(left), _norm(right)).ratio()


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
