from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import MainPowerManager, SelectedBenchmarkManager
from gapforge.selected_benchmark.main_dataset import MainDatasetBuilder, render_main_trace_dataset_report


def test_main_dataset_built_with_sufficient_count(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=3000, planned_positive_count=500)

    dataset = MainDatasetBuilder(config).build(benchmark_id)

    assert dataset.negative_count == 3000
    assert dataset.positive_count == 500
    assert dataset.alpha_targets_supported["0.001"]["status"] == "supported"
    assert dataset.generation_plan_id == f"main-power-plan-{benchmark_id}"
    assert dataset.hard_negative_count > 0
    assert dataset.observability_mode_counts["action_only"] > 0
    assert dataset.observability_mode_counts["transcript_visible"] > 0
    assert any("Synthetic main dataset" in limitation for limitation in dataset.limitations)


def test_main_dataset_insufficient_count_blocks_alpha_001(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    dataset = MainDatasetBuilder(config).build(benchmark_id, negative_count=300, positive_count=150)

    assert dataset.alpha_targets_supported["0.001"]["status"] == "underpowered"
    assert dataset.alpha_targets_supported["0.001"]["observed_negative_count"] == 300
    assert any("alpha=0.001" in limitation for limitation in dataset.limitations)


def test_main_dataset_feasibility_report_generated_when_count_too_high(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    dataset = MainDatasetBuilder(config).build(benchmark_id, negative_count=11000, positive_count=1000)
    report = MainDatasetBuilder(config).render_report(dataset.id)

    assert dataset.id.startswith("main-trace-dataset-feasibility-")
    assert dataset.negative_count == 11000
    assert dataset.positive_count == 1000
    assert dataset.scenario_coverage == {}
    assert dataset.alpha_targets_supported["0.001"]["status"] == "feasibility_only"
    assert "Feasibility Report" in report
    assert "too expensive" in report


def test_main_dataset_report_renders_and_cli(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=300, planned_positive_count=150)
    manager = MainDatasetBuilder(config)
    dataset = manager.build(benchmark_id)

    rendered = render_main_trace_dataset_report(dataset)

    assert "Main Trace Dataset Report" in rendered
    assert "Scenario Coverage" in rendered
    assert "Synthetic main dataset" in rendered

    build_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "build-main-trace-dataset",
            "--benchmark-id",
            benchmark_id,
            "--negative-count",
            "300",
            "--positive-count",
            "150",
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "main-trace-dataset-report", "--dataset-id", dataset.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert build_cli.returncode == 0, build_cli.stderr
    assert "main-trace-dataset" in build_cli.stdout
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Main Trace Dataset Report" in report_cli.stdout


def _benchmark(tmp_path: Path) -> tuple[object, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id
