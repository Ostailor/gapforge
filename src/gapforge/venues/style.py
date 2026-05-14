"""Rendering helpers for venue profiles."""

from __future__ import annotations

from gapforge.venues.profiles import VenueProfile


def render_venue_profile(profile: VenueProfile) -> str:
    lines = [
        f"# Venue Profile `{profile.id}`",
        "",
        f"- Name: {profile.name}",
        f"- Field: {profile.field}",
        f"- Venue type: `{profile.venue_type}`",
        f"- Paper style: `{profile.paper_style}`",
        f"- Page limit: {profile.page_limit or 'none'}",
        f"- Anonymity required: {profile.anonymity_required}",
        f"- Citation style: {profile.citation_style or 'not specified'}",
        f"- LaTeX/template hint: {profile.latex_template_hint or 'not specified'}",
        "",
        "## Scope",
        "",
        "This profile guides style, structure, and reviewer expectations. It does not imply acceptance or venue-specific rule compliance.",
        "",
        "## Required Sections",
        "",
        *[f"- `{section}`" for section in profile.required_sections],
        "",
        "## Common Section Order",
        "",
        *[f"- `{section}`" for section in profile.common_section_order],
        "",
        "## Artifact Expectations",
        "",
        *[f"- {item}" for item in profile.artifact_expectations],
        "",
        "## Reproducibility Expectations",
        "",
        *[f"- {item}" for item in profile.reproducibility_expectations],
        "",
        "## Reviewer Norms",
        "",
        *[f"- {item}" for item in profile.reviewer_norms],
        "",
        "## Limitations Expectations",
        "",
        *[f"- {item}" for item in profile.limitations_expectations],
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_venue_profile_list(profiles: list[VenueProfile]) -> str:
    lines = ["# Venue Profiles", ""]
    for profile in profiles:
        lines.extend(
            [
                f"## `{profile.id}`",
                "",
                f"- Name: {profile.name}",
                f"- Field: {profile.field}",
                f"- Venue type: `{profile.venue_type}`",
                f"- Paper style: `{profile.paper_style}`",
                f"- Page limit: {profile.page_limit or 'none'}",
                f"- Anonymity required: {profile.anonymity_required}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
