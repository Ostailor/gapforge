"""Statistical test planning for experiment metrics."""

from __future__ import annotations

import hashlib

from gapforge.metrics.confidence import confidence_interval_method, power_notes, sample_size_notes
from gapforge.models import ExperimentProtocol, MetricRecord, Provenance, StatisticalTestPlan
from gapforge.state import utc_now_iso


def build_statistical_test_plan(
    *,
    experiment_protocol: ExperimentProtocol | None,
    metrics: list[MetricRecord],
    workspace_id: str = "",
) -> StatisticalTestPlan:
    metric_ids = [metric.id for metric in metrics]
    low_fpr = _has_low_fpr_metric(metrics)
    test_name = "low-FPR exact proportion analysis" if low_fpr else _default_test_name(metrics)
    assumptions = _assumptions(metrics, low_fpr)
    threshold = _falsification_threshold(experiment_protocol, metrics, low_fpr)
    protocol_id = experiment_protocol.id if experiment_protocol else ""
    return StatisticalTestPlan(
        id=f"stats-plan-{_stable_id(workspace_id, protocol_id, '-'.join(metric_ids))}",
        experiment_protocol_id=protocol_id,
        metric_ids=metric_ids,
        test_name=test_name,
        assumptions=assumptions,
        sample_size_notes=sample_size_notes(metrics),
        confidence_interval_method=confidence_interval_method(metrics),
        multiple_testing_notes=_multiple_testing_notes(metrics),
        power_notes=power_notes(metrics),
        falsification_threshold=threshold,
        provenance=Provenance(
            created_by_skill="stats-planner",
            source_ids=[workspace_id, protocol_id, *metric_ids],
            timestamp=utc_now_iso(),
            reasoning_summary="Planned statistical analysis from registered metrics and experiment protocol.",
        ),
    )


def _has_low_fpr_metric(metrics: list[MetricRecord]) -> bool:
    text = " ".join([metric.id + " " + metric.name + " " + metric.description for metric in metrics]).lower()
    return any(term in text for term in ["false positive", "false-positive", "fpr", "specificity", "low fpr"])


def _default_test_name(metrics: list[MetricRecord]) -> str:
    types = {metric.metric_type for metric in metrics}
    if "ranking" in types:
        return "paired bootstrap ranking comparison"
    if "runtime" in types:
        return "repeated-run runtime summary"
    if {"classification", "detection"} & types:
        return "paired proportion or bootstrap classification comparison"
    if "regression" in types:
        return "paired bootstrap regression-error comparison"
    return "bootstrap confidence interval plan"


def _assumptions(metrics: list[MetricRecord], low_fpr: bool) -> list[str]:
    assumptions = ["Metrics are computed on frozen splits before final analysis.", "Baselines and proposed method use the same examples."]
    if low_fpr:
        assumptions.append("Negative examples are numerous enough for rare false-positive estimates.")
        assumptions.append("Alert threshold or budget is fixed before inspecting final test results.")
    if any(metric.metric_type == "runtime" for metric in metrics):
        assumptions.append("Runtime measurements use fixed hardware and enough repeated runs.")
    return assumptions


def _multiple_testing_notes(metrics: list[MetricRecord]) -> str:
    if len(metrics) <= 1:
        return "Single primary metric; report secondary metrics as exploratory."
    return "Declare one primary metric before running; treat remaining metrics as secondary or apply correction for multiple comparisons."


def _falsification_threshold(
    experiment_protocol: ExperimentProtocol | None,
    metrics: list[MetricRecord],
    low_fpr: bool,
) -> str:
    if experiment_protocol is not None and experiment_protocol.failure_modes:
        return experiment_protocol.failure_modes[0]
    if low_fpr:
        return "Hypothesis is not supported if confidence intervals overlap the strongest baseline at the target FPR."
    if metrics:
        direction = "higher" if metrics[0].higher_is_better else "lower"
        return f"Hypothesis is not supported unless the primary metric is meaningfully {direction} than the strongest baseline."
    return "Define a falsification threshold before execution."


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
