"""Experiment run manifest creation and rendering."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from gapforge.models import ExperimentProtocol, ExperimentRunManifest, ExperimentWorkspace, Provenance, ResourceRequest
from gapforge.state import utc_now_iso


def build_run_manifest(
    workspace: ExperimentWorkspace,
    *,
    protocol: ExperimentProtocol | None = None,
    run_type: str = "smoke",
    run_name: str = "",
    dataset_ids: list[str] | None = None,
    baseline_ids: list[str] | None = None,
    metric_ids: list[str] | None = None,
    config_path: str = "",
    command: str = "",
    expected_outputs: list[str] | None = None,
    random_seed: int = 0,
    resource_request: ResourceRequest | None = None,
    sequence: int = 1,
) -> ExperimentRunManifest:
    manifest_id = f"manifest-{run_type}-{sequence}"
    config = config_path or str(Path(workspace.root_dir) / "configs" / f"{manifest_id}.json")
    outputs = expected_outputs or _default_expected_outputs(workspace, protocol)
    return ExperimentRunManifest(
        id=manifest_id,
        workspace_id=workspace.id,
        experiment_protocol_id=workspace.experiment_protocol_id,
        run_name=run_name or f"{run_type} run {sequence}",
        run_type=run_type,
        dataset_ids=dataset_ids if dataset_ids is not None else list(protocol.datasets if protocol else []),
        baseline_ids=baseline_ids if baseline_ids is not None else _protocol_baseline_ids(protocol),
        metric_ids=metric_ids if metric_ids is not None else list(protocol.metrics if protocol else []),
        config_path=config,
        command=command or f"python -m run_experiment --config {config}",
        expected_outputs=outputs,
        random_seed=random_seed,
        environment=_default_environment(),
        resource_request=resource_request or ResourceRequest(),
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="experiment-manifest",
            source_ids=[workspace.id, workspace.experiment_protocol_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Created a run manifest. This manifest does not mean the experiment has executed.",
        ),
    )


def render_manifest_markdown(manifest: ExperimentRunManifest) -> str:
    lines = [
        f"# Experiment Run Manifest `{manifest.id}`",
        "",
        f"- Workspace ID: `{manifest.workspace_id}`",
        f"- Protocol ID: `{manifest.experiment_protocol_id or 'none'}`",
        f"- Run name: {manifest.run_name}",
        f"- Run type: `{manifest.run_type}`",
        f"- Config path: `{manifest.config_path}`",
        f"- Command: `{manifest.command}`",
        f"- Random seed: {manifest.random_seed}",
        f"- Created at: {manifest.created_at or 'unknown'}",
        "",
        "## Resource Request",
        "",
        f"- Environment type: `{manifest.resource_request.environment_type}`",
        f"- CPUs: {manifest.resource_request.cpu_count}",
        f"- Memory GB: {manifest.resource_request.memory_gb}",
        f"- GPUs: {manifest.resource_request.gpu_count}",
        f"- Wall time minutes: {manifest.resource_request.wall_time_minutes}",
        f"- Disk GB: {manifest.resource_request.disk_gb}",
        "",
        "## Datasets",
        "",
    ]
    lines.extend([f"- `{item}`" for item in manifest.dataset_ids] or ["- none"])
    lines.extend(["", "## Baselines", ""])
    lines.extend([f"- `{item}`" for item in manifest.baseline_ids] or ["- none"])
    lines.extend(["", "## Metrics", ""])
    lines.extend([f"- `{item}`" for item in manifest.metric_ids] or ["- none"])
    lines.extend(["", "## Expected Outputs", ""])
    lines.extend([f"- `{item}`" for item in manifest.expected_outputs] or ["- none"])
    lines.extend(["", "## Boundary", "", "This manifest is a plan for execution. It is not evidence that the experiment ran.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _default_expected_outputs(workspace: ExperimentWorkspace, protocol: ExperimentProtocol | None) -> list[str]:
    if protocol and protocol.expected_artifacts:
        return [str(Path(workspace.root_dir) / "results" / Path(item).name) for item in protocol.expected_artifacts[:6]]
    return [str(Path(workspace.root_dir) / "results" / "metrics.json")]


def _protocol_baseline_ids(protocol: ExperimentProtocol | None) -> list[str]:
    if protocol is None:
        return []
    return [item.baseline_name for item in protocol.baselines]


def _default_environment() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
