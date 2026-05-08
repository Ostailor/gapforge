"""Experiment workspace scaffolding for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentRunManifest, ExperimentWorkspace, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaselineManager
from gapforge.selected_benchmark.metrics import SequentialMetricManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso

SMOKE_TRACE_COUNT = 100
PILOT_TRACE_COUNT = 1000
SELECTED_METRIC_IDS = [
    "per_step_false_positive_rate",
    "per_episode_false_positive_rate",
    "family_wise_false_alarm_probability",
    "time_to_detection",
    "detection_delay",
    "true_positive_rate_at_fixed_false_positive_budget",
    "specificity_at_alpha",
    "sequential_calibration_error",
    "abstention_uncertain_rate",
    "zero_false_positive_upper_bound",
]


@dataclass(slots=True)
class SelectedBenchmarkWorkspaceConfig:
    id: str
    workspace_id: str
    benchmark_id: str
    project_id: str
    smoke_trace_count: int = SMOKE_TRACE_COUNT
    pilot_trace_count: int = PILOT_TRACE_COUNT
    required_monitor_ids: list[str] = field(default_factory=lambda: ["monitor-random-detector", "monitor-frequency-threshold-detector"])
    result_parser: str = "gapforge.results.parser.ResultParser"
    report_generator: str = "gapforge.selected_benchmark.experiment.render_selected_benchmark_run_report"
    smoke_label: str = "synthetic_underpowered_smoke_only"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-workspace"))


class SelectedBenchmarkWorkspaceManager:
    """Create selected-benchmark workspaces and manifests on the experiment framework."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.metric_manager = SequentialMetricManager(config)

    def create_workspace(self, benchmark_id: str) -> ExperimentWorkspace:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        workspace = self.workspace_manager.create_workspace(
            project_id=spec.project_id,
            direction_id=f"selected-benchmark-{slugify(benchmark_id)}",
            campaign_id="v2.1-selected-idea-execution",
            experiment_protocol_id=f"protocol-{slugify(benchmark_id)}",
        )
        workspace_root = Path(workspace.root_dir)
        selected_config = SelectedBenchmarkWorkspaceConfig(
            id=f"selected-benchmark-workspace-{workspace.id}",
            workspace_id=workspace.id,
            benchmark_id=benchmark_id,
            project_id=spec.project_id,
            provenance=Provenance(
                created_by_skill="selected-benchmark-workspace",
                source_ids=[benchmark_id, spec.project_id, workspace.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Scaffolded a selected benchmark experiment workspace with smoke and pilot manifests.",
            ),
        )
        self._write_workspace_files(workspace, selected_config)
        baselines = self.baseline_manager.create_baselines(benchmark_id)
        metric_plan = self.metric_manager.create_plan(benchmark_id)
        workspace_root = Path(workspace.root_dir)
        (workspace_root / "baselines" / "monitor_baselines.json").write_text(
            json.dumps(to_plain(baselines), indent=2) + "\n",
            encoding="utf-8",
        )
        (workspace_root / "metrics" / "metric_plan.json").write_text(
            json.dumps(to_plain(metric_plan), indent=2) + "\n",
            encoding="utf-8",
        )
        self.create_manifest(workspace.id, run_type="smoke")
        self.create_manifest(workspace.id, run_type="pilot")
        return self.workspace_manager.load_workspace(workspace.id)

    def create_manifest(self, workspace_id: str, *, run_type: str) -> ExperimentRunManifest:
        if run_type not in {"smoke", "pilot"}:
            raise ValueError("Selected benchmark manifests support `smoke` and `pilot` run types.")
        workspace = self.workspace_manager.load_workspace(workspace_id)
        selected_config = self.load_config(workspace_id)
        existing = [manifest for manifest in self.workspace_manager.list_manifests(workspace_id) if manifest.run_type == run_type]
        if existing:
            return existing[-1]
        config_path = Path(workspace.root_dir) / "configs" / f"{run_type}_manifest_config.json"
        manifest_config = {
            "benchmark_id": selected_config.benchmark_id,
            "workspace_id": workspace_id,
            "run_type": run_type,
            "trace_count": selected_config.smoke_trace_count if run_type == "smoke" else selected_config.pilot_trace_count,
            "required_monitor_ids": selected_config.required_monitor_ids,
            "smoke_label": selected_config.smoke_label if run_type == "smoke" else "",
            "non_claim": "Smoke outputs validate the runnable path only and cannot support strong low-FPR claims.",
        }
        config_path.write_text(json.dumps(manifest_config, indent=2) + "\n", encoding="utf-8")
        return self.workspace_manager.create_manifest(
            workspace_id=workspace_id,
            run_type=run_type,
            run_name=f"Selected benchmark {run_type} run",
            dataset_ids=[f"selected-benchmark-{run_type}-synthetic-traces"],
            baseline_ids=selected_config.required_monitor_ids,
            metric_ids=SELECTED_METRIC_IDS,
            config_path=str(config_path),
            command=f"gapforge selected-benchmark-run --workspace-id {workspace_id} --run-type {run_type}",
            expected_outputs=[
                str(Path(workspace.root_dir) / "results" / f"{run_type}_metrics.json"),
                str(Path(workspace.root_dir) / "results" / f"{run_type}_summary.json"),
                str(Path(workspace.root_dir) / "reports" / f"{run_type}_report.md"),
            ],
        )

    def load_config(self, workspace_id: str) -> SelectedBenchmarkWorkspaceConfig:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        path = Path(workspace.root_dir) / "configs" / "selected_benchmark_workspace.json"
        if not path.exists():
            raise FileNotFoundError(f"No selected benchmark workspace config found for {workspace_id}")
        return from_dict(SelectedBenchmarkWorkspaceConfig, json.loads(path.read_text(encoding="utf-8")))

    def _write_workspace_files(self, workspace: ExperimentWorkspace, selected_config: SelectedBenchmarkWorkspaceConfig) -> None:
        root = Path(workspace.root_dir)
        (root / "configs" / "selected_benchmark_workspace.json").write_text(
            json.dumps(to_plain(selected_config), indent=2) + "\n",
            encoding="utf-8",
        )
        (root / "configs" / "trace_generator_smoke.json").write_text(
            json.dumps({"run_type": "smoke", "trace_count": selected_config.smoke_trace_count, "synthetic": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        (root / "configs" / "trace_generator_pilot.json").write_text(
            json.dumps({"run_type": "pilot", "trace_count": selected_config.pilot_trace_count, "synthetic": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        (root / "code" / "result_parser.py").write_text(
            '"""Use gapforge.results.parser.ResultParser on selected-benchmark execution artifacts."""\n',
            encoding="utf-8",
        )
        (root / "code" / "report_generator.py").write_text(
            '"""Use gapforge.selected_benchmark.experiment.render_selected_benchmark_run_report."""\n',
            encoding="utf-8",
        )
        (root / "README.md").write_text(render_selected_workspace_readme(selected_config), encoding="utf-8")


def render_selected_workspace_readme(config: SelectedBenchmarkWorkspaceConfig) -> str:
    return (
        f"# Selected Benchmark Workspace `{config.workspace_id}`\n\n"
        f"- Benchmark ID: `{config.benchmark_id}`\n"
        f"- Smoke trace count: {config.smoke_trace_count}\n"
        f"- Pilot trace count: {config.pilot_trace_count}\n"
        f"- Smoke label: `{config.smoke_label}`\n\n"
        "This workspace is a runnable benchmark scaffold for the selected v2.1 idea. "
        "Smoke outputs are synthetic, underpowered, and cannot support strong low-FPR or real-deployment claims.\n\n"
        "## Included Components\n\n"
        "- Trace generator config\n"
        "- Monitor baseline configs\n"
        "- Sequential metric plan\n"
        "- Smoke and pilot manifests\n"
        "- Result parser hook\n"
        "- Report generator hook\n"
    )
