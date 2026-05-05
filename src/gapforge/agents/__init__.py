"""Agent-client adapters for optional Codex/GPT-5.4 research runs."""

from gapforge.agents.base import AgentClient, AgentRuntimeConfig, AgentUnavailableError, agent_capabilities, agent_status
from gapforge.agents.codex import CodexAgentClient
from gapforge.agents.codex_runner import CodexRunner
from gapforge.agents.fake import FakeAgentClient
from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.task_packs import write_codex_task_pack
from gapforge.agents.task_spec import create_agent_task_spec
from gapforge.agents.validation import actual_run_status, create_actual_run_attestation, validate_agent_outputs

__all__ = [
    "AgentClient",
    "AgentRuntimeConfig",
    "AgentUnavailableError",
    "CodexAgentClient",
    "CodexRunner",
    "FakeAgentClient",
    "AgentOutputImporter",
    "agent_capabilities",
    "agent_status",
    "actual_run_status",
    "create_agent_task_spec",
    "create_actual_run_attestation",
    "validate_agent_outputs",
    "write_codex_task_pack",
]
