"""v0.4 Codex/GPT-5.4 execution runner.

The runner supports an opt-in direct command adapter and an explicit handoff
path. Both routes produce task packs; direct output is still validated before
it is allowed to mutate research state.
"""

from __future__ import annotations

from pathlib import Path

from gapforge.agents.base import AgentRuntimeConfig, AgentUnavailableError
from gapforge.agents.codex import CodexAgentClient
from gapforge.agents.command_runner import (
    CommandRunResult,
    render_codex_command_template,
    run_command_template,
    validate_codex_command_template,
)
from gapforge.agents.handoff import write_handoff
from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.records import append_run_record, append_validation_result, output_dir_for_task, utc_now_iso
from gapforge.agents.schema_validator import expected_output_files
from gapforge.config import GapForgeConfig
from gapforge.models import AgentRunRecord, AgentTaskSpec, Provenance, ResearchRunState
from gapforge.redaction import redact_text
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
        dry_run: bool = False,
        allow_unknown_placeholders: bool = False,
    ) -> AgentRunRecord:
        state = self.state_manager.load_run(task_spec.run_id)
        pack_dir = CodexAgentClient(
            self.config, AgentRuntimeConfig(mode="task-pack", codex_model=self.runtime.codex_model)
        ).create_task_pack(state, task_spec)
        outputs_dir = self._outputs_dir(state, task_spec)

        if handoff:
            return self._record_handoff(state, task_spec, pack_dir, reason="Handoff mode was requested explicitly.")

        if require_direct and not self.direct_available():
            raise AgentUnavailableError(self._direct_unavailable_message())

        if dry_run:
            return self._record_direct_preview(
                state,
                task_spec,
                pack_dir,
                outputs_dir,
                allow_unknown_placeholders=allow_unknown_placeholders,
            )

        if self.direct_available() or prefer_direct:
            if not self.direct_available():
                return self._record_handoff(state, task_spec, pack_dir, reason=self._direct_unavailable_message())
            return self._run_direct(task_spec, state, pack_dir, outputs_dir, allow_unknown_placeholders=allow_unknown_placeholders)

        return self._record_handoff(state, task_spec, pack_dir, reason="No direct Codex command is configured.")

    def preview(self, task_spec: AgentTaskSpec, *, allow_unknown_placeholders: bool = False) -> dict[str, object]:
        state = self.state_manager.load_run(task_spec.run_id)
        pack_dir = CodexAgentClient(
            self.config, AgentRuntimeConfig(mode="task-pack", codex_model=self.runtime.codex_model)
        ).create_task_pack(state, task_spec)
        outputs_dir = self._outputs_dir(state, task_spec)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_codex_command_template(
            self.runtime.command_template,
            task_pack=pack_dir,
            outputs_dir=outputs_dir,
            task_id=task_spec.id,
            run_id=task_spec.run_id,
            model=self.runtime.codex_model,
            allow_unknown_placeholders=allow_unknown_placeholders,
        )
        rendered_command = ""
        if self.runtime.command_template:
            try:
                rendered_command = render_codex_command_template(
                    self.runtime.command_template,
                    task_pack=pack_dir,
                    outputs_dir=outputs_dir,
                    task_id=task_spec.id,
                    run_id=task_spec.run_id,
                    model=self.runtime.codex_model,
                    allow_unknown_placeholders=allow_unknown_placeholders,
                )
            except ValueError as exc:
                rendered_command = str(exc)
        return {
            "task_id": task_spec.id,
            "run_id": task_spec.run_id,
            "cwd": str(self.runtime.codex_workdir or pack_dir),
            "task_pack": str(pack_dir),
            "outputs_dir": str(outputs_dir),
            "expected_output_files": expected_output_files(task_spec),
            "command_template_valid": validation.valid,
            "template_validation": {
                "valid": validation.valid,
                "missing_recommended_placeholders": validation.missing_recommended_placeholders,
                "unknown_placeholders": validation.unknown_placeholders,
                "shell_risk_warnings": validation.shell_risk_warnings,
                "rendered_preview": validation.rendered_preview,
                "notes": validation.notes,
            },
            "rendered_command": redact_text(rendered_command),
            "will_execute": False,
        }

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

    def _run_direct(
        self,
        task_spec: AgentTaskSpec,
        state: ResearchRunState,
        pack_dir: Path,
        outputs_dir: Path,
        *,
        allow_unknown_placeholders: bool = False,
    ) -> AgentRunRecord:
        started_at = utc_now_iso()
        template_validation = validate_codex_command_template(
            self.runtime.command_template,
            task_pack=pack_dir,
            outputs_dir=outputs_dir,
            task_id=task_spec.id,
            run_id=task_spec.run_id,
            model=self.runtime.codex_model,
            allow_unknown_placeholders=allow_unknown_placeholders,
        )
        if not template_validation.valid:
            command_result = CommandRunResult(
                command=template_validation.rendered_preview or redact_text(self.runtime.command_template),
                cwd=str(self.runtime.codex_workdir or pack_dir),
                returncode=-1,
                error="Invalid Codex command template: " + "; ".join(template_validation.notes + template_validation.unknown_placeholders),
            )
            record = self._direct_record(
                task_spec,
                started_at=started_at,
                completed_at=utc_now_iso(),
                command_result=command_result,
                status="failed",
                error=command_result.error,
                output_paths=_existing_outputs(outputs_dir),
                expected_output_files=expected_output_files(task_spec),
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record
        outputs_dir.mkdir(parents=True, exist_ok=True)
        command_result = run_command_template(
            self.runtime.command_template,
            task_pack=pack_dir,
            outputs_dir=outputs_dir,
            task_id=task_spec.id,
            run_id=task_spec.run_id,
            model=self.runtime.codex_model,
            cwd=self.runtime.codex_workdir or pack_dir,
            timeout_seconds=self.runtime.codex_timeout_seconds,
            allow_unknown_placeholders=allow_unknown_placeholders,
        )
        expected_files = expected_output_files(task_spec)
        actual_outputs = _existing_outputs(outputs_dir)
        if not command_result.succeeded:
            record = self._direct_record(
                task_spec,
                started_at=started_at,
                completed_at=utc_now_iso(),
                command_result=command_result,
                status="failed",
                error=command_result.error or command_result.stderr[-2000:] or f"Codex command exited {command_result.returncode}.",
                output_paths=actual_outputs,
                expected_output_files=expected_files,
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record
        if not _any_expected_output_exists(outputs_dir, expected_files):
            record = self._direct_record(
                task_spec,
                started_at=started_at,
                completed_at=utc_now_iso(),
                command_result=command_result,
                status="failed",
                error=(
                    f"Codex command completed but did not write expected outputs to {outputs_dir}. "
                    f"Expected files: {', '.join(expected_files)}. "
                    f"Run fallback: gapforge codex-handoff --task-id {task_spec.id}"
                ),
                output_paths=actual_outputs,
                expected_output_files=expected_files,
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record

        output_paths_for_validation = [outputs_dir / filename for filename in expected_files]
        validation = AgentOutputImporter(self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model).validate(
            task_spec, output_paths_for_validation
        )
        if validation.status not in {"valid", "warning"}:
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
                expected_output_files=expected_files,
            )
            append_run_record(state, record)
            self.state_manager.save_run(state)
            return record

        imported_validation = AgentOutputImporter(
            self.config, agent_name=self.runtime.agent_name, model=self.runtime.codex_model
        ).import_outputs(task_spec, output_paths_for_validation)
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
            expected_output_files=expected_files,
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
        expected_output_files: list[str] | None = None,
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
                "outputs_dir": str(self._raw_outputs_dir(task_spec)),
                "expected_output_files": expected_output_files or [],
                "actual_output_files": output_paths,
                "handoff_fallback_command": f"gapforge codex-handoff --task-id {task_spec.id}",
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

    def _record_direct_preview(
        self,
        state: ResearchRunState,
        task_spec: AgentTaskSpec,
        pack_dir: Path,
        outputs_dir: Path,
        *,
        allow_unknown_placeholders: bool = False,
    ) -> AgentRunRecord:
        preview = self.preview(task_spec, allow_unknown_placeholders=allow_unknown_placeholders)
        record = AgentRunRecord(
            id=f"codex-direct-preview-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.runtime.agent_name,
            model=self.runtime.codex_model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="planned",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=[str(pack_dir), str(outputs_dir)],
            usage_summary={"mode": "direct-dry-run", **preview},
            provenance=Provenance(
                created_by_skill="codex-runner",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Rendered a direct Codex command preview without executing it.",
            ),
        )
        append_run_record(state, record)
        self.state_manager.save_run(state)
        return record

    def _outputs_dir(self, state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
        return self.runtime.codex_outputs_dir or output_dir_for_task(state, task_spec)

    def _raw_outputs_dir(self, task_spec: AgentTaskSpec) -> Path:
        if self.runtime.codex_outputs_dir is not None:
            return self.runtime.codex_outputs_dir
        state = self.state_manager.load_run(task_spec.run_id)
        return output_dir_for_task(state, task_spec)


def _existing_outputs(outputs_dir: Path) -> list[str]:
    if not outputs_dir.exists():
        return []
    return [str(path) for path in sorted(outputs_dir.iterdir()) if path.is_file()]


def _any_expected_output_exists(outputs_dir: Path, expected_files: list[str]) -> bool:
    return any((outputs_dir / filename).exists() for filename in expected_files)
