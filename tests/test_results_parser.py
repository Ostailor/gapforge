from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results import ResultParser


def test_parse_metric_json_creates_metric_result(tmp_path: Path) -> None:
    config, workspace_id = _results_workspace(tmp_path)
    manifest = _metric_manifest(config, workspace_id, {"metric_results": [{"metric_id": "false positive rate", "value": 0.01}]})
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    summary = ResultParser(config).parse_execution(execution.id)

    assert len(summary.metric_results) == 1
    assert summary.metric_results[0].metric_id.startswith("metric-false-positive-rate")
    assert summary.metric_results[0].value == 0.01
    assert summary.metric_results[0].raw_artifact_id == execution.result_artifact_ids[0]


def test_empirical_claim_created_only_with_artifact(tmp_path: Path) -> None:
    config, workspace_id = _results_workspace(tmp_path)
    manifest = _metric_manifest(
        config,
        workspace_id,
        {
            "metric_results": [
                {
                    "metric_id": "false positive rate",
                    "value": 0.01,
                    "confidence_interval": [0.0, 0.02],
                    "sample_size": 1000,
                }
            ]
        },
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    summary = ResultParser(config).parse_execution(execution.id)
    claims = ResultParser(config).empirical_claims_for_workspace(workspace_id)

    assert len(summary.empirical_claims) == 1
    assert summary.empirical_claims[0].status == "supported"
    assert summary.empirical_claims[0].metric_result_ids == [summary.metric_results[0].id]
    assert claims[0].id == summary.empirical_claims[0].id
    assert (
        Path(ExperimentWorkspaceManager(config).load_workspace(workspace_id).root_dir) / "reports" / "empirical_claim_ledger.md"
    ).exists()


def test_missing_confidence_interval_warns_for_low_fpr(tmp_path: Path) -> None:
    config, workspace_id = _results_workspace(tmp_path)
    manifest = _metric_manifest(config, workspace_id, {"metrics": {"false positive rate": 0.05}, "sample_size": 20})
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    summary = ResultParser(config).parse_execution(execution.id)

    assert any("lacks a confidence interval" in limitation for limitation in summary.limitations)
    assert any("lacks a confidence interval" in limitation for limitation in summary.empirical_claims[0].limitations)


def test_failed_experiment_with_artifact_creates_failed_claim(tmp_path: Path) -> None:
    config, workspace_id = _results_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_then_fail.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(output)!r}).write_text('{json.dumps({'metrics': {'recall': 0.0}})}\\n', encoding='utf-8')\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="pilot",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    summary = ResultParser(config).parse_execution(execution.id)

    assert execution.status == "failed"
    assert summary.failures
    assert summary.empirical_claims[0].status == "failed"
    assert "execution failed" in " ".join(summary.empirical_claims[0].limitations).lower()


def test_no_artifact_creates_no_empirical_claim(tmp_path: Path) -> None:
    config, workspace_id = _results_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "no_artifact.py"
    script.write_text("print('no artifact')\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )
    execution = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    summary = ResultParser(config).parse_execution(execution.id)

    assert summary.metric_results == []
    assert summary.empirical_claims == []
    assert any("No result artifact" in limitation for limitation in summary.limitations)


def test_results_cli_parse_summary_and_empirical_claims(tmp_path: Path) -> None:
    _config, workspace_id = _results_workspace(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    workspace = ExperimentWorkspaceManager(GapForgeConfig.from_cwd(tmp_path)).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "cli_result.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text('{json.dumps({'metrics': {'recall': 1.0}})}\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(GapForgeConfig.from_cwd(tmp_path)).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )
    execution = ExperimentRunner(GapForgeConfig.from_cwd(tmp_path)).run(workspace_id=workspace_id, manifest_id=manifest.id).execution

    parsed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "parse-results", "--execution-id", execution.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    summary = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "result-summary", "--execution-id", execution.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    claims = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "empirical-claims", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert parsed.returncode == 0, parsed.stderr
    assert summary.returncode == 0, summary.stderr
    assert claims.returncode == 0, claims.stderr
    assert "Result Summary" in parsed.stdout
    assert "Metric Results" in summary.stdout
    assert "Empirical Claims" in claims.stdout


def _metric_manifest(config: GapForgeConfig, workspace_id: str, payload: dict[str, object]):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_metrics.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )


def _results_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Result Parser Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-results",
            direction_id="direction-results",
            linked_experiment_plan_id="experiment-results",
            objective="Parse artifact-backed metric results.",
            hypothesis="Metric artifacts become empirical claims.",
            datasets=["fixture"],
            metrics=["false positive rate", "recall"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-results")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="recall")
    return config, workspace.id
