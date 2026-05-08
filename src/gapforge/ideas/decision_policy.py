"""Decision policy for active v2 idea search."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.ideas.generator import is_generic_idea_title
from gapforge.ideas.models import IdeaCandidate


@dataclass(frozen=True, slots=True)
class IdeaSearchAssessment:
    project_id: str
    iteration: int
    max_iterations: int
    portfolio_count: int = 0
    candidates: list[IdeaCandidate] = field(default_factory=list)
    constructive_gap_count: int = 0
    mutation_count: int = 0
    transfer_count: int = 0
    review_count: int = 0


@dataclass(frozen=True, slots=True)
class IdeaSearchAction:
    decision_type: str
    reason: str
    expected_value: str
    evidence: list[str] = field(default_factory=list)
    status: str = "pending"
    terminal: bool = False


class IdeaSearchDecisionPolicy:
    """Deterministic policy for deciding the next v2 idea-search action."""

    def decide(self, assessment: IdeaSearchAssessment) -> IdeaSearchAction:
        active = _active_candidates(assessment.candidates)
        weak = _weak_candidates(active)
        evidence_lacking = _evidence_lacking(active)
        novelty_unknown = [candidate for candidate in active if candidate.novelty_status in {"unchecked", "unknown"}]
        survivors = _surviving_candidates(active)

        if not assessment.portfolio_count:
            return IdeaSearchAction(
                decision_type="generate_portfolio",
                reason="No topic portfolio exists yet.",
                expected_value="Explore diverse topic variants before committing to a first obvious idea.",
                evidence=["portfolio_count=0"],
                status="running",
            )
        if not active:
            if assessment.iteration >= assessment.max_iterations:
                return IdeaSearchAction(
                    decision_type="create_agenda",
                    reason="No surviving candidates remain within the idea-search budget.",
                    expected_value="Preserve a useful research agenda instead of forcing a bad idea.",
                    evidence=[f"iteration={assessment.iteration}", f"max_iterations={assessment.max_iterations}"],
                    status="complete",
                    terminal=True,
                )
            return IdeaSearchAction(
                decision_type="synthesize_ideas",
                reason="No active idea candidates exist.",
                expected_value="Generate a diverse seed pool from the topic portfolio and project memory.",
                evidence=["active_candidates=0"],
                status="running",
            )
        if weak and assessment.mutation_count == 0:
            return IdeaSearchAction(
                decision_type="mutate_ideas",
                reason="Existing ideas are generic, rejected, or weak.",
                expected_value="Reframe weak ideas and add constructive gap paths before discarding the topic.",
                evidence=[f"weak_candidates={len(weak)}"],
                status="running",
            )
        if evidence_lacking:
            return IdeaSearchAction(
                decision_type="search_variant",
                reason="Ideas lack evidence or closest-prior-work anchors.",
                expected_value="Search topic variants and constructive transfers before novelty decisions.",
                evidence=[f"evidence_lacking={len(evidence_lacking)}"],
                status="running",
            )
        if novelty_unknown:
            return IdeaSearchAction(
                decision_type="run_prior_work",
                reason="Novelty is unchecked or unknown for active candidates.",
                expected_value="Run prior-work review before any candidate can be considered accepted.",
                evidence=[f"novelty_unknown={len(novelty_unknown)}"],
                status="running",
            )
        if len(survivors) > 1:
            return IdeaSearchAction(
                decision_type="run_tournament",
                reason="Several candidates survived initial evidence gates.",
                expected_value="Compare candidates on novelty, feasibility, impact, evidence, and reviewer risk.",
                evidence=[f"survivors={len(survivors)}"],
                status="running",
            )
        if len(survivors) == 1:
            return IdeaSearchAction(
                decision_type="request_feedback",
                reason="One candidate appears to pass deterministic gates and needs human review.",
                expected_value="Prevent the controller from accepting an idea without human judgment.",
                evidence=[survivors[0].id],
                status="blocked",
                terminal=True,
            )
        if assessment.iteration >= assessment.max_iterations:
            return IdeaSearchAction(
                decision_type="create_agenda",
                reason="No candidate passed gates before the search budget expired.",
                expected_value="Return a research agenda fallback rather than fake success.",
                evidence=[f"iteration={assessment.iteration}", f"max_iterations={assessment.max_iterations}"],
                status="complete",
                terminal=True,
            )
        return IdeaSearchAction(
            decision_type="synthesize_ideas",
            reason="No candidate currently passes gates, but search budget remains.",
            expected_value="Try another synthesis pass before falling back to an agenda.",
            evidence=[f"iteration={assessment.iteration}", f"max_iterations={assessment.max_iterations}"],
            status="running",
        )


def _active_candidates(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    return [candidate for candidate in candidates if candidate.maturity != "rejected"]


def _weak_candidates(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    return [
        candidate
        for candidate in candidates
        if is_generic_idea_title(candidate.title)
        or candidate.novelty_status in {"weak", "likely_duplicate"}
        or candidate.idea_yield_score < 0.2
        or "generic" in candidate.summary.lower()
        or "generic" in candidate.likely_failure_mode.lower()
    ]


def _evidence_lacking(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    return [
        candidate
        for candidate in candidates
        if not candidate.closest_prior_work_ids
        and not candidate.supporting_paper_ids
        and not candidate.evidence_span_ids
        and candidate.evidence_score <= 0.0
    ]


def _surviving_candidates(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    return [
        candidate
        for candidate in candidates
        if not is_generic_idea_title(candidate.title)
        and candidate.novelty_status in {"plausible", "strong"}
        and (
            candidate.closest_prior_work_ids
            or candidate.supporting_paper_ids
            or candidate.evidence_span_ids
            or candidate.evidence_score > 0
        )
        and candidate.reviewer_risk_score < 0.9
    ]
