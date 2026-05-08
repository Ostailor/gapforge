"""Sequential specificity and low-FPR metrics for selected benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.power import (
    exact_binomial_confidence_interval,
    required_negative_count_for_zero_fp_bound,
    underpowered_low_fpr_warnings,
    zero_false_positive_upper_bound,
)
from gapforge.selected_benchmark.sequential import SequentialAuditSummary, summarize_sequential_audit
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.trace_generator import SyntheticTraceGenerator, TraceDataset
from gapforge.state import slugify, utc_now_iso

DEFAULT_ALPHA_LEVELS = [0.1, 0.05, 0.01, 0.001]


@dataclass(slots=True)
class SequentialMetricResult:
    id: str
    execution_id: str
    metric_name: str
    value: float
    confidence_interval: list[float] = field(default_factory=list)
    alpha: float = 0.05
    sample_size: int = 0
    negative_trace_count: int = 0
    positive_trace_count: int = 0
    run_type: str = "smoke"
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-sequential-metrics"))


@dataclass(slots=True)
class SequentialAuditMetricPlan:
    id: str
    benchmark_id: str
    target_alpha_levels: list[float] = field(default_factory=list)
    required_negative_counts: dict[str, int] = field(default_factory=dict)
    stopping_rule: str = ""
    multiple_testing_notes: list[str] = field(default_factory=list)
    power_notes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-sequential-metrics"))


class SequentialMetricManager:
    """Plan, compute, and report selected benchmark sequential audit metrics."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)

    def create_plan(self, benchmark_id: str) -> SequentialAuditMetricPlan:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        levels = [float(item) for item in (spec.target_fpr_levels or DEFAULT_ALPHA_LEVELS)]
        if 0.001 not in levels:
            levels.append(0.001)
        levels = sorted(set(levels), reverse=True)
        plan = SequentialAuditMetricPlan(
            id=f"sequential-metric-plan-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            target_alpha_levels=levels,
            required_negative_counts={f"{level:g}": required_negative_count_for_zero_fp_bound(level) for level in levels},
            stopping_rule=(
                "Evaluate all predeclared trace windows; do not stop after early favorable low-FPR observations. "
                "Any sequential early-stop rule must be declared before pilot/main runs."
            ),
            multiple_testing_notes=[
                "Per-step, per-episode, family-wise, delay, calibration, and abstention metrics are multiple comparisons.",
                "Predeclare the primary low-FPR specificity metric before pilot/main claims.",
                "Repeated audit windows require family-wise false-alarm reporting, not only per-step FPR.",
            ],
            power_notes=[
                "Low-FPR claims require enough honest negative traces for the target alpha level.",
                "Rates use exact/binomial confidence intervals; zero false positives still require an exact upper confidence bound.",
                "Smoke runs validate metric wiring only and cannot support strong low-FPR claims.",
            ],
            provenance=Provenance(
                created_by_skill="selected-benchmark-sequential-metrics",
                source_ids=[benchmark_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Planned statistically cautious sequential specificity metrics for selected benchmark evaluation.",
            ),
        )
        path = self._benchmark_dir(spec.project_id) / "metric_plan.json"
        self._write_json(path, plan)
        (path.with_suffix(".md")).write_text(render_metric_plan(plan), encoding="utf-8")
        return plan

    def compute(self, execution_id: str) -> list[SequentialMetricResult]:
        dataset = self.trace_generator.load_dataset(execution_id)
        traces = self.trace_generator.load_traces_for_dataset(execution_id)
        summary = summarize_sequential_audit(execution_id, traces, run_type=dataset.split)
        results = compute_sequential_metric_results(dataset, summary)
        dataset_dir = self._dataset_dir(dataset.id)
        self._write_json(dataset_dir / "sequential_metrics.json", results)
        (dataset_dir / "sequential_metrics.md").write_text(render_sequential_metric_report(dataset, results), encoding="utf-8")
        return results

    def load_results(self, execution_id: str) -> list[SequentialMetricResult]:
        path = self._dataset_dir(execution_id) / "sequential_metrics.json"
        if not path.exists():
            return self.compute(execution_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(SequentialMetricResult, item) for item in raw]

    def render_low_fpr_audit_check(self, execution_id: str) -> str:
        dataset = self.trace_generator.load_dataset(execution_id)
        results = self.load_results(execution_id)
        report = render_low_fpr_audit_check(dataset, results)
        (self._dataset_dir(execution_id) / "low_fpr_audit_check.md").write_text(report, encoding="utf-8")
        return report

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dataset_dir(self, dataset_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._benchmark_dir(project.id) / "trace_datasets" / dataset_id
            if path.exists():
                return path
        raise FileNotFoundError(f"No selected benchmark trace dataset `{dataset_id}` found.")

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def compute_sequential_metric_results(dataset: TraceDataset, summary: SequentialAuditSummary) -> list[SequentialMetricResult]:
    limitations = _shared_limitations(dataset, summary)
    per_step_fpr = _rate(summary.false_positive_steps, summary.negative_step_count)
    per_episode_fpr = _rate(summary.false_alarm_episodes, summary.negative_trace_count)
    tpr = _rate(summary.detected_positive_traces, summary.positive_trace_count)
    abstention_rate = _rate(summary.ambiguous_trace_count, len(summary.trace_summaries))
    mean_detection_step = _mean(summary.detection_steps)
    mean_delay = _mean(summary.detection_delays)
    primary_alpha = 0.05
    zero_fp_bound = zero_false_positive_upper_bound(summary.negative_trace_count, alpha=primary_alpha)
    results = [
        _metric(
            dataset,
            summary,
            "per_step_false_positive_rate",
            per_step_fpr,
            sample_size=summary.negative_step_count,
            successes=summary.false_positive_steps,
            limitations=limitations,
        ),
        _metric(
            dataset,
            summary,
            "per_episode_false_positive_rate",
            per_episode_fpr,
            sample_size=summary.negative_trace_count,
            successes=summary.false_alarm_episodes,
            limitations=limitations,
        ),
        _metric(
            dataset,
            summary,
            "family_wise_false_alarm_probability",
            per_episode_fpr,
            sample_size=summary.negative_trace_count,
            successes=summary.false_alarm_episodes,
            limitations=[
                *limitations,
                "Sequential repeated decisions require family-wise false-alarm interpretation across audit windows.",
            ],
        ),
        _metric(
            dataset,
            summary,
            "time_to_detection",
            mean_detection_step,
            sample_size=len(summary.detection_steps),
            successes=0,
            confidence_interval=[],
            limitations=limitations,
        ),
        _metric(
            dataset,
            summary,
            "detection_delay",
            mean_delay,
            sample_size=len(summary.detection_delays),
            successes=0,
            confidence_interval=[],
            limitations=limitations,
        ),
        _metric(
            dataset,
            summary,
            "true_positive_rate_at_fixed_false_positive_budget",
            tpr,
            sample_size=summary.positive_trace_count,
            successes=summary.detected_positive_traces,
            limitations=[
                *limitations,
                f"TPR at alpha={primary_alpha:g} is descriptive unless the false-positive upper bound is within budget.",
            ],
        ),
        _metric(
            dataset,
            summary,
            "specificity_at_alpha",
            1 - per_episode_fpr,
            sample_size=summary.negative_trace_count,
            successes=summary.negative_trace_count - summary.false_alarm_episodes,
            limitations=limitations,
        ),
        _metric(
            dataset,
            summary,
            "sequential_calibration_error",
            abs(per_episode_fpr - primary_alpha),
            sample_size=summary.negative_trace_count,
            successes=0,
            confidence_interval=[],
            limitations=[
                *limitations,
                "Calibration error is computed against the target alpha budget, not a learned probability calibration curve.",
            ],
        ),
        _metric(
            dataset,
            summary,
            "abstention_uncertain_rate",
            abstention_rate,
            sample_size=len(summary.trace_summaries),
            successes=summary.ambiguous_trace_count,
            limitations=[
                *limitations,
                "Ambiguous traces are reported separately and excluded from main low-FPR metrics by default.",
            ],
        ),
        _metric(
            dataset,
            summary,
            "zero_false_positive_upper_bound",
            zero_fp_bound
            if summary.false_alarm_episodes == 0
            else exact_binomial_confidence_interval(summary.false_alarm_episodes, summary.negative_trace_count, alpha=primary_alpha)[-1],
            sample_size=summary.negative_trace_count,
            successes=summary.false_alarm_episodes,
            confidence_interval=[],
            limitations=[
                *limitations,
                "Zero false positives do not imply zero risk; use this upper bound for cautious low-FPR interpretation.",
            ],
        ),
    ]
    return results


def render_metric_plan(plan: SequentialAuditMetricPlan) -> str:
    lines = [
        f"# Sequential Metric Plan `{plan.id}`",
        "",
        f"- Benchmark ID: `{plan.benchmark_id}`",
        f"- Target alpha levels: {', '.join(str(item) for item in plan.target_alpha_levels)}",
        "",
        "## Required Negative Counts",
        "",
    ]
    lines.extend([f"- alpha={alpha}: {count}" for alpha, count in plan.required_negative_counts.items()])
    lines.extend(["", "## Stopping Rule", "", plan.stopping_rule, "", "## Multiple Testing Notes", ""])
    lines.extend([f"- {item}" for item in plan.multiple_testing_notes])
    lines.extend(["", "## Power Notes", ""])
    lines.extend([f"- {item}" for item in plan.power_notes])
    return "\n".join(lines).rstrip() + "\n"


def render_sequential_metric_report(dataset: TraceDataset, results: list[SequentialMetricResult]) -> str:
    lines = [
        f"# Sequential Metric Report `{dataset.id}`",
        "",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        f"- Run type: `{dataset.split}`",
        "",
        "## Metrics",
        "",
    ]
    for result in results:
        interval = _format_interval(result.confidence_interval)
        lines.append(
            f"- `{result.metric_name}`: {result.value:.6g}; sample size {result.sample_size}; alpha {result.alpha:g}; CI {interval}"
        )
    lines.extend(["", "## Caution", ""])
    lines.extend([f"- {item}" for item in _unique(item for result in results for item in result.limitations)] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_low_fpr_audit_check(dataset: TraceDataset, results: list[SequentialMetricResult]) -> str:
    warnings = _unique(item for result in results for item in result.limitations if "underpowered" in item or "multiple" in item.lower())
    upper_bound = next((item.value for item in results if item.metric_name == "zero_false_positive_upper_bound"), 1.0)
    episode_fpr = next((item.value for item in results if item.metric_name == "per_episode_false_positive_rate"), 1.0)
    status = "underpowered" if warnings or dataset.split == "smoke" else "pass"
    lines = [
        f"# Low-FPR Audit Check `{dataset.id}`",
        "",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        f"- Run type: `{dataset.split}`",
        f"- Status: `{status}`",
        f"- Per-episode FPR: {episode_fpr:.6g}",
        f"- Zero-FP upper bound: {upper_bound:.6g}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {item}" for item in warnings] or ["- none"])
    lines.extend(["", "## Non-Claims", ""])
    lines.extend(
        [
            "- Smoke results cannot support strong low-FPR claims.",
            "- Synthetic traces do not represent real deployment behavior.",
            "- Sequential multiple-testing warnings must be resolved before pilot/main claims.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _metric(
    dataset: TraceDataset,
    summary: SequentialAuditSummary,
    metric_name: str,
    value: float,
    *,
    sample_size: int,
    successes: int,
    limitations: list[str],
    confidence_interval: list[float] | None = None,
    alpha: float = 0.05,
) -> SequentialMetricResult:
    interval = confidence_interval
    if interval is None:
        interval = exact_binomial_confidence_interval(successes, sample_size, alpha=alpha)
    return SequentialMetricResult(
        id=f"sequential-metric-{slugify(metric_name)}-{slugify(dataset.id)}",
        execution_id=dataset.id,
        metric_name=metric_name,
        value=value,
        confidence_interval=interval,
        alpha=alpha,
        sample_size=sample_size,
        negative_trace_count=summary.negative_trace_count,
        positive_trace_count=summary.positive_trace_count,
        run_type=dataset.split,
        limitations=limitations,
        provenance=Provenance(
            created_by_skill="selected-benchmark-sequential-metrics",
            source_ids=[dataset.id, dataset.benchmark_id],
            timestamp=utc_now_iso(),
            reasoning_summary=f"Computed selected benchmark sequential metric `{metric_name}` with cautious low-FPR interpretation.",
        ),
    )


def _shared_limitations(dataset: TraceDataset, summary: SequentialAuditSummary) -> list[str]:
    warnings = [
        "Sequential multiple-testing warning: repeated audit windows require family-wise false-alarm interpretation.",
        *underpowered_low_fpr_warnings(
            run_type=dataset.split,
            negative_trace_count=summary.negative_trace_count,
            target_alpha_levels=DEFAULT_ALPHA_LEVELS,
        ),
    ]
    return _unique([*dataset.limitations, *warnings])


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _format_interval(interval: list[float]) -> str:
    if len(interval) != 2:
        return "not applicable"
    return f"[{interval[0]:.6g}, {interval[1]:.6g}]"


def _unique(items) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
