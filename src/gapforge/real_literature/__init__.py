"""Real-literature campaign profiles and acceptance helpers for v0.5."""

from gapforge.real_literature.acceptance import evaluate_real_literature_record
from gapforge.real_literature.dry_run import build_real_campaign_dry_run, render_real_campaign_dry_run, write_real_campaign_dry_run
from gapforge.real_literature.profiles import default_real_literature_profiles, get_real_literature_profile, render_real_literature_plan
from gapforge.real_literature.review import RealLiteratureReviewManager
from gapforge.real_literature.runner import RealLiteratureCampaignManager

__all__ = [
    "RealLiteratureCampaignManager",
    "RealLiteratureReviewManager",
    "build_real_campaign_dry_run",
    "default_real_literature_profiles",
    "evaluate_real_literature_record",
    "get_real_literature_profile",
    "render_real_campaign_dry_run",
    "render_real_literature_plan",
    "write_real_campaign_dry_run",
]
