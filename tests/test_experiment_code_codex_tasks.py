from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code.codex_tasks import ExperimentCodeTaskManager
from gapforge.experiment_code.scaffold_v2 import ExperimentCodeScaffolderV2
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import BaselineCandidate, ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_experiment_code_task_pack_generated(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_code(tmp_path)

    task = ExperimentCodeTaskManager(config).create_task(workspace_id=workspace_id, task_type="implement_metric")
    task_dir = Path(task.task_dir)

    assert (task_dir / "TASK.md").exists()
    assert (task_dir / "experiment_protocol.json").exists()
    assert (task_dir / "metric_definitions.json").exists()
    assert (task_dir / "dataset_cards").is_dir()
    assert (task_dir / "baseline_cards").is_dir()
    assert "experiment_code_patch.json" in (task_dir / "OUTPUT_CONTRACT.md").read_text(encoding="utf-8")


def test_experiment_code_handoff_includes_import_command(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_code(tmp_path)
    manager = ExperimentCodeTaskManager(config)
    task = manager.create_task(workspace_id=workspace_id, task_type="debug_smoke_run")

    handoff = manager.write_handoff(task.id)
    text = handoff.read_text(encoding="utf-8")

    assert f"gapforge experiment-code-import --task-id {task.id}" in text
    assert task.outputs_dir in text
    assert "Do not invent datasets" in text


def test_fake_implementation_patch_imports_under_workspace_code(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_code(tmp_path)
    manager = ExperimentCodeTaskManager(config)
    task = manager.create_task(workspace_id=workspace_id, task_type="implement_metric")
    code_root = Path(task.code_root)
    metrics_text = (code_root / "src" / "metrics.py").read_text(encoding="utf-8") + "\n# Codex implementation note: smoke-safe.\n"
    output = Path(task.outputs_dir) / "experiment_code_patch.json"
    output.write_text(json.dumps({"files": [{"path": "src/metrics.py", "content": metrics_text}]}), encoding="utf-8")
    mirrored_output = Path(task.outputs_dir) / "files" / "src" / "metrics.py"
    mirrored_output.parent.mkdir(parents=True)
    mirrored_output.write_text(metrics_text + "# duplicate mirror should be ignored when patch JSON exists.\n", encoding="utf-8")

    result = manager.import_outputs(task.id)

    assert result.status == "applied"
    assert result.applied_files == ["src/metrics.py"]
    assert "Codex implementation note" in (code_root / "src" / "metrics.py").read_text(encoding="utf-8")
    assert result.smoke_returncode == 0


def test_invalid_path_outside_workspace_rejected(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_code(tmp_path)
    manager = ExperimentCodeTaskManager(config)
    task = manager.create_task(workspace_id=workspace_id, task_type="implement_metric")
    output = Path(task.outputs_dir) / "experiment_code_patch.json"
    output.write_text(json.dumps({"files": [{"path": "../outside.py", "content": "print('bad')"}]}), encoding="utf-8")

    result = manager.import_outputs(task.id)

    assert result.status == "rejected"
    assert "../outside.py" in result.rejected_files
    assert any("workspace/code" in issue for issue in result.issues)


def test_fake_results_rejected(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_code(tmp_path)
    manager = ExperimentCodeTaskManager(config)
    task = manager.create_task(workspace_id=workspace_id, task_type="analyze_results")
    output = Path(task.outputs_dir) / "experiment_code_patch.json"
    output.write_text(
        json.dumps({"files": [{"path": "src/run_experiment.py", "content": "RESULTS = {'accuracy': 0.99}\n"}]}),
        encoding="utf-8",
    )

    result = manager.import_outputs(task.id)

    assert result.status == "rejected"
    assert result.rejected_files == ["src/run_experiment.py"]
    assert any("fake result metrics" in issue for issue in result.issues)


def test_experiment_code_task_cli_roundtrip(tmp_path: Path) -> None:
    _config, workspace_id = _workspace_with_code(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "experiment-code-task",
            "--workspace-id",
            workspace_id,
            "--type",
            "implement_metric",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    task_id = json.loads(created.stdout)["id"]
    handoff = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-code-handoff", "--task-id", task_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert handoff.returncode == 0, handoff.stderr
    assert Path(handoff.stdout.strip()).exists()


def _workspace_with_code(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Experiment Code Task Project")
    protocol = ExperimentProtocol(
        id="protocol-code-task",
        direction_id="direction-code-task",
        linked_experiment_plan_id="experiment-code-task",
        objective="Implement smoke-safe low-FPR experiment code.",
        hypothesis="The detector can be evaluated without fabricating results.",
        datasets=["fixture monitoring examples"],
        baselines=[
            BaselineCandidate(
                paper_id="paper-baseline",
                baseline_name="Threshold monitor",
                why_required="Needed for implementation wiring.",
            )
        ],
        metrics=["false positive rate", "recall"],
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-code-task",
    )
    dataset_path = tmp_path / "fixture.csv"
    dataset_path.write_text("id,label,score,split\n1,0,0.1,smoke\n2,1,0.9,smoke\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="Fixture monitoring examples",
        path=dataset_path,
        dataset_type="fixture",
        license="test fixture",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="Threshold monitor",
        baseline_type="heuristic",
        implementation_path="src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="recall")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    return config, workspace.id
