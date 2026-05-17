from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_drastic_review_panel import _drastic_manuscript_fixture
from test_release_gate_v26 import _v26_fixture

from gapforge.release_gate.v26 import V26ReleaseGateEnforcer
from gapforge.reviewers.issue_tracker import ReviewIssueTracker


def test_review_issues_turn_drastic_review_into_checklist(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)

    issues = ReviewIssueTracker(config).build_from_drastic_review(manuscript_id)

    assert issues
    assert any(issue.severity == "fatal" for issue in issues)
    assert any("synthetic-only" in issue.text for issue in issues)
    assert all(issue.status == "open" for issue in issues)
    assert all(issue.required_fix for issue in issues)
    assert all(issue.affected_sections for issue in issues)
    assert (next((tmp_path / "projects").glob("*/manuscripts/*")) / "reviews" / "drastic" / "review_issues.json").exists()


def test_review_issue_resolution_requires_linked_evidence(tmp_path: Path) -> None:
    config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)
    tracker = ReviewIssueTracker(config)
    fatal_issue = next(issue for issue in tracker.build_from_drastic_review(manuscript_id) if issue.severity == "fatal")

    with pytest.raises(ValueError, match="artifact/manuscript/search/experiment"):
        tracker.resolve_issue(fatal_issue.id, evidence="fixed in prose")

    resolved = tracker.resolve_issue(
        fatal_issue.id,
        evidence="manuscript:limitations documents the synthetic-only boundary and removes real benchmark validity.",
    )
    status = tracker.status(manuscript_id)

    assert resolved.status == "resolved"
    assert resolved.resolution_evidence
    assert fatal_issue.id in status["closed_issue_ids"]
    assert fatal_issue.id not in status["open_fatal_issue_ids"]


def test_review_issue_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id = _drastic_manuscript_fixture(tmp_path, synthetic_only=True)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    issues_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-issues", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert issues_cli.returncode == 0, issues_cli.stderr
    assert "Review Issues" in issues_cli.stdout
    issue_payload = json.loads(next((tmp_path / "projects").glob("*/manuscripts/*/reviews/drastic/review_issues.json")).read_text())
    issue_ids = [issue["id"] for issue in issue_payload["issues"]]

    for issue_id in issue_ids:
        resolve_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "gapforge.cli",
                "resolve-review-issue",
                "--issue-id",
                issue_id,
                "--evidence",
                "artifact:package manifest maps the issue to reproduced outputs.",
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert resolve_cli.returncode == 0, resolve_cli.stderr
    status_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-issue-status", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status_cli.returncode == 0, status_cli.stderr
    assert "open_fatal_issues: 0" in status_cli.stdout


def test_conference_candidate_requires_issue_level_closure(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, package_status="conference_candidate", likely_decision="accept_likely", adapter_support="primary")
    manuscript_root = next((tmp_path / "projects").glob("*/manuscripts/*"))
    issue_dir = manuscript_root / "reviews" / "drastic"
    issue_dir.mkdir(parents=True, exist_ok=True)
    issue_path = issue_dir / "review_issues.json"
    issue_path.write_text(
        json.dumps(
            {
                "manuscript_id": manuscript_root.name,
                "issues": [
                    {
                        "id": "review-issue-open-fatal",
                        "source_review_id": "drastic-review-v26",
                        "issue_type": "benchmark_validity",
                        "severity": "fatal",
                        "text": "fatal benchmark-validity objection remains",
                        "affected_sections": ["experiments"],
                        "required_fix": "experiment: add benchmark-validity evidence",
                        "status": "open",
                        "resolution_evidence": [],
                        "provenance": {"created_by": "test"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.status != "conference_candidate"
    assert result.requirements["review_issue_level_closure"] is False
    assert any("open fatal review issues" in blocker for blocker in result.blockers)
