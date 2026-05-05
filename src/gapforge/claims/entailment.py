"""Deterministic claim normalization and duplicate/entailment helpers."""

from __future__ import annotations

import re


def normalize_claim_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\b(the|a|an|this|that|these|those)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(normalize_claim_text(left).split())
    right_tokens = set(normalize_claim_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def are_duplicate_claims(left: str, right: str) -> bool:
    if normalize_claim_text(left) == normalize_claim_text(right):
        return True
    return token_similarity(left, right) >= 0.82
