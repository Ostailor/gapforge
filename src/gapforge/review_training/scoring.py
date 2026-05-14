"""Scoring utilities for reviewer training and calibration."""

from __future__ import annotations

import re

from gapforge.review_training.taxonomy import ReviewIssueLabel


def score_issue_recall_proxy(gold: list[ReviewIssueLabel], predicted: list[ReviewIssueLabel]) -> float:
    gold_keys = {(label.paper_id, label.issue_type) for label in gold}
    predicted_keys = {(label.paper_id, label.issue_type) for label in predicted}
    if not gold_keys:
        return 1.0 if not predicted_keys else 0.0
    return round(len(gold_keys & predicted_keys) / len(gold_keys), 4)


def score_severity_calibration(gold: list[ReviewIssueLabel], predicted: list[ReviewIssueLabel]) -> float:
    gold_by_key = {(label.paper_id, label.issue_type): label.severity for label in gold}
    predicted_by_key = {(label.paper_id, label.issue_type): label.severity for label in predicted}
    overlap = sorted(set(gold_by_key) & set(predicted_by_key))
    if not overlap:
        return 0.0
    correct = sum(1 for key in overlap if gold_by_key[key] == predicted_by_key[key])
    return round(correct / len(overlap), 4)


def score_review_specificity(predicted: list[ReviewIssueLabel]) -> float:
    if not predicted:
        return 0.0
    specific = [
        label
        for label in predicted
        if len(label.evidence_text.split()) >= 8 and not any(generic in label.evidence_text.lower() for generic in ["bad paper", "weak"])
    ]
    return round(len(specific) / len(predicted), 4)


def score_hallucination_rate(predicted: list[ReviewIssueLabel]) -> float:
    if not predicted:
        return 0.0
    hallucinated = [label for label in predicted if _has_fake_citation_or_result(label.evidence_text)]
    return round(len(hallucinated) / len(predicted), 4)


def score_evidence_linkage(predicted: list[ReviewIssueLabel]) -> float:
    if not predicted:
        return 0.0
    linked = [label for label in predicted if label.paper_id in label.evidence_text or "paper:" in label.evidence_text]
    return round(len(linked) / len(predicted), 4)


def score_missing_obvious_issue_rate(gold: list[ReviewIssueLabel], predicted: list[ReviewIssueLabel]) -> float:
    gold_keys = {(label.paper_id, label.issue_type) for label in gold if label.severity in {"major", "fatal"}}
    predicted_keys = {(label.paper_id, label.issue_type) for label in predicted}
    if not gold_keys:
        return 0.0
    return round(len(gold_keys - predicted_keys) / len(gold_keys), 4)


def score_predictions(gold: list[ReviewIssueLabel], predicted: list[ReviewIssueLabel]) -> dict[str, float]:
    return {
        "issue_recall_proxy": score_issue_recall_proxy(gold, predicted),
        "severity_calibration_score": score_severity_calibration(gold, predicted),
        "review_specificity_score": score_review_specificity(predicted),
        "hallucination_rate": score_hallucination_rate(predicted),
        "evidence_linkage_score": score_evidence_linkage(predicted),
        "missing_obvious_issue_rate": score_missing_obvious_issue_rate(gold, predicted),
    }


def _has_fake_citation_or_result(text: str) -> bool:
    lowered = text.lower()
    if "fake citation" in lowered or "invented result" in lowered or "unlinked result" in lowered:
        return True
    if re.search(r"\b[A-Z][a-z]+ et al\.?,?\s+(?:19|20)\d{2}\b", text):
        return True
    if re.search(r"\[(?:\d+|[A-Z][A-Za-z]+(?:19|20)\d{2})\]", text):
        return True
    return False
