"""Markdown table rendering for empirical result summaries."""

from __future__ import annotations

from gapforge.models import EmpiricalClaim, MetricResult, ResultSummary


def render_metric_results_table(results: list[MetricResult]) -> str:
    lines = [
        "| Metric result | Metric | Value | CI | Sample size | Dataset | Baseline | Artifact |",
        "| --- | --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    if not results:
        lines.append("| none | none |  |  |  |  |  |  |")
        return "\n".join(lines)
    for result in results:
        ci = _format_ci(result.confidence_interval)
        lines.append(
            "| "
            f"`{result.id}` | `{result.metric_id}` | {result.value:g} | {ci} | {result.sample_size or 0} | "
            f"`{result.dataset_id or 'unknown'}` | `{result.baseline_id or 'none'}` | `{result.raw_artifact_id}` |"
        )
    return "\n".join(lines)


def render_empirical_claims_table(claims: list[EmpiricalClaim]) -> str:
    lines = [
        "| Claim | Status | Confidence | Metric results | Limitations |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not claims:
        lines.append("| none | none | none | none | none |")
        return "\n".join(lines)
    for claim in claims:
        lines.append(
            "| "
            f"`{claim.id}` {claim.text} | `{claim.status}` | `{claim.confidence}` | "
            f"{', '.join(f'`{item}`' for item in claim.metric_result_ids) or 'none'} | "
            f"{'; '.join(claim.limitations) or 'none'} |"
        )
    return "\n".join(lines)


def render_result_summary_markdown(summary: ResultSummary) -> str:
    lines = [
        f"# Result Summary `{summary.execution_id}`",
        "",
        "## Metric Results",
        "",
        render_metric_results_table(summary.metric_results),
        "",
        "## Empirical Claims",
        "",
        render_empirical_claims_table(summary.empirical_claims),
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {item}" for item in summary.failures] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in summary.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _format_ci(values: list[float]) -> str:
    if not values:
        return "missing"
    if len(values) == 2:
        return f"[{values[0]:g}, {values[1]:g}]"
    return ", ".join(f"{value:g}" for value in values)
