"""Deterministic lexical retrieval with a BM25-like scorer."""

from __future__ import annotations

import math
import re
from collections import Counter

from gapforge.models import RetrievalDocument

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "under",
    "using",
    "paper",
    "study",
    "their",
    "there",
    "where",
    "which",
    "should",
}


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in STOP_WORDS]


class LexicalRetriever:
    """Small BM25-style retriever with no external dependencies."""

    def __init__(self, documents: list[RetrievalDocument]) -> None:
        self.documents = documents
        self.doc_tokens = [tokenize(f"{doc.title} {doc.text}") for doc in documents]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = sum(self.doc_lengths) / max(1, len(self.doc_lengths))
        self.document_frequency = self._document_frequency()

    def score(self, query: str) -> dict[str, float]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return {doc.id: 0.0 for doc in self.documents}
        scores: dict[str, float] = {}
        for doc, tokens, length in zip(self.documents, self.doc_tokens, self.doc_lengths, strict=True):
            counts = Counter(tokens)
            raw = 0.0
            for token in query_tokens:
                if token not in counts:
                    continue
                raw += self._idf(token) * self._term_score(counts[token], length)
            scores[doc.id] = raw
        return _normalize(scores)

    def _document_frequency(self) -> dict[str, int]:
        frequencies: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            frequencies.update(set(tokens))
        return dict(frequencies)

    def _idf(self, token: str) -> float:
        doc_count = max(1, len(self.documents))
        frequency = self.document_frequency.get(token, 0)
        return math.log(1 + (doc_count - frequency + 0.5) / (frequency + 0.5))

    def _term_score(self, count: int, doc_length: int) -> float:
        k1 = 1.4
        b = 0.75
        denom = count + k1 * (1 - b + b * doc_length / max(1.0, self.avg_doc_length))
        return count * (k1 + 1) / max(denom, 1e-9)


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 0.0
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}
