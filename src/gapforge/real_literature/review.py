"""Human review for v0.5 real-literature campaign quality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, RealLiteratureHumanReview, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


class RealLiteratureReviewManager:
    """Separate workflow acceptance from research-quality acceptance."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.campaign_manager = CampaignManager(config)

    def render_form(self, campaign_id: str) -> str:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        return render_real_literature_review_form(state)

    def review(
        self,
        campaign_id: str,
        *,
        reviewer: str = "human",
        accept_workflow: bool = True,
        accept_quality: bool = False,
        reason: str = "",
        source_quality_score: int = 0,
        paper_relevance_score: int = 0,
        prior_work_recall_score: int = 0,
        evidence_grounding_score: int = 0,
        novelty_honesty_score: int = 0,
        gap_importance_score: int = 0,
        experiment_feasibility_score: int = 0,
        reviewer_objection_quality_score: int = 0,
        report_honesty_score: int = 0,
        missed_obvious_prior_work: bool = False,
        fake_citation_found: bool = False,
        unsupported_high_confidence_claim_found: bool = False,
        overclaimed_novelty: bool = False,
    ) -> tuple[RealLiteratureHumanReview, dict[str, Any]]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        workflow_blockers = _workflow_blockers(
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
        )
        quality_blockers = _quality_blockers(
            accept_quality=accept_quality,
            missed_obvious_prior_work=missed_obvious_prior_work,
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
            overclaimed_novelty=overclaimed_novelty,
        )
        required_fixes = _dedupe([*workflow_blockers, *quality_blockers])
        review = RealLiteratureHumanReview(
            id=f"real-literature-review-{utc_now_compact()}-{campaign_id}",
            campaign_id=campaign_id,
            reviewer=reviewer,
            reviewed_at=utc_now_iso(),
            source_quality_score=source_quality_score,
            paper_relevance_score=paper_relevance_score,
            prior_work_recall_score=prior_work_recall_score,
            evidence_grounding_score=evidence_grounding_score,
            novelty_honesty_score=novelty_honesty_score,
            gap_importance_score=gap_importance_score,
            experiment_feasibility_score=experiment_feasibility_score,
            reviewer_objection_quality_score=reviewer_objection_quality_score,
            report_honesty_score=report_honesty_score,
            missed_obvious_prior_work=missed_obvious_prior_work,
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
            overclaimed_novelty=overclaimed_novelty,
            accepted_for_workflow=bool(accept_workflow and not workflow_blockers),
            accepted_for_research_quality=bool(accept_quality and not quality_blockers),
            reasons=[reason] if reason else [],
            required_fixes=required_fixes,
            provenance=Provenance(
                created_by_skill="real-literature-human-review",
                source_ids=[campaign_id],
                timestamp=utc_now_iso(),
                reasoning_summary=("Human reviewed a real-literature campaign for workflow mechanics and independent research usefulness."),
            ),
        )
        reviews = self.load_reviews(campaign_id)
        reviews.append(review)
        self._write_reviews(state, reviews)
        summary = build_real_literature_acceptance_summary(state, reviews)
        self._write_acceptance(state, summary)
        return review, summary

    def acceptance(self, campaign_id: str) -> dict[str, Any]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        reviews = self.load_reviews(campaign_id)
        summary = build_real_literature_acceptance_summary(state, reviews)
        self._write_acceptance(state, summary)
        return summary

    def load_reviews(self, campaign_id: str) -> list[RealLiteratureHumanReview]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        path = self._campaign_dir(state) / "real_literature_reviews.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RealLiteratureHumanReview, item) for item in raw]

    def _write_reviews(self, state: CampaignState, reviews: list[RealLiteratureHumanReview]) -> None:
        campaign_dir = self._campaign_dir(state)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / "real_literature_reviews.json").write_text(
            json.dumps([to_plain(review) for review in reviews], indent=2) + "\n",
            encoding="utf-8",
        )
        latest = reviews[-1]
        (campaign_dir / "real_literature_review.md").write_text(
            render_real_literature_review_report(latest, build_real_literature_acceptance_summary(state, reviews)),
            encoding="utf-8",
        )

    def _write_acceptance(self, state: CampaignState, summary: dict[str, Any]) -> None:
        campaign_dir = self._campaign_dir(state)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / "real_literature_acceptance.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (campaign_dir / "real_literature_acceptance.md").write_text(
            render_real_literature_acceptance_markdown(summary),
            encoding="utf-8",
        )

    def _campaign_dir(self, state: CampaignState) -> Path:
        return self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id


def build_real_literature_acceptance_summary(
    state: CampaignState,
    reviews: list[RealLiteratureHumanReview],
) -> dict[str, Any]:
    latest = reviews[-1] if reviews else None
    blocking: list[str] = []
    if latest is None:
        blocking.append("Real-literature human review is missing.")
    else:
        if latest.fake_citation_found:
            blocking.append("Fake citation found.")
        if latest.unsupported_high_confidence_claim_found:
            blocking.append("Unsupported high-confidence claim found.")
        if latest.missed_obvious_prior_work:
            blocking.append("Obvious prior work was missed.")
        if latest.overclaimed_novelty:
            blocking.append("Novelty or readiness was overclaimed.")
        if not latest.accepted_for_workflow:
            blocking.append("Workflow acceptance is not recorded.")
        if not latest.accepted_for_research_quality:
            blocking.append("Research-quality acceptance is not recorded.")

    return {
        "campaign_id": state.campaign.id,
        "latest_review_id": latest.id if latest else "",
        "review_count": len(reviews),
        "accepted_for_workflow": bool(latest and latest.accepted_for_workflow),
        "accepted_for_research_quality": bool(latest and latest.accepted_for_research_quality),
        "release_quality_eligible": bool(latest and latest.accepted_for_workflow and latest.accepted_for_research_quality and not blocking),
        "is_refusal_campaign": _is_refusal_campaign(state),
        "blocking_failures": _dedupe(blocking),
        "scores": _scores(latest) if latest else {},
        "next_commands": _next_commands(state, latest, blocking),
        "provenance": to_plain(
            Provenance(
                created_by_skill="real-literature-acceptance",
                source_ids=[state.campaign.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Summarized real-literature workflow and research-quality human acceptance.",
            )
        ),
    }


def render_real_literature_review_form(state: CampaignState) -> str:
    return "\n".join(
        [
            f"# Real Literature Human Review: {state.campaign.id}",
            "",
            "Score whether the campaign is research-useful, not only whether the workflow ran.",
            "",
            "## Checklist",
            "",
            "- [ ] Sources are real, relevant, and adequate for the topic.",
            "- [ ] Closest-prior-work recall is credible.",
            "- [ ] Evidence locators support important claims.",
            "- [ ] Novelty language is conservative.",
            "- [ ] The gap is important enough to pursue or the refusal is correct.",
            "- [ ] The experiment protocol is feasible when a direction is recommended.",
            "- [ ] Reviewer objections are serious and grounded.",
            "- [ ] The report does not hide uncertainty, missing searches, or weak coverage.",
            "",
            "## Commands",
            "",
            "```bash",
            f'gapforge real-literature-review --campaign-id {state.campaign.id} --accept-quality --reviewer "name"',
            "```",
            "```bash",
            f"gapforge real-literature-acceptance --campaign-id {state.campaign.id}",
            "```",
            "",
            "A campaign can be workflow-accepted but research-quality rejected. Fake citations block both.",
        ]
    )


def render_real_literature_review_report(review: RealLiteratureHumanReview, summary: dict[str, Any]) -> str:
    lines = [
        f"# Real Literature Review Report: {review.campaign_id}",
        "",
        f"- Review ID: `{review.id}`",
        f"- Reviewer: {review.reviewer}",
        f"- Reviewed at: {review.reviewed_at}",
        f"- Accepted for workflow: {str(review.accepted_for_workflow).lower()}",
        f"- Accepted for research quality: {str(review.accepted_for_research_quality).lower()}",
        f"- Release-quality eligible: {str(summary['release_quality_eligible']).lower()}",
        "",
        "## Scores",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in _scores(review).items())
    lines.extend(["", "## Blocking Findings", ""])
    lines.extend(f"- {item}" for item in summary["blocking_failures"] or ["none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend(f"- {item}" for item in review.required_fixes or ["none"])
    if review.reasons:
        lines.extend(["", "## Reasons", ""])
        lines.extend(f"- {item}" for item in review.reasons)
    return "\n".join(lines).rstrip() + "\n"


def render_real_literature_acceptance_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# Real Literature Acceptance: {summary['campaign_id']}",
        "",
        f"- Accepted for workflow: {str(summary['accepted_for_workflow']).lower()}",
        f"- Accepted for research quality: {str(summary['accepted_for_research_quality']).lower()}",
        f"- Release-quality eligible: {str(summary['release_quality_eligible']).lower()}",
        f"- Refusal campaign: {str(summary['is_refusal_campaign']).lower()}",
        "",
        "## Blocking Failures",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["blocking_failures"] or ["none"])
    lines.extend(["", "## Next Commands", ""])
    lines.extend(f"- `{item}`" for item in summary["next_commands"] or ["none"])
    return "\n".join(lines).rstrip() + "\n"


def _workflow_blockers(*, fake_citation_found: bool, unsupported_high_confidence_claim_found: bool) -> list[str]:
    blockers: list[str] = []
    if fake_citation_found:
        blockers.append("Remove fake citations before accepting workflow.")
    if unsupported_high_confidence_claim_found:
        blockers.append("Downgrade or support high-confidence claims before accepting workflow.")
    return blockers


def _quality_blockers(
    *,
    accept_quality: bool,
    missed_obvious_prior_work: bool,
    fake_citation_found: bool,
    unsupported_high_confidence_claim_found: bool,
    overclaimed_novelty: bool,
) -> list[str]:
    blockers: list[str] = []
    if not accept_quality:
        blockers.append("Research-quality acceptance was not requested.")
    if fake_citation_found:
        blockers.append("Remove fake citations before accepting research quality.")
    if unsupported_high_confidence_claim_found:
        blockers.append("Support or downgrade high-confidence claims before accepting research quality.")
    if missed_obvious_prior_work:
        blockers.append("Expand prior-work recall and revise novelty claims before accepting research quality.")
    if overclaimed_novelty:
        blockers.append("Soften novelty/readiness claims before accepting research quality.")
    return blockers


def _scores(review: RealLiteratureHumanReview | None) -> dict[str, int]:
    if review is None:
        return {}
    return {
        "source_quality": review.source_quality_score,
        "paper_relevance": review.paper_relevance_score,
        "prior_work_recall": review.prior_work_recall_score,
        "evidence_grounding": review.evidence_grounding_score,
        "novelty_honesty": review.novelty_honesty_score,
        "gap_importance": review.gap_importance_score,
        "experiment_feasibility": review.experiment_feasibility_score,
        "reviewer_objection_quality": review.reviewer_objection_quality_score,
        "report_honesty": review.report_honesty_score,
    }


def _is_refusal_campaign(state: CampaignState) -> bool:
    text = " ".join(condition.reason for condition in state.stop_conditions).lower()
    return any(marker in text for marker in ("refusal", "poor coverage", "insufficient", "not_ready", "not ready", "novelty unknown"))


def _next_commands(state: CampaignState, latest: RealLiteratureHumanReview | None, blockers: list[str]) -> list[str]:
    if latest is None:
        return [f'gapforge real-literature-review --campaign-id {state.campaign.id} --accept-quality --reviewer "<name>"']
    commands: list[str] = []
    if any("prior-work" in blocker or "prior work" in blocker for blocker in blockers):
        commands.append(f"gapforge novelty-loop --campaign-id {state.campaign.id}")
    if any("citation" in blocker.lower() for blocker in blockers):
        commands.append(f"gapforge codex-doctor --campaign-id {state.campaign.id}")
    if any("Research-quality acceptance" in blocker for blocker in blockers):
        commands.append(f'gapforge real-literature-review --campaign-id {state.campaign.id} --accept-quality --reviewer "<name>"')
    return _dedupe(commands)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
