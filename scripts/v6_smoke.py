"""Run a local, fixture-only v0.6 experiment execution smoke workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gapforge import api
from gapforge.config import GapForgeConfig
from gapforge.models import ExperimentProtocol, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager


def main() -> int:
    config = GapForgeConfig.from_cwd()
    project = api.create_project("v6 smoke project", config=config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(project.project.id)
    direction_id = f"direction-v6-smoke-{program.project.id}"
    program.research_directions.append(
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title="v6 smoke direction",
            summary="Fixture direction for v0.6 smoke validation.",
            maturity="experiment_ready",
        )
    )
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-v6-smoke",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-v6-smoke",
            objective="Validate v0.6 experiment execution plumbing.",
            hypothesis="A fixture command emits artifact-backed metrics.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence interval"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)

    workspace = api.create_experiment_workspace(program.project.id, direction_id, config=config)
    workspace_root = Path(workspace.root_dir)
    dataset_path = workspace_root / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    dataset = api.register_dataset(
        workspace.id,
        "fixture examples",
        dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="v6 smoke fixture only.",
        config=config,
    )
    baseline = api.register_baseline(
        workspace.id,
        "heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
        config=config,
    )
    metric = api.register_metric(workspace.id, "false positive rate", config=config)
    api.scaffold_experiment_code(workspace.id, config=config)

    success = _run_success(config, workspace.id, workspace_root, dataset.id, baseline.id, metric.id)
    summary = api.parse_results(success.execution.id, config=config)
    analysis = api.analyze_results(execution_id=success.execution.id, config=config)
    reproducibility = api.reproducibility_check(execution_id=success.execution.id, config=config)
    review = api.empirical_review(execution_id=success.execution.id, config=config)
    failed = _run_failure(config, workspace.id, workspace_root)
    package = api.export_paper_package_v2(workspace_id=workspace.id, config=config)
    gate = api.v6_release_gate(config=config)

    if success.execution.status != "complete":
        raise SystemExit(f"successful fixture execution did not complete: {success.execution.failure_reason}")
    if failed.execution.status != "failed":
        raise SystemExit("failed fixture execution was not recorded as failed")
    if not summary.metric_results or not summary.empirical_claims:
        raise SystemExit("successful fixture execution did not produce parsed metric results and empirical claims")

    print(
        json.dumps(
            {
                "project_id": program.project.id,
                "workspace_id": workspace.id,
                "success_execution_id": success.execution.id,
                "failed_execution_id": failed.execution.id,
                "analysis_id": analysis.id,
                "reproducibility_status": reproducibility.status,
                "empirical_review_fatal_flaws": len(review.fatal_flaws),
                "paper_package_id": package.id,
                "v6_release_gate_passed": gate.passed,
                "v6_release_gate_status": gate.status,
                "v6_release_gate_blockers": gate.blockers,
            },
            indent=2,
        )
    )
    return 0


def _run_success(
    config: GapForgeConfig,
    workspace_id: str,
    workspace_root: Path,
    dataset_id: str,
    baseline_id: str,
    metric_id: str,
):
    success_output = workspace_root / "results" / "smoke_metrics.json"
    success_script = workspace_root / "code" / "write_smoke_metrics.py"
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
    metrics_json = json.dumps(payload)
    success_script.write_text(
        f"from pathlib import Path\nPath({str(success_output)!r}).write_text({metrics_json!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    success_manifest = api.create_experiment_manifest(
        workspace_id,
        run_type="smoke",
        run_name="v6-smoke-success",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        command=f"{sys.executable} {success_script}",
        expected_outputs=["results/smoke_metrics.json"],
        random_seed=123,
        config=config,
    )
    return api.run_experiment(workspace_id, manifest_id=success_manifest.id, config=config)


def _run_failure(config: GapForgeConfig, workspace_id: str, workspace_root: Path):
    failure_script = workspace_root / "code" / "fail_smoke.py"
    failure_script.write_text("raise SystemExit(2)\n", encoding="utf-8")
    failure_manifest = api.create_experiment_manifest(
        workspace_id,
        run_type="smoke",
        run_name="v6-smoke-failure",
        command=f"{sys.executable} {failure_script}",
        expected_outputs=["results/missing_metrics.json"],
        random_seed=456,
        config=config,
    )
    return api.run_experiment(workspace_id, manifest_id=failure_manifest.id, config=config)


if __name__ == "__main__":
    raise SystemExit(main())
