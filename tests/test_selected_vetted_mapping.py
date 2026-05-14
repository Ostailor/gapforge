from __future__ import annotations

import json
import subprocess
import sys

from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.vetted_mapping import SelectedBenchmarkVettedMappingManager
from gapforge.vetted_benchmarks import VettedBenchmarkRegistry


def test_direct_mapping_fixture(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="Sequential Low-FPR Collusion Monitoring Benchmark",
        domain="multi-agent collusion monitoring",
        source_url="https://example.org/direct",
        benchmark_type="benchmark",
        task_types=["sequential low-FPR monitor evasion audit"],
        metric_ids=["specificity", "false-positive-rate"],
        license="CC-BY-4.0",
        terms_of_use="Research use with attribution.",
        vetted_status="canonical",
    )

    report = SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    mapping = report.mappings[0]

    assert mapping.mapping_type == "direct"
    assert mapping.recommended_experiment_role == "primary"
    assert vetted.id in report.primary_candidate_ids
    assert any("Sequential monitor" in item for item in mapping.what_maps)
    assert "Does not by itself validate the new sequential specificity benchmark." in mapping.unsupported_claims


def test_auxiliary_mapping_fixture(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="Rare Event Anomaly Specificity Benchmark",
        domain="anomaly detection",
        source_url="https://example.org/anomaly",
        benchmark_type="dataset",
        task_types=["rare event false positive specificity"],
        metric_ids=["false-positive-rate"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="widely_used",
    )

    report = SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    mapping = report.mappings[0]

    assert mapping.mapping_type == "auxiliary"
    assert mapping.recommended_experiment_role == "auxiliary"
    assert vetted.id in report.auxiliary_candidate_ids
    assert "Does not directly evaluate the full low-FPR collusion-audit contribution." in mapping.unsupported_claims


def test_rejected_mapping_fixture(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="Static Image Classification Benchmark",
        domain="computer vision",
        source_url="https://example.org/images",
        benchmark_type="dataset",
        task_types=["single image classification"],
        metric_ids=["accuracy"],
        license="CC0",
        terms_of_use="Public domain.",
        vetted_status="canonical",
    )

    report = SelectedBenchmarkVettedMappingManager(config).map_benchmarks(spec.id, vetted_benchmark_id=vetted.id)
    mapping = report.mappings[0]

    assert mapping.mapping_type == "rejected"
    assert mapping.recommended_experiment_role == "not_recommended"
    assert vetted.id in report.rejected_candidate_ids
    assert mapping.supported_claims == []
    assert any("Does not directly support collusion" in item for item in mapping.unsupported_claims)


def test_mapping_report_renders_and_keeps_unsupported_claims_visible(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    VettedBenchmarkRegistry(config).register(
        name="Safety Monitor Calibration Benchmark",
        domain="safety monitoring",
        source_url="https://example.org/safety",
        benchmark_type="benchmark",
        task_types=["monitor baseline calibration"],
        metric_ids=["false-positive-rate"],
        license="Apache-2.0",
        terms_of_use="Open research use.",
        vetted_status="emerging",
    )
    manager = SelectedBenchmarkVettedMappingManager(config)

    manager.map_benchmarks(spec.id)
    rendered = manager.render_report(spec.id)

    assert "Selected Benchmark Vetted Benchmark Mapping" in rendered
    assert "Unsupported Claims" in rendered
    assert "Manuscript Limitation Feed" in rendered
    assert "new benchmark protocol" in rendered


def test_selected_vetted_mapping_cli(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="CLI Sequential Monitor Benchmark",
        domain="multi-agent monitoring",
        source_url="https://example.org/cli",
        benchmark_type="benchmark",
        task_types=["sequential low-FPR monitor audit"],
        metric_ids=["specificity"],
        license="CC-BY-4.0",
        terms_of_use="Research use with attribution.",
        vetted_status="widely_used",
    )

    mapped = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-vetted-benchmark-map",
            "--benchmark-id",
            spec.id,
            "--vetted-benchmark-id",
            vetted.id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert mapped.returncode == 0, mapped.stderr
    payload = json.loads(mapped.stdout)
    assert payload["mappings"][0]["mapping_type"] == "direct"

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-vetted-benchmark-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.returncode == 0, report.stderr
    assert "Selected Benchmark Vetted Benchmark Mapping" in report.stdout
    assert "Unsupported Claims" in report.stdout
