from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_drastic_review_panel import _drastic_manuscript_fixture
from test_selected_artifact_package_loader import _selected_artifact_fixture
from test_selected_benchmark import _env
from test_selected_related_work_matrix_loader import _complete_fixture

from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.manuscript.drastic_rebuttal import DrasticRevisionManager
from gapforge.replication import ReplicationPackageExporter
from gapforge.reviewers.drastic_panel import DrasticReviewPanelBuilder, render_drastic_review_rerun_result
from gapforge.selected_benchmark import SelectedBenchmarkRelatedWorkMatrixV2Manager


def test_missing_matrix_blocker_resolved_by_rerun(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    builder = DrasticReviewPanelBuilder(config)
    old = builder.review_manuscript(manuscript_id)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    rerun = builder.rerun_manuscript(manuscript_id)

    assert any("missing:related_work_matrix" in blocker for blocker in old.fatal_flaws)
    assert any("missing:related_work_matrix" in blocker for blocker in rerun.resolved_blockers)
    assert not any("missing:related_work_matrix" in blocker for blocker in rerun.remaining_blockers)


def test_missing_artifact_package_blocker_resolved_by_rerun(tmp_path: Path) -> None:
    config, benchmark_id, manuscript_id, workspace_id = _selected_artifact_fixture(tmp_path)
    builder = DrasticReviewPanelBuilder(config)
    old = builder.review_manuscript(manuscript_id)
    ReplicationPackageExporter(config).export_workspace(workspace_id)
    ArtifactEvaluationPackageExporter(config).export(manuscript_id)

    rerun = builder.rerun_manuscript(manuscript_id)

    assert any("missing:artifact_package" in blocker for blocker in old.fatal_flaws)
    assert any("missing:artifact_package" in blocker for blocker in rerun.resolved_blockers)
    assert not any("missing:artifact_package" in blocker for blocker in rerun.remaining_blockers)


def test_remaining_fatal_blocker_blocks_conference_candidate(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)
    builder = DrasticReviewPanelBuilder(config)
    builder.review_manuscript(manuscript_id)

    rerun = builder.rerun_manuscript(manuscript_id)
    rendered = render_drastic_review_rerun_result(rerun)

    assert rerun.remaining_blockers
    assert "conference_candidate blocked" in rerun.readiness_change
    assert "Conference candidate: blocked" in rendered


def test_drastic_readiness_delta_renders_and_cli(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    builder = DrasticReviewPanelBuilder(config)
    builder.review_manuscript(manuscript_id)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    rerun = builder.rerun_manuscript(manuscript_id)

    rendered = builder.readiness_delta_report(manuscript_id)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "drastic-readiness-delta", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Drastic Review Rerun" in rendered
    assert "Readiness Guardrails" in rendered
    assert rerun.readiness_change in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Drastic Review Rerun" in cli.stdout


def test_drastic_revision_close_resolved_item(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    manager = DrasticRevisionManager(config)
    manager.build(manuscript_id)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    plan = manager.close_item(manuscript_id, "missing:related_work_matrix")

    assert any("missing:related_work_matrix" in item for item in plan.closed_items)
    assert not any("missing:related_work_matrix" in item for item in plan.fatal_fixes)
