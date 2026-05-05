"""Stop-condition helpers for campaign controller decisions."""

from __future__ import annotations

from gapforge.models import CampaignStopCondition, Provenance
from gapforge.state import utc_now_compact, utc_now_iso


def campaign_stop_condition(campaign_id: str, *, reason: str, evidence: list[str] | None = None) -> CampaignStopCondition:
    return CampaignStopCondition(
        id=f"campaign-stop-{utc_now_compact()}",
        campaign_id=campaign_id,
        reason=reason,
        triggered=True,
        evidence=evidence or [],
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="campaign-controller",
            source_ids=[campaign_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Controller stopped the campaign for an explicit auditable condition.",
        ),
    )
