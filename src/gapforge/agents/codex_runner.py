"""v0.4 Codex/GPT-5.4 execution runner.

The runner supports an opt-in direct command adapter and an explicit handoff
path. Both routes produce task packs; direct output is still validated before
it is allowed to mutate research state.
"""

from __future__ import annotations

from pathlib import Path

from gapforge.agents.base import AgentRuntimeConfig, AgentUnavailableError
from gapforge.agents.codex import CodexAgentClient
from gapforge.agents.command_runner import CommandRunResult, run_command_template
from gapforge.agents.handoff import write_handoff
from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.records import append_run_record, append_validation_result, output_dir_for_task, utc_now_iso
from gapforge.config import GapForgeConfig
from gapforge.models import AgentRunRecord, AgentTaskSpec, Provenance, ResearchRunState
from gapforge.state import ResearchStateManager, utc_now_compact


class CodexRunner:
    """Run a Codex task pack directly when configured, otherwise write handoff instructions."""

    def __init__(self, config: GapForgeConfig, runtime: AgentRuntimeConfig | None = None) -> None:
        self.config = config
        self.runtime = runtime or AgentRuntimeConfig.from_env()
        self.state_manager = ResearchStateManager(config)

    def direct_available(self) -> bool:
        return self.runtime.direct_execution_available

    def run(
        self,
        task_spec: AgentTaskSpec,
        *,
        prefer_direct: bool = False,
        handoff: bool = False,
        require_direct: bool = False,
    ) -> AgentRunRecord:
        state = self.state_manager.load_run(task_spec.run_id)
        pack_dir = CodexAgentClient(
            self.config, AgentRuntimeConfig(mode="task-pack", codex_model=self.runtime.codex_model)
        ).create_task_pack(state, task_spec)
        outputs_dir = output_dir_for_task(state, task_spec)

        if handoff:
            return self._record_handoff(state, task_spec, pack_dir, reason="Handoff mode was requested explicitly.")

        if require_direct and not self.direct_available():
            raise AgentUnavailableError(self._direct_unavailable_message())

        if self.direct_available() or prefer_direct:
            if not self.direct_available():
                return self._record_handoff(state, task_spec, pack_dir, reason=self._direct_unavailable_message())
            return self._run_direct(task_spec, state, pack_dir, outputs_dir)

        return self._record_handoff(state, task_spec, pack_dir, reason="No direct Codex command is configured.")

    def status(self, agent_run_id: str) -> AgentRunRecord:
        for run_dir in sorted(self.config.runs_dir.glob("*"), reverse=True):
            if not run_dir.is_dir():
                continue
            try:
                state = self.state_manager.load_run(run_dir.name)
            except (FileNotFoundError, ValueError):
                continue
            for record in state.agent_run_records:
                if record.id == agent_run_id:
                    return record
        raise FileNotFoundError(f"No agent run record found for {agent_run_id}")

    def _run_direct(self, task_spec: AgentTaskSpec, state: ResearchRunState, pack_dir: Path, outputs_dir: Path) -> AgentRunRecord:
        started_at = utc_now_iso()
        command_result = run_command_template(
            self.runtime.command_template,
            task_pack=pack_dir,
            outputs_dir=outputs_dir,
            task_id=task_spec.id,
            run_id=task_spec.run_id,
            model=self.runtime.codex_model,
            cwd=self.runtime.codex_workdir or pack_dir,
            timeout_seconds=self.runtime.codex_timeout_seconds,
        )
        if not command_result.succeeded:
            record = self._direct_record(
                task_spec,
                started_at=started_at,
                completed_at=utc_now_iso(),
                command_result=command_result,
                status="failed",
                error=command_result.error or command_result.stderr[-2000:] or f"Codex command exited {command_result.returncode}.",
                output_paths=_existing_outputs(outputs_dir),
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record

        validation = AgentOutputImporter(self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model).validate(
            task_spec, []
        )
        if validation.status != "valid":
            state = self.state_manager.load_run(task_spec.run_id)
            append_validation_result(state, validation)
            record = self._direct_record(
                task_spec,
                started_at=started_at,
                completed_at=utc_now_iso(),
                command_result=command_result,
                status="failed",
                error="Output validation failed: " + "; ".join(validation.issues),
                output_paths=validation.rejected_output_paths or _existing_outputs(outputs_dir),
                validation_result_id=validation.id,
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record

        imported_validation = AgentOutputImporter(
            self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model
        ).import_outputs(task_spec, [])
        state = self.state_manager.load_run(task_spec.run_id)
        record = self._direct_record(
            task_spec,
            started_at=started_at,
            completed_at=utc_now_iso(),
            command_result=command_result,
            status="complete",
            error="",
            output_paths=imported_validation.accepted_output_paths,
            validation_result_id=imported_validation.id,
        )
        append_run_record(state, record)
        self.state_manager.save_run(state)
        return record

    def _record_handoff(self, state: ResearchRunState, task_spec: AgentTaskSpec, pack_dir: Path, *, reason: str) -> AgentRunRecord:
        handoff_path = write_handoff(task_spec, pack_dir, model=self.runtime.codex_model)
        record = AgentRunRecord(
            id=f"codex-handoff-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.runtime.agent_name,
            model=self.runtime.codex_model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="planned",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=[str(pack_dir / "TASK.md"), str(handoff_path), str(pack_dir / "outputs")],
            usage_summary={
                "mode": "handoff",
                "execution_method": "manual_handoff",
                "task_pack": str(pack_dir),
                "handoff_path": str(handoff_path),
                "direct_available": self.direct_available(),
                "counts_as_actual_run": False,
                "requires_attestation": True,
                "requires_validated_import": True,
                "reason": reason,
            },
            provenance=Provenance(
                created_by_skill="codex-runner",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Prepared an explicit Codex/GPT-5.4 handoff because direct execution was not used.",
            ),
        )
        append_run_record(state, record)
        self.state_manager.save_run(state)
        return record

    def _direct_record(
        self,
        task_spec: AgentTaskSpec,
        *,
        started_at: str,
        completed_at: str,
        command_result: CommandRunResult,
        status: str,
        error: str,
        output_paths: list[str],
        validation_result_id: str = "",
    ) -> AgentRunRecord:
        return AgentRunRecord(
            id=f"codex-direct-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.runtime.agent_name,
            model=self.runtime.codex_model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            output_paths=output_paths,
            validation_result_id=validation_result_id,
            error=error,
            usage_summary={
                "mode": "direct",
                "execution_method": "direct",
                "runner_command": command_result.command,
                "cwd": command_result.cwd,
                "returncode": command_result.returncode,
                "timed_out": command_result.timed_out,
                "duration_seconds": round(command_result.duration_seconds, 3),
                "stdout_preview": command_result.stdout[-2000:],
                "stderr_preview": command_result.stderr[-2000:],
                "counts_as_actual_run": status == "complete",
                "requires_attestation": False,
                "requires_validated_import": True,
            },
            provenance=Provenance(
                created_by_skill="codex-runner",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Ran an explicitly configured Codex/GPT-5.4 command over a validation-gated task pack.",
            ),
        )

    def _direct_unavailable_message(self) -> str:
        return (
            "Direct Codex execution is unavailable. Set GAPFORGE_ENABLE_REAL_RUNS=1, "
            "GAPFORGE_AGENT_MODE=direct or codex, and GAPFORGE_CODEX_COMMAND with a command template that writes outputs "
            "to {outputs_dir}. Use `gapforge codex-run --task-id <id> --handoff` for task-pack handoff instead."
        )


def _existing_outputs(outputs_dir: Path) -> list[str]:
    if not outputs_dir.exists():
        return []
    return [str(path) for path in sorted(outputs_dir.iterdir()) if path.is_file()]
