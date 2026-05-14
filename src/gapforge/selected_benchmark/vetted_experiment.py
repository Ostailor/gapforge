"""Experiment path for selected benchmarks using vetted benchmark adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.vetted_mapping import (
    SelectedBenchmarkVettedMapping,
    SelectedBenchmarkVettedMappingManager,
    VettedBenchmarkMappingReport,
)
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks import BenchmarkAdapter, BenchmarkAdapterRegistry, BenchmarkAdapterRun


@dataclass(slots=True)
class VettedBenchmarkExperimentPlan:
    id: str
    selected_benchmark_id: str
    adapter_ids: list[str] = field(default_factory=list)
    monitor_ids: list[str] = field(default_factory=list)
    metric_ids: list[str] = field(default_factory=list)
    run_type: str = "vetted_adapter"
    expected_outputs: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-vetted-experiment-plan"))


@dataclass(slots=True)
class VettedBenchmarkExperimentResult:
    id: str
    experiment_plan_id: str
    execution_ids: list[str] = field(default_factory=list)
    metric_results: list[dict[str, Any]] = field(default_factory=list)
    comparison_tables: list[dict[str, Any]] = field(default_factory=list)
    error_analysis_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-vetted-experiment-run"))


class SelectedVettedBenchmarkExperimentManager:
    """Plan, run, and report vetted-adapter evidence for a selected benchmark."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.selected_manager = SelectedBenchmarkManager(config)
        self.mapping_manager = SelectedBenchmarkVettedMappingManager(config)
        self.adapter_registry = BenchmarkAdapterRegistry(config)

    def create_plan(self, benchmark_id: str) -> VettedBenchmarkExperimentPlan:
        spec = self.selected_manager.load_spec(benchmark_id)
        mapping_report = self.mapping_manager.load_report(spec.id)
        mappings = _usable_mappings(mapping_report)
        adapters = self._ensure_adapters(spec.id, mappings)
        plan = VettedBenchmarkExperimentPlan(
            id=f"selected-vetted-experiment-plan-{slugify(spec.id)}",
            selected_benchmark_id=spec.id,
            adapter_ids=[adapter.id for adapter in adapters],
            monitor_ids=spec.required_baselines or ["selected-monitor-baselines"],
            metric_ids=[
                "vetted_adapted_example_count",
                "vetted_label_preservation",
                "vetted_split_preservation",
                "vetted_adapter_warning_count",
            ],
            run_type="vetted_adapter",
            expected_outputs=[
                "adapter run manifests",
                "vetted-only metric summaries",
                "mapping-strength comparison table",
                "manuscript limitation feed",
            ],
            limitations=_plan_limitations(mapping_report, mappings, adapters),
            provenance=Provenance(
                created_by_skill="selected-vetted-experiment-plan",
                source_ids=[spec.id, mapping_report.id, *[adapter.id for adapter in adapters]],
                timestamp=utc_now_iso(),
                reasoning_summary="Planned vetted benchmark adapter evidence separately from synthetic selected-benchmark results.",
            ),
        )
        self._write_plan(spec.project_id, plan)
        return plan

    def load_plan(self, plan_id: str) -> VettedBenchmarkExperimentPlan:
        for project in self.project_manager.list_projects():
            path = self._experiment_dir(project.id) / f"{plan_id}.plan.json"
            if path.exists():
                return from_dict(VettedBenchmarkExperimentPlan, json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No selected vetted benchmark experiment plan found for {plan_id}")

    def run_plan(self, plan_id: str) -> VettedBenchmarkExperimentResult:
        plan = self.load_plan(plan_id)
        spec = self.selected_manager.load_spec(plan.selected_benchmark_id)
        mapping_report = self.mapping_manager.load_report(spec.id)
        mapping_by_benchmark = {mapping.vetted_benchmark_id: mapping for mapping in mapping_report.mappings}
        adapter_runs: list[tuple[BenchmarkAdapter, BenchmarkAdapterRun, dict[str, Any]]] = []
        limitations = list(plan.limitations)
        for adapter_id in plan.adapter_ids:
            adapter = self.adapter_registry.load_adapter(adapter_id)
            run = self.adapter_registry.run_adapter(adapter.id)
            payload = self._load_adapter_payload(run)
            adapter_runs.append((adapter, run, payload))
            limitations.extend(_run_limitations(adapter, run, mapping_by_benchmark.get(adapter.vetted_benchmark_id)))
        metric_results = _metric_results(plan, adapter_runs, mapping_by_benchmark)
        comparison_tables = [_comparison_table(adapter_runs, mapping_by_benchmark)]
        result = VettedBenchmarkExperimentResult(
            id=f"selected-vetted-experiment-result-{slugify(plan.id)}",
            experiment_plan_id=plan.id,
            execution_ids=[run.id for _adapter, run, _payload in adapter_runs],
            metric_results=metric_results,
            comparison_tables=comparison_tables,
            error_analysis_ids=[
                f"vetted-adapter-error-analysis-{slugify(run.id)}" for _adapter, run, _payload in adapter_runs if run.warnings
            ],
            limitations=_dedupe(limitations),
            provenance=Provenance(
                created_by_skill="selected-vetted-experiment-run",
                source_ids=[plan.id, *[run.id for _adapter, run, _payload in adapter_runs]],
                timestamp=utc_now_iso(),
                reasoning_summary="Ran vetted adapter experiments with result labels separated from synthetic benchmark outputs.",
            ),
        )
        self._write_result(spec.project_id, result)
        return result

    def render_report(self, plan_id: str) -> str:
        plan = self.load_plan(plan_id)
        spec = self.selected_manager.load_spec(plan.selected_benchmark_id)
        result = self._load_or_run_result(spec.project_id, plan)
        markdown = render_vetted_benchmark_experiment_report(plan, result)
        (self._experiment_dir(spec.project_id) / f"{plan.id}.report.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _ensure_adapters(self, selected_benchmark_id: str, mappings: list[SelectedBenchmarkVettedMapping]) -> list[BenchmarkAdapter]:
        existing = self.adapter_registry.list_adapters(selected_benchmark_id)
        by_vetted = {adapter.vetted_benchmark_id: adapter for adapter in existing}
        adapters = []
        for mapping in mappings:
            adapter = by_vetted.get(mapping.vetted_benchmark_id)
            if adapter is None:
                adapter = self.adapter_registry.create_adapter(
                    selected_benchmark_id=selected_benchmark_id,
                    vetted_benchmark_id=mapping.vetted_benchmark_id,
                )
            adapters.append(adapter)
        return adapters

    def _load_adapter_payload(self, run: BenchmarkAdapterRun) -> dict[str, Any]:
        path = self.adapter_registry.adapter_output_path(run.id)
        if run.status != "complete" or not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_or_run_result(self, project_id: str, plan: VettedBenchmarkExperimentPlan) -> VettedBenchmarkExperimentResult:
        path = self._experiment_dir(project_id) / f"{plan.id}.result.json"
        if path.exists():
            return from_dict(VettedBenchmarkExperimentResult, json.loads(path.read_text(encoding="utf-8")))
        return self.run_plan(plan.id)

    def _write_plan(self, project_id: str, plan: VettedBenchmarkExperimentPlan) -> None:
        experiment_dir = self._experiment_dir(project_id)
        experiment_dir.mkdir(parents=True, exist_ok=True)
        (experiment_dir / f"{plan.id}.plan.json").write_text(json.dumps(to_plain(plan), indent=2) + "\n", encoding="utf-8")
        (experiment_dir / f"{plan.id}.plan.md").write_text(render_vetted_benchmark_experiment_plan(plan), encoding="utf-8")

    def _write_result(self, project_id: str, result: VettedBenchmarkExperimentResult) -> None:
        experiment_dir = self._experiment_dir(project_id)
        experiment_dir.mkdir(parents=True, exist_ok=True)
        (experiment_dir / f"{result.experiment_plan_id}.result.json").write_text(
            json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8"
        )
        plan = self.load_plan(result.experiment_plan_id)
        (experiment_dir / f"{result.experiment_plan_id}.report.md").write_text(
            render_vetted_benchmark_experiment_report(plan, result),
            encoding="utf-8",
        )

    def _experiment_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "vetted_experiments"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_vetted_benchmark_experiment_plan(plan: VettedBenchmarkExperimentPlan) -> str:
    lines = [
        f"# Selected Vetted Benchmark Experiment Plan `{plan.id}`",
        "",
        f"- Selected benchmark: `{plan.selected_benchmark_id}`",
        f"- Run type: `{plan.run_type}`",
        f"- Adapters: {_fmt(plan.adapter_ids)}",
        f"- Monitors: {_fmt(plan.monitor_ids)}",
        f"- Metrics: {_fmt(plan.metric_ids)}",
        "",
        "## Separation Rule",
        "",
        "Vetted benchmark results must be reported as `vetted_adapter` evidence and kept separate from synthetic benchmark results.",
        "",
        "## Expected Outputs",
        "",
        *[f"- {item}" for item in plan.expected_outputs],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in (plan.limitations or ["No limitations recorded."])],
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_vetted_benchmark_experiment_report(
    plan: VettedBenchmarkExperimentPlan,
    result: VettedBenchmarkExperimentResult,
) -> str:
    lines = [
        f"# Selected Vetted Benchmark Experiment Report `{plan.id}`",
        "",
        f"- Selected benchmark: `{plan.selected_benchmark_id}`",
        f"- Run type: `{plan.run_type}`",
        "- Result source label: `vetted_adapter`",
        f"- Adapter executions: {_fmt(result.execution_ids)}",
        "",
        "## Separation Rule",
        "",
        "These results are not synthetic benchmark results and must not be merged with synthetic metrics without explicit labels.",
        "",
        "## Metrics",
        "",
    ]
    if result.metric_results:
        for metric in result.metric_results:
            lines.append(
                f"- `{metric['metric_id']}` on `{metric['adapter_id']}`: {metric['value']} "
                f"(mapping `{metric['mapping_type']}`, source `{metric['result_source']}`)"
            )
    else:
        lines.append("No vetted adapter metrics were produced.")
    lines.extend(["", "## Comparison Tables", ""])
    for table in result.comparison_tables:
        lines.extend([f"### {table.get('title', 'Comparison')}", ""])
        for row in table.get("rows", []):
            lines.append(
                f"- `{row['adapter_id']}` maps as `{row['mapping_type']}` and is labeled `{row['experiment_role']}`; "
                f"examples={row['adapted_example_count']}, warnings={row['warning_count']}"
            )
        lines.append("")
    lines.extend(["## Manuscript Limitation Feed", ""])
    lines.extend(f"- {item}" for item in (result.limitations or plan.limitations or ["No limitations recorded."]))
    return "\n".join(lines).rstrip() + "\n"


def _usable_mappings(report: VettedBenchmarkMappingReport) -> list[SelectedBenchmarkVettedMapping]:
    return [mapping for mapping in report.mappings if mapping.mapping_type != "rejected"]


def _plan_limitations(
    mapping_report: VettedBenchmarkMappingReport,
    mappings: list[SelectedBenchmarkVettedMapping],
    adapters: list[BenchmarkAdapter],
) -> list[str]:
    limitations = [
        "Vetted benchmark results are separate from synthetic selected-benchmark results.",
        "Do not merge synthetic and vetted benchmark metrics without explicit source labels.",
        "Vetted benchmark results can strengthen the paper only when the mapping report supports relevance.",
    ]
    if not mappings:
        limitations.append("No non-rejected vetted benchmark mapping is available; no vetted experiment evidence is planned.")
    if not mapping_report.primary_candidate_ids:
        limitations.append(
            "No direct vetted benchmark candidate is available; use vetted results only as auxiliary or sanity-check evidence."
        )
    for mapping in mappings:
        if mapping.recommended_experiment_role != "primary":
            limitations.append(
                f"Benchmark `{mapping.vetted_benchmark_id}` is `{mapping.recommended_experiment_role}`; manuscript must label it auxiliary."
            )
    for adapter in adapters:
        limitations.extend(adapter.limitations)
    return _dedupe(limitations)


def _run_limitations(
    adapter: BenchmarkAdapter,
    run: BenchmarkAdapterRun,
    mapping: SelectedBenchmarkVettedMapping | None,
) -> list[str]:
    limitations = list(adapter.limitations)
    limitations.extend(run.warnings)
    if mapping is None:
        limitations.append(f"Adapter `{adapter.id}` has no mapping report entry; results cannot strengthen claims.")
    elif mapping.mapping_type != "direct":
        limitations.append(
            f"Adapter `{adapter.id}` maps as `{mapping.mapping_type}`; manuscript must label the result as "
            f"{mapping.recommended_experiment_role}."
        )
    return limitations


def _metric_results(
    plan: VettedBenchmarkExperimentPlan,
    adapter_runs: list[tuple[BenchmarkAdapter, BenchmarkAdapterRun, dict[str, Any]]],
    mapping_by_benchmark: dict[str, SelectedBenchmarkVettedMapping],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for adapter, run, payload in adapter_runs:
        mapping = mapping_by_benchmark.get(adapter.vetted_benchmark_id)
        example_count = len(payload.get("examples", [])) if payload else 0
        preserved = payload.get("preserved_fields", {}) if payload else {}
        common = {
            "adapter_id": adapter.id,
            "execution_id": run.id,
            "selected_benchmark_id": plan.selected_benchmark_id,
            "vetted_benchmark_id": adapter.vetted_benchmark_id,
            "mapping_type": mapping.mapping_type if mapping else "unmapped",
            "experiment_role": mapping.recommended_experiment_role if mapping else "not_recommended",
            "result_source": "vetted_adapter",
            "synthetic": False,
            "do_not_merge_with_synthetic": True,
            "limitations": _dedupe(run.warnings + (mapping.unsupported_claims if mapping else [])),
        }
        results.extend(
            [
                {**common, "metric_id": "vetted_adapted_example_count", "value": example_count},
                {**common, "metric_id": "vetted_label_preservation", "value": int(bool(preserved.get("original_labels_preserved")))},
                {**common, "metric_id": "vetted_split_preservation", "value": int(bool(preserved.get("original_splits_preserved")))},
                {**common, "metric_id": "vetted_adapter_warning_count", "value": len(run.warnings)},
            ]
        )
    return results


def _comparison_table(
    adapter_runs: list[tuple[BenchmarkAdapter, BenchmarkAdapterRun, dict[str, Any]]],
    mapping_by_benchmark: dict[str, SelectedBenchmarkVettedMapping],
) -> dict[str, Any]:
    rows = []
    for adapter, run, payload in adapter_runs:
        mapping = mapping_by_benchmark.get(adapter.vetted_benchmark_id)
        rows.append(
            {
                "adapter_id": adapter.id,
                "execution_id": run.id,
                "vetted_benchmark_id": adapter.vetted_benchmark_id,
                "mapping_type": mapping.mapping_type if mapping else "unmapped",
                "experiment_role": mapping.recommended_experiment_role if mapping else "not_recommended",
                "result_source": "vetted_adapter",
                "adapted_example_count": len(payload.get("examples", [])) if payload else 0,
                "warning_count": len(run.warnings),
                "synthetic_result_count": 0,
            }
        )
    return {
        "id": "vetted_adapter_mapping_strength_table",
        "title": "Vetted Adapter Mapping Strength",
        "result_source": "vetted_adapter",
        "rows": rows,
    }


def _dedupe(items: list[str]) -> list[str]:
    deduped = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
