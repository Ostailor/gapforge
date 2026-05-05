"""Closest-prior-work dossier support for the novelty gate."""

from gapforge.novelty.comparator import PriorWorkComparator, PriorWorkMatch
from gapforge.novelty.dossier import NoveltyDossierBuilder
from gapforge.novelty.llm_comparator import LLMNoveltyComparator, LLMNoveltyComparisonResult
from gapforge.novelty.query_planner import NoveltyQueryPlanner

__all__ = [
    "LLMNoveltyComparator",
    "LLMNoveltyComparisonResult",
    "NoveltyDossierBuilder",
    "NoveltyQueryPlanner",
    "PriorWorkComparator",
    "PriorWorkMatch",
]
