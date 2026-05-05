"""PDF download support for full-text-aware research runs."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from gapforge.fulltext.artifact_store import ArtifactStore
from gapforge.models import Paper, PaperArtifact, ResearchRunState
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.http_client import CachedHttpClient, HttpClientError

DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


class BinaryHttpClient(Protocol):
    def get_bytes(
        self,
        url: str,
        params: dict[str, object] | None = None,
        *,
        namespace: str = "http",
        max_bytes: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]: ...


class PdfDownloader:
    """Download available PDFs while recording failures as state artifacts."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        http_client: BinaryHttpClient | None = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> None:
        if http_client is None:
            if cache_dir is None:
                raise ValueError("PdfDownloader requires cache_dir when http_client is not provided")
            http_client = CachedHttpClient(cache_dir)
        self.http_client = http_client
        self.max_file_size = max_file_size

    def download_for_state(
        self,
        state: ResearchRunState,
        *,
        paper_id: str | None = None,
        max_papers: int | None = None,
        skip_existing: bool = False,
    ) -> list[PaperArtifact]:
        store = ArtifactStore(Path(state.run_dir))
        selected_papers = _select_papers(state, paper_id=paper_id, max_papers=max_papers)
        new_artifacts: list[PaperArtifact] = []
        warnings: list[str] = []

        for paper in selected_papers:
            if skip_existing and _has_available_pdf(state, paper.id):
                continue
            artifact = self._download_one(store, paper, existing_artifacts=state.paper_artifacts + new_artifacts)
            new_artifacts.append(artifact)
            if artifact.status in {"failed", "skipped"}:
                warnings.append(f"{paper.id}: {artifact.error}")

        state.paper_artifacts = _merge_artifacts(state.paper_artifacts, new_artifacts)
        update_source_coverage(state, warnings)
        return new_artifacts

    def _download_one(
        self,
        store: ArtifactStore,
        paper: Paper,
        *,
        existing_artifacts: list[PaperArtifact],
    ) -> PaperArtifact:
        source_url = infer_pdf_url(paper)
        if not source_url:
            return store.failed_artifact(
                paper,
                source_url="",
                error="No reliable PDF URL available.",
                status="skipped",
            )
        if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
            return store.failed_artifact(
                paper,
                source_url=source_url,
                error="Network disabled; skipped PDF download.",
                status="skipped",
            )
        try:
            data, response_headers = self.http_client.get_bytes(
                source_url,
                namespace="pdf",
                max_bytes=self.max_file_size,
                headers={"Accept": "application/pdf"},
            )
            mime_type = _content_type(response_headers)
            _validate_pdf(data, mime_type=mime_type, source_url=source_url)
            return store.store_bytes(
                paper,
                data,
                source_url=source_url,
                artifact_type="pdf",
                mime_type=mime_type or "application/pdf",
                existing_artifacts=existing_artifacts,
            )
        except (HttpClientError, ValueError, RuntimeError, OSError) as exc:
            return store.failed_artifact(paper, source_url=source_url, error=str(exc), status="failed")


def infer_pdf_url(paper: Paper) -> str:
    """Infer only reliable PDF URLs from explicit metadata or stable source IDs."""

    if paper.pdf_url:
        return paper.pdf_url
    if paper.arxiv_id:
        return f"https://arxiv.org/pdf/{paper.arxiv_id}"
    return ""


def _select_papers(state: ResearchRunState, *, paper_id: str | None, max_papers: int | None) -> list[Paper]:
    if paper_id is not None:
        matches = [paper for paper in state.papers if paper.id == paper_id]
        if not matches:
            raise ValueError(f"No paper found for paper id {paper_id}")
        return matches

    selected = state.papers
    if state.paper_triage is not None:
        target_ids = {
            decision.paper_id
            for decision in state.paper_triage.decisions
            if decision.tier.lower().startswith("tier 1") or decision.tier.lower().startswith("tier 2")
        }
        if target_ids:
            selected = [paper for paper in state.papers if paper.id in target_ids]
    return selected[:max_papers] if max_papers is not None else selected


def _has_available_pdf(state: ResearchRunState, paper_id: str) -> bool:
    return any(
        artifact.paper_id == paper_id and artifact.artifact_type == "pdf" and artifact.status == "available"
        for artifact in state.paper_artifacts
    )


def _merge_artifacts(existing: list[PaperArtifact], new: list[PaperArtifact]) -> list[PaperArtifact]:
    by_id = {artifact.id: artifact for artifact in existing}
    for artifact in new:
        duplicate = _same_available_artifact(by_id.values(), artifact)
        if duplicate is not None:
            by_id[duplicate.id] = duplicate
            continue
        by_id[artifact.id] = artifact
    return list(by_id.values())


def _same_available_artifact(existing: Iterable[PaperArtifact], artifact: PaperArtifact) -> PaperArtifact | None:
    if artifact.status != "available":
        return None
    for current in existing:
        if (
            current.paper_id == artifact.paper_id
            and current.artifact_type == artifact.artifact_type
            and current.sha256 == artifact.sha256
            and current.status == "available"
        ):
            return current
    return None


def update_source_coverage(state: ResearchRunState, warnings: list[str] | None = None) -> None:
    skipped = [
        f"{artifact.paper_id}: {artifact.error}"
        for artifact in state.paper_artifacts
        if artifact.artifact_type == "pdf" and artifact.status == "skipped" and artifact.error
    ]
    refresh_source_coverage(state, list(warnings or []) + skipped)


def _content_type(headers: dict[str, str]) -> str:
    return headers.get("content-type", "").split(";", maxsplit=1)[0].strip().lower()


def _validate_pdf(data: bytes, *, mime_type: str, source_url: str) -> None:
    if mime_type and mime_type not in {"application/pdf", "application/octet-stream", "binary/octet-stream"}:
        raise ValueError(f"Invalid PDF response from {source_url}: content type {mime_type!r}")
    if not data:
        raise ValueError(f"Invalid PDF response from {source_url}: empty body")
    if not data.lstrip()[:4] == b"%PDF":
        raise ValueError(f"Invalid PDF response from {source_url}: body does not start with %PDF")
