"""Closest-prior-work recall gate for real literature campaigns."""

from __future__ import annotations

from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.models import Gap, Paper, PriorWorkRecallAssessment, Provenance, ResearchRunState
from gapforge.novelty.comparator import PriorWorkComparator
from gapforge.project_memory import ProjectMemoryManager
from gapforge.search_strategy.planner import search_round_requirement_status
from gapforge.sources.policies import get_source_policy_profile
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


def assess_prior_work_recall(
    state: ResearchRunState,
    *,
    target_id: str,
    comparator: PriorWorkComparator | None = None,
) -> PriorWorkRecallAssessment:
    gap = _gap_by_id(state, target_id)
    idea_summary = _idea_summary(gap, target_id)
    source_profile = str(state.config.get("source_policy_profile") or _strategy_profile(state) or "generic")
    required = required_query_rounds(state, source_profile=source_profile)
    completed_map = search_round_requirement_status(state.search_rounds)
    completed = [name for name in required if completed_map.get(name)]
    missing = [name for name in required if name not in completed]
    candidates = _candidate_prior_work(state, gap)
    matches = (comparator or PriorWorkComparator()).compare(
        idea_summary,
        candidates,
        gap=gap,
        notes=state.paper_notes,
        sections=state.paper_sections,
    )
    top = matches[:5]
    likely_duplicate = bool(top and _covers_core(top[0]))
    blocking = list(missing)
    if likely_duplicate:
        blocking.append(f"Closest prior work appears to cover problem/method/evaluation: {top[0].paper.id}")
    confidence = _recall_confidence(missing, top)
    novelty_allowed = not missing and not likely_duplicate and confidence in {"medium", "high"}
    return PriorWorkRecallAssessment(
        id=f"prior-work-recall-{target_id}-{utc_now_compact()}",
        target_id=target_id,
        required_query_rounds=required,
        completed_query_rounds=completed,
        candidate_prior_work_ids=[paper.id for paper in candidates],
        top_prior_work_ids=[match.paper.id for match in top],
        missing_required_searches=missing,
        likely_duplicate=likely_duplicate,
        recall_confidence=confidence,
        novelty_allowed=novelty_allowed,
        blocking_issues=blocking,
        provenance=Provenance(
            created_by_skill="prior-work-recall-gate",
            source_ids=[target_id, *[match.paper.id for match in top]],
            timestamp=utc_now_iso(),
            reasoning_summary="Assessed whether prior-work recall is sufficient before allowing novelty claims.",
        ),
    )


def assess_run_prior_work_recall(config: GapForgeConfig, run_id: str, *, gap_id: str) -> PriorWorkRecallAssessment:
    manager = ResearchStateManager(config)
    state = manager.load_run(run_id)
    assessment = assess_prior_work_recall(state, target_id=gap_id)
    state.prior_work_recall_assessments = [
        item for item in state.prior_work_recall_assessments if item.target_id != assessment.target_id
    ] + [assessment]
    _downgrade_novelty_if_blocked(state, assessment)
    manager.save_run(state)
    return assessment


def assess_campaign_prior_work_recall(config: GapForgeConfig, campaign_id: str) -> list[PriorWorkRecallAssessment]:
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    manager = ResearchStateManager(config)
    assessments: list[PriorWorkRecallAssessment] = []
    for run_id in campaign_state.campaign.run_ids:
        state = manager.load_run(run_id)
        targets = [gap.id for gap in state.gaps] or [dossier.target_id for dossier in state.novelty_dossiers]
        for target_id in targets:
            assessment = assess_prior_work_recall(state, target_id=target_id)
            state.prior_work_recall_assessments = [
                item for item in state.prior_work_recall_assessments if item.target_id != assessment.target_id
            ] + [assessment]
            _downgrade_novelty_if_blocked(state, assessment)
            assessments.append(assessment)
        manager.save_run(state)
    _write_campaign_report(config, campaign_id, assessments)
    return assessments


def required_query_rounds(state: ResearchRunState, *, source_profile: str) -> list[str]:
    required = ["exact_phrase_search", "method_metric_search", "benchmark_dataset_search", "survey_search"]
    try:
        profile = get_source_policy_profile(source_profile)
    except KeyError:
        profile = get_source_policy_profile("generic")
    if state.citation_graph is not None and (state.citation_graph.edges or state.citation_graph.unresolved_references):
        required.append("citation_neighborhood_search")
    if profile.adjacent_field_requirements or state.cross_domain_analogies or state.cross_domain_transfers:
        required.append("adjacent_field_search")
    return required


def render_prior_work_recall_report(assessments: list[PriorWorkRecallAssessment]) -> str:
    lines = ["# Prior Work Recall Gate", ""]
    if not assessments:
        lines.append("No prior-work recall assessments have been run.")
        return "\n".join(lines) + "\n"
    for assessment in assessments:
        lines.extend(
            [
                f"## {assessment.target_id}",
                "",
                f"- Assessment ID: `{assessment.id}`",
                f"- Novelty allowed: {str(assessment.novelty_allowed).lower()}",
                f"- Recall confidence: {assessment.recall_confidence}",
                f"- Likely duplicate: {str(assessment.likely_duplicate).lower()}",
                f"- Required rounds: {', '.join(assessment.required_query_rounds) or 'none'}",
                f"- Completed rounds: {', '.join(assessment.completed_query_rounds) or 'none'}",
                f"- Top prior work: {', '.join(assessment.top_prior_work_ids) or 'none'}",
                "",
                "### Missing Required Searches",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in assessment.missing_required_searches] or ["- none"])
        lines.extend(["", "### Blocking Issues", ""])
        lines.extend([f"- {item}" for item in assessment.blocking_issues] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_campaign_prior_work_recall_report(config: GapForgeConfig, campaign_id: str) -> str:
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    project = ProjectMemoryManager(config).load_project(campaign_state.campaign.project_id).project
    report_path = Path(project.root_dir) / "campaigns" / campaign_id / "prior_work_recall.md"
    if not report_path.exists():
        return "# Prior Work Recall Gate\n\nNo campaign prior-work recall report generated yet.\n"
    return report_path.read_text(encoding="utf-8")


def _gap_by_id(state: ResearchRunState, target_id: str) -> Gap | None:
    return next((gap for gap in state.gaps if gap.id == target_id), None)


def _idea_summary(gap: Gap | None, target_id: str) -> str:
    if gap is None:
        return target_id
    return (
        " ".join(
            [
                gap.title,
                gap.description,
                gap.why_existing_work_does_not_solve_it,
                " ".join(gap.possible_research_questions),
                gap.minimum_experiment_needed,
            ]
        ).strip()
        or gap.id
    )


def _strategy_profile(state: ResearchRunState) -> str:
    return state.search_strategies[-1].source_profile if state.search_strategies else ""


def _candidate_prior_work(state: ResearchRunState, gap: Gap | None) -> list[Paper]:
    if gap is None:
        candidates = list(state.papers)
        live_candidates = [paper for paper in candidates if not _is_fallback_paper(paper)]
        return live_candidates or candidates
    linked = set(gap.supporting_paper_ids + gap.linked_paper_ids)
    candidates = [paper for paper in state.papers if paper.id not in linked]
    live_candidates = [paper for paper in candidates if not _is_fallback_paper(paper)]
    return live_candidates or candidates


def _covers_core(match) -> bool:
    return (
        match.overall_similarity >= 0.72
        or (match.problem_overlap >= 0.6 and match.method_overlap >= 0.5 and match.evaluation_overlap >= 0.5)
        or (match.tests_minimum_experiment and match.overall_similarity >= 0.45)
    )


def _recall_confidence(missing: list[str], top) -> str:
    if missing:
        return "low"
    if top:
        return "high" if top[0].overall_similarity >= 0.38 else "medium"
    return "medium"


def _downgrade_novelty_if_blocked(state: ResearchRunState, assessment: PriorWorkRecallAssessment) -> None:
    if assessment.novelty_allowed:
        return
    for dossier in state.novelty_dossiers:
        if dossier.target_id == assessment.target_id:
            if dossier.novelty_strength not in {"unknown", "weak"}:
                dossier.novelty_strength = "weak"
            if dossier.verdict == "pursue":
                dossier.verdict = "unknown" if not assessment.likely_duplicate else "reject"
            dossier.missing_searches = _dedupe([*dossier.missing_searches, *assessment.missing_required_searches])
            dossier.reviewer_objection = _recall_objection(assessment)
    for novelty in state.novelty_assessments:
        if novelty.target_gap_or_hypothesis_id == assessment.target_id:
            if novelty.novelty_strength not in {"unknown", "weak"}:
                novelty.novelty_strength = "weak"
            if novelty.verdict == "pursue":
                novelty.verdict = "unknown" if not assessment.likely_duplicate else "reject"
            novelty.missing_searches = _dedupe([*novelty.missing_searches, *assessment.missing_required_searches])
            novelty.possible_reviewer_objection = _recall_objection(assessment)


def _recall_objection(assessment: PriorWorkRecallAssessment) -> str:
    if assessment.likely_duplicate:
        return "Closest-prior-work recall gate found likely duplicate prior work."
    return "Closest-prior-work recall gate blocks novelty until required searches complete."


def _write_campaign_report(config: GapForgeConfig, campaign_id: str, assessments: list[PriorWorkRecallAssessment]) -> None:
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    project = ProjectMemoryManager(config).load_project(campaign_state.campaign.project_id).project
    report_path = Path(project.root_dir) / "campaigns" / campaign_id / "prior_work_recall.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_prior_work_recall_report(assessments), encoding="utf-8")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _is_fallback_paper(paper: Paper) -> bool:
    return bool(paper.raw_metadata.get("fallback")) or "fallback" in (paper.provenance.reasoning_summary or "").lower()
