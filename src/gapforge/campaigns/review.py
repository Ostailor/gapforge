"""Campaign-level human review and v0.4 acceptance gates."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.acceptance import accepted_real_agent_output_ids
from gapforge.config import GapForgeConfig
from gapforge.models import CampaignAcceptanceSummary, CampaignHumanReview, Provenance, ResearchProgramState, ResearchRunState
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


class CampaignReviewManager:
    """Structured human review for full v0.4 campaigns."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manager = CampaignManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)

    def render_form(self, campaign_id: str) -> str:
        state = self.manager.load_campaign_state(campaign_id)
        return render_campaign_review_form(state)

    def review(
        self,
        campaign_id: str,
        *,
        reviewer: str = "human",
        accept: bool = False,
        reject: bool = False,
        reason: str = "",
        notes: str = "",
        source_coverage_score: int = 0,
        full_text_grounding_score: int = 0,
        citation_grounding_score: int = 0,
        retrieval_quality_score: int = 0,
        novelty_honesty_score: int = 0,
        gap_quality_score: int = 0,
        related_work_quality_score: int = 0,
        experiment_quality_score: int = 0,
        reviewer_panel_quality_score: int = 0,
        uncertainty_visibility_score: int = 0,
        stop_reason_quality_score: int = 0,
        fake_citation_found: bool = False,
        unsupported_high_confidence_claim_found: bool = False,
        obvious_prior_work_missed: bool = False,
        overclaimed_novelty: bool = False,
    ) -> tuple[CampaignHumanReview, CampaignAcceptanceSummary]:
        if accept and reject:
            raise ValueError("Use either --accept or --reject, not both.")
        state, program, runs = self._context(campaign_id)
        required_fixes = _review_required_fixes(
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
            obvious_prior_work_missed=obvious_prior_work_missed,
            overclaimed_novelty=overclaimed_novelty,
        )
        accepted = bool(accept and not required_fixes)
        if reject:
            accepted = False
        review = CampaignHumanReview(
            id=f"campaign-review-{utc_now_compact()}-{campaign_id}",
            campaign_id=campaign_id,
            reviewer=reviewer,
            reviewed_at=utc_now_iso(),
            source_coverage_score=source_coverage_score,
            full_text_grounding_score=full_text_grounding_score,
            citation_grounding_score=citation_grounding_score,
            retrieval_quality_score=retrieval_quality_score,
            novelty_honesty_score=novelty_honesty_score,
            gap_quality_score=gap_quality_score,
            related_work_quality_score=related_work_quality_score,
            experiment_quality_score=experiment_quality_score,
            reviewer_panel_quality_score=reviewer_panel_quality_score,
            uncertainty_visibility_score=uncertainty_visibility_score,
            stop_reason_quality_score=stop_reason_quality_score,
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
            obvious_prior_work_missed=obvious_prior_work_missed,
            overclaimed_novelty=overclaimed_novelty,
            accepted=accepted,
            reasons=[reason] if reason else [],
            required_fixes=required_fixes,
            notes=notes,
            provenance=Provenance(
                created_by_skill="campaign-human-review",
                source_ids=[campaign_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Human reviewed a complete campaign using structured v0.4 acceptance criteria.",
            ),
        )
        summary = build_campaign_acceptance_summary(state, program, runs, review, campaign_dir=self._campaign_dir(state))
        state.human_reviews.append(review)
        state.acceptance_summary = summary
        if summary.accepted:
            state.campaign.status = "accepted"
        elif reject or required_fixes:
            state.campaign.status = "rejected"
        self.manager.save_campaign_state(state)
        self._write_review_artifacts(state, review, summary)
        return review, summary

    def summary(self, campaign_id: str) -> CampaignAcceptanceSummary:
        state, program, runs = self._context(campaign_id)
        if state.acceptance_summary is not None:
            return state.acceptance_summary
        review = state.human_reviews[-1] if state.human_reviews else None
        return build_campaign_acceptance_summary(state, program, runs, review, campaign_dir=self._campaign_dir(state))

    def v4_actual_run_acceptance(self) -> dict[str, object]:
        summaries: list[CampaignAcceptanceSummary] = []
        for campaign_dir in self._campaign_dirs():
            try:
                state = self.manager.load_campaign_state(campaign_dir.name)
            except (FileNotFoundError, json.JSONDecodeError, ValueError):
                continue
            if state.acceptance_summary is not None:
                summaries.append(state.acceptance_summary)
        eligible = [summary for summary in summaries if summary.release_gate_eligible]
        return {
            "passed": bool(eligible),
            "accepted_real_campaign_count": len(eligible),
            "accepted_campaigns": [summary.campaign_id for summary in eligible],
            "reviewed_campaigns": [summary.campaign_id for summary in summaries],
            "missing": [] if eligible else ["No accepted real Codex/GPT-5.4 campaign is release-gate eligible."],
        }

    def _context(self, campaign_id: str) -> tuple[CampaignState, ResearchProgramState, list[ResearchRunState]]:
        state = self.manager.load_campaign_state(campaign_id)
        program = self.project_manager.load_project(state.campaign.project_id)
        runs: list[ResearchRunState] = []
        for run_id in state.campaign.run_ids:
            try:
                runs.append(self.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        return state, program, runs

    def _write_review_artifacts(
        self,
        state: CampaignState,
        review: CampaignHumanReview,
        summary: CampaignAcceptanceSummary,
    ) -> None:
        campaign_dir = self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id
        (campaign_dir / "campaign_review.md").write_text(render_campaign_review_report(review, summary), encoding="utf-8")

    def _campaign_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if not self.config.project_root.exists():
            return dirs
        for project_dir in self.config.project_root.iterdir():
            campaign_root = project_dir / "campaigns"
            if campaign_root.exists():
                dirs.extend(path for path in campaign_root.iterdir() if path.is_dir())
        return dirs

    def _campaign_dir(self, state: CampaignState) -> Path:
        return self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id


def build_campaign_acceptance_summary(
    state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    review: CampaignHumanReview | None,
    *,
    campaign_dir: Path | None = None,
) -> CampaignAcceptanceSummary:
    blocking: list[str] = []
    artifact_presence = _artifact_presence(state, campaign_dir)
    if not artifact_presence["campaign_report"]:
        blocking.append("No campaign report is present.")
    if not _has_source_coverage(runs):
        blocking.append("No source coverage is present.")
    if not state.stop_conditions:
        blocking.append("No final stop reason is recorded.")
    if _recommended_direction_requires_novelty(program) and not _has_novelty_dossier(runs):
        blocking.append("Missing novelty dossier for recommended direction.")
    if _strong_novelty_without_prior_work(runs):
        blocking.append("Strong novelty appears without closest prior work.")

    refusal = _is_refusal_campaign(state, program)
    attestation_present = _actual_run_attestation_present(state)
    real_outputs = _accepted_real_agent_outputs(state)
    if _campaign_requires_actual_agent(state) and not attestation_present:
        blocking.append("Missing human attestation for task-pack/handoff actual run.")
    if _campaign_requires_actual_agent(state) and not real_outputs:
        blocking.append("No actual Codex/GPT-5.4 output is imported.")

    if review is None:
        blocking.append("Campaign human review is missing.")
        scores: dict[str, int] = {}
    else:
        scores = _review_scores(review)
        if review.fake_citation_found:
            blocking.append("Fake citation found.")
        if review.unsupported_high_confidence_claim_found:
            blocking.append("Unsupported high-confidence claim found.")
        if review.obvious_prior_work_missed:
            blocking.append("Obvious prior work missed.")
        if review.overclaimed_novelty:
            blocking.append("Strict report overclaimed novelty or readiness.")
        if not review.accepted:
            blocking.append("Human reviewer did not accept the campaign.")

    if refusal:
        blocking = [
            item
            for item in blocking
            if item
            not in {
                "Missing human attestation for task-pack/handoff actual run.",
                "No actual Codex/GPT-5.4 output is imported.",
            }
        ]
    accepted = not blocking and review is not None and review.accepted
    release_gate_eligible = accepted and bool(real_outputs) and attestation_present and not refusal
    return CampaignAcceptanceSummary(
        campaign_id=state.campaign.id,
        accepted=accepted,
        blocking_failures=_dedupe(blocking),
        scores=scores,
        required_artifacts_present=artifact_presence,
        actual_run_attestation_present=attestation_present,
        accepted_real_agent_outputs=real_outputs,
        release_gate_eligible=release_gate_eligible,
        provenance=Provenance(
            created_by_skill="campaign-acceptance",
            source_ids=[state.campaign.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Built campaign acceptance summary from campaign state, artifacts, imported agent outputs, and human review.",
        ),
    )


def render_campaign_review_form(state: CampaignState) -> str:
    return "\n".join(
        [
            f"# Campaign Human Review: {state.campaign.id}",
            "",
            "Review the full campaign, not just one run. Do not accept if citations are fake, high-confidence claims lack evidence, "
            "or novelty is overclaimed.",
            "",
            "## Checklist",
            "",
            "- [ ] Source coverage is visible and adequate for the recommendation.",
            "- [ ] Full-text and abstract-only evidence are distinguished.",
            "- [ ] Citations and EvidenceSpan locators resolve.",
            "- [ ] Retrieval quality is adequate for closest-prior-work search.",
            "- [ ] Novelty dossiers include closest prior work or explicit unknown status.",
            "- [ ] Gap evidence matrices support recommended gaps.",
            "- [ ] Related-work matrix and experiment protocol are concrete when a direction is recommended.",
            "- [ ] Reviewer panel objections are serious.",
            "- [ ] Uncertainty and stop reasons are visible.",
            "",
            "## CLI",
            "",
            f'```bash\ngapforge campaign-review --campaign-id {state.campaign.id} --accept --reviewer "name"\n```',
            f'```bash\ngapforge campaign-review --campaign-id {state.campaign.id} --reject --reason "blocking issue"\n```',
            "",
        ]
    )


def render_campaign_review_report(review: CampaignHumanReview, summary: CampaignAcceptanceSummary) -> str:
    lines = [
        f"# Campaign Review Report: {review.campaign_id}",
        "",
        f"- Reviewer: {review.reviewer}",
        f"- Reviewed at: {review.reviewed_at}",
        f"- Accepted by reviewer: {str(review.accepted).lower()}",
        f"- Campaign accepted: {str(summary.accepted).lower()}",
        f"- Release gate eligible: {str(summary.release_gate_eligible).lower()}",
        "",
        "## Scores",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in summary.scores.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend(f"- {item}" for item in summary.blocking_failures or ["none"])
    lines.extend(["", "## Required Artifacts", ""])
    lines.extend(f"- {key}: {str(value).lower()}" for key, value in summary.required_artifacts_present.items())
    lines.extend(["", "## Required Fixes", ""])
    lines.extend(f"- {item}" for item in review.required_fixes or ["none"])
    if review.notes:
        lines.extend(["", "## Notes", "", review.notes])
    return "\n".join(lines).rstrip() + "\n"


def _review_required_fixes(
    *,
    fake_citation_found: bool,
    unsupported_high_confidence_claim_found: bool,
    obvious_prior_work_missed: bool,
    overclaimed_novelty: bool,
) -> list[str]:
    fixes: list[str] = []
    if fake_citation_found:
        fixes.append("Remove fake citations or convert them into search requests.")
    if unsupported_high_confidence_claim_found:
        fixes.append("Downgrade or support high-confidence claims with evidence.")
    if obvious_prior_work_missed:
        fixes.append("Expand closest-prior-work search and revise novelty dossiers.")
    if overclaimed_novelty:
        fixes.append("Fix strict report/novelty language so it does not overclaim.")
    return fixes


def _artifact_presence(state: CampaignState, campaign_dir: Path | None) -> dict[str, bool]:
    if campaign_dir is None:
        campaign_dir = Path(state.campaign.project_id) / "campaigns" / state.campaign.id
    return {
        "campaign_report": (campaign_dir / "campaign_report.md").exists(),
        "steps": (campaign_dir / "steps.json").exists(),
        "decisions": (campaign_dir / "decisions.json").exists(),
        "imports": (campaign_dir / "imports.json").exists(),
    }


def _has_source_coverage(runs: list[ResearchRunState]) -> bool:
    return any(run.source_coverage is not None for run in runs)


def _recommended_direction_requires_novelty(program: ResearchProgramState) -> bool:
    return any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions)


def _has_novelty_dossier(runs: list[ResearchRunState]) -> bool:
    return any(run.novelty_dossiers for run in runs)


def _strong_novelty_without_prior_work(runs: list[ResearchRunState]) -> bool:
    for run in runs:
        for dossier in run.novelty_dossiers:
            if dossier.novelty_strength == "strong" and not dossier.top_prior_work:
                return True
        for assessment in run.novelty_assessments:
            if assessment.novelty_strength == "strong" and not assessment.closest_prior_work:
                return True
    return False


def _campaign_requires_actual_agent(state: CampaignState) -> bool:
    return state.campaign.mode in {"codex_task_pack", "codex_direct", "manual_handoff"}


def _actual_run_attestation_present(state: CampaignState) -> bool:
    return bool(_accepted_real_agent_outputs(state))


def _accepted_real_agent_outputs(state: CampaignState) -> list[str]:
    return accepted_real_agent_output_ids(state)


def _is_refusal_campaign(state: CampaignState, program: ResearchProgramState) -> bool:
    no_ready_direction = not any(
        direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions
    )
    return bool(state.stop_conditions and no_ready_direction)


def _review_scores(review: CampaignHumanReview) -> dict[str, int]:
    return {
        "source_coverage": review.source_coverage_score,
        "full_text_grounding": review.full_text_grounding_score,
        "citation_grounding": review.citation_grounding_score,
        "retrieval_quality": review.retrieval_quality_score,
        "novelty_honesty": review.novelty_honesty_score,
        "gap_quality": review.gap_quality_score,
        "related_work_quality": review.related_work_quality_score,
        "experiment_quality": review.experiment_quality_score,
        "reviewer_panel_quality": review.reviewer_panel_quality_score,
        "uncertainty_visibility": review.uncertainty_visibility_score,
        "stop_reason_quality": review.stop_reason_quality_score,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
