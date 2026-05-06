"""Markdown rendering for v0.4 release-gate enforcement."""

from __future__ import annotations

from gapforge.release_gate.v04 import V04ReleaseGateResult


def render_v04_release_gate_markdown(result: V04ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.4 Actual-Run Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Deterministic CI passed: {str(result.deterministic_ci_passed).lower()}",
        f"- Fake-agent campaign canary passed: {str(result.fake_agent_canary_passed).lower()}",
        f"- Accepted real campaigns: {result.accepted_real_campaign_count}",
        f"- Experiment-ready campaign present: {str(result.experiment_ready_campaign_present).lower()}",
        f"- Refusal campaign present: {str(result.refusal_campaign_present).lower()}",
        f"- Full-text/manual-PDF campaign present: {str(result.full_text_campaign_present).lower()}",
        f"- Missing campaign types: {', '.join(result.missing_campaign_types) if result.missing_campaign_types else 'none'}",
        "",
        "## Fake vs Real",
        "",
        result.fake_vs_real_explanation,
        "",
        "## Task-Pack Actual-Run Eligibility",
        "",
        result.task_pack_actual_run_explanation,
        "",
        "## Blocking Failures",
        "",
    ]
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Blocker Categories", ""])
    if result.blocker_categories:
        for category, blockers in result.blocker_categories.items():
            lines.extend([f"### {category.replace('_', ' ').title()}", ""])
            lines.extend(f"- {item}" for item in blockers)
            lines.append("")
    else:
        lines.append("- none")
    lines.extend(["", "## Next Commands", ""])
    lines.extend([f"- `{item}`" for item in result.next_commands] or ["- none"])
    lines.extend(["", "## Campaign Assessments", ""])
    for campaign in result.campaigns:
        lines.extend(
            [
                f"### `{campaign.campaign_id}`",
                "",
                f"- Project: `{campaign.project_id}`",
                f"- Mode: `{campaign.mode}`",
                f"- Accepted real campaign: {str(campaign.accepted_real_campaign).lower()}",
                f"- Experiment-ready: {str(campaign.experiment_ready).lower()}",
                f"- Refusal: {str(campaign.refusal).lower()}",
                f"- Full text/manual PDF: {str(campaign.full_text_or_manual_pdf).lower()}",
                f"- Actual-run attestation: {str(campaign.actual_run_attestation).lower()}",
                f"- Validated imports: {str(campaign.validated_imported_outputs).lower()}",
                f"- Source coverage: {str(campaign.source_coverage).lower()}",
                f"- Retrieval index: {str(campaign.retrieval_index).lower()}",
                f"- Novelty/refusal gate: {str(campaign.novelty_or_refusal).lower()}",
                f"- Human accepted: {str(campaign.human_review_accepted).lower()}",
                f"- Campaign report: {str(campaign.campaign_report).lower()}",
                f"- Explicit stop reason: {str(campaign.explicit_stop_reason).lower()}",
                "",
                "Blockers:",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in campaign.blockers] or ["- none"])
        lines.extend(["", "Next commands:", ""])
        lines.extend([f"- `{item}`" for item in campaign.next_commands] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
