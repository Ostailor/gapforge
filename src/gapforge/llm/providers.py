"""Optional provider-backed LLM adapter."""

from __future__ import annotations

import importlib
import importlib.util
import os
import uuid
from pathlib import Path
from typing import Any

from gapforge.llm.base import LLMResponse
from gapforge.llm.budget import LLMBudgetTracker
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.json_guard import JSONGuard
from gapforge.llm.transcripts import LLMTranscriptLogger


class ProviderUnavailableError(RuntimeError):
    """Raised when provider mode is requested but unavailable."""


class ProviderLLMClient:
    """Small provider adapter behind the LLMClient protocol."""

    def __init__(
        self,
        *,
        config: LLMRuntimeConfig | None = None,
        run_dir: str | Path | None = None,
        skill_name: str = "unknown",
        prompt_pack_id: str = "",
    ) -> None:
        self.config = config or LLMRuntimeConfig.from_env()
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.skill_name = skill_name
        self.prompt_pack_id = prompt_pack_id
        self.model = self.config.model or _default_model(self.config.provider)
        self.budget = LLMBudgetTracker(self.run_dir, config=self.config)
        self.transcripts = LLMTranscriptLogger(self.run_dir)

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        call_id = f"llm-{uuid.uuid4().hex[:12]}"
        try:
            response = self._complete_provider(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
            summary = "Provider response recorded. Output remains untrusted until schema/citation validation passes."
            self.budget.record(call_id, prompt, response)
            usage_payload = self.budget.to_dict()
            self.transcripts.record(
                call_id=call_id,
                skill_name=self.skill_name,
                prompt_pack_id=self.prompt_pack_id,
                model=response.model,
                response_status="ok",
                prompt=prompt,
                response=response,
                reasoning_summary=summary,
                usage=usage_payload,
            )
            return response
        except Exception as exc:
            failure = LLMResponse(text="", model=self.model, usage={"prompt_chars": len(prompt)}, raw={"error": str(exc)})
            self.transcripts.record(
                call_id=call_id,
                skill_name=self.skill_name,
                prompt_pack_id=self.prompt_pack_id,
                model=self.model,
                response_status="failed",
                prompt=prompt,
                response=failure,
                reasoning_summary="Provider call failed gracefully; no state should be updated from this response.",
            )
            if isinstance(exc, ProviderUnavailableError):
                raise
            raise ProviderUnavailableError(str(exc)) from exc

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        response = self.complete(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        return (
            JSONGuard()
            .parse_and_validate(
                response.text,
                schema_name=schema_name,
                repair_client=self,
                repair_prompt=prompt,
                provider_mode=True,
            )
            .data
        )

    def _complete_provider(
        self,
        prompt: str,
        *,
        system: str,
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        if self.config.provider == "openai":
            return self._complete_openai(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        if self.config.provider == "custom":
            raise ProviderUnavailableError("Custom LLM provider is not configured. Implement a project-specific adapter.")
        raise ProviderUnavailableError(f"Unsupported LLM provider: {self.config.provider}")

    def _complete_openai(
        self,
        prompt: str,
        *,
        system: str,
        temperature: float,
        max_tokens: int | None,
    ) -> LLMResponse:
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderUnavailableError("OPENAI_API_KEY is not set; provider mode is unavailable.")
        try:
            openai_module = importlib.import_module("openai")
        except ImportError as exc:
            raise ProviderUnavailableError("The openai package is not installed; provider mode is unavailable.") from exc
        client_cls = getattr(openai_module, "OpenAI", None)
        if client_cls is None:
            raise ProviderUnavailableError("Installed openai package does not expose OpenAI client.")
        client = client_cls(timeout=self.config.timeout_seconds)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        token_limit = max_tokens or self.config.max_tokens
        if token_limit:
            create_kwargs["max_tokens"] = token_limit
        result = client.chat.completions.create(**create_kwargs)
        choice = result.choices[0]
        text = choice.message.content or ""
        usage = _usage_to_dict(getattr(result, "usage", None))
        usage.setdefault("prompt_chars", len(prompt) + len(system))
        usage.setdefault("completion_chars", len(text))
        return LLMResponse(text=text, model=self.model, usage=usage, raw={"provider": "openai"})


def client_from_config(
    *,
    config: LLMRuntimeConfig | None = None,
    run_dir: str | Path | None = None,
    skill_name: str = "unknown",
    prompt_pack_id: str = "",
):
    runtime = config or LLMRuntimeConfig.from_env()
    if runtime.mode == "fake":
        return FakeLLMClient()
    if runtime.mode == "provider":
        return ProviderLLMClient(config=runtime, run_dir=run_dir, skill_name=skill_name, prompt_pack_id=prompt_pack_id)
    raise ProviderUnavailableError(f"LLM mode {runtime.mode!r} does not create a live client.")


def llm_status(config: LLMRuntimeConfig | None = None) -> dict[str, Any]:
    runtime = config or LLMRuntimeConfig.from_env()
    status: dict[str, Any] = {
        "mode": runtime.mode,
        "provider": runtime.provider,
        "model": runtime.model or _default_model(runtime.provider),
        "max_tokens": runtime.max_tokens,
        "budget_usd": runtime.budget_usd,
        "timeout_seconds": runtime.timeout_seconds,
        "provider_ready": False,
        "warnings": [],
    }
    if runtime.mode != "provider":
        return status
    if runtime.provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            status["warnings"].append("OPENAI_API_KEY is not set.")
        if importlib.util.find_spec("openai") is None:
            status["warnings"].append("The openai package is not installed.")
        status["provider_ready"] = not status["warnings"]
    else:
        status["warnings"].append("Custom provider requires a project-specific adapter.")
    return status


def _default_model(provider: str) -> str:
    return "gpt-4o-mini" if provider == "openai" else "custom-model"


def _usage_to_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    result: dict[str, int] = {}
    for source, target in [
        ("prompt_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
        ("input_tokens", "prompt_tokens"),
        ("output_tokens", "completion_tokens"),
    ]:
        value = getattr(usage, source, None)
        if value is not None:
            result[target] = int(value)
    return result
