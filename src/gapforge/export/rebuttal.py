"""Reviewer objection and rebuttal planning exports."""

from __future__ import annotations

from gapforge.models import ReviewerObjection


def render_rebuttal_plan(objections: list[ReviewerObjection]) -> str:
    lines = ["# Rebuttal Plan", ""]
    if not objections:
        lines.extend(
            [
                "No reviewer objections are linked yet.",
                "",
                "Before submission, run reviewer simulation and replace this placeholder with concrete response plans.",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"
    for objection in sorted(objections, key=lambda item: (_severity_rank(item.severity), item.category, item.id)):
        lines.extend(
            [
                f"## {objection.severity.title()} {objection.category}: {objection.id}",
                "",
                f"- Objection: {objection.objection}",
                f"- Why reviewer cares: {objection.why_reviewer_would_care}",
                f"- Evidence or prior work: {', '.join(objection.evidence_or_prior_work) or 'none'}",
                f"- Blocks submission: {objection.blocks_submission}",
                "",
                "### Response Plan",
                "",
                objection.suggested_fix or "Add a concrete response, extra analysis, or manuscript revision.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_reviewer_objections(objections: list[ReviewerObjection]) -> str:
    lines = ["# Reviewer Objections", ""]
    if not objections:
        lines.append("No reviewer objections linked yet.")
        return "\n".join(lines).rstrip() + "\n"
    for objection in objections:
        lines.extend(
            [
                f"## {objection.id}",
                "",
                f"- Severity: {objection.severity}",
                f"- Category: {objection.category}",
                f"- Blocks submission: {objection.blocks_submission}",
                f"- Objection: {objection.objection}",
                f"- Suggested fix: {objection.suggested_fix or 'not specified'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _severity_rank(severity: str) -> int:
    return {"fatal": 0, "major": 1, "minor": 2}.get(severity, 3)
