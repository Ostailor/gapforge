from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.artifact_eval.badges import ArtifactBadgeAssessor
from gapforge.artifact_eval.checklist import ArtifactEvaluationChecklistManager
from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.artifact_eval.runner import ArtifactEvaluationSmokeRunner
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication import ReplicationPackageExporter


def test_artifact_package_exports_review_files(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _artifact_eval_fixture(tmp_path)
    replication = ReplicationPackageExporter(config).export_workspace(workspace_id)

    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)
    package_dir = ArtifactEvaluationPackageExporter(config).package_dir(package.id)

    assert package.status == "review_ready"
    assert package.replication_package_id == replication.id
    assert "replication_package/replication_manifest.json" in package.files
    assert "expected_hashes.json" in package.files
    assert package.install_instructions
    assert package.run_instructions
    assert any("sha256=" in item for item in package.expected_outputs)
    assert (package_dir / "INSTRUCTIONS.md").exists()


def test_checklist_blocks_missing_replication_package(tmp_path: Path) -> None:
    config, manuscript_id, _workspace_id = _artifact_eval_fixture(tmp_path)

    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)
    checklist = ArtifactEvaluationChecklistManager(config).check(package.id)

    assert package.status == "blocked"
    assert checklist.status == "blocked"
    assert checklist.checks["replication_package"] == "fail: missing replication package id"
    assert any("does not reference a replication package" in blocker for blocker in checklist.blockers)


def test_badge_assessment_is_conservative(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _artifact_eval_fixture(tmp_path)
    ReplicationPackageExporter(config).export_workspace(workspace_id)
    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)

    assessments = ArtifactBadgeAssessor(config).assess(package.id)
    by_type = {assessment.badge_type: assessment for assessment in assessments}

    assert by_type["available"].eligible is True
    assert by_type["functional"].eligible is True
    assert by_type["reproducible"].eligible is False
    assert any("smoke dry-run" in blocker for blocker in by_type["reproducible"].blockers)


def test_smoke_runner_dry_run_works(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _artifact_eval_fixture(tmp_path)
    ReplicationPackageExporter(config).export_workspace(workspace_id)
    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)

    record = ArtifactEvaluationSmokeRunner(config).dry_run(package.id)
    assessments = ArtifactBadgeAssessor(config).assess(package.id)

    assert record.status == "planned"
    assert record.commands_run
    assert any(assessment.badge_type == "reproducible" for assessment in assessments)


def test_artifact_eval_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id, workspace_id = _artifact_eval_fixture(tmp_path)
    ReplicationPackageExporter(GapForgeConfig.from_cwd(tmp_path)).export_workspace(workspace_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    exported = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "artifact-eval-package", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    package_id = json.loads(exported.stdout)["id"]

    checked = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "artifact-eval-check", "--package-id", package_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    badges = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "artifact-badges", "--package-id", package_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    smoke = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "artifact-eval-smoke", "--package-id", package_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert checked.returncode == 0, checked.stderr
    assert badges.returncode == 0, badges.stderr
    assert smoke.returncode == 0, smoke.stderr
    assert "Artifact Evaluation Checklist" in checked.stdout
    assert "Artifact Badge Assessments" in badges.stdout
    assert "Reproduction Record" in smoke.stdout


def test_restricted_data_excluded(tmp_path: Path) -> None:
    config, manuscript_id, workspace_id = _artifact_eval_fixture(tmp_path, dataset_type="real", license_name="restricted")
    ReplicationPackageExporter(config).export_workspace(workspace_id)

    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)
    package_dir = ArtifactEvaluationPackageExporter(config).package_dir(package.id)
    checklist = ArtifactEvaluationChecklistManager(config).check(package.id)

    assert package.status == "blocked"
    assert not (package_dir / "replication_package" / "data" / "fixture.csv").exists()
    assert list((package_dir / "replication_package" / "data").glob("*.record.json"))
    assert any("Restricted or real dataset" in blocker for blocker in checklist.blockers)


def _artifact_eval_fixture(
    tmp_path: Path,
    *,
    dataset_type: str = "fixture",
    license_name: str = "MIT",
) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Artifact Eval Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-artifact-eval",
            direction_id="direction-artifact-eval",
            linked_experiment_plan_id="experiment-artifact-eval",
            objective="Export an artifact evaluation package.",
            hypothesis="Artifact packages include safe replication state.",
            datasets=["fixture"],
            metrics=["accuracy"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-artifact-eval",
    )
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,label\n1,0\n2,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture data",
        path=dataset_path,
        dataset_type=dataset_type,
        license=license_name,
        source_url="https://example.test/fixture",
        intended_use="Artifact evaluation fixture.",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="accuracy")
    _run_metrics(config, workspace.id)
    manuscript = ManuscriptManager(config).create_manuscript(
        project_id=program.project.id,
        direction_id="direction-artifact-eval",
        workspace_id=workspace.id,
        title="Artifact Evaluation Draft",
    )
    return config, manuscript.manuscript.id, workspace.id


def _run_metrics(config: GapForgeConfig, workspace_id: str) -> None:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_artifact_eval_metrics.py"
    payload = json.dumps({"metric_results": [{"metric_id": "accuracy", "value": 0.8, "sample_size": 2}]})
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)
