"""Optional LLM extension points for GapForge skills.

The deterministic skills remain the default. This package provides prompt-pack
and fake-client adapters so future Codex or LLM-backed skills can be added
without making v0.2 depend on live model calls.
"""

from gapforge.llm.base import LLMClient, LLMResponse
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.prompt_pack import PromptPack, PromptPackBuilder, write_prompt_pack

__all__ = [
    "FakeLLMClient",
    "LLMClient",
    "LLMResponse",
    "PromptPack",
    "PromptPackBuilder",
    "write_prompt_pack",
]
