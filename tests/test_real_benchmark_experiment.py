from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_real_benchmark_adapters import _no_fit_candidate, _primary_candidate, _sanity_candidate
from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import (
    RealBenchmarkExperimentManager,
    RealBenchmarkSearchManager,
    SelectedBenchmarkManager,
    render_real_benchmark_experiment_attempts,
)


def test_real_benchmark_fixture_run(tmp_path: Path) -> None:
    config, spec_id = _fixture_with_candidate(tmp_path, _primary_candidate())
    manager = RealBenchmarkExperimentManager(config)

    planned = manager.plan(spec_id)
    attempts = manager.run(spec_id)

    assert planned[0].status == "planned"
    assert attempts[0].status == "complete"
    assert attempts[0].claim_support_level == "primary"
    assert attempts[0].result_artifact_ids
    assert any(metric["result_source"] == "real_public_benchmark_adapter" for metric in attempts[0].metric_results)
    assert all(metric["synthetic"] is False for metric in attempts[0].metric_results)


def test_no_fit_attempt_recorded(tmp_path: Path) -> None:
    config, spec_id = _fixture_with_candidate(tmp_path, _no_fit_candidate())

    attempts = RealBenchmarkExperimentManager(config).run(spec_id)

    assert attempts[0].status == "no_fit"
    assert attempts[0].claim_support_level == "none"
    assert attempts[0].adapter_id == ""
    assert any("No experiment run is planned" in item for item in attempts[0].limitations)


def test_sanity_check_result_labeled(tmp_path: Path) -> None:
    config, spec_id = _fixture_with_candidate(tmp_path, _sanity_candidate())

    attempts = RealBenchmarkExperimentManager(config).run(spec_id)
    metrics = attempts[0].metric_results

    assert attempts[0].status == "complete"
    assert attempts[0].claim_support_level == "sanity_check"
    assert any("cannot support primary benchmark validity" in item for item in attempts[0].limitations)
    assert all(metric["claim_support_level"] == "sanity_check" for metric in metrics)
    assert all(metric["primary_validity_supported"] is False for metric in metrics)


def test_failed_run_preserved(tmp_path: Path) -> None:
    config, spec_id = _fixture_with_candidate(tmp_path, _primary_candidate())
    manager = RealBenchmarkExperimentManager(config)
    spec = SelectedBenchmarkManager(config).load_spec(spec_id)
    attempts = manager.plan(spec_id)
    attempts[0].adapter_id = "missing-real-adapter"
    attempts[0].status = "planned"
    manager.write_attempts(spec.project_id, attempts)

    failed = manager.run(spec_id)

    assert failed[0].status == "failed"
    assert failed[0].adapter_id == "missing-real-adapter"
    assert any("failed" in item.lower() for item in failed[0].limitations)


def test_real_benchmark_experiment_report_renders_and_cli(tmp_path: Path) -> None:
    config, spec_id = _fixture_with_candidate(tmp_path, _sanity_candidate())
    attempts = RealBenchmarkExperimentManager(config).run(spec_id)

    rendered = render_real_benchmark_experiment_attempts(attempts)
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-real-benchmark-experiment-report",
            "--benchmark-id",
            spec_id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Real Benchmark Experiment Attempts" in rendered
    assert "Claim Support: `sanity_check`" in rendered
    assert "Claim Boundary" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Real Benchmark Experiment Attempts" in cli.stdout
    assert "real_public_benchmark_adapter" in cli.stdout


def _fixture_with_candidate(tmp_path: Path, candidate):
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    RealBenchmarkSearchManager(config).search(spec.id, candidates=[candidate])
    return config, spec.id
