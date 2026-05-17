from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_manuscripts import _project
from test_selected_benchmark import _env

from gapforge.external_review import ExternalExpertReviewManager
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.top_conference_revision import TopConferenceRevisionManager


def test_external_human_review_is_captured_without_conflating_simulation(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    manager = ExternalExpertReviewManager(config)

    human = manager.add_review(
        manuscript_id,
        reviewer_role="external expert",
        expertise_area="benchmark evaluation",
        overall_recommendation="weak_reject",
        key_strengths=["important problem"],
        key_weaknesses=["benchmark validity needs sharper grounding"],
        missing_experiments=["real-benchmark sanity check"],
        claim_overreach=["synthetic run is framed too strongly"],
        required_revisions=["add no-fit table"],
        notes=["human reviewer; not simulated"],
        source="human",
    )
    simulated = manager.add_review(
        manuscript_id,
        reviewer_role="simulated reviewer",
        expertise_area="paper review simulation",
        overall_recommendation="borderline",
        notes=["simulated review"],
        source="simulated",
    )
    report = manager.report(manuscript_id)

    assert human.provenance.created_by_skill == "external-expert-review-human"
    assert simulated.provenance.created_by_skill == "external-expert-review-simulated"
    assert "Human External Reviews" in report
    assert "Simulated External Reviews" in report
    assert "not conflated" in report
    assert "synthetic run is framed too strongly" in report


def test_fatal_external_review_blocks_conference_candidate_until_resolved(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    manager = ExternalExpertReviewManager(config)

    manager.add_review(
        manuscript_id,
        reviewer_role="external expert",
        expertise_area="statistics",
        overall_recommendation="reject",
        claim_overreach=["unsupported alpha claim"],
        required_revisions=["remove or support alpha claim"],
        source="human",
    )
    status = manager.status(manuscript_id)

    assert status["conference_candidate_allowed"] is False
    assert status["unresolved_fatal_external_review_count"] == 1
    assert any("reject" in blocker.lower() for blocker in status["blockers"])
    readiness = TopConferenceRevisionManager(config).readiness(manuscript_id)
    assert any("External human review" in blocker for blocker in readiness.blockers)
    assert readiness.conference_candidate_allowed is False


def test_external_review_cli_add_and_report(tmp_path: Path) -> None:
    _config, manuscript_id = _manuscript_fixture(tmp_path)

    add = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "external-review-add",
            "--manuscript-id",
            manuscript_id,
            "--reviewer-role",
            "external expert",
            "--expertise-area",
            "AI safety",
            "--overall-recommendation",
            "weak_accept",
            "--key-strength",
            "clear artifact package",
            "--required-revision",
            "tighten related work",
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "external-review-report", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert add.returncode == 0, add.stderr
    payload = json.loads(add.stdout)
    assert payload["manuscript_id"] == manuscript_id
    assert payload["overall_recommendation"] == "weak_accept"
    assert report.returncode == 0, report.stderr
    assert "External Expert Review Report" in report.stdout
    assert "clear artifact package" in report.stdout


def test_external_review_report_handles_missing_reviews(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    manager = ExternalExpertReviewManager(config)

    report = manager.report(manuscript_id)

    assert "External Expert Review Report" in report
    assert "- Total reviews: 0" in report
    assert "- none" in report
    assert manager.report_path(manuscript_id).exists()


def _manuscript_fixture(tmp_path: Path) -> tuple[object, str]:
    config, project_id = _project(tmp_path)
    state = ManuscriptManager(config).create_manuscript(
        project_id=project_id,
        direction_id="direction-external-review",
        workspace_id="workspace-external-review",
        title="External Review Draft",
    )
    return config, state.manuscript.id
