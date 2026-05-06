from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import gapforge.models as gf_models
from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature.review import RealLiteratureReviewManager
from gapforge.release_gate import parse_release_gate
from gapforge.release_gate.v04 import V04ReleaseGateEnforcer
from gapforge.release_gate.v05 import V05ReleaseGateEnforcer
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
    assert "missing_real_campaigns" in result.blocker_categories
    assert any("single_task_codex_handoff" in command for command in result.next_commands)


def test_v04_release_gate_fake_campaigns_only_fail_actual_run_gate(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "fake only", mode="fake_agent", ready=True)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert any("Fake-agent campaigns cannot count" in blocker for campaign in result.campaigns for blocker in campaign.blockers)
    assert any("fake-agent" in command.lower() or "single_task_codex_handoff" in command for command in result.next_commands)
    assert "Fake-agent canaries validate" in result.fake_vs_real_explanation


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


def test_v04_release_gate_missing_attestation_shows_command(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    campaign_id = _accepted_campaign(config, "missing attestation", ready=True, full_text=True)
    campaign_manager = CampaignManager(config)
    campaign = campaign_manager.load_campaign_state(campaign_id)
    for record in campaign.imports:
        record.accepted_objects = [item for item in record.accepted_objects if item.get("type") != "agent_actual_run_attestation"]
    campaign_manager.save_campaign_state(campaign)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert any("Actual-run attestation is missing" in blocker for blocker in result.blockers)
    assert "missing_attestation" in result.blocker_categories
    assert any("attest-agent-run" in command for command in result.next_commands)


def test_v04_release_gate_missing_manual_pdf_campaign_shows_command(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "experiment ready", ready=True)
    _accepted_campaign(config, "coverage refusal", refusal=True, stop_reason="not_ready_poor_coverage")
    _accepted_campaign(config, "another ready", ready=True)

    result = V04ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert "manual PDF/full-text campaign" in result.missing_campaign_types
    assert any("manual_pdf_codex_reading_handoff" in command for command in result.next_commands)


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


def test_v04_release_gate_explain_and_next_commands_cli(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v4-release-gate", "--explain", "--next-commands"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "single_task_codex_handoff" in result.stdout


def test_v05_release_gate_no_live_campaigns_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _accepted_campaign(config, "experiment ready", ready=True)
    _accepted_campaign(config, "coverage refusal", refusal=True, stop_reason="not_ready_poor_coverage")
    _accepted_campaign(config, "manual pdf full text", ready=True, full_text=True)

    result = V05ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.live_literature_campaign_count == 0
    assert any("At least 3 live-literature campaigns" in blocker for blocker in result.blockers)


def test_v05_release_gate_workflow_only_campaigns_fail_quality_gate(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _quality_campaign(config, "workflow one", ready=True, accept_quality=False)
    _quality_campaign(config, "workflow refusal", refusal=True, stop_reason="not_ready_poor_coverage", accept_quality=False)
    _quality_campaign(config, "workflow full text", ready=True, full_text=True, accept_quality=False)

    result = V05ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.live_literature_campaign_count == 3
    assert result.quality_accepted_campaign_ids == []
    assert any("At least 2 campaigns" in blocker for blocker in result.blockers)


def test_v05_release_gate_quality_accepted_campaigns_pass_and_report_renders(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    ready_id = _quality_campaign(config, "quality ready", ready=True, accept_quality=True)
    refusal_id = _quality_campaign(
        config,
        "quality refusal",
        refusal=True,
        stop_reason="not_ready_poor_coverage",
        accept_quality=True,
    )
    _quality_campaign(config, "quality full text", ready=True, full_text=True, accept_quality=False)

    enforcer = V05ReleaseGateEnforcer(config)
    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)

    assert result.passed is True
    assert set(result.quality_accepted_campaign_ids) == {ready_id, refusal_id}
    assert result.refusal_campaign_present is True
    assert result.experiment_ready_campaign_present is True
    assert json_path.exists()
    assert "Passed: true" in md_path.read_text(encoding="utf-8")


def test_v05_release_gate_fake_citation_blocks_quality_campaign(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    campaign_id = _quality_campaign(config, "quality fake", ready=True, accept_quality=True, force_fake_citation=True)
    _quality_campaign(config, "quality refusal", refusal=True, stop_reason="not_ready_poor_coverage", accept_quality=True)
    _quality_campaign(config, "quality full text", ready=True, full_text=True, accept_quality=False)

    result = V05ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    fake_assessment = next(item for item in result.campaigns if item.campaign_id == campaign_id)
    assert fake_assessment.fake_citation_found is True
    assert any("fake citation" in blocker.lower() for blocker in result.blockers)


def test_v05_release_gate_refusal_campaign_can_satisfy_refusal_requirement(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_ci_and_fake_canary(config)
    _quality_campaign(config, "quality ready", ready=True, accept_quality=True)
    refusal_id = _quality_campaign(
        config,
        "undercovered refusal",
        refusal=True,
        stop_reason="not_ready_poor_coverage: correct refusal",
        accept_quality=True,
    )
    _quality_campaign(config, "quality full text", ready=True, full_text=True, accept_quality=False)

    result = V05ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert refusal_id in result.quality_accepted_campaign_ids
    assert result.refusal_campaign_present is True


def test_actual_run_status_campaign_and_project_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _accepted_campaign(config, "actual status", ready=True, full_text=True)
    project_id = CampaignManager(config).load_campaign_state(campaign_id).campaign.project_id
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    campaign_status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "actual-run-status", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    project_status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "actual-run-status", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert campaign_status.returncode == 0, campaign_status.stderr
    assert project_status.returncode == 0, project_status.stderr
    assert "accepted_real_output_count" in campaign_status.stdout
    assert "accepted_real_campaign_count" in project_status.stdout


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


def _quality_campaign(
    config: GapForgeConfig,
    name: str,
    *,
    ready: bool = False,
    refusal: bool = False,
    full_text: bool = False,
    accept_quality: bool = True,
    stop_reason: str = "ready_experiment_protocol",
    force_fake_citation: bool = False,
) -> str:
    campaign_id = _accepted_campaign(
        config,
        name,
        ready=ready,
        refusal=refusal,
        full_text=full_text,
        stop_reason=stop_reason,
    )
    campaign_manager = CampaignManager(config)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    campaign = campaign_manager.load_campaign_state(campaign_id)
    program = project_manager.load_project(campaign.campaign.project_id)
    run = state_manager.load_run(campaign.campaign.run_ids[0])
    run.search_strategies.append(
        gf_models.SearchStrategy(
            id=f"strategy-{name}",
            topic=run.topic.text,
            source_profile="ai_safety",
            primary_queries=["low false positive collusion"],
            closest_prior_work_queries=["low false positive collusion prior work"],
        )
    )
    run.search_rounds.extend(
        [
            gf_models.SearchRound(
                id=f"round-initial-{name}",
                strategy_id=f"strategy-{name}",
                round_type="initial",
                status="complete",
                result_paper_ids=[f"paper-{name}"],
            ),
            gf_models.SearchRound(
                id=f"round-novelty-{name}",
                strategy_id=f"strategy-{name}",
                round_type="novelty",
                status="complete",
                result_paper_ids=[f"paper-{name}"],
            ),
        ]
    )
    run.prior_work_recall_assessments.append(
        gf_models.PriorWorkRecallAssessment(
            id=f"recall-{name}",
            target_id=f"gap-{name}",
            completed_query_rounds=["initial", "novelty", "benchmark", "survey"],
            top_prior_work_ids=[f"paper-{name}"],
            recall_confidence="medium",
            novelty_allowed=True,
        )
    )
    state_manager.save_run(run)
    program.related_work_matrices.append(
        gf_models.RelatedWorkMatrix(
            direction_id=f"direction-{name}" if ready else f"gap-{name}",
            entries=[
                gf_models.RelatedWorkEntry(
                    direction_id=f"direction-{name}" if ready else f"gap-{name}",
                    paper_id=f"paper-{name}",
                    relationship="closest_prior_work",
                    relevance_score=0.8,
                    must_cite=True,
                )
            ],
            coverage_summary="Fixture related-work matrix.",
        )
    )
    project_manager.save_project(program)
    project_root = Path(program.project.root_dir)
    (project_root / "canonical_paper_identities.json").write_text(
        f'[{{"canonical_id": "paper-{name}", "title": "Paper {name}", "source_paper_ids": ["paper-{name}"]}}]\n',
        encoding="utf-8",
    )
    real_literature_root = config.data_dir / "real_literature" / f"record-{name}"
    real_literature_root.mkdir(parents=True, exist_ok=True)
    (real_literature_root / "record.json").write_text(
        f"""{{
  "id": "real-lit-{name}",
  "profile_id": "live_low_fpr_collusion",
  "campaign_id": "{campaign_id}",
  "project_id": "{program.project.id}",
  "run_ids": ["{run.run_id}"],
  "live_source_diagnostic_id": "diagnostic-{name}",
  "real_paper_count": 3,
  "fallback_paper_count": 0,
  "full_text_count": 1,
  "abstract_only_count": 2,
  "novelty_dossier_count": 1
}}
""",
        encoding="utf-8",
    )
    RealLiteratureReviewManager(config).review(
        campaign_id,
        accept_quality=accept_quality,
        reviewer="quality-tester",
        source_quality_score=4,
        paper_relevance_score=4,
        prior_work_recall_score=4,
        evidence_grounding_score=4,
        novelty_honesty_score=4,
        gap_importance_score=4,
        experiment_feasibility_score=4,
        reviewer_objection_quality_score=4,
        report_honesty_score=4,
    )
    if force_fake_citation:
        review_path = project_root / "campaigns" / campaign_id / "real_literature_reviews.json"
        reviews = json.loads(review_path.read_text(encoding="utf-8"))
        reviews[-1]["fake_citation_found"] = True
        reviews[-1]["accepted_for_workflow"] = True
        reviews[-1]["accepted_for_research_quality"] = True
        review_path.write_text(json.dumps(reviews, indent=2) + "\n", encoding="utf-8")
    return campaign_id
