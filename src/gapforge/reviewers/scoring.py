"""Deterministic reviewer scoring helpers."""

from __future__ import annotations

from gapforge.models import ReviewerReview


def decision_risk(reviews: list[ReviewerReview]) -> str:
    if not reviews:
        return "high"
    if any(review.role == "novelty" and review.fatal_flaws for review in reviews):
        return "reject_likely"
    fatal_count = sum(bool(review.fatal_flaws) for review in reviews)
    average = sum(review.score for review in reviews) / len(reviews)
    if fatal_count >= 2 or average < 4:
        return "reject_likely"
    if fatal_count == 1 or average < 6:
        return "high"
    if average < 7:
        return "medium"
    return "low"


def score_from_issues(*, base: float = 8.0, major: int = 0, fatal: int = 0, minor: int = 0) -> float:
    score = base - (fatal * 4.0) - (major * 1.2) - (minor * 0.4)
    return round(max(1.0, min(10.0, score)), 1)


def confidence_from_evidence(evidence_count: int, *, has_full_protocol: bool = False) -> str:
    if evidence_count >= 3 and has_full_protocol:
        return "high"
    if evidence_count >= 1:
        return "medium"
    return "low"
