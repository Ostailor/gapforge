"""Agent-client adapters for optional Codex/GPT-5.4 research runs."""

from gapforge.agents.base import AgentClient, AgentRuntimeConfig, AgentUnavailableError, agent_status
from gapforge.agents.codex import CodexAgentClient
from gapforge.agents.fake import FakeAgentClient
from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.task_packs import write_codex_task_pack
from gapforge.agents.task_spec import create_agent_task_spec
from gapforge.agents.validation import validate_agent_outputs

__all__ = [
    "AgentClient",
    "AgentRuntimeConfig",
    "AgentUnavailableError",
    "CodexAgentClient",
    "FakeAgentClient",
    "AgentOutputImporter",
    "agent_status",
    "create_agent_task_spec",
    "validate_agent_outputs",
    "write_codex_task_pack",
]
