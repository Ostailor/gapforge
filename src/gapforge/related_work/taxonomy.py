"""Deterministic related-work relationship taxonomy."""

from __future__ import annotations

RELATIONSHIPS = {
    "directly_solves",
    "partially_solves",
    "adjacent_method",
    "benchmark_dataset_provider",
    "theoretical_foundation",
    "negative_result",
    "survey_background",
    "cross_domain_analogy",
    "baseline_to_include",
}

REQUIRED_CATEGORIES = {
    "directly_solves",
    "partially_solves",
    "survey_background",
    "baseline_to_include",
}


def normalize_relationship(value: str) -> str:
    key = value.lower().strip().replace(" ", "_").replace("/", "_").replace("-", "_")
    aliases = {
        "directly_solves": "directly_solves",
        "partial": "partially_solves",
        "partially_solves": "partially_solves",
        "adjacent": "adjacent_method",
        "adjacent_method": "adjacent_method",
        "benchmark": "benchmark_dataset_provider",
        "dataset": "benchmark_dataset_provider",
        "benchmark_dataset_provider": "benchmark_dataset_provider",
        "theory": "theoretical_foundation",
        "theoretical_foundation": "theoretical_foundation",
        "negative": "negative_result",
        "negative_result": "negative_result",
        "survey": "survey_background",
        "background": "survey_background",
        "survey_background": "survey_background",
        "cross_domain": "cross_domain_analogy",
        "cross_domain_analogy": "cross_domain_analogy",
        "baseline": "baseline_to_include",
        "baseline_to_include": "baseline_to_include",
    }
    return aliases.get(key, key if key in RELATIONSHIPS else "adjacent_method")


def relationship_label(value: str) -> str:
    return normalize_relationship(value).replace("_", " ")
