from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.benchmarks.comparison import BenchmarkComparisonBuilder, render_benchmark_comparison
from gapforge.benchmarks.leaderboard import LeaderboardBuilder
from gapforge.benchmarks.registry import BenchmarkRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results.database import ResultDatabaseBuilder


def test_compare_proposed_vs_baseline(tmp_path: Path) -> None:
    config, workspace_id, benchmark_id = _comparison_workspace(tmp_path)
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="baseline-required", value=0.3, run_type="main")
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="proposed", value=0.1, run_type="main")
    ResultDatabaseBuilder(config).build(workspace_id)

    comparison = BenchmarkComparisonBuilder(config).compare(workspace_id=workspace_id, benchmark_id=benchmark_id)

    assert comparison.baseline_results
    assert comparison.proposed_method_results
    assert any("proposed vs baseline-required" in item for item in comparison.comparison_metrics)


def test_missing_required_baseline_warning(tmp_path: Path) -> None:
    config, workspace_id, benchmark_id = _comparison_workspace(tmp_path)
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="proposed", value=0.1, run_type="main")
    ResultDatabaseBuilder(config).build(workspace_id)

    comparison = BenchmarkComparisonBuilder(config).compare(workspace_id=workspace_id, benchmark_id=benchmark_id)

    assert "baseline-required" in comparison.missing_baselines
    assert any("Missing required baseline" in limitation for limitation in comparison.limitations)


def test_smoke_result_not_mixed_with_main(tmp_path: Path) -> None:
    config, workspace_id, benchmark_id = _comparison_workspace(tmp_path)
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="baseline-required", value=0.9, run_type="smoke")
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="baseline-required", value=0.3, run_type="main")
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="proposed", value=0.1, run_type="main")
    ResultDatabaseBuilder(config).build(workspace_id)

    rendered = render_benchmark_comparison(BenchmarkComparisonBuilder(config).compare(workspace_id=workspace_id, benchmark_id=benchmark_id))

    assert "Run type `main`" in rendered
    assert "Run type `smoke`" in rendered
    assert "Smoke and pilot results are reported separately" in rendered


def test_sota_claim_blocked_without_evidence(tmp_path: Path) -> None:
    config, workspace_id, benchmark_id = _comparison_workspace(tmp_path)
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="baseline-required", value=0.3, run_type="main")
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="proposed", value=0.1, run_type="main")
    ResultDatabaseBuilder(config).build(workspace_id)

    leaderboard = LeaderboardBuilder(config).build(benchmark_id)
    comparison = BenchmarkComparisonBuilder(config).compare(workspace_id=workspace_id, benchmark_id=benchmark_id)

    assert leaderboard.source == "internal"
    assert any("External leaderboard was not fetched or verified" in item for item in leaderboard.limitations)
    assert any("No SOTA claim" in note for note in comparison.statistical_notes)


def test_benchmark_comparison_report_cli(tmp_path: Path) -> None:
    config, workspace_id, benchmark_id = _comparison_workspace(tmp_path)
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="baseline-required", value=0.3, run_type="main")
    _run_metric(config, workspace_id, benchmark_id=benchmark_id, baseline_id="proposed", value=0.1, run_type="main")
    ResultDatabaseBuilder(config).build(workspace_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    compared = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-compare", "--workspace-id", workspace_id, "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    leaderboard = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "leaderboard-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-comparison-report", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert compared.returncode == 0, compared.stderr
    assert leaderboard.returncode == 0, leaderboard.stderr
    assert report.returncode == 0, report.stderr
    assert "Benchmark Comparison" in compared.stdout
    assert "Leaderboard Report" in leaderboard.stdout
    assert "Benchmark Comparison Reports" in report.stdout


def _run_metric(
    config: GapForgeConfig,
    workspace_id: str,
    *,
    benchmark_id: str,
    baseline_id: str,
    value: float,
    run_type: str,
):
    payload = {
        "metric_results": [
            {
                "benchmark_id": benchmark_id,
                "dataset_id": "dataset-fixture",
                "baseline_id": baseline_id,
                "metric_id": "false positive rate",
                "split": "test",
                "value": value,
                "confidence_interval": [max(0.0, value - 0.05), value + 0.05],
                "sample_size": 100,
            }
        ]
    }
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    suffix = f"{run_type}_{baseline_id}_{len(ExperimentWorkspaceManager(config).list_manifests(workspace_id))}"
    output = Path(workspace.root_dir) / "results" / f"metrics_{suffix}.json"
    script = Path(workspace.root_dir) / "code" / f"write_metrics_{suffix}.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type=run_type,
        dataset_ids=["dataset-fixture"],
        baseline_ids=[baseline_id],
        metric_ids=["false positive rate"],
        command=f"{sys.executable} {script}",
        expected_outputs=[f"results/{output.name}"],
        random_seed=1,
    )
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution


def _comparison_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Benchmark Comparison Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-comparison",
            direction_id="direction-comparison",
            linked_experiment_plan_id="experiment-comparison",
            objective="Compare benchmark results.",
            hypothesis="Proposed methods are compared against required baselines.",
            datasets=["dataset-fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-comparison")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="Fixture Dataset",
        path=_fixture_csv(tmp_path),
        dataset_type="fixture",
        license="CC0",
    )
    baseline = BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="baseline required",
        baseline_type="heuristic",
        implementation_path="code/src/baselines.py",
    )
    metric = MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    benchmark = BenchmarkRegistry(config).register_benchmark(
        workspace_id=workspace.id,
        name="Comparison Benchmark",
        dataset_ids=["dataset-fixture"],
        baseline_ids=[baseline.id],
        metric_ids=[metric.id],
        evaluation_protocol="Lower FPR is better; report run types separately.",
    )
    return config, workspace.id, benchmark.id


def _fixture_csv(tmp_path: Path) -> str:
    path = tmp_path / "fixture.csv"
    path.write_text("label,score\n0,0.1\n1,0.9\n", encoding="utf-8")
    return str(path)
