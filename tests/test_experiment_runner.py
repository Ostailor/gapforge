from __future__ import annotations

import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_experiment_runner_dry_run_does_not_execute(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "write_result.py"
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script.write_text(f"from pathlib import Path\nPath({str(output)!r}).write_text('{{}}')\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id, dry_run=True)

    assert result.execution.status == "skipped"
    assert not output.exists()
    assert "Dry run" in Path(result.execution.stdout_path).read_text(encoding="utf-8")


def test_successful_fixture_command_records_complete_with_artifact(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    manifest = _manifest_with_script(config, workspace_id, "metrics", '{"fpr": 0.0}')

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)
    artifacts = ExperimentWorkspaceManager(config).list_result_artifacts(workspace_id)

    assert result.execution.status == "complete"
    assert result.execution.returncode == 0
    assert result.execution.result_artifact_ids == [artifacts[0].id]
    assert artifacts[0].sha256
    assert artifacts[0].artifact_type == "metrics_json"


def test_failed_command_records_failure_and_logs(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "fail.py"
    script.write_text("import sys\nprint('before failure')\nprint('bad stderr', file=sys.stderr)\nsys.exit(7)\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)

    assert result.execution.status == "failed"
    assert result.execution.returncode == 7
    assert "return code 7" in result.execution.failure_reason
    assert "before failure" in Path(result.execution.stdout_path).read_text(encoding="utf-8")
    assert "bad stderr" in Path(result.execution.stderr_path).read_text(encoding="utf-8")


def test_missing_expected_output_records_failure(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "no_output.py"
    script.write_text("print('ok but no artifact')\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)

    assert result.execution.status == "failed"
    assert result.execution.returncode == 0
    assert "Missing expected outputs" in result.execution.failure_reason
    assert result.execution.result_artifact_ids == []


def test_logs_are_redacted(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "secret_output.py"
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script.write_text(
        f"from pathlib import Path\nprint('token=sk-testSECRET123456789')\nPath({str(output)!r}).write_text('{{\"ok\": true}}')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )

    result = ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)
    stdout = Path(result.execution.stdout_path).read_text(encoding="utf-8")

    assert result.execution.status == "complete"
    assert "sk-test" not in stdout
    assert "[REDACTED]" in stdout


def test_experiment_run_status_and_rerun(tmp_path: Path) -> None:
    config, workspace_id = _runner_workspace(tmp_path)
    manifest = _manifest_with_script(config, workspace_id, "metrics", '{"rerun": true}')
    runner = ExperimentRunner(config)
    first = runner.run(workspace_id=workspace_id, manifest_id=manifest.id)

    status = runner.render_execution_status(first.execution.id)
    second = runner.rerun(first.execution.id)

    assert first.execution.id in status
    assert "Result Artifacts" in status
    assert second.execution.status == "complete"
    assert second.execution.id != first.execution.id


def _manifest_with_script(config: GapForgeConfig, workspace_id: str, name: str, payload: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / f"write_{name}.py"
    output = Path(workspace.root_dir) / "results" / f"{name}.json"
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\nprint('wrote artifact')\n",
        encoding="utf-8",
    )
    return ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=[f"results/{name}.json"],
    )


def _runner_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Experiment Runner Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-runner",
            direction_id="direction-runner",
            linked_experiment_plan_id="experiment-runner",
            objective="Execute fixture commands.",
            hypothesis="Fixture command execution is recorded.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-runner",
    )
    return config, workspace.id
