"""Experiment execution record helpers."""

from __future__ import annotations

from pathlib import Path

from gapforge.models import ExperimentExecutionRecord, ExperimentRunManifest, ExperimentWorkspace, Provenance
from gapforge.state import slugify, utc_now_iso


def build_execution_record(
    workspace: ExperimentWorkspace,
    manifest: ExperimentRunManifest,
    *,
    status: str = "planned",
    sequence: int = 1,
    command: str = "",
    returncode: int | None = None,
    stdout_path: str = "",
    stderr_path: str = "",
    result_artifact_ids: list[str] | None = None,
    failure_reason: str = "",
) -> ExperimentExecutionRecord:
    now = utc_now_iso()
    started_at = now if status in {"running", "complete", "failed", "skipped"} else ""
    completed_at = now if status in {"complete", "failed", "skipped"} else ""
    return ExperimentExecutionRecord(
        id=f"execution-{slugify(workspace.id)}-{manifest.id}-{sequence}",
        workspace_id=workspace.id,
        manifest_id=manifest.id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        command=command or manifest.command,
        returncode=returncode,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        result_artifact_ids=result_artifact_ids or [],
        failure_reason=failure_reason,
        provenance=Provenance(
            created_by_skill="experiment-execution",
            source_ids=[workspace.id, manifest.id],
            timestamp=now,
            reasoning_summary=(
                "Recorded experiment execution status. Only complete records with result artifacts should support empirical claims."
            ),
        ),
    )


def render_execution_records_markdown(records: list[ExperimentExecutionRecord]) -> str:
    lines = ["# Experiment Runs", ""]
    if not records:
        lines.append("No experiment execution records yet.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        lines.extend(
            [
                f"## `{record.id}`",
                "",
                f"- Workspace ID: `{record.workspace_id}`",
                f"- Manifest ID: `{record.manifest_id}`",
                f"- Status: `{record.status}`",
                f"- Command: `{record.command or 'none'}`",
                f"- Return code: {record.returncode if record.returncode is not None else 'none'}",
                f"- Started: {record.started_at or 'unknown'}",
                f"- Completed: {record.completed_at or 'unknown'}",
                f"- Stdout: `{_display_path(record.stdout_path)}`",
                f"- Stderr: `{_display_path(record.stderr_path)}`",
                f"- Result artifacts: {', '.join(record.result_artifact_ids) or 'none'}",
                f"- Failure reason: {record.failure_reason or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _display_path(path: str) -> str:
    return str(Path(path)) if path else "none"
