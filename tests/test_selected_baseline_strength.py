from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.models import Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import MonitorBaselineManager, SelectedBenchmarkManager
from gapforge.selected_benchmark.baselines import REQUIRED_MAIN_BASELINE_TYPES, MonitorCalibrationRecord
from gapforge.state import utc_now_iso


def test_missing_required_baseline_blocks_strength(tmp_path: Path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = MonitorBaselineManager(config)
    baselines = [
        baseline for baseline in manager.create_baselines(spec.id) if baseline.baseline_type != "permutation_null_distribution_detector"
    ]
    _write_baselines(config, selected_project_id, baselines)

    assessment = manager.assess_baseline_strength(spec.id)

    assert "permutation_null_distribution_detector" in assessment.missing_baselines
    assert assessment.strong_claim_allowed is False
    assert assessment.reviewer_risk == "blocked"
    assert any("missing required baseline type `permutation_null_distribution_detector`" in blocker for blocker in assessment.blockers)


def test_implemented_required_baselines_allow_stronger_claim_without_optional_llm_judge(tmp_path: Path) -> None:
    config, _selected_project_id, benchmark_id = _benchmark(tmp_path)
    manager = MonitorBaselineManager(config)
    baselines = [baseline for baseline in manager.create_baselines(benchmark_id) if baseline.baseline_type != "llm_judge_baseline"]
    _write_baselines_for_benchmark(config, benchmark_id, baselines)

    assessment = manager.assess_baseline_strength(benchmark_id)

    assert set(assessment.required_baselines) == REQUIRED_MAIN_BASELINE_TYPES
    assert assessment.missing_baselines == []
    assert "llm_judge_baseline" not in assessment.missing_baselines
    assert assessment.strong_claim_allowed is True
    assert assessment.reviewer_risk == "baseline_suite_ready"


def test_calibration_leakage_blocks_baseline_strength(tmp_path: Path) -> None:
    config, _selected_project_id, benchmark_id = _benchmark(tmp_path)
    manager = MonitorBaselineManager(config)
    baselines = manager.create_baselines(benchmark_id)
    leaked_monitor_id = next(item.id for item in baselines if item.baseline_type == "calibrated_anomaly_detector")
    record = MonitorCalibrationRecord(
        id="monitor-calibration-leakage",
        monitor_id=leaked_monitor_id,
        calibration_dataset_id="mixed-pilot-dataset",
        target_alpha=0.01,
        threshold=0.9,
        observed_fpr=0.0,
        warnings=["Calibration data leakage: calibration dataset includes collusive traces."],
        provenance=Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Fixture leakage record.",
        ),
    )
    _write_calibration(config, benchmark_id, record)

    assessment = manager.assess_baseline_strength(benchmark_id)

    assert assessment.calibration_status == "leakage_blocked"
    assert assessment.strong_claim_allowed is False
    assert any("calibration data leakage" in blocker.lower() for blocker in assessment.blockers)


def test_implement_required_baseline_task_restores_missing_baseline(tmp_path: Path) -> None:
    config, _selected_project_id, benchmark_id = _benchmark(tmp_path)
    manager = MonitorBaselineManager(config)
    baselines = [
        baseline for baseline in manager.create_baselines(benchmark_id) if baseline.baseline_type != "robust_lexical_substitution_monitor"
    ]
    _write_baselines_for_benchmark(config, benchmark_id, baselines)

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "implement-required-baseline-task",
            "--benchmark-id",
            benchmark_id,
            "--baseline",
            "robust_lexical_substitution_monitor",
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assessment = manager.assess_baseline_strength(benchmark_id)

    assert cli.returncode == 0, cli.stderr
    assert "robust_lexical_substitution_monitor" in cli.stdout
    assert "robust_lexical_substitution_monitor" not in assessment.missing_baselines


def test_baseline_strength_report_renders_and_cli_commands(tmp_path: Path) -> None:
    config, _selected_project_id, benchmark_id = _benchmark(tmp_path)
    manager = MonitorBaselineManager(config)
    manager.create_baselines(benchmark_id)

    report = manager.render_baseline_strength_report(benchmark_id)

    assert "Baseline Strength Assessment" in report
    assert "Strong claim allowed" in report
    assert "Optional LLM judge" in report

    status_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-baseline-strength", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-baseline-strength-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert status_cli.returncode == 0, status_cli.stderr
    assert '"strong_claim_allowed": true' in status_cli.stdout
    assert cli.returncode == 0, cli.stderr
    assert "Baseline Strength Assessment" in cli.stdout
    assert "llm_judge_baseline" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[object, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _write_baselines(config: object, selected_project_id: str, baselines: list[object]) -> None:
    project_root = Path(ProjectMemoryManager(config).load_project(selected_project_id).project.root_dir)  # type: ignore[arg-type]
    registry_path = project_root / "selected_benchmark" / "monitor_baselines.json"
    registry_path.write_text(json.dumps(to_plain(baselines), indent=2) + "\n", encoding="utf-8")


def _write_baselines_for_benchmark(config: object, benchmark_id: str, baselines: list[object]) -> None:
    spec = SelectedBenchmarkManager(config).load_spec(benchmark_id)  # type: ignore[arg-type]
    _write_baselines(config, spec.project_id, baselines)


def _write_calibration(config: object, benchmark_id: str, record: MonitorCalibrationRecord) -> None:
    spec = SelectedBenchmarkManager(config).load_spec(benchmark_id)  # type: ignore[arg-type]
    project_root = Path(ProjectMemoryManager(config).load_project(spec.project_id).project.root_dir)  # type: ignore[arg-type]
    path = project_root / "selected_benchmark" / "monitor_calibrations" / f"{record.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
