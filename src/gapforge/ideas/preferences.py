"""Human preference profiles for v2 idea discovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaPreferenceProfile, validate_contribution_type
from gapforge.ideas.store import IdeaStore
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso


class IdeaPreferenceManager:
    """Persist project-level human taste without weakening evidence gates."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)

    def save_profile(
        self,
        *,
        project_id: str,
        preferred_contribution_types: list[str] | None = None,
        preferred_domains: list[str] | None = None,
        risk_tolerance: str = "",
        time_budget: str = "",
        compute_budget: str = "",
        publication_target: str = "",
        avoid_topics: list[str] | None = None,
        notes: str = "",
    ) -> IdeaPreferenceProfile:
        self.project_manager.load_project(project_id)
        contribution_types = _dedupe(preferred_contribution_types or [])
        for contribution_type in contribution_types:
            validate_contribution_type(contribution_type)
        now = utc_now_iso()
        profile = IdeaPreferenceProfile(
            id=_profile_id(project_id),
            project_id=project_id,
            preferred_contribution_types=contribution_types,
            preferred_domains=_dedupe(preferred_domains or []),
            risk_tolerance=risk_tolerance or "medium",
            time_budget=time_budget,
            compute_budget=compute_budget,
            publication_target=publication_target,
            avoid_topics=_dedupe(avoid_topics or []),
            notes=notes,
            provenance=Provenance(
                created_by_skill="idea-preferences",
                source_ids=[project_id],
                timestamp=now,
                reasoning_summary="Recorded human preference profile for idea discovery scoring. Preferences do not override gates.",
            ),
        )
        self.store.add_preference_profile(profile)
        self.write_report(project_id)
        return profile

    def latest_profile(self, project_id: str) -> IdeaPreferenceProfile | None:
        profiles = self.store.load_state(project_id).preference_profiles
        return profiles[-1] if profiles else None

    def render_report(self, project_id: str) -> str:
        profiles = self.store.load_state(project_id).preference_profiles
        lines = [
            "# Idea Preference Profiles",
            "",
            "Preferences shape search and tournament scoring, but do not waive evidence, novelty, or review gates.",
            "",
        ]
        if not profiles:
            lines.append("- none")
            return "\n".join(lines).rstrip() + "\n"
        for profile in profiles:
            lines.extend(
                [
                    f"## `{profile.id}`",
                    "",
                    f"- Preferred contribution types: {', '.join(profile.preferred_contribution_types) or 'none'}",
                    f"- Preferred domains: {', '.join(profile.preferred_domains) or 'none'}",
                    f"- Risk tolerance: {profile.risk_tolerance or 'unspecified'}",
                    f"- Time budget: {profile.time_budget or 'unspecified'}",
                    f"- Compute budget: {profile.compute_budget or 'unspecified'}",
                    f"- Publication target: {profile.publication_target or 'unspecified'}",
                    f"- Avoid topics: {', '.join(profile.avoid_topics) or 'none'}",
                    f"- Notes: {profile.notes or 'none'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        program = self.project_manager.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_preferences.md").write_text(report, encoding="utf-8")
        return report


def _profile_id(project_id: str) -> str:
    digest = hashlib.sha1(project_id.encode()).hexdigest()[:10]
    return f"idea-preferences-{digest}"


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result
