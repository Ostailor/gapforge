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
from gapforge.results import (
    ResultStatisticsAnalyzer,
    binomial_confidence_interval,
    bootstrap_confidence_interval,
    render_analysis_report_markdown,
)


def test_binomial_confidence_interval_contains_rate() -> None:
    interval = binomial_confidence_interval(successes=1, total=100)

    assert len(interval) == 2
    assert 0.0 <= interval[0] <= 0.01 <= interval[1] <= 1.0


def test_bootstrap_confidence_interval_is_deterministic() -> None:
    interval = bootstrap_confidence_interval([0.2, 0.4, 0.6, 0.8])

    assert interval == [0.2, 0.8]


def test_low_fpr_sample_warning_and_computed_ci(tmp_path: Path) -> None:
    config, workspace_id = _statistics_workspace(tmp_path)
    manifest = _metric_manifest(
        config,
        workspace_id,
        {"metric_results": [{"metric_id": "false positive rate", "value": 0.05, "sample_size": 20}]},
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    report = ResultStatisticsAnalyzer(config).analyze_execution(execution.id)

    assert report.metric_analyses[0].confidence_method == "wilson_binomial"
    assert len(report.metric_analyses[0].confidence_interval) == 2
    assert any("low-FPR-related" in warning for warning in report.low_fpr_power_warnings)


def test_analysis_report_renders_and_writes_artifacts(tmp_path: Path) -> None:
    config, workspace_id = _statistics_workspace(tmp_path)
    manifest = _metric_manifest(
        config,
        workspace_id,
        {"metric_results": [{"metric_id": "recall", "value": 0.8, "sample_size": 50}]},
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    report = ResultStatisticsAnalyzer(config).analyze_execution(execution.id)
    markdown = render_analysis_report_markdown(report)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    reports = Path(workspace.root_dir) / "reports"

    assert "Metric Uncertainty" in markdown
    assert "wilson_binomial" in markdown
    assert (reports / f"analysis_report_{execution.id}.json").exists()
    assert (reports / f"analysis_report_{execution.id}.md").exists()
    assert (reports / "analysis_report.json").exists()


def test_workspace_analysis_handles_missing_data(tmp_path: Path) -> None:
    config, workspace_id = _statistics_workspace(tmp_path)

    report = ResultStatisticsAnalyzer(config).analyze_workspace(workspace_id)

    assert report.metric_analyses == []
    assert any("No experiment executions" in warning for warning in report.warnings)


def test_statistics_cli_commands(tmp_path: Path) -> None:
    config, workspace_id = _statistics_workspace(tmp_path)
    manifest = _metric_manifest(
        config,
        workspace_id,
        {"metric_results": [{"metric_id": "false positive rate", "value": 0.01, "sample_size": 100}]},
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    analyze = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "analyze-results", "--execution-id", execution.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    low_fpr = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "low-fpr-power-check", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert analyze.returncode == 0, analyze.stderr
    assert low_fpr.returncode == 0, low_fpr.stderr
    assert "Statistical Analysis Report" in analyze.stdout
    assert "Low-FPR Power Warnings" in low_fpr.stdout


def _metric_manifest(config: GapForgeConfig, workspace_id: str, payload: dict[str, object]):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_statistics_metrics.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )


def _statistics_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Statistics Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-statistics",
            direction_id="direction-statistics",
            linked_experiment_plan_id="experiment-statistics",
            objective="Analyze artifact-backed metric uncertainty.",
            hypothesis="Metric artifacts can be analyzed conservatively.",
            datasets=["fixture"],
            metrics=["false positive rate", "recall"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-statistics")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="recall")
    return config, workspace.id
