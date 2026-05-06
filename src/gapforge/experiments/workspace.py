"""First-class experiment workspace persistence."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from gapforge.config import GapForgeConfig
from gapforge.experiments.artifacts import build_result_artifact
from gapforge.experiments.manifests import build_run_manifest, render_manifest_markdown
from gapforge.experiments.run_state import build_execution_record, render_execution_records_markdown
from gapforge.models import (
    ExperimentExecutionRecord,
    ExperimentProtocol,
    ExperimentResultArtifact,
    ExperimentRunManifest,
    ExperimentWorkspace,
    Provenance,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso

WORKSPACE_SUBDIRS = ["manifests", "runs", "results", "logs", "reports", "code", "data", "configs", "baselines", "metrics"]
T = TypeVar("T")


class ExperimentWorkspaceManager:
    """Manage durable experiment workspace state outside normal research reports."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)

    def create_workspace(
        self,
        *,
        project_id: str,
        direction_id: str,
        campaign_id: str = "",
        experiment_protocol_id: str = "",
    ) -> ExperimentWorkspace:
        program = self.project_manager.load_project(project_id)
        protocol = _select_protocol(program.experiment_protocols, direction_id, experiment_protocol_id)
        protocol_id = protocol.id if protocol else experiment_protocol_id
        project_root = Path(program.project.root_dir)
        workspace_id = _unique_workspace_id(project_root / "experiment_workspaces", direction_id)
        root_dir = project_root / "experiment_workspaces" / workspace_id
        _ensure_workspace_dirs(root_dir)
        now = utc_now_iso()
        workspace = ExperimentWorkspace(
            id=workspace_id,
            project_id=project_id,
            campaign_id=campaign_id,
            direction_id=direction_id,
            experiment_protocol_id=protocol_id,
            root_dir=str(root_dir),
            status="scaffolded",
            created_at=now,
            updated_at=now,
            provenance=Provenance(
                created_by_skill="experiment-workspace",
                source_ids=[project_id, direction_id, protocol_id],
                timestamp=now,
                reasoning_summary=(
                    "Created a first-class experiment workspace. This is scaffolding, not evidence that an experiment executed."
                ),
            ),
        )
        self._write_workspace(workspace)
        program.experiment_workspaces = _replace_workspace(program.experiment_workspaces, workspace)
        self.project_manager.save_project(program)
        return workspace

    def load_workspace(self, workspace_id: str) -> ExperimentWorkspace:
        path = self._workspace_path(workspace_id) / "workspace.json"
        if not path.exists():
            raise FileNotFoundError(f"No experiment workspace found for {workspace_id}")
        return from_dict(ExperimentWorkspace, json.loads(path.read_text(encoding="utf-8")))

    def create_manifest(
        self,
        *,
        workspace_id: str,
        run_type: str = "smoke",
        run_name: str = "",
        dataset_ids: list[str] | None = None,
        baseline_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
        command: str = "",
        expected_outputs: list[str] | None = None,
        random_seed: int = 0,
    ) -> ExperimentRunManifest:
        workspace = self.load_workspace(workspace_id)
        protocol = self._protocol_for_workspace(workspace)
        if baseline_ids is None:
            baseline_ids = self._registered_baseline_ids(workspace_id)
        if metric_ids is None:
            metric_ids = self._registered_metric_ids(workspace_id)
        sequence = len(self.list_manifests(workspace_id)) + 1
        manifest = build_run_manifest(
            workspace,
            protocol=protocol,
            run_type=run_type,
            run_name=run_name,
            dataset_ids=dataset_ids,
            baseline_ids=baseline_ids,
            metric_ids=metric_ids,
            command=command,
            expected_outputs=expected_outputs,
            random_seed=random_seed,
            sequence=sequence,
        )
        manifest_path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
        manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
        (Path(workspace.root_dir) / "manifests" / f"{manifest.id}.md").write_text(render_manifest_markdown(manifest), encoding="utf-8")
        workspace.status = "ready"
        workspace.updated_at = utc_now_iso()
        self._write_workspace(workspace)
        self._update_project_workspace(workspace)
        return manifest

    def _registered_baseline_ids(self, workspace_id: str) -> list[str] | None:
        try:
            from gapforge.baselines.registry import BaselineRegistry

            baseline_ids = [record.id for record in BaselineRegistry(self.config).list_baselines(workspace_id)]
        except Exception:
            return None
        return baseline_ids or None

    def _registered_metric_ids(self, workspace_id: str) -> list[str] | None:
        try:
            from gapforge.metrics.registry import MetricRegistry

            metric_ids = [record.id for record in MetricRegistry(self.config).list_metrics(workspace_id)]
        except Exception:
            return None
        return metric_ids or None

    def list_manifests(self, workspace_id: str) -> list[ExperimentRunManifest]:
        manifest_dir = self._workspace_path(workspace_id) / "manifests"
        return _load_records(manifest_dir, ExperimentRunManifest)

    def record_execution(
        self,
        *,
        workspace_id: str,
        manifest_id: str,
        status: str,
        command: str = "",
        returncode: int | None = None,
        stdout_text: str = "",
        stderr_text: str = "",
        result_paths: Iterable[str | Path] = (),
        failure_reason: str = "",
    ) -> ExperimentExecutionRecord:
        if status not in {"planned", "running", "complete", "failed", "skipped"}:
            raise ValueError(f"Unsupported execution status: {status}")
        workspace = self.load_workspace(workspace_id)
        manifest = self._require_manifest(workspace_id, manifest_id)
        sequence = len(self.list_execution_records(workspace_id)) + 1
        execution_id = f"execution-{manifest.id}-{sequence}"
        stdout_path = Path(workspace.root_dir) / "logs" / f"{execution_id}.stdout.txt"
        stderr_path = Path(workspace.root_dir) / "logs" / f"{execution_id}.stderr.txt"
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        artifacts: list[ExperimentResultArtifact] = []
        for raw_path in result_paths:
            artifact_path = Path(raw_path)
            if not artifact_path.is_absolute():
                artifact_path = Path(workspace.root_dir) / artifact_path
            artifacts.append(build_result_artifact(workspace, execution_id, artifact_path))
        record = build_execution_record(
            workspace,
            manifest,
            status=status,
            sequence=sequence,
            command=command,
            returncode=returncode,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            result_artifact_ids=[artifact.id for artifact in artifacts],
            failure_reason=failure_reason,
        )
        self._write_execution_record(workspace, record)
        for artifact in artifacts:
            self._write_result_artifact(workspace, artifact)
        workspace.status = _workspace_status_from_execution(status)
        workspace.updated_at = utc_now_iso()
        self._write_workspace(workspace)
        self._update_project_workspace(workspace)
        self._write_runs_markdown(workspace)
        return record

    def list_execution_records(self, workspace_id: str) -> list[ExperimentExecutionRecord]:
        return _load_records(self._workspace_path(workspace_id) / "runs", ExperimentExecutionRecord)

    def list_result_artifacts(self, workspace_id: str) -> list[ExperimentResultArtifact]:
        return _load_records(
            self._workspace_path(workspace_id) / "results",
            ExperimentResultArtifact,
            glob_pattern="result-*.artifact.json",
        )

    def workspace_status_markdown(self, workspace_id: str) -> str:
        workspace = self.load_workspace(workspace_id)
        manifests = self.list_manifests(workspace_id)
        records = self.list_execution_records(workspace_id)
        artifacts = self.list_result_artifacts(workspace_id)
        lines = [
            f"# Experiment Workspace `{workspace.id}`",
            "",
            f"- Project ID: `{workspace.project_id}`",
            f"- Campaign ID: `{workspace.campaign_id or 'none'}`",
            f"- Direction ID: `{workspace.direction_id}`",
            f"- Protocol ID: `{workspace.experiment_protocol_id or 'none'}`",
            f"- Status: `{workspace.status}`",
            f"- Root: `{workspace.root_dir}`",
            f"- Manifests: {len(manifests)}",
            f"- Execution records: {len(records)}",
            f"- Result artifacts: {len(artifacts)}",
            "",
            "## Execution Boundary",
            "",
        ]
        if records:
            lines.append("This workspace has execution records. Only complete records with result artifacts can support empirical claims.")
        else:
            lines.append("This workspace has not executed any experiment yet.")
        return "\n".join(lines).rstrip() + "\n"

    def _workspace_path(self, workspace_id: str) -> Path:
        for project_dir in self.config.project_root.glob("*"):
            candidate = project_dir / "experiment_workspaces" / workspace_id
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No experiment workspace found for {workspace_id}")

    def _protocol_for_workspace(self, workspace: ExperimentWorkspace) -> ExperimentProtocol | None:
        program = self.project_manager.load_project(workspace.project_id)
        return _select_protocol(program.experiment_protocols, workspace.direction_id, workspace.experiment_protocol_id)

    def _require_manifest(self, workspace_id: str, manifest_id: str) -> ExperimentRunManifest:
        for manifest in self.list_manifests(workspace_id):
            if manifest.id == manifest_id:
                return manifest
        raise FileNotFoundError(f"No manifest {manifest_id} in workspace {workspace_id}")

    def _write_workspace(self, workspace: ExperimentWorkspace) -> None:
        root = Path(workspace.root_dir)
        _ensure_workspace_dirs(root)
        (root / "workspace.json").write_text(json.dumps(to_plain(workspace), indent=2) + "\n", encoding="utf-8")
        (root / "reports" / "workspace_status.md").write_text(self._render_workspace_file_status(workspace), encoding="utf-8")

    def _render_workspace_file_status(self, workspace: ExperimentWorkspace) -> str:
        return (
            f"# Experiment Workspace `{workspace.id}`\n\n"
            f"- Status: `{workspace.status}`\n"
            f"- Project ID: `{workspace.project_id}`\n"
            f"- Direction ID: `{workspace.direction_id}`\n"
            f"- Protocol ID: `{workspace.experiment_protocol_id or 'none'}`\n"
            f"- Root: `{workspace.root_dir}`\n\n"
            "This workspace is durable experiment state. A workspace alone does not prove execution.\n"
        )

    def _write_execution_record(self, workspace: ExperimentWorkspace, record: ExperimentExecutionRecord) -> None:
        path = Path(workspace.root_dir) / "runs" / f"{record.id}.json"
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")

    def _write_result_artifact(self, workspace: ExperimentWorkspace, artifact: ExperimentResultArtifact) -> None:
        path = Path(workspace.root_dir) / "results" / f"{artifact.id}.artifact.json"
        path.write_text(json.dumps(to_plain(artifact), indent=2) + "\n", encoding="utf-8")

    def _write_runs_markdown(self, workspace: ExperimentWorkspace) -> None:
        path = Path(workspace.root_dir) / "reports" / "experiment_runs.md"
        path.write_text(render_execution_records_markdown(self.list_execution_records(workspace.id)), encoding="utf-8")

    def _update_project_workspace(self, workspace: ExperimentWorkspace) -> None:
        program = self.project_manager.load_project(workspace.project_id)
        program.experiment_workspaces = _replace_workspace(program.experiment_workspaces, workspace)
        self.project_manager.save_project(program)


def _ensure_workspace_dirs(root_dir: Path) -> None:
    root_dir.mkdir(parents=True, exist_ok=True)
    for name in WORKSPACE_SUBDIRS:
        (root_dir / name).mkdir(parents=True, exist_ok=True)


def _select_protocol(
    protocols: list[ExperimentProtocol],
    direction_id: str,
    experiment_protocol_id: str = "",
) -> ExperimentProtocol | None:
    if experiment_protocol_id:
        return next((item for item in protocols if item.id == experiment_protocol_id), None)
    return next((item for item in protocols if item.direction_id == direction_id), None)


def _unique_workspace_id(base_dir: Path, direction_id: str) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    base = f"workspace-{slugify(direction_id)}"
    candidate = base
    suffix = 2
    while (base_dir / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _replace_workspace(workspaces: list[ExperimentWorkspace], workspace: ExperimentWorkspace) -> list[ExperimentWorkspace]:
    replaced = False
    result: list[ExperimentWorkspace] = []
    for item in workspaces:
        if item.id == workspace.id:
            result.append(workspace)
            replaced = True
        else:
            result.append(item)
    if not replaced:
        result.append(workspace)
    return result


def _load_records(path: Path, model: type[T], *, glob_pattern: str = "*.json") -> list[T]:
    if not path.exists():
        return []
    records: list[T] = []
    for item in sorted(path.glob(glob_pattern)):
        records.append(from_dict(model, json.loads(item.read_text(encoding="utf-8"))))
    return records


def _workspace_status_from_execution(status: str) -> str:
    if status == "running":
        return "running"
    if status == "complete":
        return "complete"
    if status == "failed":
        return "failed"
    return "ready"
