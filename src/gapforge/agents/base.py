"""Base interfaces for GapForge research agents.

AgentClient is intentionally separate from LLMClient. LLMClient handles single
text/JSON completions; AgentClient handles file-oriented research task packs,
manual/actual agent execution, validation, and safe import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from gapforge.models import AgentRunRecord, AgentTaskSpec, AgentValidationResult, ResearchRunState


class AgentUnavailableError(RuntimeError):
    """Raised when an optional real agent path is requested but unavailable."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeConfig:
    mode: str = "off"
    agent_name: str = "codex"
    codex_model: str = "gpt-5.4"
    enable_real_runs: bool = False
    output_dir: Path | None = None

    @classmethod
    def from_env(cls) -> AgentRuntimeConfig:
        mode = os.environ.get("GAPFORGE_AGENT_MODE", "off").strip().lower() or "off"
        if mode not in {"off", "task-pack", "fake", "codex"}:
            mode = "off"
        output_dir_raw = os.environ.get("GAPFORGE_AGENT_OUTPUT_DIR", "").strip()
        return cls(
            mode=mode,
            agent_name=os.environ.get("GAPFORGE_AGENT_NAME", "codex").strip() or "codex",
            codex_model=os.environ.get("GAPFORGE_CODEX_MODEL", "gpt-5.4").strip() or "gpt-5.4",
            enable_real_runs=os.environ.get("GAPFORGE_ENABLE_REAL_RUNS", "0").strip() in {"1", "true", "TRUE", "yes"},
            output_dir=Path(output_dir_raw).expanduser().resolve() if output_dir_raw else None,
        )

    @property
    def real_runs_enabled(self) -> bool:
        return self.mode == "codex" and self.enable_real_runs


class AgentClient(Protocol):
    def create_task_pack(self, state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
        """Write a file-oriented task pack and return its directory."""

    def run_task(self, task_spec: AgentTaskSpec) -> AgentRunRecord:
        """Run or prepare an agent task according to the configured mode."""

    def import_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        """Validate and import agent outputs. Research state changes require valid output."""

    def validate_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        """Validate output files without trusting model-generated claims."""


def agent_status(config: AgentRuntimeConfig | None = None) -> dict[str, object]:
    runtime = config or AgentRuntimeConfig.from_env()
    return {
        "mode": runtime.mode,
        "agent_name": runtime.agent_name,
        "codex_model": runtime.codex_model,
        "real_runs_enabled": runtime.enable_real_runs,
        "task_pack_available": runtime.mode in {"task-pack", "fake", "codex"},
        "codex_execution_available": runtime.real_runs_enabled,
        "output_dir": str(runtime.output_dir) if runtime.output_dir else "",
        "ci_safe": runtime.mode in {"off", "task-pack", "fake"},
    }
