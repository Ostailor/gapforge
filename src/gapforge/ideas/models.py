"""Typed models for v2 idea discovery."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance

CONTRIBUTION_TYPES = {
    "benchmark",
    "measurement",
    "method",
    "theory",
    "negative_result",
    "replication",
    "dataset",
    "survey",
    "system",
    "evaluation_protocol",
    "tooling",
    "hybrid",
}
IDEA_NOVELTY_STATUSES = {"unchecked", "likely_duplicate", "weak", "plausible", "strong", "unknown"}
IDEA_MATURITIES = {"seed", "candidate", "rejected", "agenda_item", "experiment_ready", "manuscript_ready"}
IDEA_LINK_TYPES = {"supports", "counters", "contextual", "closest_prior_work", "missing_evidence"}
IDEA_REVIEW_STATUSES = {"accepted", "rejected", "revise", "uncertain"}
IDEA_NOVELTY_VERDICTS = {"reject", "revise", "pursue", "unknown"}
IDEA_FEEDBACK_ACTIONS = {"upvote", "downvote", "reject", "request_mutation", "request_search", "accept"}
IDEA_SEARCH_DECISION_TYPES = {
    "generate_portfolio",
    "search_variant",
    "synthesize_ideas",
    "mutate_ideas",
    "run_prior_work",
    "run_tournament",
    "request_feedback",
    "create_agenda",
    "stop",
}
IDEA_MUTATION_STRATEGIES = {
    "metric_shift",
    "observable_shift",
    "threat_model_shift",
    "benchmark_shift",
    "dataset_shift",
    "baseline_shift",
    "guarantee_shift",
    "domain_transfer",
    "contribution_type_shift",
    "positive_to_negative_result",
    "method_to_measurement",
    "method_to_benchmark",
    "empirical_to_theory",
    "broad_to_minimum_publishable_unit",
    "reviewer_objection_to_new_idea",
}
AGENDA_STEP_TYPES = {
    "search",
    "benchmark",
    "dataset",
    "baseline_study",
    "replication",
    "theory",
    "measurement",
    "human_review",
}


@dataclass(slots=True)
class IdeaCandidate:
    id: str
    project_id: str
    source_topic_id: str
    title: str
    summary: str
    contribution_type: str = "hybrid"
    core_claim: str = ""
    proposed_experiment: str = ""
    expected_baselines: list[str] = field(default_factory=list)
    expected_metrics: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    evidence_span_ids: list[str] = field(default_factory=list)
    supporting_paper_ids: list[str] = field(default_factory=list)
    counterevidence_paper_ids: list[str] = field(default_factory=list)
    novelty_status: str = "unchecked"
    tractability_score: float = 0.0
    impact_score: float = 0.0
    evidence_score: float = 0.0
    reviewer_risk_score: float = 0.0
    idea_yield_score: float = 0.0
    maturity: str = "seed"
    likely_failure_mode: str = ""
    rejection_reason: str = ""
    human_feedback_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-discovery"))


@dataclass(slots=True)
class IdeaBank:
    id: str
    project_id: str
    root_topic: str
    candidate_ids: list[str] = field(default_factory=list)
    rejected_candidate_ids: list[str] = field(default_factory=list)
    selected_candidate_id: str = ""
    agenda_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-bank"))


@dataclass(slots=True)
class IdeaEvidenceLink:
    id: str
    idea_id: str
    link_type: str
    paper_id: str = ""
    evidence_span_id: str = ""
    claim_id: str = ""
    note: str = ""
    confidence: str = "medium"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-evidence-link"))


@dataclass(slots=True)
class IdeaReviewRecord:
    id: str
    idea_id: str
    reviewer: str
    status: str = "uncertain"
    novelty_judgment: str = ""
    feasibility_judgment: str = ""
    impact_judgment: str = ""
    required_fixes: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-human-review"))


@dataclass(slots=True)
class IdeaPreferenceProfile:
    id: str
    project_id: str
    preferred_contribution_types: list[str] = field(default_factory=list)
    preferred_domains: list[str] = field(default_factory=list)
    risk_tolerance: str = ""
    time_budget: str = ""
    compute_budget: str = ""
    publication_target: str = ""
    avoid_topics: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-preferences"))


@dataclass(slots=True)
class IdeaFeedbackRecord:
    id: str
    idea_id: str
    reviewer: str
    action: str
    rationale: str = ""
    preferred_mutations: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-feedback"))


@dataclass(slots=True)
class IdeaNoveltyAssessment:
    id: str
    idea_id: str
    closest_prior_work_ids: list[str] = field(default_factory=list)
    similarity_summary: str = ""
    missing_searches: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    verdict: str = "unknown"
    novelty_strength: str = "unknown"
    required_mutation: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-novelty-loop"))


@dataclass(slots=True)
class IdeaScoreRecord:
    idea_id: str
    evidence_score: float = 0.0
    novelty_score: float = 0.0
    experimentability_score: float = 0.0
    tractability_score: float = 0.0
    impact_score: float = 0.0
    reviewer_risk_score: float = 0.0
    time_to_demo_score: float = 0.0
    benchmark_score: float = 0.0
    baseline_score: float = 0.0
    cross_domain_score: float = 0.0
    human_preference_score: float = 0.0
    total_score: float = 0.0
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-tournament"))


@dataclass(slots=True)
class IdeaTournament:
    id: str
    project_id: str
    candidate_ids: list[str] = field(default_factory=list)
    score_records: list[IdeaScoreRecord] = field(default_factory=list)
    selected_candidate_id: str = ""
    rejected_candidate_ids: list[str] = field(default_factory=list)
    agenda_id: str = ""
    selection_reason: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-tournament"))


@dataclass(slots=True)
class IdeaMutationRecord:
    id: str
    source_idea_id: str
    mutated_idea_id: str
    strategy: str
    what_changed: str
    why_it_may_help: str
    inherited_risks: list[str] = field(default_factory=list)
    required_new_searches: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-mutation"))


@dataclass(slots=True)
class ConstructiveGapCandidate:
    id: str
    project_id: str
    title: str
    contribution_type: str
    problem: str
    why_existing_work_makes_this_useful: str
    minimum_artifact: str
    minimum_experiment: str
    required_baselines: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    novelty_risk: str = ""
    reviewer_risk: str = ""
    feasibility: str = ""
    evidence_links: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="constructive-gap"))


@dataclass(slots=True)
class IdeaTransferCandidate:
    id: str
    source_field: str
    source_concept: str
    target_problem: str
    transfer_mechanism: str
    target_idea_id: str = ""
    required_adaptation: str = ""
    what_breaks: str = ""
    supporting_source_papers: list[str] = field(default_factory=list)
    required_searches: list[str] = field(default_factory=list)
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-cross-domain-transfer"))


@dataclass(slots=True)
class IdeaSearchDecision:
    id: str
    project_id: str
    iteration: int
    decision_type: str
    reason: str
    expected_value: str = ""
    evidence: list[str] = field(default_factory=list)
    status: str = "pending"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-search-controller"))


@dataclass(slots=True)
class AgendaStep:
    id: str
    agenda_id: str
    step_type: str
    description: str
    required_artifact: str
    success_criteria: str
    next_decision: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="research-agenda"))


@dataclass(slots=True)
class ResearchAgenda:
    id: str
    project_id: str
    root_topic: str
    blocker_summary: str
    agenda_steps: list[AgendaStep] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    decision_points: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    estimated_effort: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="research-agenda"))


def validate_contribution_type(value: str) -> str:
    if value not in CONTRIBUTION_TYPES:
        raise ValueError(f"Unsupported idea contribution type: {value}. Expected one of: {', '.join(sorted(CONTRIBUTION_TYPES))}")
    return value


def validate_novelty_status(value: str) -> str:
    if value not in IDEA_NOVELTY_STATUSES:
        raise ValueError(f"Unsupported idea novelty status: {value}. Expected one of: {', '.join(sorted(IDEA_NOVELTY_STATUSES))}")
    return value


def validate_maturity(value: str) -> str:
    if value not in IDEA_MATURITIES:
        raise ValueError(f"Unsupported idea maturity: {value}. Expected one of: {', '.join(sorted(IDEA_MATURITIES))}")
    return value


def validate_link_type(value: str) -> str:
    if value not in IDEA_LINK_TYPES:
        raise ValueError(f"Unsupported idea evidence link type: {value}. Expected one of: {', '.join(sorted(IDEA_LINK_TYPES))}")
    return value


def validate_review_status(value: str) -> str:
    if value not in IDEA_REVIEW_STATUSES:
        raise ValueError(f"Unsupported idea review status: {value}. Expected one of: {', '.join(sorted(IDEA_REVIEW_STATUSES))}")
    return value


def validate_idea_feedback_action(value: str) -> str:
    if value not in IDEA_FEEDBACK_ACTIONS:
        raise ValueError(f"Unsupported idea feedback action: {value}. Expected one of: {', '.join(sorted(IDEA_FEEDBACK_ACTIONS))}")
    return value


def validate_idea_novelty_verdict(value: str) -> str:
    if value not in IDEA_NOVELTY_VERDICTS:
        raise ValueError(f"Unsupported idea novelty verdict: {value}. Expected one of: {', '.join(sorted(IDEA_NOVELTY_VERDICTS))}")
    return value


def validate_mutation_strategy(value: str) -> str:
    if value not in IDEA_MUTATION_STRATEGIES:
        raise ValueError(f"Unsupported idea mutation strategy: {value}. Expected one of: {', '.join(sorted(IDEA_MUTATION_STRATEGIES))}")
    return value


def validate_idea_search_decision_type(value: str) -> str:
    if value not in IDEA_SEARCH_DECISION_TYPES:
        raise ValueError(
            f"Unsupported idea search decision type: {value}. Expected one of: {', '.join(sorted(IDEA_SEARCH_DECISION_TYPES))}"
        )
    return value


def validate_agenda_step_type(value: str) -> str:
    if value not in AGENDA_STEP_TYPES:
        raise ValueError(f"Unsupported agenda step type: {value}. Expected one of: {', '.join(sorted(AGENDA_STEP_TYPES))}")
    return value
