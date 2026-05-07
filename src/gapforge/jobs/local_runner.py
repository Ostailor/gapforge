"""Local job runner adapter."""

from __future__ import annotations

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.models import ExperimentJob, JobRunnerResult, Provenance
from gapforge.state import utc_now_iso


class LocalJobRunner:
    """Run jobs through the existing local experiment runner."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def run(self, job: ExperimentJob) -> JobRunnerResult:
        result = ExperimentRunner(self.config).run(workspace_id=job.workspace_id, manifest_id=job.manifest_id)
        return JobRunnerResult(
            job_id=job.id,
            status="complete" if result.execution.status == "complete" else "failed",
            returncode=result.execution.returncode,
            stdout_path=result.execution.stdout_path,
            stderr_path=result.execution.stderr_path,
            result_paths=result.detected_outputs,
            error=result.execution.failure_reason,
            provenance=Provenance(
                created_by_skill="job-local-runner",
                source_ids=[job.id, result.execution.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Executed an experiment job with the local experiment runner.",
            ),
        )
