"""Run-local storage for downloaded paper artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from gapforge.fulltext.hashing import sha256_bytes
from gapforge.models import Paper, PaperArtifact, Provenance
from gapforge.state import utc_now_iso


class ArtifactStore:
    """Store artifacts under a run directory with stable metadata."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def paper_dir(self, paper_id: str) -> Path:
        directory = self.run_dir / "artifacts" / "papers" / safe_filename(paper_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def store_bytes(
        self,
        paper: Paper,
        data: bytes,
        *,
        source_url: str,
        artifact_type: str = "pdf",
        mime_type: str = "application/pdf",
        existing_artifacts: list[PaperArtifact] | None = None,
    ) -> PaperArtifact:
        digest = sha256_bytes(data)
        duplicate = _find_duplicate(paper.id, artifact_type, digest, existing_artifacts or [])
        if duplicate is not None:
            return duplicate

        extension = _extension_for(artifact_type, mime_type)
        filename = f"{safe_filename(artifact_type)}-{digest[:12]}{extension}"
        target = self.paper_dir(paper.id) / filename
        if not target.exists():
            target.write_bytes(data)
        return PaperArtifact(
            id=f"{safe_filename(paper.id)}-{safe_filename(artifact_type)}-{digest[:12]}",
            paper_id=paper.id,
            artifact_type=artifact_type,
            source_url=source_url,
            local_path=str(target.relative_to(self.run_dir)),
            sha256=digest,
            bytes_size=len(data),
            mime_type=mime_type,
            created_at=utc_now_iso(),
            status="available",
            provenance=Provenance(
                created_by_skill="pdf-downloader",
                source_ids=[paper.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Downloaded and validated artifact bytes, then stored them in the run directory.",
            ),
        )

    def failed_artifact(
        self,
        paper: Paper,
        *,
        source_url: str,
        error: str,
        artifact_type: str = "pdf",
        status: str = "failed",
    ) -> PaperArtifact:
        digest = sha256_bytes(f"{paper.id}:{source_url}:{status}:{error}".encode())[:12]
        now = utc_now_iso()
        return PaperArtifact(
            id=f"{safe_filename(paper.id)}-{safe_filename(artifact_type)}-{status}-{digest}",
            paper_id=paper.id,
            artifact_type=artifact_type,
            source_url=source_url,
            created_at=now,
            status=status,
            error=error,
            provenance=Provenance(
                created_by_skill="pdf-downloader",
                source_ids=[paper.id],
                timestamp=now,
                reasoning_summary="Recorded a PDF artifact attempt that did not produce a usable local file.",
            ),
        )


def safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    return safe[:120] or "item"


def _find_duplicate(
    paper_id: str,
    artifact_type: str,
    digest: str,
    artifacts: list[PaperArtifact],
) -> PaperArtifact | None:
    for artifact in artifacts:
        if (
            artifact.paper_id == paper_id
            and artifact.artifact_type == artifact_type
            and artifact.sha256 == digest
            and artifact.status == "available"
        ):
            return artifact
    return None


def _extension_for(artifact_type: str, mime_type: str) -> str:
    if artifact_type == "pdf" or "pdf" in mime_type.lower():
        return ".pdf"
    if artifact_type == "html" or "html" in mime_type.lower():
        return ".html"
    if artifact_type == "text" or "text" in mime_type.lower():
        return ".txt"
    return ".bin"
