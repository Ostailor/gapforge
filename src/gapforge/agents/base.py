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

from gapforge.models import AgentRunRecord, AgentRuntimeCapability, AgentTaskSpec, AgentValidationResult, Provenance, ResearchRunState


class AgentUnavailableError(RuntimeError):
    """Raised when an optional real agent path is requested but unavailable."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeConfig:
    mode: str = "off"
    agent_name: str = "codex"
    codex_model: str = "gpt-5.4"
    enable_real_runs: bool = False
    output_dir: Path | None = None
    runner_command: str = ""
    codex_command: str = ""
    codex_workdir: Path | None = None
    codex_timeout_seconds: int = 3600

    @classmethod
    def from_env(cls) -> AgentRuntimeConfig:
        mode = os.environ.get("GAPFORGE_AGENT_MODE", "off").strip().lower() or "off"
        mode = _normalize_agent_mode(mode)
        if mode not in {"off", "task-pack", "manual-handoff", "fake", "codex", "direct"}:
            mode = "off"
        output_dir_raw = os.environ.get("GAPFORGE_AGENT_OUTPUT_DIR", "").strip()
        workdir_raw = os.environ.get("GAPFORGE_CODEX_WORKDIR", "").strip()
        timeout_raw = os.environ.get("GAPFORGE_CODEX_TIMEOUT_SECONDS", "").strip()
        legacy_command = os.environ.get("GAPFORGE_CODEX_RUNNER_CMD", "").strip()
        codex_command = os.environ.get("GAPFORGE_CODEX_COMMAND", legacy_command).strip()
        return cls(
            mode=mode,
            agent_name=os.environ.get("GAPFORGE_AGENT_NAME", "codex").strip() or "codex",
            codex_model=os.environ.get("GAPFORGE_CODEX_MODEL", os.environ.get("GAPFORGE_LLM_MODEL", "gpt-5.4")).strip() or "gpt-5.4",
            enable_real_runs=os.environ.get("GAPFORGE_ENABLE_REAL_RUNS", "0").strip() in {"1", "true", "TRUE", "yes"},
            output_dir=Path(output_dir_raw).expanduser().resolve() if output_dir_raw else None,
            runner_command=legacy_command,
            codex_command=codex_command,
            codex_workdir=Path(workdir_raw).expanduser().resolve() if workdir_raw else None,
            codex_timeout_seconds=_parse_timeout(timeout_raw),
        )

    @property
    def real_runs_enabled(self) -> bool:
        return self.mode in {"codex", "direct"} and self.enable_real_runs

    @property
    def direct_execution_available(self) -> bool:
        return self.enable_real_runs and bool(self.command_template)

    @property
    def command_template(self) -> str:
        return self.codex_command or self.runner_command

    @property
    def execution_method(self) -> str:
        if self.mode == "codex":
            return "direct"
        if self.mode == "task-pack":
            return "task_pack"
        if self.mode == "manual-handoff":
            return "manual_handoff"
        return self.mode


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
        "execution_method": runtime.execution_method,
        "agent_name": runtime.agent_name,
        "codex_model": runtime.codex_model,
        "real_runs_enabled": runtime.enable_real_runs,
        "task_pack_available": runtime.mode in {"task-pack", "manual-handoff", "fake", "codex", "direct"},
        "manual_handoff_available": True,
        "codex_execution_available": runtime.direct_execution_available,
        "runner_command_configured": bool(runtime.command_template),
        "codex_command_configured": bool(runtime.codex_command),
        "codex_workdir": str(runtime.codex_workdir) if runtime.codex_workdir else "",
        "codex_timeout_seconds": runtime.codex_timeout_seconds,
        "output_dir": str(runtime.output_dir) if runtime.output_dir else "",
        "ci_safe": runtime.mode in {"off", "task-pack", "manual-handoff", "fake"},
    }


def agent_capabilities(config: AgentRuntimeConfig | None = None) -> list[AgentRuntimeCapability]:
    runtime = config or AgentRuntimeConfig.from_env()
    provenance = Provenance(created_by_skill="agent-runtime-capabilities")
    direct_available = runtime.direct_execution_available
    return [
        AgentRuntimeCapability(
            mode="direct",
            available=direct_available,
            reason=(
                "Configured direct Codex runner is available."
                if direct_available
                else "Direct execution requires GAPFORGE_ENABLE_REAL_RUNS=1 and GAPFORGE_CODEX_COMMAND."
            ),
            required_env=[
                "GAPFORGE_ENABLE_REAL_RUNS=1",
                "GAPFORGE_AGENT_MODE=direct",
                "GAPFORGE_CODEX_COMMAND",
                "GAPFORGE_CODEX_RUNNER_CMD",
            ],
            command_template=runtime.command_template,
            can_count_as_actual_run=direct_available,
            provenance=provenance,
        ),
        AgentRuntimeCapability(
            mode="task_pack",
            available=True,
            reason="GapForge can write Codex task packs and validate imported outputs.",
            required_env=["GAPFORGE_AGENT_MODE=task-pack"],
            command_template="gapforge codex-task --run-id <run-id> --skill <skill>",
            can_count_as_actual_run=True,
            provenance=provenance,
        ),
        AgentRuntimeCapability(
            mode="manual_handoff",
            available=True,
            reason="Manual handoff uses task packs plus checklist-driven external Codex execution and validated import.",
            required_env=["GAPFORGE_AGENT_MODE=manual-handoff"],
            command_template="gapforge agent-run --task-id <task-id>",
            can_count_as_actual_run=True,
            provenance=provenance,
        ),
        AgentRuntimeCapability(
            mode="fake",
            available=True,
            reason="Fake agent is deterministic and CI-safe, but never counts as actual-run acceptance.",
            required_env=["GAPFORGE_AGENT_MODE=fake"],
            command_template="gapforge agent-run --task-id <task-id> --fake",
            can_count_as_actual_run=False,
            provenance=provenance,
        ),
    ]


def _normalize_agent_mode(mode: str) -> str:
    normalized = mode.strip().lower().replace("_", "-")
    if normalized in {"taskpack", "task-pack"}:
        return "task-pack"
    if normalized in {"manual", "manual-handoff"}:
        return "manual-handoff"
    return normalized


def _parse_timeout(raw: str) -> int:
    if not raw:
        return 3600
    try:
        timeout = int(raw)
    except ValueError:
        return 3600
    return max(1, timeout)
