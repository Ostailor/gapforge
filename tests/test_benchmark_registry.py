from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.benchmarks import BenchmarkRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.metrics import MetricRegistry
from gapforge.models import BaselineCandidate, ExperimentProtocol, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager


def test_register_benchmark_and_render_card(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset, baseline, metric = _register_dependencies(config, workspace_id)
    registry = BenchmarkRegistry(config)

    record = registry.register_benchmark(
        workspace_id=workspace_id,
        name="Low FPR Fixture Benchmark",
        description="Tiny benchmark for low-FPR workflow checks.",
        domain="ai_safety",
        task_type="detection",
        dataset_ids=[dataset.id],
        baseline_ids=[baseline.id],
        metric_ids=[metric.id],
        license="CC0",
        expected_splits=["test"],
        evaluation_protocol="Report FPR with confidence intervals.",
    )
    card = registry.render_card(record.id)
    records = registry.list_benchmarks(workspace_id)

    assert record.task_type == "detection"
    assert record.dataset_ids == [dataset.id]
    assert records[0].id == record.id
    assert "Benchmark Card" in card
    assert "Low FPR Fixture Benchmark" in card
    assert "Fixture benchmark" in card


def test_create_benchmark_suite_and_status(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset, baseline, metric = _register_dependencies(config, workspace_id)
    registry = BenchmarkRegistry(config)
    record = registry.register_benchmark(
        workspace_id=workspace_id,
        name="Suite Benchmark",
        dataset_ids=[dataset.id],
        baseline_ids=[baseline.id],
        metric_ids=[metric.id],
        evaluation_protocol="Run test split.",
    )
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)

    suite = registry.create_suite(
        project_id=workspace.project_id,
        name="Low FPR Suite",
        benchmark_ids=[record.id],
        required_tasks=["benchmark-task-suite-benchmark"],
        source_profile="ai_safety",
    )
    status = registry.suite_status(suite.id)

    assert suite.benchmark_ids == [record.id]
    assert "Benchmark Suite" in status
    assert "Readiness Blockers" in status
    assert "- none" in status


def test_missing_required_metric_blocks_benchmark_readiness(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Benchmark Dataset",
        path=_fixture_csv(tmp_path),
        dataset_type="benchmark",
        license="CC0",
    )
    registry = BenchmarkRegistry(config)
    record = registry.register_benchmark(
        workspace_id=workspace_id,
        name="Missing Metric Benchmark",
        dataset_ids=[dataset.id],
        metric_ids=["metric-does-not-exist"],
    )

    blockers = registry.readiness_blockers(workspace_id)

    assert f"Benchmark `{record.id}` references missing metric `metric-does-not-exist`." in blockers


def test_fixture_benchmark_is_labeled(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Fixture Dataset",
        path=_fixture_csv(tmp_path),
        dataset_type="fixture",
        license="CC0",
    )
    metric = MetricRegistry(config).register_metric(workspace_id=workspace_id, name="false positive rate")
    registry = BenchmarkRegistry(config)

    record = registry.register_benchmark(
        workspace_id=workspace_id,
        name="Fixture Benchmark",
        dataset_ids=[dataset.id],
        metric_ids=[metric.id],
    )
    listing = Path(ExperimentWorkspaceManager(config).load_workspace(workspace_id).root_dir) / "reports" / "benchmark_registry.md"

    assert record.domain == "fixture"
    assert "Fixture benchmark: workflow validation only." in record.limitations
    assert "Benchmark label: `fixture`" in listing.read_text(encoding="utf-8")


def test_benchmark_card_appears_in_paper_package_v2(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset, baseline, metric = _register_dependencies(config, workspace_id)
    registry = BenchmarkRegistry(config)
    registry.register_benchmark(
        workspace_id=workspace_id,
        name="Package Benchmark",
        dataset_ids=[dataset.id],
        baseline_ids=[baseline.id],
        metric_ids=[metric.id],
        evaluation_protocol="Run fixture split.",
    )

    package = PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    benchmarks_md = Path(workspace.root_dir) / "paper_package_v2" / "benchmarks.md"

    assert "benchmarks.md" in package.files
    assert "Package Benchmark" in benchmarks_md.read_text(encoding="utf-8")


def test_benchmark_cli_register_card_list_suite(tmp_path: Path) -> None:
    config, workspace_id = _benchmark_workspace(tmp_path)
    dataset, baseline, metric = _register_dependencies(config, workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "benchmark-register",
            "--workspace-id",
            workspace_id,
            "--name",
            "CLI Benchmark",
            "--dataset-id",
            dataset.id,
            "--baseline-id",
            baseline.id,
            "--metric-id",
            metric.id,
            "--expected-split",
            "test",
            "--task-type",
            "detection",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert registered.returncode == 0, registered.stderr
    benchmark_id = json.loads(registered.stdout)["id"]

    card = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-card", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    listing = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-list", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    suite = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "benchmark-suite-create",
            "--project-id",
            workspace.project_id,
            "--name",
            "CLI Suite",
            "--benchmark-id",
            benchmark_id,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert suite.returncode == 0, suite.stderr
    suite_id = json.loads(suite.stdout)["id"]
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-suite-status", "--suite-id", suite_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert card.returncode == 0, card.stderr
    assert listing.returncode == 0, listing.stderr
    assert status.returncode == 0, status.stderr
    assert "Benchmark Card" in card.stdout
    assert "CLI Benchmark" in listing.stdout
    assert "Benchmark Suite" in status.stdout


def _register_dependencies(config: GapForgeConfig, workspace_id: str):
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Fixture Evaluation Data",
        path=_fixture_csv(config.root),
        dataset_type="fixture",
        license="CC0",
    )
    baseline = BaselineRegistry(config).register_baseline(
        workspace_id=workspace_id,
        name="Heuristic Baseline",
        baseline_type="heuristic",
        implementation_path="code/src/baselines.py",
    )
    metric = MetricRegistry(config).register_metric(workspace_id=workspace_id, name="false positive rate")
    return dataset, baseline, metric


def _benchmark_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Benchmark Registry Project")
    direction = ResearchDirection(
        id="direction-1",
        project_id=program.project.id,
        title="Benchmark-ready direction",
        summary="Evaluate detector behavior on an explicit benchmark.",
        maturity="experiment_ready",
    )
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id="direction-1",
        linked_experiment_plan_id="experiment-1",
        objective="Evaluate benchmark registry integration.",
        hypothesis="Explicit benchmark records improve reporting.",
        datasets=["fixture"],
        baselines=[BaselineCandidate(paper_id="paper-1", baseline_name="baseline")],
        metrics=["false positive rate"],
    )
    program.research_directions.append(direction)
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-1")
    return config, workspace.id


def _fixture_csv(base_dir: Path) -> Path:
    path = base_dir / "fixture.csv"
    path.write_text("text,label,split\nalpha,0,test\nbeta,1,test\n", encoding="utf-8")
    return path
