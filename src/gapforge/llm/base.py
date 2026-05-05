"""Protocol definitions for optional LLM-backed GapForge skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str = "unknown"
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Minimal client interface for future LLM-backed skills."""

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Return a text completion. Implementations may be local, fake, or remote."""

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object matching the named GapForge schema."""
