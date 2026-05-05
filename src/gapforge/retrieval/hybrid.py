"""Hybrid lexical/semantic retrieval over GapForge artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import IndexManifest, Provenance, ResearchProgramState, ResearchRunState, RetrievalDocument, RetrievalResult
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval.documents import documents_from_program, documents_from_state
from gapforge.retrieval.embeddings import EmbeddingClient, LocalHashEmbeddingClient, cosine
from gapforge.retrieval.index_store import RetrievalIndexStore
from gapforge.retrieval.lexical import LexicalRetriever
from gapforge.retrieval.rerank import rerank_score
from gapforge.state import ResearchStateManager, utc_now_iso


class HybridRetriever:
    """Combines deterministic BM25-like scoring with local semantic vectors."""

    def __init__(
        self,
        documents: list[RetrievalDocument],
        *,
        embeddings: list[list[float]] | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self.documents = documents
        self.embedding_client = embedding_client or LocalHashEmbeddingClient()
        self.embeddings = embeddings if embeddings is not None else self.embedding_client.embed(_embedding_texts(documents))
        self.lexical = LexicalRetriever(documents)

    def search(self, query: str, *, top_k: int = 10, semantic_weight: float = 0.5) -> list[RetrievalResult]:
        lexical_scores = self.lexical.score(query)
        query_embedding = self.embedding_client.embed([query])[0]
        semantic_scores = {
            document.id: cosine(query_embedding, embedding) for document, embedding in zip(self.documents, self.embeddings, strict=False)
        }
        semantic_scores = _normalize(semantic_scores)
        results: list[RetrievalResult] = []
        for document in self.documents:
            lexical_score = lexical_scores.get(document.id, 0.0)
            semantic_score = semantic_scores.get(document.id, 0.0)
            rerank = rerank_score(query, document)
            combined = (1 - semantic_weight) * lexical_score + semantic_weight * semantic_score + 0.18 * rerank
            if combined <= 0:
                continue
            results.append(
                RetrievalResult(
                    document_id=document.id,
                    object_type=document.object_type,
                    object_id=document.object_id,
                    paper_id=document.paper_id,
                    score=round(min(1.0, combined), 6),
                    lexical_score=round(lexical_score, 6),
                    semantic_score=round(semantic_score, 6),
                    rerank_score=round(rerank, 6),
                    text_snippet=_snippet(document.text, query),
                    locator=document.locator,
                    metadata={
                        **document.metadata,
                        "title": document.title,
                        "run_id": document.run_id,
                        "project_id": document.project_id,
                    },
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]


def build_run_index(
    state: ResearchRunState,
    *,
    embedding_client: EmbeddingClient | None = None,
    index_type: str = "hybrid",
) -> IndexManifest:
    client = embedding_client or LocalHashEmbeddingClient()
    documents = documents_from_state(state)
    embeddings = client.embed(_embedding_texts(documents))
    index_dir = Path(state.run_dir) / "retrieval"
    manifest = _manifest(
        index_dir=index_dir,
        project_id="",
        run_ids=[state.run_id],
        document_count=len(documents),
        index_type=index_type,
        embedding_model=client.model_name,
    )
    RetrievalIndexStore(index_dir).save(manifest, documents, embeddings)
    _write_retrieval_coverage(index_dir, manifest, documents)
    state.config["retrieval_index"] = {
        "path": str(index_dir),
        "document_count": len(documents),
        "embedding_model": client.model_name,
        "updated_at": manifest.created_at,
    }
    return manifest


def build_project_index(
    program: ResearchProgramState,
    *,
    embedding_client: EmbeddingClient | None = None,
    index_type: str = "hybrid",
) -> IndexManifest:
    client = embedding_client or LocalHashEmbeddingClient()
    documents = documents_from_program(program)
    embeddings = client.embed(_embedding_texts(documents))
    index_dir = Path(program.project.root_dir) / "retrieval"
    manifest = _manifest(
        index_dir=index_dir,
        project_id=program.project.id,
        run_ids=program.run_ids,
        document_count=len(documents),
        index_type=index_type,
        embedding_model=client.model_name,
    )
    RetrievalIndexStore(index_dir).save(manifest, documents, embeddings)
    _write_retrieval_coverage(index_dir, manifest, documents)
    return manifest


def search_run_index(
    config: GapForgeConfig,
    run_id: str,
    query: str,
    *,
    top_k: int = 10,
    embedding_client: EmbeddingClient | None = None,
) -> list[RetrievalResult]:
    state = ResearchStateManager(config).load_run(run_id)
    store = RetrievalIndexStore.for_run(state.run_dir)
    if not store.exists():
        build_run_index(state, embedding_client=embedding_client)
        ResearchStateManager(config).save_run(state)
    return _search_store(store, query, top_k=top_k, embedding_client=embedding_client)


def search_project_index(
    config: GapForgeConfig,
    project_id: str,
    query: str,
    *,
    top_k: int = 10,
    embedding_client: EmbeddingClient | None = None,
) -> list[RetrievalResult]:
    manager = ProjectMemoryManager(config)
    program = manager.load_project(project_id)
    store = RetrievalIndexStore.for_project(program.project.root_dir)
    if not store.exists():
        build_project_index(program, embedding_client=embedding_client)
    return _search_store(store, query, top_k=top_k, embedding_client=embedding_client)


def retrieval_candidates_for_state(
    state: ResearchRunState,
    query: str,
    *,
    top_k: int = 20,
    embedding_client: EmbeddingClient | None = None,
    persist: bool = False,
) -> tuple[list[RetrievalResult], list[str]]:
    store = RetrievalIndexStore.for_run(state.run_dir)
    if not store.exists():
        if persist:
            build_run_index(state, embedding_client=embedding_client)
            results = _search_store(store, query, top_k=top_k, embedding_client=embedding_client)
        else:
            documents = documents_from_state(state)
            retriever = HybridRetriever(documents, embedding_client=embedding_client)
            results = retriever.search(query, top_k=top_k)
    else:
        results = _search_store(store, query, top_k=top_k, embedding_client=embedding_client)
    paper_ids = []
    for result in results:
        paper_id = result.paper_id
        if not paper_id:
            linked = result.metadata.get("linked_paper_ids", [])
            if isinstance(linked, list) and linked:
                paper_id = str(linked[0])
        if paper_id and paper_id not in paper_ids:
            paper_ids.append(paper_id)
    state.config["retrieval_last_query"] = {
        "query": query,
        "result_count": len(results),
        "top_document_ids": [result.document_id for result in results[:5]],
        "updated_at": utc_now_iso(),
    }
    return results, paper_ids


def _search_store(
    store: RetrievalIndexStore,
    query: str,
    *,
    top_k: int,
    embedding_client: EmbeddingClient | None,
) -> list[RetrievalResult]:
    manifest = store.load_manifest()
    client = embedding_client
    if client is None or client.model_name != manifest.embedding_model:
        client = LocalHashEmbeddingClient()
    retriever = HybridRetriever(store.load_documents(), embeddings=store.load_embeddings(), embedding_client=client)
    return retriever.search(query, top_k=top_k)


def _manifest(
    *,
    index_dir: Path,
    project_id: str,
    run_ids: list[str],
    document_count: int,
    index_type: str,
    embedding_model: str,
) -> IndexManifest:
    now = utc_now_iso()
    manifest_id = hashlib.sha1(f"{project_id}:{','.join(run_ids)}:{document_count}:{now}".encode()).hexdigest()[:12]
    return IndexManifest(
        id=f"index-{manifest_id}",
        project_id=project_id,
        run_ids=run_ids,
        created_at=now,
        document_count=document_count,
        index_type=index_type,
        embedding_model=embedding_model,
        path=str(index_dir),
        provenance=Provenance(
            created_by_skill="retrieval-index",
            source_ids=[project_id, *run_ids],
            timestamp=now,
            reasoning_summary="Hybrid lexical/semantic retrieval index built from persisted GapForge artifacts.",
        ),
    )


def _write_retrieval_coverage(index_dir: Path, manifest: IndexManifest, documents: list[RetrievalDocument]) -> None:
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.object_type] = counts.get(document.object_type, 0) + 1
    lines = [
        "# Retrieval Coverage",
        "",
        f"- Index ID: `{manifest.id}`",
        f"- Index type: {manifest.index_type}",
        f"- Embedding model: {manifest.embedding_model}",
        f"- Documents: {manifest.document_count}",
        f"- Runs: {', '.join(manifest.run_ids) or 'none'}",
        f"- Project: {manifest.project_id or 'none'}",
        "",
        "## Documents by Type",
        "",
    ]
    lines.extend([f"- {key}: {value}" for key, value in sorted(counts.items())] or ["- none"])
    (index_dir / "retrieval_coverage.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _embedding_texts(documents: list[RetrievalDocument]) -> list[str]:
    return [f"{document.title}\n{document.text}" for document in documents]


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 0.0
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}


def _snippet(text: str, query: str, *, length: int = 220) -> str:
    clean = " ".join(text.split())
    if len(clean) <= length:
        return clean
    query_terms = [term for term in query.lower().split() if len(term) > 3]
    lower = clean.lower()
    start = 0
    for term in query_terms:
        idx = lower.find(term)
        if idx >= 0:
            start = max(0, idx - 60)
            break
    return clean[start : start + length].strip()
