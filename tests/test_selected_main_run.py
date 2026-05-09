from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.models import to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import MainDatasetBuilder, MainPowerManager, MonitorBaselineManager, SelectedBenchmarkManager
from gapforge.selected_benchmark.main_run import MainRunManager, render_selected_main_status


def test_selected_main_manifest_generated(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=300, planned_positive_count=50)
    dataset = MainDatasetBuilder(config).build(benchmark_id)

    manifest = MainRunManager(config).create_manifest(benchmark_id, dataset.id)

    assert manifest.benchmark_id == benchmark_id
    assert manifest.dataset_id == dataset.id
    assert manifest.run_type == "main"
    assert manifest.synthetic_data_label == "synthetic_main_data"
    assert manifest.alpha_targets_supported["0.01"]["status"] == "supported"
    assert manifest.alpha_targets_supported["0.001"]["status"] == "underpowered"
    assert "metrics_json" in manifest.expected_outputs
    assert manifest.calibration_record_ids


def test_fixture_main_run_executes_and_writes_artifacts(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=60, planned_positive_count=20)
    dataset = MainDatasetBuilder(config).build(benchmark_id)
    manager = MainRunManager(config)
    manifest = manager.create_manifest(benchmark_id, dataset.id)

    execution = manager.run(benchmark_id, manifest.id)

    assert execution.run_type == "main"
    assert execution.status == "complete"
    assert execution.publication_claim_blocked is True
    assert execution.metric_result_count > 0
    assert execution.monitor_run_ids
    for key in ["metrics_json", "predictions_json", "baseline_comparison", "error_analysis", "low_fpr_report_json"]:
        assert key in execution.output_paths
        assert Path(execution.output_paths[key]).exists()
    metrics = json.loads(Path(execution.output_paths["metrics_json"]).read_text(encoding="utf-8"))
    predictions = json.loads(Path(execution.output_paths["predictions_json"]).read_text(encoding="utf-8"))
    assert metrics["run_type"] == "main"
    assert predictions["run_type"] == "main"


def test_missing_required_baseline_blocks_publication_claim(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=60, planned_positive_count=20)
    baselines = [
        baseline
        for baseline in MonitorBaselineManager(config).create_baselines(benchmark_id)
        if baseline.baseline_type != "permutation_null_distribution_detector"
    ]
    _write_baselines(config, project_id, baselines)
    dataset = MainDatasetBuilder(config).build(benchmark_id)
    manager = MainRunManager(config)

    execution = manager.run(benchmark_id, manager.create_manifest(benchmark_id, dataset.id).id)

    assert execution.publication_claim_blocked is True
    assert any("permutation_null_distribution_detector" in blocker for blocker in execution.publication_blockers)


def test_powered_alpha_status_recorded(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=3000, planned_positive_count=20)
    dataset = MainDatasetBuilder(config).build(benchmark_id)

    manifest = MainRunManager(config).create_manifest(benchmark_id, dataset.id)

    assert manifest.alpha_targets_supported["0.001"]["status"] == "supported"
    assert manifest.powered_alpha_levels == ["0.001", "0.01"]


def test_selected_main_status_report_renders_and_cli(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=60, planned_positive_count=20)
    dataset = MainDatasetBuilder(config).build(benchmark_id)
    manifest_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-main-manifest",
            "--benchmark-id",
            benchmark_id,
            "--dataset-id",
            dataset.id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert manifest_cli.returncode == 0, manifest_cli.stderr
    manifest_payload = json.loads(manifest_cli.stdout)
    run_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-main-run",
            "--benchmark-id",
            benchmark_id,
            "--manifest-id",
            manifest_payload["id"],
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert run_cli.returncode == 0, run_cli.stderr
    execution_payload = json.loads(run_cli.stdout)
    execution = MainRunManager(config).status(execution_payload["id"])

    rendered = render_selected_main_status(execution)

    assert "Selected Main Benchmark Status" in rendered
    assert "Publication claim blocked" in rendered
    assert "Synthetic traces do not establish deployment validity" in rendered

    status_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-main-status", "--execution-id", execution.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert status_cli.returncode == 0, status_cli.stderr
    assert "Selected Main Benchmark Status" in status_cli.stdout


def _benchmark(tmp_path: Path) -> tuple[object, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _write_baselines(config: object, selected_project_id: str, baselines: list[object]) -> None:
    project_root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)  # type: ignore[arg-type]
    registry_path = project_root / "selected_benchmark" / "monitor_baselines.json"
    registry_path.write_text(json.dumps(to_plain(baselines), indent=2) + "\n", encoding="utf-8")
