"""Offline v0.8 manuscript, artifact-evaluation, and submission smoke test."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from gapforge import api
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentProtocol, Paper, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v08 import V08ReleaseGateEnforcer
from gapforge.state import ResearchStateManager


def main() -> int:
    config = _smoke_config(Path.cwd())
    config.ensure_dirs()
    _write_prerequisite_gate_docs(config)

    project, workspace_id, dataset_id, baseline_id, metric_id = _create_fixture_workspace(config)
    execution = _run_fixture_result(config, workspace_id, dataset_id, baseline_id, metric_id)
    api.parse_results(execution.execution.id, config=config)
    replication_package = api.export_replication_package(workspace_id, config=config)

    manuscript = _create_manuscript_fixture(
        config,
        project.project.id,
        workspace_id,
        execution.execution.id,
        execution.execution.result_artifact_ids,
    )
    manuscript_id = manuscript.manuscript.id

    api.draft_manuscript(
        manuscript_id,
        sections=["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations", "conclusion"],
        section_links={
            "related_work": {"source_paper_ids": ["paper-v8-smoke"]},
            "results": {
                "source_result_ids": [execution.execution.id],
                "source_artifact_ids": execution.execution.result_artifact_ids,
                "warnings": ["Fixture smoke result only; not a main-result claim."],
            },
            "limitations": {"warnings": ["Smoke fixture does not establish broad benchmark or venue readiness."]},
        },
        claim_uses=[
            {
                "section_type": "related_work",
                "claim_id": "claim-v8-known-paper",
                "claim_text": "Known paper metadata grounds the manuscript citation workflow.",
                "use_type": "background",
                "support_status": "supported",
                "evidence_locators": ["paper-v8-smoke:introduction:p1"],
                "citation_keys": ["lovelace2026scriptable"],
            },
            {
                "section_type": "results",
                "claim_id": "claim-v8-artifact-backed-result",
                "claim_text": "The v0.8 smoke manuscript records an artifact-backed smoke result.",
                "use_type": "result",
                "support_status": "supported",
                "evidence_locators": [],
                "citation_keys": [],
            },
            {
                "section_type": "limitations",
                "claim_id": "claim-v8-smoke-limitation",
                "claim_text": (
                    "The smoke workflow is a fixture validation, not evidence of venue acceptance or broad empirical superiority."
                ),
                "use_type": "limitation",
                "support_status": "supported",
                "evidence_locators": [],
                "citation_keys": [],
            },
        ],
        status="approved",
        config=config,
    )
    bibliography = api.build_bibliography(manuscript_id, config=config)
    rendered = api.render_manuscript(manuscript_id, config=config)
    table_assets = api.generate_manuscript_assets(manuscript_id, table_types=["result_table"], figure_types=["metric_plot"], config=config)
    traceability = api.run_traceability_check(manuscript_id, config=config)
    api.set_venue(manuscript_id, "generic_conference", config=config)
    anonymization = api.anonymize_manuscript(manuscript_id, config=config)
    initial_checklist = api.submission_checklist(manuscript_id, config=config)
    artifact_package = api.create_artifact_eval_package(manuscript_id, config=config)
    review = api.manuscript_review(manuscript_id, config=config)
    revision = api.rebuttal_plan(manuscript_id, config=config)
    submission = api.submission_package(manuscript_id, "review", config=config)
    gate = V08ReleaseGateEnforcer(config).evaluate()
    gate_json, gate_md = V08ReleaseGateEnforcer(config).write_outputs(gate)

    _assert_smoke_success(
        rendered=rendered,
        bibliography_entries=len(bibliography.entries),
        tables=len(table_assets.tables),
        traceability_blockers=traceability.blocking_issues,
        anonymization_status=anonymization.status,
        initial_checklist_status=initial_checklist.status,
        artifact_package_status=artifact_package.status,
        review_reports=len(review.reviewer_reports),
        revision_items=len(revision.rebuttal_items),
        submission_status=submission.status,
        gate_passed=gate.passed,
        gate_blockers=gate.blockers,
    )

    print("v0.8 smoke completed")
    print(f"project: {project.project.id}")
    print(f"workspace: {workspace_id}")
    print(f"execution: {execution.execution.id}")
    print(f"replication package: {replication_package.id}")
    print(f"manuscript: {manuscript_id}")
    print(f"bibliography entries: {len(bibliography.entries)}")
    print(f"result tables: {len(table_assets.tables)}")
    print(f"traceability blockers: {len(traceability.blocking_issues)}")
    print(f"initial checklist: {initial_checklist.status}")
    print(f"artifact evaluation package: {artifact_package.id} status={artifact_package.status}")
    print(f"review reports: {len(review.reviewer_reports)}")
    print(f"rebuttal items: {len(revision.rebuttal_items)} status={revision.status}")
    print(f"submission package: {submission.id} status={submission.status}")
    print(f"v8 release gate: {gate_json} {gate_md}")
    return 0


def _smoke_config(root: Path) -> GapForgeConfig:
    smoke_root = root / "data" / "v8_smoke"
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    return GapForgeConfig(
        root=root,
        runs_dir=smoke_root / "runs",
        project_root=smoke_root / "projects",
        data_dir=smoke_root / "data",
        skills_dir=root / "skills",
        cache_dir=root / ".gapforge_cache",
    )


def _create_fixture_workspace(config: GapForgeConfig):
    project_manager = ProjectMemoryManager(config)
    project = project_manager.create_project("v8 smoke project")
    direction_id = f"direction-v8-smoke-{project.project.id}"
    project.research_directions.append(
        ResearchDirection(
            id=direction_id,
            project_id=project.project.id,
            title="v8 smoke direction",
            summary="Fixture direction for v0.8 manuscript workflow validation.",
            maturity="experiment_ready",
        )
    )
    project.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-v8-smoke",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-v8-smoke",
            objective="Validate manuscript export from artifact-backed fixture results.",
            hypothesis="A local fixture command emits a result artifact that can back manuscript tables.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence interval"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(project)

    workspace = api.create_experiment_workspace(project.project.id, direction_id, config=config)
    dataset_path = Path(workspace.root_dir) / "data" / "v8_fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    dataset = api.register_dataset(
        workspace.id,
        "v8 fixture examples",
        dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="v8 smoke fixture only.",
        config=config,
    )
    baseline = api.register_baseline(
        workspace.id,
        "v8 heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
        config=config,
    )
    metric = api.register_metric(workspace.id, "false positive rate", config=config)
    api.scaffold_experiment_code(workspace.id, config=config)
    return project, workspace.id, dataset.id, baseline.id, metric.id


def _run_fixture_result(
    config: GapForgeConfig,
    workspace_id: str,
    dataset_id: str,
    baseline_id: str,
    metric_id: str,
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "v8_smoke_metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_v8_smoke_metrics.py"
    payload = {
        "metric_results": [
            {
                "metric_id": metric_id,
                "dataset_id": dataset_id,
                "baseline_id": baseline_id,
                "value": 0.01,
                "sample_size": 1000,
                "confidence_interval": [0.0, 0.02],
            }
        ]
    }
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = api.create_experiment_manifest(
        workspace_id,
        run_type="smoke",
        run_name="v8-smoke",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        command=f"{sys.executable} {script}",
        expected_outputs=["results/v8_smoke_metrics.json"],
        random_seed=808,
        config=config,
    )
    return api.run_experiment(workspace_id, manifest_id=manifest.id, config=config)


def _create_manuscript_fixture(
    config: GapForgeConfig,
    project_id: str,
    workspace_id: str,
    execution_id: str,
    artifact_ids: list[str],
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    run = api.create_run("v8 manuscript evidence", project_id=project_id, config=config)
    run.papers = [
        Paper(
            id="paper-v8-smoke",
            title="Scriptable Manuscript Workflows",
            authors=["Ada Lovelace"],
            abstract="Known paper evidence for v0.8 manuscript smoke validation.",
            year=2026,
            venue="FixtureConf",
            doi="10.1000/v8-smoke",
            url="https://example.invalid/v8-smoke",
        )
    ]
    ResearchStateManager(config).save_run(run)
    manuscript = api.create_manuscript(
        project_id,
        workspace.direction_id,
        workspace.id,
        "v8 Smoke Manuscript",
        config=config,
    )
    if not execution_id or not artifact_ids:
        raise RuntimeError("v8 smoke result did not produce an execution id and artifact id.")
    return manuscript


def _write_prerequisite_gate_docs(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text(
        json.dumps({"passed": True, "scope": "v8-smoke-prerequisite"}) + "\n",
        encoding="utf-8",
    )
    v7_json = release_dir / "v0.7_latest.json"
    v7_md = release_dir / "v0.7_latest.md"
    if not v7_json.exists() and not v7_md.exists():
        v7_md.write_text(
            "# v0.7 Gate Documentation\n\n"
            "v8 smoke did not run the v0.7 gate in this target. Run `make v7-smoke` for the fixture v0.7 gate.\n",
            encoding="utf-8",
        )


def _assert_smoke_success(
    *,
    rendered: str,
    bibliography_entries: int,
    tables: int,
    traceability_blockers: list[str],
    anonymization_status: str,
    initial_checklist_status: str,
    artifact_package_status: str,
    review_reports: int,
    revision_items: int,
    submission_status: str,
    gate_passed: bool,
    gate_blockers: list[str],
) -> None:
    if "v8 Smoke Manuscript" not in rendered:
        raise RuntimeError("manuscript draft did not render.")
    if bibliography_entries < 1:
        raise RuntimeError("bibliography did not include known paper records.")
    if tables < 1:
        raise RuntimeError("artifact-backed result table was not generated.")
    if traceability_blockers:
        raise RuntimeError("traceability blockers remain: " + "; ".join(traceability_blockers))
    if anonymization_status not in {"pass", "warning"}:
        raise RuntimeError(f"anonymization did not pass: {anonymization_status}")
    if initial_checklist_status not in {"review_ready", "submission_ready"}:
        raise RuntimeError(f"submission checklist is not reviewable: {initial_checklist_status}")
    if artifact_package_status != "review_ready":
        raise RuntimeError(f"artifact evaluation package is not review-ready: {artifact_package_status}")
    if review_reports < 1:
        raise RuntimeError("manuscript reviewer panel did not produce reviewer reports.")
    if revision_items < 1:
        raise RuntimeError("rebuttal plan did not produce actionable items.")
    if submission_status != "review_ready":
        raise RuntimeError(f"review submission package is not review-ready: {submission_status}")
    if not gate_passed:
        raise RuntimeError("v0.8 release gate did not pass: " + "; ".join(gate_blockers))


if __name__ == "__main__":
    raise SystemExit(main())
