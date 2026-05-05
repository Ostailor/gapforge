from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
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
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(REPO_ROOT / "src")},
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
    assert json.loads((run_dir / "config.json").read_text(encoding="utf-8"))["schema_version"] == 2


def test_run_writes_end_to_end_artifacts(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "run", "low false positive collusion detection")
    assert result.returncode == 0, result.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    expected = [
        "topic.md",
        "config.json",
        "state.json",
        "papers.json",
        "paper_artifacts.json",
        "paper_sections.json",
        "evidence_spans.json",
        "evidence_spans.md",
        "search_queries.json",
        "source_coverage.json",
        "source_coverage.md",
        "full_text_coverage.md",
        "citation_graph.json",
        "citation_graph.md",
        "related_work_expansion.md",
        "paper_notes.json",
        "paper_notes.md",
        "paper_ranking.json",
        "paper_ranking.md",
        "paper_triage.json",
        "paper_triage.md",
        "field_map.json",
        "field_map.md",
        "gaps.json",
        "gaps.md",
        "gap_evidence_matrix.json",
        "gap_evidence_matrix.md",
        "hypotheses.json",
        "cross_domain_analogies.json",
        "cross_domain_analogies.md",
        "cross_domain_transfers.json",
        "cross_domain_transfers.md",
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
        "human_reviews.json",
        "human_reviews.md",
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


def test_v2_dry_run_cli(tmp_path: Path) -> None:
    dry = run_cli(tmp_path, "run", "low false positive collusion detection", "--v2", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    plan = json.loads((run_dir / "orchestrator_plan.json").read_text(encoding="utf-8"))

    assert plan["dry_run"] is True
    assert [step["name"] for step in plan["steps"]][:6] == [
        "initialize-topic",
        "search-papers",
        "source-coverage",
        "map-literature",
        "triage-papers",
        "download-pdfs",
    ]
    assert any(step["name"] == "novelty-dossiers" for step in plan["steps"])


def test_v3_dry_run_cli(tmp_path: Path) -> None:
    dry = run_cli(
        tmp_path,
        "run",
        "low false positive collusion detection",
        "--v3",
        "--dry-run",
        "--project-id",
        "cli-v3-project",
        "--source-profile",
        "ai_safety",
        "--build-index",
    )
    assert dry.returncode == 0, dry.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    plan = json.loads((run_dir / "orchestrator_plan.json").read_text(encoding="utf-8"))
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))

    assert plan["dry_run"] is True
    assert config["v3"] is True
    assert config["project_id"] == "cli-v3-project"
    assert config["source_policy_profile"] == "ai_safety"
    assert any(step["name"] == "source-policy-assessment" for step in plan["steps"])
    assert any(step["name"] == "build-retrieval-index" for step in plan["steps"])
    assert any(step["name"] == "project-memory-sync" for step in plan["steps"])


def test_v2_offline_smoke_cli(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "run", "low false positive collusion detection", "--v2", "--max-papers", "8")

    assert result.returncode == 0, result.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    outcome = json.loads((run_dir / "orchestrator_result.json").read_text(encoding="utf-8"))
    coverage = json.loads((run_dir / "source_coverage.json").read_text(encoding="utf-8"))

    assert outcome["status"] == "complete"
    assert any("Network disabled" in warning for warning in coverage["coverage_warnings"])

    coverage_latest = run_cli(tmp_path, "coverage")
    assert coverage_latest.returncode == 0, coverage_latest.stderr
    assert "source_coverage.md" in coverage_latest.stdout
    refreshed_coverage = json.loads((run_dir / "source_coverage.json").read_text(encoding="utf-8"))
    assert any("Network disabled" in warning for warning in refreshed_coverage["coverage_warnings"])


def test_v3_offline_smoke_cli_with_project_and_index(tmp_path: Path) -> None:
    result = run_cli(
        tmp_path,
        "run",
        "low false positive collusion detection",
        "--v3",
        "--max-papers",
        "8",
        "--project-id",
        "cli-v3-project",
        "--build-index",
    )

    assert result.returncode == 0, result.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    outcome = json.loads((run_dir / "orchestrator_result.json").read_text(encoding="utf-8"))
    project = json.loads((tmp_path / "projects" / "cli-v3-project" / "project.json").read_text(encoding="utf-8"))

    assert outcome["status"] == "complete"
    assert run_dir.name in project["run_ids"]
    assert (run_dir / "retrieval" / "retrieval_coverage.md").exists()
    assert (run_dir / "review_queue.md").exists()


def test_v3_prompt_pack_cli_writes_agent_tasks(tmp_path: Path) -> None:
    result = run_cli(
        tmp_path,
        "run",
        "low false positive collusion detection",
        "--v3",
        "--max-papers",
        "8",
        "--mode",
        "prompt-pack",
        "--agent",
        "codex",
        "--model",
        "gpt-5.4",
        "--llm-novelty",
    )

    assert result.returncode == 0, result.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    report = (run_dir / "final_report.md").read_text(encoding="utf-8")

    assert state["config"]["run_mode"] == "prompt-pack"
    assert state["agent_task_specs"]
    assert any(record["status"] == "planned" for record in state["agent_run_records"])
    assert "Codex agent task packs:" in report


def test_v3_require_real_agent_cli_fails_without_env(tmp_path: Path) -> None:
    result = run_cli(
        tmp_path,
        "run",
        "low false positive collusion detection",
        "--v3",
        "--max-papers",
        "8",
        "--mode",
        "llm-assisted",
        "--agent",
        "codex",
        "--llm-novelty",
        "--require-real-agent",
    )

    assert result.returncode == 1
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    outcome = json.loads((run_dir / "orchestrator_result.json").read_text(encoding="utf-8"))
    assert outcome["status"] == "failed"


def test_v3_record_canary_cli(tmp_path: Path) -> None:
    result = run_cli(
        tmp_path,
        "run",
        "low false positive collusion detection",
        "--v3",
        "--max-papers",
        "8",
        "--record-canary",
        "--canary-profile",
        "fake_agent_regression",
    )

    assert result.returncode == 0, result.stderr
    canaries = list((tmp_path / "data" / "canaries").glob("*/canary_record.json"))
    assert canaries
    payload = json.loads(canaries[0].read_text(encoding="utf-8"))
    assert payload["profile_id"] == "fake_agent_regression"
    assert payload["run_id"]


def test_cache_info_cli(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "cache-info")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["entries"] == 0
    assert payload["cache_dir"].endswith(".gapforge_cache")
