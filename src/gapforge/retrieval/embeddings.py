"""Offline embedding clients for optional semantic retrieval."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from gapforge.retrieval.lexical import tokenize


class EmbeddingClient(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text."""


class LocalHashEmbeddingClient:
    """Deterministic local embedding fallback based on hashed token features."""

    model_name = "local-hash"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(_hashed_vector(text, self.dimensions)) for text in texts]


class FakeEmbeddingClient:
    """Deterministic test client with a tiny synonym map."""

    model_name = "fake-semantic"

    SYNONYMS = {
        "fpr": "false_positive",
        "false": "false_positive",
        "positive": "false_positive",
        "specificity": "false_positive",
        "recall": "sensitivity",
        "screening": "detection",
        "monitoring": "detection",
        "collusion": "coordination",
        "cartel": "coordination",
        "covert": "hidden",
        "channel": "communication",
    }

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        expanded = [" ".join(self.SYNONYMS.get(token, token) for token in tokenize(text)) for text in texts]
        return [_normalize(_hashed_vector(text, self.dimensions)) for text in expanded]


class ProviderEmbeddingClient:
    """Placeholder for future provider-backed embeddings.

    Tests and default workflows must not instantiate this client.
    """

    model_name = "provider-placeholder"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Provider embeddings are not configured. Use LocalHashEmbeddingClient or FakeEmbeddingClient.")


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, dot / (left_norm * right_norm))


def _hashed_vector(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return vector


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
