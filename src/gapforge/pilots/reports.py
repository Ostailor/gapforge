"""Markdown reports for pilot runs."""

from __future__ import annotations

import json

from gapforge.models import PilotAcceptanceSummary, PilotRunRecord, PilotSpec, to_plain


def render_pilot_report(spec: PilotSpec, record: PilotRunRecord, summary: PilotAcceptanceSummary) -> str:
    lines = [
        f"# Pilot Report: {spec.name}",
        "",
        f"- Pilot run: `{record.id}`",
        f"- Topic: {spec.topic}",
        f"- Project: `{record.project_id or 'missing'}`",
        f"- Campaign: `{record.campaign_id or 'missing'}`",
        f"- Status: `{record.status}`",
        f"- Outcome: `{record.outcome_type}`",
        f"- Acceptance passed: {str(summary.passed).lower()}",
        f"- Release gate eligible: {str(summary.release_gate_eligible).lower()}",
        "",
        "## Artifact Paths",
        "",
    ]
    if record.artifact_paths:
        lines.extend(f"- `{key}`: {path}" for key, path in sorted(record.artifact_paths.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in record.blockers] or ["- none"])
    lines.extend(["", "## Acceptance Summary", "", "```json", json.dumps(to_plain(summary), indent=2), "```", ""])
    return "\n".join(lines)


def render_pilot_acceptance(summary: PilotAcceptanceSummary) -> str:
    lines = [
        f"# Pilot Acceptance: {summary.pilot_id}",
        "",
        f"- Passed: {str(summary.passed).lower()}",
        f"- Outcome: `{summary.outcome_type}`",
        f"- Accepted direction: `{summary.accepted_direction_id or 'none'}`",
        f"- Human review: `{summary.human_review_status}`",
        f"- Release gate eligible: {str(summary.release_gate_eligible).lower()}",
        "",
        "## Refusal Reason",
        "",
        summary.refusal_reason or "none",
        "",
        "## Product Failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in summary.product_failures] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"
