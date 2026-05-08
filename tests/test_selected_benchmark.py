from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaStore, IdeaTournamentRunner, SelectedIdeaProjectManager
from gapforge.ideas.models import IdeaScoreRecord, IdeaTournament
from gapforge.models import Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    MonitorBaselineManager,
    SelectedBenchmarkCodexTaskManager,
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkWorkspaceManager,
    SequentialMetricManager,
    SyntheticTraceGenerator,
)
from gapforge.selected_benchmark.power import zero_false_positive_upper_bound
from gapforge.state import ResearchStateManager

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"
SELECTED_IDEA_ID = "idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits"
SELECTED_TITLE = "Sequential specificity benchmark for low-FPR collusion audits"


def test_selected_benchmark_spec_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)

    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    spec_path = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir) / "selected_benchmark" / "spec.json"

    assert spec.id == "benchmark-sequential-specificity-benchmark-for-low-fpr-collusion-audits"
    assert spec.project_id == selected_project_id
    assert spec.target_fpr_levels == [0.1, 0.05, 0.01]
    assert {"transcript-visible", "action-only"}.issubset(set(spec.observability_modes))
    assert spec.honest_agent_distribution["required"] is True
    assert spec_path.exists()


def test_selected_benchmark_threat_model_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)

    threat_model = manager.create_threat_model(spec.id)

    assert threat_model.benchmark_id == spec.id
    assert threat_model.communication_allowed is True
    assert "transcript messages" in threat_model.observable_signals
    assert threat_model.honest_baseline_definition
    assert threat_model.collusive_behavior_definition


def test_selected_benchmark_task_families_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)

    families = manager.create_task_families(spec.id)
    task_types = {family.task_type for family in families}

    assert {"honest_null", "collusive_alternative", "observability_ablation"}.issubset(task_types)
    assert any("hard_negative" in family.labels for family in families)
    assert manager.load_spec(spec.id).task_families == [family.id for family in families]


def test_missing_honest_null_distribution_blocks_readiness(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)
    spec.honest_agent_distribution = {}
    manager._write_spec(spec)

    blockers = manager.readiness_blockers(manager.load_spec(spec.id))

    assert f"Benchmark `{spec.id}` is missing the honest-agent null distribution." in blockers


def test_selected_benchmark_report_renders_and_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    env = _env()
    spec_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-spec", "--project-id", selected_project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert spec_cli.returncode == 0, spec_cli.stderr
    benchmark_id = json.loads(spec_cli.stdout)["id"]
    threat_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "threat-model", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    tasks_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-task-families", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert threat_cli.returncode == 0, threat_cli.stderr
    assert tasks_cli.returncode == 0, tasks_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Selected Benchmark Report" in report_cli.stdout
    assert "Honest null distribution: present" in report_cli.stdout
    assert "Collusive alternative distribution: present" in report_cli.stdout
    assert "Readiness Blockers" in report_cli.stdout
    assert "- none" in report_cli.stdout


def test_synthetic_trace_generator_creates_smoke_trace_mix(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)
    generator = SyntheticTraceGenerator(config)

    dataset = generator.generate(spec.id, count=10, split="smoke")
    traces = generator.load_traces_for_dataset(dataset.id)

    assert dataset.split == "smoke"
    assert len(traces) == 10
    assert dataset.label_balance["honest"] > 0
    assert dataset.label_balance["collusive"] > 0
    assert {trace.observability_mode for trace in traces} == {"transcript_visible", "action_only"}
    assert all("synthetic" in trace.labels for trace in traces)
    assert all(trace.metadata["synthetic"] is True for trace in traces)
    assert any(trace.trace_type == "honest" and "benign_coordination" in trace.labels for trace in traces)
    assert any(trace.trace_type == "collusive" and "explicit_collusion" in trace.labels for trace in traces)
    assert any(trace.trace_type == "ambiguous" and trace.metadata["main_metric_eligible"] is False for trace in traces)


def test_synthetic_trace_cli_report_and_list_render(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()
    generate_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "generate-traces",
            "--benchmark-id",
            spec.id,
            "--count",
            "10",
            "--split",
            "smoke",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate_cli.returncode == 0, generate_cli.stderr
    dataset_id = json.loads(generate_cli.stdout)["id"]

    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "trace-dataset-report", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    list_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "trace-list", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report_cli.returncode == 0, report_cli.stderr
    assert list_cli.returncode == 0, list_cli.stderr
    assert "Trace Dataset Report" in report_cli.stdout
    assert "Synthetic label present: yes" in report_cli.stdout
    assert "Ambiguous traces are excluded from main metrics" in report_cli.stdout
    assert "not claims about real deployment behavior" in report_cli.stdout
    assert "Selected Benchmark Traces" in list_cli.stdout
    assert "transcript_visible" in list_cli.stdout
    assert "action_only" in list_cli.stdout


def test_sequential_metrics_compute_low_fpr_results(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    metric_manager = SequentialMetricManager(config)

    results = metric_manager.compute(dataset.id)
    by_name = {result.metric_name: result for result in results}

    assert by_name["per_step_false_positive_rate"].value == 0.0
    assert by_name["per_episode_false_positive_rate"].value == 0.0
    assert by_name["family_wise_false_alarm_probability"].value == 0.0
    assert by_name["true_positive_rate_at_fixed_false_positive_budget"].value == 1.0
    assert by_name["abstention_uncertain_rate"].value == 0.2
    assert by_name["per_episode_false_positive_rate"].confidence_interval


def test_zero_false_positive_upper_bound_and_underpowered_warning(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")

    results = SequentialMetricManager(config).compute(dataset.id)
    zero_bound = next(result for result in results if result.metric_name == "zero_false_positive_upper_bound")
    limitations = "\n".join(item for result in results for item in result.limitations)

    assert zero_bound.value == zero_false_positive_upper_bound(zero_bound.negative_trace_count)
    assert zero_bound.value > 0
    assert "underpowered" in limitations
    assert "Smoke results are underpowered" in limitations
    assert "Sequential multiple-testing warning" in limitations


def test_sequential_metric_plan_and_audit_cli_render(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    env = _env()

    plan_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "sequential-metric-plan", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    compute_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "compute-sequential-metrics", "--execution-id", dataset.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    audit_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "low-fpr-audit-check", "--execution-id", dataset.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert plan_cli.returncode == 0, plan_cli.stderr
    assert compute_cli.returncode == 0, compute_cli.stderr
    assert audit_cli.returncode == 0, audit_cli.stderr
    assert "Sequential Metric Plan" in plan_cli.stdout
    assert "Multiple Testing Notes" in plan_cli.stdout
    assert "exact/binomial confidence intervals" in plan_cli.stdout
    assert "per_episode_false_positive_rate" in compute_cli.stdout
    assert "zero_false_positive_upper_bound" in compute_cli.stdout
    assert "Low-FPR Audit Check" in audit_cli.stdout
    assert "Status: `underpowered`" in audit_cli.stdout
    assert "Smoke results cannot support strong low-FPR claims" in audit_cli.stdout


def test_monitor_baseline_random_and_threshold_run(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    manager = MonitorBaselineManager(config)
    baselines = manager.create_baselines(spec.id)

    random_run = manager.run_baseline(spec.id, "random")
    threshold_run = manager.run_baseline(spec.id, "threshold")

    assert len(baselines) >= 7
    assert random_run.prediction_count > 0
    assert threshold_run.prediction_count > 0
    assert random_run.monitor_id == "monitor-random-detector"
    assert threshold_run.monitor_id == "monitor-frequency-threshold-detector"


def test_monitor_baseline_modes_work(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    manager = MonitorBaselineManager(config)
    manager.create_baselines(spec.id)

    action_run = manager.run_baseline(spec.id, "repeated-action")
    transcript_run = manager.run_baseline(spec.id, "lexical")

    assert action_run.prediction_count > 0
    assert transcript_run.prediction_count > 0
    assert action_run.monitor_id == "monitor-repeated-action-detector"
    assert transcript_run.monitor_id == "monitor-lexical-overlap-detector"


def test_monitor_baseline_readiness_and_cli_report(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    manager = MonitorBaselineManager(config)

    assert "missing monitor baseline registry" in "\n".join(manager.readiness_blockers(spec.id))
    manager.create_baselines(spec.id)
    assert "no runnable baseline smoke predictions" in "\n".join(manager.readiness_blockers(spec.id))

    env = _env()
    random_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "run-monitor-baseline", "--benchmark-id", spec.id, "--monitor", "random"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "monitor-baseline-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    baseline_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-monitor-baselines", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert random_cli.returncode == 0, random_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert baseline_cli.returncode == 0, baseline_cli.stderr
    assert "monitor-random-detector" in random_cli.stdout
    assert "Monitor Baseline Report" in report_cli.stdout
    assert "LLM judge placeholder" in report_cli.stdout
    assert "Oracle upper-bound placeholder" in report_cli.stdout
    assert "must not be compared as a deployable monitor" in report_cli.stdout
    assert "random_detector" in baseline_cli.stdout


def test_selected_benchmark_workspace_created_with_manifests(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    root = Path(workspace.root_dir)
    manifests = {manifest.run_type for manifest in SelectedBenchmarkWorkspaceManager(config).workspace_manager.list_manifests(workspace.id)}

    assert workspace.status == "ready"
    assert (root / "README.md").exists()
    assert (root / "configs" / "trace_generator_smoke.json").exists()
    assert (root / "configs" / "trace_generator_pilot.json").exists()
    assert (root / "baselines" / "monitor_baselines.json").exists()
    assert (root / "metrics" / "metric_plan.json").exists()
    assert (root / "code" / "result_parser.py").exists()
    assert (root / "code" / "report_generator.py").exists()
    assert {"smoke", "pilot"}.issubset(manifests)


def test_selected_benchmark_smoke_manifest_cli_created(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    env = _env()

    manifest_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-manifest", "--workspace-id", workspace.id, "--run-type", "smoke"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert manifest_cli.returncode == 0, manifest_cli.stderr
    manifest = json.loads(manifest_cli.stdout)
    assert manifest["run_type"] == "smoke"
    assert "selected-benchmark-run" in manifest["command"]
    assert "smoke_metrics.json" in "\n".join(manifest["expected_outputs"])


def test_selected_benchmark_smoke_run_artifact_backed_and_parsed(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)

    run_result = SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")
    root = Path(SelectedBenchmarkWorkspaceManager(config).workspace_manager.load_workspace(workspace.id).root_dir)
    records = SelectedBenchmarkWorkspaceManager(config).workspace_manager.list_execution_records(workspace.id)

    assert run_result.execution_id
    assert run_result.metric_result_count > 0
    assert len(run_result.monitor_run_ids) >= 2
    assert "underpowered" in "\n".join(run_result.warnings)
    assert (root / "results" / "smoke_metrics.json").exists()
    assert (root / "results" / "smoke_summary.json").exists()
    assert (root / "reports" / "smoke_report.md").exists()
    assert (root / "reports" / f"result_summary_{run_result.execution_id}.json").exists()
    assert records[-1].status == "complete"
    assert records[-1].result_artifact_ids
    parsed_summary = json.loads((root / "reports" / f"result_summary_{run_result.execution_id}.json").read_text(encoding="utf-8"))
    assert any("underpowered" in limitation for limitation in parsed_summary["limitations"])
    assert "Smoke outputs cannot support strong low-FPR claims" in (root / "reports" / "smoke_report.md").read_text(encoding="utf-8")


def test_selected_benchmark_workspace_and_run_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    workspace_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-workspace", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert workspace_cli.returncode == 0, workspace_cli.stderr
    workspace_id = json.loads(workspace_cli.stdout)["id"]
    run_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-run", "--workspace-id", workspace_id, "--run-type", "smoke"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert run_cli.returncode == 0, run_cli.stderr
    run_payload = json.loads(run_cli.stdout)
    assert run_payload["run_type"] == "smoke"
    assert run_payload["metric_result_count"] > 0
    assert "synthetic_underpowered_smoke_only" == run_payload["smoke_label"]
    assert any("underpowered" in warning for warning in run_payload["warnings"])


def test_selected_benchmark_codex_task_pack_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = SelectedBenchmarkCodexTaskManager(config)

    task = manager.create_task(spec.id, "implement_sequential_metrics")
    task_dir = Path(task.task_dir)

    assert task.model == "gpt-5.4"
    assert task.task_type == "implement_sequential_metrics"
    assert task.benchmark_spec["id"] == spec.id
    assert task.threat_model["benchmark_id"] == spec.id
    assert "AgentTrace" in task.trace_schema
    assert any("Random detector" in item for item in task.baseline_requirements)
    assert "per-episode false positive rate" in task.metric_definitions
    assert "src/gapforge/selected_benchmark/metrics.py" in task.expected_files
    assert "Metrics must be computed from persisted synthetic traces and monitor predictions" in task.no_fake_results_rule
    assert (task_dir / "TASK.md").exists()
    assert (task_dir / "benchmark_spec.json").exists()
    assert (task_dir / "threat_model.json").exists()
    assert (task_dir / "trace_schema.json").exists()
    assert (task_dir / "baseline_requirements.json").exists()
    assert (task_dir / "metric_definitions.json").exists()
    assert (Path(task.code_workspace) / "README.md").exists()


def test_selected_benchmark_codex_invalid_outside_workspace_patch_rejected(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = SelectedBenchmarkCodexTaskManager(config)
    task = manager.create_task(spec.id, "implement_trace_generator")
    output = Path(task.outputs_dir) / "selected_benchmark_patch.json"
    output.write_text(
        json.dumps(
            {
                "smoke_tests": "passed",
                "results_source": "computed_from_predictions_traces",
                "files": [{"path": "../outside.py", "content": "print('bad')"}],
            }
        ),
        encoding="utf-8",
    )

    result = manager.import_outputs(task.id)

    assert result.status == "rejected"
    assert "../outside.py" in result.rejected_files
    assert any("task code workspace" in issue for issue in result.issues)


def test_selected_benchmark_codex_fake_result_patch_rejected(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = SelectedBenchmarkCodexTaskManager(config)
    task = manager.create_task(spec.id, "improve_benchmark_report")
    output = Path(task.outputs_dir) / "selected_benchmark_patch.json"
    output.write_text(
        json.dumps(
            {
                "smoke_tests": "passed",
                "results_source": "manual_fake_summary",
                "files": [
                    {
                        "path": "src/gapforge/selected_benchmark/report.py",
                        "content": "SUMMARY = 'Results show the monitor outperforms every baseline.'\n",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = manager.import_outputs(task.id)

    assert result.status == "rejected"
    assert result.rejected_files == ["src/gapforge/selected_benchmark/report.py"]
    assert any("results_source" in issue for issue in result.issues)
    assert any("fake or unsupported result claims" in issue for issue in result.issues)


def test_selected_benchmark_codex_valid_fixture_patch_imports(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = SelectedBenchmarkCodexTaskManager(config)
    task = manager.create_task(spec.id, "debug_selected_benchmark")
    output = Path(task.outputs_dir) / "selected_benchmark_patch.json"
    output.write_text(
        json.dumps(
            {
                "smoke_tests": "passed",
                "results_source": "computed_from_predictions_traces",
                "files": [
                    {
                        "path": "tests/test_selected_benchmark_fixture_note.py",
                        "content": "def test_fixture_note():\n    assert 'synthetic smoke wiring'\n",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = manager.import_outputs(task.id)
    imported = Path(task.code_workspace) / "imported" / "tests" / "test_selected_benchmark_fixture_note.py"

    assert result.status == "imported"
    assert result.imported_files == ["tests/test_selected_benchmark_fixture_note.py"]
    assert imported.exists()
    assert "synthetic smoke wiring" in imported.read_text(encoding="utf-8")


def test_selected_benchmark_codex_cli_roundtrip(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-benchmark-codex-task",
            "--benchmark-id",
            spec.id,
            "--type",
            "implement_sequential_metrics",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    task = json.loads(created.stdout)
    handoff = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-codex-handoff", "--task-id", task["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert handoff.returncode == 0, handoff.stderr
    assert f"selected-benchmark-codex-import --task-id {task['id']}" in handoff.stdout
    assert "Do not invent benchmark results" in handoff.stdout

    output = Path(task["outputs_dir"]) / "selected_benchmark_patch.json"
    output.write_text(
        json.dumps(
            {
                "smoke_tests": "passed",
                "results_source": "computed_from_predictions_traces",
                "files": [{"path": "docs/selected_benchmark_task_note.md", "content": "Smoke-safe implementation note.\n"}],
            }
        ),
        encoding="utf-8",
    )
    imported = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-codex-import", "--task-id", task["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert imported.returncode == 0, imported.stderr
    assert json.loads(imported.stdout)["status"] == "imported"


def test_selected_benchmark_review_missing_null_distribution_fatal(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    benchmark_manager = SelectedBenchmarkManager(config)
    spec = benchmark_manager.create_spec(selected_project_id)
    spec.honest_agent_distribution = {}
    benchmark_manager._write_spec(spec)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)

    assert any("Missing honest null distribution" in blocker for blocker in panel.fatal_blockers)
    assert panel.publishability_assessment == "not_publishable_fatal_blockers"


def test_selected_benchmark_review_underpowered_low_fpr_major_or_fatal(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=10, split="smoke")
    SequentialMetricManager(config).compute(dataset.id)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)
    stats_review = next(review for review in panel.reviewer_reports if review.role == "statistics/low-FPR reviewer")

    assert any("Underpowered low-FPR evidence" in flaw for flaw in stats_review.fatal_flaws)
    assert any("underpowered" in fix.lower() for fix in stats_review.required_fixes)
    assert panel.publishability_assessment == "not_publishable_fatal_blockers"


def test_selected_benchmark_review_missing_baseline_major(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)
    baseline_review = next(review for review in panel.reviewer_reports if review.role == "baseline/reproducibility reviewer")

    assert any("missing monitor baseline registry" in weakness for weakness in baseline_review.weaknesses)
    assert any("Register required baselines" in fix for fix in baseline_review.required_fixes)


def test_selected_benchmark_review_smoke_only_not_publishable(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")

    panel = SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)

    assert panel.publishability_assessment.startswith("not_publishable")
    assert any("Smoke-only result artifacts" in weakness for review in panel.reviewer_reports for weakness in review.weaknesses)
    assert any("Smoke fixtures validate benchmark wiring only." in limitation for limitation in panel.limitations)


def test_selected_benchmark_review_report_and_fix_list_render(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    review_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-review", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    fix_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-fix-list", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert review_cli.returncode == 0, review_cli.stderr
    assert fix_cli.returncode == 0, fix_cli.stderr
    panel = json.loads(review_cli.stdout)
    assert panel["benchmark_id"] == spec.id
    assert "benchmark validity reviewer" in {review["role"] for review in panel["reviewer_reports"]}
    assert "area chair" in {review["role"] for review in panel["reviewer_reports"]}
    assert "Selected Benchmark Fix List" in fix_cli.stdout
    assert "Prior-work recall evidence is missing" in fix_cli.stdout


def test_selected_benchmark_manuscript_package_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")
    manager = SelectedBenchmarkManuscriptManager(config)

    manuscript = manager.generate(spec.id)
    package = manager.paper_package(spec.id)

    assert Path(manuscript.manuscript_path).exists()
    assert set(manuscript.sections) == {
        "problem motivation",
        "related work",
        "benchmark definition",
        "threat model",
        "sequential specificity metrics",
        "synthetic smoke setup",
        "baselines",
        "limitations",
        "path to pilot/main benchmark",
        "reviewer concerns",
    }
    assert "manuscript.md" in package.files
    assert "reviewer_blockers.md" in package.files
    assert Path(package.package_dir, "paper_package.json").exists()


def test_selected_benchmark_manuscript_smoke_labels_and_limitations(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")

    manuscript = SelectedBenchmarkManuscriptManager(config).generate(spec.id)
    text = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert "[SMOKE]" in text
    assert "Only synthetic traces exist: true" in text
    assert "Smoke results are labeled smoke" in text
    assert "It does not claim deployment validity." in text
    assert "Prominent Limitations" in text
    assert "Synthetic traces do not represent real deployment behavior." in text


def test_selected_benchmark_manuscript_fake_result_not_included(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    report_dir = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir) / "selected_benchmark" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "fake_result_claim.md").write_text("Results show the monitor outperforms all baselines.\n", encoding="utf-8")

    manuscript = SelectedBenchmarkManuscriptManager(config).generate(spec.id)
    text = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert "outperforms all baselines" not in text
    assert "Results show" not in text
    assert "No metric results are available" in text


def test_selected_benchmark_manuscript_reviewer_blockers_included(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")

    manuscript = SelectedBenchmarkManuscriptManager(config).generate(spec.id)
    text = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert "Reviewer Blockers" in text
    assert "Underpowered low-FPR evidence cannot support pilot/main or publication claims." in text
    assert "Run or attach prior-work recall before making novelty claims." in text
    assert "does not claim final benchmark contribution status" in text


def test_selected_benchmark_manuscript_cli_roundtrip(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")
    env = _env()

    manuscript_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-manuscript", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    package_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-paper-package", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert manuscript_cli.returncode == 0, manuscript_cli.stderr
    assert package_cli.returncode == 0, package_cli.stderr
    manuscript = json.loads(manuscript_cli.stdout)
    package = json.loads(package_cli.stdout)
    assert Path(manuscript["manuscript_path"]).exists()
    assert "review_panel.md" in package["files"]


def test_selected_idea_dashboard_and_full_report_pages(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)
    manager.create_threat_model(spec.id)
    manager.create_task_families(spec.id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")
    SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)
    SelectedBenchmarkManuscriptManager(config).paper_package(spec.id)
    env = _env()

    dashboard_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "dashboard",
            "--project-id",
            selected_project_id,
            "--include-selected-idea",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-idea-full-report", "--project-id", selected_project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    dashboard_root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir) / "dashboard"
    for name in [
        "selected_idea.html",
        "benchmark_spec.html",
        "threat_model.html",
        "trace_dataset.html",
        "monitors.html",
        "sequential_metrics.html",
        "smoke_results.html",
        "reviewer_blockers.html",
        "selected_manuscript.html",
        "v21_release_gate.html",
    ]:
        assert (dashboard_root / name).exists()

    assert dashboard_cli.returncode == 0, dashboard_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Smoke / Pilot / Main Status" in (dashboard_root / "smoke_results.html").read_text(encoding="utf-8")
    assert "synthetic_underpowered_smoke_only" in (dashboard_root / "smoke_results.html").read_text(encoding="utf-8")
    assert "Pilot" in (dashboard_root / "smoke_results.html").read_text(encoding="utf-8")
    assert "Main" in (dashboard_root / "smoke_results.html").read_text(encoding="utf-8")
    assert "Underpowered low-FPR evidence" in (dashboard_root / "reviewer_blockers.html").read_text(encoding="utf-8")
    assert "Smoke outputs are synthetic, underpowered" in report_cli.stdout
    assert "## v2.1 Release Gate" in report_cli.stdout
    assert (
        Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)
        / "selected_benchmark"
        / "reports"
        / "selected_idea_full_report.md"
    ).exists()


def _selected_project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("v2 low-FPR collusion idea pilot", description=LOW_FPR_TOPIC)
    project_manager.save_project(program)
    _attach_run(config, program.project.id, [Paper(id="paper-prior", title="Prior low-FPR monitor", authors=[], abstract="", year=2025)])
    selected = _candidate(config, program.project.id)
    IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="human", rationale="Accepted candidate.")
    IdeaTournamentRunner(config).run(program.project.id, top_k=5)
    selected_project = SelectedIdeaProjectManager(config).create_selected_project(selected.id)
    return config, selected_project.project_id


def _candidate(config: GapForgeConfig, project_id: str):
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-low-fpr",
        title=SELECTED_TITLE,
        summary="A benchmark candidate for low false-positive collusion audit execution.",
        contribution_type="benchmark",
        core_claim="Sequential audit specificity should be benchmarked before operational monitor claims.",
        proposed_experiment="Run monitors on honest and collusive multi-agent traces.",
        expected_baselines=["rule monitor", "sequential threshold monitor"],
        expected_metrics=["specificity", "family-wise false-alarm probability"],
        closest_prior_work_ids=["paper-prior"],
        novelty_status="plausible",
        tractability_score=0.8,
        impact_score=0.85,
        evidence_score=0.7,
        reviewer_risk_score=0.2,
        idea_yield_score=0.9,
        maturity="candidate",
    )
    generated_id = candidate.id
    state = store.load_state(project_id)
    candidate.id = SELECTED_IDEA_ID
    state.idea_bank.candidate_ids = [SELECTED_IDEA_ID if item == generated_id else item for item in state.idea_bank.candidate_ids]
    state.candidates[-1] = candidate
    state.tournaments.append(
        IdeaTournament(
            id="tournament-selected-benchmark",
            project_id=project_id,
            candidate_ids=[candidate.id],
            score_records=[IdeaScoreRecord(idea_id=candidate.id, total_score=0.82, blockers=[])],
            selected_candidate_id=candidate.id,
            provenance=candidate.provenance,
        )
    )
    state.idea_bank.selected_candidate_id = candidate.id
    store._save_state(project_id, state)
    return candidate


def _attach_run(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
