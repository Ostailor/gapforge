"""Pilot manifest and execution path for the selected benchmark."""

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
from gapforge.selected_benchmark.baselines import MonitorBaselineManager, MonitorBaselineRun
from gapforge.selected_benchmark.metrics import SequentialMetricManager
from gapforge.selected_benchmark.pilot_power import PilotPowerManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso

SYNTHETIC_PILOT_LABEL = "synthetic_pilot_data"
REQUIRED_OUTPUT_KEYS = [
    "metrics_json",
    "predictions_json",
    "baseline_comparison",
    "error_analysis",
    "failures_json",
    "status_json",
]


@dataclass(slots=True)
class SelectedPilotRunManifest:
    id: str
    benchmark_id: str
    dataset_id: str
    baseline_monitor_ids: list[str] = field(default_factory=list)
    calibration_record_ids: list[str] = field(default_factory=list)
    metric_plan_id: str = ""
    random_seed: int = 0
    alpha_targets: list[str] = field(default_factory=list)
    expected_outputs: dict[str, str] = field(default_factory=dict)
    run_type: str = "pilot"
    synthetic_data_label: str = SYNTHETIC_PILOT_LABEL
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-pilot-run"))


@dataclass(slots=True)
class SelectedPilotExecution:
    id: str
    benchmark_id: str
    manifest_id: str
    dataset_id: str
    run_type: str
    status: str
    synthetic_data_label: str
    metric_result_count: int = 0
    monitor_run_ids: list[str] = field(default_factory=list)
    output_paths: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-pilot-run"))


class PilotRunManager:
    """Create and execute v2.2 selected-benchmark pilot manifests."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.metric_manager = SequentialMetricManager(config)
        self.power_manager = PilotPowerManager(config)

    def create_manifest(self, benchmark_id: str, dataset_id: str, *, random_seed: int = 20260221) -> SelectedPilotRunManifest:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        self._ensure_dataset_belongs_to_benchmark(dataset_id, benchmark_id)
        baselines = self.baseline_manager.load_baselines(benchmark_id) or self.baseline_manager.create_baselines(benchmark_id)
        monitor_ids = [baseline.id for baseline in baselines if _manifest_monitor(baseline)]
        calibration_record_ids = []
        for baseline in baselines:
            if baseline.id in monitor_ids and baseline.parameters.get("calibration_required"):
                record = self.baseline_manager.calibrate_monitor(
                    benchmark_id,
                    baseline.id,
                    target_alpha=float(baseline.parameters.get("target_alpha", 0.01)),
                )
                calibration_record_ids.append(record.id)
        metric_plan = self.metric_manager.create_plan(benchmark_id)
        power_plan = self.power_manager.create_plan(benchmark_id)
        manifest = SelectedPilotRunManifest(
            id=_short_pilot_id("selected-pilot-manifest", benchmark_id, dataset_id),
            benchmark_id=benchmark_id,
            dataset_id=dataset_id,
            baseline_monitor_ids=monitor_ids,
            calibration_record_ids=calibration_record_ids,
            metric_plan_id=metric_plan.id,
            random_seed=random_seed,
            alpha_targets=[f"{alpha:g}" for alpha in power_plan.target_alpha_levels],
            expected_outputs={key: f"pilot_runs/executions/<execution-id>/{key}.json" for key in REQUIRED_OUTPUT_KEYS},
            run_type="pilot",
            synthetic_data_label=SYNTHETIC_PILOT_LABEL,
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-run",
                source_ids=[benchmark_id, spec.project_id, dataset_id, metric_plan.id, power_plan.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a locked v2.2 pilot manifest with dataset, baselines, calibration, metrics, and alpha targets.",
            ),
        )
        self._write_json(self.manifest_path(manifest.id), manifest)
        return manifest

    def load_manifest(self, manifest_id: str) -> SelectedPilotRunManifest:
        path = self.manifest_path(manifest_id)
        return from_dict(SelectedPilotRunManifest, json.loads(path.read_text(encoding="utf-8")))

    def run(self, benchmark_id: str, manifest_id: str) -> SelectedPilotExecution:
        manifest = self.load_manifest(manifest_id)
        if manifest.benchmark_id != benchmark_id:
            raise ValueError(f"Manifest `{manifest_id}` belongs to benchmark `{manifest.benchmark_id}`, not `{benchmark_id}`.")
        execution_id = _short_pilot_id("selected-pilot-execution", manifest.id)
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
                failures.append(f"Required pilot monitor `{monitor_id}` is not registered.")
                continue
            try:
                run = self.baseline_manager._run_baseline_on_dataset(  # noqa: SLF001
                    benchmark_id,
                    baseline,
                    manifest.dataset_id,
                    run_label="pilot",
                )
                monitor_runs.append(run)
                predictions_by_monitor[monitor_id] = self._load_predictions(manifest.dataset_id, monitor_id)
            except Exception as exc:  # pragma: no cover - exercised through preserved failure shape
                failures.append(f"Required pilot monitor `{monitor_id}` failed: {exc}")
        metrics = []
        try:
            metrics = self.metric_manager.compute(manifest.dataset_id)
        except Exception as exc:  # pragma: no cover - defensive preservation path
            failures.append(f"Sequential metric computation failed: {exc}")
        output_paths = self._write_execution_artifacts(
            execution_dir=execution_dir,
            manifest=manifest,
            monitor_runs=monitor_runs,
            predictions_by_monitor=predictions_by_monitor,
            metrics=metrics,
            failures=failures,
        )
        execution = SelectedPilotExecution(
            id=execution_id,
            benchmark_id=benchmark_id,
            manifest_id=manifest.id,
            dataset_id=manifest.dataset_id,
            run_type="pilot",
            status="failed" if failures else "complete",
            synthetic_data_label=manifest.synthetic_data_label,
            metric_result_count=len(metrics),
            monitor_run_ids=[run.id for run in monitor_runs],
            output_paths=output_paths,
            failures=failures,
            warnings=[
                "Pilot run uses synthetic data and must not be reported as deployment or main-benchmark evidence.",
                "alpha=0.001 claims remain blocked unless the pilot dataset supports the main-scale negative count.",
            ],
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-run",
                source_ids=[benchmark_id, manifest.id, manifest.dataset_id, *[run.id for run in monitor_runs]],
                timestamp=utc_now_iso(),
                reasoning_summary="Executed a selected benchmark pilot manifest and preserved monitor/metric failures as run artifacts.",
            ),
        )
        self._write_json(execution_dir / "status_json.json", execution)
        self._write_json(execution_dir / "execution.json", execution)
        (execution_dir / "status.md").write_text(render_selected_pilot_status(execution), encoding="utf-8")
        return execution

    def status(self, execution_id: str) -> SelectedPilotExecution:
        path = self.execution_dir(execution_id) / "execution.json"
        if not path.exists():
            raise FileNotFoundError(f"No selected pilot execution `{execution_id}` found.")
        return from_dict(SelectedPilotExecution, json.loads(path.read_text(encoding="utf-8")))

    def manifest_path(self, manifest_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._pilot_root(project.id) / "manifests" / f"{manifest_id}.json"
            if path.exists():
                return path
        projects = self.project_manager.list_projects()
        if not projects:
            raise FileNotFoundError("No projects are available for selected pilot manifests.")
        return self._pilot_root(projects[-1].id) / "manifests" / f"{manifest_id}.json"

    def execution_dir(self, execution_id: str) -> Path:
        for project in self.project_manager.list_projects():
            path = self._pilot_root(project.id) / "executions" / execution_id
            if path.exists():
                return path
        projects = self.project_manager.list_projects()
        if not projects:
            raise FileNotFoundError("No projects are available for selected pilot executions.")
        return self._pilot_root(projects[-1].id) / "executions" / execution_id

    def _write_execution_artifacts(
        self,
        *,
        execution_dir: Path,
        manifest: SelectedPilotRunManifest,
        monitor_runs: list[MonitorBaselineRun],
        predictions_by_monitor: dict[str, list[dict[str, Any]]],
        metrics: Sequence[object],
        failures: list[str],
    ) -> dict[str, str]:
        comparison = _baseline_comparison(monitor_runs)
        error_analysis = _error_analysis(manifest, monitor_runs=monitor_runs, metrics=metrics, failures=failures)
        outputs = {
            "metrics_json": execution_dir / "metrics_json.json",
            "predictions_json": execution_dir / "predictions_json.json",
            "baseline_comparison": execution_dir / "baseline_comparison.json",
            "error_analysis": execution_dir / "error_analysis.json",
            "failures_json": execution_dir / "failures_json.json",
        }
        self._write_json(
            outputs["metrics_json"],
            {"run_type": "pilot", "synthetic_data_label": manifest.synthetic_data_label, "metrics": list(metrics)},
        )
        self._write_json(
            outputs["predictions_json"],
            {"run_type": "pilot", "synthetic_data_label": manifest.synthetic_data_label, "predictions_by_monitor": predictions_by_monitor},
        )
        self._write_json(outputs["baseline_comparison"], comparison)
        self._write_json(outputs["error_analysis"], error_analysis)
        self._write_json(outputs["failures_json"], {"run_type": "pilot", "failures": failures})
        outputs["status_json"] = execution_dir / "status_json.json"
        return {key: str(path) for key, path in outputs.items()}

    def _load_predictions(self, dataset_id: str, monitor_id: str) -> list[dict[str, Any]]:
        path = self._dataset_dir(dataset_id) / "monitor_predictions" / monitor_id / "predictions.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []

    def _ensure_dataset_belongs_to_benchmark(self, dataset_id: str, benchmark_id: str) -> None:
        traces = self.metric_manager.trace_generator.load_traces_for_dataset(dataset_id)
        if any(trace.benchmark_id != benchmark_id for trace in traces):
            raise ValueError(f"Dataset `{dataset_id}` contains traces outside benchmark `{benchmark_id}`.")

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

    def _pilot_root(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "pilot_runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_selected_pilot_status(execution: SelectedPilotExecution) -> str:
    lines = [
        f"# Selected Pilot Status `{execution.id}`",
        "",
        f"- Benchmark ID: `{execution.benchmark_id}`",
        f"- Manifest ID: `{execution.manifest_id}`",
        f"- Dataset ID: `{execution.dataset_id}`",
        f"- Run type: `{execution.run_type}`",
        f"- Synthetic data label: `{execution.synthetic_data_label}`",
        f"- Status: `{execution.status}`",
        f"- Metric results: {execution.metric_result_count}",
        f"- Monitor runs: {len(execution.monitor_run_ids)}",
        "",
        "## Outputs",
        "",
    ]
    lines.extend([f"- `{key}`: {path}" for key, path in sorted(execution.output_paths.items())] or ["- none"])
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in execution.failures] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in execution.warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _manifest_monitor(baseline: Any) -> bool:
    return bool(
        baseline.parameters.get("required", False)
        and baseline.parameters.get("ci_enabled", True)
        and not baseline.parameters.get("analysis_only", False)
        and not baseline.parameters.get("optional", False)
    )


def _short_pilot_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode()).hexdigest()[:12]
    readable = slugify(parts[-1])[:36] if parts else "pilot"
    return f"{prefix}-{readable}-{digest}"


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
                "run_type": "pilot",
            }
        )
    return {
        "run_type": "pilot",
        "comparison_scope": "synthetic pilot baseline comparison",
        "rows": rows,
        "limitations": [
            "Comparison is descriptive over synthetic pilot traces only.",
            "Threshold-calibrated monitors depend on honest/null calibration records.",
        ],
    }


def _error_analysis(
    manifest: SelectedPilotRunManifest,
    *,
    monitor_runs: list[MonitorBaselineRun],
    metrics: Sequence[object],
    failures: list[str],
) -> dict[str, object]:
    expected = set(manifest.baseline_monitor_ids)
    observed = {run.monitor_id for run in monitor_runs}
    missing = sorted(expected - observed)
    return {
        "run_type": "pilot",
        "synthetic_data_label": manifest.synthetic_data_label,
        "missing_monitor_outputs": missing,
        "failure_count": len(failures),
        "failures": failures,
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
            "Error analysis is pilot artifact triage, not a deployment failure taxonomy.",
            "Failures are preserved as first-class pilot outputs instead of being hidden by partial success.",
        ],
    }
