"""Scoring helpers for research direction maturity."""

from __future__ import annotations

MATURITY_ORDER = {
    "seed": 0,
    "candidate": 1,
    "validated_gap": 2,
    "experiment_ready": 3,
    "manuscript_ready": 4,
    "rejected": -1,
}


def maturity_rank(maturity: str) -> int:
    return MATURITY_ORDER.get(maturity, 0)


def readiness_score(maturity: str, blocking_issues: list[str]) -> float:
    if maturity == "rejected":
        return 0.0
    base = {
        "seed": 0.15,
        "candidate": 0.35,
        "validated_gap": 0.55,
        "experiment_ready": 0.75,
        "manuscript_ready": 0.95,
    }.get(maturity, 0.1)
    penalty = min(0.3, 0.04 * len(blocking_issues))
    return max(0.0, min(1.0, base - penalty))


def next_maturity(current: str, proposed: str) -> str:
    if current == "rejected" or proposed == "rejected":
        return proposed
    return proposed if maturity_rank(proposed) >= maturity_rank(current) else current
