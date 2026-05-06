"""Rollback snapshots for campaign imports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.config import GapForgeConfig
from gapforge.models import CampaignImportRecord, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


def create_campaign_snapshot(config: GapForgeConfig, campaign_state: CampaignState, import_id: str) -> Path:
    campaign_dir = _campaign_dir(config, campaign_state)
    snapshot_dir = campaign_dir / "rollback_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{import_id}.json"
    path.write_text(json.dumps(to_plain(campaign_state), indent=2) + "\n", encoding="utf-8")
    return path


def rollback_import(config: GapForgeConfig, import_id: str) -> CampaignImportRecord:
    manager = CampaignManager(config)
    campaign_state, record = _find_import_record(config, import_id)
    if not record.rollback_snapshot_path:
        raise FileNotFoundError(f"No rollback snapshot recorded for {import_id}")
    snapshot_path = Path(record.rollback_snapshot_path)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Rollback snapshot missing: {snapshot_path}")
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    restored = _campaign_state_from_dict(raw)
    rollback_record = CampaignImportRecord(
        id=f"campaign-rollback-{utc_now_compact()}-{import_id}",
        campaign_id=record.campaign_id,
        task_id=record.task_id,
        input_paths=record.input_paths,
        status="rolled_back",
        accepted_objects=record.accepted_objects,
        rejected_objects=record.rejected_objects,
        issues=[f"Rolled back import {import_id}."],
        rollback_snapshot_path=record.rollback_snapshot_path,
        created_at=utc_now_iso(),
        provenance=record.provenance,
    )
    restored.imports.append(rollback_record)
    manager.save_campaign_state(restored)
    return rollback_record


def _find_import_record(config: GapForgeConfig, import_id: str) -> tuple[CampaignState, CampaignImportRecord]:
    manager = CampaignManager(config)
    for project_dir in sorted(config.project_root.glob("*")):
        campaigns_dir = project_dir / "campaigns"
        if not campaigns_dir.exists():
            continue
        for campaign_json in campaigns_dir.glob("*/campaign.json"):
            state = manager.load_campaign_state(campaign_json.parent.name)
            for record in state.imports:
                if record.id == import_id:
                    return state, record
    raise FileNotFoundError(f"No campaign import found for {import_id}")


def _campaign_state_from_dict(raw: dict[str, Any]) -> CampaignState:
    from gapforge.models import (
        AgentActualRunAttestation,
        CampaignBudget,
        CampaignDecision,
        CampaignImportRecord,
        CampaignMilestone,
        CampaignStep,
        CampaignStopCondition,
        ResearchCampaign,
    )

    return CampaignState(
        campaign=from_dict(ResearchCampaign, raw["campaign"]),
        steps=[from_dict(CampaignStep, item) for item in raw.get("steps", [])],
        decisions=[from_dict(CampaignDecision, item) for item in raw.get("decisions", [])],
        milestones=[from_dict(CampaignMilestone, item) for item in raw.get("milestones", [])],
        budget=from_dict(CampaignBudget, raw["budget"]) if raw.get("budget") else None,
        stop_conditions=[from_dict(CampaignStopCondition, item) for item in raw.get("stop_conditions", [])],
        imports=[from_dict(CampaignImportRecord, item) for item in raw.get("imports", [])],
        agent_actual_run_attestations=[from_dict(AgentActualRunAttestation, item) for item in raw.get("agent_actual_run_attestations", [])],
    )


def _campaign_dir(config: GapForgeConfig, campaign_state: CampaignState) -> Path:
    return config.project_root / campaign_state.campaign.project_id / "campaigns" / campaign_state.campaign.id
