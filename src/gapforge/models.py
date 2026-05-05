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
    roles: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="source-connector"))


@dataclass(slots=True)
class PaperArtifact:
    id: str
    paper_id: str
    artifact_type: str = "metadata"
    source_url: str = ""
    local_path: str = ""
    sha256: str = ""
    bytes_size: int = 0
    mime_type: str = ""
    created_at: str = ""
    status: str = "available"
    error: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ArtifactClassification:
    path: str
    artifact_type: str
    contains_user_pdf: bool = False
    contains_model_transcript: bool = False
    contains_potential_secret: bool = False
    safe_to_commit: bool = True
    reason: str = ""


@dataclass(slots=True)
class PaperSection:
    id: str
    paper_id: str
    title: str = ""
    normalized_title: str = ""
    section_type: str = "unknown"
    text: str = ""
    page_start: int = 0
    page_end: int = 0
    char_start: int = 0
    char_end: int = 0
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class EvidenceSpan:
    id: str
    paper_id: str
    section_id: str = ""
    quote: str = ""
    page_start: int = 0
    page_end: int = 0
    char_start: int = 0
    char_end: int = 0
    locator: str = ""
    evidence_type: str = "claim"
    confidence: str = "medium"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class SearchQueryRecord:
    id: str
    query: str
    source_names: list[str] = field(default_factory=list)
    purpose: str = "initial_topic"
    max_results: int = 0
    date_from: str = ""
    date_to: str = ""
    executed_at: str = ""
    result_paper_ids: list[str] = field(default_factory=list)
    failure_messages: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class SourceCoverageReport:
    run_id: str
    topic: str
    searched_sources: list[str] = field(default_factory=list)
    query_records: list[SearchQueryRecord] = field(default_factory=list)
    papers_by_source: dict[str, int] = field(default_factory=dict)
    papers_with_pdf: list[str] = field(default_factory=list)
    papers_with_full_text: list[str] = field(default_factory=list)
    papers_abstract_only: list[str] = field(default_factory=list)
    failed_downloads: list[str] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)
    fallback_paper_count: int = 0
    missing_source_types: list[str] = field(default_factory=list)
    coverage_warnings: list[str] = field(default_factory=list)
    confidence: str = "low"


@dataclass(slots=True)
class SourcePolicyProfile:
    id: str
    field_name: str
    required_sources: list[str] = field(default_factory=list)
    recommended_sources: list[str] = field(default_factory=list)
    venue_keywords: list[str] = field(default_factory=list)
    must_include_query_patterns: list[str] = field(default_factory=list)
    recency_window_years: int = 5
    minimum_papers: int = 10
    minimum_full_text_papers: int = 3
    minimum_surveys: int = 1
    minimum_citation_expansion_rounds: int = 1
    novelty_search_requirements: list[str] = field(default_factory=list)
    adjacent_field_requirements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CoverageStoppingAssessment:
    run_id: str
    project_id: str = ""
    profile_id: str = "generic"
    enough_for_mapping: bool = False
    enough_for_gap_mining: bool = False
    enough_for_novelty: bool = False
    enough_for_experiment_design: bool = False
    missing_requirements: list[str] = field(default_factory=list)
    recommended_queries: list[str] = field(default_factory=list)
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="source-policy"))


@dataclass(slots=True)
class ActiveLoopDecision:
    id: str
    run_id: str
    iteration: int
    decision_type: str
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    expected_value: float = 0.0
    cost_estimate: float = 0.0
    status: str = "pending"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="active-loop"))


@dataclass(slots=True)
class ResearchBudget:
    max_papers: int = 50
    max_full_text_papers: int = 12
    max_queries: int = 20
    max_llm_calls: int = 0
    max_cost_usd: float = 0.0
    max_iterations: int = 8
    wall_clock_limit_minutes: int = 30
    stop_when_coverage_sufficient: bool = True
    stop_when_no_new_papers: bool = True


@dataclass(slots=True)
class ActiveLoopState:
    decisions: list[ActiveLoopDecision] = field(default_factory=list)
    budget: ResearchBudget = field(default_factory=ResearchBudget)
    stopping_assessments: list[CoverageStoppingAssessment] = field(default_factory=list)
    current_iteration: int = 0
    status: str = "not_started"


@dataclass(slots=True)
class CitationEdge:
    source_paper_id: str
    target_paper_id: str
    edge_type: str = "related"
    source: str = ""
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class CitationGraph:
    paper_ids: list[str] = field(default_factory=list)
    edges: list[CitationEdge] = field(default_factory=list)
    unresolved_references: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class ReferenceRecord:
    id: str
    paper_id: str
    raw_reference: str
    parsed_title: str = ""
    parsed_authors: list[str] = field(default_factory=list)
    parsed_year: int = 0
    parsed_venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    resolved_paper_id: str = ""
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="fulltext-structure"))


@dataclass(slots=True)
class TableRecord:
    id: str
    paper_id: str
    section_id: str = ""
    caption: str = ""
    text: str = ""
    page_start: int = 0
    page_end: int = 0
    locator: str = ""
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="fulltext-structure"))


@dataclass(slots=True)
class EquationRecord:
    id: str
    paper_id: str
    section_id: str = ""
    text: str = ""
    page: int = 0
    locator: str = ""
    surrounding_text: str = ""
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="fulltext-structure"))


@dataclass(slots=True)
class CaptionRecord:
    id: str
    paper_id: str
    section_id: str = ""
    caption_type: str = "unknown"
    caption: str = ""
    page: int = 0
    locator: str = ""
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="fulltext-structure"))


@dataclass(slots=True)
class OcrAttemptRecord:
    id: str
    paper_id: str
    artifact_id: str = ""
    pages_attempted: list[int] = field(default_factory=list)
    status: str = "skipped"
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="ocr-hook"))


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
    sections_used: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
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
    paper_role: str = "unclear"
    why_this_role: str = ""
    source_coverage_reason: str = ""
    should_download_full_text: bool = False
    important_for_novelty_checking: bool = False
    important_for_cross_domain_transfer: bool = False


@dataclass(slots=True)
class PaperRankingDecision:
    paper_id: str
    title: str
    score: float
    rank: int = 0
    paper_role: str = "unclear"
    role_reasons: list[str] = field(default_factory=list)
    source: str = ""
    source_diversity_reason: str = ""
    role_diversity_reason: str = ""
    relevance_score: float = 0.0
    recency_score: float = 0.0
    citation_score: float = 0.0
    authority_score: float = 0.0
    full_text_score: float = 0.0
    novelty_score: float = 0.0
    adjacent_transfer_score: float = 0.0


@dataclass(slots=True)
class PaperRankingResult:
    topic: str
    decisions: list[PaperRankingDecision]
    query_purpose: str = "initial_topic"
    recency_preference: str = "newest"
    source_diversity_target: int = 2
    role_diversity_target: int = 2
    scoring_summary: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="ranking-v2"))


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
class ClaimNode:
    id: str
    project_id: str
    text: str
    normalized_text: str = ""
    claim_type: str = "background"
    status: str = "unsupported"
    confidence: str = "medium"
    linked_claim_ids: list[str] = field(default_factory=list)
    supporting_evidence_span_ids: list[str] = field(default_factory=list)
    counterevidence_span_ids: list[str] = field(default_factory=list)
    source_paper_ids: list[str] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="claim-graph"))


@dataclass(slots=True)
class ClaimEdge:
    source_claim_id: str
    target_claim_id: str
    relation: str = "supports"
    confidence: str = "low"
    evidence: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="claim-graph"))


@dataclass(slots=True)
class ClaimGraph:
    project_id: str
    nodes: list[ClaimNode] = field(default_factory=list)
    edges: list[ClaimEdge] = field(default_factory=list)
    unresolved_contradictions: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="claim-graph"))


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
class GapEvidenceRow:
    paper_id: str
    claim_or_note_id: str = ""
    evidence_span_id: str = ""
    evidence_type: str = "contextual"
    text: str = ""
    supports_or_counters: str = "supports"
    section_type: str = ""
    locator: str = ""


@dataclass(slots=True)
class GapEvidenceMatrix:
    gap_id: str
    evidence_rows: list[GapEvidenceRow] = field(default_factory=list)
    papers_supporting: list[str] = field(default_factory=list)
    papers_countering: list[str] = field(default_factory=list)
    repeated_limitation_count: int = 0
    missing_metric_count: int = 0
    missing_dataset_count: int = 0
    assumption_pattern_count: int = 0
    confidence: str = "low"
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
    status: str = "query_only"
    transfer_candidate_id: str = ""
    source_paper_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="unknown"))


@dataclass(slots=True)
class CrossDomainTransferCandidate:
    id: str
    target_gap_id: str
    source_field: str
    source_paper_ids: list[str] = field(default_factory=list)
    source_concept: str = ""
    technical_mechanism: str = ""
    why_it_maps: str = ""
    what_breaks: str = ""
    required_adaptation: str = ""
    proposed_experiment: str = ""
    evidence_span_ids: list[str] = field(default_factory=list)
    risk_of_fake_analogy: str = ""
    confidence: str = "low"
    status: str = "query_only"
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
class NoveltyDossier:
    target_id: str
    idea_summary: str
    query_plan: list[str] = field(default_factory=list)
    candidates_considered: list[str] = field(default_factory=list)
    top_prior_work: list[str] = field(default_factory=list)
    comparison_table: list[dict[str, Any]] = field(default_factory=list)
    decisive_difference_needed: str = ""
    missing_searches: list[str] = field(default_factory=list)
    verdict: str = "unknown"
    novelty_strength: str = "unknown"
    confidence: str = "low"
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    reviewer_objection: str = ""
    recommended_action: str = ""
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
class BaselineCandidate:
    paper_id: str
    baseline_name: str
    implementation_available: bool = False
    code_url: str = ""
    why_required: str = ""
    risk_if_missing: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="experiment-protocol"))


@dataclass(slots=True)
class ReproducibilityChecklist:
    random_seeds: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    dataset_versioning: str = ""
    environment_spec: str = ""
    logging_plan: str = ""
    metric_definitions: list[str] = field(default_factory=list)
    preregistered_analysis: str = ""
    negative_controls: list[str] = field(default_factory=list)
    error_analysis_plan: str = ""


@dataclass(slots=True)
class ExperimentProtocol:
    id: str
    direction_id: str
    linked_experiment_plan_id: str
    objective: str
    hypothesis: str
    datasets: list[str] = field(default_factory=list)
    baselines: list[BaselineCandidate] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    statistical_tests: list[str] = field(default_factory=list)
    power_or_sample_size_notes: str = ""
    ablations: list[str] = field(default_factory=list)
    implementation_modules: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    evaluation_script_outline: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    safety_ethics_notes: list[str] = field(default_factory=list)
    reproducibility_checklist: ReproducibilityChecklist = field(default_factory=ReproducibilityChecklist)
    compute_budget: str = ""
    timeline: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="experiment-protocol"))


@dataclass(slots=True)
class ExperimentCodeTask:
    id: str
    campaign_id: str
    direction_id: str
    experiment_protocol_id: str
    task_type: str
    instructions: str
    required_files: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    status: str = "planned"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="experiment-code-task"))


@dataclass(slots=True)
class ExperimentRepoScaffold:
    id: str
    direction_id: str
    path: str
    files: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="experiment-repo-scaffold"))


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
class ReviewerReview:
    reviewer_id: str
    role: str
    score: float = 0.0
    confidence: str = "medium"
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    fatal_flaws: list[str] = field(default_factory=list)
    evidence_or_prior_work: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-panel"))


@dataclass(slots=True)
class RebuttalPlan:
    target_review_id: str
    response_strategy: str = ""
    evidence_needed: list[str] = field(default_factory=list)
    experiments_to_add: list[str] = field(default_factory=list)
    citations_to_add: list[str] = field(default_factory=list)
    claims_to_soften: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-panel"))


@dataclass(slots=True)
class ReviewPanel:
    experiment_or_direction_id: str
    reviewer_reviews: list[ReviewerReview] = field(default_factory=list)
    area_chair_summary: str = ""
    meta_review: str = ""
    decision_risk: str = "unknown"
    rebuttal_plan: list[RebuttalPlan] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-panel"))


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
class HumanReviewRecord:
    id: str
    object_type: str
    object_id: str
    action: str
    note: str = ""
    reviewer: str = "human"
    timestamp: str = ""
    before_snapshot: dict[str, Any] = field(default_factory=dict)
    after_snapshot: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="human-review"))


@dataclass(slots=True)
class ReviewQueueItem:
    id: str
    project_id: str = ""
    run_id: str = ""
    object_type: str = ""
    object_id: str = ""
    priority: str = "medium"
    reason: str = ""
    requested_by_skill: str = "review-queue"
    status: str = "open"
    assigned_to: str = ""
    created_at: str = ""
    completed_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-queue"))


@dataclass(slots=True)
class ReviewQueue:
    project_id: str = ""
    items: list[ReviewQueueItem] = field(default_factory=list)
    summary: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-queue"))


@dataclass(slots=True)
class ResearchProject:
    id: str
    name: str
    description: str = ""
    root_dir: str = ""
    created_at: str = ""
    updated_at: str = ""
    active_topic_ids: list[str] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)
    corpus_id: str = ""
    status: str = "active"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="project-memory"))


@dataclass(slots=True)
class ProjectTopic:
    id: str
    project_id: str
    text: str
    slug: str
    created_at: str = ""
    parent_topic_id: str = ""
    status: str = "active"
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="project-memory"))


@dataclass(slots=True)
class CorpusPaperRecord:
    paper_id: str
    canonical_title: str
    canonical_doi: str = ""
    canonical_arxiv_id: str = ""
    first_seen_run_id: str = ""
    seen_run_ids: list[str] = field(default_factory=list)
    source_paper_ids: list[str] = field(default_factory=list)
    local_artifact_ids: list[str] = field(default_factory=list)
    role_tags: list[str] = field(default_factory=list)
    human_tags: list[str] = field(default_factory=list)
    trust_level: str = "unknown"
    last_updated: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="project-memory"))


@dataclass(slots=True)
class ProjectMemoryRecord:
    id: str
    project_id: str
    record_type: str
    text: str
    linked_run_ids: list[str] = field(default_factory=list)
    linked_object_ids: list[str] = field(default_factory=list)
    linked_paper_ids: list[str] = field(default_factory=list)
    status: str = "active"
    confidence: str = "low"
    created_at: str = ""
    updated_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="project-memory"))


@dataclass(slots=True)
class ResearchDirection:
    id: str
    project_id: str
    title: str
    summary: str = ""
    linked_gap_ids: list[str] = field(default_factory=list)
    linked_hypothesis_ids: list[str] = field(default_factory=list)
    linked_experiment_ids: list[str] = field(default_factory=list)
    linked_novelty_dossier_ids: list[str] = field(default_factory=list)
    supporting_paper_ids: list[str] = field(default_factory=list)
    counterevidence_paper_ids: list[str] = field(default_factory=list)
    maturity: str = "seed"
    readiness_score: float = 0.0
    blocking_issues: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    human_owner: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="project-memory"))


@dataclass(slots=True)
class RelatedWorkEntry:
    direction_id: str
    paper_id: str
    relationship: str
    relevance_score: float = 0.0
    evidence_span_ids: list[str] = field(default_factory=list)
    what_it_contributes: str = ""
    what_it_does_not_solve: str = ""
    must_cite: bool = False
    baseline_candidate: bool = False
    reviewer_risk_if_omitted: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="related-work-matrix"))


@dataclass(slots=True)
class RelatedWorkMatrix:
    direction_id: str
    entries: list[RelatedWorkEntry] = field(default_factory=list)
    coverage_summary: str = ""
    missing_categories: list[str] = field(default_factory=list)
    must_read_paper_ids: list[str] = field(default_factory=list)
    baseline_paper_ids: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="related-work-matrix"))


@dataclass(slots=True)
class ResearchCampaign:
    id: str
    project_id: str
    topic: str
    title: str = ""
    status: str = "planned"
    mode: str = "deterministic"
    agent_name: str = ""
    model: str = ""
    source_profile: str = "generic"
    budget_id: str = "small"
    run_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    decision_ids: list[str] = field(default_factory=list)
    milestone_ids: list[str] = field(default_factory=list)
    review_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign"))


@dataclass(slots=True)
class CampaignStep:
    id: str
    campaign_id: str
    name: str
    step_type: str = "search"
    status: str = "pending"
    run_id: str = ""
    task_spec_id: str = ""
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-step"))


@dataclass(slots=True)
class CampaignDecision:
    id: str
    campaign_id: str
    iteration: int = 0
    decision_type: str = "stop"
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    expected_value: str = ""
    cost_estimate: str = ""
    status: str = "pending"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-decision"))


@dataclass(slots=True)
class CampaignMilestone:
    id: str
    campaign_id: str
    milestone_type: str = "coverage_ready"
    status: str = "pending"
    linked_artifacts: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-milestone"))


@dataclass(slots=True)
class CampaignBudget:
    id: str
    max_iterations: int = 3
    max_papers: int = 50
    max_full_text_papers: int = 10
    max_agent_tasks: int = 5
    max_agent_imports: int = 5
    max_cost_usd: float = 0.0
    max_wall_clock_minutes: int = 60
    stop_when_coverage_sufficient: bool = True
    stop_when_no_new_papers: bool = True
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-budget"))


@dataclass(slots=True)
class CampaignStopCondition:
    id: str
    campaign_id: str
    reason: str = ""
    triggered: bool = False
    evidence: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-stop-condition"))


@dataclass(slots=True)
class CampaignImportRecord:
    id: str
    campaign_id: str
    task_id: str
    input_paths: list[str] = field(default_factory=list)
    status: str = "rejected"
    accepted_objects: list[dict[str, Any]] = field(default_factory=list)
    rejected_objects: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    rollback_snapshot_path: str = ""
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-import"))


@dataclass(slots=True)
class CampaignHumanReview:
    id: str
    campaign_id: str
    reviewer: str = "human"
    reviewed_at: str = ""
    source_coverage_score: int = 0
    full_text_grounding_score: int = 0
    citation_grounding_score: int = 0
    retrieval_quality_score: int = 0
    novelty_honesty_score: int = 0
    gap_quality_score: int = 0
    related_work_quality_score: int = 0
    experiment_quality_score: int = 0
    reviewer_panel_quality_score: int = 0
    uncertainty_visibility_score: int = 0
    stop_reason_quality_score: int = 0
    fake_citation_found: bool = False
    unsupported_high_confidence_claim_found: bool = False
    obvious_prior_work_missed: bool = False
    overclaimed_novelty: bool = False
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-human-review"))


@dataclass(slots=True)
class CampaignAcceptanceSummary:
    campaign_id: str
    accepted: bool = False
    blocking_failures: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    required_artifacts_present: dict[str, bool] = field(default_factory=dict)
    actual_run_attestation_present: bool = False
    accepted_real_agent_outputs: list[str] = field(default_factory=list)
    release_gate_eligible: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-acceptance"))


@dataclass(slots=True)
class AgentSearchRequest:
    id: str
    campaign_id: str
    task_id: str = ""
    query: str = ""
    purpose: str = "coverage"
    source_profile: str = "generic"
    target_sources: list[str] = field(default_factory=list)
    reason: str = ""
    priority: int = 3
    status: str = "proposed"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-search-agent"))


@dataclass(slots=True)
class AgentSearchBatch:
    id: str
    campaign_id: str
    requests: list[AgentSearchRequest] = field(default_factory=list)
    validation_status: str = "pending"
    executed_at: str = ""
    result_paper_ids: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-search-agent"))


@dataclass(slots=True)
class PaperPackage:
    id: str
    direction_id: str
    created_at: str
    files: list[str] = field(default_factory=list)
    readiness: str = ""
    missing_requirements: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="paper-package-export"))


@dataclass(slots=True)
class ResearchProgramState:
    project: ResearchProject
    topics: list[ProjectTopic] = field(default_factory=list)
    corpus_papers: list[CorpusPaperRecord] = field(default_factory=list)
    memory_records: list[ProjectMemoryRecord] = field(default_factory=list)
    research_directions: list[ResearchDirection] = field(default_factory=list)
    campaigns: list[ResearchCampaign] = field(default_factory=list)
    related_work_matrices: list[RelatedWorkMatrix] = field(default_factory=list)
    experiment_protocols: list[ExperimentProtocol] = field(default_factory=list)
    baseline_candidates: list[BaselineCandidate] = field(default_factory=list)
    experiment_code_tasks: list[ExperimentCodeTask] = field(default_factory=list)
    experiment_repo_scaffolds: list[ExperimentRepoScaffold] = field(default_factory=list)
    review_panels: list[ReviewPanel] = field(default_factory=list)
    review_queue: ReviewQueue | None = None
    claim_graph: ClaimGraph | None = None
    run_ids: list[str] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchProgramState:
        return from_dict(cls, data)


@dataclass(slots=True)
class RetrievalDocument:
    id: str
    object_type: str
    object_id: str
    project_id: str = ""
    run_id: str = ""
    paper_id: str = ""
    title: str = ""
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    locator: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="retrieval-index"))


@dataclass(slots=True)
class RetrievalResult:
    document_id: str
    object_type: str
    object_id: str
    paper_id: str = ""
    score: float = 0.0
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    rerank_score: float = 0.0
    text_snippet: str = ""
    locator: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IndexManifest:
    id: str
    project_id: str = ""
    run_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    document_count: int = 0
    index_type: str = "hybrid"
    embedding_model: str = "local-hash"
    path: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="retrieval-index"))


@dataclass(slots=True)
class AgentTaskSpec:
    id: str
    run_id: str
    project_id: str = ""
    skill_name: str = ""
    task_type: str = "deep_reading"
    instructions: str = ""
    input_artifacts: list[str] = field(default_factory=list)
    output_schema_name: str = ""
    required_output_files: list[str] = field(default_factory=list)
    evidence_rules: list[str] = field(default_factory=list)
    uncertainty_rules: list[str] = field(default_factory=list)
    max_runtime_notes: str = ""
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-client"))


@dataclass(slots=True)
class AgentRunRecord:
    id: str
    agent_name: str
    model: str
    task_spec_id: str
    run_id: str = ""
    project_id: str = ""
    status: str = "planned"
    started_at: str = ""
    completed_at: str = ""
    output_paths: list[str] = field(default_factory=list)
    validation_result_id: str = ""
    error: str = ""
    usage_summary: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-client"))


@dataclass(slots=True)
class AgentValidationResult:
    id: str
    task_spec_id: str
    status: str = "warning"
    issues: list[str] = field(default_factory=list)
    accepted_output_paths: list[str] = field(default_factory=list)
    rejected_output_paths: list[str] = field(default_factory=list)
    unsupported_claim_count: int = 0
    invalid_locator_count: int = 0
    invalid_prior_work_count: int = 0
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-validation"))


@dataclass(slots=True)
class AgentRepairRecord:
    id: str
    original_task_id: str
    validation_result_id: str
    repair_task_id: str
    status: str = "created"
    issues_to_fix: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-repair"))


@dataclass(slots=True)
class AgentRuntimeCapability:
    mode: str
    available: bool = False
    reason: str = ""
    required_env: list[str] = field(default_factory=list)
    command_template: str = ""
    can_count_as_actual_run: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-runtime-capability"))


@dataclass(slots=True)
class AgentExecutionMethod:
    method: str
    agent_name: str = "codex"
    model: str = "gpt-5.4"
    counts_as_actual_run: bool = False
    requires_human_attestation: bool = True
    requires_validated_import: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentActualRunAttestation:
    id: str
    task_spec_id: str
    agent_run_record_id: str = ""
    attester: str = "human"
    agent_name: str = "codex"
    model: str = "gpt-5.4"
    execution_method: str = "task_pack"
    statement: str = ""
    created_at: str = ""
    accepted_as_actual_run: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="agent-actual-run-attestation"))


@dataclass(slots=True)
class CanaryRunProfile:
    id: str
    title: str
    topic: str
    project_name: str = ""
    source_profile: str = "generic"
    mode: str = "task_pack"
    required_steps: list[str] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)
    max_papers: int = 20
    max_expanded_papers: int = 10
    requires_network: bool = False
    requires_codex: bool = False
    requires_human_review: bool = False
    expected_artifacts: list[str] = field(default_factory=list)
    pass_criteria: list[str] = field(default_factory=list)
    known_risks: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="canary-profile"))


@dataclass(slots=True)
class CanaryRunRecord:
    id: str
    profile_id: str
    run_id: str = ""
    project_id: str = ""
    status: str = "planned"
    command_log: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    validation_summary: dict[str, Any] = field(default_factory=dict)
    human_review_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="canary-runner"))


@dataclass(slots=True)
class CampaignCanaryProfile:
    id: str
    title: str
    topic: str
    source_profile: str = "generic"
    campaign_mode: str = "deterministic"
    agent_name: str = "codex"
    model: str = "gpt-5.4"
    budget: str = "small"
    requires_codex: bool = False
    requires_network: bool = False
    requires_local_pdf: bool = False
    required_milestones: list[str] = field(default_factory=list)
    expected_stop_reason: str = ""
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    known_risks: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-canary-profile"))


@dataclass(slots=True)
class CampaignCanaryRecord:
    id: str
    profile_id: str
    campaign_id: str = ""
    project_id: str = ""
    status: str = "planned"
    milestones_reached: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    actual_run_status: str = "not_applicable"
    human_review_status: str = "not_required"
    accepted: bool = False
    failure_reason: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="campaign-canary-runner"))


@dataclass(slots=True)
class CanaryHumanReview:
    id: str
    canary_run_id: str
    reviewer: str = "human"
    reviewed_at: str = ""
    source_coverage_score: int = 0
    full_text_grounding_score: int = 0
    citation_grounding_score: int = 0
    novelty_honesty_score: int = 0
    gap_quality_score: int = 0
    experiment_quality_score: int = 0
    uncertainty_visibility_score: int = 0
    fake_citation_found: bool = False
    unsupported_high_confidence_claim_found: bool = False
    obvious_prior_work_missed: bool = False
    strict_report_behaved_correctly: bool = False
    accepted: bool = False
    reasons: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="canary-human-review"))


@dataclass(slots=True)
class CanaryAcceptanceSummary:
    canary_run_id: str
    passed: bool = False
    blocking_failures: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    accepted_artifacts: list[str] = field(default_factory=list)
    rejected_artifacts: list[str] = field(default_factory=list)
    release_gate_status: str = "not_passed"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="canary-acceptance"))


@dataclass(slots=True)
class AgentEnvironmentStatus:
    real_runs_enabled: bool = False
    agent_mode: str = "off"
    agent_name: str = "codex"
    codex_model: str = "gpt-5.4"
    provider_mode: str = "off"
    required_env_present: bool = False
    missing_env: list[str] = field(default_factory=list)
    safe_to_execute_real_agent: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentPathStatus:
    direct_execution_available: bool = False
    task_pack_available: bool = False
    manual_import_available: bool = False
    fake_agent_available: bool = True
    provider_llm_available: bool = False
    failure_reason: str = ""
    recommended_path: str = ""


@dataclass(slots=True)
class RealRunDiagnostic:
    id: str
    version: str
    created_at: str
    environment_status: AgentEnvironmentStatus
    agent_runtime_status: AgentPathStatus
    codex_execution_status: str = "unavailable"
    task_pack_status: str = "unknown"
    import_validator_status: str = "unknown"
    canary_status: str = "unknown"
    blocking_issues: list[str] = field(default_factory=list)
    recommended_fixes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="real-run-diagnostics"))


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
    paper_artifacts: list[PaperArtifact] = field(default_factory=list)
    paper_sections: list[PaperSection] = field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    search_queries: list[SearchQueryRecord] = field(default_factory=list)
    source_coverage: SourceCoverageReport | None = None
    coverage_stopping_assessment: CoverageStoppingAssessment | None = None
    citation_graph: CitationGraph | None = None
    references: list[ReferenceRecord] = field(default_factory=list)
    tables: list[TableRecord] = field(default_factory=list)
    equations: list[EquationRecord] = field(default_factory=list)
    captions: list[CaptionRecord] = field(default_factory=list)
    ocr_attempts: list[OcrAttemptRecord] = field(default_factory=list)
    paper_notes: list[PaperNote] = field(default_factory=list)
    paper_ranking: PaperRankingResult | None = None
    paper_triage: PaperTriageResult | None = None
    field_map: FieldMap | None = None
    claims: list[Claim] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    gap_evidence_matrices: list[GapEvidenceMatrix] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    cross_domain_analogies: list[CrossDomainAnalogy] = field(default_factory=list)
    cross_domain_transfers: list[CrossDomainTransferCandidate] = field(default_factory=list)
    novelty_assessments: list[NoveltyAssessment] = field(default_factory=list)
    novelty_dossiers: list[NoveltyDossier] = field(default_factory=list)
    related_work_matrices: list[RelatedWorkMatrix] = field(default_factory=list)
    experiments: list[ExperimentPlan] = field(default_factory=list)
    experiment_protocols: list[ExperimentProtocol] = field(default_factory=list)
    baseline_candidates: list[BaselineCandidate] = field(default_factory=list)
    reviewer_objections: list[ReviewerObjection] = field(default_factory=list)
    reviewer_summaries: list[ReviewerSimulationSummary] = field(default_factory=list)
    orchestrator_plan: OrchestratorPlan | None = None
    orchestrator_result: OrchestratorResult | None = None
    active_loop: ActiveLoopState | None = None
    run_log: list[RunLogEntry] = field(default_factory=list)
    rejected_ideas: list[RejectedIdea] = field(default_factory=list)
    human_reviews: list[HumanReviewRecord] = field(default_factory=list)
    review_queue: ReviewQueue | None = None
    agent_task_specs: list[AgentTaskSpec] = field(default_factory=list)
    agent_run_records: list[AgentRunRecord] = field(default_factory=list)
    agent_validation_results: list[AgentValidationResult] = field(default_factory=list)
    agent_repair_records: list[AgentRepairRecord] = field(default_factory=list)
    agent_actual_run_attestations: list[AgentActualRunAttestation] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    completed_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchRunState:
        return from_dict(cls, data)
