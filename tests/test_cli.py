from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "gapforge.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "--help"],
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "init-topic" in result.stdout


def test_init_topic_creates_run_directory(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "init-topic", "low false positive collusion detection")
    assert result.returncode == 0, result.stderr
    run_dir = Path(result.stdout.strip())
    assert run_dir.exists()
    assert run_dir.parent == tmp_path / "runs"
    assert (run_dir / "topic.md").exists()
    assert "low false positive collusion detection" in (run_dir / "topic.md").read_text(encoding="utf-8")


def test_run_writes_end_to_end_artifacts(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "run", "low false positive collusion detection")
    assert result.returncode == 0, result.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    expected = [
        "topic.md",
        "config.json",
        "state.json",
        "papers.json",
        "paper_notes.json",
        "paper_notes.md",
        "paper_triage.json",
        "paper_triage.md",
        "field_map.json",
        "field_map.md",
        "gaps.json",
        "gaps.md",
        "hypotheses.json",
        "cross_domain_analogies.json",
        "cross_domain_analogies.md",
        "novelty_gate.json",
        "novelty_gate.md",
        "claims.json",
        "experiments.json",
        "experiments.md",
        "implementation_tasks.md",
        "reviewer_objections.json",
        "reviewer_summaries.json",
        "reviewer_simulation.md",
        "revised_experiment_recommendations.md",
        "orchestrator_plan.json",
        "orchestrator_result.json",
        "run_log.json",
        "rejected_ideas.json",
        "provenance.json",
        "run_report.md",
        "final_report.md",
    ]
    for filename in expected:
        assert (run_dir / filename).exists(), filename

    papers = json.loads((run_dir / "papers.json").read_text(encoding="utf-8"))
    claims = json.loads((run_dir / "claims.json").read_text(encoding="utf-8"))
    experiments = json.loads((run_dir / "experiments.json").read_text(encoding="utf-8"))
    assert len(papers) >= 5
    assert any(claim["type"] == "novelty" for claim in claims)
    assert experiments[0]["metrics"]
    report = (run_dir / "run_report.md").read_text(encoding="utf-8")
    for heading in [
        "## Field Map",
        "## Top Papers",
        "## Strongest Gaps",
        "## Novelty Assessments",
        "## Experiment Plans",
        "## Reviewer Objections",
        "## Claim Ledger Summary",
        "## Uncertainty",
    ]:
        assert heading in report

    validation = run_cli(tmp_path, "validate-state")
    assert validation.returncode == 0
    assert "State is valid" in validation.stdout

    status = run_cli(tmp_path, "status", "--run-id", run_dir.name)
    assert status.returncode == 0
    assert '"status": "complete"' in status.stdout

    final_report = (run_dir / "final_report.md").read_text(encoding="utf-8")
    assert "Recommended strongest direction" in final_report

    latest_report = run_cli(tmp_path, "report")
    assert latest_report.returncode == 0
    assert "final_report.md" in latest_report.stdout


def test_dry_run_and_resume_cli(tmp_path: Path) -> None:
    dry = run_cli(tmp_path, "run", "low false positive collusion detection", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    plan = json.loads((run_dir / "orchestrator_plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    assert all(step["status"] == "pending" for step in plan["steps"])

    resumed = run_cli(tmp_path, "resume", "--run-id", run_dir.name)
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads((run_dir / "orchestrator_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "complete"


def test_cache_info_cli(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "cache-info")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["entries"] == 0
    assert payload["cache_dir"].endswith(".gapforge_cache")
