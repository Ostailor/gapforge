"""Low-FPR power and confidence planning helpers.

The functions in this module are intentionally standard-library only. They do
not make significance claims; they make rare false-positive sample-size limits
visible before a paper package or reviewer can overclaim a low-FPR result.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics.registry import MetricRegistry
from gapforge.models import ExperimentWorkspace, MetricRecord, MetricResult, Provenance, ResultSummary, to_plain
from gapforge.results.parser import ResultParser
from gapforge.state import utc_now_iso

LOW_FPR_TERMS = ("false positive", "false-positive", "false_positive", "fpr", "low-fpr", "low fpr", "specificity")
DEFAULT_TARGET_FPR = 0.001
DEFAULT_CI_WIDTH = 0.0005
DEFAULT_CONFIDENCE = 0.95


@dataclass(slots=True)
class LowFPRPlan:
    id: str
    target_fpr: float
    ci_width: float
    confidence: float
    required_negative_count: int
    zero_fp_upper_bound_examples: dict[str, float] = field(default_factory=dict)
    alpha_trial_requirements: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="low-fpr-power-planner"))


@dataclass(slots=True)
class LowFPRMetricCheck:
    metric_result_id: str
    execution_id: str
    metric_id: str
    value: float
    sample_size: int
    confidence_interval: list[float]
    required_negative_count: int
    observed_false_positives: int
    zero_fp_upper_bound: float = 0.0
    underpowered: bool = False
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LowFPRCheckResult:
    id: str
    workspace_id: str
    execution_id: str = ""
    status: str = "warning"
    plan: LowFPRPlan | None = None
    metric_checks: list[LowFPRMetricCheck] = field(default_factory=list)
    underpowered_metric_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    source_summary_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="low-fpr-power-check"))


def required_negative_sample_count(
    *,
    target_fpr: float,
    ci_width: float,
    confidence: float = DEFAULT_CONFIDENCE,
) -> int:
    """Approximate negative examples needed for a two-sided CI of width ``ci_width``.

    The approximation uses the normal/Wald planning equation around the target
    FPR and is deliberately conservative for planning. Observed results still
    use binomial intervals and explicit warning text.
    """

    _validate_probability("target_fpr", target_fpr)
    _validate_probability("ci_width", ci_width)
    if ci_width >= 1:
        raise ValueError("ci_width must be below 1.")
    half_width = ci_width / 2
    z = _normal_z(confidence)
    return math.ceil((z * z * target_fpr * (1 - target_fpr)) / (half_width * half_width))


def zero_false_positive_upper_bound(*, negative_count: int, confidence: float = DEFAULT_CONFIDENCE) -> float:
    """One-sided exact upper confidence bound when zero false positives occur."""

    if negative_count <= 0:
        raise ValueError("negative_count must be positive.")
    _validate_probability("confidence", confidence)
    return 1 - ((1 - confidence) ** (1 / negative_count))


def minimum_trials_for_alpha(alpha: float, *, confidence: float = DEFAULT_CONFIDENCE) -> int:
    """Trials needed to have ``confidence`` chance of seeing at least one alpha-rate event."""

    _validate_probability("alpha", alpha)
    _validate_probability("confidence", confidence)
    return math.ceil(math.log(1 - confidence) / math.log(1 - alpha))


def binomial_interval(successes: int, total: int, *, confidence: float = DEFAULT_CONFIDENCE) -> list[float]:
    """Return a binomial interval helper for rare-rate reporting.

    Zero-event upper bounds use the exact one-sided rule of three generalized to
    the requested confidence. Other rates use a Wilson interval to avoid adding
    a heavy scipy dependency.
    """

    if total <= 0:
        return []
    bounded_successes = min(max(successes, 0), total)
    if bounded_successes == 0:
        return [0.0, zero_false_positive_upper_bound(negative_count=total, confidence=confidence)]
    z = _normal_z(confidence)
    proportion = bounded_successes / total
    denominator = 1 + (z * z / total)
    center = (proportion + (z * z / (2 * total))) / denominator
    margin = (z / denominator) * math.sqrt((proportion * (1 - proportion) / total) + (z * z / (4 * total * total)))
    return [max(0.0, center - margin), min(1.0, center + margin)]


def plan_low_fpr(
    *,
    target_fpr: float,
    ci_width: float,
    confidence: float = DEFAULT_CONFIDENCE,
) -> LowFPRPlan:
    required = required_negative_sample_count(target_fpr=target_fpr, ci_width=ci_width, confidence=confidence)
    alpha_requirements = {f"{alpha:.0e}": minimum_trials_for_alpha(alpha, confidence=confidence) for alpha in [1e-2, 1e-3, 1e-4]}
    examples = {
        str(count): zero_false_positive_upper_bound(negative_count=count, confidence=confidence)
        for count in sorted({1_000, 3_000, 10_000, required})
        if count > 0
    }
    return LowFPRPlan(
        id=f"low-fpr-plan-{_stable_id(str(target_fpr), str(ci_width), str(confidence))}",
        target_fpr=target_fpr,
        ci_width=ci_width,
        confidence=confidence,
        required_negative_count=required,
        zero_fp_upper_bound_examples=examples,
        alpha_trial_requirements=alpha_requirements,
        notes=[
            "Use negative examples as the denominator for false-positive-rate claims.",
            "Smoke tests and tiny fixtures do not establish low-FPR empirical performance.",
            "If the observed confidence interval is wider than the planned width, soften the claim.",
        ],
        provenance=Provenance(
            created_by_skill="low-fpr-power-planner",
            timestamp=utc_now_iso(),
            reasoning_summary="Planned rare false-positive sample size requirements from target FPR and confidence interval width.",
        ),
    )


class LowFPRPowerChecker:
    """Audit parsed experiment metrics for underpowered low-FPR claims."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.parser = ResultParser(config)
        self.metric_registry = MetricRegistry(config)

    def check_execution(
        self,
        execution_id: str,
        *,
        target_fpr: float = DEFAULT_TARGET_FPR,
        ci_width: float = DEFAULT_CI_WIDTH,
        confidence: float = DEFAULT_CONFIDENCE,
    ) -> LowFPRCheckResult:
        workspace, _execution = ExperimentRunner(self.config).find_execution(execution_id)
        summary = self.parser.load_or_parse_summary(execution_id)
        result = self._check_summaries(
            workspace,
            [summary],
            execution_id=execution_id,
            target_fpr=target_fpr,
            ci_width=ci_width,
            confidence=confidence,
        )
        self._write_result(workspace, result, stem=f"low_fpr_check_{execution_id}")
        self._write_result(workspace, result, stem="low_fpr_check")
        return result

    def check_workspace(
        self,
        workspace_id: str,
        *,
        target_fpr: float = DEFAULT_TARGET_FPR,
        ci_width: float = DEFAULT_CI_WIDTH,
        confidence: float = DEFAULT_CONFIDENCE,
    ) -> LowFPRCheckResult:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        summaries: list[ResultSummary] = []
        warnings: list[str] = []
        for execution in self.workspace_manager.list_execution_records(workspace.id):
            try:
                summaries.append(self.parser.load_or_parse_summary(execution.id))
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                warnings.append(f"Could not load low-FPR inputs for execution `{execution.id}`: {exc}")
        result = self._check_summaries(
            workspace,
            summaries,
            execution_id="",
            target_fpr=target_fpr,
            ci_width=ci_width,
            confidence=confidence,
        )
        result.warnings.extend(_unique(warnings))
        if not summaries:
            result.warnings.append("No execution summaries were available for low-FPR checking.")
            result.status = "warning"
        self._write_result(workspace, result, stem="low_fpr_check")
        return result

    def _check_summaries(
        self,
        workspace: ExperimentWorkspace,
        summaries: list[ResultSummary],
        *,
        execution_id: str,
        target_fpr: float,
        ci_width: float,
        confidence: float,
    ) -> LowFPRCheckResult:
        plan = plan_low_fpr(target_fpr=target_fpr, ci_width=ci_width, confidence=confidence)
        metric_lookup = _metric_lookup(self.metric_registry.list_metrics(workspace.id))
        low_fpr_results = [
            result
            for summary in summaries
            for result in summary.metric_results
            if _is_low_fpr_metric(result, metric_lookup.get(result.metric_id))
        ]
        metric_checks = [
            _check_metric(result, metric_lookup.get(result.metric_id), plan, confidence=confidence) for result in low_fpr_results
        ]
        blockers = _unique(blocker for check in metric_checks for blocker in check.blockers)
        warnings = _unique(warning for check in metric_checks for warning in check.warnings)
        if not low_fpr_results:
            warnings.append("No low-FPR metric results were found.")
        status = "fail" if blockers else ("warning" if warnings else "pass")
        return LowFPRCheckResult(
            id=f"low-fpr-check-{_stable_id(workspace.id, execution_id, *[summary.execution_id for summary in summaries])}",
            workspace_id=workspace.id,
            execution_id=execution_id,
            status=status,
            plan=plan,
            metric_checks=metric_checks,
            underpowered_metric_ids=[check.metric_id for check in metric_checks if check.underpowered],
            warnings=warnings,
            blockers=blockers,
            source_summary_ids=[summary.execution_id for summary in summaries],
            provenance=Provenance(
                created_by_skill="low-fpr-power-check",
                source_ids=[workspace.id, *[summary.execution_id for summary in summaries]],
                timestamp=utc_now_iso(),
                reasoning_summary="Checked low-FPR metric denominators and intervals before allowing rare-event claims.",
            ),
        )

    def _write_result(self, workspace: ExperimentWorkspace, result: LowFPRCheckResult, *, stem: str) -> None:
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / f"{stem}.json").write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (reports / f"{stem}.md").write_text(render_low_fpr_check_markdown(result), encoding="utf-8")


def render_low_fpr_plan_markdown(plan: LowFPRPlan) -> str:
    lines = [
        f"# Low-FPR Plan `{plan.id}`",
        "",
        f"- Target FPR: {plan.target_fpr:g}",
        f"- Planned CI width: {plan.ci_width:g}",
        f"- Confidence: {plan.confidence:g}",
        f"- Required negative examples: {plan.required_negative_count}",
        "",
        "## Minimum Trials For Alpha Targets",
        "",
    ]
    lines.extend([f"- alpha {alpha}: {count} trials" for alpha, count in plan.alpha_trial_requirements.items()])
    lines.extend(["", "## Zero False Positive Upper Bounds", ""])
    lines.extend([f"- n={count}: upper bound {upper:.6g}" for count, upper in plan.zero_fp_upper_bound_examples.items()])
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {note}" for note in plan.notes])
    return "\n".join(lines).rstrip() + "\n"


def render_low_fpr_check_markdown(result: LowFPRCheckResult) -> str:
    plan = result.plan
    lines = [
        f"# Low-FPR Power Check `{result.id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Workspace ID: `{result.workspace_id}`",
        f"- Execution ID: `{result.execution_id or 'workspace'}`",
    ]
    if plan is not None:
        lines.extend(
            [
                f"- Target FPR: {plan.target_fpr:g}",
                f"- Planned CI width: {plan.ci_width:g}",
                f"- Required negative examples: {plan.required_negative_count}",
            ]
        )
    lines.extend(
        [
            "",
            "## Metric Checks",
            "",
            "| Metric result | Metric | Value | Negative examples | Required | Observed FP | Zero-FP upper bound | Status |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    if result.metric_checks:
        for check in result.metric_checks:
            status = "underpowered" if check.underpowered else "ok"
            lines.append(
                "| "
                f"`{check.metric_result_id}` | `{check.metric_id}` | {check.value:g} | {check.sample_size} | "
                f"{check.required_negative_count} | {check.observed_false_positives} | {check.zero_fp_upper_bound:.6g} | {status} |"
            )
    else:
        lines.append("| none | none |  |  |  |  |  | no low-FPR metrics |")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(["", "## Interpretation", ""])
    lines.append("- Underpowered low-FPR findings must be softened or rerun with enough negative examples before paper-ready claims.")
    return "\n".join(lines).rstrip() + "\n"


def _check_metric(
    result: MetricResult,
    metric: MetricRecord | None,
    plan: LowFPRPlan,
    *,
    confidence: float,
) -> LowFPRMetricCheck:
    warnings: list[str] = []
    blockers: list[str] = []
    observed_fp = max(0, round(result.value * result.sample_size)) if result.sample_size > 0 else 0
    zero_upper = (
        zero_false_positive_upper_bound(negative_count=result.sample_size, confidence=confidence) if result.sample_size > 0 else 0.0
    )
    if result.sample_size <= 0:
        blockers.append(f"Metric `{result.metric_id}` is low-FPR-related, but the negative sample count is missing.")
    elif result.sample_size < plan.required_negative_count:
        blockers.append(
            f"Metric `{result.metric_id}` is underpowered for FPR {plan.target_fpr:g}: "
            f"{result.sample_size} negative examples observed, {plan.required_negative_count} required for CI width {plan.ci_width:g}."
        )
    interval_width = _interval_width(result.confidence_interval)
    if not result.confidence_interval:
        warnings.append(f"Metric `{result.metric_id}` is low-FPR-related but lacks a confidence interval.")
    elif interval_width > plan.ci_width:
        warnings.append(
            f"Metric `{result.metric_id}` has CI width {interval_width:g}, wider than planned {plan.ci_width:g}; soften low-FPR claims."
        )
    if result.sample_size > 0 and observed_fp == 0:
        warnings.append(f"Metric `{result.metric_id}` observed zero false positives; one-sided upper bound is {zero_upper:.6g}, not zero.")
    if result.value <= plan.target_fpr and blockers:
        warnings.append(
            f"Metric `{result.metric_id}` appears to claim operation at or below target FPR {plan.target_fpr:g}, "
            "but denominator is insufficient."
        )
    if metric is not None and "smoke" in metric.description.lower():
        warnings.append(f"Metric `{result.metric_id}` appears fixture/smoke-related; do not treat it as real low-FPR evidence.")
    return LowFPRMetricCheck(
        metric_result_id=result.id,
        execution_id=result.execution_id,
        metric_id=result.metric_id,
        value=result.value,
        sample_size=result.sample_size,
        confidence_interval=list(result.confidence_interval),
        required_negative_count=plan.required_negative_count,
        observed_false_positives=observed_fp,
        zero_fp_upper_bound=zero_upper,
        underpowered=bool(blockers),
        warnings=_unique(warnings),
        blockers=_unique(blockers),
    )


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


def _interval_width(interval: list[float]) -> float:
    if len(interval) < 2:
        return 0.0
    return max(interval) - min(interval)


def _normal_z(confidence: float) -> float:
    _validate_probability("confidence", confidence)
    if math.isclose(confidence, 0.90):
        return 1.6448536269514722
    if math.isclose(confidence, 0.99):
        return 2.5758293035489004
    return 1.959963984540054


def _validate_probability(name: str, value: float) -> None:
    if not 0 < value < 1:
        raise ValueError(f"{name} must be between 0 and 1.")


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _unique(items) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items
