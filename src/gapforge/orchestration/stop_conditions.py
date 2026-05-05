"""Stop-condition checks for active orchestration."""

from __future__ import annotations

from gapforge.models import ActiveLoopState, ResearchBudget, ResearchRunState


def budget_exhausted(state: ResearchRunState, budget: ResearchBudget) -> list[str]:
    reasons: list[str] = []
    if len(state.papers) >= budget.max_papers:
        reasons.append(f"paper budget exhausted: {len(state.papers)}/{budget.max_papers}")
    if len(state.search_queries) >= budget.max_queries:
        reasons.append(f"query budget exhausted: {len(state.search_queries)}/{budget.max_queries}")
    if _full_text_count(state) >= budget.max_full_text_papers:
        reasons.append(f"full-text budget exhausted: {_full_text_count(state)}/{budget.max_full_text_papers}")
    if state.active_loop and state.active_loop.current_iteration >= budget.max_iterations:
        reasons.append(f"iteration budget exhausted: {state.active_loop.current_iteration}/{budget.max_iterations}")
    return reasons


def coverage_sufficient(state: ResearchRunState, budget: ResearchBudget) -> bool:
    if not budget.stop_when_coverage_sufficient or state.coverage_stopping_assessment is None:
        return False
    return state.coverage_stopping_assessment.enough_for_experiment_design and bool(state.experiments)


def no_new_papers_stop(loop: ActiveLoopState, budget: ResearchBudget) -> bool:
    if not budget.stop_when_no_new_papers:
        return False
    recent = loop.decisions[-2:]
    if not recent:
        return False
    search_decisions = [decision for decision in recent if decision.decision_type in {"search_more", "expand_citations"}]
    return bool(search_decisions) and all("new_papers=0" in decision.evidence for decision in search_decisions)


def _full_text_count(state: ResearchRunState) -> int:
    return len({section.paper_id for section in state.paper_sections if section.text.strip()})
