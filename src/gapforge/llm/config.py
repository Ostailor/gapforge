"""Configuration for optional LLM-backed GapForge skills."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    mode: str = "off"
    provider: str = "openai"
    model: str = ""
    max_tokens: int | None = None
    budget_usd: float | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> LLMRuntimeConfig:
        mode = os.environ.get("GAPFORGE_LLM_MODE", "off").strip().lower() or "off"
        if mode not in {"off", "prompt-pack", "fake", "provider"}:
            mode = "off"
        provider = os.environ.get("GAPFORGE_LLM_PROVIDER", "openai").strip().lower() or "openai"
        if provider not in {"openai", "custom"}:
            provider = "custom"
        return cls(
            mode=mode,
            provider=provider,
            model=os.environ.get("GAPFORGE_LLM_MODEL", "").strip(),
            max_tokens=_optional_int(os.environ.get("GAPFORGE_LLM_MAX_TOKENS")),
            budget_usd=_optional_float(os.environ.get("GAPFORGE_LLM_BUDGET_USD")),
            timeout_seconds=_optional_float(os.environ.get("GAPFORGE_LLM_TIMEOUT_SECONDS")) or 30.0,
        )

    @property
    def provider_enabled(self) -> bool:
        return self.mode == "provider"


def _optional_int(raw: str | None) -> int | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _optional_float(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0 else None
