"""Replication manifest construction helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gapforge.datasets import DatasetRegistry
from gapforge.models import (
    DatasetRecord,
    ExperimentExecutionRecord,
    ExperimentResultArtifact,
    ExperimentRunManifest,
    ExperimentWorkspace,
    Provenance,
    ReplicationManifest,
)
from gapforge.state import utc_now_iso


def build_replication_manifest(
    *,
    package_id: str,
    workspace: ExperimentWorkspace,
    manifests: list[ExperimentRunManifest],
    executions: list[ExperimentExecutionRecord],
    artifacts: list[ExperimentResultArtifact],
    dataset_records: list[DatasetRecord],
    dataset_download_instructions: list[str],
    result_hashes: dict[str, str],
) -> ReplicationManifest:
    return ReplicationManifest(
        package_id=package_id,
        code_version=_code_version(Path(workspace.root_dir)),
        dataset_records=dataset_records,
        dataset_download_instructions=dataset_download_instructions,
        environment=_environment(manifests),
        commands=_commands(manifests, executions),
        expected_outputs=_expected_outputs(manifests),
        result_hashes=result_hashes,
        random_seeds=sorted({manifest.random_seed for manifest in manifests if manifest.random_seed}),
        limitations=_limitations(dataset_records, artifacts),
        provenance=Provenance(
            created_by_skill="replication-manifest",
            source_ids=[workspace.id, *[execution.id for execution in executions]],
            timestamp=utc_now_iso(),
            reasoning_summary="Built a replication manifest from recorded commands, seeds, datasets, environments, and result hashes.",
        ),
    )


def dataset_download_instruction(record: DatasetRecord) -> str:
    source = record.source_url or record.source or "source URL not recorded"
    return (
        f"Dataset `{record.id}` (`{record.name}`) was not bundled. Obtain it from {source}; "
        f"verify license `{record.license or 'unknown'}` and place it at the path expected by the run manifest."
    )


def safe_to_bundle_dataset(record: DatasetRecord) -> bool:
    text = f"{record.dataset_type} {record.license} {record.source} {record.source_url}".lower()
    if record.dataset_type in {"fixture", "synthetic", "generated"}:
        return True
    restricted_terms = ["restricted", "proprietary", "non-commercial", "manual", "auth", "unknown"]
    return not any(term in text for term in restricted_terms) and record.dataset_type not in {"real", "benchmark", "unknown"}


def workspace_datasets(config, workspace_id: str) -> list[DatasetRecord]:
    return DatasetRegistry(config).list_datasets(workspace_id)


def _commands(manifests: list[ExperimentRunManifest], executions: list[ExperimentExecutionRecord]) -> list[str]:
    manifest_by_id = {manifest.id: manifest for manifest in manifests}
    commands: list[str] = []
    for execution in executions:
        manifest = manifest_by_id.get(execution.manifest_id)
        command = execution.command or (manifest.command if manifest is not None else "")
        if command:
            commands.append(command)
    return list(dict.fromkeys(commands))


def _expected_outputs(manifests: list[ExperimentRunManifest]) -> list[str]:
    return list(dict.fromkeys(output for manifest in manifests for output in manifest.expected_outputs))


def _environment(manifests: list[ExperimentRunManifest]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for manifest in manifests:
        merged.update(manifest.environment)
        merged.setdefault("resource_environment", manifest.resource_request.environment_type)
    return merged


def _limitations(dataset_records: list[DatasetRecord], artifacts: list[ExperimentResultArtifact]) -> list[str]:
    limitations: list[str] = []
    if not dataset_records:
        limitations.append("No dataset records were available; replication requires manual data reconstruction.")
    if not artifacts:
        limitations.append("No result artifact hashes were available; package cannot verify empirical outputs.")
    if any(not safe_to_bundle_dataset(record) for record in dataset_records):
        limitations.append("Some datasets were excluded for safety or licensing reasons and require manual download.")
    return limitations


def _code_version(workspace_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=workspace_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"
