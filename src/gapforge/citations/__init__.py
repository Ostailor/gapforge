"""Citation graph and related-work expansion support."""

from gapforge.citations.expansion import CitationExpansionPlanner, RelatedWorkExpander
from gapforge.citations.graph import CitationGraphBuilder
from gapforge.citations.resolvers import MetadataReferenceResolver

__all__ = [
    "CitationExpansionPlanner",
    "CitationGraphBuilder",
    "MetadataReferenceResolver",
    "RelatedWorkExpander",
]
