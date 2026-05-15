"""Experiment path for selected benchmarks using vetted benchmark adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.real_benchmark_search import RealBenchmarkCandidate, RealBenchmarkSearchManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.vetted_mapping import (
    SelectedBenchmarkVettedMapping,
    SelectedBenchmarkVettedMappingManager,
    VettedBenchmarkMappingReport,
)
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks import (
    BenchmarkAdapter,
    BenchmarkAdapterRegistry,
    BenchmarkAdapterRun,
    RealBenchmarkAdapterAssessment,
    render_benchmark_adapter_report,
    render_real_benchmark_adapter_assessment,
)


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
        self.real_search = RealBenchmarkSearchManager(config)

    def assess_real_candidate(self, benchmark_id: str, candidate_id: str) -> RealBenchmarkAdapterAssessment:
        spec = self.selected_manager.load_spec(benchmark_id)
        candidate = self._real_candidate(spec.id, candidate_id)
        assessment = _assess_real_candidate(spec.id, candidate)
        self._write_real_adapter_assessment(spec.project_id, assessment)
        return assessment

    def create_real_candidate_adapter(self, benchmark_id: str, candidate_id: str) -> BenchmarkAdapter:
        spec = self.selected_manager.load_spec(benchmark_id)
        candidate = self._real_candidate(spec.id, candidate_id)
        assessment = self.assess_real_candidate(spec.id, candidate.id)
        if not assessment.adapter_possible:
            raise ValueError(f"No honest real benchmark adapter can be created for `{candidate.id}`: " + "; ".join(assessment.blockers))
        adapter = BenchmarkAdapter(
            id=_real_adapter_id(spec.id, candidate.id),
            vetted_benchmark_id=candidate.id,
            candidate_benchmark_id=candidate.id,
            selected_benchmark_id=spec.id,
            adapter_type=assessment.adapter_type,
            evidence_label=assessment.expected_claim_support,
            expected_claim_support=assessment.expected_claim_support,
            input_schema=_real_candidate_input_schema(candidate),
            output_schema=_real_candidate_output_schema(assessment),
            transformation_description=_real_candidate_transformation_description(candidate, assessment),
            limitations=_dedupe(
                [
                    *candidate.limitations,
                    *assessment.schema_mismatches,
                    *assessment.label_mismatches,
                    *assessment.blockers,
                    "Real public benchmark adapter does not download datasets automatically.",
                    "Adapter output must remain separated from synthetic selected-benchmark results.",
                ]
            ),
            implementation_path="gapforge.selected_benchmark.vetted_experiment.run_real_candidate_adapter",
            provenance=Provenance(
                created_by_skill="selected-real-benchmark-adapter-create",
                source_ids=[spec.id, candidate.id, candidate.source_url, assessment.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a metadata-only real public benchmark adapter with explicit claim support labels.",
            ),
        )
        self._write_real_adapter(spec.project_id, adapter, assessment)
        return adapter

    def run_real_candidate_adapter(self, adapter_id: str) -> BenchmarkAdapterRun:
        adapter = self.adapter_registry.load_adapter(adapter_id)
        if not adapter.candidate_benchmark_id:
            return self.adapter_registry.run_adapter(adapter_id)
        spec = self.selected_manager.load_spec(adapter.selected_benchmark_id)
        candidate = self._real_candidate(spec.id, adapter.candidate_benchmark_id)
        assessment = self.assess_real_candidate(spec.id, candidate.id)
        run_id = _real_adapter_run_id(adapter.id)
        output_dir = self.config.data_dir / "vetted_benchmarks" / "adapter_runs" / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        warnings = _real_adapter_run_warnings(adapter, assessment)
        output = _real_adapter_output(adapter, candidate, assessment, warnings)
        output_path = output_dir / "adapted_trace_units.json"
        output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        run = BenchmarkAdapterRun(
            id=run_id,
            adapter_id=adapter.id,
            dataset_id=f"candidate-metadata:{candidate.id}",
            status="complete",
            output_dataset_id=f"metadata-adapted-{candidate.id}",
            warnings=warnings,
            provenance=Provenance(
                created_by_skill="selected-real-benchmark-adapter-run",
                source_ids=[adapter.id, candidate.id, candidate.source_url, assessment.id, str(output_path)],
                timestamp=utc_now_iso(),
                reasoning_summary="Ran a metadata-only real benchmark adapter without downloading benchmark datasets.",
            ),
        )
        (output_dir / "run.json").write_text(json.dumps(to_plain(run), indent=2) + "\n", encoding="utf-8")
        (output_dir / "run.md").write_text(_render_real_adapter_run(run, output_path), encoding="utf-8")
        return run

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

    def _real_candidate(self, benchmark_id: str, candidate_id: str) -> RealBenchmarkCandidate:
        candidates = self.real_search.load_candidates(benchmark_id)
        for candidate in candidates:
            if candidate.id == candidate_id:
                return candidate
        raise FileNotFoundError(f"No real benchmark candidate `{candidate_id}` for selected benchmark `{benchmark_id}`")

    def _write_real_adapter_assessment(self, project_id: str, assessment: RealBenchmarkAdapterAssessment) -> None:
        assessment_dir = self._real_adapter_dir(project_id)
        assessment_dir.mkdir(parents=True, exist_ok=True)
        path = assessment_dir / f"{assessment.id}.json"
        path.write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_real_benchmark_adapter_assessment(assessment), encoding="utf-8")

    def _write_real_adapter(
        self,
        project_id: str,
        adapter: BenchmarkAdapter,
        assessment: RealBenchmarkAdapterAssessment,
    ) -> None:
        adapters_dir = self.config.data_dir / "vetted_benchmarks" / "adapters"
        adapters_dir.mkdir(parents=True, exist_ok=True)
        adapter_path = adapters_dir / f"{adapter.id}.adapter.json"
        adapter_path.write_text(json.dumps(to_plain(adapter), indent=2) + "\n", encoding="utf-8")
        adapter_path.with_suffix(".md").write_text(render_benchmark_adapter_report(adapter, []), encoding="utf-8")
        real_dir = self._real_adapter_dir(project_id)
        real_dir.mkdir(parents=True, exist_ok=True)
        (real_dir / f"{adapter.id}.adapter.json").write_text(json.dumps(to_plain(adapter), indent=2) + "\n", encoding="utf-8")
        (real_dir / f"{adapter.id}.adapter.md").write_text(render_benchmark_adapter_report(adapter, []), encoding="utf-8")
        (real_dir / f"{adapter.id}.assessment.json").write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")

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

    def _real_adapter_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "real_benchmark_adapters"
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


def _assess_real_candidate(selected_benchmark_id: str, candidate: RealBenchmarkCandidate) -> RealBenchmarkAdapterAssessment:
    text = _candidate_text(candidate)
    has_collusion = _has_any(text, ["collusion", "collusive", "covert", "coordination", "cartel"])
    has_monitoring = _has_any(text, ["monitor", "audit", "safety", "security", "attack", "defense"])
    has_sequential = _has_any(text, ["sequential", "streaming", "time-series", "online", "repeated", "window", "trajectory"])
    has_low_fpr = _has_any(text, ["low-fpr", "low false", "false-positive", "specificity", "false alarm"])
    has_labels = _has_any(text, ["label", "ground truth", "outcome", "attack success", "classification", "anomaly"])
    has_agent = _has_any(text, ["agent", "llm", "tool", "prompt injection", "deception"])
    schema_mismatches = []
    label_mismatches = []
    blockers = []
    if "separate" in candidate.dataset_access.lower() or "authentication" in candidate.dataset_access.lower():
        schema_mismatches.append(
            "Benchmark assets require separate access review; adapter must remain metadata-only until fetched explicitly."
        )
    if not has_sequential:
        schema_mismatches.append("Source benchmark does not expose native sequential windows; sequentialization would be artificial.")
    if not has_labels:
        label_mismatches.append("No explicit source labels are visible in candidate metadata.")
    if not has_collusion:
        label_mismatches.append("Source labels do not directly map to collusion or covert coordination.")
    if not has_monitoring:
        label_mismatches.append("Source task does not directly map to monitoring or audit decisions.")

    if candidate.fit_status == "no_fit":
        blockers.append(candidate.fit_reason or "Candidate was explicitly marked no-fit by benchmark search.")
    if has_collusion and has_monitoring and has_sequential and has_low_fpr and has_labels:
        adapter_type = "direct"
        expected_claim_support = "primary"
        adapter_possible = True
    elif has_agent and has_monitoring and has_labels:
        adapter_type = "trace_conversion"
        expected_claim_support = "auxiliary"
        adapter_possible = True
        blockers.append("Strong claims are blocked because candidate metadata does not establish collusion-specific low-FPR labels.")
    elif has_sequential or _has_any(text, ["anomaly", "time-series", "specificity", "false alarm"]):
        adapter_type = "sanity_check"
        expected_claim_support = "sanity_check"
        adapter_possible = True
        blockers.append("Strong claims are blocked because candidate can only sanity-check metric or sequentialization plumbing.")
    else:
        adapter_type = "auxiliary"
        expected_claim_support = "no_fit"
        adapter_possible = False
        blockers.append("Candidate metadata does not provide an honest adapter path for the selected benchmark.")

    return RealBenchmarkAdapterAssessment(
        id=f"real-benchmark-adapter-assessment-{slugify(selected_benchmark_id)}-{slugify(candidate.id)}",
        candidate_benchmark_id=candidate.id,
        selected_benchmark_id=selected_benchmark_id,
        adapter_possible=adapter_possible,
        adapter_type=adapter_type,
        schema_mismatches=_dedupe(schema_mismatches),
        label_mismatches=_dedupe(label_mismatches),
        sequentialization_needed=not has_sequential,
        observability_mapping=_observability_mapping(candidate, expected_claim_support),
        expected_claim_support=expected_claim_support,
        blockers=_dedupe(blockers),
        provenance=Provenance(
            created_by_skill="real-benchmark-adapter-assessment",
            source_ids=[selected_benchmark_id, candidate.id, candidate.source_url],
            timestamp=utc_now_iso(),
            reasoning_summary="Assessed real public benchmark adapter feasibility without downloading assets or upgrading claims.",
        ),
    )


def _observability_mapping(candidate: RealBenchmarkCandidate, expected_claim_support: str) -> list[str]:
    mapping = [
        "Candidate metadata maps to adapter provenance and source boundary fields.",
        "Original benchmark labels, if later fetched, must be preserved as `original_label`.",
        "Source observations, prompts, traces, or time-series rows must be preserved as source observations.",
    ]
    if expected_claim_support == "sanity_check":
        mapping.append("Adapter output must be labeled `sanity_check` and cannot support strong collusion claims.")
    elif expected_claim_support == "primary":
        mapping.append("Primary support remains conditional on preserving source collusion/monitoring labels during transformation.")
    else:
        mapping.append("Adapter output must be labeled auxiliary unless mapping assessment is strengthened.")
    if "prompt injection" in _candidate_text(candidate):
        mapping.append("Prompt-injection attack outcomes may map to monitor-evasion evidence, not collusion labels.")
    return mapping


def _real_candidate_input_schema(candidate: RealBenchmarkCandidate) -> dict[str, Any]:
    return {
        "candidate_benchmark_id": candidate.id,
        "name": candidate.name,
        "source_url": candidate.source_url,
        "benchmark_type": candidate.benchmark_type,
        "domain": candidate.domain,
        "task_type": candidate.task_type,
        "license": candidate.license,
        "dataset_access": candidate.dataset_access,
        "local_dataset_available": False,
        "downloaded_by_adapter": False,
    }


def _real_candidate_output_schema(assessment: RealBenchmarkAdapterAssessment) -> dict[str, Any]:
    return {
        "adapter_id": "string",
        "candidate_benchmark_id": "string",
        "selected_benchmark_id": "string",
        "result_source": "real_public_benchmark_adapter",
        "evidence_label": assessment.expected_claim_support,
        "strong_claims_allowed": assessment.expected_claim_support == "primary" and not assessment.blockers,
        "examples": "empty until explicit dataset acquisition and adapter transformation are run",
    }


def _real_candidate_transformation_description(
    candidate: RealBenchmarkCandidate,
    assessment: RealBenchmarkAdapterAssessment,
) -> str:
    sequentialization = (
        "Sequentialization would be artificial and must be warning-labeled."
        if assessment.sequentialization_needed
        else "Candidate metadata indicates native sequential or trajectory structure."
    )
    return (
        f"Record metadata-only adapter for `{candidate.name}` from `{candidate.source_url}`. "
        "No benchmark assets are downloaded by adapter creation. "
        f"Output is labeled `{assessment.expected_claim_support}` and cannot be used for stronger claims unless a later "
        "dataset transformation preserves source labels, splits, and observability units. "
        f"{sequentialization}"
    )


def _real_adapter_output(
    adapter: BenchmarkAdapter,
    candidate: RealBenchmarkCandidate,
    assessment: RealBenchmarkAdapterAssessment,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "adapter_id": adapter.id,
        "candidate_benchmark_id": candidate.id,
        "selected_benchmark_id": adapter.selected_benchmark_id,
        "source_url": candidate.source_url,
        "result_source": "real_public_benchmark_adapter",
        "evidence_label": adapter.evidence_label,
        "expected_claim_support": adapter.expected_claim_support,
        "strong_claims_allowed": assessment.expected_claim_support == "primary" and not assessment.blockers,
        "synthetic": False,
        "downloaded_dataset": False,
        "transformation_description": adapter.transformation_description,
        "observability_mapping": list(assessment.observability_mapping),
        "warnings": warnings,
        "preserved_fields": {
            "original_labels_preserved": False,
            "original_splits_preserved": False,
            "reason": "metadata-only run; no dataset was downloaded or transformed",
        },
        "examples": [],
    }


def _real_adapter_run_warnings(
    adapter: BenchmarkAdapter,
    assessment: RealBenchmarkAdapterAssessment,
) -> list[str]:
    warnings = [
        "Metadata-only real benchmark adapter run; no benchmark dataset was downloaded.",
        *assessment.schema_mismatches,
        *assessment.label_mismatches,
        *assessment.blockers,
    ]
    if adapter.evidence_label == "sanity_check":
        warnings.append("Adapter output is sanity-check only and must not support strong benchmark-validity claims.")
    if assessment.sequentialization_needed:
        warnings.append("Sequentialization is artificial for this candidate and must be described as such.")
    return _dedupe(warnings)


def _render_real_adapter_run(run: BenchmarkAdapterRun, output_path: Path) -> str:
    lines = [
        f"# Real Benchmark Adapter Run `{run.id}`",
        "",
        f"- Adapter ID: `{run.adapter_id}`",
        f"- Status: `{run.status}`",
        f"- Dataset: `{run.dataset_id}`",
        f"- Output dataset ID: `{run.output_dataset_id}`",
        f"- Output artifact: `{output_path}`",
        "",
        "## Warnings",
        "",
        *[f"- {warning}" for warning in (run.warnings or ["none"])],
    ]
    return "\n".join(lines).rstrip() + "\n"


def _real_adapter_id(selected_benchmark_id: str, candidate_id: str) -> str:
    digest = hashlib.sha1(f"{selected_benchmark_id}:{candidate_id}".encode()).hexdigest()[:6]
    return f"real-benchmark-adapter-{slugify(selected_benchmark_id)}-{slugify(candidate_id)}-{digest}"


def _real_adapter_run_id(adapter_id: str) -> str:
    digest = hashlib.sha1(f"{adapter_id}:{utc_now_iso()}".encode()).hexdigest()[:6]
    return f"real-benchmark-adapter-run-{slugify(adapter_id)}-{digest}"


def _candidate_text(candidate: RealBenchmarkCandidate) -> str:
    return " ".join(
        [
            candidate.name,
            candidate.benchmark_type,
            candidate.domain,
            candidate.task_type,
            candidate.relevance_to_selected_benchmark,
            candidate.fit_reason,
            " ".join(candidate.adaptation_required),
            " ".join(candidate.limitations),
        ]
    ).lower()


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _dedupe(items: list[str]) -> list[str]:
    deduped = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
