"""Label extraction helpers for review calibration datasets."""

from __future__ import annotations

import hashlib
import re
from typing import Any

LABEL_SCHEMA = {
    "review_fields": [
        "strengths",
        "weaknesses",
        "questions",
        "limitations",
        "novelty_comments",
        "empirical_comments",
        "clarity_comments",
        "reproducibility_comments",
        "ethics_comments",
    ],
    "score_scale": ["numeric score when available", "0.0 when absent"],
    "privacy": ["reviewer identifiers are SHA-256 hashed with a dataset-local prefix"],
}


def hash_reviewer_id(reviewer_id: str, *, dataset_id: str) -> str:
    digest = hashlib.sha256(f"{dataset_id}:{reviewer_id}".encode()).hexdigest()
    return f"reviewer-{digest[:16]}"


def parse_score(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    text = str(value or "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else 0.0


def normalize_confidence(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    number = parse_score(text)
    lowered = text.lower()
    if number >= 4 or "high" in lowered:
        return "high"
    if number > 0 and number <= 2 or "low" in lowered:
        return "low"
    return "medium"


def recommendation_from_score(score: float) -> str:
    if score >= 8:
        return "strong_accept"
    if score >= 6:
        return "weak_accept"
    if score >= 4:
        return "borderline"
    if score > 0:
        return "reject"
    return "unknown"


def split_review_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    bullet_items = [item.strip(" -\t") for item in re.split(r"\n+|; ", text) if item.strip(" -\t")]
    return bullet_items or [text]


def extract_topic_tags(title: str, abstract: str) -> list[str]:
    text = f"{title} {abstract}".lower()
    tags: list[str] = []
    tag_terms = {
        "benchmark": ["benchmark", "dataset", "evaluation"],
        "safety": ["safety", "monitor", "alignment", "risk"],
        "language_models": ["language model", "llm", "transformer"],
        "multi_agent": ["multi-agent", "multiagent", "agent"],
        "reproducibility": ["reproducib", "artifact", "replication"],
    }
    for tag, terms in tag_terms.items():
        if any(term in text for term in terms):
            tags.append(tag)
    return tags


def confidence_summary(confidences: list[str]) -> str:
    if not confidences:
        return "unknown"
    counts = {label: confidences.count(label) for label in sorted(set(confidences))}
    return ", ".join(f"{label}={count}" for label, count in counts.items())


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
