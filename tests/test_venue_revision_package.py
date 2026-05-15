from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env
from test_selected_related_work_matrix_loader import _complete_fixture
from test_venue_artifact_integration import _add_artifact_package

from gapforge.manuscript import ManuscriptManager
from gapforge.selected_benchmark import (
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    VenueRevisionPackageManager,
    render_venue_revision_package,
)


def test_workshop_venue_revision_package_generated(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _venue_revision_fixture(tmp_path)

    package = VenueRevisionPackageManager(config).create(benchmark_id)

    assert package.status == "workshop_candidate"
    assert package.manuscript_id == manuscript_id
    assert package.related_work_matrix_id
    assert package.artifact_package_id
    assert "venue_shaped_manuscript.md" in package.files
    assert "submission_checklist.md" in package.files


def test_conference_package_requires_no_fatal_blockers(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _venue_revision_fixture(tmp_path)
    manager = ManuscriptManager(config)
    state = manager.load_state(manuscript_id)
    section = next(item for item in state.sections if item.section_type == "method")
    manager.link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section.id,
        claim_id="claim-fatal-unsup",
        claim_text="The method definitively solves benchmark deployment.",
        use_type="method",
        support_status="unsupported",
    )

    package = VenueRevisionPackageManager(config).create(benchmark_id)

    assert package.status == "revise_for_reviews"
    assert any("unsupported_claims" in item for item in package.limitations)


def test_fake_citation_blocks_venue_revision_package(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _venue_revision_fixture(tmp_path)
    manager = ManuscriptManager(config)
    root = manager.manuscript_root(manuscript_id)
    state = manager.load_state(manuscript_id)
    intro = next(item for item in state.sections if item.section_type == "introduction")
    (root / intro.content_path).write_text("# Introduction\n\nThis follows Smith et al. 2024.\n", encoding="utf-8")

    package = VenueRevisionPackageManager(config).create(benchmark_id)

    assert package.status == "no_go"
    assert any("citation-shaped" in item for item in package.limitations)


def test_venue_revision_package_includes_artifact_package(tmp_path: Path) -> None:
    config, project_id, benchmark_id, _manuscript_id = _venue_revision_fixture(tmp_path)

    package = VenueRevisionPackageManager(config).create(benchmark_id)
    package_dir = Path(config.project_root, project_id, "selected_benchmark", "venue_revision_package", package.id)

    assert package.artifact_package_id
    assert (package_dir / "artifact_evaluation_package" / "artifact_evaluation_package.json").exists()
    assert any(path.startswith("artifact_evaluation_package/") for path in package.files)


def test_venue_revision_report_renders_and_cli(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, _manuscript_id = _venue_revision_fixture(tmp_path)
    package = VenueRevisionPackageManager(config).create(benchmark_id)

    rendered = render_venue_revision_package(package)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-venue-revision-status", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Venue Revision Package" in rendered
    assert "Package Boundary" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Venue Revision Package" in cli.stdout
    assert "workshop_candidate" in cli.stdout


def _venue_revision_fixture(tmp_path: Path):
    config, project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    _add_artifact_package(config, manuscript_id)
    return config, project_id, benchmark_id, manuscript_id
