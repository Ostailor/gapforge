"""Safe Codex/GPT-5.4 AgentClient adapter.

This adapter intentionally supports task-pack and validated-import workflows
without assuming a fragile Codex runtime API. Actual execution is opt-in and
must be enabled explicitly; otherwise Codex mode fails clearly.
"""

from __future__ import annotations

import subprocess
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
        if self.runtime.mode in {"task-pack", "manual-handoff"}:
            record = self._planned_record(task_spec, pack_dir, self.runtime.execution_method)
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record
        if not self.runtime.real_runs_enabled:
            raise AgentUnavailableError(
                "Codex actual runs require GAPFORGE_AGENT_MODE=direct or codex and GAPFORGE_ENABLE_REAL_RUNS=1. "
                "Use GAPFORGE_AGENT_MODE=task-pack or manual-handoff to create an external Codex handoff instead."
            )
        if self.runtime.runner_command:
            record = self._run_direct_runner(task_spec, pack_dir)
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record
        raise AgentUnavailableError(
            "Direct Codex execution is not configured in this GapForge build. "
            f"A task pack was written to {pack_dir}; rerun with GAPFORGE_AGENT_MODE=task-pack or manual-handoff, "
            "then import validated Codex outputs after external execution."
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
            usage_summary={
                "mode": mode,
                "execution_method": mode,
                "task_pack": str(pack_dir),
                "counts_as_actual_run": False,
                "requires_attestation": mode in {"task_pack", "manual_handoff"},
                "note": note,
            },
            provenance=Provenance(
                created_by_skill="codex-agent",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Prepared a Codex/GPT-5.4 task pack; research state awaits validated output import.",
            ),
        )

    def _run_direct_runner(self, task_spec: AgentTaskSpec, pack_dir: Path) -> AgentRunRecord:
        started_at = utc_now_iso()
        command = self.runtime.runner_command.format(
            task_pack=str(pack_dir),
            task_id=task_spec.id,
            run_id=task_spec.run_id,
            model=self.runtime.codex_model,
        )
        completed_at = ""
        try:
            result = subprocess.run(
                command,
                cwd=pack_dir,
                shell=True,
                text=True,
                capture_output=True,
                timeout=3600,
                check=False,
            )
            completed_at = utc_now_iso()
            status = "complete" if result.returncode == 0 else "failed"
            error = result.stderr[-2000:] if result.returncode else ""
            usage_summary = {
                "mode": "direct",
                "execution_method": "direct",
                "task_pack": str(pack_dir),
                "runner_command": command,
                "returncode": result.returncode,
                "stdout_preview": result.stdout[-2000:],
                "stderr_preview": result.stderr[-2000:],
                "counts_as_actual_run": result.returncode == 0,
                "requires_attestation": False,
            }
        except (OSError, subprocess.SubprocessError) as exc:
            completed_at = utc_now_iso()
            status = "failed"
            error = str(exc)
            usage_summary = {
                "mode": "direct",
                "execution_method": "direct",
                "task_pack": str(pack_dir),
                "runner_command": command,
                "counts_as_actual_run": False,
                "requires_attestation": False,
            }
        return AgentRunRecord(
            id=f"agent-run-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.runtime.agent_name,
            model=self.runtime.codex_model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            output_paths=[str(pack_dir / "TASK.md"), str(pack_dir / "task_spec.json")],
            error=error,
            usage_summary=usage_summary,
            provenance=Provenance(
                created_by_skill="codex-agent",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Attempted configured direct Codex/GPT-5.4 runner over a validation-gated task pack.",
            ),
        )
