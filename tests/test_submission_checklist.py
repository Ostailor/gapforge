from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager
from gapforge.manuscript.venues import ManuscriptVenueManager, list_venue_templates
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results import ResultParser
from gapforge.state import ResearchStateManager


def test_venue_templates_list(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    template_ids = {template.id for template in list_venue_templates()}
    cli_ids = {item["id"] for item in json.loads(listed.stdout)}
    assert listed.returncode == 0, listed.stderr
    assert {"generic_conference", "generic_workshop", "arxiv_preprint", "ml_conference_like", "artifact_evaluation_like"} <= template_ids
    assert template_ids == cli_ids


def test_checklist_blocks_missing_bibliography(tmp_path: Path) -> None:
    config, manuscript_id = _complete_submission_fixture(tmp_path, build_bibliography=False)

    checklist = SubmissionChecklistManager(config).build(manuscript_id)

    assert checklist.status == "not_ready"
    assert checklist.checks["bibliography"] == "fail: bibliography not built"
    assert "Bibliography has not been built." in checklist.blocking_issues


def test_checklist_blocks_unsupported_claims(tmp_path: Path) -> None:
    config, manuscript_id = _complete_submission_fixture(tmp_path)
    state = ManuscriptManager(config).load_state(manuscript_id)
    section = next(item for item in state.sections if item.section_type == "method")
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section.id,
        claim_id="claim-unsupported",
        claim_text="The method definitively solves venue submission readiness.",
        use_type="method",
        support_status="unsupported",
    )

    checklist = SubmissionChecklistManager(config).build(manuscript_id)

    assert checklist.status == "not_ready"
    assert checklist.checks["claim_traceability"].startswith("fail:")
    assert any("Soften the claim" in issue or "Add evidence" in issue for issue in checklist.blocking_issues)


def test_checklist_passes_complete_fixture(tmp_path: Path) -> None:
    config, manuscript_id = _complete_submission_fixture(tmp_path)

    checklist = SubmissionChecklistManager(config).build(manuscript_id)

    assert checklist.status == "submission_ready"
    assert checklist.blocking_issues == []
    assert checklist.checks["required_sections"] == "pass"
    assert checklist.checks["bibliography"] == "pass"
    assert checklist.checks["citations_valid"] == "pass"
    assert checklist.checks["claim_traceability"] == "pass"
    assert checklist.checks["result_artifacts"] == "pass"
    assert checklist.checks["anonymization"] == "pass"


def test_arxiv_template_less_strict_than_conference_template(tmp_path: Path) -> None:
    config, manuscript_id = _complete_submission_fixture(tmp_path, anonymized=False)

    conference = SubmissionChecklistManager(config).build(manuscript_id)
    ManuscriptVenueManager(config).set_venue(manuscript_id, "arxiv_preprint")
    preprint = SubmissionChecklistManager(config).build(manuscript_id)

    assert conference.status == "not_ready"
    assert any("requires anonymization" in issue for issue in conference.blocking_issues)
    assert preprint.status == "submission_ready"
    assert preprint.checks["anonymization"] == "pass: not required"


def test_submission_checklist_cli_and_set_venue(tmp_path: Path) -> None:
    _config, manuscript_id = _complete_submission_fixture(tmp_path, set_venue=False)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    set_venue = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-set-venue",
            "--manuscript-id",
            manuscript_id,
            "--venue",
            "generic_conference",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    checklist = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "submission-checklist", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert set_venue.returncode == 0, set_venue.stderr
    assert json.loads(set_venue.stdout)["target_venue"] == "generic_conference"
    assert checklist.returncode == 0, checklist.stderr
    assert "Submission Checklist" in checklist.stdout
    assert "- Status: `submission_ready`" in checklist.stdout


def _complete_submission_fixture(
    tmp_path: Path,
    *,
    build_bibliography: bool = True,
    anonymized: bool = True,
    set_venue: bool = True,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    run = ResearchStateManager(config).create_run("submission checklist")
    run.papers = [
        Paper(
            id="paper-1",
            title="Submission Traceability",
            authors=["Ada Lovelace"],
            abstract="Traceable submission readiness.",
            year=2025,
            venue="ICLR",
            doi="10.1000/submission",
            url="https://example.test/submission",
        )
    ]
    ResearchStateManager(config).save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Submission Checklist Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-submission",
            direction_id="direction-submission",
            linked_experiment_plan_id="experiment-submission",
            objective="Create venue-aware submission checklists.",
            hypothesis="Submission readiness is blocked by unsupported manuscript state.",
            datasets=["dataset-fixture"],
            metrics=["accuracy"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-submission",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="accuracy")
    execution = _run_result(config, workspace.id)

    manuscript_manager = ManuscriptManager(config)
    state = manuscript_manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-submission",
        workspace_id=workspace.id,
        title="Submission Ready Draft",
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
        claim_text="Prior work motivates traceable submission readiness.",
        use_type="background",
        support_status="supported",
        evidence_locators=["paper-1:p1"],
    )
    manuscript_manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_ids["results"],
        claim_id="claim-result",
        claim_text="The artifact-backed fixture records an accuracy result.",
        use_type="result",
        support_status="supported",
    )
    if build_bibliography:
        ManuscriptBibliographyManager(config).build(state.manuscript.id)
    if set_venue:
        ManuscriptVenueManager(config).set_venue(state.manuscript.id, "generic_conference")
    if anonymized:
        root = manuscript_manager.manuscript_root(state.manuscript.id)
        (root / "submission" / "anonymization.json").write_text(json.dumps({"status": "ready"}) + "\n", encoding="utf-8")
    return config, state.manuscript.id


def _run_result(config: GapForgeConfig, workspace_id: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics_submission.json"
    script = Path(workspace.root_dir) / "code" / "write_submission_metrics.py"
    payload = {
        "metric_results": [
            {
                "metric_id": "accuracy",
                "value": 0.77,
                "sample_size": 10,
                "dataset_id": "dataset-fixture",
            }
        ]
    }
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="main",
        metric_ids=["accuracy"],
        command=f"{sys.executable} {script}",
        expected_outputs=[str(output.relative_to(workspace.root_dir))],
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    ResultParser(config).parse_execution(execution.id)
    return execution
