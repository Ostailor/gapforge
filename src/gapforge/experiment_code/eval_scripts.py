"""Small render helpers for generated experiment scaffold files."""

from __future__ import annotations

from gapforge.models import BaselineCandidate, ExperimentProtocol, ReproducibilityChecklist


def metric_definitions(protocol: ExperimentProtocol) -> list[str]:
    """Return explicit metric definitions for a scaffold README or metrics module."""
    if not protocol.metrics:
        return ["No primary metric is defined yet; block implementation until the protocol is updated."]
    return [
        f"{metric}: define exact numerator, denominator, aggregation, and confidence interval before running."
        for metric in protocol.metrics
    ]


def baseline_names(baselines: list[BaselineCandidate]) -> list[str]:
    names = [candidate.baseline_name for candidate in baselines if candidate.baseline_name]
    return names or ["No validated baseline is available yet; keep placeholder interfaces clearly marked."]


def render_reproducibility_lines(checklist: ReproducibilityChecklist) -> list[str]:
    seeds = ", ".join(str(seed) for seed in checklist.random_seeds) or "not specified"
    lines = [
        f"Random seeds: {seeds}",
        f"Dataset versioning: {checklist.dataset_versioning or 'required before real runs'}",
        f"Environment spec: {checklist.environment_spec or 'record Python/package versions before real runs'}",
        f"Logging plan: {checklist.logging_plan or 'write metrics and config to artifacts/'}",
        f"Preregistered analysis: {checklist.preregistered_analysis or 'not preregistered'}",
        f"Error analysis: {checklist.error_analysis_plan or 'include false-positive/false-negative slices'}",
    ]
    lines.extend([f"Negative control: {item}" for item in checklist.negative_controls])
    return lines


def render_eval_script(protocol: ExperimentProtocol) -> str:
    metrics = protocol.metrics or ["primary_metric"]
    metric_list = ", ".join(repr(metric) for metric in metrics)
    return f'''"""Smoke evaluation entry point for the experiment scaffold.

This script intentionally does not report research results. It validates that
the package wiring, placeholder data path, metrics, and baseline interfaces run.
"""

from __future__ import annotations


METRICS = [{metric_list}]


def run_smoke() -> dict[str, object]:
    return {{
        "status": "smoke_only",
        "metrics_defined": METRICS,
        "results": "not run",
    }}


if __name__ == "__main__":
    print(run_smoke())
'''
