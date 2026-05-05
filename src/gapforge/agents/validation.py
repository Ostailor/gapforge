"""Backward-compatible validation entrypoint for AgentClient implementations."""

from __future__ import annotations

from pathlib import Path

from gapforge.agents.schema_validator import validate_task_outputs
from gapforge.models import AgentTaskSpec, AgentValidationResult, ResearchRunState


def validate_agent_outputs(state: ResearchRunState, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
    return validate_task_outputs(state, task_spec, output_paths)
