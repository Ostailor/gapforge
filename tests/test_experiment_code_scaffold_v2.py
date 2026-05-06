from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code.scaffold_v2 import ExperimentCodeScaffolderV2
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import BaselineCandidate, ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_scaffold_experiment_code_creates_runnable_layout(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_registries(tmp_path)

    code_root = ExperimentCodeScaffolderV2(config).scaffold(workspace_id)

    assert (code_root / "pyproject.toml").exists()
    assert (code_root / "README.md").exists()
    assert (code_root / "src" / "__init__.py").exists()
    assert (code_root / "src" / "data.py").exists()
    assert (code_root / "src" / "baselines.py").exists()
    assert (code_root / "src" / "metrics.py").exists()
    assert (code_root / "src" / "run_experiment.py").exists()
    assert (code_root / "configs" / "smoke.json").exists()
    assert (code_root / "configs" / "pilot.json").exists()
    assert (code_root / "scripts" / "run_smoke.sh").exists()
    assert "No experiment results" in (code_root / "README.md").read_text(encoding="utf-8")


def test_scaffold_includes_smoke_tests_and_metrics_run(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_registries(tmp_path)
    code_root = ExperimentCodeScaffolderV2(config).scaffold(workspace_id)

    result = ExperimentCodeScaffolderV2(config).validate(workspace_id)

    assert (code_root / "tests" / "test_metrics.py").exists()
    assert (code_root / "tests" / "test_baselines.py").exists()
    assert (code_root / "tests" / "test_data.py").exists()
    assert result.status == "valid"
    assert result.smoke_returncode == 0
    assert "smoke_only" in result.stdout
    assert "not run" in result.stdout


def test_scaffold_does_not_generate_fake_results(tmp_path: Path) -> None:
    config, workspace_id = _workspace_with_registries(tmp_path)
    code_root = ExperimentCodeScaffolderV2(config).scaffold(workspace_id)

    assert not (code_root / "results.json").exists()
    assert not (code_root / "results").exists()
    manifest = json.loads((code_root / "SCAFFOLD_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["results"] == "not run"
    assert manifest["fixture_data"] is True


def test_experiment_code_cli_lifecycle(tmp_path: Path) -> None:
    _config, workspace_id = _workspace_with_registries(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    scaffolded = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "scaffold-experiment-code", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-code-status", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    validation = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "experiment-code-validate", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert scaffolded.returncode == 0, scaffolded.stderr
    assert status.returncode == 0, status.stderr
    assert validation.returncode == 0, validation.stderr
    assert "Missing expected files: 0" in status.stdout
    assert "Status: `valid`" in validation.stdout


def _workspace_with_registries(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Experiment Code Scaffold Project")
    protocol = ExperimentProtocol(
        id="protocol-code-v2",
        direction_id="direction-code-v2",
        linked_experiment_plan_id="experiment-code-v2",
        objective="Smoke-test low-FPR experiment code wiring.",
        hypothesis="The detector can be evaluated at fixed low false-positive rate.",
        datasets=["fixture monitoring examples"],
        baselines=[
            BaselineCandidate(
                paper_id="paper-baseline",
                baseline_name="Threshold monitor",
                why_required="Needed for smoke comparison wiring.",
            )
        ],
        metrics=["false positive rate", "recall"],
        expected_artifacts=["metrics.json"],
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-code-v2",
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
    return config, workspace.id
