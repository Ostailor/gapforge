from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_real_benchmark_adapters import _no_fit_candidate
from test_selected_artifact_package_loader import _run_metrics, _selected_artifact_fixture
from test_selected_benchmark import _env
from test_selected_related_work_matrix_loader import _complete_fixture

from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.metrics import MetricRegistry
from gapforge.replication import ReplicationPackageExporter
from gapforge.selected_benchmark import (
    RealBenchmarkSearchManager,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    VenueArtifactIntegrationManager,
    render_venue_artifact_integration_report,
)


def test_venue_artifact_integration_succeeds_with_matrix_and_package(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    _add_artifact_package(config, manuscript_id)

    report = VenueArtifactIntegrationManager(config).integrate(benchmark_id)
    state = ManuscriptManager(config).load_state(manuscript_id)

    assert report.blockers == []
    assert report.related_work_matrix_status == "loaded"
    assert report.artifact_package_status == "loaded"
    assert report.integrated_sections
    assert report.updated_citations
    assert any("artifact-eval" in link for link in report.updated_artifact_links)
    assert any(section.title == "Artifact Evaluation Appendix" for section in state.sections)


def test_venue_artifact_integration_missing_matrix_blocks(tmp_path: Path) -> None:
    config, benchmark_id, _manuscript_id, _workspace_id = _selected_artifact_fixture(tmp_path)
    _export_artifact_package(config, benchmark_id)

    report = VenueArtifactIntegrationManager(config).integrate(benchmark_id)

    assert report.integrated_sections == []
    assert report.related_work_matrix_status in {"missing", "invalid"}
    assert any("related-work matrix" in blocker for blocker in report.blockers)


def test_venue_artifact_integration_missing_package_blocks(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, _manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    report = VenueArtifactIntegrationManager(config).integrate(benchmark_id)

    assert report.integrated_sections == []
    assert report.artifact_package_status in {"missing", "invalid"}
    assert any("artifact evaluation package" in blocker for blocker in report.blockers)


def test_venue_artifact_integration_includes_no_fit_report(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    _add_artifact_package(config, manuscript_id)
    RealBenchmarkSearchManager(config).search(benchmark_id, candidates=[_no_fit_candidate()])

    report = VenueArtifactIntegrationManager(config).integrate(benchmark_id)

    assert report.blockers == []
    assert report.real_benchmark_status == "no_fit"
    assert any("real_benchmark_no_fit_report.md" in link for link in report.updated_artifact_links)


def test_venue_artifact_report_renders_and_cli(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    _add_artifact_package(config, manuscript_id)
    report = VenueArtifactIntegrationManager(config).integrate(benchmark_id)

    rendered = render_venue_artifact_integration_report(report)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-venue-artifact-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Venue Artifact Integration Report" in rendered
    assert "Claim Boundary" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Venue Artifact Integration Report" in cli.stdout
    assert "Real benchmark status" in cli.stdout


def _add_artifact_package(config, manuscript_id: str) -> None:
    state = ManuscriptManager(config).load_state(manuscript_id)
    workspace_id = state.manuscript.workspace_id
    workspace_root = Path(ExperimentWorkspaceManager(config).load_workspace(workspace_id).root_dir)
    dataset_path = workspace_root / "data" / "fixture.csv"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text("id,label\n1,0\n2,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="fixture data",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        source_url="https://example.test/fixture",
        intended_use="Selected benchmark venue artifact integration fixture.",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace_id, name="specificity")
    _run_metrics(config, workspace_id)
    ReplicationPackageExporter(config).export_workspace(workspace_id)
    ArtifactEvaluationPackageExporter(config).export(manuscript_id)


def _export_artifact_package(config, benchmark_id: str) -> None:
    from gapforge.selected_benchmark.artifact_package_loader import ArtifactPackageLoader

    context_result = ArtifactPackageLoader(config).load(benchmark_id, write_report=False)
    manuscript_id = context_result.manuscript_id
    state = ManuscriptManager(config).load_state(manuscript_id)
    _run_metrics(config, state.manuscript.workspace_id)
    ReplicationPackageExporter(config).export_workspace(state.manuscript.workspace_id)
    ArtifactEvaluationPackageExporter(config).export(manuscript_id)
