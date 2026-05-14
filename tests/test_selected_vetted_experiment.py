from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_benchmark_adapters import _register_fixture_dataset
from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import SelectedBenchmarkManager, SelectedVettedBenchmarkExperimentManager
from gapforge.selected_benchmark.vetted_mapping import SelectedBenchmarkVettedMappingManager
from gapforge.vetted_benchmarks import VettedBenchmarkRegistry


def test_selected_vetted_experiment_plan_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_direct_vetted_fixture(config, dataset_id)
    SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)

    plan = SelectedVettedBenchmarkExperimentManager(config).create_plan(spec.id)

    assert plan.selected_benchmark_id == spec.id
    assert plan.run_type == "vetted_adapter"
    assert len(plan.adapter_ids) == 1
    assert "vetted_adapted_example_count" in plan.metric_ids
    assert any("separate from synthetic" in item for item in plan.limitations)


def test_fixture_adapter_experiment_runs(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_direct_vetted_fixture(config, dataset_id)
    SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    manager = SelectedVettedBenchmarkExperimentManager(config)
    plan = manager.create_plan(spec.id)

    result = manager.run_plan(plan.id)

    assert result.experiment_plan_id == plan.id
    assert len(result.execution_ids) == 1
    assert any(metric["metric_id"] == "vetted_adapted_example_count" for metric in result.metric_results)
    assert any(metric["value"] == 2 for metric in result.metric_results if metric["metric_id"] == "vetted_adapted_example_count")


def test_vetted_and_synthetic_results_are_separated_and_labeled(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_direct_vetted_fixture(config, dataset_id)
    SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    manager = SelectedVettedBenchmarkExperimentManager(config)
    plan = manager.create_plan(spec.id)

    result = manager.run_plan(plan.id)

    assert result.metric_results
    assert all(metric["result_source"] == "vetted_adapter" for metric in result.metric_results)
    assert all(metric["synthetic"] is False for metric in result.metric_results)
    assert all(metric["do_not_merge_with_synthetic"] is True for metric in result.metric_results)
    assert result.comparison_tables[0]["rows"][0]["synthetic_result_count"] == 0


def test_auxiliary_benchmark_limitation_appears(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="Rare Event Specificity Benchmark",
        domain="anomaly detection",
        benchmark_type="dataset",
        task_types=["rare event false positive specificity"],
        dataset_ids=[dataset_id],
        metric_ids=["false-positive-rate"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="widely_used",
    )
    SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    manager = SelectedVettedBenchmarkExperimentManager(config)
    plan = manager.create_plan(spec.id)
    result = manager.run_plan(plan.id)
    report = manager.render_report(plan.id)

    assert any("manuscript must label it auxiliary" in item for item in result.limitations)
    assert "manuscript must label it auxiliary" in report
    assert "mapping `auxiliary`" in report


def test_selected_vetted_experiment_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_direct_vetted_fixture(config, dataset_id)
    SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)

    planned = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-vetted-experiment-plan", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert planned.returncode == 0, planned.stderr
    plan_id = json.loads(planned.stdout)["id"]

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-vetted-experiment-run", "--plan-id", plan_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-vetted-experiment-report", "--plan-id", plan_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["metric_results"][0]["result_source"] == "vetted_adapter"
    assert report.returncode == 0, report.stderr
    assert "Selected Vetted Benchmark Experiment Report" in report.stdout
    assert "must not be merged with synthetic metrics" in report.stdout


def _register_direct_vetted_fixture(config, dataset_id: str):
    return VettedBenchmarkRegistry(config).register(
        name="Sequential Low-FPR Collusion Monitoring Trace Benchmark",
        domain="multi-agent collusion monitoring",
        benchmark_type="benchmark",
        task_types=["sequential low-FPR collusion monitor audit trace"],
        dataset_ids=[dataset_id],
        metric_ids=["specificity", "false-positive-rate"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="canonical",
    )
