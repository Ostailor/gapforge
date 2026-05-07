from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.experiments.sweeps import ExperimentSweepManager, render_ablation_plan_markdown, render_sweep_status
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.jobs.scheduler import JobScheduler
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_parameter_sweep_generates_manifests_with_parameter_diffs(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)
    base_manifest = _base_manifest(config, workspace_id)

    sweep = ExperimentSweepManager(config).create_parameter_sweep(
        workspace_id=workspace_id,
        base_manifest_id=base_manifest.id,
        name="threshold sweep",
        parameters={"metric.threshold": ["0.1", "0.2", "0.3"]},
    )
    manifests = ExperimentWorkspaceManager(config).list_manifests(workspace_id)
    generated = [manifest for manifest in manifests if manifest.id in sweep.generated_manifest_ids]

    assert len(sweep.generated_manifest_ids) == 3
    assert [manifest.random_seed for manifest in generated] == [base_manifest.random_seed] * 3
    written_configs = [json.loads(Path(manifest.config_path).read_text(encoding="utf-8")) for manifest in generated]
    assert [item["metric"]["threshold"] for item in written_configs] == [0.1, 0.2, 0.3]
    assert sweep.parameters == {"metric.threshold": ["0.1", "0.2", "0.3"]}


def test_seed_plan_generates_seeded_manifests(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)
    _base_manifest(config, workspace_id)

    seed_plan = ExperimentSweepManager(config).create_seed_plan(
        workspace_id=workspace_id,
        seeds=[1, 2, 3],
        rationale="Exercise stochastic variation.",
    )
    generated = [
        manifest
        for manifest in ExperimentWorkspaceManager(config).list_manifests(workspace_id)
        if manifest.id in seed_plan.generated_manifest_ids
    ]

    assert seed_plan.seeds == [1, 2, 3]
    assert [manifest.random_seed for manifest in generated] == [1, 2, 3]


def test_ablation_plan_renders(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)

    plan = ExperimentSweepManager(config).create_ablation_plan(
        workspace_id=workspace_id,
        name="remove components",
        factors=["retrieval", "reranker"],
        controls=["full system"],
        expected_comparisons=["full system vs no retrieval"],
    )
    rendered = render_ablation_plan_markdown(plan)

    assert "remove components" in rendered
    assert "retrieval" in rendered
    assert "full system vs no retrieval" in rendered


def test_large_sweep_requires_confirmation(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)
    base_manifest = _base_manifest(config, workspace_id)

    with pytest.raises(ValueError, match="confirm_large"):
        ExperimentSweepManager(config).create_parameter_sweep(
            workspace_id=workspace_id,
            base_manifest_id=base_manifest.id,
            name="too large",
            parameters={
                "metric.threshold": ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6"],
                "model.depth": ["1", "2", "3", "4", "5", "6"],
            },
        )


def test_sweep_submit_and_status_updates_from_jobs(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "write_result.py"
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text('{{\"ok\": true}}' + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    base_manifest = _base_manifest(config, workspace_id, command=f"{sys.executable} {script}")
    sweep = ExperimentSweepManager(config).create_parameter_sweep(
        workspace_id=workspace_id,
        base_manifest_id=base_manifest.id,
        name="single sweep",
        parameters={"metric.threshold": ["0.1"]},
    )

    queue = ExperimentSweepManager(config).submit_sweep(sweep.id)
    JobScheduler(config).run_next(queue.id)
    status = ExperimentSweepManager(config).sweep_status(sweep.id)
    rendered = render_sweep_status(status)

    assert status["complete"] == 1
    assert "complete: 1" in rendered


def test_sweep_cli_create_and_status(tmp_path: Path) -> None:
    config, workspace_id = _sweep_workspace(tmp_path)
    base_manifest = _base_manifest(config, workspace_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "sweep-create",
            "--workspace-id",
            workspace_id,
            "--manifest-id",
            base_manifest.id,
            "--param",
            "metric.threshold=0.1,0.2",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    sweep_id = json.loads(created.stdout)["id"]

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "sweep-status", "--sweep-id", sweep_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status.returncode == 0, status.stderr
    assert sweep_id in status.stdout
    assert "queued: 0" in status.stdout


def _base_manifest(config: GapForgeConfig, workspace_id: str, command: str = ""):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    base_config = Path(workspace.root_dir) / "configs" / "base.json"
    base_config.write_text(json.dumps({"metric": {"threshold": 0.0}, "model": {"depth": 1}}) + "\n", encoding="utf-8")
    return ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        run_name="base",
        command=command or f"python -m run_experiment --config {base_config}",
        expected_outputs=["results/metrics.json"],
        random_seed=7,
        config_path=str(base_config),
    )


def _sweep_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Sweep Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-sweeps",
            direction_id="direction-sweeps",
            linked_experiment_plan_id="experiment-sweeps",
            objective="Exercise sweeps.",
            hypothesis="Systematic variations are recorded.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-sweeps")
    return config, workspace.id
