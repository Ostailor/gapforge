"""Campaign-level state and persistence for v0.4 agentic research workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from gapforge.config import GapForgeConfig
from gapforge.models import (
    AgentActualRunAttestation,
    AgentSearchBatch,
    AgentSearchRequest,
    CampaignAcceptanceSummary,
    CampaignBudget,
    CampaignDecision,
    CampaignHumanReview,
    CampaignImportRecord,
    CampaignMilestone,
    CampaignStep,
    CampaignStopCondition,
    Provenance,
    ResearchCampaign,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, slugify, utc_now_compact, utc_now_iso


@dataclass(slots=True)
class CampaignState:
    campaign: ResearchCampaign
    steps: list[CampaignStep] = field(default_factory=list)
    decisions: list[CampaignDecision] = field(default_factory=list)
    milestones: list[CampaignMilestone] = field(default_factory=list)
    budget: CampaignBudget | None = None
    stop_conditions: list[CampaignStopCondition] = field(default_factory=list)
    imports: list[CampaignImportRecord] = field(default_factory=list)
    agent_actual_run_attestations: list[AgentActualRunAttestation] = field(default_factory=list)
    human_reviews: list[CampaignHumanReview] = field(default_factory=list)
    acceptance_summary: CampaignAcceptanceSummary | None = None
    search_requests: list[AgentSearchRequest] = field(default_factory=list)
    search_batches: list[AgentSearchBatch] = field(default_factory=list)


class CampaignManager:
    """Durable manager for project-level campaigns."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)

    def create_campaign(
        self,
        topic: str,
        *,
        project_id: str,
        title: str = "",
        mode: str = "deterministic",
        agent_name: str = "",
        model: str = "",
        source_profile: str = "generic",
        budget_id: str = "small",
    ) -> CampaignState:
        program = self.project_manager.load_project(project_id)
        now = utc_now_iso()
        campaign_id = self._unique_campaign_id(program.project.id, topic)
        campaign = ResearchCampaign(
            id=campaign_id,
            project_id=program.project.id,
            topic=topic,
            title=title or topic,
            status="planned",
            mode=mode,
            agent_name=agent_name,
            model=model,
            source_profile=source_profile,
            budget_id=budget_id,
            created_at=now,
            updated_at=now,
            provenance=_campaign_provenance("campaign-create", [], "Created durable campaign state."),
        )
        budget = _budget_for_id(budget_id)
        state = CampaignState(campaign=campaign, budget=budget)
        self.save_campaign_state(state)
        program.campaigns = [item for item in program.campaigns if item.id != campaign.id]
        program.campaigns.append(campaign)
        self.project_manager.save_project(program)
        return state

    def load_campaign_state(self, campaign_id: str) -> CampaignState:
        campaign_dir = self._find_campaign_dir(campaign_id)
        campaign = from_dict(ResearchCampaign, _read_json(campaign_dir / "campaign.json"))
        steps = _load_list(campaign_dir / "steps.json", CampaignStep)
        decisions = _load_list(campaign_dir / "decisions.json", CampaignDecision)
        milestones = _load_list(campaign_dir / "milestones.json", CampaignMilestone)
        raw_budget = _read_json(campaign_dir / "budget.json") if (campaign_dir / "budget.json").exists() else {}
        budget = from_dict(CampaignBudget, raw_budget) if raw_budget else None
        stop_conditions = _load_list(campaign_dir / "stop_conditions.json", CampaignStopCondition)
        imports = _load_list(campaign_dir / "imports.json", CampaignImportRecord)
        agent_actual_run_attestations = _load_list(campaign_dir / "agent_actual_run_attestations.json", AgentActualRunAttestation)
        human_reviews = _load_list(campaign_dir / "campaign_reviews.json", CampaignHumanReview)
        search_requests = _load_list(campaign_dir / "agent_search_requests.json", AgentSearchRequest)
        search_batches = _load_list(campaign_dir / "agent_search_batches.json", AgentSearchBatch)
        raw_acceptance = (
            _read_json(campaign_dir / "campaign_acceptance_summary.json")
            if (campaign_dir / "campaign_acceptance_summary.json").exists()
            else {}
        )
        acceptance_summary = from_dict(CampaignAcceptanceSummary, raw_acceptance) if raw_acceptance else None
        return CampaignState(
            campaign=campaign,
            steps=steps,
            decisions=decisions,
            milestones=milestones,
            budget=budget,
            stop_conditions=stop_conditions,
            imports=imports,
            agent_actual_run_attestations=agent_actual_run_attestations,
            human_reviews=human_reviews,
            acceptance_summary=acceptance_summary,
            search_requests=search_requests,
            search_batches=search_batches,
        )

    def save_campaign_state(self, state: CampaignState) -> None:
        campaign_dir = self._campaign_dir(state.campaign.project_id, state.campaign.id)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        state.campaign.updated_at = utc_now_iso()
        _write_json(campaign_dir / "campaign.json", state.campaign)
        _write_json(campaign_dir / "steps.json", state.steps)
        _write_json(campaign_dir / "decisions.json", state.decisions)
        _write_json(campaign_dir / "milestones.json", state.milestones)
        _write_json(campaign_dir / "budget.json", state.budget)
        _write_json(campaign_dir / "stop_conditions.json", state.stop_conditions)
        _write_json(campaign_dir / "imports.json", state.imports)
        _write_json(campaign_dir / "agent_actual_run_attestations.json", state.agent_actual_run_attestations)
        _write_json(campaign_dir / "campaign_reviews.json", state.human_reviews)
        _write_json(campaign_dir / "campaign_acceptance_summary.json", state.acceptance_summary)
        _write_json(campaign_dir / "agent_search_requests.json", state.search_requests)
        _write_json(campaign_dir / "agent_search_batches.json", state.search_batches)
        from gapforge.campaigns.reporting import (
            build_campaign_report_payload,
            load_campaign_report_context,
            render_campaign_report_markdown,
        )

        program, runs = load_campaign_report_context(self.config, state)
        payload = build_campaign_report_payload(state, program, runs, campaign_dir=campaign_dir)
        (campaign_dir / "campaign_report.md").write_text(render_campaign_report_markdown(payload), encoding="utf-8")
        _write_json(campaign_dir / "campaign_report.json", payload)
        self._sync_project_campaign_index(state.campaign)

    def attach_run(self, campaign_id: str, run_id: str) -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        if run_id not in state.campaign.run_ids:
            state.campaign.run_ids.append(run_id)
        step = CampaignStep(
            id=f"campaign-step-{utc_now_compact()}-run",
            campaign_id=campaign_id,
            name=f"Attach run {run_id}",
            step_type="retrieve",
            status="complete",
            run_id=run_id,
            output_artifacts=[run_id],
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            provenance=_campaign_provenance("campaign-attach-run", [run_id], "Attached a run to the campaign."),
        )
        state.steps.append(step)
        self.save_campaign_state(state)
        return state

    def attach_task(self, campaign_id: str, task_id: str, *, run_id: str = "") -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        if task_id not in state.campaign.task_ids:
            state.campaign.task_ids.append(task_id)
        step = CampaignStep(
            id=f"campaign-step-{utc_now_compact()}-task",
            campaign_id=campaign_id,
            name=f"Attach task {task_id}",
            step_type="read",
            status="complete",
            run_id=run_id,
            task_spec_id=task_id,
            output_artifacts=[task_id],
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            provenance=_campaign_provenance("campaign-attach-task", [task_id], "Attached an agent task to the campaign."),
        )
        state.steps.append(step)
        self.save_campaign_state(state)
        return state

    def add_decision(
        self,
        campaign_id: str,
        *,
        decision_type: str,
        reason: str,
        evidence: list[str] | None = None,
        expected_value: str = "",
        cost_estimate: str = "",
        status: str = "complete",
    ) -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        decision = CampaignDecision(
            id=f"campaign-decision-{utc_now_compact()}",
            campaign_id=campaign_id,
            iteration=len(state.decisions) + 1,
            decision_type=decision_type,
            reason=reason,
            evidence=evidence or [],
            expected_value=expected_value,
            cost_estimate=cost_estimate,
            status=status,
            provenance=_campaign_provenance("campaign-decision", [], "Recorded an auditable campaign decision."),
        )
        state.decisions.append(decision)
        if decision.id not in state.campaign.decision_ids:
            state.campaign.decision_ids.append(decision.id)
        self.save_campaign_state(state)
        return state

    def add_milestone(
        self,
        campaign_id: str,
        *,
        milestone_type: str,
        status: str = "complete",
        linked_artifacts: list[str] | None = None,
        notes: str = "",
    ) -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        milestone = CampaignMilestone(
            id=f"campaign-milestone-{utc_now_compact()}",
            campaign_id=campaign_id,
            milestone_type=milestone_type,
            status=status,
            linked_artifacts=linked_artifacts or [],
            notes=notes,
            provenance=_campaign_provenance("campaign-milestone", linked_artifacts or [], "Recorded a campaign milestone."),
        )
        state.milestones.append(milestone)
        if milestone.id not in state.campaign.milestone_ids:
            state.campaign.milestone_ids.append(milestone.id)
        self.save_campaign_state(state)
        return state

    def stop_campaign(self, campaign_id: str, *, reason: str) -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        stop_condition = CampaignStopCondition(
            id=f"campaign-stop-{utc_now_compact()}",
            campaign_id=campaign_id,
            reason=reason,
            triggered=True,
            evidence=[reason],
            created_at=utc_now_iso(),
            provenance=_campaign_provenance("campaign-stop", [], "Campaign stopped for an explicit auditable reason."),
        )
        self.add_decision(
            campaign_id,
            decision_type="stop",
            reason=reason,
            evidence=[stop_condition.id],
            status="complete",
        )
        state = self.load_campaign_state(campaign_id)
        state.campaign.status = "paused"
        state.stop_conditions.append(stop_condition)
        self.save_campaign_state(state)
        return state

    def resume_campaign(self, campaign_id: str) -> CampaignState:
        state = self.load_campaign_state(campaign_id)
        state.campaign.status = "running"
        state.steps.append(
            CampaignStep(
                id=f"campaign-step-{utc_now_compact()}-resume",
                campaign_id=campaign_id,
                name="Resume campaign",
                step_type="human_review",
                status="complete",
                started_at=utc_now_iso(),
                completed_at=utc_now_iso(),
                provenance=_campaign_provenance("campaign-resume", [], "Campaign resumed after a pause or stop condition."),
            )
        )
        self.save_campaign_state(state)
        return state

    def campaign_report(self, campaign_id: str, *, output_format: str = "markdown") -> Path:
        from gapforge.campaigns.reporting import write_campaign_report

        return write_campaign_report(self.config, campaign_id, output_format=output_format)

    def _sync_project_campaign_index(self, campaign: ResearchCampaign) -> None:
        program = self.project_manager.load_project(campaign.project_id)
        program.campaigns = [item for item in program.campaigns if item.id != campaign.id]
        program.campaigns.append(campaign)
        self.project_manager.save_project(program)

    def _unique_campaign_id(self, project_id: str, topic: str) -> str:
        base = f"campaign-{utc_now_compact()}-{slugify(topic)}"
        campaign_id = base
        suffix = 2
        while self._campaign_dir(project_id, campaign_id).exists():
            campaign_id = f"{base}-{suffix}"
            suffix += 1
        return campaign_id

    def _find_campaign_dir(self, campaign_id: str) -> Path:
        for project_dir in sorted(self.config.project_root.glob("*")):
            campaign_dir = project_dir / "campaigns" / campaign_id
            if (campaign_dir / "campaign.json").exists():
                return campaign_dir
        raise FileNotFoundError(f"No campaign found for {campaign_id}")

    def _campaign_dir(self, project_id: str, campaign_id: str) -> Path:
        return self.config.project_root / project_id / "campaigns" / campaign_id


def render_campaign_report(state: CampaignState) -> str:
    from gapforge.campaigns.reporting import build_campaign_report_payload, render_campaign_report_markdown

    config = GapForgeConfig.from_cwd(Path.cwd())
    project_manager = ProjectMemoryManager(config)
    state_manager = ResearchStateManager(config)
    program = project_manager.load_project(state.campaign.project_id)
    runs = []
    for run_id in state.campaign.run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    campaign_dir = config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id
    payload = build_campaign_report_payload(state, program, runs, campaign_dir=campaign_dir)
    return render_campaign_report_markdown(payload)


def _budget_for_id(budget_id: str) -> CampaignBudget:
    if budget_id == "large":
        return CampaignBudget(id=budget_id, max_iterations=8, max_papers=200, max_full_text_papers=40, max_agent_tasks=20)
    if budget_id == "medium":
        return CampaignBudget(id=budget_id, max_iterations=5, max_papers=100, max_full_text_papers=20, max_agent_tasks=10)
    return CampaignBudget(id=budget_id or "small")


T = TypeVar("T")


def _load_list(path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(model, item) for item in raw]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def _campaign_provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(created_by_skill=skill, source_ids=source_ids, timestamp=utc_now_iso(), reasoning_summary=summary)
