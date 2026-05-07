from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.revisions import ManuscriptRevisionManager
from gapforge.manuscript.submission import SubmissionPackageExporter
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.manuscript.venues import ManuscriptVenueManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication import ReplicationPackageExporter
from gapforge.results import ResultParser
from gapforge.state import ResearchStateManager


def test_review_package_exported(tmp_path: Path) -> None:
    config, manuscript_id = _submission_package_fixture(tmp_path)

    package = SubmissionPackageExporter(config).export(manuscript_id, "review")
    package_dir = SubmissionPackageExporter(config).package_dir(package.id)

    assert package.package_type == "review"
    assert package.status == "review_ready"
    assert "manuscript.md" in package.files
    assert "checklist_report.md" in package.files
    assert "anonymization_report.md" in package.files
    assert (package_dir / "submission_package.json").exists()


def test_anonymization_required_blocks_anonymous_venue(tmp_path: Path) -> None:
    config, manuscript_id = _submission_package_fixture(tmp_path, anonymized=False)

    package = SubmissionPackageExporter(config).export(manuscript_id, "review")

    assert package.status == "blocked"
    assert "anonymization_report.md" not in package.files


def test_camera_ready_blocked_by_open_rebuttal_items(tmp_path: Path) -> None:
    config, manuscript_id = _submission_package_fixture(tmp_path, unsupported_claim=True, package_type="internal")
    ManuscriptRevisionManager(config).build(manuscript_id)

    package = SubmissionPackageExporter(config).export(manuscript_id, "camera_ready")

    assert package.status == "blocked"


def test_package_includes_bibliography_and_assets(tmp_path: Path) -> None:
    config, manuscript_id = _submission_package_fixture(tmp_path, with_assets=True)

    package = SubmissionPackageExporter(config).export(manuscript_id, "review")

    assert "bibliography/references.bib" in package.files
    assert any(path.startswith("figures/") for path in package.files)
    assert any(path.startswith("tables/") for path in package.files)
    assert "artifact_evaluation/README.md" in package.files
    assert "replication_instructions.md" in package.files


def test_unsupported_claim_blocks_package(tmp_path: Path) -> None:
    config, manuscript_id = _submission_package_fixture(tmp_path, unsupported_claim=True)

    package = SubmissionPackageExporter(config).export(manuscript_id, "review")

    assert package.status == "blocked"


def test_submission_package_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id = _submission_package_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    exported = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "submission-package", "--manuscript-id", manuscript_id, "--type", "review"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    package_id = json.loads(exported.stdout)["id"]

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "submission-package-status", "--package-id", package_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status.returncode == 0, status.stderr
    assert "Submission Package" in status.stdout
    assert "- Status: `review_ready`" in status.stdout


def _submission_package_fixture(
    tmp_path: Path,
    *,
    anonymized: bool = True,
    with_assets: bool = False,
    unsupported_claim: bool = False,
    package_type: str = "review",
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    run = ResearchStateManager(config).create_run("submission package")
    run.papers = [
        Paper(
            id="paper-1",
            title="Submission Package Evidence",
            authors=["Ada Lovelace"],
            abstract="Package evidence.",
            year=2025,
            venue="ICLR",
            doi="10.1000/package",
        )
    ]
    ResearchStateManager(config).save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Submission Package Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-submission-package",
            direction_id="direction-submission-package",
            linked_experiment_plan_id="experiment-submission-package",
            objective="Export a complete submission package.",
            hypothesis="Submission packages are auditable.",
            datasets=["dataset-fixture"],
            metrics=["accuracy"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)

    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-submission-package",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="accuracy")
    execution = _run_metrics(config, workspace.id)
    ReplicationPackageExporter(config).export_workspace(workspace.id)

    manuscript_manager = ManuscriptManager(config)
    state = manuscript_manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-submission-package",
        workspace_id=workspace.id,
        title="Submission Package Draft",
    )
    section_ids: dict[str, str] = {}
    for section_type in [
        "abstract",
        "introduction",
        "related_work",
        "method",
        "experiments",
        "results",
        "limitations",
        "conclusion",
    ]:
        section = manuscript_manager.create_section(
            manuscript_id=state.manuscript.id,
            section_type=section_type,
            title=section_type.replace("_", " ").title(),
            source_paper_ids=["paper-1"] if section_type == "related_work" else [],
            source_result_ids=[execution.id] if section_type == "results" else [],
            source_artifact_ids=execution.result_artifact_ids if section_type == "results" else [],
            status="approved",
        )
        section_ids[section_type] = section.id
    manuscript_manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_ids["related_work"],
        claim_id="claim-background",
        claim_text="Prior work motivates auditable submission packages.",
        use_type="background",
        support_status="supported",
        evidence_locators=["paper-1:p1"],
    )
    manuscript_manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_ids["results"],
        claim_id="claim-result",
        claim_text="The fixture records an artifact-backed accuracy result.",
        use_type="result",
        support_status="supported",
    )
    if unsupported_claim:
        manuscript_manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=section_ids["method"],
            claim_id="claim-unsupported",
            claim_text="The package definitively solves submission.",
            use_type="method",
            support_status="unsupported",
        )
    ManuscriptBibliographyManager(config).build(state.manuscript.id)
    ManuscriptVenueManager(config).set_venue(state.manuscript.id, "generic_conference")
    if anonymized:
        root = manuscript_manager.manuscript_root(state.manuscript.id)
        (root / "submission" / "anonymization.json").write_text(json.dumps({"status": "ready"}) + "\n", encoding="utf-8")
    ArtifactEvaluationPackageExporter(config).export(state.manuscript.id)
    if with_assets:
        ManuscriptTableGenerator(config).generate(state.manuscript.id, "result_table")
        ManuscriptFigureGenerator(config).generate(state.manuscript.id, "metric_plot")
    if package_type == "camera_ready":
        state = manuscript_manager.load_state(state.manuscript.id)
        state.manuscript.status = "camera_ready"
        manuscript_manager._save_state(state)
    return config, state.manuscript.id


def _run_metrics(config: GapForgeConfig, workspace_id: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics_submission_package.json"
    script = Path(workspace.root_dir) / "code" / "write_submission_package_metrics.py"
    payload = {"metric_results": [{"metric_id": "accuracy", "value": 0.81, "sample_size": 12, "dataset_id": "fixture"}]}
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="main",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics_submission_package.json"],
        metric_ids=["accuracy"],
        random_seed=123,
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    ResultParser(config).parse_execution(execution.id)
    return execution
