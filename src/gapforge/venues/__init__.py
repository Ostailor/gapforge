"""Venue profiles for top-conference-style manuscript generation."""

from gapforge.venues.profiles import VenueProfile, get_venue_profile, is_venue_profile, list_venue_profiles, venue_profiles_json
from gapforge.venues.style import render_venue_profile, render_venue_profile_list


def __getattr__(name: str):
    if name in {"VenueProfileManager", "profile_to_venue_template", "required_section_blockers"}:
        from gapforge.venues.constraints import VenueProfileManager, profile_to_venue_template, required_section_blockers

        return {
            "VenueProfileManager": VenueProfileManager,
            "profile_to_venue_template": profile_to_venue_template,
            "required_section_blockers": required_section_blockers,
        }[name]
    raise AttributeError(name)


__all__ = [
    "VenueProfile",
    "VenueProfileManager",
    "get_venue_profile",
    "is_venue_profile",
    "list_venue_profiles",
    "profile_to_venue_template",
    "render_venue_profile",
    "render_venue_profile_list",
    "required_section_blockers",
    "venue_profiles_json",
]
