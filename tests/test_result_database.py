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
from gapforge.results.aggregate import ResultAggregator
from gapforge.results.database import ResultDatabaseBuilder, render_result_table_markdown


def test_result_db_from_fixture_results(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    execution = _run_metric(config, workspace_id, run_type="main", seed=1, value=0.1)

    table = ResultDatabaseBuilder(config).build(workspace_id)

    assert len(table.rows) == 1
    row = table.rows[0]
    assert row.execution_id == execution.id
    assert row.benchmark_id == "benchmark-low-fpr"
    assert row.dataset_id == "dataset-fixture"
    assert row.baseline_id == "baseline-a"
    assert row.metric_id.startswith("metric-false-positive-rate")
    assert row.run_type == "main"
    assert row.seed == 1


def test_aggregate_across_seeds(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    _run_metric(config, workspace_id, run_type="main", seed=1, value=0.1)
    _run_metric(config, workspace_id, run_type="main", seed=2, value=0.3)
    ResultDatabaseBuilder(config).build(workspace_id)

    aggregates = ResultAggregator(config).aggregate(workspace_id)

    assert len(aggregates) == 1
    assert aggregates[0].n == 2
    assert aggregates[0].seeds == [1, 2]
    assert aggregates[0].mean == 0.2
    assert aggregates[0].std > 0


def test_smoke_and_main_are_separated_by_default(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    _run_metric(config, workspace_id, run_type="smoke", seed=1, value=0.9)
    _run_metric(config, workspace_id, run_type="main", seed=2, value=0.1)
    ResultDatabaseBuilder(config).build(workspace_id)

    default_aggregates = ResultAggregator(config).aggregate(workspace_id)
    with_smoke = ResultAggregator(config).aggregate(workspace_id, include_smoke=True)

    assert default_aggregates[0].mean == 0.1
    assert default_aggregates[0].n == 1
    assert len(with_smoke) == 2


def test_failed_run_excluded_from_aggregate_but_listed(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    _run_metric(config, workspace_id, run_type="main", seed=1, value=0.2)
    _run_failed(config, workspace_id)

    table = ResultDatabaseBuilder(config).build(workspace_id)
    aggregates = ResultAggregator(config).aggregate(workspace_id)
    rendered = render_result_table_markdown(table)

    assert len(table.rows) == 1
    assert len(aggregates) == 1
    assert "failed" in rendered.lower()
    assert "execution-" in rendered


def test_results_export_csv(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    _run_metric(config, workspace_id, run_type="main", seed=1, value=0.1)
    ResultDatabaseBuilder(config).build(workspace_id)

    csv_path = ResultDatabaseBuilder(config).export_csv(workspace_id)

    text = csv_path.read_text(encoding="utf-8")
    assert "workspace_id,execution_id,benchmark_id" in text
    assert "benchmark-low-fpr" in text


def test_results_db_cli(tmp_path: Path) -> None:
    config, workspace_id = _result_db_workspace(tmp_path)
    _run_metric(config, workspace_id, run_type="main", seed=1, value=0.1)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    built = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "results-db-build", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    table = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "results-table", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    aggregate = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "results-aggregate", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert built.returncode == 0, built.stderr
    assert table.returncode == 0, table.stderr
    assert aggregate.returncode == 0, aggregate.stderr
    assert "Result Table" in table.stdout
    assert "Aggregate Results" in aggregate.stdout


def _run_metric(config: GapForgeConfig, workspace_id: str, *, run_type: str, seed: int, value: float):
    payload = {
        "metric_results": [
            {
                "benchmark_id": "benchmark-low-fpr",
                "dataset_id": "dataset-fixture",
                "baseline_id": "baseline-a",
                "metric_id": "false positive rate",
                "split": "test",
                "value": value,
                "confidence_interval": [max(0.0, value - 0.05), value + 0.05],
                "sample_size": 100,
            }
        ]
    }
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / f"metrics_{run_type}_{seed}.json"
    script = Path(workspace.root_dir) / "code" / f"write_metrics_{run_type}_{seed}.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type=run_type,
        run_name=f"{run_type} seed {seed}",
        dataset_ids=["dataset-fixture"],
        baseline_ids=["baseline-a"],
        metric_ids=["false positive rate"],
        command=f"{sys.executable} {script}",
        expected_outputs=[f"results/{output.name}"],
        random_seed=seed,
    )
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution


def _run_failed(config: GapForgeConfig, workspace_id: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "failed_run.py"
    script.write_text("raise SystemExit(3)\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="main",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/missing_metrics.json"],
        random_seed=9,
    )
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution


def _result_db_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Result DB Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-result-db",
            direction_id="direction-result-db",
            linked_experiment_plan_id="experiment-result-db",
            objective="Aggregate fixture benchmark results.",
            hypothesis="Seeded result artifacts can be compared.",
            datasets=["dataset-fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-result-db")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    return config, workspace.id
