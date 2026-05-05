from __future__ import annotations

from pathlib import Path

import gapforge.models as gf_models
from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate import parse_release_gate
from gapforge.release_gate.v04 import V04ReleaseGateEnforcer
from gapforge.state import ResearchStateManager


def test_v030_release_gate_reports_actual_run_not_completed() -> None:
    gate = parse_release_gate(Path(__file__).resolve().parents[1] / "docs" / "releases" / "v0.3.0-real-run-acceptance.md")

    assert gate.version == "0.3.0"
    assert gate.actual_run_acceptance == "not_completed"
    assert gate.actual_run_acceptance_passed is False
    assert gate.accepted_real_canary_count == 0
    assert gate.passed is False
    assert {item["profile_id"] for item in gate.real_canaries} == {
        "low_fpr_collusion_codex",
        "manual_pdf_fulltext_codex",
    }


def test_release_gate_requires_accepted_real_canary(tmp_path: Path) -> None:
    path = tmp_path / "release.md"
    path.write_text(
        """---
{
  "version": "0.3.0",
  "actual_run_acceptance": "passed",
  "actual_run_acceptance_passed": true,
  "accepted_real_canary_count": 0,
  "real_canaries": []
}
---
# Release
""",
        encoding="utf-8",
    )

    assert parse_release_gate(path).passed is False


def test_v04_release_gate_no_campaigns_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert "No campaigns were found" in " ".join(result.blockers)


def test_v04_release_gate_fake_campaigns_only_fail_actual_run_gate(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "fake only", mode="fake_agent", ready=True)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert any("Fake-agent campaigns cannot count" in blocker for campaign in result.campaigns for blocker in campaign.blockers)


def test_v04_release_gate_below_real_campaign_threshold_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "real one", ready=True, full_text=True)
    _accepted_campaign(config, "real two", refusal=True, stop_reason="not_ready_poor_coverage")

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert any("At least 3 accepted real" in blocker for blocker in result.blockers)


def test_v04_release_gate_accepted_campaign_with_blockers_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "blocked", ready=True, retrieval=False)
    _accepted_campaign(config, "ok refusal", refusal=True, stop_reason="not_ready_novelty_unknown")
    _accepted_campaign(config, "ok full text", ready=True, full_text=True)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert any("Retrieval index is missing" in blocker for blocker in result.blockers)


def test_v04_release_gate_required_campaign_mix_passes_and_report_renders(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "experiment ready", ready=True)
    _accepted_campaign(config, "coverage refusal", refusal=True, stop_reason="not_ready_poor_coverage")
    _accepted_campaign(config, "manual pdf full text", ready=True, full_text=True)

    enforcer = V04ReleaseGateEnforcer(config)
    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)

    assert result.passed is True
    assert len(result.accepted_real_campaign_ids) == 3
    assert result.experiment_ready_campaign_present is True
    assert result.refusal_campaign_present is True
    assert result.full_text_campaign_present is True
    assert json_path.exists()
    assert md_path.exists()
    assert "Passed: true" in md_path.read_text(encoding="utf-8")


def _write_ci_and_fake_canary(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true, "commands": ["make ci"]}\n', encoding="utf-8")
    canary_dir = config.data_dir / "campaign_canaries" / "fake"
    canary_dir.mkdir(parents=True, exist_ok=True)
    (canary_dir / "record.json").write_text(
        """{
  "id": "campaign-canary-fake",
  "profile_id": "fake_agent_campaign_regression",
  "status": "complete",
  "actual_run_status": "fake_not_actual",
  "human_review_status": "not_required",
  "accepted": true
}
""",
        encoding="utf-8",
    )


def _accepted_campaign(
    config: GapForgeConfig,
    name: str,
    *,
    mode: str = "codex_task_pack",
    ready: bool = False,
    refusal: bool = False,
    full_text: bool = False,
    retrieval: bool = True,
    stop_reason: str = "ready_experiment_protocol",
) -> str:
    project_manager = ProjectMemoryManager(config)
    state_manager = ResearchStateManager(config)
    campaign_manager = CampaignManager(config)
    program = project_manager.create_project(f"Gate {name}")
    run = state_manager.create_run(f"Gate topic {name}")
    run.papers.append(gf_models.Paper(id=f"paper-{name}", title=f"Paper {name}", authors=["A"], abstract="A", year=2026))
    run.source_coverage = gf_models.SourceCoverageReport(
        run_id=run.run_id,
        topic=run.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 1},
        papers_with_full_text=[f"paper-{name}"] if full_text else [],
        confidence="medium",
    )
    run.novelty_dossiers.append(
        gf_models.NoveltyDossier(
            target_id=f"gap-{name}",
            idea_summary="Gate fixture novelty.",
            top_prior_work=[f"paper-{name}"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    )
    if full_text:
        run.paper_sections.append(
            gf_models.PaperSection(id=f"section-{name}", paper_id=f"paper-{name}", title="Abstract", text="Full text.")
        )
    state_manager.save_run(run)
    project_manager.attach_run(program.project.id, run.run_id)
    program = project_manager.sync_project_memory(program.project.id)
    if ready:
        program.research_directions.append(
            gf_models.ResearchDirection(
                id=f"direction-{name}",
                project_id=program.project.id,
                title=f"Direction {name}",
                linked_gap_ids=[f"gap-{name}"],
                maturity="experiment_ready",
            )
        )
    project_manager.save_project(program)
    if retrieval:
        retrieval_dir = Path(program.project.root_dir) / "retrieval"
        retrieval_dir.mkdir(parents=True, exist_ok=True)
        (retrieval_dir / "manifest.json").write_text('{"document_count": 1}\n', encoding="utf-8")
    campaign = campaign_manager.create_campaign(
        f"Campaign {name}", project_id=program.project.id, mode=mode, agent_name="codex", model="gpt-5.4"
    )
    campaign = campaign_manager.attach_run(campaign.campaign.id, run.run_id)
    campaign = campaign_manager.stop_campaign(campaign.campaign.id, reason=stop_reason if not refusal else stop_reason)
    campaign.imports.append(
        gf_models.CampaignImportRecord(
            id=f"import-{name}",
            campaign_id=campaign.campaign.id,
            task_id=f"task-{name}",
            status="applied",
            accepted_objects=[
                {"type": "novelty_dossier", "id": f"dossier-{name}", "source_path": "outputs/novelty_dossiers_patch.json"},
                {"type": "agent_actual_run_attestation", "id": f"attestation-{name}", "accepted": True},
            ],
        )
    )
    campaign.human_reviews.append(
        gf_models.CampaignHumanReview(id=f"review-{name}", campaign_id=campaign.campaign.id, reviewer="tester", accepted=True)
    )
    campaign.acceptance_summary = gf_models.CampaignAcceptanceSummary(
        campaign_id=campaign.campaign.id,
        accepted=True,
        actual_run_attestation_present=True,
        accepted_real_agent_outputs=[f"import-{name}"],
        release_gate_eligible=True,
    )
    campaign_manager.save_campaign_state(campaign)
    return campaign.campaign.id
