from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.benchmarks.canaries import BenchmarkCanaryRunner
from gapforge.config import GapForgeConfig
from gapforge.release_gate.v07 import V07ReleaseGateEnforcer, render_v07_release_gate_markdown


def test_v07_release_gate_missing_benchmark_success_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_prerequisite_gate_docs(config)
    BenchmarkCanaryRunner(config).run("fixture_benchmark_failure")

    result = V07ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["fixture_benchmark_success"] is False
    assert "No fixture benchmark success canary has passed." in result.blockers


def test_v07_release_gate_missing_failed_path_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_prerequisite_gate_docs(config)
    success = BenchmarkCanaryRunner(config).run("fixture_benchmark_success")
    _write_supporting_reports(config, success.workspace_id, success.benchmark_id)

    result = V07ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["fixture_benchmark_failure_path"] is False
    assert "No fixture benchmark failure path has been recorded." in result.blockers


def test_v07_release_gate_missing_replication_package_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_prerequisite_gate_docs(config)
    runner = BenchmarkCanaryRunner(config)
    success = runner.run("fixture_benchmark_success")
    runner.run("fixture_benchmark_failure")
    runner.run("low_fpr_underpowered_benchmark")
    _write_supporting_reports(config, success.workspace_id, success.benchmark_id)

    result = V07ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["replication_package_exported"] is False
    assert "No replication package has been exported." in result.blockers


def test_v07_release_gate_fake_result_fails(tmp_path: Path) -> None:
    config, _, _ = _passing_fixture_gate(tmp_path)
    fake_marker = config.project_root / "fake" / "experiment_workspaces" / "ws" / "reports" / "fake_result.json"
    fake_marker.parent.mkdir(parents=True, exist_ok=True)
    fake_marker.write_text('{"fake_result": true, "accepted": true}\n', encoding="utf-8")

    result = V07ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_fake_results_accepted"] is False
    assert any("fake result" in blocker.lower() for blocker in result.blockers)


def test_v07_release_gate_all_fixture_requirements_pass(tmp_path: Path) -> None:
    config, _, _ = _passing_fixture_gate(tmp_path)
    enforcer = V07ReleaseGateEnforcer(config)

    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)
    rendered = render_v07_release_gate_markdown(result)

    assert result.passed is True
    assert result.fixture_gate_passed is True
    assert result.real_benchmark_claimed is False
    assert result.real_benchmark_gate_passed is False
    assert result.requirements["replication_verification_attempted"] is True
    assert "v0.7 Benchmark Release Gate" in rendered
    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    assert "Fixture gate passed" in md_path.read_text(encoding="utf-8")


def test_v07_release_gate_real_claim_without_real_canary_fails(tmp_path: Path) -> None:
    config, _, _ = _passing_fixture_gate(tmp_path)

    result = V07ReleaseGateEnforcer(config).evaluate(claim_real_benchmark_validation=True)

    assert result.passed is False
    assert result.fixture_gate_passed is True
    assert result.real_benchmark_claimed is True
    assert result.real_benchmark_gate_passed is False
    assert "Real benchmark validation was claimed, but no accepted opt-in real benchmark canary was found." in result.blockers


def test_v07_release_gate_real_claim_passes_with_public_small_canary(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    config, _, _ = _passing_fixture_gate(tmp_path)
    source = _write_iris_fixture(tmp_path)
    monkeypatch.setenv("GAPFORGE_LOCAL_PUBLIC_BENCHMARK_URL", source.as_uri())

    real_record = BenchmarkCanaryRunner(config).run("local_public_small_benchmark", real=True, download_consent=True)
    result = V07ReleaseGateEnforcer(config).evaluate(claim_real_benchmark_validation=True)

    assert real_record.status == "passed"
    assert result.passed is True
    assert result.fixture_gate_passed is True
    assert result.real_benchmark_claimed is True
    assert result.real_benchmark_gate_passed is True
    assert result.real_benchmark_requirements["accepted_opt_in_real_benchmark_canary"] is True
    assert result.real_benchmark_requirements["dataset_consent_recorded"] is True
    assert result.real_benchmark_requirements["real_results_artifact_backed"] is True
    assert result.real_benchmark_requirements["real_reproduction_package_exported"] is True


def test_v07_release_gate_cli_json(tmp_path: Path) -> None:
    config, _, _ = _passing_fixture_gate(tmp_path)
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    completed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v7-release-gate", "--json"],
        cwd=config.root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["fixture_gate_passed"] is True


def _passing_fixture_gate(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_prerequisite_gate_docs(config)
    runner = BenchmarkCanaryRunner(config)
    success = runner.run("fixture_benchmark_success")
    runner.run("fixture_benchmark_failure")
    runner.run("low_fpr_underpowered_benchmark")
    runner.run("replication_package_canary")
    _write_supporting_reports(config, success.workspace_id, success.benchmark_id)
    return config, success.workspace_id, success.benchmark_id


def _write_prerequisite_gate_docs(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true}\n', encoding="utf-8")
    (release_dir / "v0.6_latest.json").write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _write_supporting_reports(config: GapForgeConfig, workspace_id: str, benchmark_id: str) -> None:
    workspace_path = next(config.project_root.glob(f"*/experiment_workspaces/{workspace_id}"))
    reports = workspace_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"benchmark_comparison_{benchmark_id}.json").write_text(
        json.dumps({"benchmark_id": benchmark_id, "workspace_id": workspace_id, "smoke_results_separated": True}) + "\n",
        encoding="utf-8",
    )
    (reports / "aggregate_results.json").write_text(
        json.dumps([{"workspace_id": workspace_id, "run_type": "smoke", "n": 1}]) + "\n",
        encoding="utf-8",
    )
    (reports / "error_analysis_execution.json").write_text(
        json.dumps({"workspace_id": workspace_id, "limitations": ["No predictions artifact in fixture."]}) + "\n",
        encoding="utf-8",
    )


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
