"""Lightweight reranking features for hybrid retrieval."""

from __future__ import annotations

from gapforge.models import RetrievalDocument
from gapforge.retrieval.lexical import tokenize


def rerank_score(query: str, document: RetrievalDocument) -> float:
    query_lower = query.lower()
    text_lower = f"{document.title} {document.text}".lower()
    score = 0.0
    if query_lower and query_lower in text_lower:
        score += 0.35
    query_tokens = set(tokenize(query))
    title_tokens = set(tokenize(document.title))
    if query_tokens:
        score += 0.18 * (len(query_tokens & title_tokens) / len(query_tokens))
    score += _object_type_boost(document)
    score += _section_type_boost(query_lower, str(document.metadata.get("section_type", "")))
    score += _evidence_type_boost(query_lower, str(document.metadata.get("evidence_type", "")))
    if _has_novelty_terms(query_lower) and document.object_type in {"novelty_dossier", "gap", "claim", "project_memory"}:
        score += 0.08
    if document.metadata.get("roles"):
        roles = {str(role).lower() for role in document.metadata.get("roles", [])}
        if "survey" in roles and any(term in query_lower for term in ["survey", "prior work", "related work"]):
            score += 0.08
        if "benchmark" in roles and "benchmark" in query_lower:
            score += 0.08
    if document.object_type in {"paper_section", "evidence_span"}:
        score += 0.04
    return min(1.0, score)


def _object_type_boost(document: RetrievalDocument) -> float:
    return {
        "evidence_span": 0.36,
        "paper_section": 0.12,
        "paper_note": 0.08,
        "novelty_dossier": 0.08,
        "project_memory": 0.08,
        "gap": 0.05,
        "claim": 0.04,
        "paper": 0.0,
    }.get(document.object_type, 0.0)


def _section_type_boost(query: str, section_type: str) -> float:
    if not section_type:
        return 0.0
    if section_type in {"results", "experiments"} and any(term in query for term in ["result", "metric", "benchmark", "evaluation"]):
        return 0.1
    if section_type == "method" and any(term in query for term in ["method", "algorithm", "approach"]):
        return 0.1
    if section_type in {"limitations", "discussion"} and any(term in query for term in ["limitation", "future", "unsolved", "gap"]):
        return 0.1
    if section_type == "related_work" and any(term in query for term in ["prior", "related", "closest"]):
        return 0.1
    return 0.0


def _evidence_type_boost(query: str, evidence_type: str) -> float:
    if not evidence_type:
        return 0.0
    if evidence_type == "counterevidence" and any(term in query for term in ["counter", "contradict", "prior"]):
        return 0.12
    if evidence_type == "result" and any(term in query for term in ["result", "metric", "evaluation"]):
        return 0.12
    if evidence_type == "limitation" and any(term in query for term in ["limitation", "gap", "future"]):
        return 0.12
    if evidence_type == "method" and "method" in query:
        return 0.12
    return 0.0


def _has_novelty_terms(query: str) -> bool:
    return any(term in query for term in ["novel", "prior", "closest", "duplicate", "already", "related work"])
