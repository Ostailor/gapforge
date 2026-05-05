"""Full review panel and rebuttal planning workflow."""

from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.llm.base import LLMClient
from gapforge.models import (
    ClaimGraph,
    ExperimentPlan,
    ExperimentProtocol,
    NoveltyDossier,
    Provenance,
    RebuttalPlan,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ReviewerReview,
    ReviewPanel,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.scoring import confidence_from_evidence, decision_risk, score_from_issues
from gapforge.state import ResearchStateManager, utc_now_iso


class ReviewPanelBuilder:
    """Build deterministic, evidence-linked review panels for project directions."""

    def __init__(self, config: GapForgeConfig, *, llm_client: LLMClient | None = None) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.llm_client = llm_client

    def build_for_project(self, project_id: str, direction_id: str) -> ReviewPanel:
        program = self.project_manager.load_project(project_id)
        direction = _require_direction(program, direction_id)
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        context = _PanelContext.from_program(program, states, direction)
        panel = build_review_panel(direction, context, llm_client=self.llm_client)
        program.review_panels = _replace_panel(program.review_panels, panel)
        self.project_manager.save_project(program)
        _write_direction_panel(Path(program.project.root_dir), panel)
        return panel

    def rebuttal_plan_for_project(self, project_id: str, direction_id: str) -> list[RebuttalPlan]:
        panel = self._ensure_panel(project_id, direction_id)
        return panel.rebuttal_plan

    def meta_review_for_project(self, project_id: str, direction_id: str) -> str:
        panel = self._ensure_panel(project_id, direction_id)
        return panel.meta_review

    def _ensure_panel(self, project_id: str, direction_id: str) -> ReviewPanel:
        program = self.project_manager.load_project(project_id)
        panel = next((item for item in program.review_panels if item.experiment_or_direction_id == direction_id), None)
        if panel is not None:
            return panel
        return self.build_for_project(project_id, direction_id)


class _PanelContext:
    def __init__(
        self,
        *,
        experiment: ExperimentPlan | None,
        protocol: ExperimentProtocol | None,
        matrix: RelatedWorkMatrix | None,
        dossier: NoveltyDossier | None,
        claim_graph: ClaimGraph | None,
    ) -> None:
        self.experiment = experiment
        self.protocol = protocol
        self.matrix = matrix
        self.dossier = dossier
        self.claim_graph = claim_graph

    @classmethod
    def from_program(cls, program: ResearchProgramState, states: list[ResearchRunState], direction: ResearchDirection) -> _PanelContext:
        experiment = _first_experiment(states, direction)
        return cls(
            experiment=experiment,
            protocol=_first_protocol(program, states, direction, experiment),
            matrix=_first_matrix(program, states, direction),
            dossier=_first_dossier(states, direction),
            claim_graph=program.claim_graph,
        )


def build_review_panel(
    direction: ResearchDirection,
    context: _PanelContext,
    *,
    llm_client: LLMClient | None = None,
) -> ReviewPanel:
    reviews = [
        _technical_review(direction, context),
        _novelty_review(direction, context),
        _empirical_review(direction, context),
        _theory_review(direction, context),
        _ethics_review(direction, context),
    ]
    if llm_client is not None:
        reviews.append(_safe_llm_review(direction, context, llm_client))
    risk = decision_risk(reviews)
    required_changes = _required_changes(reviews)
    rebuttals = [_rebuttal_for(review, context) for review in reviews if review.required_fixes or review.fatal_flaws]
    return ReviewPanel(
        experiment_or_direction_id=direction.id,
        reviewer_reviews=reviews,
        area_chair_summary=_area_chair_summary(direction, reviews, risk),
        meta_review=_meta_review(direction, reviews, risk, required_changes),
        decision_risk=risk,
        rebuttal_plan=rebuttals,
        required_changes=required_changes,
        provenance=Provenance(
            created_by_skill="review-panel",
            source_ids=[direction.id, *direction.linked_gap_ids, *direction.linked_experiment_ids],
            timestamp=utc_now_iso(),
            reasoning_summary="Aggregated deterministic reviewer roles into an actionable review and rebuttal plan.",
        ),
    )


def render_review_panel_markdown(panel: ReviewPanel) -> str:
    lines = [
        "# Review Panel",
        "",
        f"- Target: `{panel.experiment_or_direction_id}`",
        f"- Decision risk: {panel.decision_risk}",
        "",
        "## Area Chair Summary",
        "",
        panel.area_chair_summary or "No area chair summary generated.",
        "",
        "## Meta Review",
        "",
        panel.meta_review or "No meta-review generated.",
        "",
        "## Reviews",
        "",
    ]
    for review in panel.reviewer_reviews:
        lines.extend(
            [
                f"### {review.reviewer_id}: {review.role}",
                "",
                f"- Score: {review.score:.1f}",
                f"- Confidence: {review.confidence}",
                f"- Evidence/prior work: {', '.join(review.evidence_or_prior_work) or 'none'}",
                "",
                "**Strengths**",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in review.strengths] or ["- none"])
        lines.extend(["", "**Weaknesses**", ""])
        lines.extend([f"- {item}" for item in review.weaknesses] or ["- none"])
        lines.extend(["", "**Questions**", ""])
        lines.extend([f"- {item}" for item in review.questions] or ["- none"])
        lines.extend(["", "**Required Fixes**", ""])
        lines.extend([f"- {item}" for item in review.required_fixes] or ["- none"])
        lines.extend(["", "**Fatal Flaws**", ""])
        lines.extend([f"- {item}" for item in review.fatal_flaws] or ["- none"])
        lines.append("")
    lines.extend(["## Required Changes", ""])
    lines.extend([f"- {item}" for item in panel.required_changes] or ["- none"])
    lines.extend(["", "## Rebuttal Plan", ""])
    for plan in panel.rebuttal_plan:
        lines.extend(
            [
                f"### `{plan.target_review_id}`",
                "",
                f"- Strategy: {plan.response_strategy}",
                f"- Evidence needed: {', '.join(plan.evidence_needed) or 'none'}",
                f"- Experiments to add: {', '.join(plan.experiments_to_add) or 'none'}",
                f"- Citations to add: {', '.join(plan.citations_to_add) or 'none'}",
                f"- Claims to soften: {', '.join(plan.claims_to_soften) or 'none'}",
                f"- Risks: {', '.join(plan.risks) or 'none'}",
                "",
            ]
        )
    if not panel.rebuttal_plan:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _technical_review(direction: ResearchDirection, context: _PanelContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    protocol = context.protocol
    experiment = context.experiment
    if protocol is None:
        fatal.append("No experiment protocol is available.")
        fixes.append("Generate `gapforge experiment-protocol` before treating the direction as submission-ready.")
    else:
        evidence.append(protocol.id)
        if not protocol.hypothesis:
            weaknesses.append("Protocol lacks a concrete hypothesis.")
            fixes.append("Add a testable hypothesis to the protocol.")
        if not protocol.failure_modes:
            weaknesses.append("Protocol does not list failure modes.")
            fixes.append("Add failure modes and falsification checks.")
        if not protocol.reproducibility_checklist.metric_definitions:
            weaknesses.append("Metric definitions are incomplete.")
            fixes.append("Complete the reproducibility checklist metric definitions.")
    if experiment is not None:
        evidence.append(experiment.id)
        if not experiment.what_result_would_falsify_the_idea:
            weaknesses.append("Experiment lacks a falsification condition.")
            fixes.append("State what result would falsify the claim.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "R1",
        "technical",
        score,
        strengths=["The direction is linked to an executable protocol."] if protocol is not None else [],
        weaknesses=weaknesses,
        questions=["Which result would falsify the central claim?"] if weaknesses else [],
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
        has_full_protocol=protocol is not None,
    )


def _novelty_review(direction: ResearchDirection, context: _PanelContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    dossier = context.dossier
    if dossier is None:
        fatal.append("No novelty dossier is linked to the direction.")
        fixes.append("Build a closest-prior-work dossier and compare against top prior work.")
    else:
        evidence.extend(dossier.top_prior_work or dossier.candidates_considered)
        if dossier.verdict == "reject":
            fatal.append("Novelty dossier rejects the idea as duplicative or too close to prior work.")
            fixes.append("Reject or reframe the direction before manuscript work.")
        elif dossier.verdict == "unknown":
            fatal.append("Novelty dossier is unknown; closest prior work is not resolved.")
            fixes.append("Complete missing novelty searches before claiming contribution.")
        elif dossier.verdict == "revise":
            weaknesses.append("Novelty dossier requires revision before pursuit.")
            fixes.append(dossier.decisive_difference_needed or "Define a decisive difference from closest prior work.")
        if dossier.missing_searches:
            weaknesses.append("Novelty dossier still has missing searches.")
            fixes.append("Resolve missing searches: " + "; ".join(dossier.missing_searches[:3]))
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "R2",
        "novelty",
        score,
        strengths=["Closest prior work is represented."] if dossier is not None and dossier.top_prior_work else [],
        weaknesses=weaknesses,
        questions=["What is the decisive difference from the closest prior work?"],
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
        has_full_protocol=context.protocol is not None,
    )


def _empirical_review(direction: ResearchDirection, context: _PanelContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    protocol = context.protocol
    matrix = context.matrix
    baselines: list[str] = []
    if protocol is not None:
        baselines.extend(candidate.paper_id or candidate.baseline_name for candidate in protocol.baselines)
        evidence.append(protocol.id)
    if context.experiment is not None:
        baselines.extend(context.experiment.baselines)
        evidence.append(context.experiment.id)
    if matrix is not None:
        baselines.extend(matrix.baseline_paper_ids)
        evidence.extend(matrix.baseline_paper_ids)
    if not any(item for item in baselines):
        fatal.append("No baseline candidate is linked to the experiment, protocol, or related-work matrix.")
        fixes.append("Add closest-prior-work and simple baseline candidates before submission.")
    if protocol is not None:
        if not protocol.metrics:
            fatal.append("Protocol has no metrics.")
            fixes.append("Define primary and secondary metrics.")
        if not protocol.statistical_tests:
            weaknesses.append("Protocol has no statistical tests.")
            fixes.append("Add confidence intervals or appropriate paired tests.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "R3",
        "empirical",
        score,
        strengths=["Baselines are linked through the protocol or related-work matrix."] if baselines else [],
        weaknesses=weaknesses,
        questions=["Are the baselines strong enough for a skeptical empirical reviewer?"],
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
        has_full_protocol=protocol is not None,
    )


def _theory_review(direction: ResearchDirection, context: _PanelContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    if context.claim_graph is not None:
        evidence.append("claim_graph")
        if context.claim_graph.unresolved_contradictions:
            fatal.append("Project claim graph has unresolved contradictions.")
            fixes.append("Resolve claim graph contradictions or soften claims before submission.")
    if context.matrix is not None:
        evidence.extend(context.matrix.must_read_paper_ids[:5])
        direct = [entry.paper_id for entry in context.matrix.entries if entry.relationship in {"directly_solves", "directly solves"}]
        if direct:
            fatal.append("Related-work matrix includes prior work that directly solves the direction.")
            fixes.append("Downgrade or reject the direction unless the direct-solve classification is corrected.")
            evidence.extend(direct)
    else:
        weaknesses.append("No related-work matrix is available for theory and positioning review.")
        fixes.append("Build a related-work matrix before manuscript framing.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "R4",
        "theory",
        score,
        strengths=["Positioning is linked to a related-work matrix."] if context.matrix is not None else [],
        weaknesses=weaknesses,
        questions=["Does the paper overstate theory relative to evidence?"],
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
        has_full_protocol=context.protocol is not None,
    )


def _ethics_review(direction: ResearchDirection, context: _PanelContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    evidence: list[str] = []
    protocol = context.protocol
    if protocol is not None:
        evidence.append(protocol.id)
        if not protocol.safety_ethics_notes:
            weaknesses.append("Protocol lacks safety or ethics notes.")
            fixes.append("Add safety, ethics, and misuse considerations to the protocol.")
    elif context.experiment is None:
        weaknesses.append("No experiment context is available for ethics review.")
        fixes.append("Generate an experiment plan and protocol before ethics review.")
    score = score_from_issues(base=8.0, major=len(weaknesses))
    return _review(
        "R5",
        "ethics",
        score,
        strengths=["Safety and ethics notes are present."] if protocol is not None and protocol.safety_ethics_notes else [],
        weaknesses=weaknesses,
        questions=["Could false positives, misuse, or deployment harms affect the study?"],
        required_fixes=fixes,
        evidence=evidence,
        has_full_protocol=protocol is not None,
    )


def _safe_llm_review(direction: ResearchDirection, context: _PanelContext, llm_client: LLMClient) -> ReviewerReview:
    prompt = (
        "Produce a conservative reviewer note for this GapForge direction. "
        "Do not invent results or citations. Return JSON for schema reviewer-simulation.\n"
        f"Direction ID: {direction.id}\n"
        f"Title: {direction.title}\n"
        f"Protocol: {context.protocol.id if context.protocol else 'missing'}\n"
    )
    try:
        payload = llm_client.complete_json(prompt, schema_name="reviewer-simulation")
    except Exception as exc:  # pragma: no cover - defensive provider boundary
        return _review(
            "LLM",
            "area_chair",
            1.0,
            weaknesses=[f"LLM reviewer unavailable or invalid: {exc}"],
            required_fixes=["Use deterministic review panel output until model output is valid."],
            fatal_flaws=["Optional LLM reviewer did not produce usable grounded output."],
            evidence=[],
            confidence="low",
        )
    final = str(payload.get("final_recommendation", "not_ready"))
    return _review(
        "LLM",
        "area_chair",
        4.0 if final == "not_ready" else 6.0,
        weaknesses=["Fake/provider reviewer produced no evidence-backed acceptance rationale."],
        required_fixes=["Treat optional LLM review as advisory; keep deterministic blockers authoritative."],
        evidence=[],
        confidence="low",
    )


def _review(
    reviewer_id: str,
    role: str,
    score: float,
    *,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    questions: list[str] | None = None,
    required_fixes: list[str] | None = None,
    fatal_flaws: list[str] | None = None,
    evidence: list[str] | None = None,
    has_full_protocol: bool = False,
    confidence: str | None = None,
) -> ReviewerReview:
    evidence_items = _dedupe(evidence or [])
    return ReviewerReview(
        reviewer_id=reviewer_id,
        role=role,
        score=score,
        confidence=confidence or confidence_from_evidence(len(evidence_items), has_full_protocol=has_full_protocol),
        strengths=strengths or [],
        weaknesses=weaknesses or [],
        questions=questions or [],
        required_fixes=_dedupe(required_fixes or []),
        fatal_flaws=_dedupe(fatal_flaws or []),
        evidence_or_prior_work=evidence_items,
        provenance=Provenance(
            created_by_skill="review-panel",
            source_ids=evidence_items,
            timestamp=utc_now_iso(),
            reasoning_summary=f"Deterministic {role} reviewer scored public artifacts and evidence links.",
        ),
    )


def _rebuttal_for(review: ReviewerReview, context: _PanelContext) -> RebuttalPlan:
    citations = _citations_for_review(review, context)
    experiments = []
    if review.role in {"empirical", "technical"}:
        experiments.extend(["Add or update the experiment protocol; do not claim results until the experiment is run."])
    if review.role == "novelty":
        experiments.extend(["Run additional closest-prior-work searches and update the novelty dossier."])
    return RebuttalPlan(
        target_review_id=review.reviewer_id,
        response_strategy=_response_strategy(review),
        evidence_needed=review.evidence_or_prior_work or ["Evidence locator or prior-work ID for each response claim."],
        experiments_to_add=_dedupe(experiments),
        citations_to_add=citations,
        claims_to_soften=_claims_to_soften(review),
        risks=["Do not present planned or expected results as completed findings."],
        provenance=Provenance(
            created_by_skill="review-panel",
            source_ids=review.evidence_or_prior_work,
            timestamp=utc_now_iso(),
            reasoning_summary="Converted reviewer weaknesses into an evidence-seeking rebuttal plan without inventing results.",
        ),
    )


def _response_strategy(review: ReviewerReview) -> str:
    if review.fatal_flaws:
        return "Do not rebut by assertion; fix the fatal flaw with evidence, an added experiment, or a softened claim."
    if review.required_fixes:
        return "Address the required fix directly and cite the updated artifact or prior work."
    return "Acknowledge the question and point to existing evidence."


def _citations_for_review(review: ReviewerReview, context: _PanelContext) -> list[str]:
    citations = [
        item for item in review.evidence_or_prior_work if item and not item.startswith("protocol") and not item.startswith("experiment")
    ]
    if context.matrix is not None and review.role in {"novelty", "empirical", "theory"}:
        citations.extend(context.matrix.must_read_paper_ids[:5])
    if context.dossier is not None and review.role == "novelty":
        citations.extend(context.dossier.top_prior_work[:5])
    return _dedupe(citations)


def _claims_to_soften(review: ReviewerReview) -> list[str]:
    claims = []
    if review.role == "novelty" and (review.fatal_flaws or review.weaknesses):
        claims.append("Soften novelty claims until closest prior work and missing searches are resolved.")
    if review.role == "theory" and review.fatal_flaws:
        claims.append("Soften theory and generality claims until contradictions or direct-solve prior work are resolved.")
    if review.role == "empirical" and review.fatal_flaws:
        claims.append("Soften empirical claims until baselines and metrics are complete.")
    return claims


def _area_chair_summary(direction: ResearchDirection, reviews: list[ReviewerReview], risk: str) -> str:
    fatal_roles = [review.role for review in reviews if review.fatal_flaws]
    if fatal_roles:
        return (
            f"The direction `{direction.id}` has likely blocking issues from {', '.join(fatal_roles)} reviewers. "
            "It should not be framed as submission-ready until those issues are fixed."
        )
    return f"The direction `{direction.id}` has decision risk `{risk}` and can proceed only with the listed required changes tracked."


def _meta_review(direction: ResearchDirection, reviews: list[ReviewerReview], risk: str, required_changes: list[str]) -> str:
    average = sum(review.score for review in reviews) / max(1, len(reviews))
    lines = [
        f"Average review score: {average:.1f}/10.",
        f"Decision risk: {risk}.",
    ]
    if required_changes:
        lines.append("Required changes remain before manuscript or rebuttal work can be credible.")
    else:
        lines.append("No blocking deterministic review changes were found, but this is not a substitute for human peer review.")
    if direction.maturity != "manuscript_ready":
        lines.append(f"Direction maturity is `{direction.maturity}`, so manuscript claims should remain provisional.")
    return " ".join(lines)


def _required_changes(reviews: list[ReviewerReview]) -> list[str]:
    changes = []
    for review in reviews:
        changes.extend(review.fatal_flaws)
        changes.extend(review.required_fixes)
    return _dedupe(changes)


def _first_experiment(states: list[ResearchRunState], direction: ResearchDirection) -> ExperimentPlan | None:
    return next(
        (
            experiment
            for state in states
            for experiment in state.experiments
            if experiment.id in direction.linked_experiment_ids or set(experiment.linked_gap_ids).intersection(direction.linked_gap_ids)
        ),
        None,
    )


def _first_protocol(
    program: ResearchProgramState,
    states: list[ResearchRunState],
    direction: ResearchDirection,
    experiment: ExperimentPlan | None,
) -> ExperimentProtocol | None:
    protocols = [*program.experiment_protocols, *[protocol for state in states for protocol in state.experiment_protocols]]
    return next(
        (
            protocol
            for protocol in protocols
            if protocol.direction_id == direction.id
            or protocol.direction_id in direction.linked_gap_ids
            or (experiment is not None and protocol.linked_experiment_plan_id == experiment.id)
        ),
        None,
    )


def _first_matrix(program: ResearchProgramState, states: list[ResearchRunState], direction: ResearchDirection) -> RelatedWorkMatrix | None:
    matrices = [*program.related_work_matrices, *[matrix for state in states for matrix in state.related_work_matrices]]
    return next(
        (matrix for matrix in matrices if matrix.direction_id == direction.id or matrix.direction_id in direction.linked_gap_ids), None
    )


def _first_dossier(states: list[ResearchRunState], direction: ResearchDirection) -> NoveltyDossier | None:
    return next(
        (
            dossier
            for state in states
            for dossier in state.novelty_dossiers
            if dossier.target_id in direction.linked_gap_ids or dossier.target_id in direction.linked_novelty_dossier_ids
        ),
        None,
    )


def _require_direction(program: ResearchProgramState, direction_id: str) -> ResearchDirection:
    direction = next((item for item in program.research_directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _replace_panel(existing: list[ReviewPanel], panel: ReviewPanel) -> list[ReviewPanel]:
    return [item for item in existing if item.experiment_or_direction_id != panel.experiment_or_direction_id] + [panel]


def _write_direction_panel(project_root: Path, panel: ReviewPanel) -> None:
    out_dir = project_root / "review_panels"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{panel.experiment_or_direction_id}.md").write_text(render_review_panel_markdown(panel), encoding="utf-8")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
