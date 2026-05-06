"""Statistical analysis helpers for artifact-backed experiment results."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentWorkspace, MetricRecord, MetricResult, Provenance, ResultSummary, to_plain
from gapforge.results.parser import ResultParser
from gapforge.state import utc_now_iso

LOW_FPR_TERMS = ("false positive", "false-positive", "false_positive", "fpr", "low-fpr", "low fpr", "specificity")
LOW_FPR_SAMPLE_WARNING_THRESHOLD = 10_000


@dataclass(slots=True)
class MetricAnalysis:
    metric_result_id: str
    execution_id: str
    metric_id: str
    dataset_id: str = ""
    baseline_id: str = ""
    split_name: str = ""
    value: float = 0.0
    sample_size: int = 0
    confidence_interval: list[float] = field(default_factory=list)
    confidence_method: str = ""
    exact_count_summary: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PairedDifferenceSummary:
    metric_id: str
    dataset_id: str = ""
    split_name: str = ""
    baseline_a: str = ""
    baseline_b: str = ""
    value_a: float = 0.0
    value_b: float = 0.0
    difference_b_minus_a: float = 0.0
    warning: str = "Exploratory summary only; no paired per-example artifact was available."


@dataclass(slots=True)
class StatisticalAnalysisReport:
    id: str
    workspace_id: str
    execution_ids: list[str] = field(default_factory=list)
    metric_analyses: list[MetricAnalysis] = field(default_factory=list)
    paired_differences: list[PairedDifferenceSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    multiple_testing_warning: str = ""
    low_fpr_power_warnings: list[str] = field(default_factory=list)
    source_summary_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="result-statistics"))


def binomial_confidence_interval(successes: int, total: int, confidence: float = 0.95) -> list[float]:
    """Return a Wilson score interval for a binomial rate.

    The implementation is deterministic and standard-library only. It is a
    conservative reporting aid, not a significance test.
    """

    if total <= 0:
        return []
    bounded_successes = min(max(successes, 0), total)
    z = _normal_z(confidence)
    proportion = bounded_successes / total
    denominator = 1 + (z * z / total)
    center = (proportion + (z * z / (2 * total))) / denominator
    margin = (z / denominator) * math.sqrt((proportion * (1 - proportion) / total) + (z * z / (4 * total * total)))
    return [max(0.0, center - margin), min(1.0, center + margin)]


def bootstrap_confidence_interval(values: list[float], confidence: float = 0.95) -> list[float]:
    """Return a deterministic percentile-style interval for scalar samples.

    This is intentionally simple: GapForge does not infer significance from it.
    It provides a reproducible uncertainty range until richer per-example
    bootstrap artifacts are available.
    """

    if not values:
        return []
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return [sorted_values[0], sorted_values[0]]
    alpha = max(0.0, min(1.0, 1 - confidence))
    lower_index = math.floor((alpha / 2) * (len(sorted_values) - 1))
    upper_index = math.ceil((1 - alpha / 2) * (len(sorted_values) - 1))
    return [sorted_values[lower_index], sorted_values[upper_index]]


class ResultStatisticsAnalyzer:
    """Analyze parsed metric results and write uncertainty reports."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.parser = ResultParser(config)
        self.metric_registry = MetricRegistry(config)

    def analyze_execution(self, execution_id: str) -> StatisticalAnalysisReport:
        workspace, _execution = ExperimentRunner(self.config).find_execution(execution_id)
        summary = self.parser.load_or_parse_summary(execution_id)
        report = self._build_report(workspace, [summary], report_scope=execution_id)
        self._write_report(workspace, report, stem=f"analysis_report_{execution_id}")
        self._write_report(workspace, report, stem="analysis_report")
        return report

    def analyze_workspace(self, workspace_id: str) -> StatisticalAnalysisReport:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        summaries: list[ResultSummary] = []
        warnings: list[str] = []
        for execution in self.workspace_manager.list_execution_records(workspace.id):
            try:
                summaries.append(self.parser.load_or_parse_summary(execution.id))
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                warnings.append(f"Could not analyze execution `{execution.id}`: {exc}")
        report = self._build_report(workspace, summaries, report_scope="workspace")
        report.warnings.extend(_unique(warnings))
        if not summaries:
            report.warnings.append("No experiment executions were available; no metric uncertainty could be analyzed.")
        self._write_report(workspace, report, stem="analysis_report")
        return report

    def low_fpr_power_check(self, workspace_id: str) -> StatisticalAnalysisReport:
        report = self.analyze_workspace(workspace_id)
        workspace = self.workspace_manager.load_workspace(workspace_id)
        self._write_report(workspace, report, stem="low_fpr_power_check")
        return report

    def _build_report(
        self,
        workspace: ExperimentWorkspace,
        summaries: list[ResultSummary],
        *,
        report_scope: str,
    ) -> StatisticalAnalysisReport:
        metric_lookup = _metric_lookup(self.metric_registry.list_metrics(workspace.id))
        all_results = [result for summary in summaries for result in summary.metric_results]
        metric_analyses = [_analyze_metric_result(result, metric_lookup) for result in all_results]
        multiple_testing_warning = multiple_testing_warning_for_results(all_results)
        low_fpr_warnings = _unique(
            warning for analysis in metric_analyses for warning in analysis.warnings if "low-FPR" in warning or "false positive" in warning
        )
        warnings = _unique([item for summary in summaries for item in [*summary.limitations, *summary.failures]])
        if multiple_testing_warning:
            warnings.append(multiple_testing_warning)
        if all_results and not any(analysis.confidence_interval for analysis in metric_analyses):
            warnings.append("No confidence intervals were available or computable from the parsed metric results.")
        report_id = f"analysis-{_stable_id(workspace.id, report_scope, *[summary.execution_id for summary in summaries])}"
        return StatisticalAnalysisReport(
            id=report_id,
            workspace_id=workspace.id,
            execution_ids=[summary.execution_id for summary in summaries],
            metric_analyses=metric_analyses,
            paired_differences=paired_difference_summary(all_results),
            warnings=_unique(warnings),
            multiple_testing_warning=multiple_testing_warning,
            low_fpr_power_warnings=low_fpr_warnings,
            source_summary_ids=[summary.execution_id for summary in summaries],
            provenance=Provenance(
                created_by_skill="result-statistics",
                source_ids=[workspace.id, *[summary.execution_id for summary in summaries]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Computed reproducible uncertainty summaries from parsed metric artifacts without overstating significance."
                ),
            ),
        )

    def _write_report(self, workspace: ExperimentWorkspace, report: StatisticalAnalysisReport, *, stem: str) -> None:
        reports_dir = Path(workspace.root_dir) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{stem}.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (reports_dir / f"{stem}.md").write_text(render_analysis_report_markdown(report), encoding="utf-8")


def _analyze_metric_result(result: MetricResult, metric_lookup: dict[str, MetricRecord]) -> MetricAnalysis:
    metric = metric_lookup.get(result.metric_id)
    warnings: list[str] = []
    interval = list(result.confidence_interval)
    method = "reported"
    count_summary = exact_count_summary(result)
    if not interval and _looks_like_rate(result, metric) and result.sample_size > 0:
        successes = round(result.value * result.sample_size)
        interval = binomial_confidence_interval(successes, result.sample_size)
        method = "wilson_binomial"
    elif not interval and result.sample_size <= 0:
        warnings.append("Sample size is missing; confidence interval could not be computed.")
        method = ""
    elif not interval:
        method = ""
    if _is_low_fpr_metric(result, metric):
        warnings.extend(low_fpr_sample_size_warnings(result, metric))
    return MetricAnalysis(
        metric_result_id=result.id,
        execution_id=result.execution_id,
        metric_id=result.metric_id,
        dataset_id=result.dataset_id,
        baseline_id=result.baseline_id,
        split_name=result.split_name,
        value=result.value,
        sample_size=result.sample_size,
        confidence_interval=interval,
        confidence_method=method,
        exact_count_summary=count_summary,
        warnings=_unique(warnings),
    )


def paired_difference_summary(results: list[MetricResult]) -> list[PairedDifferenceSummary]:
    groups: dict[tuple[str, str, str], list[MetricResult]] = {}
    for result in results:
        key = (result.metric_id, result.dataset_id, result.split_name)
        groups.setdefault(key, []).append(result)
    summaries: list[PairedDifferenceSummary] = []
    for (metric_id, dataset_id, split_name), grouped_results in groups.items():
        baseline_results = [item for item in grouped_results if item.baseline_id]
        unique_by_baseline: dict[str, MetricResult] = {}
        for item in baseline_results:
            unique_by_baseline.setdefault(item.baseline_id, item)
        if len(unique_by_baseline) < 2:
            continue
        baseline_a, baseline_b = list(unique_by_baseline.values())[:2]
        summaries.append(
            PairedDifferenceSummary(
                metric_id=metric_id,
                dataset_id=dataset_id,
                split_name=split_name,
                baseline_a=baseline_a.baseline_id,
                baseline_b=baseline_b.baseline_id,
                value_a=baseline_a.value,
                value_b=baseline_b.value,
                difference_b_minus_a=baseline_b.value - baseline_a.value,
            )
        )
    return summaries


def multiple_testing_warning_for_results(results: list[MetricResult]) -> str:
    unique_metrics = {result.metric_id for result in results}
    if len(unique_metrics) <= 1:
        return ""
    return (
        f"{len(unique_metrics)} metrics were analyzed. Treat these as multiple comparisons, predeclare a primary metric, "
        "and adjust interpretation before making significance claims."
    )


def low_fpr_sample_size_warnings(result: MetricResult, metric: MetricRecord | None = None) -> list[str]:
    if not _is_low_fpr_metric(result, metric):
        return []
    if result.sample_size <= 0:
        return [f"Metric `{result.metric_id}` is low-FPR-related, but sample size is missing."]
    if result.sample_size < LOW_FPR_SAMPLE_WARNING_THRESHOLD:
        return [
            (
                f"Metric `{result.metric_id}` is low-FPR-related with sample size {result.sample_size}; "
                f"rare false-positive claims are unstable below about {LOW_FPR_SAMPLE_WARNING_THRESHOLD} trials."
            )
        ]
    return []


def exact_count_summary(result: MetricResult) -> str:
    if result.sample_size <= 0:
        return "sample size unavailable"
    if _looks_like_rate(result, None):
        event_count = round(result.value * result.sample_size)
        return f"approximately {event_count} events out of {result.sample_size}"
    return f"value {result.value:g} over sample size {result.sample_size}"


def render_analysis_report_markdown(report: StatisticalAnalysisReport) -> str:
    lines = [
        f"# Statistical Analysis Report `{report.id}`",
        "",
        f"- Workspace ID: `{report.workspace_id}`",
        f"- Executions: {', '.join(f'`{item}`' for item in report.execution_ids) if report.execution_ids else 'none'}",
        "- Interpretation: uncertainty summaries only; no significance claim is made by this report.",
        "",
        "## Metric Uncertainty",
        "",
        "| Metric result | Metric | Value | Sample size | Confidence interval | Method | Count summary |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    if report.metric_analyses:
        for analysis in report.metric_analyses:
            interval = _format_interval(analysis.confidence_interval)
            lines.append(
                "| "
                f"`{analysis.metric_result_id}` | `{analysis.metric_id}` | {analysis.value:g} | {analysis.sample_size or 'unknown'} | "
                f"{interval} | {analysis.confidence_method or 'none'} | {analysis.exact_count_summary or 'none'} |"
            )
    else:
        lines.append("| none | none |  |  |  |  |  |")
    lines.extend(["", "## Paired Differences", ""])
    if report.paired_differences:
        lines.extend(
            [
                "| Metric | Dataset | Split | Baseline A | Baseline B | Difference B-A | Warning |",
                "| --- | --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for paired in report.paired_differences:
            lines.append(
                "| "
                f"`{paired.metric_id}` | `{paired.dataset_id or 'unknown'}` | `{paired.split_name or 'unknown'}` | "
                f"`{paired.baseline_a}` ({paired.value_a:g}) | `{paired.baseline_b}` ({paired.value_b:g}) | "
                f"{paired.difference_b_minus_a:g} | {paired.warning} |"
            )
    else:
        lines.append("No paired baseline summaries were available.")
    lines.extend(["", "## Low-FPR Power Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.low_fpr_power_warnings] or ["- none"])
    lines.extend(["", "## General Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.warnings] or ["- none"])
    lines.extend(["", "## Reproducibility", ""])
    lines.append("- Analysis was derived from parsed `metrics_json` artifacts and saved as Markdown and JSON.")
    lines.append("- Missing artifacts or missing sample sizes remain visible instead of being inferred.")
    return "\n".join(lines).rstrip() + "\n"


def _format_interval(interval: list[float]) -> str:
    if len(interval) < 2:
        return "none"
    return f"[{interval[0]:.6g}, {interval[1]:.6g}]"


def _looks_like_rate(result: MetricResult, metric: MetricRecord | None) -> bool:
    if 0.0 <= result.value <= 1.0:
        return True
    text = result.metric_id.lower()
    if metric is not None:
        text += f" {metric.name.lower()} {metric.description.lower()} {metric.metric_type.lower()}"
    return any(term in text for term in ["rate", "precision", "recall", "auroc", "auprc", "specificity", "fpr"])


def _is_low_fpr_metric(result: MetricResult, metric: MetricRecord | None) -> bool:
    text = result.metric_id.lower()
    if metric is not None:
        text += f" {metric.name.lower()} {metric.description.lower()}"
    return any(term in text for term in LOW_FPR_TERMS)


def _metric_lookup(metrics: list[MetricRecord]) -> dict[str, MetricRecord]:
    lookup: dict[str, MetricRecord] = {}
    for metric in metrics:
        lookup[metric.id] = metric
        lookup[metric.name.lower()] = metric
    return lookup


def _normal_z(confidence: float) -> float:
    if math.isclose(confidence, 0.90):
        return 1.6448536269514722
    if math.isclose(confidence, 0.99):
        return 2.5758293035489004
    return 1.959963984540054


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items
