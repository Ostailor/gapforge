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
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, ResearchDirection, to_plain
from gapforge.project_memory import ProjectMemoryManager


def test_v2_package_with_no_results_labels_planned_only(tmp_path: Path) -> None:
    config, workspace_id, _direction_id = _workspace_fixture(tmp_path)

    package = PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    result_summary = Path(workspace.root_dir) / "paper_package_v2" / "result_summary.md"
    readme = Path(workspace.root_dir) / "paper_package_v2" / "README.md"

    assert package.readiness == "planned_experiment"
    assert "planned experiment only" in result_summary.read_text(encoding="utf-8").lower()
    assert "Result state: planned_experiment" in readme.read_text(encoding="utf-8")


def test_v2_package_with_smoke_result_labels_smoke(tmp_path: Path) -> None:
    config, workspace_id, _direction_id = _workspace_fixture(tmp_path)
    _run_workspace(config, workspace_id, run_type="smoke")

    package = PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    execution_records = Path(workspace.root_dir) / "paper_package_v2" / "execution_records.md"
    result_summary = Path(workspace.root_dir) / "paper_package_v2" / "result_summary.md"

    assert package.readiness in {"smoke_result", "paper_ready_empirical"}
    assert "Label: `smoke_result`" in execution_records.read_text(encoding="utf-8")
    assert "Artifact-Backed Empirical Claims" in result_summary.read_text(encoding="utf-8")


def test_v2_package_includes_failed_result(tmp_path: Path) -> None:
    config, workspace_id, _direction_id = _workspace_fixture(tmp_path)
    _run_workspace(config, workspace_id, fail_after_output=True)

    package = PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    negative_results = Path(workspace.root_dir) / "paper_package_v2" / "negative_results.md"

    assert package.readiness == "failed_result"
    assert "failed or negative runs must stay visible" in negative_results.read_text(encoding="utf-8")


def test_v2_empirical_claim_only_with_artifact(tmp_path: Path) -> None:
    config, workspace_id, _direction_id = _workspace_fixture(tmp_path)
    _run_workspace(config, workspace_id, write_output=False)

    PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    claim_ledger = Path(workspace.root_dir) / "paper_package_v2" / "claim_ledger.md"
    result_summary = Path(workspace.root_dir) / "paper_package_v2" / "result_summary.md"

    assert "- none" in claim_ledger.read_text(encoding="utf-8")
    assert "No artifact-backed empirical claims" in result_summary.read_text(encoding="utf-8")


def test_v2_paper_ready_blocked_if_reproducibility_fails(tmp_path: Path) -> None:
    config, workspace_id, _direction_id = _workspace_fixture(tmp_path, include_baseline=False)
    _run_workspace(config, workspace_id)

    package = PaperPackageExporter(config).export_workspace_v2(workspace_id)

    assert package.readiness != "paper_ready_empirical"
    assert any("Reproducibility gate" in item for item in package.missing_requirements)


def test_v2_export_cli_workspace_and_direction(tmp_path: Path) -> None:
    config, workspace_id, direction_id = _workspace_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    by_workspace = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-paper-package-v2", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    by_direction = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-paper-package-v2", "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert by_workspace.returncode == 0, by_workspace.stderr
    assert by_direction.returncode == 0, by_direction.stderr
    assert "Exported v0.6 paper package" in by_workspace.stdout
    assert "Exported v0.6 paper package" in by_direction.stdout


def _workspace_fixture(tmp_path: Path, *, include_baseline: bool = True) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Paper Package v2 Project")
    direction_id = "direction-paper-package-v2"
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-package-v2",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-package-v2",
            objective="Package empirical execution artifacts honestly.",
            hypothesis="Artifact-backed packages distinguish planned, smoke, pilot, main, and failed results.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            statistical_tests=["confidence intervals"],
            expected_artifacts=["metrics.json"],
        )
    )
    program.research_directions = [
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title="Paper Package v2 Direction",
            summary="Tests v0.6 empirical package boundaries.",
            maturity="experiment_ready",
            readiness_score=0.8,
        )
    ]
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture examples",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="Package v2 fixture.",
    )
    if include_baseline:
        BaselineRegistry(config).register_baseline(
            workspace_id=workspace.id,
            name="heuristic baseline",
            baseline_type="heuristic",
            code_available=True,
            implementation_path="code/src/baselines.py",
        )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    return config, workspace.id, direction_id


def _run_workspace(
    config: GapForgeConfig,
    workspace_id: str,
    *,
    run_type: str = "smoke",
    write_output: bool = True,
    fail_after_output: bool = False,
) -> str:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_package_v2_metrics.py"
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
            "from pathlib import Path\n"
            f"Path({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n"
            + ("raise SystemExit(2)\n" if fail_after_output else ""),
            encoding="utf-8",
        )
    else:
        script.write_text("print('no result artifact')\n", encoding="utf-8")
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace_id,
        run_type=run_type,
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    return execution.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
