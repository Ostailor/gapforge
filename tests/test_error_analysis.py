from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results.error_analysis import ErrorAnalysisBuilder, render_error_analysis_report
from gapforge.results.slices import SliceAnalysisBuilder


def test_error_analysis_from_fixture_predictions(tmp_path: Path) -> None:
    config, workspace_id = _error_workspace(tmp_path)
    execution_id = _run_predictions(config, workspace_id)

    report = ErrorAnalysisBuilder(config).analyze_execution(execution_id)

    assert any("false_positive: 2" == item for item in report.top_error_types)
    assert any("false_negative: 1" == item for item in report.top_error_types)
    assert report.qualitative_examples
    assert all(example["id"] in {"p1", "p2", "p4"} for example in report.qualitative_examples)


def test_no_predictions_warns(tmp_path: Path) -> None:
    config, workspace_id = _error_workspace(tmp_path)
    execution_id = _run_metrics_only(config, workspace_id)

    report = ErrorAnalysisBuilder(config).analyze_execution(execution_id)

    assert report.slices == []
    assert any("No predictions artifact" in item for item in report.limitations)


def test_slice_analysis_filters_predictions(tmp_path: Path) -> None:
    config, workspace_id = _error_workspace(tmp_path)
    execution_id = _run_predictions(config, workspace_id)

    error_slice = SliceAnalysisBuilder(config).analyze_slice(execution_id, "cohort=rare")

    assert error_slice.slice_name == "cohort=rare"
    assert error_slice.sample_count == 3
    assert any(result.metric_id == "false_positive_count" and result.value == 2 for result in error_slice.metric_results)
    assert all(example["cohort"] == "rare" for example in error_slice.examples)


def test_low_fpr_highlights_false_positives(tmp_path: Path) -> None:
    config, workspace_id = _error_workspace(tmp_path)
    execution_id = _run_predictions(config, workspace_id)

    report = ErrorAnalysisBuilder(config).analyze_execution(execution_id)

    assert report.top_error_types[0].startswith("false_positive")
    assert any("Low-FPR" in limitation for limitation in report.limitations)


def test_error_report_renders_and_cli(tmp_path: Path) -> None:
    config, workspace_id = _error_workspace(tmp_path)
    execution_id = _run_predictions(config, workspace_id)
    report = ErrorAnalysisBuilder(config).analyze_execution(execution_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    rendered = render_error_analysis_report(report)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "slice-analysis", "--execution-id", execution_id, "--slice", "cohort=rare"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    workspace_report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "error-report", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Error Analysis Report" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "cohort=rare" in cli.stdout
    assert workspace_report.returncode == 0, workspace_report.stderr
    assert "Error Analysis Reports" in workspace_report.stdout


def _run_predictions(config: GapForgeConfig, workspace_id: str) -> str:
    payload = {
        "predictions": [
            {"id": "p1", "label": 0, "prediction": 1, "cohort": "rare", "text": "artifact example fp one"},
            {"id": "p2", "label": 0, "prediction": 1, "cohort": "rare", "text": "artifact example fp two"},
            {"id": "p3", "label": 1, "prediction": 1, "cohort": "common", "text": "artifact example tp"},
            {"id": "p4", "label": 1, "prediction": 0, "cohort": "rare", "text": "artifact example fn"},
        ]
    }
    metrics = {"metric_results": [{"metric_id": "false positive rate", "value": 0.5, "sample_size": 2}]}
    return _run_payload(config, workspace_id, predictions=payload, metrics=metrics)


def _run_metrics_only(config: GapForgeConfig, workspace_id: str) -> str:
    metrics = {"metric_results": [{"metric_id": "false positive rate", "value": 0.0, "sample_size": 2}]}
    return _run_payload(config, workspace_id, predictions=None, metrics=metrics)


def _run_payload(config: GapForgeConfig, workspace_id: str, *, predictions: dict[str, object] | None, metrics: dict[str, object]) -> str:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    metrics_path = Path(workspace.root_dir) / "results" / "metrics.json"
    predictions_path = Path(workspace.root_dir) / "results" / "predictions.json"
    script = (
        Path(workspace.root_dir) / "code" / f"write_error_payload_{len(ExperimentWorkspaceManager(config).list_manifests(workspace_id))}.py"
    )
    lines = [
        "from pathlib import Path",
        f"Path({str(metrics_path)!r}).write_text({json.dumps(json.dumps(metrics))} + '\\n', encoding='utf-8')",
    ]
    expected = ["results/metrics.json"]
    if predictions is not None:
        lines.append(f"Path({str(predictions_path)!r}).write_text({json.dumps(json.dumps(predictions))} + '\\n', encoding='utf-8')")
        expected.append("results/predictions.json")
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="main",
        dataset_ids=["dataset-fixture"],
        baseline_ids=["baseline-a"],
        metric_ids=["false positive rate"],
        command=f"{sys.executable} {script}",
        expected_outputs=expected,
        random_seed=1,
    )
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution.id


def _error_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Error Analysis Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-error-analysis",
            direction_id="direction-error-analysis",
            linked_experiment_plan_id="experiment-error-analysis",
            objective="Inspect prediction failures.",
            hypothesis="Prediction artifacts expose failure modes.",
            datasets=["dataset-fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json", "predictions.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-error-analysis")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    return config, workspace.id
