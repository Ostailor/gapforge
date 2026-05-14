from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.vetted_benchmarks import BenchmarkAdapterRegistry, VettedBenchmarkRegistry


def test_adapter_created_for_vetted_benchmark(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_vetted_fixture(config, dataset_id)

    adapter = BenchmarkAdapterRegistry(config).create_adapter(
        selected_benchmark_id=spec.id,
        vetted_benchmark_id=vetted.id,
    )

    assert adapter.selected_benchmark_id == spec.id
    assert adapter.vetted_benchmark_id == vetted.id
    assert adapter.adapter_type in {"trace_conversion", "label_mapping"}
    assert adapter.output_schema["adapter_id"] == "string"
    assert any("must not be called real collusion traces" in item for item in adapter.limitations)


def test_adapter_run_on_fixture_preserves_labels_and_splits(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_vetted_fixture(config, dataset_id)
    registry = BenchmarkAdapterRegistry(config)
    adapter = registry.create_adapter(selected_benchmark_id=spec.id, vetted_benchmark_id=vetted.id)

    run = registry.run_adapter(adapter.id)
    payload = json.loads((config.data_dir / "vetted_benchmarks" / "adapter_runs" / run.id / "adapted_trace_units.json").read_text())

    assert run.status == "complete"
    assert payload["preserved_fields"]["original_labels_preserved"] is True
    assert payload["preserved_fields"]["original_splits_preserved"] is True
    assert [item["original_label"] for item in payload["examples"]] == ["benign", "unsafe"]
    assert [item["original_split"] for item in payload["examples"]] == ["train", "test"]


def test_adapter_generates_limitation_warning_for_non_collusion_source(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = VettedBenchmarkRegistry(config).register(
        name="Generic Safety Prompt Benchmark",
        domain="safety monitoring",
        benchmark_type="dataset",
        task_types=["prompt classification"],
        dataset_ids=[dataset_id],
        metric_ids=["accuracy"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="widely_used",
    )
    registry = BenchmarkAdapterRegistry(config)
    adapter = registry.create_adapter(selected_benchmark_id=spec.id, vetted_benchmark_id=vetted.id)

    run = registry.run_adapter(adapter.id)

    assert any("must not be described as real collusion traces" in warning for warning in run.warnings)


def test_adapter_report_renders_claim_guardrails(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_vetted_fixture(config, dataset_id)
    registry = BenchmarkAdapterRegistry(config)
    adapter = registry.create_adapter(selected_benchmark_id=spec.id, vetted_benchmark_id=vetted.id)
    registry.run_adapter(adapter.id)

    report = registry.render_report(adapter.id)

    assert "Benchmark Adapter" in report
    assert "Claim Guardrail" in report
    assert "Do not call adapted data real collusion traces" in report
    assert "Warnings" in report


def test_benchmark_adapter_cli_create_run_report(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset_id = _register_fixture_dataset(config, selected_project_id)
    vetted = _register_vetted_fixture(config, dataset_id)

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "benchmark-adapter-create",
            "--selected-benchmark-id",
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
    assert created.returncode == 0, created.stderr
    adapter_id = json.loads(created.stdout)["id"]

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-adapter-run", "--adapter-id", adapter_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-adapter-report", "--adapter-id", adapter_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["status"] == "complete"
    assert report.returncode == 0, report.stderr
    assert "Claim Guardrail" in report.stdout


def _register_fixture_dataset(config, selected_project_id: str) -> str:
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=selected_project_id,
        direction_id="direction-adapter-fixture",
    )
    fixture = Path(workspace.root_dir) / "adapter_source.csv"
    fixture.write_text(
        "text,label,split\nRoutine assistant exchange,benign,train\nPolicy-violating request,unsafe,test\n",
        encoding="utf-8",
    )
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="Adapter Fixture Dataset",
        path=fixture,
        dataset_type="fixture",
        description="Fixture benchmark substrate for adapter tests.",
        source="fixture",
        license="MIT",
        intended_use="Adapter transformation tests.",
    )
    return dataset.id


def _register_vetted_fixture(config, dataset_id: str):
    return VettedBenchmarkRegistry(config).register(
        name="Agent Conversation Trace Benchmark",
        domain="multi-agent safety monitoring",
        benchmark_type="dataset",
        task_types=["conversation trace monitor evaluation"],
        dataset_ids=[dataset_id],
        metric_ids=["false-positive-rate"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="widely_used",
    )
