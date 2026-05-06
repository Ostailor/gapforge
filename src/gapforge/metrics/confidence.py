"""Confidence interval guidance for metric planning."""

from __future__ import annotations

from gapforge.models import MetricRecord


def confidence_interval_method(metrics: list[MetricRecord]) -> str:
    text = _metric_text(metrics)
    if _is_low_fpr(text):
        return "exact/binomial confidence intervals for false-positive proportions; report numerator, denominator, and target FPR"
    if any(term in text for term in ["precision", "recall", "true positive", "abstention"]):
        return "bootstrap or Wilson-style intervals for proportions, stratified by split when possible"
    if any(term in text for term in ["auroc", "auprc", "ranking"]):
        return "paired bootstrap confidence intervals over examples or query groups"
    if any(term in text for term in ["runtime", "latency"]):
        return "median and interquartile range across repeated runs on fixed hardware"
    return "bootstrap confidence intervals for primary metrics"


def sample_size_notes(metrics: list[MetricRecord]) -> str:
    text = _metric_text(metrics)
    if _is_low_fpr(text):
        return (
            "Low-FPR claims need large negative pools. For a target FPR of 0.1%, thousands to tens of thousands of "
            "negative examples may be needed; small fixture or smoke runs can only validate wiring."
        )
    if any(term in text for term in ["runtime", "latency"]):
        return "Use repeated measurements and report hardware, warmup, and variance."
    return "Predefine minimum detectable effect, number of seeds, and analysis population before inspecting final results."


def power_notes(metrics: list[MetricRecord]) -> str:
    text = _metric_text(metrics)
    if _is_low_fpr(text):
        return "Power depends on rare negative-event counts; report when the study is underpowered for the claimed alert budget."
    return "Document minimum detectable effect and whether the run is pilot or main."


def _metric_text(metrics: list[MetricRecord]) -> str:
    return " ".join([metric.id + " " + metric.name + " " + metric.description + " " + metric.metric_type for metric in metrics]).lower()


def _is_low_fpr(text: str) -> bool:
    return any(term in text for term in ["false positive", "false-positive", "fpr", "specificity", "low-fpr", "low fpr"])
