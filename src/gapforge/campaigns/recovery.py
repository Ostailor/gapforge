"""Recovery helpers for resumable campaign controller runs."""

from __future__ import annotations

from gapforge.campaigns import CampaignState


def blocked_campaign_tasks(state: CampaignState) -> list[str]:
    imported_task_ids = {record.task_id for record in state.imports if record.status in {"applied", "partial", "valid"}}
    task_ids: list[str] = []
    for step in state.steps:
        if step.task_spec_id and step.status in {"pending", "blocked"} and step.task_spec_id not in imported_task_ids:
            task_ids.append(step.task_spec_id)
    return task_ids


def mark_waiting_steps_running(state: CampaignState) -> None:
    for step in state.steps:
        if step.status == "blocked" and step.blocking_issues and any("awaiting" in issue.lower() for issue in step.blocking_issues):
            step.status = "pending"
