"""Deterministic query set generation for real literature searches."""

from __future__ import annotations

from gapforge.models import SourcePolicyProfile


def primary_queries(topic: str) -> list[str]:
    return _dedupe([topic, f'"{topic}"'])


def recency_queries(topic: str) -> list[str]:
    return _dedupe(
        [
            f"{topic} recent",
            f"{topic} 2024 2025 2026",
            f"{topic} frontier",
        ]
    )


def survey_queries(topic: str, profile: SourcePolicyProfile) -> list[str]:
    patterns = profile.must_include_query_patterns or ["survey"]
    return _dedupe(
        [f"{topic} survey", f"{topic} systematic review", *[f"{topic} {pattern}" for pattern in patterns if "survey" in pattern]]
    )


def benchmark_queries(topic: str) -> list[str]:
    return _dedupe([f"{topic} benchmark", f"{topic} evaluation", f"{topic} baseline comparison"])


def dataset_queries(topic: str) -> list[str]:
    return _dedupe([f"{topic} dataset", f"{topic} benchmark dataset", f"{topic} evaluation data"])


def method_queries(topic: str) -> list[str]:
    method_terms = _method_terms(topic)
    return _dedupe([f"{topic} method", f"{topic} approach", *[f"{term} method {topic}" for term in method_terms[:3]]])


def closest_prior_work_queries(topic: str) -> list[str]:
    return _dedupe(
        [
            f"{topic} closest prior work",
            f"{topic} related work",
            f"{topic} limitation",
            f"{topic} already solved",
            f"{topic} reproducibility evaluation",
        ]
    )


def adjacent_field_queries(topic: str, profile: SourcePolicyProfile) -> list[str]:
    adjacent = list(profile.adjacent_field_requirements)
    lowered = topic.lower()
    if "false positive" in lowered or "specificity" in lowered:
        adjacent.extend(["medical screening specificity", "industrial quality control false positives"])
    if "covert" in lowered or "collusion" in lowered:
        adjacent.extend(["covert channels", "cartel detection", "steganography"])
    if "evasion" in lowered or "monitor" in lowered:
        adjacent.extend(["intrusion detection evasion", "adversarial machine learning"])
    return _dedupe([f"{field} {topic}" for field in adjacent])


def exclusion_queries(topic: str) -> list[str]:
    return _dedupe([f"{topic} negative result", f"{topic} failure mode", f"{topic} limitations"])


def _method_terms(topic: str) -> list[str]:
    stop = {"the", "and", "for", "with", "against", "in", "of", "to", "a", "an"}
    return [token for token in topic.lower().replace("-", " ").split() if len(token) > 3 and token not in stop]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
