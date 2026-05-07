from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager
from gapforge.manuscript.reviewer_panel import ManuscriptReviewPanelBuilder
from gapforge.manuscript.submission import SubmissionPackageExporter
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.manuscript.venues import ManuscriptVenueManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v08 import V08ReleaseGateEnforcer, render_v08_release_gate_markdown
from gapforge.replication import ReplicationPackageExporter
from gapforge.results import ResultParser
from gapforge.state import ResearchStateManager


def test_v08_release_gate_no_manuscript_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_release_prerequisites(config)

    result = V08ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["manuscript_project_created"] is False
    assert "No manuscript project was found." in result.blockers


def test_v08_release_gate_unsupported_claim_fails(tmp_path: Path) -> None:
    config, manuscript_id = _complete_v08_fixture(tmp_path)
    state = ManuscriptManager(config).load_state(manuscript_id)
    method = next(section for section in state.sections if section.section_type == "method")
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=method.id,
        claim_id="claim-unsupported-v8",
        claim_text="The submission package proves unmatched readiness.",
        use_type="method",
        support_status="unsupported",
    )
    ManuscriptTraceabilityAuditor(config).audit(manuscript_id)
    SubmissionPackageExporter(config).export(manuscript_id, "review")

    result = V08ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["unsupported_claims_blocked"] is False
    assert any("Unsupported manuscript claims remain" in blocker for blocker in result.blockers)


def test_v08_release_gate_fake_citation_fails(tmp_path: Path) -> None:
    config, manuscript_id = _complete_v08_fixture(tmp_path)
    state = ManuscriptManager(config).load_state(manuscript_id)
    intro = next(section for section in state.sections if section.section_type == "introduction")
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=intro.id,
        claim_id="claim-fake-citation",
        claim_text="Fake citation should be blocked.",
        use_type="background",
        support_status="supported",
        citation_keys=["Imaginary Paper 2026"],
    )
    SubmissionPackageExporter(config).export(manuscript_id, "review")

    result = V08ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["fake_citations_blocked"] is False
    assert any("fake-looking citation" in blocker.lower() for blocker in result.blockers)


def test_v08_release_gate_no_artifact_package_fails(tmp_path: Path) -> None:
    config, manuscript_id = _complete_v08_fixture(tmp_path)
    root = ManuscriptManager(config).manuscript_root(manuscript_id)
    for path in root.glob("artifact_evaluation/*/artifact_evaluation_package.json"):
        path.unlink()

    result = V08ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["artifact_evaluation_package_generated"] is False


def test_v08_release_gate_complete_fixture_passes(tmp_path: Path) -> None:
    config, _manuscript_id = _complete_v08_fixture(tmp_path)
    enforcer = V08ReleaseGateEnforcer(config)

    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)
    rendered = render_v08_release_gate_markdown(result)

    assert result.passed is True
    assert all(result.requirements.values())
    assert "v0.8 Manuscript Release Gate" in rendered
    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    assert "Submission package" in md_path.read_text(encoding="utf-8")


def test_v08_release_gate_camera_ready_blocked_by_open_fatal_review_item(tmp_path: Path) -> None:
    config, manuscript_id = _complete_v08_fixture(tmp_path, package_type="camera_ready")
    revision = ManuscriptRebuttalManager(config).build(manuscript_id)
    assert revision.rebuttal_items
    ManuscriptRebuttalManager(config).mark_item(revision.rebuttal_items[0].id, "open")
    SubmissionPackageExporter(config).export(manuscript_id, "camera_ready")

    result = V08ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["camera_ready_rebuttal_blockers_addressed"] is False
    assert any("camera-ready" in blocker.lower() for blocker in result.blockers)


def test_v08_release_gate_cli_json(tmp_path: Path) -> None:
    config, _manuscript_id = _complete_v08_fixture(tmp_path)
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    completed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v8-release-gate", "--json"],
        cwd=config.root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["passed"] is True


def _complete_v08_fixture(tmp_path: Path, *, package_type: str = "review") -> tuple[GapForgeConfig, str]:
    config, manuscript_id = _submission_package_fixture(tmp_path, with_assets=True)
    _write_release_prerequisites(config)
    ManuscriptFigureGenerator(config).generate(manuscript_id, "metric_plot")
    ManuscriptTableGenerator(config).generate(manuscript_id, "result_table")
    ManuscriptTraceabilityAuditor(config).audit(manuscript_id)
    ManuscriptReviewPanelBuilder(config).review(manuscript_id)
    revision = ManuscriptRebuttalManager(config).build(manuscript_id)
    for item in revision.rebuttal_items:
        ManuscriptRebuttalManager(config).mark_item(item.id, "addressed")
    if package_type == "camera_ready":
        state = ManuscriptManager(config).load_state(manuscript_id)
        state.manuscript.status = "camera_ready"
        ManuscriptManager(config)._save_state(state)
    SubmissionPackageExporter(config).export(manuscript_id, package_type)
    return config, manuscript_id


def _write_release_prerequisites(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true}\n', encoding="utf-8")
    (release_dir / "v0.7_latest.json").write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _submission_package_fixture(
    tmp_path: Path,
    *,
    anonymized: bool = True,
    with_assets: bool = False,
    unsupported_claim: bool = False,
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
    from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter

    ArtifactEvaluationPackageExporter(config).export(state.manuscript.id)
    if with_assets:
        ManuscriptTableGenerator(config).generate(state.manuscript.id, "result_table")
        ManuscriptFigureGenerator(config).generate(state.manuscript.id, "metric_plot")
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
