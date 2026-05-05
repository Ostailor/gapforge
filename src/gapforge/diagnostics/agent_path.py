"""Agent path diagnostics for Codex/GPT-5.4 actual-run readiness."""

from __future__ import annotations

from gapforge.agents.base import AgentRuntimeConfig
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.models import AgentPathStatus


def inspect_agent_path() -> AgentPathStatus:
    """Inspect available AgentClient paths without starting a real agent."""

    agent_runtime = AgentRuntimeConfig.from_env()
    llm_runtime = LLMRuntimeConfig.from_env()
    task_pack_available = True
    manual_import_available = True
    fake_agent_available = True
    provider_llm_available = llm_runtime.provider_enabled

    failure_reason = (
        "Direct Codex execution is not implemented in the v0.3 CodexAgentClient; "
        "the safe supported actual-run path is task-pack handoff plus validated import."
    )
    if agent_runtime.mode == "task-pack":
        recommended_path = "Use the manual Codex handoff: generate a task pack, run Codex/GPT-5.4 manually, then validate and import."
    elif agent_runtime.mode == "fake":
        recommended_path = "Use fake-agent mode for CI regression only; switch to task-pack or codex mode for real validation."
    elif agent_runtime.real_runs_enabled:
        recommended_path = (
            "Real execution was requested, but direct execution is unavailable; use task-pack/import until v0.4 adds execution."
        )
    else:
        recommended_path = (
            "Set GAPFORGE_AGENT_MODE=task-pack for a manual Codex handoff, or enable codex mode once direct execution exists."
        )

    return AgentPathStatus(
        direct_execution_available=False,
        task_pack_available=task_pack_available,
        manual_import_available=manual_import_available,
        fake_agent_available=fake_agent_available,
        provider_llm_available=provider_llm_available,
        failure_reason=failure_reason,
        recommended_path=recommended_path,
    )
