from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.evals.benchmark import run_evals
from gapforge.evals.fixtures import FIXTURE_NAMES, list_fixtures, load_fixture


def test_eval_fixtures_are_complete() -> None:
    names = list_fixtures()
    assert set(FIXTURE_NAMES).issubset(names)
    for name in FIXTURE_NAMES:
        fixture = load_fixture(name)
        assert fixture.topic
        assert fixture.papers
        assert fixture.paper_notes
        assert fixture.known_good_gaps
        assert fixture.known_bad_gaps
        assert fixture.duplicate_ideas
        assert fixture.expected_reviewer_objections


def test_run_evals_single_fixture_writes_report(tmp_path: Path) -> None:
    report = run_evals(fixture="low_fpr_collusion", output_dir=tmp_path, write_report=True)

    assert report.report_path == tmp_path / "eval_report.md"
    assert report.report_path.exists()
    text = report.report_path.read_text(encoding="utf-8")
    assert "gap_specificity_score" in text
    assert "Unsupported Claims" in text
    assert "Novelty Gate Failures" in text
    assert len(report.results) == 1
    result = report.results[0]
    assert result.scores.novelty_gate_accuracy == 1.0
    assert result.scores.duplicate_detection_rate > 0
    assert result.unsupported_claims
    assert result.missing_baselines


def test_run_evals_all_fixtures_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(output_dir=tmp_path, write_report=True)

    assert len(report.results) >= 4
    assert report.overall_score > 0
    assert all(result.accepted_gaps for result in report.results)
    assert any(result.rejected_gaps for result in report.results)


def test_eval_cli_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "low_fpr_collusion", "--write-report"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "eval_report.md" in result.stdout
    report_path = Path.cwd() / "eval_report.md"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "low_fpr_collusion" in text
    report_path.unlink()


def test_fixture_duplicate_ideas_are_intentionally_rejected() -> None:
    report = run_evals(fixture="quantum_portfolio_optimization", write_report=False)
    result = report.results[0]

    assert result.scores.novelty_gate_accuracy == 1.0
    assert "dup-qpo-1" in result.rejected_gaps
