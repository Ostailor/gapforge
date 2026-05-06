from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code import ExperimentCodeScaffolderV2
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, to_plain
from gapforge.project_memory import ProjectMemoryManager


def test_complete_fixture_passes_reproducibility_check(tmp_path: Path) -> None:
    config, workspace_id, execution_id = _reproducible_execution(tmp_path)

    result = ReproducibilityChecker(config).check_execution(execution_id)

    assert result.status == "pass"
    assert result.blockers == []
    assert result.warnings == []
    assert result.checks["dataset_cards"] == "pass"
    assert result.checks["result_artifacts_hashed"] == "pass"


def test_missing_seed_warns(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _reproducible_execution(tmp_path, random_seed=0)

    result = ReproducibilityChecker(config).check_execution(execution_id)

    assert result.status == "warning"
    assert any("random seed" in warning for warning in result.warnings)


def test_missing_dataset_card_fails(tmp_path: Path) -> None:
    config, workspace_id, execution_id = _reproducible_execution(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    for path in (Path(workspace.root_dir) / "data" / "cards").glob("*.card.json"):
        path.unlink()

    result = ReproducibilityChecker(config).check_execution(execution_id)

    assert result.status == "fail"
    assert any("Dataset card is missing" in blocker for blocker in result.blockers)


def test_missing_result_artifact_fails(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _reproducible_execution(tmp_path, write_output=False)

    result = ReproducibilityChecker(config).check_execution(execution_id)

    assert result.status == "fail"
    assert any("No result artifacts" in blocker or "Expected output" in blocker for blocker in result.blockers)


def test_fake_data_label_required(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _reproducible_execution(
        tmp_path,
        dataset_name="fake generated examples",
        dataset_type="unknown",
    )

    result = ReproducibilityChecker(config).check_execution(execution_id)

    assert result.status == "fail"
    assert any("appears fixture/synthetic/generated" in blocker for blocker in result.blockers)


def test_reproducibility_check_cli(tmp_path: Path) -> None:
    _config, workspace_id, execution_id = _reproducible_execution(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    by_execution = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproducibility-check", "--execution-id", execution_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    by_workspace = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproducibility-check", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert by_execution.returncode == 0, by_execution.stderr
    assert by_workspace.returncode == 0, by_workspace.stderr
    assert "Reproducibility Check" in by_execution.stdout
    assert "Status: `pass`" in by_workspace.stdout


def _reproducible_execution(
    tmp_path: Path,
    *,
    random_seed: int = 123,
    write_output: bool = True,
    dataset_name: str = "fixture examples",
    dataset_type: str = "fixture",
) -> tuple[GapForgeConfig, str, str]:
    config, workspace_id = _workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name=dataset_name,
        path=dataset_path,
        dataset_type=dataset_type,
        license="MIT",
        intended_use="Fixture smoke validation.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace_id,
        name="heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace_id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_repro_metrics.py"
    if write_output:
        payload = json.dumps(
            {
                "metric_results": [
                    {
                        "metric_id": "false positive rate",
                        "value": 0.01,
                        "sample_size": 1000,
                        "confidence_interval": [0.0, 0.02],
                    }
                ]
            }
        )
        script.write_text(
            f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
    else:
        script.write_text("print('no result artifact')\n", encoding="utf-8")
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=random_seed,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    return config, workspace_id, execution.id


def _workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Reproducibility Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-reproducibility",
            direction_id="direction-reproducibility",
            linked_experiment_plan_id="experiment-reproducibility",
            objective="Audit experiment reproducibility.",
            hypothesis="Complete artifacts should pass reproducibility checks.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-reproducibility",
    )
    return config, workspace.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
