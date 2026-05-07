from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results import ResultParser


def test_result_table_generated_from_result_artifact(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _manuscript_workspace(tmp_path)
    execution = _run_metric_artifact(config, workspace_id, run_type="smoke", baseline_id="baseline-a", value=0.72)

    table = ManuscriptTableGenerator(config).generate(manuscript_id, "result_table")
    table_path = ManuscriptManager(config).manuscript_root(manuscript_id) / table.path
    content = table_path.read_text(encoding="utf-8")

    assert table.source_result_ids == [execution.id]
    assert table.source_artifact_ids == execution.result_artifact_ids
    assert "| Execution | Run type | Status | Metric | Value | Sample size | Artifact | Limitations |" in content
    assert "`smoke`" in content
    assert "0.72" in content
    assert "Smoke and pilot rows are not presented as main results." in table.caption


def test_baseline_comparison_table_generated_from_artifacts(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _manuscript_workspace(tmp_path)
    _run_metric_artifact(config, workspace_id, run_type="main", baseline_id="baseline-a", value=0.61)
    _run_metric_artifact(config, workspace_id, run_type="main", baseline_id="baseline-b", value=0.75)

    table = ManuscriptTableGenerator(config).generate(manuscript_id, "baseline_comparison")
    content = (ManuscriptManager(config).manuscript_root(manuscript_id) / table.path).read_text(encoding="utf-8")

    assert len(table.source_artifact_ids) == 2
    assert "`baseline-a`" in content
    assert "`baseline-b`" in content
    assert "`main`" in content
    assert "Artifact-backed baseline comparison" in table.caption


def test_no_result_artifact_blocks_table_generation(tmp_path: Path) -> None:
    config, manuscript_id, _workspace_id = _manuscript_workspace(tmp_path)

    with pytest.raises(ValueError, match="No result artifacts"):
        ManuscriptTableGenerator(config).generate(manuscript_id, "result_table")


def test_captions_include_run_type_labels(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _manuscript_workspace(tmp_path)
    _run_metric_artifact(config, workspace_id, run_type="pilot", baseline_id="baseline-a", value=0.44)

    table = ManuscriptTableGenerator(config).generate(manuscript_id, "result_table")
    figure = ManuscriptFigureGenerator(config).generate(manuscript_id, "metric_plot")

    assert "Run type labels visible: pilot" in table.caption
    assert "Run type labels visible: pilot" in figure.caption
    assert "not main-result evidence" in figure.caption


def test_failed_run_table_generated_for_appendix_evidence(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _manuscript_workspace(tmp_path)
    execution = _run_metric_artifact(
        config,
        workspace_id,
        run_type="pilot",
        baseline_id="baseline-a",
        value=0.0,
        fail_after_artifact=True,
    )

    table = ManuscriptTableGenerator(config).generate(manuscript_id, "result_table")
    content = (ManuscriptManager(config).manuscript_root(manuscript_id) / table.path).read_text(encoding="utf-8")

    assert execution.status == "failed"
    assert "`failed`" in content
    assert "`pilot`" in content
    assert "Failed runs are included as failure rows." in table.caption


def test_metric_plot_and_asset_list_are_artifact_backed(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _manuscript_workspace(tmp_path)
    execution = _run_metric_artifact(config, workspace_id, run_type="smoke", baseline_id="baseline-a", value=0.81)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    generated = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-figure",
            "--manuscript-id",
            manuscript_id,
            "--type",
            "metric_plot",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assets = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-assets", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert generated.returncode == 0, generated.stderr
    figure = json.loads(generated.stdout)
    assert figure["source_artifact_ids"] == execution.result_artifact_ids
    assert (ManuscriptManager(config).manuscript_root(manuscript_id) / figure["path"]).exists()
    assert assets.returncode == 0, assets.stderr
    listed = json.loads(assets.stdout)
    assert listed["figures"][0]["id"] == figure["id"]


def _run_metric_artifact(
    config: GapForgeConfig,
    workspace_id: str,
    *,
    run_type: str,
    baseline_id: str,
    value: float,
    fail_after_artifact: bool = False,
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / f"metrics_{run_type}_{baseline_id}.json"
    script = Path(workspace.root_dir) / "code" / f"write_{run_type}_{baseline_id}.py"
    payload = {
        "metric_results": [
            {
                "metric_id": "accuracy",
                "value": value,
                "sample_size": 12,
                "baseline_id": baseline_id,
                "dataset_id": "dataset-fixture",
            }
        ]
    }
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n"
        + ("raise SystemExit(2)\n" if fail_after_artifact else ""),
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type=run_type,
        baseline_ids=[baseline_id],
        metric_ids=["accuracy"],
        command=f"{sys.executable} {script}",
        expected_outputs=[str(output.relative_to(workspace.root_dir))],
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    ResultParser(config).parse_execution(execution.id)
    return execution


def _manuscript_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Manuscript Assets Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-assets",
            direction_id="direction-assets",
            linked_experiment_plan_id="experiment-assets",
            objective="Generate artifact-backed manuscript assets.",
            hypothesis="Result artifacts can render conservative tables and figures.",
            datasets=["dataset-fixture"],
            metrics=["accuracy"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-assets")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="accuracy")
    state = ManuscriptManager(config).create_manuscript(
        project_id=program.project.id,
        direction_id="direction-assets",
        workspace_id=workspace.id,
        title="Artifact Backed Manuscript",
    )
    return config, state.manuscript.id, workspace.id
