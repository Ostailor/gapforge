"""Optional LLM extension points for GapForge skills.

The deterministic skills remain the default. This package provides prompt-pack
and fake-client adapters so future Codex or LLM-backed skills can be added
without making v0.2 depend on live model calls.
"""

from gapforge.llm.base import LLMClient, LLMResponse
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.prompt_pack import PromptPack, PromptPackBuilder, write_prompt_pack
from gapforge.llm.providers import ProviderLLMClient, ProviderUnavailableError, client_from_config, llm_status

__all__ = [
    "FakeLLMClient",
    "LLMClient",
    "LLMResponse",
    "LLMRuntimeConfig",
    "PromptPack",
    "PromptPackBuilder",
    "ProviderLLMClient",
    "ProviderUnavailableError",
    "client_from_config",
    "llm_status",
    "write_prompt_pack",
]
