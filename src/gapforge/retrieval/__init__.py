"""Hybrid retrieval index for GapForge v0.3."""

from gapforge.retrieval.documents import documents_from_program, documents_from_state
from gapforge.retrieval.embeddings import EmbeddingClient, FakeEmbeddingClient, LocalHashEmbeddingClient
from gapforge.retrieval.hybrid import HybridRetriever, build_project_index, build_run_index, search_project_index, search_run_index
from gapforge.retrieval.index_store import RetrievalIndexStore

__all__ = [
    "EmbeddingClient",
    "FakeEmbeddingClient",
    "HybridRetriever",
    "LocalHashEmbeddingClient",
    "RetrievalIndexStore",
    "build_project_index",
    "build_run_index",
    "documents_from_program",
    "documents_from_state",
    "search_project_index",
    "search_run_index",
]
