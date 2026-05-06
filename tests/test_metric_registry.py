from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry, builtin_metric_templates
from gapforge.metrics.reporting import render_metric_card_markdown
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_builtin_metric_templates_load() -> None:
    templates = builtin_metric_templates()

    assert "false positive rate" in templates
    assert "true positive rate" in templates
    assert "precision" in templates
    assert "recall" in templates
    assert "auroc" in templates
    assert "auprc" in templates
    assert "calibration error" in templates
    assert "abstention rate" in templates
    assert "cost weighted error" in templates
    assert "runtime/latency" in templates
    assert templates["false positive rate"].higher_is_better is False


def test_low_fpr_stats_plan_warns_about_sample_size_and_confidence_intervals(tmp_path: Path) -> None:
    config, workspace_id = _metric_workspace(tmp_path)
    registry = MetricRegistry(config)
    metric = registry.register_metric(workspace_id=workspace_id, name="false positive rate")

    plan = registry.create_stats_plan(workspace_id=workspace_id)

    assert metric.metric_type == "detection"
    assert metric.id in plan.metric_ids
    assert "Low-FPR" in plan.sample_size_notes
    assert "exact/binomial" in plan.confidence_interval_method
    assert "target FPR" in plan.confidence_interval_method


def test_metric_card_renders(tmp_path: Path) -> None:
    config, workspace_id = _metric_workspace(tmp_path)
    registry = MetricRegistry(config)

    metric = registry.register_metric(workspace_id=workspace_id, name="runtime/latency")
    card = render_metric_card_markdown(metric)

    assert "Metric Card" in card
    assert "runtime/latency" in card
    assert "Report hardware" in card


def test_missing_metric_blocks_execution_readiness(tmp_path: Path) -> None:
    config, workspace_id = _metric_workspace(tmp_path)
    registry = MetricRegistry(config)

    blockers = registry.readiness_blockers(workspace_id)
    registry.register_metric(workspace_id=workspace_id, name="precision")
    cleared = registry.readiness_blockers(workspace_id)

    assert blockers == ["No explicit metric records are registered for this experiment workspace."]
    assert cleared == []


def test_registered_metrics_feed_experiment_manifest(tmp_path: Path) -> None:
    config, workspace_id = _metric_workspace(tmp_path)
    registry = MetricRegistry(config)
    metric = registry.register_metric(workspace_id=workspace_id, name="precision")

    manifest = ExperimentWorkspaceManager(config).create_manifest(workspace_id=workspace_id, run_type="smoke")

    assert metric.id in manifest.metric_ids


def test_metric_cli_register_list_stats_plan(tmp_path: Path) -> None:
    _config, workspace_id = _metric_workspace(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "metric-register",
            "--workspace-id",
            workspace_id,
            "--name",
            "false positive rate",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "metric-list", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    planned = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "stats-plan", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert registered.returncode == 0, registered.stderr
    assert json.loads(registered.stdout)["metric_type"] == "detection"
    assert listed.returncode == 0, listed.stderr
    assert planned.returncode == 0, planned.stderr
    assert "false positive rate" in listed.stdout
    assert "exact/binomial" in planned.stdout


def test_stats_plan_cli_accepts_experiment_id_without_workspace_metrics(tmp_path: Path) -> None:
    _config, _workspace_id = _metric_workspace(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    planned = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "stats-plan", "--experiment-id", "protocol-1"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert planned.returncode == 0, planned.stderr
    assert "protocol-1" in planned.stdout
    assert "exact/binomial" in planned.stdout
    assert "metric-false-positive-rate" in planned.stdout


def _metric_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Metric Registry Project")
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id="direction-1",
        linked_experiment_plan_id="experiment-1",
        objective="Evaluate low-FPR behavior.",
        hypothesis="The proposed detector improves recall at fixed low FPR.",
        datasets=["fixture"],
        metrics=["false positive rate", "recall"],
        failure_modes=["No improvement over strongest baseline at target FPR."],
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-1")
    return config, workspace.id
