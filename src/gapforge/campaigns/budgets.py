"""Budget accounting for v0.4 campaign controller loops."""

from __future__ import annotations

from dataclasses import dataclass

from gapforge.campaigns import CampaignState
from gapforge.models import CampaignBudget


@dataclass(frozen=True, slots=True)
class CampaignBudgetStatus:
    exhausted: bool
    reasons: list[str]
    iterations_used: int
    agent_tasks_used: int
    imports_used: int
    papers_seen: int


def campaign_budget_status(
    state: CampaignState,
    *,
    papers_seen: int = 0,
    max_iterations_override: int | None = None,
) -> CampaignBudgetStatus:
    budget = state.budget or CampaignBudget(id=state.campaign.budget_id or "small")
    max_iterations = max_iterations_override if max_iterations_override is not None else budget.max_iterations
    reasons: list[str] = []
    iterations_used = len(state.decisions)
    agent_tasks_used = len(state.campaign.task_ids)
    imports_used = len(state.imports)
    if iterations_used >= max_iterations:
        reasons.append(f"iteration budget exhausted ({iterations_used}/{max_iterations})")
    if agent_tasks_used >= budget.max_agent_tasks:
        reasons.append(f"agent task budget exhausted ({agent_tasks_used}/{budget.max_agent_tasks})")
    if imports_used >= budget.max_agent_imports:
        reasons.append(f"agent import budget exhausted ({imports_used}/{budget.max_agent_imports})")
    if papers_seen >= budget.max_papers:
        reasons.append(f"paper budget reached ({papers_seen}/{budget.max_papers})")
    return CampaignBudgetStatus(
        exhausted=bool(reasons),
        reasons=reasons,
        iterations_used=iterations_used,
        agent_tasks_used=agent_tasks_used,
        imports_used=imports_used,
        papers_seen=papers_seen,
    )


def agent_task_budget_available(state: CampaignState) -> bool:
    budget = state.budget or CampaignBudget(id=state.campaign.budget_id or "small")
    return len(state.campaign.task_ids) < budget.max_agent_tasks
