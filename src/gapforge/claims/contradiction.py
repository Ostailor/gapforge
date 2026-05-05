"""Deterministic contradiction checks for project claim graphs."""

from __future__ import annotations

import re
from collections.abc import Iterable

from gapforge.claims.entailment import normalize_claim_text, token_similarity
from gapforge.llm.base import LLMClient


def contradiction_reason(left: str, right: str) -> str:
    left_norm = normalize_claim_text(left)
    right_norm = normalize_claim_text(right)
    if _low_fpr_evaluation_conflict(left_norm, right_norm):
        return "One claim says work was evaluated at low FPR while the other says it was not."
    if _requires_conflict(left_norm, right_norm):
        return "One claim says a requirement exists while the other says it does not."
    if _works_fails_conflict(left_norm, right_norm):
        return "One claim says the approach works while the other says it fails."
    if _metric_direction_conflict(left_norm, right_norm):
        return "Claims make opposite metric-direction statements."
    return ""


def contradicts(left: str, right: str) -> bool:
    return bool(contradiction_reason(left, right))


def llm_contradiction_check(
    left: str,
    right: str,
    client: LLMClient | None = None,
) -> tuple[bool, str]:
    """Optional LLM contradiction hook. Tests should use fake clients only."""

    deterministic = contradiction_reason(left, right)
    if deterministic or client is None:
        return bool(deterministic), deterministic
    try:
        payload = client.complete_json(
            (
                "Determine whether two public research claims contradict each other. "
                "Return JSON with keys contradicts (boolean) and reason (string).\n"
                f"Claim A: {left}\nClaim B: {right}"
            ),
            schema_name="claim-contradiction",
            system="Return valid JSON only. Do not invent evidence.",
        )
    except ValueError:
        payload = client.complete_json(
            (
                "Determine whether two public research claims contradict each other. "
                "Return a conservative novelty-gate JSON object if no claim-contradiction schema is available.\n"
                f"Claim A: {left}\nClaim B: {right}"
            ),
            schema_name="novelty-gate",
            system="Return valid JSON only. Do not invent evidence.",
        )
    value = bool(payload.get("contradicts", False))
    reason = str(payload.get("reason", "LLM contradiction check returned no reason."))
    return value, reason if value else ""


def contradiction_pairs(texts: Iterable[tuple[str, str]]) -> list[tuple[str, str, str]]:
    pairs = list(texts)
    found: list[tuple[str, str, str]] = []
    for index, (left_id, left_text) in enumerate(pairs):
        for right_id, right_text in pairs[index + 1 :]:
            reason = contradiction_reason(left_text, right_text)
            if reason:
                found.append((left_id, right_id, reason))
    return found


def _low_fpr_evaluation_conflict(left: str, right: str) -> bool:
    return _bidirectional(left, right, _has_low_fpr_positive, _has_low_fpr_negative)


def _has_low_fpr_positive(text: str) -> bool:
    if _has_low_fpr_negative(text):
        return False
    return any(phrase in text for phrase in ["evaluated at low fpr", "evaluated under low fpr", "low false positive evaluation"])


def _has_low_fpr_negative(text: str) -> bool:
    return any(
        phrase in text
        for phrase in [
            "not evaluated at low fpr",
            "not evaluated under low fpr",
            "without low fpr evaluation",
            "lacks low false positive evaluation",
        ]
    )


def _requires_conflict(left: str, right: str) -> bool:
    requires = re.compile(r"\brequires?\s+([a-z0-9 ]{2,40})")
    no_requires = re.compile(r"\b(?:does not|doesn't|do not|without|no)\s+requires?\s+([a-z0-9 ]{2,40})")
    return _pattern_conflict(left, right, requires, no_requires)


def _works_fails_conflict(left: str, right: str) -> bool:
    positive_terms = ["works", "succeeds", "improves", "is robust", "generalizes"]
    negative_terms = ["fails", "does not work", "doesn't work", "degrades", "is not robust", "does not generalize"]
    return _bidirectional(left, right, lambda text: _contains_any(text, positive_terms), lambda text: _contains_any(text, negative_terms))


def _metric_direction_conflict(left: str, right: str) -> bool:
    metric_terms = ["accuracy", "precision", "recall", "auc", "false positive", "fpr", "latency"]
    if not any(term in left and term in right for term in metric_terms):
        return False
    positive = ["improves", "increases", "higher", "reduces false positive", "lowers false positive"]
    negative = ["worsens", "decreases", "lower", "increases false positive", "raises false positive"]
    return _bidirectional(left, right, lambda text: _contains_any(text, positive), lambda text: _contains_any(text, negative))


def _pattern_conflict(left: str, right: str, positive: re.Pattern[str], negative: re.Pattern[str]) -> bool:
    for first, second in [(left, right), (right, left)]:
        pos = positive.search(first)
        neg = negative.search(second)
        if pos and neg and token_similarity(pos.group(1), neg.group(1)) >= 0.3:
            return True
    return False


def _bidirectional(left: str, right: str, positive, negative) -> bool:
    return (positive(left) and negative(right)) or (positive(right) and negative(left))


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)
