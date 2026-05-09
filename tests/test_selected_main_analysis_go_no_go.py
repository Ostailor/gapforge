from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project
from test_selected_related_work_completion import _attach_papers, _complete_real_papers

from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    MainDatasetBuilder,
    MainPowerManager,
    MainRunManager,
    RelatedWorkCompletionManager,
    SelectedBenchmarkManager,
)
from gapforge.selected_benchmark.go_no_go import GoNoGoManager, render_go_no_go_report
from gapforge.selected_benchmark.main_analysis import MainAnalysisManager, render_selected_main_analysis


def test_powered_complete_fixture_goes_to_publication_candidate(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    execution_id = _main_execution(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id)
    _write_review_and_traceability(config, project_id)
    MainAnalysisManager(config).analyze(execution_id)

    decision = GoNoGoManager(config).decide(benchmark_id)

    assert decision.decision == "go_publication_candidate"
    assert decision.blockers == []
    assert decision.confidence == "medium"
    assert "main-analysis" in " ".join(decision.evidence)


def test_missing_related_work_revises_or_runs_more(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    execution_id = _main_execution(config, benchmark_id, negative_count=3000, positive_count=20)
    _write_review_and_traceability(config, project_id)
    MainAnalysisManager(config).analyze(execution_id)

    decision = GoNoGoManager(config).decide(benchmark_id)

    assert decision.decision in {"revise_benchmark", "run_more_experiments"}
    assert any("related work" in blocker.lower() for blocker in decision.blockers)


def test_underpowered_main_run_requires_more_experiments(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    execution_id = _main_execution(config, benchmark_id, negative_count=300, positive_count=20)
    _complete_related_work(config, project_id)
    _write_review_and_traceability(config, project_id)
    MainAnalysisManager(config).analyze(execution_id)

    decision = GoNoGoManager(config).decide(benchmark_id)

    assert decision.decision == "run_more_experiments"
    assert any("alpha=0.001" in blocker for blocker in decision.blockers)


def test_fatal_novelty_duplicate_is_no_go(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    execution_id = _main_execution(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id)
    _write_review_and_traceability(config, project_id, fatal_blockers=["Fatal novelty duplicate: closest prior work already covers it."])
    MainAnalysisManager(config).analyze(execution_id)

    decision = GoNoGoManager(config).decide(benchmark_id)

    assert decision.decision == "no_go"
    assert any("duplicate" in blocker.lower() for blocker in decision.blockers)


def test_main_analysis_and_go_no_go_reports_render_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    execution_id = _main_execution(config, benchmark_id, negative_count=300, positive_count=20)
    _complete_related_work(config, project_id)
    _write_review_and_traceability(config, project_id)

    analysis = MainAnalysisManager(config).analyze(execution_id)
    decision = GoNoGoManager(config).decide(benchmark_id)

    assert "Main Result Analysis" in render_selected_main_analysis(analysis)
    assert "Selected Benchmark Go/No-Go" in render_go_no_go_report(decision)

    analysis_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-main-analysis", "--execution-id", execution_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    decision_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-benchmark-go-no-go", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-go-no-go-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert analysis_cli.returncode == 0, analysis_cli.stderr
    assert "Main Result Analysis" in analysis_cli.stdout
    assert decision_cli.returncode in {0, 1}
    assert "run_more_experiments" in decision_cli.stdout
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Selected Benchmark Go/No-Go" in report_cli.stdout


def _benchmark(tmp_path: Path) -> tuple[object, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _main_execution(config: object, benchmark_id: str, *, negative_count: int, positive_count: int) -> str:
    MainPowerManager(config).create_plan(  # type: ignore[arg-type]
        benchmark_id,
        planned_negative_count=negative_count,
        planned_positive_count=positive_count,
    )
    dataset = MainDatasetBuilder(config).build(benchmark_id)  # type: ignore[arg-type]
    manager = MainRunManager(config)  # type: ignore[arg-type]
    return manager.run(benchmark_id, manager.create_manifest(benchmark_id, dataset.id).id).id


def _complete_related_work(config: object, project_id: str) -> None:
    _attach_papers(config, project_id, _complete_real_papers())  # type: ignore[arg-type]
    benchmark_id = SelectedBenchmarkManager(config).create_spec(project_id).id  # type: ignore[arg-type]
    RelatedWorkCompletionManager(config).complete(benchmark_id)  # type: ignore[arg-type]


def _write_review_and_traceability(
    config: object,
    project_id: str,
    *,
    fatal_blockers: list[str] | None = None,
) -> None:
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"  # type: ignore[arg-type]
    reviews = root / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    (reviews / "main_publication_review.json").write_text(
        json.dumps(
            {
                "fatal_blockers": fatal_blockers or [],
                "nonfatal_blockers": [],
                "status": "pass" if not fatal_blockers else "fatal",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manuscript = root / "main_manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "traceability.json").write_text(
        json.dumps({"status": "pass", "traceability_passed": True, "fatal_blockers": []}, indent=2) + "\n",
        encoding="utf-8",
    )
