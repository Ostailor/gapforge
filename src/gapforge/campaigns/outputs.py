"""Compatibility entrypoints for campaign task output validation/import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.config import GapForgeConfig
from gapforge.models import to_plain


def validate_campaign_outputs(config: GapForgeConfig, campaign_id: str, task_id: str, paths: list[Path]) -> dict[str, Any]:
    return to_plain(CampaignOutputImporter(config).validate(campaign_id, task_id, paths))


def import_campaign_outputs(
    config: GapForgeConfig,
    campaign_id: str,
    task_id: str,
    paths: list[Path],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    return to_plain(CampaignOutputImporter(config).import_outputs(campaign_id, task_id, paths, dry_run=dry_run))
