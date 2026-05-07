from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.jobs.scheduler import JobScheduler
from gapforge.models import ExperimentProtocol, ResourceRequest
from gapforge.project_memory import ProjectMemoryManager


def test_local_job_completes_and_creates_execution_record(tmp_path: Path) -> None:
    config, workspace_id = _job_workspace(tmp_path)
    manifest = _manifest_with_script(config, workspace_id, "metrics", '{"fpr": 0.0}')
    scheduler = JobScheduler(config)

    job = scheduler.submit(workspace_id=workspace_id, manifest_id=manifest.id)
    result = scheduler.run_next(job.queue_id)
    reloaded = scheduler.get_job(job.id)
    executions = ExperimentWorkspaceManager(config).list_execution_records(workspace_id)

    assert result.status == "complete"
    assert reloaded.status == "complete"
    assert reloaded.execution_id == executions[0].id
    assert executions[0].status == "complete"
    assert result.result_paths


def test_failed_job_is_recorded_with_logs(tmp_path: Path) -> None:
    config, workspace_id = _job_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    script = Path(workspace.root_dir) / "code" / "fail_job.py"
    script.write_text("import sys\nprint('job failed', file=sys.stderr)\nsys.exit(9)\n", encoding="utf-8")
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
    )
    scheduler = JobScheduler(config)

    job = scheduler.submit(workspace_id=workspace_id, manifest_id=manifest.id)
    result = scheduler.run_next(job.queue_id)

    assert result.status == "failed"
    assert result.returncode == 9
    assert "return code 9" in result.error
    assert Path(result.stderr_path).read_text(encoding="utf-8")


def test_unavailable_docker_job_reports_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", "")
    config, workspace_id = _job_workspace(tmp_path)
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command="echo should-not-run",
        expected_outputs=["results/metrics.json"],
        resource_request=ResourceRequest(environment_type="docker"),
    )
    scheduler = JobScheduler(config)

    job = scheduler.submit(workspace_id=workspace_id, manifest_id=manifest.id)
    result = scheduler.run_next(job.queue_id)

    assert result.status == "failed"
    assert "Docker" in result.error or "docker" in result.error
    assert scheduler.get_job(job.id).status == "failed"


def test_queue_persists_and_cancel_queued_job(tmp_path: Path) -> None:
    config, workspace_id = _job_workspace(tmp_path)
    manifest = _manifest_with_script(config, workspace_id, "metrics", '{"fpr": 0.0}')
    scheduler = JobScheduler(config)

    job = scheduler.submit(workspace_id=workspace_id, manifest_id=manifest.id)
    queue = scheduler.load_queue(job.queue_id)
    cancelled = scheduler.cancel(job.id)
    reloaded_queue = JobScheduler(config).load_queue(job.queue_id)

    assert queue.jobs[0].id == job.id
    assert cancelled.status == "cancelled"
    assert reloaded_queue.jobs[0].status == "cancelled"


def test_job_cli_submit_list_and_status(tmp_path: Path) -> None:
    config, workspace_id = _job_workspace(tmp_path)
    manifest = _manifest_with_script(config, workspace_id, "metrics", '{"fpr": 0.0}')
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    submitted = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "job-submit", "--workspace-id", workspace_id, "--manifest-id", manifest.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert submitted.returncode == 0, submitted.stderr
    job_id = json.loads(submitted.stdout)["id"]

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "job-list", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "job-status", "--job-id", job_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert listed.returncode == 0, listed.stderr
    assert status.returncode == 0, status.stderr
    assert job_id in listed.stdout
    assert job_id in status.stdout


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


def _job_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Job Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-jobs",
            direction_id="direction-jobs",
            linked_experiment_plan_id="experiment-jobs",
            objective="Execute fixture jobs.",
            hypothesis="Job execution is recorded.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-jobs")
    return config, workspace.id
