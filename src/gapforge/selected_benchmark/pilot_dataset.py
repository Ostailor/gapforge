"""Pilot trace dataset builder for the selected benchmark."""

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
from gapforge.selected_benchmark.pilot_power import PilotPowerManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.trace_generator import AgentTrace, SyntheticTraceGenerator
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class PilotTraceDataset:
    id: str
    benchmark_id: str
    honest_trace_ids: list[str] = field(default_factory=list)
    collusive_trace_ids: list[str] = field(default_factory=list)
    ambiguous_trace_ids: list[str] = field(default_factory=list)
    split: str = "pilot"
    negative_count: int = 0
    positive_count: int = 0
    hard_negative_count: int = 0
    observability_mode_counts: dict[str, int] = field(default_factory=dict)
    scenario_coverage: dict[str, int] = field(default_factory=dict)
    alpha_targets_supported: dict[str, dict[str, Any]] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-pilot-dataset"))


class PilotDatasetBuilder:
    """Build a combined v2.2 pilot trace dataset from honest negatives and collusive positives."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.honest_manager = HonestNullManager(config)
        self.collusive_manager = CollusiveAlternativeManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)

    def build(self, benchmark_id: str, *, negative_count: int = 300, positive_count: int = 150) -> PilotTraceDataset:
        if negative_count <= 0:
            raise ValueError("negative_count must be positive.")
        if positive_count <= 0:
            raise ValueError("positive_count must be positive.")
        spec = self.benchmark_manager.load_spec(benchmark_id)
        honest_source = self.honest_manager.generate(benchmark_id, count=negative_count)
        collusive_source = self.collusive_manager.generate(benchmark_id, count=positive_count)
        honest_traces = self.trace_generator.load_traces_for_dataset(honest_source.id)
        collusive_traces = self.trace_generator.load_traces_for_dataset(collusive_source.id)
        primary_honest = [trace for trace in honest_traces if trace.trace_type == HONEST_LABEL]
        primary_collusive = [trace for trace in collusive_traces if trace.trace_type == COLLUSIVE_LABEL]
        ambiguous_traces: list[AgentTrace] = []
        traces = primary_honest + primary_collusive
        now = utc_now_iso()
        dataset_id = f"pilot-trace-dataset-{slugify(benchmark_id)}"
        alpha_support = self._alpha_support(benchmark_id, negative_count=len(primary_honest))
        limitations = self._limitations(
            alpha_support=alpha_support,
            negative_count=len(primary_honest),
            positive_count=len(primary_collusive),
            ambiguous_count=len(ambiguous_traces),
        )
        dataset = PilotTraceDataset(
            id=dataset_id,
            benchmark_id=benchmark_id,
            honest_trace_ids=[trace.id for trace in primary_honest],
            collusive_trace_ids=[trace.id for trace in primary_collusive],
            ambiguous_trace_ids=[trace.id for trace in ambiguous_traces],
            split="pilot",
            negative_count=len(primary_honest),
            positive_count=len(primary_collusive),
            hard_negative_count=sum(1 for trace in primary_honest if HARD_NEGATIVE_LABEL in trace.labels),
            observability_mode_counts=_mode_counts(traces),
            scenario_coverage=_scenario_counts(traces),
            alpha_targets_supported=alpha_support,
            limitations=limitations,
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-dataset",
                source_ids=[benchmark_id, spec.project_id, honest_source.id, collusive_source.id],
                timestamp=now,
                reasoning_summary=("Built a v2.2 pilot trace dataset from synthetic honest-null negatives and collusive alternatives."),
            ),
        )
        dataset_dir = self._dataset_dir(spec.project_id, dataset.id)
        self._write_json(dataset_dir / "dataset.json", dataset)
        self._write_json(dataset_dir / "traces.json", traces)
        self._write_json(self._pilot_dir(spec.project_id) / f"{dataset.id}.json", dataset)
        report = render_pilot_trace_dataset_report(dataset)
        (dataset_dir / "report.md").write_text(report, encoding="utf-8")
        (self._pilot_dir(spec.project_id) / f"{dataset.id}.md").write_text(report, encoding="utf-8")
        (self._pilot_dir(spec.project_id) / "dataset_card.md").write_text(render_pilot_dataset_card(dataset), encoding="utf-8")
        return dataset

    def load(self, dataset_id: str) -> PilotTraceDataset:
        for project in self.project_manager.list_projects():
            path = self._pilot_dir(project.id) / f"{dataset_id}.json"
            if path.exists():
                return from_dict(PilotTraceDataset, json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No pilot trace dataset `{dataset_id}` found.")

    def report(self, dataset_id: str) -> PilotTraceDataset:
        dataset = self.load(dataset_id)
        spec = self.benchmark_manager.load_spec(dataset.benchmark_id)
        report = render_pilot_trace_dataset_report(dataset)
        (self._pilot_dir(spec.project_id) / f"{dataset.id}.md").write_text(report, encoding="utf-8")
        (self._dataset_dir(spec.project_id, dataset.id) / "report.md").write_text(report, encoding="utf-8")
        return dataset

    def _alpha_support(self, benchmark_id: str, *, negative_count: int) -> dict[str, dict[str, Any]]:
        plan = PilotPowerManager(self.config).load_plan(benchmark_id)
        support: dict[str, dict[str, Any]] = {}
        for target in plan.target_alpha_levels:
            key = f"{target:g}"
            required = plan.negative_trace_requirements[key]
            status = "supported" if negative_count >= required else "underpowered"
            support[key] = {
                "status": status,
                "target_alpha": target,
                "observed_negative_count": negative_count,
                "required_negative_count": required,
            }
        return support

    def _limitations(
        self,
        *,
        alpha_support: dict[str, dict[str, Any]],
        negative_count: int,
        positive_count: int,
        ambiguous_count: int,
    ) -> list[str]:
        limitations = [
            "Synthetic pilot dataset: traces are generated benchmark artifacts, not deployment data.",
            "Ambiguous traces are excluded from primary metrics unless explicitly enabled in a future manifest.",
            "Dataset provenance links the pilot dataset to generated honest-null and collusive alternative sources.",
        ]
        if alpha_support.get("0.01", {}).get("status") != "supported":
            limitations.append(f"Negative trace count {negative_count} blocks pilot alpha=0.01 specificity claims.")
        if alpha_support.get("0.001", {}).get("status") != "supported":
            limitations.append("alpha=0.001 remains main-scale unless enough negative traces exist.")
        if positive_count < 100:
            limitations.append(f"Positive trace count is below pilot recommendation: {positive_count} observed, 100 recommended.")
        if ambiguous_count == 0:
            limitations.append("Ambiguous traces are excluded from primary metrics by default.")
        return limitations

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _pilot_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "pilot_dataset"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _trace_root(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "trace_datasets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dataset_dir(self, project_id: str, dataset_id: str) -> Path:
        path = self._trace_root(project_id) / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_pilot_trace_dataset_report(dataset: PilotTraceDataset) -> str:
    lines = [
        "# Pilot Trace Dataset Report",
        "",
        f"- Dataset ID: `{dataset.id}`",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        f"- Split: `{dataset.split}`",
        f"- Negative traces: {dataset.negative_count}",
        f"- Positive traces: {dataset.positive_count}",
        f"- Hard-negative traces: {dataset.hard_negative_count}",
        f"- Ambiguous traces excluded from primary metrics: {len(dataset.ambiguous_trace_ids)}",
        "",
        "## Alpha Target Support",
        "",
    ]
    for alpha, payload in sorted(dataset.alpha_targets_supported.items()):
        lines.append(
            f"- alpha={alpha}: {payload['status']} "
            f"({payload['observed_negative_count']} observed / {payload['required_negative_count']} required)"
        )
    lines.extend(["", "## Observability Modes", ""])
    lines.extend([f"- {mode}: {count}" for mode, count in sorted(dataset.observability_mode_counts.items())] or ["- none"])
    lines.extend(["", "## Scenario Coverage", ""])
    lines.extend([f"- `{scenario_id}`: {count}" for scenario_id, count in sorted(dataset.scenario_coverage.items())] or ["- none"])
    lines.extend(["", "## Synthetic/pilot status", ""])
    lines.extend([f"- {item}" for item in dataset.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_pilot_dataset_card(dataset: PilotTraceDataset) -> str:
    lines = [
        "# Dataset Card: v2.2 Pilot Trace Dataset",
        "",
        f"- Dataset ID: `{dataset.id}`",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        "- Type: `synthetic`",
        f"- Split: `{dataset.split}`",
        "",
        "## Composition",
        "",
        f"- Honest negative traces: {dataset.negative_count}",
        f"- Collusive positive traces: {dataset.positive_count}",
        f"- Hard-negative traces: {dataset.hard_negative_count}",
        f"- Ambiguous traces excluded from primary metrics: {len(dataset.ambiguous_trace_ids)}",
        "",
        "## Intended Use",
        "",
        "Pilot-scale specificity and detection-delay analysis for the selected benchmark.",
        "",
        "## Limitations",
        "",
    ]
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
