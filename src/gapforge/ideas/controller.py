"""Active v2 idea-search controller."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.controller import CampaignController
from gapforge.config import GapForgeConfig
from gapforge.ideas.agenda import ResearchAgendaManager
from gapforge.ideas.codex_tasks import IdeaCodexTaskManager
from gapforge.ideas.constructive_gap import ConstructiveGapGenerator
from gapforge.ideas.decision_policy import IdeaSearchAction, IdeaSearchAssessment, IdeaSearchDecisionPolicy
from gapforge.ideas.generator import IdeaSeedGenerator, is_generic_idea_title
from gapforge.ideas.models import IdeaCandidate, IdeaSearchDecision
from gapforge.ideas.mutation import IdeaMutationEngine
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolioGenerator, TopicVariant
from gapforge.ideas.tournament import IdeaTournamentRunner
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_compact, utc_now_iso


@dataclass(slots=True)
class IdeaSearchRunResult:
    project_id: str
    status: str
    decisions: list[IdeaSearchDecision] = field(default_factory=list)
    stopped_reason: str = ""


class IdeaSearchController:
    """Run an auditable active search loop over the v2 idea-discovery surface."""

    def __init__(self, config: GapForgeConfig, policy: IdeaSearchDecisionPolicy | None = None) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.store = IdeaStore(config)
        self.portfolios = TopicPortfolioGenerator(config)
        self.generator = IdeaSeedGenerator(config)
        self.mutations = IdeaMutationEngine(config)
        self.constructive_gaps = ConstructiveGapGenerator(config)
        self.campaigns = CampaignManager(config)
        self.campaign_controller = CampaignController(config)
        self.codex_tasks = IdeaCodexTaskManager(config)
        self.tournaments = IdeaTournamentRunner(config)
        self.agendas = ResearchAgendaManager(config)
        self.policy = policy or IdeaSearchDecisionPolicy()

    def run(self, project_id: str, *, max_iterations: int = 5) -> IdeaSearchRunResult:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        self.project_manager.load_project(project_id)
        decisions: list[IdeaSearchDecision] = []
        status = "running"
        stopped_reason = ""
        for run_iteration in range(1, max_iterations + 1):
            iteration = len(self.store.load_state(project_id).search_decisions) + 1
            assessment = self._assess(project_id, iteration=run_iteration, max_iterations=max_iterations)
            action = self.policy.decide(assessment)
            execution_evidence, execution_status = self._execute(project_id, action, iteration)
            decision = self._record_decision(
                project_id=project_id,
                iteration=iteration,
                action=action,
                execution_evidence=execution_evidence,
                execution_status=execution_status,
            )
            decisions.append(decision)
            self._write_reports(project_id)
            if action.terminal or action.decision_type in {"request_feedback", "create_agenda", "stop"}:
                status = execution_status
                stopped_reason = action.reason
                break
        else:
            status = "budget_exhausted"
            stopped_reason = f"Stopped after max_iterations={max_iterations}."
        return IdeaSearchRunResult(project_id=project_id, status=status, decisions=decisions, stopped_reason=stopped_reason)

    def render_status(self, project_id: str) -> str:
        state = self.store.load_state(project_id)
        portfolios = self.portfolios.list_project_portfolios(project_id)
        active = [candidate for candidate in state.candidates if candidate.maturity != "rejected"]
        latest = state.search_decisions[-1] if state.search_decisions else None
        lines = [
            "# Idea Search Status",
            "",
            f"- Project ID: `{project_id}`",
            f"- Topic portfolios: {len(portfolios)}",
            f"- Active candidates: {len(active)}",
            f"- Rejected candidates retained: {len([candidate for candidate in state.candidates if candidate.maturity == 'rejected'])}",
            f"- Constructive gaps: {len(state.constructive_gaps)}",
            f"- Mutations: {len(state.mutations)}",
            f"- Human reviews: {len(state.reviews)}",
            f"- Decisions: {len(state.search_decisions)}",
        ]
        if latest is not None:
            lines.extend(
                [
                    "",
                    "## Latest Decision",
                    "",
                    f"- Type: `{latest.decision_type}`",
                    f"- Status: `{latest.status}`",
                    f"- Reason: {latest.reason}",
                    f"- Evidence: {'; '.join(latest.evidence) or 'none'}",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def render_decisions(self, project_id: str) -> str:
        state = self.store.load_state(project_id)
        lines = [
            "# Idea Search Decisions",
            "",
            "Every controller step is persisted as an auditable decision. "
            "Search may stop with a candidate needing review or with an agenda.",
            "",
        ]
        if not state.search_decisions:
            lines.append("- none")
            return "\n".join(lines).rstrip() + "\n"
        for decision in state.search_decisions:
            lines.extend(
                [
                    f"## `{decision.id}`",
                    "",
                    f"- Iteration: {decision.iteration}",
                    f"- Type: `{decision.decision_type}`",
                    f"- Status: `{decision.status}`",
                    f"- Reason: {decision.reason}",
                    f"- Expected value: {decision.expected_value}",
                    f"- Evidence: {'; '.join(decision.evidence) or 'none'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def _assess(self, project_id: str, *, iteration: int, max_iterations: int) -> IdeaSearchAssessment:
        state = self.store.load_state(project_id)
        return IdeaSearchAssessment(
            project_id=project_id,
            iteration=iteration,
            max_iterations=max_iterations,
            portfolio_count=len(self.portfolios.list_project_portfolios(project_id)),
            candidates=state.candidates,
            constructive_gap_count=len(state.constructive_gaps),
            mutation_count=len(state.mutations),
            transfer_count=len(state.transfer_candidates),
            review_count=len(state.reviews),
        )

    def _execute(self, project_id: str, action: IdeaSearchAction, iteration: int) -> tuple[list[str], str]:
        if action.decision_type == "generate_portfolio":
            portfolio = self.portfolios.generate(project_id=project_id)
            return [portfolio.id, f"variants={len(portfolio.topic_variants)}"], "complete"
        if action.decision_type == "synthesize_ideas":
            result = self.generator.generate(project_id=project_id, max_candidates=30)
            return [result.bank.id, f"seed_candidates={len(result.candidates)}"], "complete"
        if action.decision_type == "mutate_ideas":
            return self._mutate_weak_ideas(project_id)
        if action.decision_type == "search_variant":
            return self._search_variant(project_id, iteration)
        if action.decision_type == "run_prior_work":
            task = self.codex_tasks.create_task(project_id, "idea_critique")
            return [task.id, "task_type=idea_critique"], "complete"
        if action.decision_type == "run_tournament":
            tournament = self.tournaments.run(project_id)
            return [tournament.id, f"selected={tournament.selected_candidate_id or 'none'}"], "complete"
        if action.decision_type == "request_feedback":
            return self._request_feedback(project_id, action)
        if action.decision_type == "create_agenda":
            agenda = self._create_agenda(project_id, action)
            return [agenda.id], "complete"
        return [], "complete"

    def _mutate_weak_ideas(self, project_id: str) -> tuple[list[str], str]:
        state = self.store.load_state(project_id)
        weak = [
            candidate
            for candidate in state.candidates
            if candidate.maturity != "rejected"
            and (
                is_generic_idea_title(candidate.title)
                or candidate.novelty_status in {"weak", "likely_duplicate"}
                or candidate.idea_yield_score < 0.2
                or "generic" in candidate.summary.lower()
                or "generic" in candidate.likely_failure_mode.lower()
            )
        ]
        evidence: list[str] = []
        for candidate in weak[:10]:
            result = self.mutations.mutate_idea(candidate.id)
            evidence.append(result.record.id)
        constructive = self.constructive_gaps.generate_for_project(project_id)
        evidence.append(f"constructive_gaps={len(constructive.candidates)}")
        return evidence, "complete"

    def _search_variant(self, project_id: str, iteration: int) -> tuple[list[str], str]:
        portfolios = self.portfolios.list_project_portfolios(project_id)
        portfolio = portfolios[-1] if portfolios else self.portfolios.generate(project_id=project_id)
        variant = _variant_for_iteration(portfolio.topic_variants, iteration)
        campaign = self.campaigns.create_campaign(
            variant.text if variant is not None else portfolio.root_topic,
            project_id=project_id,
            title=f"Idea search variant: {variant.transformation_type if variant is not None else 'root'}",
            source_profile="generic",
            budget_id="small",
        )
        campaign_state = self.campaign_controller.run(campaign.campaign.id, max_iterations=1)
        evidence = [campaign.campaign.id, f"campaign_status={campaign_state.campaign.status}"]
        if variant is not None:
            evidence.extend([variant.id, f"variant_type={variant.transformation_type}"])
        return evidence, "complete"

    def _request_feedback(self, project_id: str, action: IdeaSearchAction) -> tuple[list[str], str]:
        survivor_id = next((item for item in action.evidence if item.startswith("idea-")), "")
        if not survivor_id:
            survivors = _surviving_candidates(self.store.load_state(project_id).candidates)
            survivor_id = survivors[0].id if survivors else ""
        if not survivor_id:
            return ["no_survivor_found"], "blocked"
        review = self.store.add_review(
            idea_id=survivor_id,
            reviewer="human-review-required",
            status="uncertain",
            novelty_judgment="Controller requests human novelty review before acceptance.",
            feasibility_judgment="Controller requests feasibility review before acceptance.",
            impact_judgment="Controller requests impact review before acceptance.",
            required_fixes=[
                "Confirm closest prior work does not subsume the idea.",
                "Confirm minimum experiment and baselines are acceptable.",
                "Confirm the idea is worth advancing beyond seed/candidate maturity.",
            ],
            notes="Active idea search found one candidate that passed deterministic gates; human review is required.",
        )
        return [survivor_id, review.id], "blocked"

    def _create_agenda(self, project_id: str, action: IdeaSearchAction):
        state = self.store.load_state(project_id)
        return self.agendas.generate(
            project_id,
            blocker_summary=(
                "Active v2 idea search did not produce an accepted idea candidate within the configured budget. "
                "No candidate may be forced through the evidence gates."
            ),
            source_ids=[*[decision.id for decision in state.search_decisions], *action.evidence],
        )

    def _record_decision(
        self,
        *,
        project_id: str,
        iteration: int,
        action: IdeaSearchAction,
        execution_evidence: list[str],
        execution_status: str,
    ) -> IdeaSearchDecision:
        now = utc_now_iso()
        decision = IdeaSearchDecision(
            id=_decision_id(project_id, iteration, action.decision_type, action.reason, execution_evidence),
            project_id=project_id,
            iteration=iteration,
            decision_type=action.decision_type,
            reason=action.reason,
            expected_value=action.expected_value,
            evidence=[*action.evidence, *execution_evidence],
            status=execution_status,
            provenance=Provenance(
                created_by_skill="idea-search-controller",
                source_ids=[project_id, *action.evidence, *execution_evidence],
                timestamp=now,
                reasoning_summary="Recorded an auditable active idea-search controller decision.",
            ),
        )
        return self.store.add_search_decision(decision)

    def _write_reports(self, project_id: str) -> None:
        program = self.project_manager.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_search_status.md").write_text(self.render_status(project_id), encoding="utf-8")
        (reports_dir / "idea_search_decisions.md").write_text(self.render_decisions(project_id), encoding="utf-8")


def _variant_for_iteration(variants: list[TopicVariant], iteration: int) -> TopicVariant | None:
    if not variants:
        return None
    return variants[(iteration - 1) % len(variants)]


def _surviving_candidates(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.maturity != "rejected"
        and not is_generic_idea_title(candidate.title)
        and candidate.novelty_status in {"plausible", "strong"}
        and (
            candidate.closest_prior_work_ids
            or candidate.supporting_paper_ids
            or candidate.evidence_span_ids
            or candidate.evidence_score > 0
        )
        and candidate.reviewer_risk_score < 0.9
    ]


def _decision_id(project_id: str, iteration: int, decision_type: str, reason: str, evidence: list[str]) -> str:
    digest = hashlib.sha1("::".join([project_id, str(iteration), decision_type, reason, *evidence]).encode("utf-8")).hexdigest()[:8]
    return f"idea-search-decision-{utc_now_compact()}-{iteration}-{slugify(decision_type)}-{digest}"
