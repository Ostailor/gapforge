from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_real_benchmark_adapters import _no_fit_candidate, _primary_candidate, _sanity_candidate
from test_selected_benchmark import _env, _selected_project

from gapforge.selected_benchmark import RealBenchmarkSearchManager, SelectedBenchmarkManager
from gapforge.selected_benchmark.benchmark_fit_hardening import BenchmarkFitHardeningManager


def test_benchmark_fit_hardening_maps_multiple_candidates_and_writes_reports(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)
    RealBenchmarkSearchManager(config).search(spec.id, candidates=[_primary_candidate(), _sanity_candidate(), _no_fit_candidate()])

    report = BenchmarkFitHardeningManager(config).harden(spec.id)

    output_dir = Path(config.project_root / project_id / "selected_benchmark" / "benchmark_fit_hardening")
    assert len(report.candidate_rows) == 3
    assert report.decision == "credible_real_benchmark_grounding"
    assert any(row.claim_support == "primary" for row in report.candidate_rows)
    assert any(row.use_as == "auxiliary_sanity_check" for row in report.candidate_rows)
    assert "why not use" in report.reviewer_objection_answer.lower()
    assert (output_dir / "benchmark_fit_hardening_report.md").exists()
    assert (output_dir / "no_fit_argument.md").exists()
    assert (output_dir / "manuscript_insertion_text.md").exists()


def test_no_fit_argument_records_what_each_benchmark_lacks(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)
    RealBenchmarkSearchManager(config).search(spec.id, candidates=[_sanity_candidate(), _no_fit_candidate()])

    argument = BenchmarkFitHardeningManager(config).no_fit_argument(spec.id)
    output_dir = Path(config.project_root / project_id / "selected_benchmark" / "benchmark_fit_hardening")
    text = (output_dir / "no_fit_argument.md").read_text(encoding="utf-8")

    assert argument.decision == "new_benchmark_needed"
    assert "What existing benchmark lacks" in text
    assert "Streaming Anomaly Specificity Benchmark" in text
    assert "Static Image Classification Benchmark" in text
    assert "collusion" in text.lower()
    assert "low false-positive" in text.lower() or "low-fpr" in text.lower()
    assert "Manuscript Insertion Text" in text


def test_benchmark_fit_hardening_cli_outputs_report(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(project_id)
    RealBenchmarkSearchManager(config).search(spec.id, candidates=[_sanity_candidate(), _no_fit_candidate()])

    harden_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-fit-harden", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    no_fit_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "benchmark-no-fit-argument", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert harden_cli.returncode == 0, harden_cli.stderr
    assert "Benchmark Fit Hardening Report" in harden_cli.stdout
    assert "Reviewer Objection Answer" in harden_cli.stdout
    assert no_fit_cli.returncode == 0, no_fit_cli.stderr
    assert "Benchmark No-Fit Argument" in no_fit_cli.stdout
