"""Metric registry and statistical plan rendering."""

from __future__ import annotations

from gapforge.models import MetricRecord, StatisticalTestPlan


def render_metric_registry_markdown(records: list[MetricRecord]) -> str:
    lines = ["# Metric Registry", ""]
    if not records:
        lines.append("No metrics registered yet.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        lines.extend(
            [
                f"## `{record.id}` {record.name}",
                "",
                f"- Type: `{record.metric_type}`",
                f"- Higher is better: {str(record.higher_is_better).lower()}",
                f"- Formula: {record.formula or 'not specified'}",
                f"- Required inputs: {', '.join(record.required_inputs) or 'none'}",
                "",
                record.description or "No description.",
                "",
            ]
        )
        _extend_list(lines, "Edge Cases", record.edge_cases)
    return "\n".join(lines).rstrip() + "\n"


def render_metric_card_markdown(record: MetricRecord) -> str:
    lines = [
        f"# Metric Card: {record.name}",
        "",
        f"- Metric ID: `{record.id}`",
        f"- Type: `{record.metric_type}`",
        f"- Higher is better: {str(record.higher_is_better).lower()}",
        f"- Formula: {record.formula or 'not specified'}",
        "",
        "## Description",
        "",
        record.description or "Not specified.",
        "",
    ]
    _extend_list(lines, "Required Inputs", record.required_inputs)
    _extend_list(lines, "Edge Cases", record.edge_cases)
    return "\n".join(lines).rstrip() + "\n"


def render_statistical_plan_markdown(plan: StatisticalTestPlan, metrics: list[MetricRecord]) -> str:
    metric_names = {metric.id: metric.name for metric in metrics}
    lines = [
        f"# Statistical Test Plan `{plan.id}`",
        "",
        f"- Protocol ID: `{plan.experiment_protocol_id or 'none'}`",
        f"- Test name: {plan.test_name or 'not specified'}",
        f"- Confidence interval method: {plan.confidence_interval_method or 'not specified'}",
        f"- Falsification threshold: {plan.falsification_threshold or 'not specified'}",
        "",
        "## Metrics",
        "",
    ]
    lines.extend([f"- `{metric_id}` {metric_names.get(metric_id, '')}".rstrip() for metric_id in plan.metric_ids] or ["- none"])
    _extend_list(lines, "Assumptions", plan.assumptions)
    lines.extend(
        [
            "## Sample Size Notes",
            "",
            plan.sample_size_notes or "Not specified.",
            "",
            "## Multiple Testing Notes",
            "",
            plan.multiple_testing_notes or "Not specified.",
            "",
            "## Power Notes",
            "",
            plan.power_notes or "Not specified.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _extend_list(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend([f"## {title}", ""])
    lines.extend([f"- {item}" for item in items] or ["- none"])
    lines.append("")
