"""Export safe-by-default independent replication packages."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import (
    DatasetRecord,
    ExperimentExecutionRecord,
    ExperimentResultArtifact,
    ExperimentRunManifest,
    ExperimentWorkspace,
    Provenance,
    ReplicationManifest,
    ReplicationPackage,
    from_dict,
    to_plain,
)
from gapforge.replication.manifest import (
    build_replication_manifest,
    dataset_download_instruction,
    safe_to_bundle_dataset,
    workspace_datasets,
)
from gapforge.state import utc_now_iso


class ReplicationPackageExporter:
    """Build a shareable replication bundle from recorded experiment artifacts."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def export_workspace(self, workspace_id: str, execution_ids: list[str] | None = None) -> ReplicationPackage:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        executions = _select_executions(self.workspace_manager.list_execution_records(workspace.id), execution_ids)
        manifests = _manifests_for_executions(self.workspace_manager.list_manifests(workspace.id), executions)
        artifacts = _artifacts_for_executions(self.workspace_manager.list_result_artifacts(workspace.id), executions)
        datasets = workspace_datasets(self.config, workspace.id)
        package_id = f"replication-package-{workspace.id}"
        package_dir = Path(workspace.root_dir) / "replication_packages" / package_id
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True, exist_ok=True)

        result_hashes = _copy_result_artifacts(package_dir, artifacts)
        _copy_code(package_dir, workspace)
        _copy_manifest_records(package_dir, manifests, executions)
        dataset_instructions = _write_dataset_records(package_dir, datasets)
        manifest = build_replication_manifest(
            package_id=package_id,
            workspace=workspace,
            manifests=manifests,
            executions=executions,
            artifacts=artifacts,
            dataset_records=datasets,
            dataset_download_instructions=dataset_instructions,
            result_hashes=result_hashes,
        )
        manifest_path = package_dir / "replication_manifest.json"
        manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
        (package_dir / "replication_manifest.md").write_text(render_replication_manifest_markdown(manifest), encoding="utf-8")
        missing = _missing_requirements(manifests, executions, artifacts, datasets, dataset_instructions)
        package = ReplicationPackage(
            id=package_id,
            workspace_id=workspace.id,
            execution_ids=[execution.id for execution in executions],
            manifest_path=str(manifest_path),
            safe_to_share=not missing,
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="replication-package",
                source_ids=[workspace.id, *[execution.id for execution in executions]],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported a safe-by-default replication package from recorded commands, seeds, and result hashes.",
            ),
        )
        (package_dir / "README.md").write_text(render_replication_package_markdown(package, manifest), encoding="utf-8")
        (package_dir / "replication_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        package.files = _relative_files(package_dir)
        (package_dir / "replication_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def latest_for_workspace(self, workspace_id: str) -> ReplicationPackage | None:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        root = Path(workspace.root_dir) / "replication_packages"
        if not root.exists():
            return None
        records = sorted(root.glob("*/replication_package.json"))
        if not records:
            return None
        return from_dict(ReplicationPackage, json.loads(records[-1].read_text(encoding="utf-8")))


def render_replication_status(config: GapForgeConfig, workspace_id: str) -> str:
    exporter = ReplicationPackageExporter(config)
    package = exporter.latest_for_workspace(workspace_id)
    lines = ["# Replication Status", "", f"- Workspace ID: `{workspace_id}`"]
    if package is None:
        lines.extend(["- Package: none", "", "Run `gapforge export-replication-package --workspace-id ...` first."])
    else:
        lines.extend(
            [
                f"- Package ID: `{package.id}`",
                f"- Manifest: `{package.manifest_path}`",
                f"- Safe to share: {str(package.safe_to_share).lower()}",
                "- Independently verified: false unless `verify-replication-package` has passed.",
                "",
                "## Missing Requirements",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in package.missing_requirements] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_replication_package_markdown(package: ReplicationPackage, manifest: ReplicationManifest) -> str:
    lines = [
        f"# Replication Package `{package.id}`",
        "",
        "This package is a reproduction aid, not proof that independent replication has happened.",
        "",
        f"- Workspace ID: `{package.workspace_id}`",
        f"- Executions: {', '.join(f'`{item}`' for item in package.execution_ids) or 'none'}",
        f"- Manifest: `{Path(package.manifest_path).name}`",
        f"- Safe to share: {str(package.safe_to_share).lower()}",
        "",
        "## Reproduction Commands",
        "",
    ]
    lines.extend([f"```bash\n{command}\n```" for command in manifest.commands] or ["No commands recorded."])
    lines.extend(["", "## Dataset Download Instructions", ""])
    lines.extend([f"- {item}" for item in manifest.dataset_download_instructions] or ["- none"])
    lines.extend(["", "## Result Hashes", ""])
    lines.extend([f"- `{path}`: `{digest}`" for path, digest in manifest.result_hashes.items()] or ["- none"])
    lines.extend(["", "## Missing Requirements", ""])
    lines.extend([f"- {item}" for item in package.missing_requirements] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_replication_manifest_markdown(manifest: ReplicationManifest) -> str:
    lines = [
        f"# Replication Manifest `{manifest.package_id}`",
        "",
        f"- Code version: `{manifest.code_version}`",
        f"- Random seeds: {', '.join(str(seed) for seed in manifest.random_seeds) or 'none'}",
        f"- Expected outputs: {', '.join(f'`{item}`' for item in manifest.expected_outputs) or 'none'}",
        "",
        "## Environment",
        "",
    ]
    lines.extend([f"- `{key}`: `{value}`" for key, value in sorted(manifest.environment.items())] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in manifest.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _select_executions(
    executions: list[ExperimentExecutionRecord],
    execution_ids: list[str] | None,
) -> list[ExperimentExecutionRecord]:
    if not execution_ids:
        return executions
    selected = [execution for execution in executions if execution.id in set(execution_ids)]
    missing = sorted(set(execution_ids) - {execution.id for execution in selected})
    if missing:
        raise FileNotFoundError("No execution record found for: " + ", ".join(missing))
    return selected


def _manifests_for_executions(
    manifests: list[ExperimentRunManifest],
    executions: list[ExperimentExecutionRecord],
) -> list[ExperimentRunManifest]:
    manifest_ids = {execution.manifest_id for execution in executions}
    return [manifest for manifest in manifests if manifest.id in manifest_ids]


def _artifacts_for_executions(
    artifacts: list[ExperimentResultArtifact],
    executions: list[ExperimentExecutionRecord],
) -> list[ExperimentResultArtifact]:
    execution_ids = {execution.id for execution in executions}
    return [artifact for artifact in artifacts if artifact.execution_id in execution_ids]


def _copy_result_artifacts(package_dir: Path, artifacts: list[ExperimentResultArtifact]) -> dict[str, str]:
    result_dir = package_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for artifact in artifacts:
        source = Path(artifact.path)
        if not source.exists():
            continue
        destination = result_dir / f"{artifact.id}-{source.name}"
        shutil.copy2(source, destination)
        hashes[str(destination.relative_to(package_dir))] = artifact.sha256
    return hashes


def _copy_code(package_dir: Path, workspace: ExperimentWorkspace) -> None:
    source = Path(workspace.root_dir) / "code"
    destination = package_dir / "code"
    if source.exists():
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))


def _copy_manifest_records(
    package_dir: Path,
    manifests: list[ExperimentRunManifest],
    executions: list[ExperimentExecutionRecord],
) -> None:
    records_dir = package_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / "manifests.json").write_text(json.dumps(to_plain(manifests), indent=2) + "\n", encoding="utf-8")
    (records_dir / "executions.json").write_text(json.dumps(to_plain(executions), indent=2) + "\n", encoding="utf-8")


def _write_dataset_records(package_dir: Path, datasets: list[DatasetRecord]) -> list[str]:
    data_dir = package_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    instructions: list[str] = []
    for record in datasets:
        (data_dir / f"{record.id}.record.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        if safe_to_bundle_dataset(record):
            source = Path(record.local_path)
            if source.exists():
                shutil.copy2(source, data_dir / source.name)
        else:
            instructions.append(dataset_download_instruction(record))
    return instructions


def _missing_requirements(
    manifests: list[ExperimentRunManifest],
    executions: list[ExperimentExecutionRecord],
    artifacts: list[ExperimentResultArtifact],
    datasets: list[DatasetRecord],
    dataset_instructions: list[str],
) -> list[str]:
    missing: list[str] = []
    if not executions:
        missing.append("No execution records are included.")
    if not manifests:
        missing.append("No run manifests are included.")
    if not artifacts:
        missing.append("No result artifacts are included.")
    if any(not safe_to_bundle_dataset(record) for record in datasets):
        missing.append("Restricted or real dataset files were excluded; use recorded download instructions.")
    if any(not safe_to_bundle_dataset(record) for record in datasets) and not dataset_instructions:
        missing.append("Dataset download instructions are missing for excluded datasets.")
    if any(not manifest.random_seed for manifest in manifests):
        missing.append("One or more manifests lack a random seed.")
    return list(dict.fromkeys(missing))


def _relative_files(package_dir: Path) -> list[str]:
    return sorted(str(path.relative_to(package_dir)) for path in package_dir.rglob("*") if path.is_file())
