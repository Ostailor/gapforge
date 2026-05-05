"""Closest-prior-work dossier support for the novelty gate."""

from gapforge.novelty.comparator import PriorWorkComparator, PriorWorkMatch
from gapforge.novelty.dossier import NoveltyDossierBuilder
from gapforge.novelty.query_planner import NoveltyQueryPlanner

__all__ = ["NoveltyDossierBuilder", "NoveltyQueryPlanner", "PriorWorkComparator", "PriorWorkMatch"]
