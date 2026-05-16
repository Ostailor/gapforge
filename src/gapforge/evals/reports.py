"""Report rendering helpers for eval output."""

from __future__ import annotations

from typing import Any

from gapforge.evals.metrics import EvalScoreGroup


def render_score_group_summary(report: Any) -> list[str]:
    group = report.aggregate_score_group()
    lines = [
        "## Grouped Scores",
        "",
        f"- regression_score: {group.regression_score:.3f}",
        f"- safety_score: {group.safety_score:.3f}",
        f"- workflow_score: {group.workflow_score:.3f}",
        f"- paper_quality_score: {group.paper_quality_score:.3f}",
        f"- release_gate_score: {group.release_gate_score:.3f}",
        f"- overall_score: {group.overall_score:.3f}",
        f"- provenance: {', '.join(f'{key}={value}' for key, value in sorted(group.provenance.items()))}",
        "",
    ]
    lines.extend(_render_list("Blocking Failures", group.blocking_failures))
    lines.extend(_render_list("Warnings", group.warnings))
    if group.paper_quality_score < 0.6 and group.workflow_score >= 0.8:
        lines.extend(
            [
                "Paper quality is visibly below workflow completeness; do not treat artifact completeness as paper readiness.",
                "",
            ]
        )
    return lines


def render_fixture_score_group(group: EvalScoreGroup) -> list[str]:
    lines = [
        "### Grouped Scores",
        "",
        f"- regression_score: {group.regression_score:.3f}",
        f"- safety_score: {group.safety_score:.3f}",
        f"- workflow_score: {group.workflow_score:.3f}",
        f"- paper_quality_score: {group.paper_quality_score:.3f}",
        f"- release_gate_score: {group.release_gate_score:.3f}",
        f"- overall_score: {group.overall_score:.3f}",
        "",
    ]
    lines.extend(_render_list("Blocking Failures", group.blocking_failures))
    lines.extend(_render_list("Warnings", group.warnings))
    return lines


def _render_list(title: str, values: list[str]) -> list[str]:
    return [f"### {title}", "", *([f"- {value}" for value in values] if values else ["- none"]), ""]
