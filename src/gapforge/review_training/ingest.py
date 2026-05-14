"""Synthetic and guarded OpenReview-style dataset ingestion."""

from __future__ import annotations

from typing import Any

from gapforge.models import Provenance
from gapforge.review_training.labels import (
    confidence_summary,
    extract_topic_tags,
    hash_reviewer_id,
    normalize_confidence,
    parse_score,
    recommendation_from_score,
    split_review_items,
)
from gapforge.review_training.schemas import ReviewDatasetPaper, ReviewRecord
from gapforge.state import slugify, utc_now_iso

SYNTHETIC_OPENREVIEW_FIXTURE: list[dict[str, Any]] = [
    {
        "id": "fixture-paper-calibrated-monitoring",
        "title": "Calibrated Monitoring Benchmarks for Sequential Audits",
        "venue": "FixtureReview",
        "year": 2024,
        "paper_url": "https://example.invalid/openreview/fixture-paper-calibrated-monitoring",
        "abstract": "A synthetic fixture paper about benchmark calibration for safety monitoring.",
        "decision": "accept",
        "reviews": [
            {
                "reviewer_id": "reviewer-a@example.invalid",
                "score": "8: accept",
                "confidence": "4: high",
                "strengths": ["Clear benchmark motivation.", "Strong calibration analysis."],
                "weaknesses": ["Limited external validity.", "Baselines need a stronger monitor."],
                "questions": ["How sensitive are thresholds to class imbalance?"],
                "limitations": ["Synthetic traces are not deployment evidence."],
                "novelty_comments": ["Novelty is incremental but useful for measurement."],
                "empirical_comments": ["Experiments are clear but should separate auxiliary datasets."],
                "clarity_comments": ["Writing is direct."],
                "reproducibility_comments": ["Artifact checklist is adequate."],
                "ethics_comments": ["Misuse risks are acknowledged."],
            },
            {
                "reviewer_id": "reviewer-b@example.invalid",
                "score": 6,
                "confidence": "3",
                "strengths": ["The problem framing is timely."],
                "weaknesses": ["The paper overstates what monitor specificity proves."],
                "questions": ["Can this support low-FPR deployment claims?"],
                "limitations": ["The benchmark is not real collusion evidence."],
                "novelty_comments": ["Closest prior work should be sharper."],
                "empirical_comments": ["More ablations are needed."],
                "clarity_comments": ["Contribution boundaries should be clearer."],
                "reproducibility_comments": ["Seeds and splits are present."],
                "ethics_comments": ["Safety claims need stronger caveats."],
            },
        ],
    },
    {
        "id": "fixture-paper-weak-evidence",
        "title": "A Broad Claim About Autonomous Evaluation",
        "venue": "FixtureReview",
        "year": 2024,
        "paper_url": "https://example.invalid/openreview/fixture-paper-weak-evidence",
        "abstract": "A synthetic fixture paper with unclear empirical grounding.",
        "decision": "reject",
        "reviews": [
            {
                "reviewer_id": "reviewer-c@example.invalid",
                "score": "3: reject",
                "confidence": "5: high",
                "strengths": ["The motivation is understandable."],
                "weaknesses": ["Unsupported claims dominate the paper.", "The empirical setup is underspecified."],
                "questions": ["What data were actually used?"],
                "limitations": ["No meaningful limitations section is present."],
                "novelty_comments": ["Novelty is not established."],
                "empirical_comments": ["The results are not auditable."],
                "clarity_comments": ["Definitions are ambiguous."],
                "reproducibility_comments": ["No runnable artifact is provided."],
                "ethics_comments": ["Potential misuse is not discussed."],
            }
        ],
    },
]


def guarded_openreview_ingest_warning(venue: str, year: int) -> str:
    return (
        f"Live OpenReview ingestion for {venue} {year} is disabled unless public availability, source terms, and privacy boundaries "
        "are explicitly verified. No hidden/private review data was downloaded or stored."
    )


def parse_fixture_paper(raw: dict[str, Any], *, dataset_id: str) -> tuple[ReviewDatasetPaper, list[ReviewRecord]]:
    reviews = [parse_fixture_review(item, dataset_id=dataset_id, paper_id=raw["id"]) for item in raw.get("reviews", [])]
    scores = [review.score for review in reviews if review.score > 0]
    confidences = [review.confidence for review in reviews]
    average_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    paper = ReviewDatasetPaper(
        id=raw["id"],
        title=str(raw.get("title", "")),
        venue=str(raw.get("venue", "")),
        year=int(raw.get("year", 0)),
        paper_url=str(raw.get("paper_url", "")),
        pdf_path=str(raw.get("pdf_path", "")),
        abstract=str(raw.get("abstract", "")),
        decision=str(raw.get("decision", "")),
        average_score=average_score,
        confidence_summary=confidence_summary(confidences),
        topic_tags=extract_topic_tags(str(raw.get("title", "")), str(raw.get("abstract", ""))),
        provenance=Provenance(
            created_by_skill="review-dataset-ingest-fixture",
            source_ids=[dataset_id, raw["id"]],
            timestamp=utc_now_iso(),
            reasoning_summary="Parsed synthetic public fixture paper metadata for reviewer calibration tests.",
        ),
    )
    return paper, reviews


def parse_fixture_review(raw: dict[str, Any], *, dataset_id: str, paper_id: str) -> ReviewRecord:
    score = parse_score(raw.get("score"))
    reviewer_hash = hash_reviewer_id(str(raw.get("reviewer_id", "anonymous")), dataset_id=dataset_id)
    return ReviewRecord(
        id=f"review-{slugify(paper_id)}-{reviewer_hash}",
        paper_id=paper_id,
        reviewer_id_hash=reviewer_hash,
        score=score,
        confidence=normalize_confidence(raw.get("confidence")),
        strengths=split_review_items(raw.get("strengths")),
        weaknesses=split_review_items(raw.get("weaknesses")),
        questions=split_review_items(raw.get("questions")),
        limitations=split_review_items(raw.get("limitations")),
        novelty_comments=split_review_items(raw.get("novelty_comments")),
        empirical_comments=split_review_items(raw.get("empirical_comments")),
        clarity_comments=split_review_items(raw.get("clarity_comments")),
        reproducibility_comments=split_review_items(raw.get("reproducibility_comments")),
        ethics_comments=split_review_items(raw.get("ethics_comments")),
        recommendation=str(raw.get("recommendation") or recommendation_from_score(score)),
        provenance=Provenance(
            created_by_skill="review-dataset-ingest-fixture",
            source_ids=[dataset_id, paper_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Parsed synthetic fixture review with reviewer identifier hashed.",
        ),
    )
