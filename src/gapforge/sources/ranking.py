"""Ranking, deduplication, and source diversity utilities."""

from __future__ import annotations

import difflib
import math
import re
from collections import Counter

from gapforge.models import Paper

AUTHORITATIVE_VENUE_TERMS = {
    "nature",
    "science",
    "neurips",
    "icml",
    "iclr",
    "acl",
    "emnlp",
    "cvpr",
    "iccv",
    "eccv",
    "kdd",
    "www",
    "sigir",
    "chi",
    "usenix",
    "sigmod",
    "vldb",
    "jmlr",
    "pnas",
}


def rank_papers(query: str, papers: list[Paper], *, newest_first: bool = True, per_source_limit: int | None = None) -> list[Paper]:
    deduped = deduplicate_papers(papers)
    ranked = sorted(deduped, key=lambda paper: _score(query, paper, newest_first), reverse=True)
    if per_source_limit is not None:
        ranked = apply_source_diversity(ranked, per_source_limit)
    return ranked


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    merged: list[Paper] = []
    for paper in papers:
        existing = _find_duplicate(merged, paper)
        if existing is None:
            merged.append(paper)
        else:
            _merge_into(existing, paper)
    return merged


def apply_source_diversity(papers: list[Paper], per_source_limit: int) -> list[Paper]:
    counts: Counter[str] = Counter()
    selected: list[Paper] = []
    deferred: list[Paper] = []
    for paper in papers:
        if counts[paper.source] < per_source_limit:
            selected.append(paper)
            counts[paper.source] += 1
        else:
            deferred.append(paper)
    return selected + deferred


def _score(query: str, paper: Paper, newest_first: bool) -> float:
    title = paper.title.lower()
    query_norm = query.lower()
    exact_boost = 5.0 if query_norm in title else 0.0
    title_similarity = difflib.SequenceMatcher(None, _norm(query_norm), _norm(title)).ratio() * 2.0
    venue_boost = 1.5 if any(term in paper.venue.lower() for term in AUTHORITATIVE_VENUE_TERMS) else 0.0
    citation_boost = min(math.log1p(max(paper.citation_count, 0)), 8.0) / 2.0
    year_score = (paper.year or 0) / 1000.0
    if not newest_first:
        year_score = -year_score
    return exact_boost + title_similarity + venue_boost + citation_boost + year_score


def _find_duplicate(existing: list[Paper], candidate: Paper) -> Paper | None:
    for paper in existing:
        if candidate.doi and paper.doi and candidate.doi.lower() == paper.doi.lower():
            return paper
        if candidate.arxiv_id and paper.arxiv_id and candidate.arxiv_id == paper.arxiv_id:
            return paper
        if _title_similarity(candidate.title, paper.title) >= 0.94:
            return paper
    return None


def _merge_into(target: Paper, source: Paper) -> None:
    target.authors = target.authors or source.authors
    target.abstract = _longer(target.abstract, source.abstract)
    target.year = target.year or source.year
    target.published_date = target.published_date or source.published_date
    target.venue = target.venue or source.venue
    target.url = target.url or source.url
    target.pdf_url = target.pdf_url or source.pdf_url
    target.doi = target.doi or source.doi
    target.arxiv_id = target.arxiv_id or source.arxiv_id
    target.openreview_id = target.openreview_id or source.openreview_id
    target.semantic_scholar_id = target.semantic_scholar_id or source.semantic_scholar_id
    target.citation_count = max(target.citation_count, source.citation_count)
    target.keywords = sorted(set(target.keywords + source.keywords))
    target.raw_metadata.setdefault("merged_from", [])
    target.raw_metadata["merged_from"].append({"source": source.source, "id": source.id})
    target.provenance.source_ids = sorted(set(target.provenance.source_ids + source.provenance.source_ids))


def _longer(left: str, right: str) -> str:
    return right if len(right) > len(left) else left


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, _norm(left), _norm(right)).ratio()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
