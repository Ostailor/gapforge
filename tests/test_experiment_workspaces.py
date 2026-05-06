from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.artifacts import sha256_file
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import BaselineCandidate, ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_create_experiment_workspace_persists_project_state(tmp_path: Path) -> None:
    config, project_id, protocol = _workspace_project(tmp_path)
    manager = ExperimentWorkspaceManager(config)

    workspace = manager.create_workspace(project_id=project_id, direction_id="direction-1")

    root = Path(workspace.root_dir)
    loaded = manager.load_workspace(workspace.id)
    program = ProjectMemoryManager(config).load_project(project_id)

    assert loaded.status == "scaffolded"
    assert loaded.experiment_protocol_id == protocol.id
    assert (root / "workspace.json").exists()
    assert (root / "manifests").is_dir()
    assert (root / "runs").is_dir()
    assert (root / "results").is_dir()
    assert (root / "logs").is_dir()
    assert any(item.id == workspace.id for item in program.experiment_workspaces)


def test_create_manifest_does_not_mark_experiment_executed(tmp_path: Path) -> None:
    config, project_id, _protocol = _workspace_project(tmp_path)
    manager = ExperimentWorkspaceManager(config)
    workspace = manager.create_workspace(project_id=project_id, direction_id="direction-1")

    manifest = manager.create_manifest(workspace_id=workspace.id, run_type="smoke")
    reloaded = manager.load_workspace(workspace.id)
    status = manager.workspace_status_markdown(workspace.id)

    assert manifest.run_type == "smoke"
    assert manifest.experiment_protocol_id == "protocol-1"
    assert reloaded.status == "ready"
    assert manager.list_execution_records(workspace.id) == []
    assert "has not executed any experiment yet" in status
    assert (Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json").exists()


def test_record_execution_complete_with_artifact_hash(tmp_path: Path) -> None:
    config, project_id, _protocol = _workspace_project(tmp_path)
    manager = ExperimentWorkspaceManager(config)
    workspace = manager.create_workspace(project_id=project_id, direction_id="direction-1")
    manifest = manager.create_manifest(workspace_id=workspace.id, run_type="pilot")
    metrics = Path(workspace.root_dir) / "results" / "metrics.json"
    metrics.write_text(json.dumps({"accuracy": 0.75}) + "\n", encoding="utf-8")

    record = manager.record_execution(
        workspace_id=workspace.id,
        manifest_id=manifest.id,
        status="complete",
        returncode=0,
        stdout_text="ok\n",
        stderr_text="",
        result_paths=[metrics],
    )
    artifacts = manager.list_result_artifacts(workspace.id)
    reloaded = manager.load_workspace(workspace.id)

    assert record.status == "complete"
    assert record.result_artifact_ids == [artifacts[0].id]
    assert artifacts[0].sha256 == sha256_file(metrics)
    assert artifacts[0].artifact_type == "metrics_json"
    assert reloaded.status == "complete"
    assert Path(record.stdout_path).read_text(encoding="utf-8") == "ok\n"


def test_record_execution_failure_is_visible_without_results(tmp_path: Path) -> None:
    config, project_id, _protocol = _workspace_project(tmp_path)
    manager = ExperimentWorkspaceManager(config)
    workspace = manager.create_workspace(project_id=project_id, direction_id="direction-1")
    manifest = manager.create_manifest(workspace_id=workspace.id, run_type="smoke")

    record = manager.record_execution(
        workspace_id=workspace.id,
        manifest_id=manifest.id,
        status="failed",
        returncode=2,
        stderr_text="dataset missing\n",
        failure_reason="Dataset fixture was not found.",
    )
    runs_md = Path(workspace.root_dir) / "reports" / "experiment_runs.md"

    assert record.status == "failed"
    assert record.result_artifact_ids == []
    assert manager.load_workspace(workspace.id).status == "failed"
    assert "Dataset fixture was not found." in runs_md.read_text(encoding="utf-8")


def test_experiment_workspace_cli_lifecycle(tmp_path: Path) -> None:
    config, project_id, _protocol = _workspace_project(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "experiment-workspace-create",
            "--project-id",
            project_id,
            "--direction-id",
            "direction-1",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    workspace_id = json.loads(created.stdout)["id"]

    manifest = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-manifest-create", "--workspace-id", workspace_id, "--run-type", "smoke"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-workspace-status", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    runs = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-runs", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert manifest.returncode == 0, manifest.stderr
    assert status.returncode == 0, status.stderr
    assert runs.returncode == 0, runs.stderr
    assert json.loads(runs.stdout) == []
    assert "has not executed any experiment yet" in status.stdout


def test_generated_experiment_workspaces_are_ignored_unless_fixtures() -> None:
    ignore = Path(__file__).resolve().parents[1] / ".gitignore"

    text = ignore.read_text(encoding="utf-8")

    assert "projects/*" in text
    assert "*.pdf" in text


def _workspace_project(tmp_path: Path) -> tuple[GapForgeConfig, str, ExperimentProtocol]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Experiment Workspace Project")
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id="direction-1",
        linked_experiment_plan_id="experiment-1",
        objective="Measure whether the fixture method improves the smoke metric.",
        hypothesis="The fixture method should produce a measurable output.",
        datasets=["fixture-dataset"],
        baselines=[
            BaselineCandidate(
                paper_id="paper-1",
                baseline_name="fixture baseline",
                why_required="Required to compare the proposed workflow.",
            )
        ],
        metrics=["accuracy"],
        expected_artifacts=["metrics.json"],
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    return config, program.project.id, protocol
