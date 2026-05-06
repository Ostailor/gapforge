"""Baseline selection from related-work matrices."""

from __future__ import annotations

from gapforge.models import BaselineRecord, CorpusPaperRecord, Provenance, RelatedWorkEntry
from gapforge.state import utc_now_iso


def baseline_record_from_related_work(
    entry: RelatedWorkEntry,
    *,
    corpus_papers: list[CorpusPaperRecord] | None = None,
) -> BaselineRecord:
    paper_title = _paper_title(entry.paper_id, corpus_papers or [])
    baseline_type = _baseline_type(entry.relationship)
    related_entry_id = related_work_entry_id(entry)
    return BaselineRecord(
        id=f"baseline-{related_entry_id}",
        name=f"{paper_title} baseline",
        description=entry.what_it_contributes or "Baseline selected from related-work matrix.",
        baseline_type=baseline_type,
        source_paper_ids=[entry.paper_id] if entry.paper_id else [],
        related_work_entry_ids=[related_entry_id],
        code_available=False,
        required_for_submission=entry.must_cite or entry.baseline_candidate,
        risk_if_missing=entry.reviewer_risk_if_omitted or "Reviewer may object if this related-work baseline is omitted.",
        expected_inputs=["experiment dataset"],
        expected_outputs=["baseline predictions", "baseline metric summary"],
        provenance=Provenance(
            created_by_skill="baseline-selection",
            source_ids=[entry.direction_id, entry.paper_id, related_entry_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Converted a related-work baseline candidate into an explicit experiment baseline record.",
        ),
    )


def related_work_entry_id(entry: RelatedWorkEntry) -> str:
    return f"rw-{entry.direction_id}-{entry.paper_id}-{entry.relationship}".replace("/", "-")


def _paper_title(paper_id: str, corpus_papers: list[CorpusPaperRecord]) -> str:
    record = next((item for item in corpus_papers if item.paper_id == paper_id or paper_id in item.source_paper_ids), None)
    if record is not None and record.canonical_title:
        return record.canonical_title
    return paper_id or "related work"


def _baseline_type(relationship: str) -> str:
    if relationship in {"directly_solves", "partially_solves", "baseline_to_include"}:
        return "prior_work"
    if relationship == "benchmark_dataset_provider":
        return "prior_work"
    if relationship == "negative_result":
        return "heuristic"
    return "unknown"
