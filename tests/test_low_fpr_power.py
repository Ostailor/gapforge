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
from gapforge.metrics.low_fpr_power import (
    LowFPRPowerChecker,
    minimum_trials_for_alpha,
    plan_low_fpr,
    render_low_fpr_check_markdown,
    required_negative_sample_count,
    zero_false_positive_upper_bound,
)
from gapforge.models import ExperimentProtocol, ResearchDirection, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.empirical import EmpiricalReviewBuilder


def test_low_fpr_sample_size_calculations_are_sane() -> None:
    required = required_negative_sample_count(target_fpr=0.001, ci_width=0.0005)
    plan = plan_low_fpr(target_fpr=0.001, ci_width=0.0005)

    assert 50_000 <= required <= 70_000
    assert plan.required_negative_count == required
    assert plan.alpha_trial_requirements["1e-03"] >= 2_900
    assert "1e-04" in plan.alpha_trial_requirements


def test_zero_false_positives_upper_bound_reported() -> None:
    upper = zero_false_positive_upper_bound(negative_count=3000, confidence=0.95)
    min_trials = minimum_trials_for_alpha(0.001, confidence=0.95)

    assert 0.0009 < upper < 0.0011
    assert 2_900 <= min_trials <= 3_100


def test_underpowered_low_fpr_execution_is_flagged(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _low_fpr_execution(tmp_path, sample_size=1000, confidence_interval=[0.0, 0.002])

    result = LowFPRPowerChecker(config).check_execution(execution_id, target_fpr=0.001, ci_width=0.0005)
    rendered = render_low_fpr_check_markdown(result)

    assert result.status == "fail"
    assert result.underpowered_metric_ids
    assert any("underpowered" in item.lower() for item in result.blockers)
    assert "Low-FPR Power Check" in rendered


def test_adequate_low_fpr_execution_passes(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _low_fpr_execution(
        tmp_path,
        sample_size=75_000,
        confidence_interval=[0.0008, 0.0012],
    )

    result = LowFPRPowerChecker(config).check_execution(execution_id, target_fpr=0.001, ci_width=0.0005)

    assert result.status == "pass"
    assert not result.underpowered_metric_ids


def test_low_fpr_cli_plan_and_check_render(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _low_fpr_execution(tmp_path, sample_size=1000, confidence_interval=[0.0, 0.002])
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    plan_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "low-fpr-plan",
            "--target-fpr",
            "0.001",
            "--ci-width",
            "0.0005",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    check_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "low-fpr-check",
            "--execution-id",
            execution_id,
            "--target-fpr",
            "0.001",
            "--ci-width",
            "0.0005",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert plan_result.returncode == 0, plan_result.stderr
    assert "Required negative examples" in plan_result.stdout
    assert check_result.returncode == 1
    assert "underpowered" in check_result.stdout.lower()
    assert config.root == tmp_path


def test_paper_package_includes_low_fpr_warning(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _low_fpr_execution(tmp_path, sample_size=1000, confidence_interval=[0.0, 0.002])

    PaperPackageExporter(config).export_workspace_v2(workspace_id)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    statistical_analysis = Path(workspace.root_dir) / "paper_package_v2" / "statistical_analysis.md"

    assert "Low-FPR Power Check" in statistical_analysis.read_text(encoding="utf-8")
    assert "underpowered" in statistical_analysis.read_text(encoding="utf-8").lower()


def test_empirical_reviewer_treats_underpowered_low_fpr_as_major_or_fatal(tmp_path: Path) -> None:
    config, _workspace_id, execution_id = _low_fpr_execution(tmp_path, sample_size=1000, confidence_interval=[0.0, 0.002])

    panel = EmpiricalReviewBuilder(config).review_execution(execution_id)
    statistics_review = next(review for review in panel.reviewer_reviews if review.role == "statistics")

    assert any("underpowered" in weakness.lower() for weakness in statistics_review.weaknesses)
    assert any("negative examples" in fix.lower() for fix in statistics_review.required_fixes)


def _low_fpr_execution(
    tmp_path: Path,
    *,
    sample_size: int,
    confidence_interval: list[float],
) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Low-FPR Power Project")
    direction_id = "direction-low-fpr-power"
    program.research_directions = [
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title="Low-FPR Power Direction",
            summary="Validate low-FPR sample-size warnings.",
            maturity="experiment_ready",
        )
    ]
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-low-fpr-power",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-low-fpr-power",
            objective="Estimate false positive rate.",
            hypothesis="FPR is below the target threshold.",
            datasets=["fixture negatives"],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence intervals"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,0\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture negatives",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="Low-FPR power validation.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="zero alert baseline",
        baseline_type="trivial",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_low_fpr_metrics.py"
    payload = json.dumps(
        {
            "metric_results": [
                {
                    "metric_id": "false positive rate",
                    "value": 0.001,
                    "sample_size": sample_size,
                    "confidence_interval": confidence_interval,
                }
            ]
        }
    )
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace.id,
        run_type="main",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    manifest_path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
    execution = ExperimentRunner(config).run(workspace_id=workspace.id, manifest_id=manifest.id).execution
    return config, workspace.id, execution.id
