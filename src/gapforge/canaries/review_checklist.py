"""Human review checklist rendering for canary records."""

from __future__ import annotations

from gapforge.models import CanaryRunProfile, CanaryRunRecord


def render_review_checklist(profile: CanaryRunProfile, record: CanaryRunRecord | None = None) -> str:
    lines = [
        f"# Canary Review Checklist: {profile.id}",
        "",
        f"- Title: {profile.title}",
        f"- Requires Codex/GPT-5.4: {str(profile.requires_codex).lower()}",
        f"- Requires human review: {str(profile.requires_human_review).lower()}",
        "",
        "## Pass Criteria",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in profile.pass_criteria)
    lines.extend(["", "## Expected Artifacts", ""])
    lines.extend(f"- [ ] `{item}`" for item in profile.expected_artifacts)
    lines.extend(
        [
            "",
            "## Evidence Safety",
            "",
            "- [ ] No fake citations are present.",
            "- [ ] No unsupported high-confidence claims are present.",
            "- [ ] Novelty dossiers include closest prior work or explicitly mark novelty unknown.",
            "- [ ] Strict report remains conservative under weak coverage.",
            "- [ ] Human review notes are recorded when required.",
            "",
        ]
    )
    if record is not None:
        lines.extend(
            [
                "## Record",
                "",
                f"- Canary ID: `{record.id}`",
                f"- Status: {record.status}",
                f"- Run ID: `{record.run_id or 'none'}`",
                f"- Project ID: `{record.project_id or 'none'}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
