"""Durable experiment job scheduler."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.jobs.base import JobRunner
from gapforge.jobs.docker_runner import DockerJobRunner
from gapforge.jobs.local_runner import LocalJobRunner
from gapforge.jobs.queue import load_queue, save_queue
from gapforge.jobs.slurm_runner import SlurmJobRunner
from gapforge.models import ExperimentJob, ExperimentRunManifest, ExperimentWorkspace, JobQueue, JobRunnerResult, Provenance, to_plain
from gapforge.state import utc_now_iso


class JobScheduler:
    """Persist queued experiment jobs and dispatch them to backend runners."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def submit(self, *, workspace_id: str, manifest_id: str) -> ExperimentJob:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        manifest = self._require_manifest(workspace_id, manifest_id)
        queue = self._load_or_create_queue(workspace)
        sequence = len(queue.jobs) + 1
        now = utc_now_iso()
        environment_id = _environment_id(manifest.resource_request.environment_type)
        job = ExperimentJob(
            id=f"job-{manifest.id}-{sequence}",
            workspace_id=workspace.id,
            manifest_id=manifest.id,
            command=manifest.command,
            environment_id=environment_id,
            resource_request=manifest.resource_request,
            status="queued",
            submitted_at=now,
            queue_id=queue.id,
            provenance=Provenance(
                created_by_skill="job-scheduler",
                source_ids=[workspace.id, manifest.id],
                timestamp=now,
                reasoning_summary="Queued an experiment manifest for execution through a job runner.",
            ),
        )
        queue.jobs.append(job)
        queue.status = _queue_status(queue.jobs)
        self._save_queue(workspace, queue)
        return job

    def load_queue(self, queue_id: str) -> JobQueue:
        path = self._queue_path_by_id(queue_id)
        return load_queue(path)

    def list_jobs(self, workspace_id: str) -> list[ExperimentJob]:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        queue = self._load_or_create_queue(workspace)
        return queue.jobs

    def get_job(self, job_id: str) -> ExperimentJob:
        queue, job = self._find_job(job_id)
        return job

    def cancel(self, job_id: str) -> ExperimentJob:
        workspace, queue, job = self._find_job_with_workspace(job_id)
        if job.status != "queued":
            raise ValueError(f"Only queued jobs can be cancelled; {job_id} is {job.status}.")
        job.status = "cancelled"
        job.completed_at = utc_now_iso()
        queue.status = _queue_status(queue.jobs)
        self._save_queue(workspace, queue)
        return job

    def run_next(self, queue_id: str) -> JobRunnerResult:
        workspace, queue = self._load_queue_with_workspace(queue_id)
        job = next((item for item in queue.jobs if item.status == "queued"), None)
        if job is None:
            raise ValueError(f"No queued jobs in {queue_id}.")
        job.status = "running"
        job.started_at = utc_now_iso()
        queue.status = _queue_status(queue.jobs)
        self._save_queue(workspace, queue)

        result = self._runner_for(job).run(job)
        job.status = result.status if result.status in {"complete", "failed", "cancelled"} else "failed"
        job.completed_at = utc_now_iso()
        job.execution_id = _execution_id_from_result(self.workspace_manager, job.workspace_id, job.manifest_id)
        job.logs = [path for path in [result.stdout_path, result.stderr_path] if path]
        queue.status = _queue_status(queue.jobs)
        self._save_queue(workspace, queue)
        self._write_result(workspace, result)
        return result

    def _runner_for(self, job: ExperimentJob) -> JobRunner:
        if job.environment_id == "local":
            return LocalJobRunner(self.config)
        if job.environment_id == "docker":
            return DockerJobRunner(self.config)
        if job.environment_id == "slurm":
            return SlurmJobRunner(self.config)
        if job.environment_id == "gpu_local":
            return LocalJobRunner(self.config)
        return DockerJobRunner(self.config)

    def _require_manifest(self, workspace_id: str, manifest_id: str) -> ExperimentRunManifest:
        for manifest in self.workspace_manager.list_manifests(workspace_id):
            if manifest.id == manifest_id:
                return manifest
        raise FileNotFoundError(f"No experiment manifest found for {manifest_id}")

    def _load_or_create_queue(self, workspace: ExperimentWorkspace) -> JobQueue:
        path = _queue_path(workspace)
        if path.exists():
            return load_queue(path)
        return JobQueue(
            id=f"queue-{workspace.id}",
            project_id=workspace.project_id,
            status="idle",
            provenance=Provenance(
                created_by_skill="job-queue",
                source_ids=[workspace.project_id, workspace.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a durable experiment job queue.",
            ),
        )

    def _save_queue(self, workspace: ExperimentWorkspace, queue: JobQueue) -> None:
        save_queue(_queue_path(workspace), queue)
        (_jobs_dir(workspace) / "queue.md").write_text(render_job_queue(queue), encoding="utf-8")

    def _queue_path_by_id(self, queue_id: str) -> Path:
        for project_dir in self.config.project_root.glob("*"):
            for path in project_dir.glob(f"experiment_workspaces/*/jobs/{queue_id}.json"):
                return path
        raise FileNotFoundError(f"No job queue found for {queue_id}")

    def _load_queue_with_workspace(self, queue_id: str) -> tuple[ExperimentWorkspace, JobQueue]:
        path = self._queue_path_by_id(queue_id)
        workspace = self.workspace_manager.load_workspace(path.parents[1].name)
        return workspace, load_queue(path)

    def _find_job(self, job_id: str) -> tuple[JobQueue, ExperimentJob]:
        _workspace, queue, job = self._find_job_with_workspace(job_id)
        return queue, job

    def _find_job_with_workspace(self, job_id: str) -> tuple[ExperimentWorkspace, JobQueue, ExperimentJob]:
        for project_dir in self.config.project_root.glob("*"):
            for path in project_dir.glob("experiment_workspaces/*/jobs/queue-*.json"):
                queue = load_queue(path)
                for job in queue.jobs:
                    if job.id == job_id:
                        workspace = self.workspace_manager.load_workspace(job.workspace_id)
                        return workspace, queue, job
        raise FileNotFoundError(f"No experiment job found for {job_id}")

    def _write_result(self, workspace: ExperimentWorkspace, result: JobRunnerResult) -> None:
        path = _jobs_dir(workspace) / f"{result.job_id}.result.json"
        path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")


def render_job(job: ExperimentJob) -> str:
    return (
        "\n".join(
            [
                f"# Experiment Job `{job.id}`",
                "",
                f"- Workspace ID: `{job.workspace_id}`",
                f"- Manifest ID: `{job.manifest_id}`",
                f"- Queue ID: `{job.queue_id}`",
                f"- Environment ID: `{job.environment_id}`",
                f"- Status: `{job.status}`",
                f"- Command: `{job.command}`",
                f"- Execution ID: `{job.execution_id or 'none'}`",
                f"- Submitted: {job.submitted_at or 'unknown'}",
                f"- Started: {job.started_at or 'unknown'}",
                f"- Completed: {job.completed_at or 'unknown'}",
                "",
                "## Logs",
                "",
                *([f"- `{path}`" for path in job.logs] or ["- none"]),
            ]
        ).rstrip()
        + "\n"
    )


def render_job_queue(queue: JobQueue) -> str:
    lines = [f"# Job Queue `{queue.id}`", "", f"- Project ID: `{queue.project_id}`", f"- Status: `{queue.status}`", "", "## Jobs", ""]
    if not queue.jobs:
        lines.append("- none")
    else:
        for job in queue.jobs:
            lines.append(f"- `{job.id}` `{job.status}` manifest `{job.manifest_id}` environment `{job.environment_id}`")
    return "\n".join(lines).rstrip() + "\n"


def render_job_runner_result(result: JobRunnerResult) -> str:
    lines = [
        f"# Job Runner Result `{result.job_id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Return code: {result.returncode if result.returncode is not None else 'none'}",
        f"- Stdout: `{result.stdout_path or 'none'}`",
        f"- Stderr: `{result.stderr_path or 'none'}`",
        f"- Error: {result.error or 'none'}",
        "",
        "## Result Paths",
        "",
    ]
    lines.extend([f"- `{path}`" for path in result.result_paths] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _queue_path(workspace: ExperimentWorkspace) -> Path:
    return _jobs_dir(workspace) / f"queue-{workspace.id}.json"


def _jobs_dir(workspace: ExperimentWorkspace) -> Path:
    path = Path(workspace.root_dir) / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _queue_status(jobs: list[ExperimentJob]) -> str:
    if any(job.status == "running" for job in jobs):
        return "running"
    if any(job.status == "queued" for job in jobs):
        return "queued"
    if any(job.status == "failed" for job in jobs):
        return "failed"
    if jobs and all(job.status == "cancelled" for job in jobs):
        return "cancelled"
    if jobs and all(job.status == "complete" for job in jobs):
        return "complete"
    return "idle"


def _environment_id(environment_type: str) -> str:
    if environment_type in {"", "local"}:
        return "local"
    if environment_type == "gpu":
        return "gpu_local"
    return environment_type


def _execution_id_from_result(manager: ExperimentWorkspaceManager, workspace_id: str, manifest_id: str) -> str:
    records = [record for record in manager.list_execution_records(workspace_id) if record.manifest_id == manifest_id]
    return records[-1].id if records else ""
