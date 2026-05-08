"""Runnable selected-benchmark experiment smoke path."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import Provenance, to_plain
from gapforge.results.parser import ResultParser
from gapforge.selected_benchmark.baselines import MonitorBaselineManager, MonitorBaselineRun
from gapforge.selected_benchmark.metrics import SequentialMetricManager, SequentialMetricResult
from gapforge.selected_benchmark.trace_generator import SyntheticTraceGenerator, TraceDataset
from gapforge.selected_benchmark.workspace import SelectedBenchmarkWorkspaceManager
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class SelectedBenchmarkRunResult:
    id: str
    workspace_id: str
    benchmark_id: str
    run_type: str
    dataset_id: str
    execution_id: str
    metric_result_count: int
    monitor_run_ids: list[str] = field(default_factory=list)
    result_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    smoke_label: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-experiment"))


class SelectedBenchmarkExperimentRunner:
    """Run selected benchmark smoke/pilot manifests through artifact-backed execution records."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.selected_workspace_manager = SelectedBenchmarkWorkspaceManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.metric_manager = SequentialMetricManager(config)
        self.result_parser = ResultParser(config)

    def run(self, workspace_id: str, *, run_type: str) -> SelectedBenchmarkRunResult:
        if run_type not in {"smoke", "pilot"}:
            raise ValueError("Selected benchmark runs support `smoke` and `pilot` run types.")
        workspace = self.workspace_manager.load_workspace(workspace_id)
        selected_config = self.selected_workspace_manager.load_config(workspace_id)
        manifest = self.selected_workspace_manager.create_manifest(workspace_id, run_type=run_type)
        trace_count = selected_config.smoke_trace_count if run_type == "smoke" else selected_config.pilot_trace_count
        dataset = self.trace_generator.generate(selected_config.benchmark_id, count=trace_count, split=run_type)
        self.baseline_manager.create_baselines(selected_config.benchmark_id)
        monitor_runs = [
            self.baseline_manager.run_baseline(selected_config.benchmark_id, monitor_id)
            for monitor_id in selected_config.required_monitor_ids
        ]
        metrics = self.metric_manager.compute(dataset.id)
        audit_report = self.metric_manager.render_low_fpr_audit_check(dataset.id)
        result_paths = self._write_result_artifacts(
            workspace_root=Path(workspace.root_dir),
            run_type=run_type,
            dataset=dataset,
            monitor_runs=monitor_runs,
            metrics=metrics,
            audit_report=audit_report,
            smoke_label=selected_config.smoke_label if run_type == "smoke" else "",
        )
        warnings = _warnings(metrics, run_type=run_type)
        execution = self.workspace_manager.record_execution(
            workspace_id=workspace_id,
            manifest_id=manifest.id,
            status="complete",
            command=f"gapforge selected-benchmark-run --workspace-id {workspace_id} --run-type {run_type}",
            returncode=0,
            stdout_text=(
                f"Generated selected benchmark {run_type} dataset `{dataset.id}` with {len(dataset.trace_ids)} traces.\n"
                f"Computed {len(metrics)} sequential metrics.\n" + "\n".join(warnings) + "\n"
            ),
            stderr_text="",
            result_paths=result_paths,
        )
        self.result_parser.parse_execution(execution.id)
        run_result = SelectedBenchmarkRunResult(
            id=f"selected-benchmark-run-{execution.id}",
            workspace_id=workspace_id,
            benchmark_id=selected_config.benchmark_id,
            run_type=run_type,
            dataset_id=dataset.id,
            execution_id=execution.id,
            metric_result_count=len(metrics),
            monitor_run_ids=[run.id for run in monitor_runs],
            result_paths=[str(path) for path in result_paths],
            warnings=warnings,
            smoke_label=selected_config.smoke_label if run_type == "smoke" else "",
            provenance=Provenance(
                created_by_skill="selected-benchmark-experiment",
                source_ids=[workspace_id, selected_config.benchmark_id, dataset.id, execution.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Ran an artifact-backed selected benchmark smoke/pilot path through the experiment workspace framework.",
            ),
        )
        run_result_path = Path(workspace.root_dir) / "results" / f"{run_type}_run_result.json"
        run_result_path.write_text(json.dumps(to_plain(run_result), indent=2) + "\n", encoding="utf-8")
        return run_result

    def _write_result_artifacts(
        self,
        *,
        workspace_root: Path,
        run_type: str,
        dataset: TraceDataset,
        monitor_runs: list[MonitorBaselineRun],
        metrics: list[SequentialMetricResult],
        audit_report: str,
        smoke_label: str,
    ) -> list[Path]:
        results_dir = workspace_root / "results"
        reports_dir = workspace_root / "reports"
        results_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = results_dir / f"{run_type}_metrics.json"
        summary_path = results_dir / f"{run_type}_summary.json"
        report_path = reports_dir / f"{run_type}_report.md"
        metrics_path.write_text(json.dumps(_metrics_payload(dataset, metrics), indent=2) + "\n", encoding="utf-8")
        warnings = _warnings(metrics, run_type=run_type)
        summary_path.write_text(
            json.dumps(
                {
                    "benchmark_id": dataset.benchmark_id,
                    "dataset_id": dataset.id,
                    "run_type": run_type,
                    "trace_count": len(dataset.trace_ids),
                    "monitor_run_ids": [run.id for run in monitor_runs],
                    "metric_result_count": len(metrics),
                    "warnings": warnings,
                    "smoke_label": smoke_label,
                    "artifact_backed": True,
                    "limitations": dataset.limitations,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            render_selected_benchmark_run_report(
                dataset=dataset,
                monitor_runs=monitor_runs,
                metrics=metrics,
                audit_report=audit_report,
                run_type=run_type,
                smoke_label=smoke_label,
            ),
            encoding="utf-8",
        )
        return [metrics_path, summary_path, report_path]


def render_selected_benchmark_run_report(
    *,
    dataset: TraceDataset,
    monitor_runs: list[MonitorBaselineRun],
    metrics: list[SequentialMetricResult],
    audit_report: str,
    run_type: str,
    smoke_label: str,
) -> str:
    lines = [
        f"# Selected Benchmark {run_type.title()} Run",
        "",
        f"- Benchmark ID: `{dataset.benchmark_id}`",
        f"- Dataset ID: `{dataset.id}`",
        f"- Trace count: {len(dataset.trace_ids)}",
        f"- Monitor runs: {len(monitor_runs)}",
        f"- Metric results: {len(metrics)}",
        f"- Smoke label: `{smoke_label or 'not-smoke'}`",
        "",
        "## Monitor Runs",
        "",
    ]
    for run in monitor_runs:
        lines.append(f"- `{run.monitor_id}`: {run.prediction_count} predictions, {run.alert_count} alerts")
    lines.extend(["", "## Sequential Metrics", ""])
    for metric in metrics:
        lines.append(f"- `{metric.metric_name}`: {metric.value:.6g}, sample size {metric.sample_size}")
    lines.extend(["", "## Low-FPR Audit", "", audit_report.strip(), "", "## Non-Claims", ""])
    lines.extend(
        [
            "- Smoke outputs are synthetic and underpowered.",
            "- Smoke outputs cannot support strong low-FPR claims.",
            "- Synthetic traces do not represent real deployment behavior.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _metrics_payload(dataset: TraceDataset, metrics: list[SequentialMetricResult]) -> dict[str, object]:
    limitations = _warnings(metrics, run_type=dataset.split)
    return {
        "dataset_id": dataset.id,
        "split": dataset.split,
        "metadata": {
            "benchmark_id": dataset.benchmark_id,
            "synthetic": True,
            "smoke_underpowered": dataset.split == "smoke",
        },
        "limitations": limitations,
        "metric_results": [
            {
                "metric_id": metric.metric_name,
                "value": metric.value,
                "confidence_interval": metric.confidence_interval,
                "sample_size": metric.sample_size,
                "dataset_id": dataset.id,
                "baseline_id": "selected-monitor-baselines",
                "split": dataset.split,
                "limitations": limitations,
            }
            for metric in metrics
        ],
    }


def _warnings(metrics: list[SequentialMetricResult], *, run_type: str) -> list[str]:
    warnings: list[str] = []
    if run_type == "smoke":
        warnings.append("Smoke outputs are underpowered and cannot support strong low-FPR claims.")
    for metric in metrics:
        for limitation in metric.limitations:
            if ("underpowered" in limitation or "Sequential multiple-testing" in limitation) and limitation not in warnings:
                warnings.append(limitation)
    return warnings
