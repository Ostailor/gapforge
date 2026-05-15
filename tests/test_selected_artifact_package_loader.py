from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.metrics import MetricRegistry
from gapforge.replication import ReplicationPackageExporter
from gapforge.reviewers.drastic_panel import DrasticReviewPanelBuilder
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.artifact_package_loader import (
    ArtifactPackageLoader,
    render_artifact_package_load_result,
)
from gapforge.state import slugify


def test_loader_loads_artifact_package_fixture(tmp_path: Path) -> None:
    config, benchmark_id, manuscript_id, workspace_id = _selected_artifact_fixture(tmp_path)
    replication = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package = ArtifactEvaluationPackageExporter(config).export(manuscript_id)

    result = ArtifactPackageLoader(config).load(benchmark_id)

    assert result.status == "loaded"
    assert result.selected_package_id == package.id
    assert result.workspace_id == workspace_id
    assert result.required_files_present is True
    assert result.expected_outputs_present is True
    assert result.replication_package_present is True
    assert result.hardware_requirements_present is True
    assert result.run_instructions_present is True
    assert result.blockers == []
    assert replication.id in result.provenance.source_ids or package.id in result.provenance.source_ids


def test_loader_repairs_package_from_workspace_fixture_for_drastic_review(tmp_path: Path) -> None:
    config, benchmark_id, manuscript_id, workspace_id = _selected_artifact_fixture(tmp_path)
    ReplicationPackageExporter(config).export_workspace(workspace_id)

    repair = ArtifactPackageLoader(config).repair(benchmark_id)
    panel = DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)
    artifact_review = next(review for review in panel.reviewer_reports if review.reviewer_id == "R5")

    assert repair.status == "repaired"
    assert repair.repaired_package_id == f"artifact-eval-{manuscript_id}"
    assert not any("missing:artifact_package" in flaw for flaw in artifact_review.fatal_flaws)
    assert any("artifact-package:" in evidence for evidence in artifact_review.evidence_or_prior_work)


def test_missing_replication_package_blocks_repair(tmp_path: Path) -> None:
    config, benchmark_id, _manuscript_id, workspace_id = _selected_artifact_fixture(tmp_path, run_metrics=False)

    repair = ArtifactPackageLoader(config).repair(benchmark_id)

    assert repair.status == "blocked"
    assert repair.source_workspace_id == workspace_id
    assert repair.source_replication_package_id == ""
    assert any("export-replication-package" in action for action in repair.repair_actions)


def test_restricted_data_excluded_by_repair(tmp_path: Path) -> None:
    config, benchmark_id, manuscript_id, workspace_id = _selected_artifact_fixture(
        tmp_path,
        dataset_type="real",
        license_name="restricted",
    )
    ReplicationPackageExporter(config).export_workspace(workspace_id)

    repair = ArtifactPackageLoader(config).repair(benchmark_id)
    package = ArtifactEvaluationPackageExporter(config).load(f"artifact-eval-{manuscript_id}")
    package_dir = ArtifactEvaluationPackageExporter(config).package_dir(package.id)
    result = ArtifactPackageLoader(config).load(benchmark_id)

    assert repair.status == "blocked"
    assert not (package_dir / "replication_package" / "data" / "fixture.csv").exists()
    assert list((package_dir / "replication_package" / "data").glob("*.record.json"))
    assert result.status == "invalid"
    assert any("excluded" in warning for warning in result.warnings)
    assert not any("unsafe dataset files are bundled" in blocker for blocker in result.blockers)


def test_artifact_package_report_renders_and_cli_status(tmp_path: Path) -> None:
    config, benchmark_id, manuscript_id, workspace_id = _selected_artifact_fixture(tmp_path)
    ReplicationPackageExporter(config).export_workspace(workspace_id)
    ArtifactEvaluationPackageExporter(config).export(manuscript_id)
    result = ArtifactPackageLoader(config).load(benchmark_id)

    rendered = render_artifact_package_load_result(result)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-artifact-package-status", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Artifact Package Load Result" in rendered
    assert "Candidate Paths" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Artifact Package Load Result" in cli.stdout
    assert "Status: `loaded`" in cli.stdout


def _selected_artifact_fixture(
    tmp_path: Path,
    *,
    dataset_type: str = "fixture",
    license_name: str = "MIT",
    run_metrics: bool = True,
) -> tuple[GapForgeConfig, str, str, str]:
    config, project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(project_id).id
    direction_id = f"selected-benchmark-{slugify(benchmark_id)}"
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=project_id, direction_id=direction_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,label\n1,0\n2,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture data",
        path=dataset_path,
        dataset_type=dataset_type,
        license=license_name,
        source_url="https://example.test/fixture",
        intended_use="Selected benchmark artifact evaluation fixture.",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="specificity")
    if run_metrics:
        _run_metrics(config, workspace.id)
    manuscript = ManuscriptManager(config).create_manuscript(
        project_id=project_id,
        direction_id=direction_id,
        workspace_id=workspace.id,
        title="Sequential specificity benchmark for low-FPR collusion audits",
    )
    _write_sections(config, manuscript.manuscript.id)
    return config, benchmark_id, manuscript.manuscript.id, workspace.id


def _run_metrics(config: GapForgeConfig, workspace_id: str) -> None:
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_selected_artifact_metrics.py"
    payload = json.dumps({"metric_results": [{"metric_id": "specificity", "value": 0.99, "sample_size": 2}]})
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = ExperimentWorkspaceManager(config).create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id)


def _write_sections(config: GapForgeConfig, manuscript_id: str) -> None:
    manager = ManuscriptManager(config)
    root = manager.manuscript_root(manuscript_id)
    sections = {
        "abstract": "We study sequential specificity for low-FPR collusion audits.",
        "introduction": "This paper contribution is a benchmark protocol for sequential specificity.",
        "related_work": "Closest prior work and benchmark baselines are compared.",
        "method": "The method uses vetted benchmark adapters and synthetic protocol scaffolding.",
        "results": "Results report specificity, uncertainty, power, ablation evidence, and baseline monitors.",
        "limitations": "Limitations include synthetic data validity and benchmark adaptation boundaries.",
    }
    for section_type, text in sections.items():
        section = manager.create_section(manuscript_id=manuscript_id, section_type=section_type, title=section_type.title())
        (root / section.content_path).write_text(f"# {section.title}\n\n{text}\n", encoding="utf-8")
