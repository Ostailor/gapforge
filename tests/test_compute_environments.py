from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.compute.environments import check_environment, detect_compute_environments
from gapforge.compute.resources import validate_resource_request
from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentProtocol, ResourceRequest
from gapforge.project_memory import ProjectMemoryManager


def test_local_environment_available() -> None:
    result = check_environment("local")

    assert result.status == "available"
    assert result.environment_id == "local"
    assert int(result.checks["cpu_count"]) >= 1


def test_missing_docker_reports_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("PATH", "")

    result = check_environment("docker")

    assert result.status == "unavailable"
    assert any("Docker command was not found" in blocker for blocker in result.blockers)


def test_fake_gpu_fixture_reports_available(monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_FAKE_CUDA", "1")
    monkeypatch.setenv("GAPFORGE_FAKE_GPU_COUNT", "2")

    environments = detect_compute_environments()
    gpu_env = next(item for item in environments if item.environment_type == "gpu_local")

    assert gpu_env.available is True
    assert gpu_env.cuda_available is True
    assert gpu_env.gpu_count == 2


def test_resource_request_validation_blocks_missing_gpu(monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_FAKE_CUDA", raising=False)
    monkeypatch.delenv("GAPFORGE_FAKE_GPU_COUNT", raising=False)

    result = validate_resource_request(ResourceRequest(gpu_count=1, environment_type="gpu_local"))

    assert result.status in {"degraded", "unavailable"}
    assert any("GPU" in blocker for blocker in result.blockers)


def test_compute_cli_status_json(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    completed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "compute-status", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert any(item["environment_type"] == "local" and item["available"] for item in payload)


def test_incompatible_manifest_resource_request_fails_before_execution(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_FAKE_CUDA", raising=False)
    monkeypatch.delenv("GAPFORGE_FAKE_GPU_COUNT", raising=False)
    config, workspace_id = _runner_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_metrics.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text('{{\"ok\": true}}')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        resource_request=ResourceRequest(gpu_count=1, environment_type="gpu_local"),
    )

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)

    assert result.execution.status == "failed"
    assert output.exists() is False
    assert "Resource request is incompatible" in result.execution.failure_reason


def _runner_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Compute Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-compute",
            direction_id="direction-compute",
            linked_experiment_plan_id="experiment-compute",
            objective="Execute fixture commands.",
            hypothesis="Fixture command execution is recorded.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-compute",
    )
    return config, workspace.id
