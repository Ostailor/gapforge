"""Main-scale trace dataset builder for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.collusive_alternatives import CollusiveAlternativeManager
from gapforge.selected_benchmark.honest_null import HonestNullManager
from gapforge.selected_benchmark.labels import COLLUSIVE_LABEL, HARD_NEGATIVE_LABEL, HONEST_LABEL
from gapforge.selected_benchmark.main_power import MainPowerManager, MainPowerPlan
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.trace_generator import AgentTrace, SyntheticTraceGenerator
from gapforge.state import slugify, utc_now_iso

MAX_SYNTHETIC_MAIN_TRACES = 10_000


@dataclass(slots=True)
class MainTraceDataset:
    id: str
    benchmark_id: str
    negative_count: int
    positive_count: int
    hard_negative_count: int
    observability_mode_counts: dict[str, int] = field(default_factory=dict)
    scenario_coverage: dict[str, int] = field(default_factory=dict)
    alpha_targets_supported: dict[str, dict[str, Any]] = field(default_factory=dict)
    generation_plan_id: str = ""
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-dataset"))


class MainDatasetBuilder:
    """Build or feasibility-gate the v2.3 selected benchmark main trace dataset."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.honest_manager = HonestNullManager(config)
        self.collusive_manager = CollusiveAlternativeManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)
        self.power_manager = MainPowerManager(config)

    def build(
        self,
        benchmark_id: str,
        *,
        negative_count: int | None = None,
        positive_count: int | None = None,
    ) -> MainTraceDataset:
        plan = self._aligned_plan(benchmark_id, negative_count=negative_count, positive_count=positive_count)
        requested_negative = plan.planned_negative_count
        requested_positive = plan.planned_positive_count
        if requested_negative <= 0:
            raise ValueError("negative_count must be positive.")
        if requested_positive <= 0:
            raise ValueError("positive_count must be positive.")
        if requested_negative + requested_positive > MAX_SYNTHETIC_MAIN_TRACES:
            return self._write_feasibility_dataset(plan, requested_negative=requested_negative, requested_positive=requested_positive)
        return self._generate_dataset(plan, negative_count=requested_negative, positive_count=requested_positive)

    def load(self, dataset_id: str) -> MainTraceDataset:
        for project in self.project_manager.list_projects():
            path = self._main_dataset_dir(project.id) / f"{dataset_id}.json"
            if path.exists():
                return from_dict(MainTraceDataset, json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No main trace dataset `{dataset_id}` found.")

    def render_report(self, dataset_id: str) -> str:
        dataset = self.load(dataset_id)
        report = render_main_trace_dataset_report(dataset)
        spec = self.benchmark_manager.load_spec(dataset.benchmark_id)
        (self._main_dataset_dir(spec.project_id) / f"{dataset.id}.md").write_text(report, encoding="utf-8")
        trace_report = self._trace_dataset_dir(spec.project_id, dataset.id) / "report.md"
        if trace_report.parent.exists():
            trace_report.write_text(report, encoding="utf-8")
        return report

    def _aligned_plan(
        self,
        benchmark_id: str,
        *,
        negative_count: int | None,
        positive_count: int | None,
    ) -> MainPowerPlan:
        if negative_count is not None or positive_count is not None:
            existing = self.power_manager.load_plan(benchmark_id)
            return self.power_manager.create_plan(
                benchmark_id,
                planned_negative_count=negative_count if negative_count is not None else existing.planned_negative_count,
                planned_positive_count=positive_count if positive_count is not None else existing.planned_positive_count,
            )
        return self.power_manager.load_plan(benchmark_id)

    def _generate_dataset(self, plan: MainPowerPlan, *, negative_count: int, positive_count: int) -> MainTraceDataset:
        spec = self.benchmark_manager.load_spec(plan.benchmark_id)
        honest_source = self.honest_manager.generate(plan.benchmark_id, count=negative_count)
        collusive_source = self.collusive_manager.generate(plan.benchmark_id, count=positive_count)
        honest_traces = [
            trace for trace in self.trace_generator.load_traces_for_dataset(honest_source.id) if trace.trace_type == HONEST_LABEL
        ]
        collusive_traces = [
            trace for trace in self.trace_generator.load_traces_for_dataset(collusive_source.id) if trace.trace_type == COLLUSIVE_LABEL
        ]
        traces = honest_traces + collusive_traces
        dataset = MainTraceDataset(
            id=f"main-trace-dataset-{slugify(plan.benchmark_id)}",
            benchmark_id=plan.benchmark_id,
            negative_count=len(honest_traces),
            positive_count=len(collusive_traces),
            hard_negative_count=sum(1 for trace in honest_traces if HARD_NEGATIVE_LABEL in trace.labels),
            observability_mode_counts=_mode_counts(traces),
            scenario_coverage=_scenario_counts(traces),
            alpha_targets_supported=self._alpha_support(plan, negative_count=len(honest_traces), feasibility_only=False),
            generation_plan_id=plan.id,
            limitations=self._limitations(plan, negative_count=len(honest_traces), positive_count=len(collusive_traces), generated=True),
            provenance=Provenance(
                created_by_skill="selected-main-dataset",
                source_ids=[plan.benchmark_id, spec.project_id, plan.id, honest_source.id, collusive_source.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Built a v2.3 synthetic main trace dataset aligned with the main power plan.",
            ),
        )
        dataset_dir = self._trace_dataset_dir(spec.project_id, dataset.id)
        self._write_json(dataset_dir / "traces.json", traces)
        self._write_json(dataset_dir / "dataset.json", dataset)
        self._write_dataset_outputs(spec.project_id, dataset)
        return dataset

    def _write_feasibility_dataset(
        self,
        plan: MainPowerPlan,
        *,
        requested_negative: int,
        requested_positive: int,
    ) -> MainTraceDataset:
        spec = self.benchmark_manager.load_spec(plan.benchmark_id)
        dataset = MainTraceDataset(
            id=f"main-trace-dataset-feasibility-{slugify(plan.benchmark_id)}",
            benchmark_id=plan.benchmark_id,
            negative_count=requested_negative,
            positive_count=requested_positive,
            hard_negative_count=0,
            observability_mode_counts={},
            scenario_coverage={},
            alpha_targets_supported=self._alpha_support(plan, negative_count=requested_negative, feasibility_only=True),
            generation_plan_id=plan.id,
            limitations=self._limitations(plan, negative_count=requested_negative, positive_count=requested_positive, generated=False),
            provenance=Provenance(
                created_by_skill="selected-main-dataset",
                source_ids=[plan.benchmark_id, spec.project_id, plan.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Recorded a v2.3 main dataset feasibility decision because requested synthetic generation is too expensive."
                ),
            ),
        )
        self._write_dataset_outputs(spec.project_id, dataset)
        return dataset

    def _alpha_support(self, plan: MainPowerPlan, *, negative_count: int, feasibility_only: bool) -> dict[str, dict[str, Any]]:
        support: dict[str, dict[str, Any]] = {}
        for alpha in plan.target_alpha_levels:
            key = f"{alpha:g}"
            required = plan.required_negative_counts[key]
            if negative_count >= required:
                status = "feasibility_only" if feasibility_only else "supported"
            else:
                status = "underpowered"
            support[key] = {
                "status": status,
                "target_alpha": alpha,
                "observed_negative_count": negative_count,
                "required_negative_count": required,
            }
        return support

    def _limitations(self, plan: MainPowerPlan, *, negative_count: int, positive_count: int, generated: bool) -> list[str]:
        limitations = [
            "Synthetic main dataset: traces are generated benchmark artifacts, not deployment data.",
            "Synthetic-only evidence cannot establish deployment validity.",
            "Scenario diversity must be interpreted through the reported scenario coverage, not assumed from trace count alone.",
            f"Dataset counts are aligned with main power plan `{plan.id}`.",
        ]
        if not generated:
            limitations.append(
                f"Requested main dataset is too expensive for automatic generation: "
                f"{negative_count + positive_count} requested traces exceeds limit {MAX_SYNTHETIC_MAIN_TRACES}."
            )
            limitations.append("Feasibility report generated instead of pretending that main traces were built.")
        if negative_count < plan.required_negative_counts["0.001"]:
            limitations.append(
                f"alpha=0.001 is underpowered: {negative_count} negative traces observed/planned, "
                f"{plan.required_negative_counts['0.001']} required."
            )
        if positive_count < plan.required_positive_counts["0.001"]:
            limitations.append(
                f"Positive trace count is below alpha=0.001 context target: {positive_count} observed/planned, "
                f"{plan.required_positive_counts['0.001']} recommended."
            )
        return limitations

    def _write_dataset_outputs(self, project_id: str, dataset: MainTraceDataset) -> None:
        report = render_main_trace_dataset_report(dataset)
        self._write_json(self._main_dataset_dir(project_id) / f"{dataset.id}.json", dataset)
        (self._main_dataset_dir(project_id) / f"{dataset.id}.md").write_text(report, encoding="utf-8")
        dataset_dir = self._trace_dataset_dir(project_id, dataset.id)
        self._write_json(dataset_dir / "dataset.json", dataset)
        (dataset_dir / "report.md").write_text(report, encoding="utf-8")

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _main_dataset_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "main_dataset"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _trace_dataset_dir(self, project_id: str, dataset_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "trace_datasets" / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_main_trace_dataset_report(dataset: MainTraceDataset) -> str:
    title = (
        "Main Trace Dataset Feasibility Report" if dataset.id.startswith("main-trace-dataset-feasibility-") else "Main Trace Dataset Report"
    )
    lines = [
        f"# {title}",
        "",
        f"- Dataset ID: `{dataset.id}`",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        f"- Generation plan ID: `{dataset.generation_plan_id}`",
        f"- Negative traces: {dataset.negative_count}",
        f"- Positive traces: {dataset.positive_count}",
        f"- Hard-negative traces: {dataset.hard_negative_count}",
        "",
        "## Alpha Target Support",
        "",
    ]
    for alpha, payload in sorted(dataset.alpha_targets_supported.items(), key=lambda item: float(item[0])):
        lines.append(
            f"- alpha={alpha}: {payload['status']} "
            f"({payload['observed_negative_count']} observed/planned / {payload['required_negative_count']} required)"
        )
    lines.extend(["", "## Observability Modes", ""])
    lines.extend([f"- {mode}: {count}" for mode, count in sorted(dataset.observability_mode_counts.items())] or ["- none"])
    lines.extend(["", "## Scenario Coverage", ""])
    lines.extend([f"- `{scenario_id}`: {count}" for scenario_id, count in sorted(dataset.scenario_coverage.items())] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in dataset.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _mode_counts(traces: list[AgentTrace]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trace in traces:
        counts[trace.observability_mode] = counts.get(trace.observability_mode, 0) + 1
    return counts


def _scenario_counts(traces: list[AgentTrace]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trace in traces:
        counts[trace.scenario_id] = counts.get(trace.scenario_id, 0) + 1
    return counts
