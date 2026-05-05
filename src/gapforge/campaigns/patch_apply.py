"""Apply validated campaign patches with provenance and partial acceptance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignState
from gapforge.models import CampaignDecision, CampaignMilestone, CampaignStep, CampaignStopCondition, Provenance
from gapforge.state import utc_now_compact, utc_now_iso


def apply_campaign_patch_paths(campaign_state: CampaignState, import_id: str, accepted_objects: list[dict[str, Any]]) -> None:
    files = {item["source_path"] for item in accepted_objects if item.get("type") == "file" and item.get("source_path")}
    for raw_path in sorted(files):
        path = Path(raw_path)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        apply_campaign_patch(campaign_state, import_id, path.name, payload)


def apply_campaign_patch(campaign_state: CampaignState, import_id: str, filename: str, payload: dict[str, Any]) -> None:
    if filename == "proposed_steps.json":
        for item in _items(payload.get("proposed_steps")):
            campaign_state.steps.append(
                CampaignStep(
                    id=str(item.get("id") or f"campaign-step-{utc_now_compact()}"),
                    campaign_id=campaign_state.campaign.id,
                    name=str(item.get("name") or "Proposed step"),
                    step_type=str(item.get("step_type") or "review"),
                    status=str(item.get("status") or "pending"),
                    input_artifacts=[str(value) for value in item.get("input_artifacts", []) if value],
                    output_artifacts=[str(value) for value in item.get("output_artifacts", []) if value],
                    provenance=_provenance(import_id, "Imported agent-backed proposed campaign step."),
                )
            )
    if filename == "stop_condition_patch.json":
        for item in _items(payload.get("stop_condition_patch")):
            campaign_state.stop_conditions.append(
                CampaignStopCondition(
                    id=str(item.get("id") or f"campaign-stop-{utc_now_compact()}"),
                    campaign_id=campaign_state.campaign.id,
                    reason=str(item.get("reason") or ""),
                    triggered=bool(item.get("triggered", True)),
                    evidence=[str(value) for value in item.get("evidence", []) if value],
                    created_at=utc_now_iso(),
                    provenance=_provenance(import_id, "Imported agent-backed campaign stop condition."),
                )
            )
    if filename in {"campaign_plan_patch.json", "final_recommendation_patch.json"}:
        campaign_state.decisions.append(
            CampaignDecision(
                id=f"campaign-decision-{utc_now_compact()}",
                campaign_id=campaign_state.campaign.id,
                iteration=len(campaign_state.decisions) + 1,
                decision_type="import_outputs",
                reason=str(payload.get("public_reasoning_summary") or f"Imported {filename}"),
                evidence=[filename],
                status="complete",
                provenance=_provenance(import_id, "Imported agent-backed campaign decision patch."),
            )
        )
    if filename.endswith("_patch.json"):
        campaign_state.milestones.append(
            CampaignMilestone(
                id=f"campaign-milestone-{utc_now_compact()}",
                campaign_id=campaign_state.campaign.id,
                milestone_type="package_ready" if "final" in filename else "reading_ready",
                status="complete",
                linked_artifacts=[filename],
                notes=f"Imported validated agent-backed campaign output from {filename}.",
                provenance=_provenance(import_id, "Imported campaign milestone from validated agent output."),
            )
        )


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _provenance(import_id: str, summary: str) -> Provenance:
    return Provenance(
        created_by_skill="campaign-patch-apply",
        source_ids=[import_id],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )
