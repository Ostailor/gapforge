"""Schemas for OpenReview-style reviewer calibration datasets."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance


@dataclass(slots=True)
class ReviewDatasetPaper:
    id: str
    title: str
    venue: str
    year: int
    paper_url: str
    pdf_path: str
    abstract: str
    decision: str
    average_score: float
    confidence_summary: str
    topic_tags: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-dataset"))


@dataclass(slots=True)
class ReviewRecord:
    id: str
    paper_id: str
    reviewer_id_hash: str
    score: float
    confidence: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    novelty_comments: list[str] = field(default_factory=list)
    empirical_comments: list[str] = field(default_factory=list)
    clarity_comments: list[str] = field(default_factory=list)
    reproducibility_comments: list[str] = field(default_factory=list)
    ethics_comments: list[str] = field(default_factory=list)
    recommendation: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-dataset"))


@dataclass(slots=True)
class ReviewDataset:
    id: str
    name: str
    source: str
    venue_years: list[str] = field(default_factory=list)
    paper_count: int = 0
    review_count: int = 0
    label_schema: dict[str, list[str]] = field(default_factory=dict)
    license_warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-dataset"))
