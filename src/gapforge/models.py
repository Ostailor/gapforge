"""Typed domain models for research ideation."""

from __future__ import annotations

import types
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(cast(Any, value)).items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value


T = TypeVar("T")


def from_dict(model: type[T], data: dict[str, Any]) -> T:
    """Build a dataclass from a JSON dictionary, recursively handling known lists."""

    kwargs: dict[str, Any] = {}
    type_hints = get_type_hints(model)
    for model_field in fields(cast(Any, model)):
        if model_field.name not in data:
            continue
        raw_value = data[model_field.name]
        kwargs[model_field.name] = _coerce_value(type_hints.get(model_field.name, model_field.type), raw_value)
    return model(**kwargs)


def _coerce_value(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType) and type(None) in args:
        if value is None:
            return None
        non_none = next(arg for arg in args if arg is not type(None))
        return _coerce_value(non_none, value)
    if origin is list and args and isinstance(value, list):
        item_type = args[0]
        if is_dataclass(item_type):
            return [from_dict(cast(Any, item_type), item) if isinstance(item, dict) else item for item in value]
        return value
    if origin is dict and args and isinstance(value, dict):
        value_type = args[1]
        if is_dataclass(value_type):
            return {key: from_dict(cast(Any, value_type), item) if isinstance(item, dict) else item for key, item in value.items()}
        return value
    if is_dataclass(annotation) and isinstance(value, dict):
        return from_dict(cast(Any, annotation), value)
    return value


@dataclass(slots=True)
class Provenance:
    created_by_skill: str
    source_ids: list[str] = field(default_factory=list)
    timestamp: str = ""
    reasoning_summary: str = ""


@dataclass(slots=True)
class ResearchTopic:
    text: str
    slug: str
    created_at: str


@dataclass(slots=True)
class Evidence:
    source_id: str
    quote: str
    locator: str
    confidence: str = "medium"
    source_paper_id: str = ""
    notes: str = ""


@dataclass(slots=True)
class Paper:
    id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    published_date: str = ""
    venue: str = ""
    source: str = ""
    url: str = ""
    pdf_url: str = ""
    doi: str = ""
    arxiv_id: str = ""
    openreview_id: str = ""
    semantic_scholar_id: str = ""
    citation_count: int = 0
    keywords: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="source-connector"))


@dataclass(slots=True)
class PaperNote:
    paper_id: str
    citation_key: str = ""
    one_sentence_summary: str = ""
    core_claims: list[str] = field(default_factory=list)
    method: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    main_results: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    stated_limitations: list[str] = field(default_factory=list)
    unstated_limitations: list[str] = field(default_factory=list)
    what_it_cannot_answer: list[str] = field(default_factory=list)
    useful_technical_tools: list[str] = field(default_factory=list)
    possible_connections: list[str] = field(default_factory=list)
    relevance_to_topic: str = ""
    confidence: str = "low"
    quotes_or_evidence_snippets: list[Evidence] = field(default_factory=list)
    created_by_skill: str = "unknown"
    source_basis: str = "metadata/abstract only"
    summary: str = ""
    methods: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class PaperTriageDecision:
    paper_id: str
    title: str
    tier: str
    score: float
    reasons: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    recommended_reading_depth: str = ""


@dataclass(slots=True)
class PaperTriageResult:
    topic: str
    decisions: list[PaperTriageDecision]
    tier_counts: dict[str, int] = field(default_factory=dict)
    max_tier1: int = 20
    scoring_summary: str = ""
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class Cluster:
    name: str
    description: str
    paper_ids: list[str]
    representative_papers: list[str]
    dominant_methods: list[str]
    open_questions: list[str]
    why_it_matters: str


@dataclass(slots=True)
class FieldMap:
    topic: str
    clusters: list[Cluster]
    major_questions: list[str] = field(default_factory=list)
    dominant_methods: list[str] = field(default_factory=list)
    common_datasets: list[str] = field(default_factory=list)
    common_metrics: list[str] = field(default_factory=list)
    key_papers_by_cluster: dict[str, list[str]] = field(default_factory=dict)
    newest_papers_by_cluster: dict[str, list[str]] = field(default_factory=dict)
    saturated_areas: list[str] = field(default_factory=list)
    underexplored_areas: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    adjacent_fields: list[str] = field(default_factory=list)
    initial_gap_candidates: list[str] = field(default_factory=list)
    confidence: str = "low"
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class Claim:
    id: str
    text: str
    type: str
    status: str = "unsupported"
    confidence: str = "medium"
    supporting_evidence: list[Evidence] = field(default_factory=list)
    counter_evidence: list[Evidence] = field(default_factory=list)
    source_paper_ids: list[str] = field(default_factory=list)
    created_by_skill: str = "unknown"
    needs_verification: bool = True
    notes: str = ""
    closest_prior_work: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class Gap:
    id: str
    description: str = ""
    title: str = ""
    type: str = "evaluation gap"
    supporting_paper_ids: list[str] = field(default_factory=list)
    supporting_claim_ids: list[str] = field(default_factory=list)
    counterevidence_claim_ids: list[str] = field(default_factory=list)
    why_existing_work_does_not_solve_it: str = ""
    why_it_matters: str = ""
    possible_research_questions: list[str] = field(default_factory=list)
    minimum_experiment_needed: str = ""
    risk_that_gap_is_fake: str = ""
    confidence: str = "low"
    novelty_status: str = "unchecked"
    closest_prior_work: list[str] = field(default_factory=list)
    linked_paper_ids: list[str] = field(default_factory=list)
    explicit_reason: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class Hypothesis:
    id: str
    text: str
    rationale: str
    gap_id: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class CrossDomainAnalogy:
    source_field: str
    source_concept: str
    target_gap_id: str
    why_it_maps: str
    what_breaks_in_the_mapping: str
    technical_transfer_candidate: str
    papers_or_sources_to_search: list[str]
    possible_experiment: str
    risk_of_fake_analogy: str
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class NoveltyAssessment:
    target_gap_or_hypothesis_id: str
    idea_summary: str
    closest_prior_work: list[str] = field(default_factory=list)
    similarity_to_prior_work: float = 0.0
    what_is_new: list[str] = field(default_factory=list)
    what_is_not_new: list[str] = field(default_factory=list)
    possible_reviewer_objection: str = ""
    decisive_difference_needed: str = ""
    search_queries_used: list[str] = field(default_factory=list)
    missing_searches: list[str] = field(default_factory=list)
    verdict: str = "unknown"
    novelty_strength: str = "unknown"
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ExperimentPlan:
    id: str
    title: str
    hypothesis_id: str = ""
    design: str = ""
    linked_gap_ids: list[str] = field(default_factory=list)
    hypothesis: str = ""
    core_claim_being_tested: str = ""
    minimum_viable_experiment: str = ""
    datasets_needed: list[str] = field(default_factory=list)
    baselines: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    statistical_tests: list[str] = field(default_factory=list)
    ablations: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    compute_requirements: str = ""
    implementation_steps: list[str] = field(default_factory=list)
    expected_result_patterns: list[str] = field(default_factory=list)
    what_result_would_falsify_the_idea: str = ""
    reviewer_killer_result: str = ""
    risks: list[str] = field(default_factory=list)
    ethical_or_safety_considerations: list[str] = field(default_factory=list)
    novelty_assessment_id: str = ""
    confidence: str = "low"
    expected_failure_modes: list[str] = field(default_factory=list)
    paper_ready: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ReviewerObjection:
    id: str
    experiment_id: str = ""
    severity: str = "major"
    category: str = "clarity"
    objection: str = ""
    why_reviewer_would_care: str = ""
    evidence_or_prior_work: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    blocks_submission: bool = False
    confidence: str = "medium"
    reviewer_role: str = ""
    target_id: str = ""
    mitigation: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ReviewerSimulationSummary:
    experiment_id: str
    submission_readiness_score: int
    blocking_issues: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    optional_fixes: list[str] = field(default_factory=list)
    final_recommendation: str = "not_ready"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class OrchestratorStep:
    id: str
    name: str
    status: str = "pending"
    iteration: int = 0
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestratorPlan:
    run_id: str
    topic: str
    max_papers: int = 50
    max_iterations: int = 1
    sources: list[str] = field(default_factory=list)
    dry_run: bool = False
    steps: list[OrchestratorStep] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class OrchestratorResult:
    run_id: str
    status: str = "pending"
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    message: str = ""


@dataclass(slots=True)
class RunLogEntry:
    timestamp: str
    level: str
    step_id: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RejectedIdea:
    id: str
    idea: str
    reason: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    object_id: str = ""
    severity: str = "error"


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(slots=True)
class ResearchRunState:
    run_id: str
    topic: ResearchTopic
    run_dir: str
    config: dict[str, Any] = field(default_factory=dict)
    papers: list[Paper] = field(default_factory=list)
    paper_notes: list[PaperNote] = field(default_factory=list)
    paper_triage: PaperTriageResult | None = None
    field_map: FieldMap | None = None
    claims: list[Claim] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    cross_domain_analogies: list[CrossDomainAnalogy] = field(default_factory=list)
    novelty_assessments: list[NoveltyAssessment] = field(default_factory=list)
    experiments: list[ExperimentPlan] = field(default_factory=list)
    reviewer_objections: list[ReviewerObjection] = field(default_factory=list)
    reviewer_summaries: list[ReviewerSimulationSummary] = field(default_factory=list)
    orchestrator_plan: OrchestratorPlan | None = None
    orchestrator_result: OrchestratorResult | None = None
    run_log: list[RunLogEntry] = field(default_factory=list)
    rejected_ideas: list[RejectedIdea] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    completed_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchRunState:
        return from_dict(cls, data)
