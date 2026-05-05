"""Decision policy for the active research loop."""

from __future__ import annotations

from datetime import UTC, datetime

from gapforge.models import ActiveLoopDecision, ActiveLoopState, Provenance, ResearchBudget, ResearchRunState
from gapforge.orchestration.stop_conditions import budget_exhausted, coverage_sufficient, no_new_papers_stop
from gapforge.review.audit import is_rejected
from gapforge.review.queue import open_review_items
from gapforge.sources.stopping import assess_literature_coverage


class ActiveLoopDecider:
    """Choose the next active-loop action from current state and budget."""

    def decide(self, state: ResearchRunState, loop: ActiveLoopState) -> ActiveLoopDecision:
        budget = loop.budget
        exhausted = budget_exhausted(state, budget)
        if exhausted:
            return _decision(state, loop, "stop", "Budget exhausted.", exhausted, expected_value=0.0, cost_estimate=0.0)
        if coverage_sufficient(state, budget):
            return _decision(
                state,
                loop,
                "stop",
                "Coverage, novelty, and experiment-design policy gates are sufficient.",
                ["coverage sufficient", "experiment exists"],
            )
        if no_new_papers_stop(loop, budget):
            return _decision(
                state,
                loop,
                "stop",
                "Recent search/expansion decisions found no new papers.",
                ["no_new_papers"],
            )

        assessment = state.coverage_stopping_assessment or assess_literature_coverage(state)
        if not assessment.enough_for_mapping and _queries_remaining(state, budget):
            return _decision(
                state,
                loop,
                "search_more",
                "Source policy coverage is insufficient for mapping.",
                assessment.missing_requirements[:8] + assessment.recommended_queries[:4],
                expected_value=0.85,
                cost_estimate=1.0,
            )

        if _tier1_missing_full_text(state) and _full_text_remaining(state, budget):
            return _decision(
                state,
                loop,
                "parse_more",
                "Tier 1 papers lack parsed full text.",
                _tier1_missing_full_text(state)[:8],
                expected_value=0.75,
                cost_estimate=1.4,
            )

        if not state.paper_notes or not state.gaps or _gaps_are_low_confidence(state):
            return _decision(
                state,
                loop,
                "read_more",
                "Notes or evidence-backed gaps are missing or low confidence.",
                [f"notes={len(state.paper_notes)}", f"gaps={len(state.gaps)}"],
                expected_value=0.70,
                cost_estimate=1.0,
            )

        if _needs_citation_expansion(state) and _queries_remaining(state, budget):
            return _decision(
                state,
                loop,
                "expand_citations",
                "Closest-prior-work evidence is weak or citation graph is missing.",
                [f"citation_graph={state.citation_graph is not None}", f"dossiers={len(state.novelty_dossiers)}"],
                expected_value=0.65,
                cost_estimate=1.2,
            )

        if _needs_novelty_check(state):
            return _decision(
                state,
                loop,
                "check_novelty",
                "Candidate gaps lack auditable novelty dossiers or assessments.",
                [gap.id for gap in _active_gaps(state)[:8]],
                expected_value=0.60,
                cost_estimate=0.8,
            )

        if _should_design_experiments(state):
            return _decision(
                state,
                loop,
                "design_experiment",
                "At least one non-rejected gap has pursue/revise novelty and lacks an experiment.",
                [gap.id for gap in _experiment_ready_gaps(state)[:8]],
                expected_value=0.55,
                cost_estimate=0.8,
            )

        queued_review = open_review_items(state.review_queue)
        if queued_review:
            return _decision(
                state,
                loop,
                "request_human_review",
                "Open review queue items need human action before further automation.",
                [f"{item.priority}:{item.object_type}:{item.object_id}" for item in queued_review[:8]],
                expected_value=0.50,
                cost_estimate=0.1,
            )

        if _needs_human_review(state):
            return _decision(
                state,
                loop,
                "request_human_review",
                "Generated experiment/novelty outputs are ready for human review before further automation.",
                [f"experiments={len(state.experiments)}", f"reviewer_objections={len(state.reviewer_objections)}"],
                expected_value=0.45,
                cost_estimate=0.1,
            )

        return _decision(
            state,
            loop,
            "stop",
            "No higher-value automated action remains under current evidence and policy state.",
            ["no_action_available"],
        )


def _decision(
    state: ResearchRunState,
    loop: ActiveLoopState,
    decision_type: str,
    reason: str,
    evidence: list[str],
    *,
    expected_value: float = 0.0,
    cost_estimate: float = 0.0,
) -> ActiveLoopDecision:
    return ActiveLoopDecision(
        id=f"active-decision-{len(loop.decisions) + 1:04d}",
        run_id=state.run_id,
        iteration=loop.current_iteration + 1,
        decision_type=decision_type,
        reason=reason,
        evidence=evidence,
        expected_value=expected_value,
        cost_estimate=cost_estimate,
        provenance=Provenance(
            created_by_skill="active-loop",
            source_ids=[state.run_id],
            timestamp=datetime.now(UTC).isoformat(),
            reasoning_summary="Selected next active-loop action from budget, source policy, evidence, and novelty state.",
        ),
    )


def _queries_remaining(state: ResearchRunState, budget: ResearchBudget) -> bool:
    return len(state.search_queries) < budget.max_queries


def _full_text_remaining(state: ResearchRunState, budget: ResearchBudget) -> bool:
    return len({section.paper_id for section in state.paper_sections if section.text.strip()}) < budget.max_full_text_papers


def _tier1_missing_full_text(state: ResearchRunState) -> list[str]:
    if state.paper_triage is None:
        return []
    full_text_ids = {section.paper_id for section in state.paper_sections if section.text.strip()}
    return [
        decision.paper_id
        for decision in state.paper_triage.decisions
        if decision.tier == "Tier 1" and decision.paper_id not in full_text_ids
    ]


def _gaps_are_low_confidence(state: ResearchRunState) -> bool:
    active = _active_gaps(state)
    if not active:
        return True
    return all(gap.confidence in {"low", "unknown"} for gap in active)


def _needs_citation_expansion(state: ResearchRunState) -> bool:
    if state.citation_graph is None:
        return bool(_active_gaps(state))
    if not state.novelty_dossiers:
        return False
    return any(not dossier.top_prior_work or dossier.missing_searches for dossier in state.novelty_dossiers)


def _needs_novelty_check(state: ResearchRunState) -> bool:
    active_ids = {gap.id for gap in _active_gaps(state)}
    assessed = {assessment.target_gap_or_hypothesis_id for assessment in state.novelty_assessments}
    dossiers = {dossier.target_id for dossier in state.novelty_dossiers}
    return bool(active_ids - assessed) or bool(active_ids - dossiers)


def _should_design_experiments(state: ResearchRunState) -> bool:
    experiment_gap_ids = {gap_id for experiment in state.experiments for gap_id in experiment.linked_gap_ids}
    return any(gap.id not in experiment_gap_ids for gap in _experiment_ready_gaps(state))


def _experiment_ready_gaps(state: ResearchRunState):
    novelty_by_gap = {assessment.target_gap_or_hypothesis_id: assessment for assessment in state.novelty_assessments}
    return [
        gap
        for gap in _active_gaps(state)
        if novelty_by_gap.get(gap.id) is not None and novelty_by_gap[gap.id].verdict in {"pursue", "revise"}
    ]


def _needs_human_review(state: ResearchRunState) -> bool:
    if not state.experiments:
        return False
    reviewed_ids = {review.object_id for review in state.human_reviews if review.object_type in {"gap", "experiment"}}
    experiment_ids = {experiment.id for experiment in state.experiments}
    return bool(experiment_ids - reviewed_ids)


def _active_gaps(state: ResearchRunState):
    return [gap for gap in state.gaps if not is_rejected(state, "gap", gap.id)]
