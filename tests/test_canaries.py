from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.acceptance import create_campaign_actual_run_attestation
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.canaries import CampaignCanaryRunManager, CanaryReviewManager, CanaryRunManager, default_canary_profiles
from gapforge.config import GapForgeConfig


def test_list_profiles_includes_required_canaries() -> None:
    profile_ids = {profile.id for profile in default_canary_profiles()}

    assert "low_fpr_collusion_codex" in profile_ids
    assert "manual_pdf_fulltext_codex" in profile_ids
    assert "undercovered_topic_refusal" in profile_ids
    assert "fake_agent_regression" in profile_ids


def test_campaign_canary_profiles_include_required_v4_profiles(tmp_path: Path) -> None:
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))
    profile_ids = {profile.id for profile in manager.list_profiles()}

    assert "agentic_low_fpr_collusion" in profile_ids
    assert "agentic_monitor_evasion" in profile_ids
    assert "agentic_cross_domain_specificity" in profile_ids
    assert "agentic_undercovered_refusal" in profile_ids
    assert "manual_pdf_agentic" in profile_ids
    assert "fake_agent_campaign_regression" in profile_ids
    assert "single_task_codex_handoff" in profile_ids
    assert "single_task_fake_handoff_regression" in profile_ids
    assert "manual_pdf_codex_reading_handoff" in profile_ids
    assert "manual_pdf_fake_reading_regression" in profile_ids


def test_campaign_canary_plan_includes_commands_and_acceptance_criteria(tmp_path: Path) -> None:
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    plan = manager.plan("agentic_low_fpr_collusion")

    assert "Campaign Canary Plan" in plan
    assert "gapforge campaign-canary-run" in plan
    assert "Acceptance Criteria" in plan
    assert "novelty dossier" in plan.lower()


def test_fake_campaign_canary_runs_offline_and_persists_record(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("fake_agent_campaign_regression")

    assert record.status == "complete"
    assert record.accepted is True
    assert record.campaign_id
    assert record.project_id
    assert record.actual_run_status == "fake_not_actual"
    assert record.artifacts
    loaded = manager.load_record(record.id)
    assert loaded.id == record.id


def test_single_task_fake_handoff_regression_passes_ci(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("single_task_fake_handoff_regression")

    assert record.status == "complete"
    assert record.accepted is True
    assert record.actual_run_status == "fake_not_actual"
    campaign_state = CampaignManager(manager.config).load_campaign_state(record.campaign_id)
    assert campaign_state.imports
    assert campaign_state.agent_actual_run_attestations
    assert campaign_state.agent_actual_run_attestations[-1].agent_name == "fake"


def test_manual_pdf_fake_reading_regression_passes_ci(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("manual_pdf_fake_reading_regression")

    assert record.status == "complete"
    assert record.accepted is True
    assert record.actual_run_status == "fake_not_actual"
    campaign_state = CampaignManager(manager.config).load_campaign_state(record.campaign_id)
    assert any(
        item.task_id.endswith("deep_reader_batch") and item.status in {"applied", "partial", "valid"} for item in campaign_state.imports
    )


def test_single_task_real_handoff_refuses_without_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("single_task_codex_handoff", real=True)

    assert record.status == "failed"
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in record.failure_reason


def test_manual_pdf_reading_real_handoff_refuses_without_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("manual_pdf_codex_reading_handoff", real=True)

    assert record.status == "failed"
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in record.failure_reason


def test_single_task_real_handoff_creates_copy_paste_bundle(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("single_task_codex_handoff", real=True)

    assert record.status == "planned"
    assert record.actual_run_status == "manual_handoff_pending"
    campaign_state = CampaignManager(manager.config).load_campaign_state(record.campaign_id)
    assert campaign_state.campaign.status == "paused"
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    assert task_pack.name == task_id
    assert (task_pack / "CODEX_PROMPT.md").exists()
    assert (task_pack / "VALIDATE_AND_IMPORT.sh").exists()
    assert "outputs" in (task_pack / "CODEX_PROMPT.md").read_text(encoding="utf-8")


def test_manual_pdf_reading_handoff_creates_deep_reading_task(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("manual_pdf_codex_reading_handoff", real=True)

    assert record.status == "planned"
    assert record.actual_run_status == "manual_handoff_pending"
    campaign_state = CampaignManager(manager.config).load_campaign_state(record.campaign_id)
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    assert task_id.endswith("deep_reader_batch")
    assert "paper_notes_patch.json" in (task_pack / "CODEX_PROMPT.md").read_text(encoding="utf-8")


def test_single_task_completion_fails_until_import_attestation_review(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))
    record = manager.run("single_task_codex_handoff", real=True)

    incomplete = manager.complete(record.id)

    assert incomplete.accepted is False
    assert "Validated import is missing." in incomplete.failure_reason
    assert "attestation" in incomplete.failure_reason.lower()
    assert "Human campaign review acceptance is missing." in incomplete.failure_reason


def test_manual_pdf_reading_invalid_locator_fails_validation(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = CampaignCanaryRunManager(config)
    record = manager.run("manual_pdf_codex_reading_handoff", real=True)
    campaign_state = CampaignManager(config).load_campaign_state(record.campaign_id)
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    _write_fixture_reading_output(task_pack, locator="missing-span")

    import_record = CampaignOutputImporter(config).import_outputs(record.campaign_id, task_id, [])

    assert import_record.status == "rejected"
    assert any("unknown evidence_span_id: missing-span" in issue for issue in import_record.issues)


def test_manual_pdf_reading_review_blocks_missing_attestation(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = CampaignCanaryRunManager(config)
    record = manager.run("manual_pdf_codex_reading_handoff", real=True)
    campaign_state = CampaignManager(config).load_campaign_state(record.campaign_id)
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    _write_fixture_reading_output(task_pack)
    CampaignOutputImporter(config).import_outputs(record.campaign_id, task_id, [])
    CampaignReviewManager(config).review(record.campaign_id, accept=True, reviewer="Reviewer")

    completed = manager.complete(record.id)

    assert completed.accepted is False
    assert "Codex/GPT-5.4 attestation is missing." in completed.failure_reason


def test_manual_pdf_reading_valid_fixture_output_passes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = CampaignCanaryRunManager(config)
    record = manager.run("manual_pdf_codex_reading_handoff", real=True)
    campaign_manager = CampaignManager(config)
    campaign_state = campaign_manager.load_campaign_state(record.campaign_id)
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    _write_fixture_reading_output(task_pack, include_claim=True)
    import_record = CampaignOutputImporter(config).import_outputs(record.campaign_id, task_id, [])
    assert import_record.status == "partial"
    campaign_state = campaign_manager.load_campaign_state(record.campaign_id)
    create_campaign_actual_run_attestation(
        campaign_state,
        task_id,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="Reviewer",
    )
    campaign_manager.save_campaign_state(campaign_state)
    CampaignReviewManager(config).review(record.campaign_id, accept=True, reviewer="Reviewer")

    completed = manager.complete(record.id)

    assert completed.status == "accepted"
    assert completed.accepted is True
    assert completed.actual_run_status == "accepted"


def test_single_task_completion_passes_after_simulated_codex_flow(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_ENABLE_REAL_RUNS", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = CampaignCanaryRunManager(config)
    record = manager.run("single_task_codex_handoff", real=True)
    campaign_manager = CampaignManager(config)
    campaign_state = campaign_manager.load_campaign_state(record.campaign_id)
    task_id = campaign_state.campaign.task_ids[-1]
    task_pack = next(Path(path).parent for path in record.artifacts if path.endswith("CAMPAIGN_TASK.md"))
    (task_pack / "outputs" / "novelty_dossiers_patch.json").write_text(
        json.dumps(
            {
                "novelty_dossiers_patch": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "Fixture Codex output marks novelty unknown.",
                        "top_prior_work": [],
                        "comparison_table": [],
                        "verdict": "unknown",
                        "novelty_strength": "unknown",
                        "confidence": "low",
                        "missing_searches": ["fixture canary does not run external searches"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    CampaignOutputImporter(config).import_outputs(record.campaign_id, task_id, [])
    campaign_state = campaign_manager.load_campaign_state(record.campaign_id)
    create_campaign_actual_run_attestation(
        campaign_state,
        task_id,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="Reviewer",
    )
    campaign_manager.save_campaign_state(campaign_state)
    CampaignReviewManager(config).review(record.campaign_id, accept=True, reviewer="Reviewer")

    completed = manager.complete(record.id)

    assert completed.status == "accepted"
    assert completed.accepted is True
    assert completed.actual_run_status == "accepted"


def _write_fixture_reading_output(
    task_pack: Path,
    *,
    locator: str = "paper-1:Abstract:p1",
    include_claim: bool = False,
) -> None:
    outputs_dir = task_pack / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "paper_notes_patch.json").write_text(
        json.dumps(
            {
                "paper_notes_patch": [
                    {
                        "paper_id": "paper-1",
                        "source_basis": "fixture full text",
                        "one_sentence_summary": "Fixture section supports a workflow-only reading note.",
                        "main_claims": ["Fixture section exists for canary validation."],
                        "main_results": [],
                        "limitations": ["Fixture-only content is not real literature evidence."],
                        "evidence_locators": [locator],
                        "confidence": "medium",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    if include_claim:
        (outputs_dir / "claims_patch.json").write_text(
            json.dumps(
                {
                    "claims_patch": [
                        {
                            "id": "claim-fixture-reading",
                            "paper_id": "paper-1",
                            "text": "Fixture section exists for canary validation.",
                            "status": "supported",
                            "confidence": "medium",
                            "evidence_locators": [locator],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )


def test_real_campaign_canary_refuses_without_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("agentic_low_fpr_collusion", real=True)

    assert record.status == "failed"
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in record.failure_reason
    assert record.accepted is False


def test_campaign_undercovered_refusal_can_pass_by_refusing_recommendation(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = CampaignCanaryRunManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("agentic_undercovered_refusal")

    assert record.status == "complete"
    assert record.accepted is True
    assert record.actual_run_status == "not_applicable"


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


def test_campaign_canary_cli_list_plan_run_status(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-canary-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert "fake_agent_campaign_regression" in listed.stdout

    plan = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-canary-plan", "--profile", "agentic_low_fpr_collusion"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert plan.returncode == 0, plan.stderr
    assert "Campaign Canary Plan" in plan.stdout

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-canary-run", "--profile", "fake_agent_campaign_regression"],
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
        [sys.executable, "-m", "gapforge.cli", "campaign-canary-status", "--canary-id", payload["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["id"] == payload["id"]


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
