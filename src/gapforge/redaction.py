"""Shared secret redaction helpers."""

from __future__ import annotations

import re

SECRET_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|authorization|openai_api_key)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}['\"]?"),
]


def redact_text(text: str) -> str:
    """Redact common API keys, bearer tokens, and credential assignments."""

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(_redaction, redacted)
    return redacted


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _redaction(match: re.Match[str]) -> str:
    text = match.group(0)
    if "=" in text:
        return f"{text.split('=', 1)[0]}=[REDACTED]"
    if ":" in text and not text.lower().startswith("bearer"):
        return f"{text.split(':', 1)[0]}: [REDACTED]"
    return "[REDACTED]"
