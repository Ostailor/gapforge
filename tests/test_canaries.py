from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.canaries import CanaryReviewManager, CanaryRunManager, default_canary_profiles
from gapforge.config import GapForgeConfig


def test_list_profiles_includes_required_canaries() -> None:
    profile_ids = {profile.id for profile in default_canary_profiles()}

    assert "low_fpr_collusion_codex" in profile_ids
    assert "manual_pdf_fulltext_codex" in profile_ids
    assert "undercovered_topic_refusal" in profile_ids
    assert "fake_agent_regression" in profile_ids


def test_plan_fake_and_real_profiles(tmp_path: Path) -> None:
    manager = CanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    fake_plan = manager.plan("fake_agent_regression")
    real_plan = manager.plan("low_fpr_collusion_codex")

    assert "Fake AgentClient regression canary" in fake_plan
    assert "Codex/GPT-5.4" in real_plan
    assert "Pass Criteria" in real_plan
    assert "Expected Artifacts" in real_plan


def test_fake_canary_runs_offline_and_persists_record(tmp_path: Path) -> None:
    manager = CanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("fake_agent_regression")

    assert record.status == "complete"
    assert record.run_id
    assert record.validation_summary["validation_status"] == "valid"
    loaded = manager.load_record(record.id)
    assert loaded.id == record.id
    artifacts = manager.artifact_paths(record.id)
    assert any(path.endswith("record.json") for path in artifacts)
    assert any(path.endswith("TASK.md") for path in artifacts)


def test_real_profile_refuses_without_real_run_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    manager = CanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("low_fpr_collusion_codex", real=True)

    assert record.status == "failed"
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in record.validation_summary["reason"]
    assert record.validation_summary["counts_as_actual_run"] is False


def test_canary_cli_list_plan_run_status_artifacts(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert "fake_agent_regression" in listed.stdout

    plan = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-plan", "--profile", "low_fpr_collusion_codex"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert plan.returncode == 0, plan.stderr
    assert "Canary Plan" in plan.stdout

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-run", "--profile", "fake_agent_regression"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["status"] == "complete"

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-status", "--canary-id", payload["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["id"] == payload["id"]

    artifacts = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-artifacts", "--canary-id", payload["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert artifacts.returncode == 0, artifacts.stderr
    assert "record.json" in artifacts.stdout


def test_review_form_renders(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = CanaryRunManager(config).run("fake_agent_regression")

    form = CanaryReviewManager(config).render_form(record.id)

    assert "Did it find real sources?" in form
    assert "Did every high-confidence claim have evidence?" in form
    assert "gapforge canary-review" in form


def test_accept_valid_canary_review(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    run_manager = CanaryRunManager(config)
    record = run_manager.run("fake_agent_regression")

    review, summary = CanaryReviewManager(config).review(
        record.id,
        reviewer="Test Reviewer",
        accept=True,
        source_coverage_score=3,
        full_text_grounding_score=3,
        citation_grounding_score=3,
        novelty_honesty_score=3,
        gap_quality_score=3,
        experiment_quality_score=3,
        uncertainty_visibility_score=3,
        strict_report_behaved_correctly=True,
    )

    assert review.accepted is True
    assert summary.passed is True
    loaded = run_manager.load_record(record.id)
    assert loaded.status == "accepted"
    assert loaded.human_review_id == review.id
    assert (config.data_dir / "canaries" / record.id / "human_review.json").exists()
    assert (config.data_dir / "canaries" / record.id / "acceptance_summary.json").exists()
    assert (config.data_dir / "canaries" / record.id / "review_report.md").exists()


def test_reject_canary_with_fake_citation(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = CanaryRunManager(config).run("fake_agent_regression")

    review, summary = CanaryReviewManager(config).review(
        record.id,
        reviewer="Test Reviewer",
        accept=True,
        fake_citation_found=True,
        strict_report_behaved_correctly=True,
    )

    assert review.accepted is False
    assert summary.passed is False
    assert "Fake citation found." in summary.blocking_failures


def test_reject_canary_with_unsupported_high_confidence_claim(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = CanaryRunManager(config).run("fake_agent_regression")

    _, summary = CanaryReviewManager(config).review(
        record.id,
        reviewer="Test Reviewer",
        accept=True,
        unsupported_high_confidence_claim_found=True,
        strict_report_behaved_correctly=True,
    )

    assert summary.passed is False
    assert "Unsupported high-confidence claim found." in summary.blocking_failures


def test_real_run_acceptance_reports_missing_review_as_not_passed(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    CanaryRunManager(config).run("fake_agent_regression")

    payload = CanaryReviewManager(config).real_run_acceptance()

    assert payload["passed"] is False
    assert "No human-reviewed actual Codex/GPT-5.4 canary has been accepted." in payload["missing"]


def test_canary_review_cli_accept_reject_and_summary(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-run", "--profile", "fake_agent_regression"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    canary_id = json.loads(run.stdout)["id"]

    form = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-review", "--canary-id", canary_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert form.returncode == 0
    assert "Canary Human Review" in form.stdout

    reject = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "canary-review",
            "--canary-id",
            canary_id,
            "--reject",
            "--reason",
            "fixture rejection",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert reject.returncode == 1
    assert "fixture rejection" in reject.stdout

    summary = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "canary-summary", "--canary-id", canary_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert summary.returncode == 1
    assert json.loads(summary.stdout)["release_gate_status"] == "not_passed"

    gate = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "real-run-acceptance"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert gate.returncode == 1
    assert json.loads(gate.stdout)["passed"] is False
