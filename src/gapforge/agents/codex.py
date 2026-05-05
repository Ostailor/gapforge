"""Safe Codex/GPT-5.4 AgentClient adapter.

This adapter intentionally supports task-pack and validated-import workflows
without assuming a fragile Codex runtime API. Actual execution is opt-in and
must be enabled explicitly; otherwise Codex mode fails clearly.
"""

from __future__ import annotations

from pathlib import Path

from gapforge.agents.base import AgentRuntimeConfig, AgentUnavailableError
from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.records import append_run_record, utc_now_iso, write_task_pack
from gapforge.config import GapForgeConfig
from gapforge.models import AgentRunRecord, AgentTaskSpec, AgentValidationResult, Provenance, ResearchRunState
from gapforge.state import ResearchStateManager, utc_now_compact


class CodexAgentClient:
    """Task-pack/import adapter for actual Codex/GPT-5.4 research runs."""

    def __init__(self, config: GapForgeConfig, runtime: AgentRuntimeConfig | None = None) -> None:
        self.config = config
        self.runtime = runtime or AgentRuntimeConfig.from_env()
        self.state_manager = ResearchStateManager(config)

    def create_task_pack(self, state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
        return write_task_pack(state, task_spec)

    def run_task(self, task_spec: AgentTaskSpec) -> AgentRunRecord:
        state = self.state_manager.load_run(task_spec.run_id)
        pack_dir = self.create_task_pack(state, task_spec)
        if self.runtime.mode == "task-pack":
            record = self._planned_record(task_spec, pack_dir, "task-pack")
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record
        if not self.runtime.real_runs_enabled:
            raise AgentUnavailableError(
                "Codex actual runs require GAPFORGE_AGENT_MODE=codex and GAPFORGE_ENABLE_REAL_RUNS=1. "
                "Use GAPFORGE_AGENT_MODE=task-pack to create a manual task pack instead."
            )
        raise AgentUnavailableError(
            "Direct Codex execution is not configured in this GapForge build. "
            f"A task pack was written to {pack_dir}; rerun with GAPFORGE_AGENT_MODE=task-pack "
            "or import Codex outputs after manual execution."
        )

    def import_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        return AgentOutputImporter(self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model).import_outputs(
            task_spec, output_paths
        )

    def validate_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        return AgentOutputImporter(self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model).validate(
            task_spec, output_paths
        )

    def _planned_record(self, task_spec: AgentTaskSpec, pack_dir: Path, mode: str, note: str = "") -> AgentRunRecord:
        return AgentRunRecord(
            id=f"agent-run-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.runtime.agent_name,
            model=self.runtime.codex_model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="planned",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=[str(pack_dir / "TASK.md"), str(pack_dir / "task_spec.json")],
            usage_summary={"mode": mode, "task_pack": str(pack_dir), "note": note},
            provenance=Provenance(
                created_by_skill="codex-agent",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Prepared a Codex/GPT-5.4 task pack; research state awaits validated output import.",
            ),
        )
