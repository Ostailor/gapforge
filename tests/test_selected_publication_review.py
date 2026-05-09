from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project
from test_selected_related_work_completion import _attach_papers, _complete_real_papers

from gapforge.models import to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    MainAnalysisManager,
    MainDatasetBuilder,
    MainPowerManager,
    MainRunManager,
    PilotAnalysisManager,
    PilotDatasetBuilder,
    PilotRunManager,
    RelatedWorkCompletionManager,
    SelectedBenchmarkManager,
    SelectedBenchmarkReviewerPanelBuilder,
    render_publication_readiness_review,
)


def test_complete_main_fixture_is_conference_candidate(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)
    _write_manuscript_inputs(config, project_id)

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)

    assert review.readiness == "conference_candidate"
    assert review.fatal_blockers == []
    assert review.major_blockers == []
    assert "main-analysis" in " ".join(review.provenance.source_ids)


def test_pilot_only_fixture_stays_workshop_or_not_ready(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_pilot_analysis(config, benchmark_id, negative_count=40, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)
    _write_manuscript_inputs(config, project_id)

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)

    assert review.readiness in {"workshop_candidate", "not_ready"}
    assert review.readiness != "conference_candidate"
    assert any("pilot-only" in item.lower() or "pilot" in item.lower() for item in review.required_revisions)


def test_synthetic_deployment_overclaim_is_fatal(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)
    _write_manuscript_inputs(
        config,
        project_id,
        claims=["The synthetic benchmark establishes deployment validity for deployed monitors."],
    )

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)

    assert review.readiness != "conference_candidate"
    assert any("deployment" in blocker.lower() for blocker in review.fatal_blockers)


def test_missing_related_work_is_major_or_fatal(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _write_manuscript_inputs(config, project_id)

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)

    assert review.readiness != "conference_candidate"
    blockers = [*review.fatal_blockers, *review.major_blockers]
    assert any("related work" in blocker.lower() for blocker in blockers)


def test_publication_review_report_renders_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=300, positive_count=20)
    _write_manuscript_inputs(config, project_id, claims=["Claim alpha=0.001 specificity support."])

    review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id)
    rendered = render_publication_readiness_review(review)

    assert "# Publication Readiness Review" in rendered
    assert "Readiness:" in rendered

    review_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-publication-review", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    fix_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-publication-fix-list", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert review_cli.returncode in {0, 1}
    assert "Publication Readiness Review" in review_cli.stdout
    assert fix_cli.returncode == 0, fix_cli.stderr
    assert "Publication Readiness Fix List" in fix_cli.stdout


def _benchmark(tmp_path: Path) -> tuple[object, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _complete_main_analysis(config: object, benchmark_id: str, *, negative_count: int, positive_count: int) -> None:
    power_manager = MainPowerManager(config)  # type: ignore[arg-type]
    power_manager.create_plan(benchmark_id, planned_negative_count=negative_count, planned_positive_count=positive_count)
    power_manager.decide_alpha(benchmark_id, alpha_level=0.001)
    dataset = MainDatasetBuilder(config).build(benchmark_id)  # type: ignore[arg-type]
    run_manager = MainRunManager(config)  # type: ignore[arg-type]
    manifest = run_manager.create_manifest(benchmark_id, dataset.id)
    execution = run_manager.run(benchmark_id, manifest.id)
    MainAnalysisManager(config).analyze(execution.id)  # type: ignore[arg-type]


def _complete_pilot_analysis(config: object, benchmark_id: str, *, negative_count: int, positive_count: int) -> None:
    dataset = PilotDatasetBuilder(config).build(benchmark_id, negative_count=negative_count, positive_count=positive_count)  # type: ignore[arg-type]
    run_manager = PilotRunManager(config)  # type: ignore[arg-type]
    manifest = run_manager.create_manifest(benchmark_id, dataset.id)
    execution = run_manager.run(benchmark_id, manifest.id)
    PilotAnalysisManager(config).analyze(execution.id)  # type: ignore[arg-type]


def _complete_related_work(config: object, project_id: str, benchmark_id: str) -> None:
    _attach_papers(config, project_id, _complete_real_papers())  # type: ignore[arg-type]
    RelatedWorkCompletionManager(config).complete(benchmark_id)  # type: ignore[arg-type]


def _write_manuscript_inputs(
    config: object,
    project_id: str,
    *,
    claims: list[str] | None = None,
) -> None:
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"  # type: ignore[arg-type]
    manuscript = root / "main_manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "traceability.json").write_text(
        json.dumps({"status": "pass", "traceability_passed": True, "fatal_blockers": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    package = {
        "id": "main-manuscript-package-fixture",
        "status": "draft",
        "claims": claims or ["Synthetic main benchmark specificity claim at powered primary alpha."],
        "deployment_validity_claim": False,
    }
    (manuscript / "package.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    (manuscript / "package.md").write_text("\n".join(package["claims"]) + "\n", encoding="utf-8")
    (manuscript / "package_copy.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
