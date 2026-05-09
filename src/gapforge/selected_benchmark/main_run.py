"""Main benchmark manifest and execution workflow for the selected benchmark."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import (
    REQUIRED_MAIN_BASELINE_TYPES,
    MonitorBaselineManager,
    MonitorBaselineRun,
)
from gapforge.selected_benchmark.main_dataset import MainDatasetBuilder, MainTraceDataset
from gapforge.selected_benchmark.metrics import (
    SequentialMetricResult,
    compute_sequential_metric_results,
    render_low_fpr_audit_check,
    render_sequential_metric_report,
)
from gapforge.selected_benchmark.sequential import summarize_sequential_audit
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.trace_generator import AgentTrace, SyntheticTraceGenerator, TraceDataset
from gapforge.state import slugify, utc_now_iso

SYNTHETIC_MAIN_LABEL = "synthetic_main_data"
REQUIRED_MAIN_OUTPUT_KEYS = [
    "metrics_json",
    "predictions_json",
    "baseline_comparison",
    "error_analysis",
    "low_fpr_report_json",
    "low_fpr_report_md",
    "failures_json",
    "status_json",
]


@dataclass(slots=True)
class SelectedMainRunManifest:
    id: str
    benchmark_id: str
    dataset_id: str
    baseline_monitor_ids: list[str] = field(default_factory=list)
    calibration_record_ids: list[str] = field(default_factory=list)
    metric_plan_id: str = ""
    random_seed: int = 0
    alpha_targets_supported: dict[str, dict[str, Any]] = field(default_factory=dict)
    powered_alpha_levels: list[str] = field(default_factory=list)
    expected_outputs: dict[str, str] = field(default_factory=dict)
    run_type: str = "main"
    synthetic_data_label: str = SYNTHETIC_MAIN_LABEL
    publication_blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-run"))


@dataclass(slots=True)
class SelectedMainExecution:
    id: str
    benchmark_id: str
    manifest_id: str
    dataset_id: str
    run_type: str
    status: str
    synthetic_data_label: str
    metric_result_count: int = 0
    monitor_run_ids: list[str] = field(default_factory=list)
    powered_alpha_levels: list[str] = field(default_factory=list)
    output_paths: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    publication_claim_blocked: bool = True
    publication_blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-run"))


class MainRunManager:
    """Create and execute v2.3 selected-benchmark main manifests."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.dataset_builder = MainDatasetBuilder(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)

    def create_manifest(self, benchmark_id: str, dataset_id: str, *, random_seed: int = 20260323) -> SelectedMainRunManifest:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        dataset = self.dataset_builder.load(dataset_id)
        if dataset.benchmark_id != benchmark_id:
            raise ValueError(f"Dataset `{dataset_id}` belongs to benchmark `{dataset.benchmark_id}`, not `{benchmark_id}`.")
        baselines = self.baseline_manager.load_baselines(benchmark_id) or self.baseline_manager.create_baselines(benchmark_id)
        monitor_ids = [baseline.id for baseline in baselines if _main_manifest_monitor(baseline)]
        calibration_record_ids = []
        for baseline in baselines:
            if baseline.id in monitor_ids and baseline.parameters.get("calibration_required"):
                try:
                    record = self.baseline_manager.calibrate_monitor(
                        benchmark_id,
                        baseline.id,
                        target_alpha=float(baseline.parameters.get("target_alpha", 0.01)),
                    )
                    calibration_record_ids.append(record.id)
                except Exception:
                    continue
        metric_plan = self._metric_plan(benchmark_id)
        baseline_strength = self.baseline_manager.assess_baseline_strength(benchmark_id)
        dataset_blockers = _dataset_publication_blockers(dataset)
        publication_blockers = [*baseline_strength.blockers, *dataset_blockers]
        manifest = SelectedMainRunManifest(
            id=_short_main_id("selected-main-manifest", benchmark_id, dataset_id),
            benchmark_id=benchmark_id,
            dataset_id=dataset_id,
            baseline_monitor_ids=monitor_ids,
            calibration_record_ids=calibration_record_ids,
            metric_plan_id=metric_plan.id,
            random_seed=random_seed,
            alpha_targets_supported=dataset.alpha_targets_supported,
            powered_alpha_levels=_powered_alpha_levels(dataset),
            expected_outputs={key: f"main_runs/executions/<execution-id>/{key}.json" for key in REQUIRED_MAIN_OUTPUT_KEYS},
            run_type="main",
            synthetic_data_label=SYNTHETIC_MAIN_LABEL,
            publication_blockers=publication_blockers,
            provenance=Provenance(
                created_by_skill="selected-main-run",
                source_ids=[benchmark_id, spec.project_id, dataset_id, metric_plan.id, *calibration_record_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a locked v2.3 main manifest with dataset, required baselines, calibration, and alpha support.",
            ),
        )
        self._write_json(self.manifest_path(manifest.id), manifest)
        return manifest

    def load_manifest(self, manifest_id: str) -> SelectedMainRunManifest:
        return from_dict(SelectedMainRunManifest, json.loads(self.manifest_path(manifest_id).read_text(encoding="utf-8")))

    def run(self, benchmark_id: str, manifest_id: str) -> SelectedMainExecution:
        manifest = self.load_manifest(manifest_id)
        if manifest.benchmark_id != benchmark_id:
            raise ValueError(f"Manifest `{manifest_id}` belongs to benchmark `{manifest.benchmark_id}`, not `{benchmark_id}`.")
        execution_id = _short_main_id("selected-main-execution", manifest.id)
        execution_dir = self.execution_dir(execution_id)
        execution_dir.mkdir(parents=True, exist_ok=True)
        failures: list[str] = []
        monitor_runs: list[MonitorBaselineRun] = []
        predictions_by_monitor: dict[str, list[dict[str, Any]]] = {}
        baselines = self.baseline_manager.load_baselines(benchmark_id)
        baseline_by_id = {baseline.id: baseline for baseline in baselines}
        for monitor_id in manifest.baseline_monitor_ids:
            baseline = baseline_by_id.get(monitor_id)
            if baseline is None:
                failures.append(f"Required main monitor `{monitor_id}` is not registered.")
                continue
            try:
                run = self.baseline_manager._run_baseline_on_dataset(  # noqa: SLF001
                    benchmark_id,
                    baseline,
                    manifest.dataset_id,
                    run_label="main",
                )
                monitor_runs.append(run)
                predictions_by_monitor[monitor_id] = self._load_predictions(manifest.dataset_id, monitor_id)
            except Exception as exc:  # pragma: no cover - defensive preserved-failure path
                failures.append(f"Required main monitor `{monitor_id}` failed: {exc}")
        metrics: list[SequentialMetricResult] = []
        try:
            metrics = self._compute_metrics(manifest.dataset_id)
        except Exception as exc:  # pragma: no cover - defensive preserved-failure path
            failures.append(f"Sequential metric computation failed: {exc}")
        dataset = self.dataset_builder.load(manifest.dataset_id)
        baseline_strength = self.baseline_manager.assess_baseline_strength(benchmark_id)
        publication_blockers = [*manifest.publication_blockers, *baseline_strength.blockers, *_dataset_publication_blockers(dataset)]
        output_paths = self._write_execution_artifacts(
            execution_dir=execution_dir,
            manifest=manifest,
            dataset=dataset,
            monitor_runs=monitor_runs,
            predictions_by_monitor=predictions_by_monitor,
            metrics=metrics,
            failures=failures,
            publication_blockers=publication_blockers,
        )
        execution = SelectedMainExecution(
            id=execution_id,
            benchmark_id=benchmark_id,
            manifest_id=manifest.id,
            dataset_id=manifest.dataset_id,
            run_type="main",
            status="failed" if failures else "complete",
            synthetic_data_label=manifest.synthetic_data_label,
            metric_result_count=len(metrics),
            monitor_run_ids=[run.id for run in monitor_runs],
            powered_alpha_levels=manifest.powered_alpha_levels,
            output_paths=output_paths,
            failures=failures,
            warnings=[
                "Main run uses synthetic traces and must not be reported as deployment-validity evidence.",
                "Publication claims remain gated by alpha support, required baselines, calibration leakage, and reviewer blockers.",
            ],
            publication_claim_blocked=bool(publication_blockers),
            publication_blockers=_unique(publication_blockers),
            provenance=Provenance(
                created_by_skill="selected-main-run",
                source_ids=[benchmark_id, manifest.id, manifest.dataset_id, *[run.id for run in monitor_runs]],
                timestamp=utc_now_iso(),
                reasoning_summary="Executed a selected benchmark main manifest and preserved monitor/metric failures as artifacts.",
            ),
        )
        self._write_json(execution_dir / "status_json.json", execution)
        self._write_json(execution_dir / "execution.json", execution)
        (execution_dir / "status.md").write_text(render_selected_main_status(execution), encoding="utf-8")
        return execution

    def status(self, execution_id: str) -> SelectedMainExecution:
        path = self.execution_dir(execution_id) / "execution.json"
        if not path.exists():
            raise FileNotFoundError(f"No selected main execution `{execution_id}` found.")
        return from_dict(SelectedMainExecution, json.loads(path.read_text(encoding="utf-8")))

    def manifest_path(self, manifest_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._main_root(project.id) / "manifests" / f"{manifest_id}.json"
            if path.exists():
                return path
        projects = self.project_manager.list_projects()
        if not projects:
            raise FileNotFoundError("No projects are available for selected main manifests.")
        return self._main_root(projects[-1].id) / "manifests" / f"{manifest_id}.json"

    def execution_dir(self, execution_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._main_root(project.id) / "executions" / execution_id
            if path.exists():
                return path
        projects = self.project_manager.list_projects()
        if not projects:
            raise FileNotFoundError("No projects are available for selected main executions.")
        return self._main_root(projects[-1].id) / "executions" / execution_id

    def _metric_plan(self, benchmark_id: str) -> Any:
        from gapforge.selected_benchmark.metrics import SequentialMetricManager

        return SequentialMetricManager(self.config).create_plan(benchmark_id)

    def _compute_metrics(self, dataset_id: str) -> list[SequentialMetricResult]:
        dataset = self.dataset_builder.load(dataset_id)
        traces = self._load_traces(dataset_id)
        trace_dataset = TraceDataset(
            id=dataset.id,
            benchmark_id=dataset.benchmark_id,
            scenario_ids=sorted(dataset.scenario_coverage),
            trace_ids=[trace.id for trace in traces],
            split="main",
            limitations=dataset.limitations,
            provenance=dataset.provenance,
        )
        summary = summarize_sequential_audit(dataset_id, traces, run_type="main")
        metrics = compute_sequential_metric_results(trace_dataset, summary)
        dataset_dir = self._dataset_dir(dataset_id)
        self._write_json(dataset_dir / "sequential_metrics.json", metrics)
        (dataset_dir / "sequential_metrics.md").write_text(render_sequential_metric_report(trace_dataset, metrics), encoding="utf-8")
        low_fpr = render_low_fpr_audit_check(trace_dataset, metrics)
        (dataset_dir / "low_fpr_audit_check.md").write_text(low_fpr, encoding="utf-8")
        return metrics

    def _write_execution_artifacts(
        self,
        *,
        execution_dir: Path,
        manifest: SelectedMainRunManifest,
        dataset: MainTraceDataset,
        monitor_runs: list[MonitorBaselineRun],
        predictions_by_monitor: dict[str, list[dict[str, Any]]],
        metrics: Sequence[SequentialMetricResult],
        failures: list[str],
        publication_blockers: list[str],
    ) -> dict[str, str]:
        comparison = _baseline_comparison(monitor_runs)
        error_analysis = _error_analysis(
            manifest,
            monitor_runs=monitor_runs,
            metrics=metrics,
            failures=failures,
            publication_blockers=publication_blockers,
        )
        low_fpr_report = _low_fpr_report(dataset, metrics=metrics, publication_blockers=publication_blockers)
        outputs = {
            "metrics_json": execution_dir / "metrics_json.json",
            "predictions_json": execution_dir / "predictions_json.json",
            "baseline_comparison": execution_dir / "baseline_comparison.json",
            "error_analysis": execution_dir / "error_analysis.json",
            "low_fpr_report_json": execution_dir / "low_fpr_report_json.json",
            "low_fpr_report_md": execution_dir / "low_fpr_report_md.md",
            "failures_json": execution_dir / "failures_json.json",
        }
        self._write_json(
            outputs["metrics_json"],
            {"run_type": "main", "synthetic_data_label": SYNTHETIC_MAIN_LABEL, "metrics": list(metrics)},
        )
        self._write_json(
            outputs["predictions_json"],
            {"run_type": "main", "synthetic_data_label": SYNTHETIC_MAIN_LABEL, "predictions_by_monitor": predictions_by_monitor},
        )
        self._write_json(outputs["baseline_comparison"], comparison)
        self._write_json(outputs["error_analysis"], error_analysis)
        self._write_json(outputs["low_fpr_report_json"], low_fpr_report)
        outputs["low_fpr_report_md"].write_text(_render_low_fpr_report(low_fpr_report), encoding="utf-8")
        self._write_json(outputs["failures_json"], {"run_type": "main", "failures": failures})
        outputs["status_json"] = execution_dir / "status_json.json"
        return {key: str(path) for key, path in outputs.items()}

    def _load_predictions(self, dataset_id: str, monitor_id: str) -> list[dict[str, Any]]:
        path = self._dataset_dir(dataset_id) / "monitor_predictions" / monitor_id / "predictions.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []

    def _load_traces(self, dataset_id: str) -> list[AgentTrace]:
        path = self._dataset_dir(dataset_id) / "traces.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(AgentTrace, item) for item in raw]

    def _dataset_dir(self, dataset_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._benchmark_dir(project.id) / "trace_datasets" / dataset_id
            if path.exists():
                return path
        raise FileNotFoundError(f"No selected benchmark trace dataset `{dataset_id}` found.")

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _main_root(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "main_runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_selected_main_status(execution: SelectedMainExecution) -> str:
    lines = [
        f"# Selected Main Benchmark Status `{execution.id}`",
        "",
        f"- Benchmark ID: `{execution.benchmark_id}`",
        f"- Manifest ID: `{execution.manifest_id}`",
        f"- Dataset ID: `{execution.dataset_id}`",
        f"- Run type: `{execution.run_type}`",
        f"- Synthetic data label: `{execution.synthetic_data_label}`",
        f"- Status: `{execution.status}`",
        f"- Metric results: {execution.metric_result_count}",
        f"- Monitor runs: {len(execution.monitor_run_ids)}",
        f"- Powered alpha levels: {', '.join(execution.powered_alpha_levels) or 'none'}",
        f"- Publication claim blocked: {str(execution.publication_claim_blocked).lower()}",
        "",
        "## Outputs",
        "",
    ]
    lines.extend([f"- `{key}`: {path}" for key, path in sorted(execution.output_paths.items())] or ["- none"])
    lines.extend(["", "## Publication Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in execution.publication_blockers] or ["- none"])
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in execution.failures] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in execution.warnings] or ["- none"])
    lines.extend(["", "## Non-Claims", ""])
    lines.append("- Synthetic traces do not establish deployment validity.")
    return "\n".join(lines).rstrip() + "\n"


def _main_manifest_monitor(baseline: Any) -> bool:
    return bool(
        baseline.parameters.get("required", False)
        and baseline.parameters.get("ci_enabled", True)
        and not baseline.parameters.get("analysis_only", False)
        and not baseline.parameters.get("optional", False)
    )


def _short_main_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode()).hexdigest()[:12]
    readable = slugify(parts[-1])[:36] if parts else "main"
    return f"{prefix}-{readable}-{digest}"


def _powered_alpha_levels(dataset: MainTraceDataset) -> list[str]:
    return [
        alpha
        for alpha, payload in sorted(dataset.alpha_targets_supported.items(), key=lambda item: float(item[0]))
        if payload.get("status") == "supported"
    ]


def _dataset_publication_blockers(dataset: MainTraceDataset) -> list[str]:
    blockers = []
    for alpha, payload in sorted(dataset.alpha_targets_supported.items(), key=lambda item: float(item[0])):
        if payload.get("status") != "supported":
            blockers.append(f"alpha={alpha} is not powered for dataset `{dataset.id}` ({payload.get('status')}).")
    blockers.append("Synthetic-only main run cannot support deployment-validity claims.")
    return blockers


def _baseline_comparison(monitor_runs: list[MonitorBaselineRun]) -> dict[str, object]:
    rows = []
    for run in monitor_runs:
        alert_rate = run.alert_count / run.prediction_count if run.prediction_count else 0.0
        rows.append(
            {
                "monitor_id": run.monitor_id,
                "prediction_count": run.prediction_count,
                "alert_count": run.alert_count,
                "alert_rate": alert_rate,
                "trace_count": run.trace_count,
                "run_type": "main",
            }
        )
    return {
        "run_type": "main",
        "comparison_scope": "synthetic main baseline comparison",
        "rows": rows,
        "limitations": [
            "Comparison is descriptive over synthetic main traces only.",
            "Threshold-calibrated monitors depend on honest/null calibration records.",
            "Missing required baselines block publication contribution claims.",
        ],
    }


def _error_analysis(
    manifest: SelectedMainRunManifest,
    *,
    monitor_runs: list[MonitorBaselineRun],
    metrics: Sequence[SequentialMetricResult],
    failures: list[str],
    publication_blockers: list[str],
) -> dict[str, object]:
    expected = set(manifest.baseline_monitor_ids)
    observed = {run.monitor_id for run in monitor_runs}
    return {
        "run_type": "main",
        "synthetic_data_label": manifest.synthetic_data_label,
        "missing_monitor_outputs": sorted(expected - observed),
        "missing_required_baseline_types": _missing_required_baseline_types(manifest.baseline_monitor_ids),
        "failure_count": len(failures),
        "failures": failures,
        "publication_blockers": _unique(publication_blockers),
        "metric_result_count": len(metrics),
        "monitor_summaries": [
            {
                "monitor_id": run.monitor_id,
                "alert_count": run.alert_count,
                "prediction_count": run.prediction_count,
                "error_bucket": "high_alert_rate" if run.prediction_count and run.alert_count / run.prediction_count > 0.5 else "nominal",
            }
            for run in monitor_runs
        ],
        "limitations": [
            "Error analysis is main-run artifact triage, not a deployment failure taxonomy.",
            "Failures are preserved as first-class outputs instead of being hidden by partial success.",
        ],
    }


def _missing_required_baseline_types(monitor_ids: list[str]) -> list[str]:
    present_types = {monitor_id.removeprefix("monitor-").replace("-", "_") for monitor_id in monitor_ids}
    present_types.add("lexical_similarity_detector" if "monitor-lexical-overlap-detector" in monitor_ids else "")
    return sorted(REQUIRED_MAIN_BASELINE_TYPES - present_types)


def _low_fpr_report(
    dataset: MainTraceDataset,
    *,
    metrics: Sequence[SequentialMetricResult],
    publication_blockers: list[str],
) -> dict[str, object]:
    zero_bound = next((metric.value for metric in metrics if metric.metric_name == "zero_false_positive_upper_bound"), 1.0)
    episode_fpr = next((metric.value for metric in metrics if metric.metric_name == "per_episode_false_positive_rate"), 1.0)
    supported = [alpha for alpha, payload in dataset.alpha_targets_supported.items() if payload.get("status") == "supported"]
    underpowered = [alpha for alpha, payload in dataset.alpha_targets_supported.items() if payload.get("status") != "supported"]
    return {
        "run_type": "main",
        "dataset_id": dataset.id,
        "synthetic_data_label": SYNTHETIC_MAIN_LABEL,
        "supported_alpha_levels": supported,
        "underpowered_alpha_levels": underpowered,
        "per_episode_fpr": episode_fpr,
        "zero_false_positive_upper_bound": zero_bound,
        "publication_claim_blocked": bool(publication_blockers),
        "publication_blockers": _unique(publication_blockers),
        "limitations": [
            "No synthetic main result establishes deployment validity.",
            "Powered alpha levels require enough negative traces and calibrated thresholds.",
            "Missing required baselines or calibration leakage block publication-readiness claims.",
        ],
    }


def _render_low_fpr_report(report: dict[str, Any]) -> str:
    lines = [
        "# Main Low-FPR Report",
        "",
        f"- Dataset ID: `{report['dataset_id']}`",
        f"- Supported alpha levels: {', '.join(report['supported_alpha_levels']) or 'none'}",
        f"- Underpowered alpha levels: {', '.join(report['underpowered_alpha_levels']) or 'none'}",
        f"- Per-episode FPR: {report['per_episode_fpr']:.6g}",
        f"- Zero-FP upper bound: {report['zero_false_positive_upper_bound']:.6g}",
        f"- Publication claim blocked: {str(report['publication_claim_blocked']).lower()}",
        "",
        "## Publication Blockers",
        "",
    ]
    lines.extend([f"- {blocker}" for blocker in report["publication_blockers"]] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in report["limitations"]])
    return "\n".join(lines).rstrip() + "\n"


def _unique(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
