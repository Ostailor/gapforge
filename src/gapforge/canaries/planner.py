"""Canary run planning."""

from __future__ import annotations

from gapforge.canaries.profiles import get_canary_profile
from gapforge.canaries.review_checklist import render_review_checklist
from gapforge.models import CanaryRunProfile


class CanaryPlanner:
    def plan(self, profile_id: str) -> str:
        return render_canary_plan(get_canary_profile(profile_id))


def render_canary_plan(profile: CanaryRunProfile) -> str:
    lines = [
        f"# Canary Plan: {profile.id}",
        "",
        f"- Title: {profile.title}",
        f"- Topic: {profile.topic}",
        f"- Project: {profile.project_name or 'none'}",
        f"- Source profile: {profile.source_profile}",
        f"- Mode: {profile.mode}",
        f"- Max papers: {profile.max_papers}",
        f"- Max expanded papers: {profile.max_expanded_papers}",
        f"- Requires network: {str(profile.requires_network).lower()}",
        f"- Requires Codex/GPT-5.4: {str(profile.requires_codex).lower()}",
        f"- Requires human review: {str(profile.requires_human_review).lower()}",
        "",
        "## Required Steps",
        "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(profile.required_steps, start=1))
    lines.extend(["", "## Recommended Commands", ""])
    lines.extend(f"```bash\n{command}\n```" for command in profile.recommended_commands)
    lines.extend(["", "## Expected Artifacts", ""])
    lines.extend(f"- `{artifact}`" for artifact in profile.expected_artifacts)
    lines.extend(["", "## Pass Criteria", ""])
    lines.extend(f"- {criterion}" for criterion in profile.pass_criteria)
    lines.extend(["", "## Known Risks", ""])
    lines.extend(f"- {risk}" for risk in profile.known_risks)
    lines.extend(["", render_review_checklist(profile)])
    return "\n".join(lines).rstrip() + "\n"
