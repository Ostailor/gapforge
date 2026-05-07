"""Shared job runner interface."""

from __future__ import annotations

from typing import Protocol

from gapforge.models import ExperimentJob, JobRunnerResult


class JobRunner(Protocol):
    """Runner protocol for local and future cluster backends."""

    def run(self, job: ExperimentJob) -> JobRunnerResult:
        """Execute or reject a job and return a durable result summary."""
