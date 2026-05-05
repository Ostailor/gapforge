"""Evidence-based rebuttal planning renderers."""

from __future__ import annotations

from gapforge.models import RebuttalPlan, ReviewPanel


def render_rebuttal_plans_markdown(panels: list[ReviewPanel]) -> str:
    lines = ["# Rebuttal Plans", ""]
    if not panels:
        lines.append("No review panels generated yet.")
        return "\n".join(lines).rstrip() + "\n"
    for panel in panels:
        lines.extend([f"## `{panel.experiment_or_direction_id}`", ""])
        if not panel.rebuttal_plan:
            lines.extend(["No rebuttal actions generated.", ""])
            continue
        for plan in panel.rebuttal_plan:
            _extend_plan(lines, plan)
    return "\n".join(lines).rstrip() + "\n"


def render_meta_review_markdown(panels: list[ReviewPanel]) -> str:
    lines = ["# Meta Review", ""]
    if not panels:
        lines.append("No review panels generated yet.")
        return "\n".join(lines).rstrip() + "\n"
    for panel in panels:
        lines.extend(
            [
                f"## `{panel.experiment_or_direction_id}`",
                "",
                f"- Decision risk: {panel.decision_risk}",
                f"- Area chair summary: {panel.area_chair_summary or 'Not generated.'}",
                "",
                panel.meta_review or "No meta-review generated.",
                "",
                "### Required Changes",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in panel.required_changes] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _extend_plan(lines: list[str], plan: RebuttalPlan) -> None:
    lines.extend(
        [
            f"### Response for `{plan.target_review_id}`",
            "",
            f"- Strategy: {plan.response_strategy or 'Not specified.'}",
            f"- Evidence needed: {', '.join(plan.evidence_needed) or 'none'}",
            f"- Experiments to add: {', '.join(plan.experiments_to_add) or 'none'}",
            f"- Citations to add: {', '.join(plan.citations_to_add) or 'none'}",
            f"- Claims to soften: {', '.join(plan.claims_to_soften) or 'none'}",
            f"- Risks: {', '.join(plan.risks) or 'none'}",
            "",
        ]
    )
