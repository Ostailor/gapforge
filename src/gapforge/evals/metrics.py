"""Metrics for evaluator harnesses."""

from __future__ import annotations

import re
from dataclasses import dataclass

from gapforge.models import Claim, ExperimentPlan, Gap, NoveltyAssessment, ResearchRunState, ReviewerObjection


@dataclass(slots=True)
class RunMetrics:
    paper_count: int
    claim_count: int
    gap_count: int
    experiment_count: int

    @classmethod
    def from_state(cls, state: ResearchRunState) -> RunMetrics:
        return cls(
            paper_count=len(state.papers),
            claim_count=len(state.claims),
            gap_count=len(state.gaps),
            experiment_count=len(state.experiments),
        )


@dataclass(slots=True)
class EvalScores:
    gap_specificity_score: float
    evidence_linkage_score: float
    novelty_gate_accuracy: float
    duplicate_detection_rate: float
    unsupported_claim_rate: float
    experiment_completeness_score: float
    reviewer_objection_quality_score: float

    def overall(self) -> float:
        positive = [
            self.gap_specificity_score,
            self.evidence_linkage_score,
            self.novelty_gate_accuracy,
            self.duplicate_detection_rate,
            self.experiment_completeness_score,
            self.reviewer_objection_quality_score,
        ]
        return round((sum(positive) + (1.0 - self.unsupported_claim_rate)) / 7, 3)


def gap_specificity_score(gaps: list[Gap]) -> float:
    if not gaps:
        return 0.0
    generic_terms = {"better", "improve", "ai", "modern", "novel", "use"}
    scores = []
    for gap in gaps:
        text = f"{gap.title} {gap.description} {gap.why_existing_work_does_not_solve_it} {gap.minimum_experiment_needed}"
        tokens = _tokens(text)
        has_mechanism = any(
            term in text.lower()
            for term in ["false-positive", "fixed", "benchmark", "sensor", "transaction", "lexical", "calibration", "outage"]
        )
        generic_penalty = sum(1 for token in tokens if token in generic_terms) / max(1, len(tokens))
        length_score = min(len(tokens) / 28, 1.0)
        scores.append(max(0.0, min(1.0, (0.55 * length_score) + (0.45 if has_mechanism else 0.0) - generic_penalty)))
    return round(sum(scores) / len(scores), 3)


def evidence_linkage_score(gaps: list[Gap]) -> float:
    if not gaps:
        return 0.0
    linked = [
        bool(gap.supporting_paper_ids or gap.supporting_claim_ids or gap.linked_paper_ids or gap.explicit_reason)
        and bool(gap.risk_that_gap_is_fake)
        for gap in gaps
    ]
    return round(sum(1 for item in linked if item) / len(gaps), 3)


def novelty_gate_accuracy(assessments: list[NoveltyAssessment], expected_duplicates: list[dict[str, object]]) -> float:
    if not expected_duplicates:
        return 1.0
    correct = 0
    for duplicate in expected_duplicates:
        expected = str(duplicate.get("expected_verdict", "reject"))
        duplicate_text = f"{duplicate.get('id', '')} {duplicate.get('title', '')} {duplicate.get('description', '')}".lower()
        matched = [
            assessment
            for assessment in assessments
            if _overlap(duplicate_text, assessment.idea_summary.lower()) >= 0.25
            or str(duplicate.get("id", "")) == assessment.target_gap_or_hypothesis_id
        ]
        if any(assessment.verdict == expected for assessment in matched):
            correct += 1
    return round(correct / len(expected_duplicates), 3)


def duplicate_detection_rate(assessments: list[NoveltyAssessment]) -> float:
    duplicate_like = [
        assessment for assessment in assessments if assessment.similarity_to_prior_work >= 0.7 or assessment.verdict == "reject"
    ]
    if not duplicate_like:
        return 0.0
    return round(sum(1 for item in duplicate_like if item.verdict == "reject") / len(duplicate_like), 3)


def unsupported_claim_rate(claims: list[Claim]) -> float:
    if not claims:
        return 0.0
    unsupported = [
        claim
        for claim in claims
        if claim.status == "supported"
        and (not claim.supporting_evidence or not claim.source_paper_ids)
        or claim.type == "novelty"
        and not claim.closest_prior_work
        or claim.status == "unsupported"
    ]
    return round(len(unsupported) / len(claims), 3)


def experiment_completeness_score(experiments: list[ExperimentPlan]) -> float:
    if not experiments:
        return 0.0
    required = [
        "linked_gap_ids",
        "hypothesis",
        "minimum_viable_experiment",
        "baselines",
        "metrics",
        "statistical_tests",
        "ablations",
        "what_result_would_falsify_the_idea",
        "reviewer_killer_result",
        "risks",
    ]
    scores = []
    for experiment in experiments:
        present = 0
        for field_name in required:
            value = getattr(experiment, field_name)
            present += bool(value)
        scores.append(present / len(required))
    return round(sum(scores) / len(scores), 3)


def reviewer_objection_quality_score(objections: list[ReviewerObjection]) -> float:
    if not objections:
        return 0.0
    categories = {item.category for item in objections}
    serious = sum(1 for item in objections if item.severity in {"major", "fatal"})
    concrete = sum(1 for item in objections if item.why_reviewer_would_care and item.suggested_fix)
    return round(min(1.0, (0.4 * len(categories) / 6) + (0.3 * serious / len(objections)) + (0.3 * concrete / len(objections))), 3)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9-]+", text.lower())


def _overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
