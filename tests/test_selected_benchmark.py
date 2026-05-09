from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaFeedbackManager, IdeaStore, IdeaTournamentRunner, SelectedIdeaProjectManager
from gapforge.ideas.models import IdeaScoreRecord, IdeaTournament
from gapforge.models import Paper, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    CollusiveAlternativeManager,
    HonestNullManager,
    MonitorBaselineManager,
    PilotAnalysisManager,
    PilotDatasetBuilder,
    PilotPowerManager,
    PilotRunManager,
    SelectedBenchmarkCodexTaskManager,
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkRelatedWorkManager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkWorkspaceManager,
    SelectedPilotManuscriptManager,
    SequentialMetricManager,
    SyntheticTraceGenerator,
)
from gapforge.selected_benchmark.collusive_alternatives import render_collusive_distribution_report
from gapforge.selected_benchmark.honest_null import render_honest_null_report
from gapforge.selected_benchmark.pilot_analysis import render_selected_pilot_report
from gapforge.selected_benchmark.pilot_dataset import render_pilot_trace_dataset_report
from gapforge.selected_benchmark.pilot_power import render_pilot_power_assessment
from gapforge.selected_benchmark.pilot_run import render_selected_pilot_status
from gapforge.selected_benchmark.power import zero_false_positive_upper_bound
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES, render_novelty_positioning
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


def test_honest_null_scenarios_generated_with_hard_negatives(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    scenarios = HonestNullManager(config).create_scenarios(spec.id)
    coordination_types = {scenario.coordination_type for scenario in scenarios}

    assert {
        "independent",
        "benign_parallel_strategy",
        "shared_context",
        "role_specialization",
        "repeated_convention",
        "tool_induced_similarity",
        "accidental_correlation",
    }.issubset(coordination_types)
    assert any("hard_negative" in scenario.generation_parameters.get("labels", []) for scenario in scenarios)
    assert any(scenario.false_positive_risk == "high" for scenario in scenarios)
    assert all(scenario.provenance.created_by_skill == "selected-benchmark-honest-null" for scenario in scenarios)


def test_generate_honest_null_traces_cover_modes_and_limitations(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = HonestNullManager(config)
    manager.create_scenarios(spec.id)

    dataset = manager.generate(spec.id, count=42)
    traces = SyntheticTraceGenerator(config).load_traces_for_dataset(dataset.id)

    assert dataset.split == "pilot_honest_null"
    assert len(traces) == 42
    assert dataset.label_balance["honest"] == 42
    assert dataset.label_balance["hard_negative"] > 0
    assert dataset.label_balance["transcript_visible"] > 0
    assert dataset.label_balance["action_only"] > 0
    assert {trace.trace_type for trace in traces} == {"honest"}
    assert {trace.observability_mode for trace in traces} == {"transcript_visible", "action_only"}
    assert all("synthetic" in trace.labels for trace in traces)
    assert all(trace.metadata["synthetic"] is True for trace in traces)
    assert any("Synthetic honest-null traces" in limitation for limitation in dataset.limitations)


def test_honest_null_report_renders_and_warns_for_insufficient_hard_negatives(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = HonestNullManager(config)
    manager.create_scenarios(spec.id)
    manager.generate(spec.id, count=12)

    report = manager.report(spec.id)
    rendered = render_honest_null_report(report)

    assert report.benchmark_id == spec.id
    assert report.trace_count == 12
    assert report.hard_negative_count > 0
    assert "hard negatives are underrepresented" in "\n".join(report.limitations)
    assert "Honest Null Distribution Report" in rendered
    assert "Synthetic limitations remain visible" in rendered
    assert "insufficient hard negatives" in rendered


def test_honest_null_cli_roundtrip(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    scenarios_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "honest-null-scenarios", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    generate_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "generate-honest-null", "--benchmark-id", spec.id, "--count", "42"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "honest-null-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert scenarios_cli.returncode == 0, scenarios_cli.stderr
    assert generate_cli.returncode == 0, generate_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "repeated_convention" in scenarios_cli.stdout
    assert json.loads(generate_cli.stdout)["label_balance"]["honest"] == 42
    assert "Honest Null Distribution Report" in report_cli.stdout
    assert "action-only hard negatives" in report_cli.stdout


def test_collusive_scenarios_generated_with_multiple_types(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    scenarios = CollusiveAlternativeManager(config).create_scenarios(spec.id)
    collusion_types = {scenario.collusion_type for scenario in scenarios}
    modes = {scenario.observability_mode for scenario in scenarios}
    difficulties = {scenario.difficulty for scenario in scenarios}

    assert {
        "explicit_coordination",
        "covert_channel",
        "lexical_signal",
        "timing_signal",
        "role_based_collusion",
        "reward_sharing",
        "adversarial_decoy",
    }.issubset(collusion_types)
    assert {"transcript_visible", "action_only"}.issubset(modes)
    assert {"easy", "hard"}.issubset(difficulties)
    assert all(scenario.provenance.created_by_skill == "selected-benchmark-collusive-alternatives" for scenario in scenarios)


def test_generate_collusive_traces_cover_modes_difficulty_and_labels(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = CollusiveAlternativeManager(config)
    manager.create_scenarios(spec.id)

    dataset = manager.generate(spec.id, count=49)
    traces = SyntheticTraceGenerator(config).load_traces_for_dataset(dataset.id)

    assert dataset.split == "pilot_collusive_alternatives"
    assert len(traces) == 49
    assert dataset.label_balance["collusive"] == 49
    assert dataset.label_balance["transcript_visible"] > 0
    assert dataset.label_balance["action_only"] > 0
    assert dataset.label_balance["hard"] > 0
    assert dataset.label_balance["easy"] > 0
    assert {trace.trace_type for trace in traces} == {"collusive"}
    assert {trace.observability_mode for trace in traces} == {"transcript_visible", "action_only"}
    assert any(trace.metadata["collusion_type"] == "adversarial_decoy" for trace in traces)
    assert all("synthetic" in trace.labels for trace in traces)
    assert all("collusive" in trace.labels for trace in traces)
    assert any("Synthetic collusive alternatives" in limitation for limitation in dataset.limitations)


def test_collusive_distribution_report_renders_difficulty_mix(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = CollusiveAlternativeManager(config)
    manager.create_scenarios(spec.id)
    manager.generate(spec.id, count=49)

    report = manager.report(spec.id)
    rendered = render_collusive_distribution_report(report)

    assert report.benchmark_id == spec.id
    assert report.trace_count == 49
    assert report.difficulty_mix["easy"] > 0
    assert report.difficulty_mix["hard"] > 0
    assert "Alternative limitations are explicit" in rendered
    assert "does not claim coverage of all collusion behavior" in "\n".join(report.limitations)
    assert "Collusive Distribution Report" in rendered


def test_collusive_alternative_cli_roundtrip(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    scenarios_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "collusive-scenarios", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    generate_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "generate-collusive-traces", "--benchmark-id", spec.id, "--count", "49"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "collusive-distribution-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert scenarios_cli.returncode == 0, scenarios_cli.stderr
    assert generate_cli.returncode == 0, generate_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "covert_channel" in scenarios_cli.stdout
    assert json.loads(generate_cli.stdout)["label_balance"]["collusive"] == 49
    assert "Collusive Distribution Report" in report_cli.stdout
    assert "Difficulty Mix" in report_cli.stdout


def test_pilot_trace_dataset_built_with_counts_and_alpha_support(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=150)

    assert dataset.benchmark_id == spec.id
    assert dataset.split == "pilot"
    assert dataset.negative_count == 300
    assert dataset.positive_count == 150
    assert len(dataset.honest_trace_ids) == 300
    assert len(dataset.collusive_trace_ids) == 150
    assert dataset.hard_negative_count > 0
    assert dataset.observability_mode_counts["transcript_visible"] > 0
    assert dataset.observability_mode_counts["action_only"] > 0
    assert dataset.alpha_targets_supported["0.01"]["status"] == "supported"
    assert dataset.alpha_targets_supported["0.001"]["status"] == "underpowered"
    assert "Synthetic pilot dataset" in "\n".join(dataset.limitations)
    assert dataset.provenance.created_by_skill == "selected-benchmark-pilot-dataset"


def test_pilot_trace_dataset_blocks_underpowered_negative_count(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=60, positive_count=150)

    assert dataset.negative_count == 60
    assert dataset.alpha_targets_supported["0.01"]["status"] == "underpowered"
    assert any("blocks pilot alpha=0.01" in limitation for limitation in dataset.limitations)


def test_pilot_trace_dataset_warns_on_low_positive_count_and_excludes_ambiguous(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=20)

    assert dataset.positive_count == 20
    assert dataset.ambiguous_trace_ids == []
    assert any("Positive trace count is below" in limitation for limitation in dataset.limitations)
    assert any("Ambiguous traces are excluded from primary metrics" in limitation for limitation in dataset.limitations)


def test_pilot_trace_dataset_report_and_card_render(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    builder = PilotDatasetBuilder(config)
    dataset = builder.build(spec.id, negative_count=300, positive_count=150)

    report = builder.report(dataset.id)
    rendered = render_pilot_trace_dataset_report(report)
    project_root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)

    assert report.id == dataset.id
    assert "Pilot Trace Dataset Report" in rendered
    assert "alpha=0.01: supported" in rendered
    assert "alpha=0.001: underpowered" in rendered
    assert "Synthetic/pilot status" in rendered
    assert (project_root / "selected_benchmark" / "pilot_dataset" / "dataset_card.md").exists()
    assert "Dataset Card" in (project_root / "selected_benchmark" / "pilot_dataset" / "dataset_card.md").read_text(encoding="utf-8")


def test_pilot_trace_dataset_cli_roundtrip(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    env = _env()

    build_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "build-pilot-trace-dataset",
            "--benchmark-id",
            spec.id,
            "--negative-count",
            "300",
            "--positive-count",
            "150",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build_cli.returncode == 0, build_cli.stderr
    dataset_id = json.loads(build_cli.stdout)["id"]
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "pilot-trace-dataset-report", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report_cli.returncode == 0, report_cli.stderr
    assert "Pilot Trace Dataset Report" in report_cli.stdout
    assert "alpha=0.01: supported" in report_cli.stdout


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


def test_monitor_calibration_record_created(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    HonestNullManager(config).generate(spec.id, count=120)
    manager = MonitorBaselineManager(config)
    manager.create_baselines(spec.id)

    record = manager.calibrate_monitor(spec.id, "threshold", target_alpha=0.01)

    assert record.monitor_id == "monitor-frequency-threshold-detector"
    assert record.calibration_dataset_id == f"trace-dataset-pilot-honest-null-{spec.id}"
    assert record.target_alpha == 0.01
    assert 0.0 <= record.threshold <= 1.0
    assert 0.0 <= record.observed_fpr <= 1.0
    assert record.confidence_interval["observed_negative_count"] == 120


def test_pilot_baseline_required_suite_runs_and_reports(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    required_for_pilot = PilotPowerManager(config).create_plan(spec.id).negative_trace_requirements["0.01"]
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=required_for_pilot, positive_count=100)
    manager = MonitorBaselineManager(config)
    manager.create_baselines(spec.id)

    runs = manager.run_pilot_baselines(spec.id, dataset.id)
    report = manager.render_pilot_report(spec.id)

    run_ids = {run.monitor_id for run in runs}
    assert "monitor-random-detector" in run_ids
    assert "monitor-frequency-threshold-detector" in run_ids
    assert "monitor-statistical-anomaly-detector" in run_ids
    assert "monitor-action-only-heuristic-monitor" in run_ids
    assert any(run.monitor_id == "monitor-action-only-heuristic-monitor" and run.prediction_count > 0 for run in runs)
    assert "Pilot Baseline Report" in report
    assert "Optional LLM judge baseline is not required for CI or pilot readiness." in report


def test_pilot_baseline_missing_required_blocks(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = MonitorBaselineManager(config)
    baselines = [baseline for baseline in manager.create_baselines(spec.id) if baseline.baseline_type != "statistical_anomaly_detector"]
    project_root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)
    registry_path = project_root / "selected_benchmark" / "monitor_baselines.json"
    registry_path.write_text(json.dumps(to_plain(baselines), indent=2) + "\n", encoding="utf-8")

    blockers = manager.pilot_readiness_blockers(spec.id)

    assert any("missing required pilot baseline type `statistical_anomaly_detector`" in blocker for blocker in blockers)


def test_monitor_calibration_leakage_warning(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=60, positive_count=30)
    manager = MonitorBaselineManager(config)
    manager.create_baselines(spec.id)

    record = manager.calibrate_monitor(
        spec.id,
        "anomaly",
        target_alpha=0.01,
        calibration_dataset_id=dataset.id,
    )

    joined = "\n".join(record.warnings)
    assert "Calibration data leakage" in joined
    assert "collusive traces" in joined


def test_pilot_baseline_cli_commands(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    env = _env()

    calibration_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "calibrate-monitor",
            "--benchmark-id",
            spec.id,
            "--monitor",
            "threshold",
            "--target-alpha",
            "0.01",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    run_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "run-pilot-baselines",
            "--benchmark-id",
            spec.id,
            "--dataset-id",
            dataset.id,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "pilot-baseline-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert calibration_cli.returncode == 0, calibration_cli.stderr
    assert run_cli.returncode == 0, run_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "monitor-frequency-threshold-detector" in calibration_cli.stdout
    assert "monitor-action-only-heuristic-monitor" in run_cli.stdout
    assert "Pilot Baseline Report" in report_cli.stdout


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


def test_selected_pilot_manifest_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)

    manifest = PilotRunManager(config).create_manifest(spec.id, dataset.id)

    assert manifest.benchmark_id == spec.id
    assert manifest.dataset_id == dataset.id
    assert manifest.run_type == "pilot"
    assert manifest.synthetic_data_label == "synthetic_pilot_data"
    assert "monitor-random-detector" in manifest.baseline_monitor_ids
    assert "monitor-action-only-heuristic-monitor" in manifest.baseline_monitor_ids
    assert manifest.calibration_record_ids
    assert "0.01" in manifest.alpha_targets
    assert "metrics_json" in manifest.expected_outputs


def test_selected_pilot_run_executes_on_fixture_data(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    manager = PilotRunManager(config)
    manifest = manager.create_manifest(spec.id, dataset.id)

    execution = manager.run(spec.id, manifest.id)

    assert execution.run_type == "pilot"
    assert execution.status == "complete"
    assert execution.metric_result_count > 0
    assert execution.monitor_run_ids
    assert not execution.failures
    for key in ["metrics_json", "predictions_json", "baseline_comparison", "error_analysis"]:
        assert Path(execution.output_paths[key]).exists()
    status = render_selected_pilot_status(execution)
    assert "Run type: `pilot`" in status


def test_selected_pilot_failures_preserved(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    manager = PilotRunManager(config)
    manifest = manager.create_manifest(spec.id, dataset.id)
    manifest_path = manager.manifest_path(manifest.id)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["baseline_monitor_ids"].append("monitor-missing-required-baseline")
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    execution = manager.run(spec.id, manifest.id)

    assert execution.status == "failed"
    assert any("monitor-missing-required-baseline" in failure for failure in execution.failures)
    assert Path(execution.output_paths["failures_json"]).exists()
    assert Path(execution.output_paths["metrics_json"]).exists()


def test_selected_pilot_cli_manifest_run_status(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    env = _env()

    manifest_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-pilot-manifest",
            "--benchmark-id",
            spec.id,
            "--dataset-id",
            dataset.id,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert manifest_cli.returncode == 0, manifest_cli.stderr
    manifest_payload = json.loads(manifest_cli.stdout)

    run_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-pilot-run",
            "--benchmark-id",
            spec.id,
            "--manifest-id",
            manifest_payload["id"],
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run_cli.returncode == 0, run_cli.stderr
    execution_payload = json.loads(run_cli.stdout)

    status_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-pilot-status",
            "--execution-id",
            execution_payload["id"],
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status_cli.returncode == 0, status_cli.stderr
    assert "Selected Pilot Status" in status_cli.stdout
    assert "Run type: `pilot`" in status_cli.stdout
    assert "synthetic_pilot_data" in status_cli.stdout


def test_selected_pilot_analysis_outputs_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    execution = run_manager.run(spec.id, run_manager.create_manifest(spec.id, dataset.id).id)

    analysis = PilotAnalysisManager(config).analyze(execution.id)

    expected = {
        "pilot_metrics_json",
        "pilot_metrics_md",
        "pilot_baseline_comparison_json",
        "pilot_baseline_comparison_md",
        "pilot_error_analysis_json",
        "pilot_error_analysis_md",
        "pilot_low_fpr_report_json",
        "pilot_low_fpr_report_md",
        "pilot_limitations_md",
    }
    assert expected.issubset(analysis.output_paths)
    for key in expected:
        assert Path(analysis.output_paths[key]).exists()
    assert analysis.run_type == "pilot"


def test_selected_pilot_analysis_preserves_low_fpr_caveats_and_slices(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    execution = run_manager.run(spec.id, run_manager.create_manifest(spec.id, dataset.id).id)

    analysis = PilotAnalysisManager(config).analyze(execution.id)
    low_fpr = json.loads(Path(analysis.output_paths["pilot_low_fpr_report_json"]).read_text(encoding="utf-8"))
    comparison = json.loads(Path(analysis.output_paths["pilot_baseline_comparison_json"]).read_text(encoding="utf-8"))
    limitations = Path(analysis.output_paths["pilot_limitations_md"]).read_text(encoding="utf-8")

    assert "0.001" in low_fpr["underpowered_alpha_levels"]
    assert "alpha=0.001" in limitations
    assert comparison["observability_comparison"]["action_only"]
    assert comparison["observability_comparison"]["transcript_visible"]
    assert "synthetic pilot data" in limitations
    assert "weak" in limitations.lower()


def test_selected_pilot_analysis_error_examples_artifact_backed(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    execution = run_manager.run(spec.id, run_manager.create_manifest(spec.id, dataset.id).id)

    analysis = PilotAnalysisManager(config).analyze(execution.id)
    error_analysis = json.loads(Path(analysis.output_paths["pilot_error_analysis_json"]).read_text(encoding="utf-8"))

    assert error_analysis["artifact_source"] == execution.output_paths["predictions_json"]
    assert error_analysis["examples"]
    assert all(example["source_artifact"] == execution.output_paths["predictions_json"] for example in error_analysis["examples"])


def test_selected_pilot_analysis_failed_baselines_visible(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    manifest = run_manager.create_manifest(spec.id, dataset.id)
    manifest_path = run_manager.manifest_path(manifest.id)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["baseline_monitor_ids"].append("monitor-missing-required-baseline")
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    execution = run_manager.run(spec.id, manifest.id)

    analysis = PilotAnalysisManager(config).analyze(execution.id)
    error_analysis = json.loads(Path(analysis.output_paths["pilot_error_analysis_json"]).read_text(encoding="utf-8"))

    assert error_analysis["failed_baseline_runs"]
    assert any("monitor-missing-required-baseline" in item for item in error_analysis["failed_baseline_runs"])


def test_selected_pilot_analysis_cli_and_report_render(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = PilotDatasetBuilder(config).build(spec.id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    execution = run_manager.run(spec.id, run_manager.create_manifest(spec.id, dataset.id).id)
    env = _env()

    analysis_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-analysis", "--execution-id", execution.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert analysis_cli.returncode == 0, analysis_cli.stderr
    assert report_cli.returncode == 0, report_cli.stderr
    assert "pilot_low_fpr_report_json" in analysis_cli.stdout
    assert "Selected Pilot Result Report" in report_cli.stdout
    assert "Run type: `pilot`" in report_cli.stdout
    rendered = render_selected_pilot_report(PilotAnalysisManager(config).load_latest_for_benchmark(spec.id))
    assert "Run type: `pilot`" in rendered
    assert "Run type: `smoke`" not in rendered
    assert "Run type: `main`" not in rendered


def test_selected_related_work_required_categories_detected(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())

    recall = SelectedBenchmarkRelatedWorkManager(config).build_prior_work_recall(spec.id)

    assert set(REQUIRED_RELATED_WORK_CATEGORIES).issubset(recall.category_paper_ids)
    assert all(recall.category_paper_ids[category] for category in REQUIRED_RELATED_WORK_CATEGORIES)
    assert recall.closest_prior_work_ids


def test_selected_related_work_missing_categories_block_strong_novelty(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = SelectedBenchmarkRelatedWorkManager(config)

    recall = manager.build_prior_work_recall(spec.id)
    positioning = manager.novelty_report(spec.id)

    assert recall.missing_categories
    assert positioning.novelty_strength in {"unknown", "weak"}
    assert not positioning.strong_novelty_allowed
    assert any("Missing prior-work categories" in issue for issue in positioning.blocking_issues)


def test_selected_related_work_matrix_renders(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    manager = SelectedBenchmarkRelatedWorkManager(config)
    manager.build_prior_work_recall(spec.id)

    matrix = manager.build_related_work_matrix(spec.id)
    rendered = manager.render_related_work_matrix(spec.id)

    assert matrix.entries
    assert "Selected Benchmark Related-Work Matrix" in rendered
    assert "Closest prior work" in rendered
    assert "benchmark/evaluation protocol" in rendered


def test_selected_related_work_fake_citation_rejected(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    manager = SelectedBenchmarkRelatedWorkManager(config)
    recall = manager.build_prior_work_recall(spec.id)
    recall_path = manager.prior_work_recall_path(spec.id)
    payload = json.loads(recall_path.read_text(encoding="utf-8"))
    payload["category_paper_ids"][REQUIRED_RELATED_WORK_CATEGORIES[0]].append("paper-fake")
    recall_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    try:
        manager.build_related_work_matrix(spec.id)
    except ValueError as exc:
        assert "fake or unknown paper IDs" in str(exc)
    else:
        raise AssertionError("Expected fake citation rejection.")
    assert recall.id


def test_selected_related_work_novelty_positioning_conservative_and_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    env = _env()

    prior_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-prior-work", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    matrix_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-related-work", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    novelty_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-novelty-report", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert prior_cli.returncode == 0, prior_cli.stderr
    assert matrix_cli.returncode == 0, matrix_cli.stderr
    assert novelty_cli.returncode == 0, novelty_cli.stderr
    assert "Selected Benchmark Prior-Work Recall" in prior_cli.stdout
    assert "Selected Benchmark Related-Work Matrix" in matrix_cli.stdout
    assert "Novelty Positioning" in novelty_cli.stdout
    assert "benchmark/evaluation protocol" in novelty_cli.stdout
    positioning = SelectedBenchmarkRelatedWorkManager(config).novelty_report(spec.id)
    rendered = render_novelty_positioning(positioning)
    assert "strong novelty" not in rendered.lower()
    assert positioning.contribution_positioning == "benchmark/evaluation protocol"


def test_selected_pilot_review_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_prior_work_recall(spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_related_work_matrix(spec.id)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec.id)
    root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir) / "selected_benchmark" / "reviews"

    roles = {review.role for review in panel.reviewer_reports}
    assert {
        "benchmark validity reviewer",
        "statistics/low-FPR reviewer",
        "baseline reviewer",
        "related-work/novelty reviewer",
        "synthetic data validity reviewer",
        "area chair",
    }.issubset(roles)
    assert (root / "pilot_review_panel.json").exists()
    assert (root / "pilot_review_panel.md").exists()
    assert (root / "required_fixes.json").exists()
    assert (root / "required_fixes.md").exists()
    assert (root / "publishability_assessment.md").exists()


def test_selected_pilot_review_missing_related_work_category_flagged(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _complete_pilot_evidence(config, spec.id)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec.id)
    related_review = next(review for review in panel.reviewer_reports if review.role == "related-work/novelty reviewer")

    assert any("Missing prior-work categories" in flaw for flaw in related_review.fatal_flaws)
    assert any("Missing prior-work categories" in blocker for blocker in panel.fatal_blockers)


def test_selected_pilot_review_synthetic_deployment_overclaim_flagged(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_prior_work_recall(spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_related_work_matrix(spec.id)
    root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir) / "selected_benchmark"
    (root / "paper_package").mkdir(parents=True, exist_ok=True)
    (root / "paper_package" / "overclaim.md").write_text(
        "This pilot establishes deployment validity for operational collusion monitoring.\n",
        encoding="utf-8",
    )

    panel = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec.id)
    synthetic_review = next(review for review in panel.reviewer_reports if review.role == "synthetic data validity reviewer")

    assert any("deployment claims" in flaw.lower() for flaw in synthetic_review.fatal_flaws)


def test_selected_pilot_review_weak_baseline_flagged(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_prior_work_recall(spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_related_work_matrix(spec.id)

    panel = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec.id)
    baseline_review = next(review for review in panel.reviewer_reports if review.role == "baseline reviewer")

    assert any("Weak baseline suite" in flaw for flaw in baseline_review.fatal_flaws)


def test_selected_pilot_review_underpowered_alpha_flagged_and_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_prior_work_recall(spec.id)
    SelectedBenchmarkRelatedWorkManager(config).build_related_work_matrix(spec.id)
    env = _env()

    review_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-review", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    fix_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-fix-list", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    panel = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec.id)
    stats_review = next(review for review in panel.reviewer_reports if review.role == "statistics/low-FPR reviewer")
    assert review_cli.returncode == 0, review_cli.stderr
    assert fix_cli.returncode == 0, fix_cli.stderr
    assert "Pilot Review Panel" in review_cli.stdout
    assert "Required Fixes" in fix_cli.stdout
    assert any("alpha=0.001" in flaw for flaw in stats_review.fatal_flaws)
    assert "not_publishable" in panel.publishability_assessment


def test_selected_pilot_manuscript_generated_with_conservative_claims(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
    related_work_manager.build_prior_work_recall(spec.id)
    related_work_manager.build_related_work_matrix(spec.id)

    manuscript = SelectedPilotManuscriptManager(config).generate(spec.id)
    rendered = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert manuscript.run_type == "pilot"
    assert set(manuscript.sections) == {
        "motivation",
        "benchmark definition",
        "threat model",
        "pilot trace dataset",
        "baseline monitors",
        "calibration",
        "sequential specificity metrics",
        "pilot results",
        "low-FPR limitations",
        "related work",
        "reviewer blockers",
        "path to main benchmark",
    }
    assert "Run type: `pilot`" in rendered
    assert "Synthetic pilot data: yes" in rendered
    assert "alpha=0.001" in rendered
    assert "blocked" in rendered.lower()
    assert "related work" in rendered.lower()
    assert "not publication-ready" in rendered.lower()
    assert not manuscript.publication_ready


def test_selected_pilot_paper_package_includes_related_work_and_blocks_overclaim_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    _attach_run(config, selected_project_id, _selected_related_work_papers())
    _complete_pilot_evidence(config, spec.id)
    related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
    related_work_manager.build_prior_work_recall(spec.id)
    related_work_manager.build_related_work_matrix(spec.id)
    env = _env()

    manuscript_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-manuscript", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    package_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-paper-package", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert manuscript_cli.returncode == 0, manuscript_cli.stderr
    assert package_cli.returncode == 0, package_cli.stderr
    package = json.loads(package_cli.stdout)
    package_dir = Path(package["package_dir"])
    assert package["readiness"].startswith("not_publication_ready")
    assert "selected_pilot_manuscript.md" in package["files"]
    assert "selected_related_work_matrix.md" in package["files"]
    assert "pilot_artifact_manifest.json" in package["files"]
    assert "deployment validity" not in (package_dir / "selected_pilot_manuscript.md").read_text(encoding="utf-8").lower()
    assert "Publication-ready claim: blocked" in (package_dir / "selected_pilot_manuscript.md").read_text(encoding="utf-8")


def test_selected_pilot_power_plan_generated(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    plan = PilotPowerManager(config).create_plan(spec.id)

    assert plan.benchmark_id == spec.id
    assert plan.pilot_alpha == 0.01
    assert plan.main_alpha == 0.001
    assert plan.target_alpha_levels == [0.01, 0.001]
    assert plan.negative_trace_requirements["0.01"] < plan.negative_trace_requirements["0.001"]
    assert plan.negative_trace_requirements["0.01"] > 0
    assert "family-wise false-alarm" in "\n".join(plan.sequential_testing_notes)


def test_selected_pilot_power_underpowered_dataset_blocks_alpha_01_and_001(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=60, split="pilot")

    assessment = PilotPowerManager(config).check_dataset(dataset.id)

    assert assessment.observed_negative_count < assessment.alpha_targets_underpowered["0.01"]["required_negative_count"]
    assert "0.01" not in assessment.alpha_targets_met
    assert "0.01" in assessment.alpha_targets_underpowered
    assert "0.001" in assessment.alpha_targets_underpowered
    assert any("underpowered for alpha=0.01" in blocker for blocker in assessment.blockers)
    assert assessment.zero_false_positive_upper_bounds["0.01"] > 0.01


def test_selected_pilot_power_adequate_pilot_dataset_passes_alpha_001_only(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    required_for_pilot = PilotPowerManager(config).create_plan(spec.id).negative_trace_requirements["0.01"]
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=required_for_pilot * 3, split="pilot")

    assessment = PilotPowerManager(config).check_dataset(dataset.id)

    assert "0.01" in assessment.alpha_targets_met
    assert "0.001" in assessment.alpha_targets_underpowered
    assert any("main-scale" in warning for warning in assessment.warnings)
    assert not assessment.blockers
    assert assessment.alpha_targets_met["0.01"]["observed_negative_count"] >= required_for_pilot


def test_selected_pilot_power_report_renders_and_cli(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    required_for_pilot = PilotPowerManager(config).create_plan(spec.id).negative_trace_requirements["0.01"]
    dataset = SyntheticTraceGenerator(config).generate(spec.id, count=required_for_pilot * 3, split="pilot")
    env = _env()

    plan_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-power-plan", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    check_by_dataset_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-power-check", "--dataset-id", dataset.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    check_by_benchmark_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-pilot-power-check", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert plan_cli.returncode == 0, plan_cli.stderr
    assert check_by_dataset_cli.returncode == 0, check_by_dataset_cli.stdout
    assert check_by_benchmark_cli.returncode == 0, check_by_benchmark_cli.stdout
    assert "Pilot Power and Sample-Size Plan" in plan_cli.stdout
    assert "alpha=0.01" in plan_cli.stdout
    assert "Pilot Power Assessment" in check_by_dataset_cli.stdout
    assert "alpha=0.01: supported" in check_by_dataset_cli.stdout
    assert "alpha=0.001: underpowered" in check_by_dataset_cli.stdout
    assert "Zero false positives are bounded estimates" in check_by_dataset_cli.stdout
    assert render_pilot_power_assessment(PilotPowerManager(config).check_dataset(dataset.id)).startswith("# Pilot Power Assessment")


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


def _selected_related_work_papers() -> list[Paper]:
    return [
        Paper(
            id="paper-low-fpr",
            title="Low false positive specificity evaluation for safety monitors",
            authors=[],
            abstract="Evaluates false alarm rates and specificity for detector benchmarks.",
            year=2024,
            source="fixture",
        ),
        Paper(
            id="paper-collusion",
            title="Multi-agent collusion and covert coordination in repeated games",
            authors=[],
            abstract="Studies collusion, covert coordination, and communication among multiple agents.",
            year=2023,
            source="fixture",
        ),
        Paper(
            id="paper-evasion",
            title="Monitor evasion by adversarial agents",
            authors=[],
            abstract="Adversarial examples evade monitoring and audit detectors.",
            year=2025,
            source="fixture",
        ),
        Paper(
            id="paper-sequential",
            title="Sequential testing and change-point detection for alarms",
            authors=[],
            abstract="Sequential tests, change-point detection, and repeated alarm windows.",
            year=2022,
            source="fixture",
        ),
        Paper(
            id="paper-benchmark",
            title="Benchmark and evaluation protocol design for safety audits",
            authors=[],
            abstract="Defines benchmark datasets, baselines, and evaluation protocols.",
            year=2025,
            source="fixture",
            roles=["benchmark"],
        ),
        Paper(
            id="paper-anomaly",
            title="Anomaly detection specificity under rare event false positives",
            authors=[],
            abstract="Anomaly detection systems require specificity and calibrated false-positive analysis.",
            year=2021,
            source="fixture",
        ),
        Paper(
            id="paper-medical",
            title="Medical screening specificity and diagnostic false positive rates",
            authors=[],
            abstract="Medical screening evaluates sensitivity, specificity, and diagnostic false positives.",
            year=2020,
            source="fixture",
        ),
        Paper(
            id="paper-cartel",
            title="Cartel detection and covert-channel analogies",
            authors=[],
            abstract="Cartel behavior, covert channels, and price-fixing analogies for hidden coordination.",
            year=2019,
            source="fixture",
        ),
    ]


def _complete_pilot_evidence(config: GapForgeConfig, benchmark_id: str):
    dataset = PilotDatasetBuilder(config).build(benchmark_id, negative_count=300, positive_count=100)
    run_manager = PilotRunManager(config)
    execution = run_manager.run(benchmark_id, run_manager.create_manifest(benchmark_id, dataset.id).id)
    PilotAnalysisManager(config).analyze(execution.id)
    return dataset, execution


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
