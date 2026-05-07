from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code import ExperimentCodeScaffolderV2
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, ReplicationManifest, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication import ReplicationPackageExporter, ReplicationPackageVerifier


def test_replication_package_exports_manifest_and_files(tmp_path: Path) -> None:
    config, workspace_id, execution_id = _replication_execution(tmp_path)

    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    manifest = from_dict(ReplicationManifest, json.loads(Path(package.manifest_path).read_text(encoding="utf-8")))

    assert package.workspace_id == workspace_id
    assert execution_id in package.execution_ids
    assert (package_dir / "README.md").exists()
    assert "replication_manifest.json" in package.files
    assert manifest.commands
    assert manifest.random_seeds == [123]
    assert manifest.result_hashes
    assert package.safe_to_share is True


def test_restricted_dataset_is_excluded_and_instructions_included(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path, dataset_type="real", license_name="restricted")

    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    manifest = from_dict(ReplicationManifest, json.loads(Path(package.manifest_path).read_text(encoding="utf-8")))
    package_dir = Path(package.manifest_path).parent

    assert package.safe_to_share is False
    assert any("restricted" in item.lower() for item in package.missing_requirements)
    assert manifest.dataset_download_instructions
    assert not (package_dir / "data" / "fixture.csv").exists()


def test_replication_verifier_passes_fixture_package(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)

    result = ReplicationPackageVerifier(config).verify(Path(package.manifest_path).parent)

    assert result.status == "pass"
    assert result.blockers == []
    assert result.checks["manifest"] == "pass"
    assert result.checks["result_hashes"] == "pass"


def test_missing_dataset_instruction_warns(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path, dataset_type="real", license_name="restricted")
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    manifest_path = Path(package.manifest_path)
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["dataset_download_instructions"] = []
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

    result = ReplicationPackageVerifier(config).verify(manifest_path.parent)

    assert result.status == "warning"
    assert any("download instruction" in blocker.lower() for blocker in result.blockers)


def test_replication_cli_exports_verifies_and_reports_status(tmp_path: Path) -> None:
    _config, workspace_id, _execution_id = _replication_execution(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    export_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-replication-package", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    package_path = next((tmp_path / "projects").glob("*/experiment_workspaces/*/replication_packages/*"))
    verify_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "verify-replication-package", "--package-path", str(package_path)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "replication-status", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert export_result.returncode == 0, export_result.stderr
    assert "Replication Package" in export_result.stdout
    assert verify_result.returncode == 0, verify_result.stderr
    assert "Verification Result" in verify_result.stdout
    assert status_result.returncode == 0, status_result.stderr
    assert "Replication Status" in status_result.stdout


def _replication_execution(
    tmp_path: Path,
    *,
    dataset_type: str = "fixture",
    license_name: str = "MIT",
) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Replication Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-replication",
            direction_id="direction-replication",
            linked_experiment_plan_id="experiment-replication",
            objective="Export a replication package.",
            hypothesis="Artifact-backed runs can be reproduced from package instructions.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-replication",
    )
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture examples",
        path=dataset_path,
        dataset_type=dataset_type,
        license=license_name,
        source_url="https://example.test/dataset",
        intended_use="Replication fixture.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_replication_metrics.py"
    payload = json.dumps({"metric_results": [{"metric_id": "false positive rate", "value": 0.0, "sample_size": 100}]})
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace.id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    execution = ExperimentRunner(config).run(workspace_id=workspace.id, manifest_id=manifest.id).execution
    return config, workspace.id, execution.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
