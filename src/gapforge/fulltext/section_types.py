"""Section heading normalization for parsed research papers."""

from __future__ import annotations

import re

SECTION_TYPES = {
    "abstract",
    "introduction",
    "related_work",
    "method",
    "experiments",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "appendix",
    "unknown",
}

_HEADING_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("abstract", ("abstract",)),
    ("introduction", ("introduction", "overview")),
    ("related_work", ("related work", "background", "prior work", "literature review")),
    ("method", ("method", "methods", "methodology", "approach", "model", "framework", "algorithm")),
    ("experiments", ("experiment", "experiments", "experimental setup", "evaluation", "empirical evaluation")),
    ("results", ("results", "findings")),
    ("discussion", ("discussion", "analysis")),
    ("limitations", ("limitation", "limitations", "threats to validity")),
    ("conclusion", ("conclusion", "conclusions", "future work")),
    ("appendix", ("appendix", "supplementary material", "supplemental material")),
]


def normalize_heading(title: str) -> str:
    clean = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+|[A-Z])\.?\s+", "", title.strip(), flags=re.IGNORECASE)
    clean = re.sub(r"[^A-Za-z0-9]+", " ", clean).strip().lower()
    return clean


def classify_section_title(title: str) -> str:
    normalized = normalize_heading(title)
    if not normalized:
        return "unknown"
    for section_type, patterns in _HEADING_PATTERNS:
        if any(normalized == pattern or normalized.startswith(f"{pattern} ") for pattern in patterns):
            return section_type
    return "unknown"
