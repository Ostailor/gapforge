from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import SelectedAblationManager, SelectedBenchmarkManager
from gapforge.selected_benchmark.ablations import REQUIRED_SELECTED_ABLATION_TYPES


def test_selected_ablation_plan_lists_required_reviewer_blockers(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)

    plan = SelectedAblationManager(config).create_plan(spec.id)

    output_dir = Path(config.project_root / project_id / "selected_benchmark" / "ablations")
    assert plan.required_ablation_types == list(REQUIRED_SELECTED_ABLATION_TYPES)
    assert {item.ablation_type for item in plan.ablations} == set(REQUIRED_SELECTED_ABLATION_TYPES)
    assert plan.missing_ablation_types == list(REQUIRED_SELECTED_ABLATION_TYPES)
    assert plan.strong_claim_allowed is False
    assert any("Missing required ablation" in blocker for blocker in plan.reviewer_blockers)
    assert (output_dir / "selected_ablation_plan.json").exists()
    assert (output_dir / "selected_ablation_plan.md").exists()


def test_selected_ablation_run_is_artifact_backed_and_synthetic_labeled(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)

    run = SelectedAblationManager(config).run(spec.id)
    report = SelectedAblationManager(config).report(spec.id)

    output_dir = Path(config.project_root / project_id / "selected_benchmark" / "ablations")
    assert run.required_ablation_types == list(REQUIRED_SELECTED_ABLATION_TYPES)
    assert not run.missing_ablation_types
    assert run.strong_claim_allowed is True
    assert run.synthetic is True
    assert all(result.status == "complete" for result in run.results)
    assert all(result.synthetic is True for result in run.results)
    assert all(result.artifact_backed for result in run.results)
    assert all(result.artifact_paths for result in run.results)
    assert all(Path(path).exists() for result in run.results for path in result.artifact_paths)
    assert (output_dir / "selected_ablation_run.json").exists()
    assert (output_dir / "selected_ablation_run.md").exists()
    assert (output_dir / "selected_ablation_report.md").exists()
    assert "Synthetic: `true`" in report
    assert "Strong claims allowed: `true`" in report
    assert "threshold_calibration" in report
    assert "sequential_vs_non_sequential" in report
    assert "No missing required ablations." in report


def test_selected_ablation_missing_artifact_remains_visible(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)
    manager = SelectedAblationManager(config)
    run = manager.run(spec.id)
    first_artifact = Path(run.results[0].artifact_paths[0])
    first_artifact.unlink()

    status = manager.status(spec.id)
    report = manager.report(spec.id)

    assert status.strong_claim_allowed is False
    assert run.results[0].ablation_type in status.missing_ablation_types
    assert "Reviewer Blockers" in report
    assert "Missing artifact-backed ablation" in report
    assert run.results[0].ablation_type in report


def test_selected_ablation_cli_plan_run_and_report(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)
    env = _env()

    plan_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-ablation-plan", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    run_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-ablation-run", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-ablation-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert plan_cli.returncode == 0, plan_cli.stderr
    assert "Selected Ablation Plan" in plan_cli.stdout
    assert "threshold_calibration" in plan_cli.stdout
    assert run_cli.returncode == 0, run_cli.stderr
    run_payload = json.loads(run_cli.stdout)
    assert run_payload["strong_claim_allowed"] is True
    assert run_payload["synthetic"] is True
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Selected Ablation Report" in report_cli.stdout
    assert "Missing Ablations" in report_cli.stdout
