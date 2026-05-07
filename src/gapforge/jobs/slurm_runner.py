"""Slurm job runner placeholder."""

from __future__ import annotations

from gapforge.compute.environments import check_environment
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentJob, JobRunnerResult, Provenance
from gapforge.redaction import redact_text
from gapforge.state import utc_now_iso


class SlurmJobRunner:
    """Refuse Slurm execution until a concrete cluster runner is implemented."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def run(self, job: ExperimentJob) -> JobRunnerResult:
        check = check_environment("slurm")
        error = _blocked_message("Slurm", check.blockers)
        record = ExperimentWorkspaceManager(self.config).record_execution(
            workspace_id=job.workspace_id,
            manifest_id=job.manifest_id,
            status="failed",
            command=redact_text(job.command),
            stderr_text=redact_text(error + "\n"),
            failure_reason=error,
        )
        return JobRunnerResult(
            job_id=job.id,
            status="failed",
            returncode=None,
            stdout_path=record.stdout_path,
            stderr_path=record.stderr_path,
            error=error,
            provenance=Provenance(
                created_by_skill="job-slurm-runner",
                source_ids=[job.id, record.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Rejected a Slurm job because Slurm execution is a placeholder backend.",
            ),
        )


def _blocked_message(name: str, blockers: list[str]) -> str:
    details = "; ".join(blockers) if blockers else f"{name} runner is not implemented."
    return f"{name} job runner is unavailable. {details}"
