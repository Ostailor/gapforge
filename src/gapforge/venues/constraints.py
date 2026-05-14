"""Venue profile constraints and manuscript integration."""

from __future__ import annotations

import json

from gapforge.config import GapForgeConfig
from gapforge.manuscript.models import ManuscriptState, VenueTemplate
from gapforge.models import Provenance, to_plain
from gapforge.state import utc_now_iso
from gapforge.venues.profiles import VenueProfile, get_venue_profile


class VenueProfileManager:
    """Assign rich venue profiles to manuscript state."""

    def __init__(self, config: GapForgeConfig) -> None:
        from gapforge.manuscript.manager import ManuscriptManager

        self.config = config
        self.manuscript_manager = ManuscriptManager(config)

    def set_profile(self, manuscript_id: str, venue_id: str) -> ManuscriptState:
        profile = get_venue_profile(venue_id)
        state = self.manuscript_manager.load_state(manuscript_id)
        state.manuscript.target_venue = profile.id
        state.manuscript.updated_at = utc_now_iso()
        state.provenance.append(
            Provenance(
                created_by_skill="manuscript-venue-profile",
                source_ids=[manuscript_id, profile.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Assigned venue profile for paper structure and reviewer expectation guidance, not acceptance claims.",
            )
        )
        self.manuscript_manager._save_state(state)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        (root / "submission" / "venue_profile.json").write_text(json.dumps(to_plain(profile), indent=2) + "\n", encoding="utf-8")
        (root / "submission" / "venue_template.json").write_text(
            json.dumps(to_plain(profile_to_venue_template(profile)), indent=2) + "\n",
            encoding="utf-8",
        )
        return state


def profile_to_venue_template(profile: VenueProfile) -> VenueTemplate:
    return VenueTemplate(
        id=profile.id,
        name=profile.name,
        venue_type=profile.venue_type,
        format="latex",
        sections_required=profile.required_sections,
        page_limit=profile.page_limit,
        anonymization_required=profile.anonymity_required,
        artifact_policy=_artifact_policy(profile),
        ethics_required="ethics" in profile.required_sections,
        reproducibility_required=bool(profile.reproducibility_expectations),
        citation_style=profile.citation_style,
        provenance=profile.provenance,
    )


def required_section_blockers(profile: VenueProfile, present_section_types: set[str]) -> list[str]:
    missing = [section_type for section_type in profile.required_sections if section_type not in present_section_types]
    return [f"Required section `{section_type}` is missing for venue profile `{profile.id}`." for section_type in missing]


def _artifact_policy(profile: VenueProfile) -> str:
    text = " ".join(profile.artifact_expectations).lower()
    if "required" in text:
        return "required"
    if profile.venue_type == "preprint":
        return "optional"
    if profile.artifact_expectations:
        return "expected"
    return "optional"
