"""Optional OCR hook for low-density PDF text extraction."""

from __future__ import annotations

from typing import Protocol

from gapforge.models import OcrAttemptRecord, PaperArtifact, Provenance, ResearchRunState
from gapforge.state import utc_now_iso


class OcrProvider(Protocol):
    def attempt(self, artifact: PaperArtifact, pages: list[int]) -> OcrAttemptRecord:
        """Attempt OCR for selected pages."""


class UnavailableOcrProvider:
    """Default OCR provider: records that OCR is unavailable without adding dependencies."""

    def attempt(self, artifact: PaperArtifact, pages: list[int]) -> OcrAttemptRecord:
        return OcrAttemptRecord(
            id=f"ocr-{artifact.paper_id}-{artifact.id}",
            paper_id=artifact.paper_id,
            artifact_id=artifact.id,
            pages_attempted=pages,
            status="unavailable",
            warnings=["OCR is optional and no OCR provider is configured."],
            provenance=Provenance(
                created_by_skill="ocr-hook",
                source_ids=[artifact.paper_id, artifact.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Recorded OCR recommendation without attempting OCR because no provider is configured.",
            ),
        )


def record_ocr_recommendations(
    state: ResearchRunState,
    *,
    provider: OcrProvider | None = None,
    density_threshold: int = 300,
) -> list[OcrAttemptRecord]:
    provider = provider or UnavailableOcrProvider()
    section_text_by_paper: dict[str, str] = {}
    for section in state.paper_sections:
        section_text_by_paper.setdefault(section.paper_id, "")
        section_text_by_paper[section.paper_id] += section.text
    records: list[OcrAttemptRecord] = []
    existing = {(record.paper_id, record.artifact_id) for record in state.ocr_attempts}
    for artifact in state.paper_artifacts:
        if artifact.artifact_type != "pdf" or artifact.status != "available":
            continue
        if (artifact.paper_id, artifact.id) in existing:
            continue
        text_length = len(section_text_by_paper.get(artifact.paper_id, "").strip())
        if text_length >= density_threshold:
            records.append(
                OcrAttemptRecord(
                    id=f"ocr-{artifact.paper_id}-{artifact.id}",
                    paper_id=artifact.paper_id,
                    artifact_id=artifact.id,
                    status="skipped",
                    warnings=["Extracted text density appears sufficient; OCR not recommended."],
                    provenance=Provenance(
                        created_by_skill="ocr-hook",
                        source_ids=[artifact.paper_id, artifact.id],
                        timestamp=utc_now_iso(),
                        reasoning_summary="Skipped OCR because parsed text density was above the configured threshold.",
                    ),
                )
            )
        else:
            records.append(provider.attempt(artifact, pages=[]))
    state.ocr_attempts = _merge_ocr(state.ocr_attempts, records)
    return state.ocr_attempts


def _merge_ocr(existing: list[OcrAttemptRecord], new_records: list[OcrAttemptRecord]) -> list[OcrAttemptRecord]:
    by_key = {(record.paper_id, record.artifact_id): record for record in existing}
    for record in new_records:
        by_key[(record.paper_id, record.artifact_id)] = record
    return list(by_key.values())
