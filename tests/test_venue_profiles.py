from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_manuscripts import _project

from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager
from gapforge.venues import VenueProfileManager, get_venue_profile, list_venue_profiles, render_venue_profile


def test_venue_profiles_list(tmp_path: Path) -> None:
    profiles = list_venue_profiles()
    ids = {profile.id for profile in profiles}
    env = _env()

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-profile-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert {
        "generic_ml_conference",
        "generic_ai_safety_workshop",
        "generic_systems_conference",
        "generic_dataset_benchmark_track",
        "generic_theory_workshop",
        "arxiv_preprint",
    } <= ids
    assert listed.returncode == 0, listed.stderr
    assert "Venue Profiles" in listed.stdout
    assert "generic_ml_conference" in listed.stdout


def test_venue_profile_renders_reviewer_expectations(tmp_path: Path) -> None:
    profile = get_venue_profile("generic_dataset_benchmark_track")
    rendered = render_venue_profile(profile)
    env = _env()
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-profile", "--venue", profile.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Reviewer Norms" in rendered
    assert "does not imply acceptance" in rendered
    assert "benchmark_protocol" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Venue Profile `generic_dataset_benchmark_track`" in cli.stdout


def test_manuscript_venue_profile_set(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)

    state = VenueProfileManager(config).set_profile(manuscript_id, "generic_ml_conference")
    saved = ManuscriptManager(config).load_state(manuscript_id)
    profile_path = ManuscriptManager(config).manuscript_root(manuscript_id) / "submission" / "venue_profile.json"

    assert state.manuscript.target_venue == "generic_ml_conference"
    assert saved.manuscript.target_venue == "generic_ml_conference"
    assert json.loads(profile_path.read_text(encoding="utf-8"))["paper_style"] == "empirical"


def test_missing_required_sections_block_checklist_for_profile(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    manager = ManuscriptManager(config)
    manager.create_section(manuscript_id=manuscript_id, section_type="abstract", title="Abstract", status="drafted")
    manager.create_section(manuscript_id=manuscript_id, section_type="introduction", title="Introduction", status="drafted")
    VenueProfileManager(config).set_profile(manuscript_id, "generic_dataset_benchmark_track")

    checklist = SubmissionChecklistManager(config).build(manuscript_id)

    assert checklist.status == "not_ready"
    assert checklist.venue_template_id == "generic_dataset_benchmark_track"
    assert checklist.checks["required_sections"].startswith("fail:")
    assert any("Required section `dataset` is missing for venue profile" in issue for issue in checklist.blocking_issues)
    assert any("Required section `benchmark_protocol` is missing for venue profile" in issue for issue in checklist.blocking_issues)


def test_manuscript_set_venue_profile_cli(tmp_path: Path) -> None:
    _config, manuscript_id = _manuscript_fixture(tmp_path)

    set_profile = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-set-venue-profile",
            "--manuscript-id",
            manuscript_id,
            "--venue",
            "generic_ai_safety_workshop",
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert set_profile.returncode == 0, set_profile.stderr
    assert json.loads(set_profile.stdout)["target_venue"] == "generic_ai_safety_workshop"


def _manuscript_fixture(tmp_path: Path):
    config, project_id = _project(tmp_path)
    state = ManuscriptManager(config).create_manuscript(
        project_id=project_id,
        direction_id="direction-venue",
        workspace_id="workspace-venue",
        title="Venue Profile Draft",
    )
    return config, state.manuscript.id


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
