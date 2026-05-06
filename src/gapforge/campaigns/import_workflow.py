"""Convenience workflows for campaign task validation/import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.handoff import write_campaign_handoff
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.task_packs import CAMPAIGN_TASK_OUTPUTS
from gapforge.config import GapForgeConfig
from gapforge.diagnostics.real_run import build_real_run_diagnostic
from gapforge.diagnostics.report import render_real_run_diagnostic_markdown
from gapforge.models import CampaignImportRecord, to_plain


def find_campaign_task(config: GapForgeConfig, task_id: str) -> tuple[CampaignState, Path]:
    manager = CampaignManager(config)
    for project_dir in sorted(config.project_root.glob("*")):
        campaigns_dir = project_dir / "campaigns"
        if not campaigns_dir.exists():
            continue
        for campaign_dir in sorted(campaigns_dir.glob("*")):
            if not campaign_dir.is_dir():
                continue
            try:
                state = manager.load_campaign_state(campaign_dir.name)
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                continue
            if task_id in state.campaign.task_ids or any(step.task_spec_id == task_id for step in state.steps):
                return state, campaign_dir / "agent_tasks" / task_id
    raise FileNotFoundError(f"No campaign task found for {task_id}")


def write_task_handoff(config: GapForgeConfig, task_id: str, *, model: str = "gpt-5.4") -> Path:
    state, pack_dir = find_campaign_task(config, task_id)
    return write_campaign_handoff(state, task_id, pack_dir, model=model, expected_outputs=expected_campaign_files(task_id))


def validate_import_all(config: GapForgeConfig, campaign_id: str) -> dict[str, Any]:
    manager = CampaignManager(config)
    state = manager.load_campaign_state(campaign_id)
    importer = CampaignOutputImporter(config)
    imported_task_ids = {record.task_id for record in state.imports if record.status in {"applied", "partial"}}
    records: list[CampaignImportRecord] = []
    for task_id in state.campaign.task_ids:
        if task_id in imported_task_ids:
            continue
        record = importer.import_outputs(campaign_id, task_id, [])
        records.append(record)
        if record.status == "rejected":
            _write_campaign_diagnostic(config, campaign_id, task_id)
    status = _aggregate_status(records)
    return {
        "campaign_id": campaign_id,
        "status": status,
        "task_count": len(state.campaign.task_ids),
        "processed_task_count": len(records),
        "applied_count": sum(1 for record in records if record.status == "applied"),
        "partial_count": sum(1 for record in records if record.status == "partial"),
        "rejected_count": sum(1 for record in records if record.status == "rejected"),
        "records": [to_plain(record) for record in records],
        "repair_commands": [
            f"gapforge repair-agent-output --task-id {record.task_id} --path <fixed-output.json>"
            for record in records
            if record.status in {"partial", "rejected"}
        ],
    }


def expected_campaign_files(task_id: str) -> list[str]:
    task_type = _task_type_from_id(task_id)
    return CAMPAIGN_TASK_OUTPUTS.get(task_type, [])


def _aggregate_status(records: list[CampaignImportRecord]) -> str:
    if not records:
        return "no_tasks_processed"
    if all(record.status == "applied" for record in records):
        return "applied"
    if any(record.status in {"applied", "partial"} for record in records):
        return "partial"
    return "rejected"


def _write_campaign_diagnostic(config: GapForgeConfig, campaign_id: str, task_id: str) -> None:
    state = CampaignManager(config).load_campaign_state(campaign_id)
    campaign_dir = config.project_root / state.campaign.project_id / "campaigns" / campaign_id
    diagnostics_dir = campaign_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    diagnostic = build_real_run_diagnostic(config)
    json_path = diagnostics_dir / f"real_run_diagnostic_{task_id}.json"
    markdown_path = diagnostics_dir / f"real_run_diagnostic_{task_id}.md"
    json_path.write_text(json.dumps(to_plain(diagnostic), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_real_run_diagnostic_markdown(diagnostic), encoding="utf-8")


def _task_type_from_id(task_id: str) -> str:
    for task_type in CAMPAIGN_TASK_OUTPUTS:
        if task_id.endswith(task_type):
            return task_type
    return task_id.rsplit("-", 1)[-1]
