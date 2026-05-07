"""Execute experiment manifests and record artifact-backed run state."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.compute.resources import resource_request_is_default, validate_resource_request
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentExecutionRecord, ExperimentRunManifest, ExperimentWorkspace
from gapforge.redaction import redact_text


@dataclass(slots=True)
class ExperimentRunResult:
    execution: ExperimentExecutionRecord
    missing_outputs: list[str] = field(default_factory=list)
    detected_outputs: list[str] = field(default_factory=list)
    dry_run: bool = False
    timed_out: bool = False


class ExperimentRunner:
    """Run commands from experiment manifests without fabricating outputs."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def run(
        self,
        *,
        workspace_id: str,
        manifest_id: str = "",
        run_type: str = "",
        timeout_seconds: int = 300,
        dry_run: bool = False,
    ) -> ExperimentRunResult:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        manifest = self._select_manifest(workspace, manifest_id=manifest_id, run_type=run_type)
        command = manifest.command
        resource_check = _validate_manifest_resources(manifest)
        if dry_run:
            record = self.workspace_manager.record_execution(
                workspace_id=workspace.id,
                manifest_id=manifest.id,
                status="skipped",
                command=redact_text(command),
                stdout_text=redact_text(f"Dry run only. Would execute from {workspace.root_dir}: {command}\n"),
                stderr_text="",
                failure_reason="Dry run; command was not executed.",
            )
            return ExperimentRunResult(execution=record, dry_run=True)
        if resource_check.status != "available":
            failure_reason = _resource_failure_reason(resource_check)
            record = self.workspace_manager.record_execution(
                workspace_id=workspace.id,
                manifest_id=manifest.id,
                status="failed",
                command=redact_text(command),
                stdout_text="",
                stderr_text=redact_text(failure_reason + "\n"),
                failure_reason=failure_reason,
            )
            return ExperimentRunResult(execution=record)

        stdout, stderr, returncode, timed_out = _run_command(command, workspace=workspace, timeout_seconds=timeout_seconds)
        detected_outputs, missing_outputs = _detect_expected_outputs(workspace, manifest)
        failure_reason = _failure_reason(returncode, timed_out, missing_outputs, detected_outputs)
        status = "complete" if returncode == 0 and detected_outputs and not missing_outputs and not timed_out else "failed"
        record = self.workspace_manager.record_execution(
            workspace_id=workspace.id,
            manifest_id=manifest.id,
            status=status,
            command=redact_text(command),
            returncode=returncode,
            stdout_text=redact_text(stdout),
            stderr_text=redact_text(stderr),
            result_paths=detected_outputs,
            failure_reason=failure_reason,
        )
        return ExperimentRunResult(
            execution=record,
            missing_outputs=[str(path) for path in missing_outputs],
            detected_outputs=[str(path) for path in detected_outputs],
            timed_out=timed_out,
        )

    def rerun(self, execution_id: str, *, timeout_seconds: int = 300, dry_run: bool = False) -> ExperimentRunResult:
        workspace, execution = self.find_execution(execution_id)
        return self.run(
            workspace_id=workspace.id,
            manifest_id=execution.manifest_id,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )

    def find_execution(self, execution_id: str) -> tuple[ExperimentWorkspace, ExperimentExecutionRecord]:
        for project_dir in self.config.project_root.glob("*"):
            workspace_root = project_dir / "experiment_workspaces"
            if not workspace_root.exists():
                continue
            for workspace_dir in workspace_root.iterdir():
                if not workspace_dir.is_dir():
                    continue
                workspace_path = workspace_dir / "workspace.json"
                execution_path = workspace_dir / "runs" / f"{execution_id}.json"
                if workspace_path.exists() and execution_path.exists():
                    workspace = self.workspace_manager.load_workspace(workspace_dir.name)
                    record = next(item for item in self.workspace_manager.list_execution_records(workspace.id) if item.id == execution_id)
                    return workspace, record
        raise FileNotFoundError(f"No experiment execution found for {execution_id}")

    def render_execution_status(self, execution_id: str) -> str:
        workspace, record = self.find_execution(execution_id)
        artifacts = self.workspace_manager.list_result_artifacts(workspace.id)
        artifact_by_id = {artifact.id: artifact for artifact in artifacts}
        lines = [
            f"# Experiment Execution `{record.id}`",
            "",
            f"- Workspace ID: `{workspace.id}`",
            f"- Manifest ID: `{record.manifest_id}`",
            f"- Status: `{record.status}`",
            f"- Return code: {record.returncode if record.returncode is not None else 'none'}",
            f"- Command: `{record.command or 'none'}`",
            f"- Stdout: `{record.stdout_path or 'none'}`",
            f"- Stderr: `{record.stderr_path or 'none'}`",
            f"- Failure reason: {record.failure_reason or 'none'}",
            "",
            "## Result Artifacts",
            "",
        ]
        if record.result_artifact_ids:
            for artifact_id in record.result_artifact_ids:
                artifact = artifact_by_id.get(artifact_id)
                if artifact is None:
                    lines.append(f"- `{artifact_id}` (metadata missing)")
                else:
                    lines.append(f"- `{artifact.id}` {artifact.artifact_type}, sha256 `{artifact.sha256}` at `{artifact.path}`")
        else:
            lines.append("- none")
        return "\n".join(lines).rstrip() + "\n"

    def _select_manifest(self, workspace: ExperimentWorkspace, *, manifest_id: str, run_type: str) -> ExperimentRunManifest:
        if manifest_id:
            return _require_manifest(self.workspace_manager.list_manifests(workspace.id), manifest_id)
        if not run_type:
            raise ValueError("Either manifest_id or run_type is required.")
        matches = [manifest for manifest in self.workspace_manager.list_manifests(workspace.id) if manifest.run_type == run_type]
        if matches:
            return matches[-1]
        return self.workspace_manager.create_manifest(
            workspace_id=workspace.id,
            run_type=run_type,
            command=_default_command_for_workspace(workspace),
        )


def render_run_result(result: ExperimentRunResult) -> str:
    lines = [
        f"# Experiment Run Result `{result.execution.id}`",
        "",
        f"- Status: `{result.execution.status}`",
        f"- Return code: {result.execution.returncode if result.execution.returncode is not None else 'none'}",
        f"- Dry run: {str(result.dry_run).lower()}",
        f"- Timed out: {str(result.timed_out).lower()}",
        f"- Failure reason: {result.execution.failure_reason or 'none'}",
        "",
        "## Detected Outputs",
        "",
    ]
    lines.extend([f"- `{item}`" for item in result.detected_outputs] or ["- none"])
    lines.extend(["", "## Missing Expected Outputs", ""])
    lines.extend([f"- `{item}`" for item in result.missing_outputs] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _run_command(
    command: str,
    *,
    workspace: ExperimentWorkspace,
    timeout_seconds: int,
) -> tuple[str, str, int | None, bool]:
    env = {**os.environ, "PYTHONPATH": _pythonpath_for_workspace(workspace)}
    try:
        completed = subprocess.run(
            command,
            cwd=workspace.root_dir,
            env=env,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_text(exc.stdout)
        stderr = _timeout_text(exc.stderr) + f"\nCommand timed out after {timeout_seconds} seconds."
        return stdout, stderr, 124, True
    return completed.stdout, completed.stderr, completed.returncode, False


def _detect_expected_outputs(
    workspace: ExperimentWorkspace,
    manifest: ExperimentRunManifest,
) -> tuple[list[Path], list[Path]]:
    detected: list[Path] = []
    missing: list[Path] = []
    for raw_output in manifest.expected_outputs:
        path = Path(raw_output)
        if not path.is_absolute():
            path = Path(workspace.root_dir) / path
        if path.exists():
            detected.append(path)
        else:
            missing.append(path)
    return detected, missing


def _failure_reason(returncode: int | None, timed_out: bool, missing_outputs: list[Path], detected_outputs: list[Path]) -> str:
    reasons: list[str] = []
    if timed_out:
        reasons.append("Command timed out.")
    if returncode not in {0, None}:
        reasons.append(f"Command exited with return code {returncode}.")
    if missing_outputs:
        reasons.append("Missing expected outputs: " + ", ".join(str(path) for path in missing_outputs))
    if returncode == 0 and not detected_outputs:
        reasons.append("Command succeeded but produced no expected result artifacts.")
    return " ".join(reasons)


def _validate_manifest_resources(manifest: ExperimentRunManifest):
    request = manifest.resource_request
    if resource_request_is_default(request):
        return validate_resource_request(request)
    result = validate_resource_request(request)
    if request.environment_type in {"docker", "slurm"}:
        result.blockers.append(
            "The current experiment runner executes local shell commands only; "
            f"`{request.environment_type}` requires dry-run or a future runner."
        )
        result.status = "unavailable"
    return result


def _resource_failure_reason(resource_check) -> str:
    blockers = "; ".join(resource_check.blockers) if resource_check.blockers else "no compatible compute environment was available"
    return f"Resource request is incompatible with available compute. {blockers}"


def _require_manifest(manifests: list[ExperimentRunManifest], manifest_id: str) -> ExperimentRunManifest:
    for manifest in manifests:
        if manifest.id == manifest_id:
            return manifest
    raise FileNotFoundError(f"No experiment manifest found for {manifest_id}")


def _default_command_for_workspace(workspace: ExperimentWorkspace) -> str:
    script = Path(workspace.root_dir) / "code" / "scripts" / "run_smoke.sh"
    if script.exists():
        return f"bash {script}"
    return "python -m run_experiment"


def _pythonpath_for_workspace(workspace: ExperimentWorkspace) -> str:
    code_src = Path(workspace.root_dir) / "code" / "src"
    existing = os.environ.get("PYTHONPATH", "")
    return str(code_src) if not existing else f"{code_src}{os.pathsep}{existing}"


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
