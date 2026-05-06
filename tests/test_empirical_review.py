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
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.empirical import EmpiricalReviewBuilder, render_empirical_review_markdown


def test_missing_baseline_flagged_as_fatal(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _empirical_execution(tmp_path, include_baseline=False)

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)

    assert any("No baseline" in flaw for flaw in panel.fatal_flaws)
    assert any(review.role == "empirical_rigor" and review.fatal_flaws for review in panel.reviewer_reviews)


def test_no_result_artifact_is_fatal(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _empirical_execution(tmp_path, write_output=False)

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)

    assert any("No result artifact" in flaw for flaw in panel.fatal_flaws)
    assert any("Remove or mark empirical result claims as unsupported" in item for item in panel.result_claim_softening_recommendations)


def test_failed_experiment_not_accepted_as_success(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _empirical_execution(tmp_path, fail_after_output=True)

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)

    assert any("execution failed" in flaw.lower() for flaw in panel.fatal_flaws)
    assert any("failed or inconclusive" in item for item in panel.result_claim_softening_recommendations)


def test_low_fpr_missing_ci_flagged_as_major(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _empirical_execution(tmp_path, include_ci=False)

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)
    statistics_review = next(review for review in panel.reviewer_reviews if review.role == "statistics")

    assert not statistics_review.fatal_flaws
    assert any("Low-FPR metrics are missing confidence intervals" in weakness for weakness in statistics_review.weaknesses)
    assert any("confidence intervals" in fix for fix in statistics_review.required_fixes)


def test_empirical_review_report_renders_and_cli(tmp_path: Path) -> None:
    config, workspace_id, execution_id = _empirical_execution(tmp_path)

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)
    markdown = render_empirical_review_markdown(panel)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "empirical-review", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Empirical Review Panel" in markdown
    assert (Path(workspace.root_dir) / "reports" / "empirical_review.md").exists()
    assert result.returncode == 0, result.stderr
    assert "Empirical Review Panel" in result.stdout


def _empirical_execution(
    tmp_path: Path,
    *,
    include_baseline: bool = True,
    write_output: bool = True,
    fail_after_output: bool = False,
    include_ci: bool = True,
) -> tuple[GapForgeConfig, str, str]:
    config, workspace_id = _workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="fixture examples",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="Fixture empirical review validation.",
    )
    if include_baseline:
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
    script = Path(workspace.root_dir) / "code" / "write_empirical_metrics.py"
    if write_output:
        metric_entry = {
            "metric_id": "false positive rate",
            "value": 0.01,
            "sample_size": 1000,
        }
        if include_ci:
            metric_entry["confidence_interval"] = [0.0, 0.02]
        payload = json.dumps({"metric_results": [metric_entry]})
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
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
    return config, workspace_id, execution.id


def _workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Empirical Review Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-empirical-review",
            direction_id="direction-empirical-review",
            linked_experiment_plan_id="experiment-empirical-review",
            objective="Review executed empirical results.",
            hypothesis="Artifact-backed results should survive empirical review.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-empirical-review",
    )
    return config, workspace.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
