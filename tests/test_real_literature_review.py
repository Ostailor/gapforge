from __future__ import annotations

from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature.review import RealLiteratureReviewManager


def _campaign(config: GapForgeConfig, *, stop_reason: str = "") -> str:
    project = ProjectMemoryManager(config).create_project("Real Literature Review Project")
    state = CampaignManager(config).create_campaign(
        "low false positive collusion detection",
        project_id=project.project.id,
        mode="codex_task_pack",
        agent_name="codex",
        model="gpt-5.4",
        source_profile="ai_safety",
    )
    if stop_reason:
        CampaignManager(config).stop_campaign(state.campaign.id, reason=stop_reason)
    return state.campaign.id


def test_workflow_accepted_but_quality_rejected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _campaign(config)
    manager = RealLiteratureReviewManager(config)

    review, summary = manager.review(campaign_id, reviewer="tester")

    assert review.accepted_for_workflow is True
    assert review.accepted_for_research_quality is False
    assert summary["accepted_for_workflow"] is True
    assert summary["accepted_for_research_quality"] is False
    assert "Research-quality acceptance is not recorded." in summary["blocking_failures"]


def test_fake_citation_blocks_workflow_and_quality(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _campaign(config)

    review, summary = RealLiteratureReviewManager(config).review(
        campaign_id,
        accept_quality=True,
        fake_citation_found=True,
    )

    assert review.accepted_for_workflow is False
    assert review.accepted_for_research_quality is False
    assert "Fake citation found." in summary["blocking_failures"]


def test_missed_prior_work_blocks_quality_not_workflow(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _campaign(config)

    review, summary = RealLiteratureReviewManager(config).review(
        campaign_id,
        accept_quality=True,
        missed_obvious_prior_work=True,
    )

    assert review.accepted_for_workflow is True
    assert review.accepted_for_research_quality is False
    assert "Obvious prior work was missed." in summary["blocking_failures"]


def test_undercovered_refusal_can_be_quality_accepted(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _campaign(config, stop_reason="not_ready_poor_coverage: correctly refused recommendation")

    review, summary = RealLiteratureReviewManager(config).review(
        campaign_id,
        accept_quality=True,
        source_quality_score=3,
        novelty_honesty_score=5,
        report_honesty_score=5,
    )

    assert review.accepted_for_workflow is True
    assert review.accepted_for_research_quality is True
    assert summary["is_refusal_campaign"] is True
    assert summary["release_quality_eligible"] is True


def test_real_literature_review_report_renders(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    campaign_id = _campaign(config)
    manager = RealLiteratureReviewManager(config)

    manager.review(campaign_id, accept_quality=True, reviewer="tester", reason="Research-useful refusal.")
    summary = manager.acceptance(campaign_id)
    campaign_dir = next((tmp_path / "projects").glob(f"*/campaigns/{campaign_id}"))

    report = (campaign_dir / "real_literature_review.md").read_text(encoding="utf-8")
    acceptance = (campaign_dir / "real_literature_acceptance.md").read_text(encoding="utf-8")
    assert "Real Literature Review Report" in report
    assert "Accepted for research quality: true" in report
    assert "Real Literature Acceptance" in acceptance
    assert summary["accepted_for_research_quality"] is True
