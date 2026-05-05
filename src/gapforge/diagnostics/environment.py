"""Environment diagnostics for actual real-agent runs."""

from __future__ import annotations

from gapforge.agents.base import AgentRuntimeConfig
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.models import AgentEnvironmentStatus


def inspect_agent_environment() -> AgentEnvironmentStatus:
    """Summarize whether the current process is configured for real Codex runs."""

    agent_runtime = AgentRuntimeConfig.from_env()
    llm_runtime = LLMRuntimeConfig.from_env()
    missing_env: list[str] = []
    notes: list[str] = []

    if not agent_runtime.enable_real_runs:
        missing_env.append("GAPFORGE_ENABLE_REAL_RUNS=1")
    if agent_runtime.mode != "codex":
        missing_env.append("GAPFORGE_AGENT_MODE=codex")
    if not agent_runtime.agent_name:
        missing_env.append("GAPFORGE_AGENT_NAME=codex")
    if not agent_runtime.codex_model:
        missing_env.append("GAPFORGE_CODEX_MODEL=gpt-5.4")

    if agent_runtime.mode == "task-pack":
        notes.append("Task-pack mode can prepare a manual Codex handoff, but it is not direct actual-run execution.")
    elif agent_runtime.mode == "fake":
        notes.append("Fake-agent mode is CI-safe and validates integration, but it never counts as actual-run acceptance.")
    elif agent_runtime.mode == "off":
        notes.append("Agent mode is off; only deterministic and prompt-pack-free paths are active.")

    if llm_runtime.provider_enabled:
        notes.append("Provider LLM mode is enabled separately from the Codex AgentClient path.")
    if agent_runtime.codex_model != "gpt-5.4":
        notes.append(f"Codex model is configured as {agent_runtime.codex_model!r}; v0.3 acceptance docs expect gpt-5.4.")

    safe_to_execute = agent_runtime.real_runs_enabled and agent_runtime.agent_name == "codex" and bool(agent_runtime.codex_model)
    if safe_to_execute:
        notes.append("Environment permits a real Codex run attempt, but direct execution capability must still be checked.")

    return AgentEnvironmentStatus(
        real_runs_enabled=agent_runtime.enable_real_runs,
        agent_mode=agent_runtime.mode,
        agent_name=agent_runtime.agent_name,
        codex_model=agent_runtime.codex_model,
        provider_mode=llm_runtime.mode,
        required_env_present=not missing_env,
        missing_env=missing_env,
        safe_to_execute_real_agent=safe_to_execute,
        notes=notes,
    )
