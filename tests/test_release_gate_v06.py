from __future__ import annotations

import json
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.benchmarks.canaries import BenchmarkCanaryRunner
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code import ExperimentCodeScaffolderV2
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, ResearchDirection, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v06 import V06ReleaseGateEnforcer, render_v06_release_gate_markdown


def test_v06_release_gate_no_executed_experiment_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_prerequisite_gate_docs(config)

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "fail"
    assert result.requirements["successful_fixture_experiment_executed"] is False
    assert "No fixture or smoke experiment workspace executed successfully." in result.blockers


def test_v06_release_gate_successful_fixture_run_is_partial_without_failure_path(tmp_path: Path) -> None:
    config, workspace_id = _workspace_fixture(tmp_path)
    _write_prerequisite_gate_docs(config)
    _run_workspace(config, workspace_id, name="success")

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "partial"
    assert result.requirements["successful_fixture_experiment_executed"] is True
    assert result.requirements["failed_experiment_path_recorded"] is False


def test_v06_release_gate_no_failed_path_fails(tmp_path: Path) -> None:
    config, workspace_id = _workspace_fixture(tmp_path)
    _write_prerequisite_gate_docs(config)
    _run_workspace(config, workspace_id, name="success")
    PaperPackageExporter(config).export_workspace_v2(workspace_id)

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert "No failed experiment path was recorded." in result.blockers


def test_v06_release_gate_fake_result_acceptance_fails(tmp_path: Path) -> None:
    config, workspace_id = _workspace_fixture(tmp_path)
    _write_prerequisite_gate_docs(config)
    _run_workspace(config, workspace_id, name="success")
    _run_workspace(config, workspace_id, name="failed", fail_after_output=True)
    PaperPackageExporter(config).export_workspace_v2(workspace_id)
    _force_package_readiness(config, workspace_id, "paper_ready_empirical")

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_fake_results_accepted"] is False
    assert any("fixture/synthetic/generated result" in blocker for blocker in result.blockers)


def test_v06_release_gate_reproducibility_missing_fails(tmp_path: Path) -> None:
    config, workspace_id = _workspace_fixture(tmp_path)
    _write_prerequisite_gate_docs(config)
    _run_workspace(config, workspace_id, name="success")
    _run_workspace(config, workspace_id, name="failed", fail_after_output=True)

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["reproducibility_checker_run"] is False
    assert "Reproducibility checker has not been run." in result.blockers


def test_v06_release_gate_all_requirements_pass_and_report_renders(tmp_path: Path) -> None:
    config, workspace_id = _passing_workspace(tmp_path)
    enforcer = V06ReleaseGateEnforcer(config)

    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)
    rendered = render_v06_release_gate_markdown(result)

    assert result.passed is True
    assert result.status == "pass"
    assert result.requirements["failed_experiments_not_hidden"] is True
    assert result.workspaces[0].result_scope == "fixture"
    assert "v0.6 Empirical Validation Release Gate" in rendered
    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    assert "Failed execution paths" in md_path.read_text(encoding="utf-8")


def test_v06_release_gate_ignores_v07_benchmark_canary_workspaces(tmp_path: Path) -> None:
    config, _workspace_id = _passing_workspace(tmp_path)
    BenchmarkCanaryRunner(config).run("fixture_benchmark_failure")
    markerless_workspace = (
        config.project_root
        / "benchmark-canary-fixture-benchmark-failure-2"
        / "experiment_workspaces"
        / "workspace-direction-fixture-benchmark-failure"
    )
    markerless_workspace.mkdir(parents=True)
    (markerless_workspace / "workspace.json").write_text(
        json.dumps(
            {
                "id": "workspace-direction-fixture-benchmark-failure",
                "project_id": "benchmark-canary-fixture-benchmark-failure-2",
                "direction_id": "direction-fixture-benchmark-failure",
                "root_dir": str(markerless_workspace),
                "status": "failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = V06ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert all("fixture-benchmark-failure" not in item.workspace_id for item in result.workspaces)


def _passing_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config, workspace_id = _workspace_fixture(tmp_path)
    _write_prerequisite_gate_docs(config)
    _run_workspace(config, workspace_id, name="success")
    _run_workspace(config, workspace_id, name="failed", fail_after_output=True)
    PaperPackageExporter(config).export_workspace_v2(workspace_id)
    return config, workspace_id


def _workspace_fixture(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("v0.6 release gate project")
    direction_id = "direction-v06-gate"
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-v06-gate",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-v06-gate",
            objective="Validate v0.6 release-gate empirical artifact boundaries.",
            hypothesis="Only artifact-backed executions can support empirical claims.",
            datasets=["fixture"],
            statistical_tests=["binomial confidence intervals"],
            expected_artifacts=["metrics.json"],
        )
    )
    program.research_directions = [
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title="v0.6 release gate direction",
            summary="Fixture direction for empirical release-gate tests.",
            maturity="experiment_ready",
        )
    ]
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture examples",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="Release-gate fixture only.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    return config, workspace.id


def _run_workspace(config: GapForgeConfig, workspace_id: str, *, name: str, fail_after_output: bool = False) -> str:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / f"{name}_metrics.json"
    script = Path(workspace.root_dir) / "code" / f"write_{name}_metrics.py"
    payload = json.dumps(
        {
            "metric_results": [
                {
                    "metric_id": "false positive rate",
                    "dataset_id": "dataset-fixture-examples",
                    "baseline_id": "baseline-heuristic-baseline",
                    "value": 0.01,
                    "sample_size": 1000,
                    "confidence_interval": [0.0, 0.02],
                }
            ]
        }
    )
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n"
        + ("raise SystemExit(2)\n" if fail_after_output else ""),
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        run_name=name,
        command=f"{sys.executable} {script}",
        expected_outputs=[f"results/{name}_metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")


def _write_prerequisite_gate_docs(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true}\n', encoding="utf-8")
    (release_dir / "v0.4_latest.json").write_text('{"passed": true, "documented": true}\n', encoding="utf-8")
    (release_dir / "v0.5_latest.json").write_text('{"passed": true, "documented": true}\n', encoding="utf-8")


def _force_package_readiness(config: GapForgeConfig, workspace_id: str, readiness: str) -> None:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    package_path = Path(workspace.root_dir) / "paper_package_v2" / "paper_package.json"
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    payload["readiness"] = readiness
    package_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
