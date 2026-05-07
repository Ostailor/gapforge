from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.benchmarks.canaries import BenchmarkCanaryRunner, default_benchmark_canary_profiles, render_benchmark_canary_record
from gapforge.config import GapForgeConfig


def test_benchmark_canary_profile_listing() -> None:
    profile_ids = [profile.id for profile in default_benchmark_canary_profiles()]

    assert "fixture_benchmark_success" in profile_ids
    assert "fixture_benchmark_failure" in profile_ids
    assert "local_public_small_benchmark" in profile_ids
    assert "low_fpr_underpowered_benchmark" in profile_ids
    assert "replication_package_canary" in profile_ids


def test_fixture_success_canary_passes(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("fixture_benchmark_success")

    assert record.status == "passed"
    assert record.execution_status == "complete"
    assert record.benchmark_id
    assert "metrics.json" in " ".join(record.artifact_paths)


def test_fixture_failure_canary_preserves_failed_path(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("fixture_benchmark_failure")

    assert record.status == "failed"
    assert record.execution_status == "failed"
    assert any("failed" in issue.lower() for issue in record.issues)


def test_real_profile_refuses_without_download_consent(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("local_public_small_benchmark", real=True)

    assert record.status == "refused"
    assert any("consent" in issue.lower() for issue in record.issues)


def test_real_profile_runs_public_small_canary_with_consent(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    source = _write_iris_fixture(tmp_path)
    monkeypatch.setenv("GAPFORGE_LOCAL_PUBLIC_BENCHMARK_URL", source.as_uri())
    config = GapForgeConfig.from_cwd(tmp_path)

    record = BenchmarkCanaryRunner(config).run("local_public_small_benchmark", real=True, download_consent=True)

    assert record.status == "passed"
    assert record.execution_status == "complete"
    assert record.replication_package_id
    assert record.validation_summary["dataset_download"] == "downloaded"
    assert record.validation_summary["result_parse"] == "pass"
    assert record.validation_summary["error_analysis"] == "pass"
    assert record.validation_summary["replication_verification"] == "pass"
    assert any("predictions.json" in path for path in record.artifact_paths)


def test_low_fpr_underpowered_canary_records_warning(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("low_fpr_underpowered_benchmark")

    assert record.status == "warning"
    assert any("underpowered" in warning.lower() for warning in record.warnings + record.issues)


def test_replication_package_canary_passes(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("replication_package_canary")

    assert record.status == "passed"
    assert record.replication_package_id
    assert "replication_verification" in record.validation_summary


def test_benchmark_canary_cli_list_and_run(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-canary-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-canary-run", "--profile", "fixture_benchmark_success"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert listed.returncode == 0, listed.stderr
    assert "fixture_benchmark_success" in listed.stdout
    assert run.returncode == 0, run.stderr
    assert "Benchmark Canary Record" in run.stdout
    assert "Status: `passed`" in run.stdout


def test_benchmark_canary_report_renders(tmp_path: Path) -> None:
    record = BenchmarkCanaryRunner(GapForgeConfig.from_cwd(tmp_path)).run("fixture_benchmark_success")

    assert "Benchmark Canary Record" in render_benchmark_canary_record(record)


def _write_iris_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "iris_public_small.csv"
    path.write_text(
        "\n".join(
            [
                "5.1,3.5,1.4,0.2,Iris-setosa",
                "4.9,3.0,1.4,0.2,Iris-setosa",
                "7.0,3.2,4.7,1.4,Iris-versicolor",
                "6.4,3.2,4.5,1.5,Iris-versicolor",
                "6.3,3.3,6.0,2.5,Iris-virginica",
                "5.8,2.7,5.1,1.9,Iris-virginica",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path
