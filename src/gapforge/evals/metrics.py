"""Metrics for evaluator harnesses."""

from __future__ import annotations

import re
from dataclasses import dataclass

from gapforge.models import (
    Claim,
    ExperimentPlan,
    ExperimentProtocol,
    Gap,
    GapEvidenceMatrix,
    NoveltyAssessment,
    NoveltyDossier,
    RelatedWorkMatrix,
    ResearchRunState,
    ReviewerObjection,
)


@dataclass(slots=True)
class RunMetrics:
    paper_count: int
    claim_count: int
    gap_count: int
    experiment_count: int

    @classmethod
    def from_state(cls, state: ResearchRunState) -> RunMetrics:
        return cls(
            paper_count=len(state.papers),
            claim_count=len(state.claims),
            gap_count=len(state.gaps),
            experiment_count=len(state.experiments),
        )


@dataclass(slots=True)
class EvalScores:
    gap_specificity_score: float
    evidence_linkage_score: float
    novelty_gate_accuracy: float
    duplicate_detection_rate: float
    unsupported_claim_rate: float
    experiment_completeness_score: float
    reviewer_objection_quality_score: float
    full_text_coverage_score: float | None = None
    evidence_span_precision_proxy: float | None = None
    section_grounding_score: float | None = None
    gap_evidence_matrix_score: float | None = None
    novelty_dossier_completeness_score: float | None = None
    source_coverage_transparency_score: float | None = None
    human_review_respect_score: float | None = None
    report_uncertainty_score: float | None = None
    retrieval_relevance_at_k: float | None = None
    prior_work_recall_proxy: float | None = None
    related_work_matrix_quality: float | None = None
    direction_maturity_accuracy: float | None = None
    protocol_completeness: float | None = None
    manuscript_package_honesty: float | None = None
    contradiction_detection_score: float | None = None
    source_policy_compliance: float | None = None
    llm_output_grounding_score: float | None = None
    campaign_decision_quality: float | None = None
    stop_reason_correctness: float | None = None
    agent_output_validation_strictness: float | None = None
    actual_run_gate_correctness: float | None = None
    novelty_research_loop_quality: float | None = None
    direction_maturity_gate_accuracy: float | None = None
    campaign_report_honesty: float | None = None
    review_queue_quality: float | None = None
    experiment_code_task_quality: float | None = None
    rollback_safety: float | None = None
    live_source_coverage_score: float | None = None
    search_strategy_completeness: float | None = None
    prior_work_recall_gate_score: float | None = None
    canonicalization_quality: float | None = None
    real_literature_refusal_quality: float | None = None
    research_direction_quality_proxy: float | None = None
    quality_review_gate_correctness: float | None = None
    v5_release_gate_correctness: float | None = None
    experiment_execution_integrity: float | None = None
    result_artifact_grounding: float | None = None
    empirical_claim_validity: float | None = None
    statistical_caution_score: float | None = None
    reproducibility_score: float | None = None
    empirical_review_quality: float | None = None
    fake_result_rejection: float | None = None
    paper_package_honesty: float | None = None
    v6_release_gate_correctness: float | None = None
    benchmark_execution_integrity: float | None = None
    benchmark_failure_path_preservation: float | None = None
    result_aggregation_quality: float | None = None
    error_analysis_quality: float | None = None
    benchmark_comparison_honesty: float | None = None
    replication_package_quality: float | None = None
    reproduction_verification_quality: float | None = None
    low_fpr_underpowered_warning_score: float | None = None
    v7_release_gate_correctness: float | None = None
    manuscript_traceability_score: float | None = None
    citation_validity_score: float | None = None
    result_claim_honesty_score: float | None = None
    venue_checklist_score: float | None = None
    artifact_eval_package_score: float | None = None
    reviewer_panel_quality: float | None = None
    rebuttal_actionability: float | None = None
    anonymization_safety: float | None = None
    submission_package_completeness: float | None = None
    v8_release_gate_correctness: float | None = None
    pilot_outcome_classification: float | None = None
    idea_gate_quality: float | None = None
    external_review_completeness: float | None = None
    v1_readiness_gate_correctness: float | None = None
    migration_audit_score: float | None = None
    cli_audit_score: float | None = None
    docs_audit_score: float | None = None
    artifact_hygiene_score: float | None = None
    v9_release_gate_correctness: float | None = None
    topic_portfolio_diversity: float | None = None
    idea_candidate_specificity: float | None = None
    mutation_quality: float | None = None
    constructive_gap_quality: float | None = None
    cross_domain_transfer_quality: float | None = None
    novelty_loop_quality: float | None = None
    tournament_selection_quality: float | None = None
    human_feedback_integration: float | None = None
    research_agenda_quality: float | None = None
    idea_yield_gate_correctness: float | None = None
    benchmark_spec_completeness: float | None = None
    threat_model_quality: float | None = None
    trace_generator_validity: float | None = None
    baseline_suite_completeness: float | None = None
    sequential_metric_correctness: float | None = None
    underpowered_claim_rejection: float | None = None
    reviewer_blocker_quality: float | None = None
    selected_benchmark_release_gate_correctness: float | None = None
    pilot_power_plan_quality: float | None = None
    honest_null_distribution_quality: float | None = None
    collusive_distribution_quality: float | None = None
    baseline_calibration_quality: float | None = None
    pilot_metric_correctness: float | None = None
    low_fpr_overclaim_rejection: float | None = None
    related_work_attachment_quality: float | None = None
    pilot_reviewer_quality: float | None = None
    v22_release_gate_correctness: float | None = None
    main_power_decision_quality: float | None = None
    related_work_completion_quality: float | None = None
    baseline_strength_quality: float | None = None
    main_result_analysis_quality: float | None = None
    go_no_go_decision_quality: float | None = None
    publication_review_quality: float | None = None
    manuscript_maturity_honesty: float | None = None
    v23_release_gate_correctness: float | None = None
    related_work_search_quality: float | None = None
    category_curation_quality: float | None = None
    prior_work_dossier_quality: float | None = None
    positioning_safety: float | None = None
    selected_related_work_matrix_quality: float | None = None
    publication_review_correctness: float | None = None
    manuscript_revision_honesty: float | None = None
    v24_release_gate_correctness: float | None = None
    vetted_benchmark_fit_quality: float | None = None
    adapter_transparency_score: float | None = None
    venue_style_safety_score: float | None = None
    citation_plagiarism_safety: float | None = None
    review_dataset_integrity: float | None = None
    review_taxonomy_quality: float | None = None
    reviewer_calibration_score: float | None = None
    drastic_review_quality: float | None = None
    revision_plan_actionability: float | None = None
    v25_release_gate_correctness: float | None = None

    def overall(self) -> float:
        positive = [
            self.gap_specificity_score,
            self.evidence_linkage_score,
            self.novelty_gate_accuracy,
            self.duplicate_detection_rate,
            self.experiment_completeness_score,
            self.reviewer_objection_quality_score,
        ]
        return round((sum(positive) + (1.0 - self.unsupported_claim_rate)) / 7, 3)

    def v2_overall(self) -> float | None:
        values = [
            self.full_text_coverage_score,
            self.evidence_span_precision_proxy,
            self.section_grounding_score,
            self.gap_evidence_matrix_score,
            self.novelty_dossier_completeness_score,
            self.source_coverage_transparency_score,
            self.human_review_respect_score,
            self.report_uncertainty_score,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v3_overall(self) -> float | None:
        values = [
            self.retrieval_relevance_at_k,
            self.prior_work_recall_proxy,
            self.related_work_matrix_quality,
            self.direction_maturity_accuracy,
            self.protocol_completeness,
            self.manuscript_package_honesty,
            self.contradiction_detection_score,
            self.source_policy_compliance,
            self.llm_output_grounding_score,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v4_overall(self) -> float | None:
        values = [
            self.campaign_decision_quality,
            self.stop_reason_correctness,
            self.agent_output_validation_strictness,
            self.actual_run_gate_correctness,
            self.novelty_research_loop_quality,
            self.direction_maturity_gate_accuracy,
            self.campaign_report_honesty,
            self.review_queue_quality,
            self.experiment_code_task_quality,
            self.rollback_safety,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v5_overall(self) -> float | None:
        values = [
            self.live_source_coverage_score,
            self.search_strategy_completeness,
            self.prior_work_recall_gate_score,
            self.canonicalization_quality,
            self.real_literature_refusal_quality,
            self.research_direction_quality_proxy,
            self.quality_review_gate_correctness,
            self.v5_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v6_overall(self) -> float | None:
        values = [
            self.experiment_execution_integrity,
            self.result_artifact_grounding,
            self.empirical_claim_validity,
            self.statistical_caution_score,
            self.reproducibility_score,
            self.empirical_review_quality,
            self.fake_result_rejection,
            self.paper_package_honesty,
            self.v6_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v7_overall(self) -> float | None:
        values = [
            self.benchmark_execution_integrity,
            self.benchmark_failure_path_preservation,
            self.result_aggregation_quality,
            self.error_analysis_quality,
            self.benchmark_comparison_honesty,
            self.replication_package_quality,
            self.reproduction_verification_quality,
            self.low_fpr_underpowered_warning_score,
            self.v7_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v8_overall(self) -> float | None:
        values = [
            self.manuscript_traceability_score,
            self.citation_validity_score,
            self.result_claim_honesty_score,
            self.venue_checklist_score,
            self.artifact_eval_package_score,
            self.reviewer_panel_quality,
            self.rebuttal_actionability,
            self.anonymization_safety,
            self.submission_package_completeness,
            self.v8_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v9_overall(self) -> float | None:
        values = [
            self.pilot_outcome_classification,
            self.idea_gate_quality,
            self.external_review_completeness,
            self.v1_readiness_gate_correctness,
            self.migration_audit_score,
            self.cli_audit_score,
            self.docs_audit_score,
            self.artifact_hygiene_score,
            self.v9_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v2_ideas_overall(self) -> float | None:
        values = [
            self.topic_portfolio_diversity,
            self.idea_candidate_specificity,
            self.mutation_quality,
            self.constructive_gap_quality,
            self.cross_domain_transfer_quality,
            self.novelty_loop_quality,
            self.tournament_selection_quality,
            self.human_feedback_integration,
            self.research_agenda_quality,
            self.idea_yield_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v21_overall(self) -> float | None:
        values = [
            self.benchmark_spec_completeness,
            self.threat_model_quality,
            self.trace_generator_validity,
            self.baseline_suite_completeness,
            self.sequential_metric_correctness,
            self.underpowered_claim_rejection,
            self.reviewer_blocker_quality,
            self.selected_benchmark_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v22_overall(self) -> float | None:
        values = [
            self.pilot_power_plan_quality,
            self.honest_null_distribution_quality,
            self.collusive_distribution_quality,
            self.baseline_calibration_quality,
            self.pilot_metric_correctness,
            self.low_fpr_overclaim_rejection,
            self.related_work_attachment_quality,
            self.pilot_reviewer_quality,
            self.v22_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v23_overall(self) -> float | None:
        values = [
            self.main_power_decision_quality,
            self.related_work_completion_quality,
            self.baseline_strength_quality,
            self.main_result_analysis_quality,
            self.go_no_go_decision_quality,
            self.publication_review_quality,
            self.manuscript_maturity_honesty,
            self.v23_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v24_overall(self) -> float | None:
        values = [
            self.related_work_search_quality,
            self.category_curation_quality,
            self.prior_work_dossier_quality,
            self.positioning_safety,
            self.selected_related_work_matrix_quality,
            self.publication_review_correctness,
            self.manuscript_revision_honesty,
            self.v24_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)

    def v25_overall(self) -> float | None:
        values = [
            self.vetted_benchmark_fit_quality,
            self.adapter_transparency_score,
            self.venue_style_safety_score,
            self.citation_plagiarism_safety,
            self.review_dataset_integrity,
            self.review_taxonomy_quality,
            self.reviewer_calibration_score,
            self.drastic_review_quality,
            self.revision_plan_actionability,
            self.v25_release_gate_correctness,
        ]
        present = [value for value in values if value is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 3)


def gap_specificity_score(gaps: list[Gap]) -> float:
    if not gaps:
        return 0.0
    generic_terms = {"better", "improve", "ai", "modern", "novel", "use"}
    scores = []
    for gap in gaps:
        text = f"{gap.title} {gap.description} {gap.why_existing_work_does_not_solve_it} {gap.minimum_experiment_needed}"
        tokens = _tokens(text)
        has_mechanism = any(
            term in text.lower()
            for term in ["false-positive", "fixed", "benchmark", "sensor", "transaction", "lexical", "calibration", "outage"]
        )
        generic_penalty = sum(1 for token in tokens if token in generic_terms) / max(1, len(tokens))
        length_score = min(len(tokens) / 28, 1.0)
        scores.append(max(0.0, min(1.0, (0.55 * length_score) + (0.45 if has_mechanism else 0.0) - generic_penalty)))
    return round(sum(scores) / len(scores), 3)


def evidence_linkage_score(gaps: list[Gap]) -> float:
    if not gaps:
        return 0.0
    linked = [
        bool(gap.supporting_paper_ids or gap.supporting_claim_ids or gap.linked_paper_ids or gap.explicit_reason)
        and bool(gap.risk_that_gap_is_fake)
        for gap in gaps
    ]
    return round(sum(1 for item in linked if item) / len(gaps), 3)


def novelty_gate_accuracy(
    assessments: list[NoveltyAssessment],
    expected_duplicates: list[dict[str, object]],
    dossiers: list[NoveltyDossier] | None = None,
) -> float:
    if not expected_duplicates:
        return 1.0
    correct = 0
    dossier_by_target = {dossier.target_id: dossier for dossier in dossiers or []}
    for duplicate in expected_duplicates:
        expected = str(duplicate.get("expected_verdict", "reject"))
        duplicate_text = f"{duplicate.get('id', '')} {duplicate.get('title', '')} {duplicate.get('description', '')}".lower()
        matched = [
            assessment
            for assessment in assessments
            if _overlap(duplicate_text, assessment.idea_summary.lower()) >= 0.25
            or str(duplicate.get("id", "")) == assessment.target_gap_or_hypothesis_id
        ]
        matched_dossiers = [
            dossier
            for target_id, dossier in dossier_by_target.items()
            if str(duplicate.get("id", "")) == target_id or _overlap(duplicate_text, dossier.idea_summary.lower()) >= 0.25
        ]
        assessment_correct = any(assessment.verdict == expected for assessment in matched)
        dossier_correct = any(dossier.verdict == expected for dossier in matched_dossiers)
        if assessment_correct or dossier_correct:
            correct += 1
    return round(correct / len(expected_duplicates), 3)


def duplicate_detection_rate(assessments: list[NoveltyAssessment]) -> float:
    duplicate_like = [
        assessment for assessment in assessments if assessment.similarity_to_prior_work >= 0.7 or assessment.verdict == "reject"
    ]
    if not duplicate_like:
        return 0.0
    return round(sum(1 for item in duplicate_like if item.verdict == "reject") / len(duplicate_like), 3)


def unsupported_claim_rate(claims: list[Claim], state: ResearchRunState | None = None) -> float:
    if not claims:
        return 0.0
    full_text_paper_ids = {section.paper_id for section in state.paper_sections if section.text.strip()} if state is not None else set()
    span_paper_ids = {span.paper_id for span in state.evidence_spans} if state is not None else set()
    unsupported = [
        claim
        for claim in claims
        if claim.status == "supported"
        and (not claim.supporting_evidence or not claim.source_paper_ids)
        or claim.type == "novelty"
        and not claim.closest_prior_work
        or claim.status == "unsupported"
        or (
            claim.status == "supported"
            and claim.confidence == "high"
            and bool(set(claim.source_paper_ids) & full_text_paper_ids)
            and not bool(set(claim.source_paper_ids) & span_paper_ids)
        )
    ]
    return round(len(unsupported) / len(claims), 3)


def experiment_completeness_score(experiments: list[ExperimentPlan], dossiers: list[NoveltyDossier] | None = None) -> float:
    if not experiments:
        return 0.0
    dossier_targets = {dossier.target_id for dossier in dossiers or []}
    required = [
        "linked_gap_ids",
        "hypothesis",
        "minimum_viable_experiment",
        "baselines",
        "metrics",
        "statistical_tests",
        "ablations",
        "what_result_would_falsify_the_idea",
        "reviewer_killer_result",
        "risks",
    ]
    scores = []
    for experiment in experiments:
        present = 0
        for field_name in required:
            value = getattr(experiment, field_name)
            present += bool(value)
        novelty_linked = bool(set(experiment.linked_gap_ids) & dossier_targets) or experiment.novelty_assessment_id in dossier_targets
        explicit_unknown = experiment.novelty_assessment_id in {"", "unknown"} and any(
            "novelty" in risk.lower() for risk in experiment.risks
        )
        scores.append((present + int(novelty_linked or explicit_unknown)) / (len(required) + 1))
    return round(sum(scores) / len(scores), 3)


def reviewer_objection_quality_score(objections: list[ReviewerObjection]) -> float:
    if not objections:
        return 0.0
    categories = {item.category for item in objections}
    serious = sum(1 for item in objections if item.severity in {"major", "fatal"})
    concrete = sum(1 for item in objections if item.why_reviewer_would_care and item.suggested_fix)
    return round(min(1.0, (0.4 * len(categories) / 6) + (0.3 * serious / len(objections)) + (0.3 * concrete / len(objections))), 3)


def full_text_coverage_score(state: ResearchRunState) -> float:
    if not state.papers:
        return 0.0
    full_text_ids = {section.paper_id for section in state.paper_sections if section.text.strip()}
    return round(len(full_text_ids) / len(state.papers), 3)


def evidence_span_precision_proxy(state: ResearchRunState) -> float:
    if not state.evidence_spans:
        return 0.0
    sections_by_id = {section.id: section for section in state.paper_sections}
    valid = 0
    for span in state.evidence_spans:
        section = sections_by_id.get(span.section_id)
        quote = " ".join(span.quote.lower().split())
        section_text = " ".join(section.text.lower().split()) if section is not None else ""
        if span.paper_id and quote and (not section or quote[:80] in section_text or _overlap(quote, section_text) >= 0.35):
            valid += 1
    return round(valid / len(state.evidence_spans), 3)


def section_grounding_score(state: ResearchRunState) -> float:
    if not state.paper_notes:
        return 0.0
    known_sections = {section.id for section in state.paper_sections}
    span_paper_ids = {span.paper_id for span in state.evidence_spans}
    scores = []
    for note in state.paper_notes:
        if note.source_basis == "full text":
            has_known_section = bool(set(note.sections_used) & known_sections)
            results_grounded = (
                not note.main_results or note.paper_id in span_paper_ids or bool(note.quotes_or_evidence_snippets or note.evidence)
            )
            scores.append((int(has_known_section) + int(results_grounded)) / 2)
        else:
            scores.append(0.5 if note.confidence in {"low", "medium"} else 0.0)
    return round(sum(scores) / len(scores), 3)


def gap_evidence_matrix_score(gaps: list[Gap], matrices: list[GapEvidenceMatrix]) -> float:
    if not gaps:
        return 0.0
    by_gap = {matrix.gap_id: matrix for matrix in matrices}
    scores = []
    for gap in gaps:
        matrix = by_gap.get(gap.id)
        if matrix is None:
            scores.append(0.0 if not gap.explicit_reason else 0.4)
            continue
        linked = bool(matrix.evidence_rows or matrix.papers_supporting or matrix.papers_countering)
        counters_represented = bool(matrix.papers_countering) or gap.confidence != "high"
        confidence_ok = gap.confidence != "high" or len(matrix.papers_supporting) >= 2
        scores.append((int(linked) + int(counters_represented) + int(confidence_ok)) / 3)
    return round(sum(scores) / len(scores), 3)


def novelty_dossier_completeness_score(dossiers: list[NoveltyDossier], expected_duplicates: list[dict[str, object]]) -> float:
    if not dossiers:
        return 0.0
    duplicate_ids = {str(item.get("id", "")) for item in expected_duplicates}
    scores = []
    for dossier in dossiers:
        required = [
            bool(dossier.query_plan),
            bool(dossier.candidates_considered),
            bool(dossier.top_prior_work),
            bool(dossier.comparison_table),
            bool(dossier.decisive_difference_needed),
            bool(dossier.recommended_action),
            dossier.verdict in {"reject", "revise", "pursue", "unknown"},
        ]
        if dossier.target_id in duplicate_ids:
            required.append(dossier.verdict == "reject")
        scores.append(sum(1 for item in required if item) / len(required))
    return round(sum(scores) / len(scores), 3)


def source_coverage_transparency_score(state: ResearchRunState) -> float:
    coverage = state.source_coverage
    if coverage is None:
        return 0.0
    checks = [
        bool(coverage.searched_sources),
        bool(coverage.query_records),
        bool(coverage.papers_by_source),
        coverage.papers_with_full_text is not None,
        coverage.papers_abstract_only is not None,
        coverage.confidence in {"low", "medium", "high"},
        bool(coverage.coverage_warnings) or coverage.confidence == "high",
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def human_review_respect_score(state: ResearchRunState) -> float:
    rejected_gap_ids = {record.object_id for record in state.human_reviews if record.object_type == "gap" and record.action == "reject"}
    locked_ids = {record.object_id for record in state.human_reviews if record.action == "lock"}
    if not rejected_gap_ids and not locked_ids:
        return 1.0
    experiments_for_rejected = [experiment.id for experiment in state.experiments if rejected_gap_ids & set(experiment.linked_gap_ids)]
    locked_objects_present = all(
        any(getattr(item, "id", "") == object_id for item in state.gaps + state.experiments + state.claims) for object_id in locked_ids
    )
    checks = [not experiments_for_rejected, locked_objects_present]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def report_uncertainty_score(state: ResearchRunState) -> float:
    uncertainty_signals = 0
    uncertainty_signals += sum(
        1 for claim in state.claims if claim.status in {"unsupported", "uncertain", "contested"} or claim.needs_verification
    )
    uncertainty_signals += sum(1 for gap in state.gaps if gap.risk_that_gap_is_fake)
    uncertainty_signals += sum(1 for dossier in state.novelty_dossiers if dossier.missing_searches or dossier.confidence == "low")
    uncertainty_signals += sum(1 for note in state.paper_notes if note.source_basis != "full text")
    denominator = max(1, len(state.claims) + len(state.gaps) + len(state.novelty_dossiers) + len(state.paper_notes))
    return round(min(1.0, uncertainty_signals / denominator), 3)


def retrieval_relevance_at_k(retrieved_paper_ids: list[str], relevant_paper_ids: list[str], *, k: int = 5) -> float:
    if not relevant_paper_ids:
        return 1.0
    retrieved = set(retrieved_paper_ids[:k])
    relevant = set(relevant_paper_ids)
    return round(len(retrieved & relevant) / min(len(relevant), k), 3)


def prior_work_recall_proxy(dossiers: list[NoveltyDossier], human_gold_prior_work: list[dict[str, object]]) -> float:
    expected = {str(item.get("paper_id", "")) for item in human_gold_prior_work if item.get("paper_id")}
    if not expected:
        return 1.0
    found = {paper_id for dossier in dossiers for paper_id in [*dossier.top_prior_work, *dossier.candidates_considered]}
    found.update(str(row.get("paper_id", "")) for dossier in dossiers for row in dossier.comparison_table)
    return round(len(expected & found) / len(expected), 3)


def related_work_matrix_quality(matrices: list[RelatedWorkMatrix], gold_matrices: list[RelatedWorkMatrix]) -> float:
    gold_entries = {(entry.paper_id, entry.relationship) for matrix in gold_matrices for entry in matrix.entries}
    if not gold_entries:
        return 1.0
    actual_entries = {(entry.paper_id, entry.relationship) for matrix in matrices for entry in matrix.entries}
    must_cite_gold = {entry.paper_id for matrix in gold_matrices for entry in matrix.entries if entry.must_cite}
    must_cite_actual = {entry.paper_id for matrix in matrices for entry in matrix.entries if entry.must_cite}
    baseline_gold = {entry.paper_id for matrix in gold_matrices for entry in matrix.entries if entry.baseline_candidate}
    baseline_actual = {entry.paper_id for matrix in matrices for entry in matrix.entries if entry.baseline_candidate}
    relation_score = len(gold_entries & actual_entries) / len(gold_entries)
    cite_score = len(must_cite_gold & must_cite_actual) / max(1, len(must_cite_gold))
    baseline_score = len(baseline_gold & baseline_actual) / max(1, len(baseline_gold))
    return round((0.5 * relation_score) + (0.25 * cite_score) + (0.25 * baseline_score), 3)


def direction_maturity_accuracy(actual_maturity: str, expected_not_ready_reasons: list[str]) -> float:
    should_be_ready = not expected_not_ready_reasons
    if should_be_ready:
        return 1.0 if actual_maturity in {"experiment_ready", "manuscript_ready"} else 0.4
    if actual_maturity in {"seed", "candidate", "validated_gap"}:
        return 1.0
    if actual_maturity == "experiment_ready":
        return 0.5
    return 0.3


def protocol_completeness(protocols: list[ExperimentProtocol]) -> float:
    if not protocols:
        return 0.0
    required = [
        "objective",
        "hypothesis",
        "datasets",
        "baselines",
        "metrics",
        "statistical_tests",
        "power_or_sample_size_notes",
        "ablations",
        "implementation_modules",
        "expected_artifacts",
        "evaluation_script_outline",
        "failure_modes",
        "reproducibility_checklist",
        "compute_budget",
        "timeline",
    ]
    scores = []
    for protocol in protocols:
        present = 0
        for field_name in required:
            value = getattr(protocol, field_name)
            present += bool(value)
        checklist = protocol.reproducibility_checklist
        checklist_score = (
            sum(
                bool(value)
                for value in [
                    checklist.random_seeds,
                    checklist.dataset_versioning,
                    checklist.environment_spec,
                    checklist.logging_plan,
                    checklist.metric_definitions,
                    checklist.negative_controls,
                    checklist.error_analysis_plan,
                ]
            )
            / 7
        )
        scores.append(((present / len(required)) * 0.75) + (checklist_score * 0.25))
    return round(sum(scores) / len(scores), 3)


def manuscript_package_honesty(markdown_texts: list[str]) -> float:
    if not markdown_texts:
        return 0.0
    text = "\n".join(markdown_texts).lower()
    fake_result_phrases = ["we found", "our results show", "we demonstrate", "significantly outperforms"]
    bad = sum(1 for phrase in fake_result_phrases if phrase in text)
    honesty_signals = sum(1 for phrase in ["hypothetical", "not run", "expected", "missing", "uncertain"] if phrase in text)
    return round(max(0.0, min(1.0, (honesty_signals / 5) - (bad * 0.25) + 0.4)), 3)


def contradiction_detection_score(unresolved_contradictions: list[str], expected_contradictions: list[str] | None = None) -> float:
    expected = expected_contradictions or []
    if not expected:
        return 1.0 if not unresolved_contradictions else 0.7
    matched = sum(1 for item in expected if any(_overlap(item.lower(), actual.lower()) >= 0.35 for actual in unresolved_contradictions))
    return round(matched / len(expected), 3)


def source_policy_compliance(state: ResearchRunState, required_sources: list[str] | None = None) -> float:
    coverage = state.source_coverage
    if coverage is None:
        return 0.0
    required = set(required_sources or [])
    searched = set(coverage.searched_sources)
    required_score = len(required & searched) / len(required) if required else 1.0
    full_text_score = 1.0 if coverage.papers_with_full_text else 0.0
    warning_score = 1.0 if coverage.confidence in {"medium", "high"} or coverage.coverage_warnings else 0.0
    return round((0.5 * required_score) + (0.25 * full_text_score) + (0.25 * warning_score), 3)


def llm_output_grounding_score(outputs: list[dict[str, object]], known_locators: list[str]) -> float:
    if not outputs:
        return 1.0
    known = set(known_locators)
    grounded = 0
    total = 0
    for output in outputs:
        locators = output.get("evidence_locators", [])
        if isinstance(locators, list):
            total += 1
            grounded += bool(locators) and all(str(locator) in known for locator in locators)
    if total == 0:
        return 0.0
    return round(grounded / total, 3)


def campaign_decision_quality(fixture: dict[str, object]) -> float:
    decisions = _dicts(fixture.get("decisions"))
    expected = [str(item) for item in _list(fixture.get("expected_decisions"))]
    if not expected:
        return 1.0 if decisions else 0.0
    actual = [str(item.get("decision_type", "")) for item in decisions]
    coverage = len(set(expected) & set(actual)) / len(set(expected))
    grounded = [
        bool(str(item.get("reason", "")).strip())
        and bool(_list(item.get("evidence")))
        and item.get("status") in {"complete", "pending", "blocked"}
        for item in decisions
        if str(item.get("decision_type", "")) in expected
    ]
    grounding = sum(1 for item in grounded if item) / len(grounded) if grounded else 0.0
    return round((0.65 * coverage) + (0.35 * grounding), 3)


def stop_reason_correctness(fixture: dict[str, object]) -> float:
    stop = _dict(fixture.get("stop_reason"))
    actual = str(stop.get("actual", ""))
    expected = str(stop.get("expected", ""))
    if not expected:
        return 0.0
    reason_match = actual == expected
    not_ready = actual.startswith("not_ready") or actual in {"rejected_duplicate_prior_work", "human_review_required"}
    recommendation_ok = not (not_ready and bool(stop.get("recommended_direction")))
    explicit = bool(str(stop.get("explanation", "")).strip()) or bool(_list(stop.get("evidence")))
    return round((0.5 * int(reason_match)) + (0.3 * int(recommendation_ok)) + (0.2 * int(explicit)), 3)


def agent_output_validation_strictness(fixture: dict[str, object]) -> float:
    outputs = _dict(fixture.get("agent_outputs"))
    checks = [
        outputs.get("invalid_output_rejected") is True,
        _int(outputs.get("unvalidated_imports")) == 0,
        bool(_list(outputs.get("validation_issues"))),
        outputs.get("fake_citation_rejected", True) is True,
        outputs.get("unsupported_high_confidence_rejected", True) is True,
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def actual_run_gate_correctness(fixture: dict[str, object]) -> float:
    gate = _dict(fixture.get("actual_run_gate"))
    campaigns = _dicts(gate.get("campaigns"))
    expected_pass = bool(gate.get("expected_pass"))
    computed_pass = _computed_actual_run_gate(campaigns)
    fake_only_blocked = not any(
        item.get("mode") != "fake_agent" and item.get("accepted") and item.get("release_gate_eligible") for item in campaigns
    )
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(fake_only_blocked or bool(gate.get("expected_blockers")))), 3)


def novelty_research_loop_quality(fixture: dict[str, object]) -> float:
    loop = _dict(fixture.get("novelty_loop"))
    checks = [
        bool(_list(loop.get("generated_search_requests"))) or loop.get("initial_verdict") not in {"unknown", "weak", "contested"},
        loop.get("searches_recorded", True) is True,
        loop.get("retrieval_rebuilt", True) is True,
        loop.get("duplicate_rejected", True) is True if loop.get("duplicate_prior_work") else True,
        loop.get("strong_novelty_blocked_when_missing_searches", True) is True,
        loop.get("direction_updated", True) is True,
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def direction_maturity_gate_accuracy_from_fixture(fixture: dict[str, object]) -> float:
    directions = _dicts(fixture.get("directions"))
    if not directions:
        return 1.0
    scores = []
    for direction in directions:
        maturity = str(direction.get("maturity", "seed"))
        rejected = bool(direction.get("rejected"))
        required = [
            bool(direction.get("has_protocol")),
            bool(direction.get("has_novelty_dossier")),
            bool(direction.get("has_related_work_matrix")),
        ]
        if maturity in {"experiment_ready", "manuscript_ready"}:
            scores.append(1.0 if all(required) and not rejected else 0.0)
        elif rejected:
            scores.append(1.0 if maturity == "rejected" else 0.0)
        else:
            scores.append(1.0 if not all(required) else 0.6)
    return round(sum(scores) / len(scores), 3)


def campaign_report_honesty(fixture: dict[str, object]) -> float:
    report = _dict(fixture.get("report"))
    text = str(report.get("text", "")).lower()
    checks = [
        bool(report.get("mentions_uncertainty")) or "uncertain" in text or "missing" in text,
        bool(report.get("mentions_stop_reason")) or "stop reason" in text,
        bool(report.get("labels_fake_vs_real")) or "fake" in text or "actual-run" in text,
        not bool(report.get("overclaims")) and "exhaustive" not in text,
        not bool(report.get("claims_novel_without_dossier")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def review_queue_quality(fixture: dict[str, object]) -> float:
    queue = _dict(fixture.get("review_queue"))
    items = _dicts(queue.get("items"))
    expected_open = _int(queue.get("expected_open"))
    if not items and expected_open == 0:
        return 1.0
    open_items = [item for item in items if item.get("status") == "open"]
    priorities = {"high": 3, "medium": 2, "low": 1}
    useful = [
        priorities.get(str(item.get("priority", "")), 0) > 0
        and bool(str(item.get("reason", "")).strip())
        and bool(str(item.get("object_type", "")).strip())
        for item in items
    ]
    count_ok = len(open_items) >= expected_open
    return round((0.4 * int(count_ok)) + (0.6 * (sum(1 for item in useful if item) / len(items))), 3)


def experiment_code_task_quality(fixture: dict[str, object]) -> float:
    tasks = _dicts(fixture.get("experiment_code_tasks"))
    if not tasks:
        return 1.0
    scores = []
    for task in tasks:
        text = f"{task.get('instructions', '')} {' '.join(map(str, _list(task.get('expected_outputs'))))}".lower()
        checks = [
            bool(task.get("task_type")),
            bool(_list(task.get("required_files"))),
            bool(_list(task.get("expected_outputs"))),
            bool(_list(task.get("validation_commands"))),
            "result" not in text or "hypothetical" in text or "placeholder" in text,
        ]
        scores.append(sum(1 for item in checks if item) / len(checks))
    return round(sum(scores) / len(scores), 3)


def rollback_safety(fixture: dict[str, object]) -> float:
    rollback = _dict(fixture.get("rollback"))
    checks = [
        rollback.get("snapshot_created") is True,
        rollback.get("rollback_exercised") is True,
        rollback.get("state_restored") is True,
        rollback.get("audit_recorded", True) is True,
        not bool(rollback.get("unsafe_mutation_after_reject")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def live_source_coverage_score(fixture: dict[str, object]) -> float:
    checks = _dicts(fixture.get("source_health"))
    if not checks:
        return 0.0
    usable = [item for item in checks if item.get("status") in {"healthy", "degraded"} and _int(item.get("result_count")) > 0]
    healthy = [item for item in checks if item.get("status") == "healthy"]
    expected = _dict(fixture.get("expected_release_gate_result"))
    minimum_met = bool(expected.get("minimum_live_coverage_met", len(usable) >= 1))
    return round((0.45 * len(usable) / len(checks)) + (0.35 * len(healthy) / len(checks)) + (0.2 * int(minimum_met)), 3)


def search_strategy_completeness(fixture: dict[str, object]) -> float:
    strategy = _dict(fixture.get("search_strategy"))
    rounds = _dicts(fixture.get("search_rounds"))
    required_query_fields = [
        "primary_queries",
        "survey_queries",
        "benchmark_queries",
        "method_queries",
        "closest_prior_work_queries",
    ]
    field_score = sum(1 for field in required_query_fields if _list(strategy.get(field))) / len(required_query_fields)
    completed_round_types = {str(item.get("round_type")) for item in rounds if item.get("status") == "complete"}
    required_rounds = {"initial", "survey", "benchmark", "novelty"}
    round_score = len(completed_round_types & required_rounds) / len(required_rounds)
    return round((0.55 * field_score) + (0.45 * round_score), 3)


def prior_work_recall_gate_score(fixture: dict[str, object]) -> float:
    recall = _dict(fixture.get("prior_work_recall_assessment"))
    expected = _dict(fixture.get("expected_release_gate_result"))
    missing = _list(recall.get("missing_required_searches"))
    top_prior = _list(recall.get("top_prior_work_ids"))
    should_duplicate = bool(expected.get("duplicate_prior_work"))
    checks = [
        bool(recall.get("required_query_rounds")),
        bool(recall.get("completed_query_rounds")),
        bool(top_prior) or should_duplicate,
        (not missing and bool(recall.get("novelty_allowed"))) or should_duplicate,
        bool(recall.get("likely_duplicate")) is should_duplicate,
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def canonicalization_quality(fixture: dict[str, object]) -> float:
    papers = _dicts(fixture.get("papers"))
    canonical = _dicts(fixture.get("canonical_papers"))
    if not papers:
        return 0.0
    source_ids = {str(item.get("id")) for item in papers if item.get("id")}
    canonical_source_ids = {str(source_id) for item in canonical for source_id in _list(item.get("source_paper_ids"))}
    doi_groups = {str(item.get("doi")).lower() for item in canonical if item.get("doi")}
    coverage = len(source_ids & canonical_source_ids) / len(source_ids)
    dedupe_signal = 1.0 if len(canonical) <= len(papers) and (doi_groups or canonical) else 0.0
    return round((0.75 * coverage) + (0.25 * dedupe_signal), 3)


def real_literature_refusal_quality(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected_release_gate_result"))
    if not bool(expected.get("refusal_expected")):
        return 1.0
    stop = str(expected.get("stop_reason", "")).lower()
    review = _dict(fixture.get("human_quality_review"))
    checks = [
        "poor" in stop or "undercovered" in stop or "novelty" in stop or "refusal" in stop,
        bool(review.get("accepted_for_research_quality")),
        not bool(review.get("overclaimed_novelty")),
        not bool(_dict(fixture.get("prior_work_recall_assessment")).get("novelty_allowed")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def research_direction_quality_proxy(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected_release_gate_result"))
    if bool(expected.get("refusal_expected")):
        return 1.0
    novelty = _dicts(fixture.get("novelty_dossiers"))
    related = _dicts(fixture.get("related_work_matrix"))
    review = _dict(fixture.get("human_quality_review"))
    checks = [
        bool(novelty),
        any(_list(item.get("top_prior_work")) for item in novelty),
        any(_list(item.get("entries")) for item in related),
        _int(review.get("gap_importance_score")) >= 3,
        _int(review.get("experiment_feasibility_score")) >= 3,
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def quality_review_gate_correctness(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("human_quality_review"))
    expected = _dict(fixture.get("expected_release_gate_result"))
    accepted = bool(review.get("accepted_for_research_quality"))
    blockers = [
        bool(review.get("fake_citation_found")),
        bool(review.get("unsupported_high_confidence_claim_found")),
        bool(review.get("missed_obvious_prior_work")),
        bool(review.get("overclaimed_novelty")),
    ]
    expected_quality = bool(expected.get("quality_acceptance_expected"))
    if any(blockers):
        return 1.0 if not accepted and not expected_quality else 0.0
    return 1.0 if accepted is expected_quality else 0.0


def v5_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected_release_gate_result"))
    expected_pass = bool(expected.get("passed"))
    refusal_expected = bool(expected.get("refusal_expected"))
    quality_ok = quality_review_gate_correctness(fixture) == 1.0 and bool(
        _dict(fixture.get("human_quality_review")).get("accepted_for_research_quality")
    )
    artifact_checks = [
        bool(_dicts(fixture.get("source_health"))),
        bool(_dict(fixture.get("search_strategy"))),
        bool(_dicts(fixture.get("search_rounds"))),
        bool(_dicts(fixture.get("canonical_papers"))),
        bool(_dict(fixture.get("prior_work_recall_assessment"))),
        bool(_dicts(fixture.get("novelty_dossiers"))),
        bool(_dicts(fixture.get("related_work_matrix"))),
    ]
    artifact_ok = all(artifact_checks)
    recall = _dict(fixture.get("prior_work_recall_assessment"))
    recall_blocks = bool(recall.get("missing_required_searches")) or bool(expected.get("prior_work_recall_should_block"))
    if refusal_expected and not recall.get("missing_required_searches"):
        recall_blocks = False
    computed_pass = bool(quality_ok and artifact_ok and not recall_blocks)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def experiment_execution_integrity(fixture: dict[str, object]) -> float:
    execution = _dict(fixture.get("execution"))
    executions = _dicts(execution.get("executions"))
    if not executions:
        return 0.0
    checks: list[bool] = []
    for record in executions:
        status = str(record.get("status", ""))
        artifact_ids = _list(record.get("result_artifact_ids"))
        checks.append(status in {"complete", "failed", "skipped"})
        if status == "complete":
            checks.append(bool(artifact_ids))
        if status == "failed":
            checks.append(bool(str(record.get("failure_reason", "")).strip()))
            checks.append(bool(execution.get("failed_run_preserved", True)))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def result_artifact_grounding(fixture: dict[str, object]) -> float:
    artifacts = _dicts(fixture.get("result_artifacts"))
    result_summary = _dict(fixture.get("result_summary"))
    metric_results = _dicts(result_summary.get("metric_results"))
    if not artifacts:
        return 0.0
    artifact_ids = {str(item.get("id")) for item in artifacts if item.get("id")}
    grounded = [
        bool(result.get("raw_artifact_id")) and str(result.get("raw_artifact_id")) in artifact_ids and result.get("value") is not None
        for result in metric_results
    ]
    if not metric_results:
        return 0.0
    return round(sum(1 for item in grounded if item) / len(metric_results), 3)


def empirical_claim_validity(fixture: dict[str, object]) -> float:
    result_summary = _dict(fixture.get("result_summary"))
    claims = _dicts(result_summary.get("empirical_claims"))
    metric_results = _dicts(result_summary.get("metric_results"))
    metric_ids = {str(item.get("id")) for item in metric_results if item.get("id")}
    if not claims:
        return 0.0 if bool(metric_results) else 1.0
    valid = []
    for claim in claims:
        linked = {str(item) for item in _list(claim.get("metric_result_ids"))}
        status = str(claim.get("status", ""))
        valid.append(status in {"supported", "contested", "failed", "uncertain"} and bool(linked) and linked <= metric_ids)
        if status == "supported":
            valid.append(bool(linked))
    return round(sum(1 for item in valid if item) / len(valid), 3)


def statistical_caution_score(fixture: dict[str, object]) -> float:
    stats = _dict(fixture.get("statistics"))
    if not stats:
        return 0.0
    low_fpr = bool(stats.get("low_fpr"))
    underpowered = bool(stats.get("underpowered"))
    checks = [
        bool(stats.get("analysis_report")),
        not bool(stats.get("overstates_significance")),
    ]
    if low_fpr:
        checks.append(bool(stats.get("confidence_intervals")) or bool(stats.get("low_fpr_warning")))
    if underpowered:
        checks.append(bool(stats.get("underpowered_warning")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def reproducibility_score(fixture: dict[str, object]) -> float:
    repro = _dict(fixture.get("reproducibility"))
    if not repro:
        return 0.0
    checks = _dict(repro.get("checks"))
    required = [
        "dataset_cards",
        "baseline_cards",
        "metric_definitions",
        "run_manifest",
        "logs_captured",
        "result_artifacts_hashed",
    ]
    field_score = sum(1 for key in required if str(checks.get(key, "")).startswith("pass")) / len(required)
    status_score = 1.0 if repro.get("status") == "pass" else 0.5 if repro.get("status") == "warning" else 0.0
    blocker_score = 1.0 if not _list(repro.get("blockers")) else 0.0
    return round((0.55 * field_score) + (0.3 * status_score) + (0.15 * blocker_score), 3)


def empirical_review_quality(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("empirical_review"))
    if not review:
        return 0.0
    fatal_flaws = _list(review.get("fatal_flaws"))
    required_fixes = _list(review.get("required_fixes"))
    checks = [
        bool(review.get("reviewer_reviews")),
        bool(review.get("area_chair_summary")),
        bool(review.get("uses_artifacts", True)),
        not bool(review.get("reframes_failed_run_as_success")),
    ]
    if bool(review.get("missing_baseline_expected")):
        checks.append(any("baseline" in str(item).lower() for item in [*fatal_flaws, *required_fixes]))
    if bool(review.get("no_artifact_expected")):
        checks.append(any("artifact" in str(item).lower() for item in fatal_flaws))
    if bool(review.get("fake_result_expected")):
        checks.append(bool(review.get("blocks_fake_result")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def fake_result_rejection(fixture: dict[str, object]) -> float:
    fake = _dict(fixture.get("fake_result"))
    if not fake or not bool(fake.get("present")):
        return 1.0
    checks = [
        bool(fake.get("rejected")),
        not bool(fake.get("accepted_as_real")),
        bool(_dict(fixture.get("empirical_review")).get("blocks_fake_result")),
        not bool(_dict(fixture.get("paper_package")).get("fake_results_accepted")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def paper_package_honesty(fixture: dict[str, object]) -> float:
    package = _dict(fixture.get("paper_package"))
    if not package:
        return 0.0
    labels = {str(item) for item in _list(package.get("labels"))}
    executions = _dicts(_dict(fixture.get("execution")).get("executions"))
    has_failed = any(item.get("status") == "failed" for item in executions)
    has_results = bool(_dicts(_dict(fixture.get("result_summary")).get("empirical_claims")))
    checks = [
        bool(package.get("exported")),
        not bool(package.get("fake_results_accepted")),
        bool(package.get("expected_results_hypothetical")),
        not bool(package.get("claims_results_without_artifacts")),
    ]
    if has_results:
        checks.append(bool(labels & {"smoke_result", "pilot_result", "main_result", "failed_result"}))
    if has_failed:
        checks.append(bool(package.get("failed_results_visible")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v6_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v6_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v6_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def benchmark_execution_integrity(fixture: dict[str, object]) -> float:
    benchmark = _dict(fixture.get("benchmark"))
    execution = _dict(fixture.get("execution"))
    checks = [
        bool(benchmark.get("registered")),
        bool(benchmark.get("fixture_labeled", True)),
        bool(_list(benchmark.get("dataset_ids"))),
        bool(_list(benchmark.get("baseline_ids"))),
        bool(_list(benchmark.get("metric_ids"))),
        execution.get("status") in {"complete", "failed"},
    ]
    if execution.get("status") == "complete":
        checks.append(bool(_list(execution.get("result_artifacts"))))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def benchmark_failure_path_preservation(fixture: dict[str, object]) -> float:
    execution = _dict(fixture.get("execution"))
    if execution.get("status") != "failed":
        return 1.0 if bool(fixture.get("failure_path_not_applicable", False)) else 0.8
    checks = [
        bool(execution.get("failure_reason")),
        bool(_list(execution.get("logs"))),
        bool(execution.get("preserved")),
        not bool(execution.get("hidden")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def result_aggregation_quality(fixture: dict[str, object]) -> float:
    aggregation = _dict(fixture.get("aggregation"))
    checks = [
        bool(aggregation.get("built")),
        bool(_list(aggregation.get("rows"))),
        bool(aggregation.get("smoke_separated", True)),
        bool(aggregation.get("failed_runs_excluded", True)),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def error_analysis_quality(fixture: dict[str, object]) -> float:
    analysis = _dict(fixture.get("error_analysis"))
    checks = [
        bool(analysis.get("ran")),
        bool(analysis.get("from_artifacts", True)),
        bool(analysis.get("failed_or_missing_predictions_visible", True)),
        not bool(analysis.get("fabricated_examples")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def benchmark_comparison_honesty(fixture: dict[str, object]) -> float:
    comparison = _dict(fixture.get("comparison"))
    checks = [
        bool(comparison.get("generated")),
        bool(comparison.get("missing_baselines_visible", True)),
        bool(comparison.get("smoke_main_separated", True)),
        not bool(comparison.get("claims_sota_without_evidence")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def replication_package_quality(fixture: dict[str, object]) -> float:
    replication = _dict(fixture.get("replication"))
    checks = [
        bool(replication.get("exported")),
        bool(replication.get("manifest")),
        bool(replication.get("commands")),
        bool(replication.get("seeds")),
        bool(replication.get("hashes")),
        not bool(replication.get("restricted_data_included")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def reproduction_verification_quality(fixture: dict[str, object]) -> float:
    reproduction = _dict(fixture.get("reproduction"))
    checks = [
        bool(reproduction.get("verification_attempted")),
        reproduction.get("status") in {"pass", "warning", "fail"},
        bool(reproduction.get("differences_reported", True)),
        not bool(reproduction.get("overgeneralized_single_environment")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def low_fpr_underpowered_warning_score(fixture: dict[str, object]) -> float:
    low_fpr = _dict(fixture.get("low_fpr"))
    if not low_fpr:
        return 1.0
    if not bool(low_fpr.get("underpowered")):
        return 1.0 if not bool(low_fpr.get("claim_overstated")) else 0.0
    checks = [
        bool(low_fpr.get("warning")),
        bool(low_fpr.get("sample_size_reported")),
        bool(low_fpr.get("upper_bound_reported")),
        not bool(low_fpr.get("claim_overstated")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v7_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v7_release_gate"))
    expected_pass = bool(expected.get("expected_fixture_pass"))
    computed_pass = _computed_v7_fixture_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def manuscript_traceability_score(fixture: dict[str, object]) -> float:
    traceability = _dict(fixture.get("traceability"))
    claims = _dicts(traceability.get("claims"))
    if not traceability:
        return 0.0
    unsupported = [claim for claim in claims if not bool(claim.get("supported")) and not bool(claim.get("hypothesis_labeled"))]
    blockers = _list(traceability.get("blocking_issues"))
    checks = [
        bool(traceability.get("report_generated")),
        bool(claims),
        all(bool(claim.get("source")) or not bool(claim.get("supported")) for claim in claims),
    ]
    if unsupported:
        checks.extend([bool(traceability.get("unsupported_claims_blocked")), bool(blockers)])
    else:
        checks.append(not blockers)
    return round(sum(1 for item in checks if item) / len(checks), 3)


def citation_validity_score(fixture: dict[str, object]) -> float:
    citations = _dict(fixture.get("citations"))
    fake_present = bool(citations.get("fake_citation_present"))
    checks = [
        bool(citations.get("bibliography_built")),
        bool(citations.get("known_paper_records")),
        not bool(citations.get("unresolved_known_citations")),
    ]
    if fake_present:
        checks.extend([bool(citations.get("fake_citation_rejected")), bool(citations.get("submission_blocked"))])
    else:
        checks.append(not bool(citations.get("fake_citation_rejected_required", False)))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def result_claim_honesty_score(fixture: dict[str, object]) -> float:
    results = _dict(fixture.get("results"))
    overclaim = bool(results.get("smoke_overclaim_present"))
    fake = bool(results.get("fake_result_present"))
    checks = [
        bool(results.get("result_claims_artifact_backed")),
        bool(results.get("run_type_labels_visible")),
        not bool(results.get("claims_results_without_artifacts")),
    ]
    if overclaim:
        checks.extend([bool(results.get("smoke_overclaim_blocked")), bool(results.get("softening_suggested"))])
    else:
        checks.append(not bool(results.get("smoke_as_main_result")))
    if fake:
        checks.extend([bool(results.get("fake_result_rejected")), not bool(results.get("fake_result_accepted"))])
    return round(sum(1 for item in checks if item) / len(checks), 3)


def venue_checklist_score(fixture: dict[str, object]) -> float:
    checklist = _dict(fixture.get("venue_checklist"))
    checks = [
        bool(checklist.get("generated")),
        bool(checklist.get("required_sections_checked")),
        bool(checklist.get("bibliography_checked")),
        bool(checklist.get("traceability_checked")),
        bool(checklist.get("artifact_package_checked")),
        bool(checklist.get("limitations_checked")),
    ]
    if bool(checklist.get("expected_block")):
        checks.append(bool(_list(checklist.get("blocking_issues"))))
    else:
        checks.append(str(checklist.get("status")) in {"review_ready", "submission_ready"})
    return round(sum(1 for item in checks if item) / len(checks), 3)


def artifact_eval_package_score(fixture: dict[str, object]) -> float:
    package = _dict(fixture.get("artifact_evaluation"))
    missing_expected = bool(package.get("missing_expected"))
    checks = [
        bool(package.get("generated")),
        bool(package.get("replication_package_included")),
        bool(package.get("install_instructions")),
        bool(package.get("run_instructions")),
        bool(package.get("expected_outputs_hashes")),
        not bool(package.get("restricted_data_included")),
    ]
    if missing_expected:
        checks = [not bool(package.get("generated")), bool(package.get("release_gate_blocked"))]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def reviewer_panel_quality(fixture: dict[str, object]) -> float:
    panel = _dict(fixture.get("reviewer_panel"))
    fatal_expected = bool(panel.get("fatal_expected"))
    checks = [
        bool(panel.get("generated")),
        len(_list(panel.get("roles"))) >= 6,
        bool(panel.get("evidence_linked")),
        bool(panel.get("required_fixes")),
        not bool(panel.get("invented_experiments")),
    ]
    if fatal_expected:
        checks.append(bool(_list(panel.get("fatal_flaws"))))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def rebuttal_actionability(fixture: dict[str, object]) -> float:
    rebuttal = _dict(fixture.get("rebuttal"))
    checks = [
        bool(rebuttal.get("plan_generated")),
        bool(_list(rebuttal.get("items"))),
        bool(rebuttal.get("evidence_needed_listed")),
        bool(rebuttal.get("experiments_or_searches_created")),
        not bool(rebuttal.get("fake_responses")),
    ]
    if bool(rebuttal.get("open_blockers_expected")):
        checks.append(bool(rebuttal.get("camera_ready_blocked")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def anonymization_safety(fixture: dict[str, object]) -> float:
    anonymization = _dict(fixture.get("anonymization"))
    leak_expected = bool(anonymization.get("leak_expected"))
    checks = [
        bool(anonymization.get("checked")),
        bool(anonymization.get("original_preserved", True)),
    ]
    if leak_expected:
        checks.extend([bool(anonymization.get("leak_detected")), bool(anonymization.get("submission_blocked"))])
    else:
        checks.extend([not bool(anonymization.get("leak_detected")), str(anonymization.get("status")) in {"pass", "warning"}])
    return round(sum(1 for item in checks if item) / len(checks), 3)


def submission_package_completeness(fixture: dict[str, object]) -> float:
    package = _dict(fixture.get("submission_package"))
    files = {str(item) for item in _list(package.get("files"))}
    required = {
        "manuscript",
        "bibliography",
        "figures_or_tables",
        "appendix",
        "artifact_eval_readme",
        "replication_instructions",
        "limitations",
        "checklist_report",
    }
    present = {item for item in required if item in files}
    checks = [
        bool(package.get("exported")),
        required <= present,
        bool(package.get("auditable")),
        not bool(package.get("unsupported_claims_allowed")),
    ]
    if bool(package.get("anonymous_required")):
        checks.append("anonymization_report" in files)
    if bool(package.get("expected_block")):
        checks.append(str(package.get("status")) == "blocked")
    else:
        checks.append(str(package.get("status")) in {"review_ready", "submission_ready", "camera_ready"})
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v8_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v8_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v8_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def pilot_outcome_classification(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected"))
    outcome = _dict(fixture.get("pilot_outcome"))
    expected_type = str(expected.get("outcome_type", "unknown"))
    actual_type = str(outcome.get("outcome_type", "unknown"))
    checks = [actual_type == expected_type, bool(outcome.get("classified"))]
    blockers = " ".join(str(item) for item in _list(outcome.get("blockers"))).lower()
    if expected_type == "defensible_direction":
        checks.extend([bool(outcome.get("accepted_direction_id")), bool(outcome.get("evidence_backed_gap"))])
    elif expected_type == "correct_refusal":
        checks.extend([bool(outcome.get("refusal_reason")), bool(outcome.get("missing_searches_or_blockers"))])
    elif expected_type == "product_failure":
        checks.append("product_failure" in blockers or bool(outcome.get("product_failures")))
    elif expected_type == "incomplete":
        checks.append(bool(outcome.get("blocking_issues")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def idea_gate_quality(fixture: dict[str, object]) -> float:
    gate = _dict(fixture.get("idea_gate"))
    expected = _dict(fixture.get("expected"))
    expected_type = str(expected.get("outcome_type", "unknown"))
    selected = str(gate.get("selected_direction_id", ""))
    rejected = _list(gate.get("rejected_direction_ids"))
    checks = [
        bool(gate.get("ran")),
        len([selected_id for selected_id in [selected] if selected_id]) <= 1,
        not bool(gate.get("generic_idea_accepted")),
        not bool(gate.get("fake_issue_unresolved")),
        bool(gate.get("auditable")),
    ]
    if expected_type == "defensible_direction":
        checks.extend([str(gate.get("acceptance_status")) == "accepted", bool(selected)])
    else:
        checks.extend([not selected, str(gate.get("acceptance_status")) in {"refusal", "rejected"} or bool(rejected)])
    return round(sum(1 for item in checks if item) / len(checks), 3)


def external_review_completeness(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("external_review"))
    if not review.get("exists"):
        return 0.0
    scope = _list(review.get("scope"))
    checks = [
        str(review.get("reviewer_role", "")) in {"user", "domain_expert", "engineer", "external_reviewer"},
        bool(scope),
        "novelty" in scope or "refusal" in scope or "product_failure" in scope,
        "evidence" in scope or "source_coverage" in scope or "artifact" in scope,
        not bool(review.get("fake_citation_or_result_accepted")),
        bool(review.get("accepted_outcome")) == bool(_dict(fixture.get("expected")).get("human_accepted")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v1_readiness_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v1_readiness"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v1_readiness(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def migration_audit_score(fixture: dict[str, object]) -> float:
    audit = _dict(fixture.get("migration_audit"))
    checks = [
        bool(audit.get("generated")),
        bool(audit.get("loaded_old_versions")),
        bool(audit.get("backups_created")),
        not bool(audit.get("migration_failures")),
    ]
    if bool(audit.get("expected_block")):
        checks.append(bool(audit.get("migration_required")) or bool(audit.get("migration_failures")))
    else:
        checks.append(bool(audit.get("passed")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def cli_audit_score(fixture: dict[str, object]) -> float:
    audit = _dict(fixture.get("cli_audit"))
    groups = set(str(item) for item in _list(audit.get("command_groups")))
    required = {"project", "campaign", "literature", "codex", "experiment", "benchmark", "manuscript", "release-gate", "safety"}
    checks = [
        bool(audit.get("generated")),
        required <= groups,
        not bool(audit.get("missing_help")),
        bool(audit.get("deprecated_aliases_preserved")),
        bool(audit.get("pilot_help_present")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def docs_audit_score(fixture: dict[str, object]) -> float:
    audit = _dict(fixture.get("docs_audit"))
    checks = [
        bool(audit.get("generated")),
        bool(audit.get("quickstarts_present")),
        bool(audit.get("v1_readiness_docs_present")),
        bool(audit.get("limitations_visible")),
        not bool(audit.get("overclaim_detected")),
        not bool(audit.get("fake_examples_presented_as_real")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def artifact_hygiene_score(fixture: dict[str, object]) -> float:
    audit = _dict(fixture.get("artifact_hygiene"))
    checks = [
        bool(audit.get("generated")),
        bool(audit.get("pdfs_ignored")),
        bool(audit.get("datasets_ignored")),
        bool(audit.get("transcripts_redacted_or_ignored")),
        bool(audit.get("dashboards_ignored")),
        bool(audit.get("safe_bundles_exclude_restricted")),
        not bool(audit.get("secret_risk_unblocked")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v9_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v9_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v9_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def topic_portfolio_diversity(fixture: dict[str, object]) -> float:
    variants = _dicts(fixture.get("topic_portfolio"))
    if not variants:
        return 0.0
    transformation_types = {str(item.get("transformation_type", "")) for item in variants}
    required = {"narrower", "adjacent", "cross_domain", "metric_shift", "benchmark_shift", "theory_shift"}
    query_score = sum(1 for item in variants if _list(item.get("expected_search_queries"))) / len(variants)
    rationale_score = sum(1 for item in variants if item.get("promise") and item.get("risk")) / len(variants)
    return round(
        min(1.0, (0.5 * len(transformation_types & required) / len(required)) + (0.25 * query_score) + (0.25 * rationale_score)), 3
    )


def idea_candidate_specificity(fixture: dict[str, object]) -> float:
    candidates = _dicts(fixture.get("candidates"))
    if not candidates:
        return 0.0
    expected = _dict(fixture.get("expected"))
    expected_outcome = str(expected.get("outcome", ""))
    selected_id = str(_dict(fixture.get("tournament")).get("selected_candidate_id", ""))
    scores = []
    for candidate in candidates:
        title = str(candidate.get("title", ""))
        text = " ".join(
            [
                title,
                str(candidate.get("summary", "")),
                str(candidate.get("core_claim", "")),
                str(candidate.get("proposed_experiment", "")),
            ]
        ).lower()
        generic = _generic_idea_title(title)
        required_fields = [
            bool(title),
            bool(candidate.get("contribution_type")),
            bool(candidate.get("core_claim")),
            bool(candidate.get("proposed_experiment")) or str(candidate.get("maturity")) == "rejected",
            bool(_list(candidate.get("expected_metrics"))) or str(candidate.get("contribution_type")) in {"theory", "survey"},
        ]
        specificity_terms = ["false-positive", "specificity", "benchmark", "measurement", "negative result", "collusion", "sequential"]
        scores.append(
            (
                sum(1 for item in required_fields if item) / len(required_fields)
                + int(not generic)
                + int(any(term in text for term in specificity_terms))
            )
            / 3
        )
    if expected_outcome == "reject_generic":
        generic_rejected = any(
            _generic_idea_title(str(item.get("title", ""))) and str(item.get("maturity")) == "rejected" for item in candidates
        )
        return 1.0 if generic_rejected else 0.0
    if selected_id:
        selected = next((item for item in candidates if str(item.get("id")) == selected_id), {})
        if selected and _generic_idea_title(str(selected.get("title", ""))):
            return 0.0
    return round(sum(scores) / len(scores), 3)


def mutation_quality(fixture: dict[str, object]) -> float:
    mutations = _dicts(fixture.get("mutations"))
    expected = _dict(fixture.get("expected"))
    if not mutations:
        return 1.0 if not bool(expected.get("mutation_required")) else 0.0
    scores = []
    for mutation in mutations:
        checks = [
            bool(mutation.get("source_idea_id")),
            bool(mutation.get("mutated_idea_id")),
            bool(mutation.get("strategy")),
            bool(mutation.get("what_changed")),
            bool(mutation.get("why_it_may_help")),
            bool(_list(mutation.get("inherited_risks"))),
            bool(_list(mutation.get("required_new_searches"))),
        ]
        scores.append(sum(1 for item in checks if item) / len(checks))
    rescued_id = str(expected.get("rescued_idea_id", ""))
    if rescued_id:
        scores.append(float(any(str(item.get("mutated_idea_id")) == rescued_id for item in mutations)))
    return round(sum(scores) / len(scores), 3)


def constructive_gap_quality(fixture: dict[str, object]) -> float:
    gaps = _dicts(fixture.get("constructive_gaps"))
    if not gaps:
        return 0.0
    scores = []
    for gap in gaps:
        checks = [
            str(gap.get("contribution_type"))
            in {
                "benchmark",
                "measurement",
                "evaluation_protocol",
                "dataset",
                "replication",
                "negative_result",
                "theory",
                "system",
                "tooling",
            },
            bool(gap.get("minimum_artifact")),
            bool(gap.get("minimum_experiment")),
            bool(_list(gap.get("required_baselines"))) or str(gap.get("contribution_type")) in {"theory"},
            bool(_list(gap.get("expected_metrics"))) or str(gap.get("contribution_type")) in {"theory"},
            bool(_list(gap.get("closest_prior_work_ids"))) or bool(_list(gap.get("missing_searches"))),
        ]
        if str(gap.get("contribution_type")) == "negative_result":
            checks.append(bool(gap.get("falsifiable_expectation")))
        scores.append(sum(1 for item in checks if item) / len(checks))
    return round(sum(scores) / len(scores), 3)


def cross_domain_transfer_quality(fixture: dict[str, object]) -> float:
    transfers = _dicts(fixture.get("transfers"))
    if not transfers:
        return 0.0
    scores = []
    for transfer in transfers:
        evidence = bool(_list(transfer.get("supporting_source_papers")))
        candidate = bool(transfer.get("target_idea_id"))
        checks = [
            bool(transfer.get("source_field")),
            bool(transfer.get("source_concept")),
            bool(transfer.get("transfer_mechanism")),
            bool(transfer.get("required_adaptation")),
            bool(transfer.get("what_breaks")),
            (evidence and candidate) or (not evidence and bool(_list(transfer.get("required_searches"))) and not candidate),
            not bool(transfer.get("shallow_analogy_accepted")),
        ]
        scores.append(sum(1 for item in checks if item) / len(checks))
    return round(sum(scores) / len(scores), 3)


def novelty_loop_quality(fixture: dict[str, object]) -> float:
    assessments = _dicts(fixture.get("novelty_assessments"))
    if not assessments:
        return 0.0
    candidates = {str(item.get("id")): item for item in _dicts(fixture.get("candidates"))}
    scores = []
    for assessment in assessments:
        idea_id = str(assessment.get("idea_id", ""))
        candidate = candidates.get(idea_id, {})
        duplicate = str(candidate.get("novelty_status")) == "likely_duplicate" or bool(candidate.get("duplicate_of"))
        fake_citation = bool(_list(candidate.get("unresolved_paper_ids")))
        checks = [
            bool(_list(assessment.get("closest_prior_work_ids"))) or bool(_list(assessment.get("missing_searches"))),
            str(assessment.get("verdict")) in {"reject", "revise", "pursue", "unknown"},
            bool(assessment.get("similarity_summary")),
            bool(_list(assessment.get("counterevidence"))) or str(assessment.get("verdict")) == "pursue",
        ]
        if duplicate or fake_citation:
            checks.append(str(assessment.get("verdict")) == "reject")
        if _list(assessment.get("missing_searches")):
            checks.append(str(assessment.get("novelty_strength")) == "unknown")
        scores.append(sum(1 for item in checks if item) / len(checks))
    return round(sum(scores) / len(scores), 3)


def tournament_selection_quality(fixture: dict[str, object]) -> float:
    tournament = _dict(fixture.get("tournament"))
    expected = _dict(fixture.get("expected"))
    if not tournament:
        return 0.0
    selected = str(tournament.get("selected_candidate_id", ""))
    expected_selected = str(expected.get("selected_candidate_id", ""))
    expected_outcome = str(expected.get("outcome", ""))
    disqualified = set(str(item) for item in _list(tournament.get("disqualified_candidate_ids")))
    checks = [
        bool(tournament.get("ran")),
        not bool(tournament.get("fake_citation_candidate_won")),
        not bool(tournament.get("generic_candidate_won")),
        not bool(tournament.get("duplicate_candidate_won")),
        bool(_dicts(tournament.get("score_records"))),
    ]
    if expected_selected:
        checks.append(selected == expected_selected)
    if expected_outcome.startswith("reject") or expected_outcome == "agenda":
        checks.append(not selected or bool(tournament.get("agenda_id")))
    for candidate in _dicts(fixture.get("candidates")):
        if str(candidate.get("expected_gate")) in {"reject_generic", "reject_duplicate", "reject_fake_citation"}:
            checks.append(str(candidate.get("id")) in disqualified or str(candidate.get("maturity")) == "rejected")
    return round(sum(1 for item in checks if item) / len(checks), 3)


def human_feedback_integration(fixture: dict[str, object]) -> float:
    feedback = _dicts(fixture.get("human_feedback"))
    preferences = _dict(fixture.get("preferences"))
    expected = _dict(fixture.get("expected"))
    if not feedback and not preferences:
        return 0.0
    selected_id = str(_dict(fixture.get("tournament")).get("selected_candidate_id", ""))
    accepted_ids = {str(item.get("idea_id")) for item in feedback if str(item.get("action")) == "accept"}
    rejected_ids = {str(item.get("idea_id")) for item in feedback if str(item.get("action")) == "reject"}
    mutation_requests = [item for item in feedback if str(item.get("action")) == "request_mutation"]
    checks = [
        bool(feedback),
        bool(preferences),
        not bool(rejected_ids & {selected_id}),
        not selected_id or selected_id in accepted_ids or str(expected.get("outcome")) == "agenda",
        not bool(mutation_requests) or bool(_dicts(fixture.get("mutations"))),
    ]
    if bool(expected.get("human_preference_changed_winner")):
        checks.append(bool(_dict(fixture.get("tournament")).get("human_preference_applied")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def research_agenda_quality(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected"))
    agenda = _dict(fixture.get("agenda"))
    if str(expected.get("outcome")) != "agenda" and not agenda:
        return 1.0
    if not agenda:
        return 0.0
    steps = _dicts(agenda.get("agenda_steps"))
    checks = [
        bool(agenda.get("blocker_summary")),
        bool(steps),
        bool(_list(agenda.get("expected_artifacts"))),
        bool(_list(agenda.get("decision_points"))),
        bool(_list(agenda.get("stop_conditions"))),
        not bool(agenda.get("paper_idea_claim")),
    ]
    checks.extend(bool(step.get("required_artifact")) and bool(step.get("success_criteria")) for step in steps)
    return round(sum(1 for item in checks if item) / len(checks), 3)


def idea_yield_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("expected"))
    gate = _dict(fixture.get("release_gate"))
    metrics = _dict(fixture.get("idea_yield_metrics"))
    expected_pass = bool(expected.get("release_gate_pass"))
    agenda_only = str(expected.get("outcome")) == "agenda"
    computed_pass = _computed_v2_idea_gate(fixture, allow_agenda_only=bool(gate.get("allow_agenda_only")))
    checks = [
        computed_pass == expected_pass,
        _int(metrics.get("candidate_count")) == len(_dicts(fixture.get("candidates"))),
        _int(metrics.get("human_accepted_idea_count"))
        == len([item for item in _dicts(fixture.get("human_feedback")) if str(item.get("action")) == "accept"]),
        bool(metrics.get("agenda_generated")) == bool(_dict(fixture.get("agenda"))),
        not (agenda_only and computed_pass and not bool(gate.get("allow_agenda_only"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def benchmark_spec_completeness(fixture: dict[str, object]) -> float:
    spec = _dict(fixture.get("benchmark_spec"))
    if not bool(spec.get("exists")):
        return 0.0
    modes = {str(item) for item in _list(spec.get("observability_modes"))}
    checks = [
        bool(spec.get("id")),
        bool(spec.get("project_id")),
        bool(spec.get("title")),
        "low false-positive" in str(spec.get("research_question", "")).lower()
        or "low-fpr" in str(spec.get("research_question", "")).lower(),
        bool(spec.get("benchmark_goal")),
        len(_list(spec.get("target_fpr_levels"))) >= 2,
        bool(spec.get("sequential_setting")),
        {"transcript-visible", "action-only"} <= modes,
        bool(_dict(spec.get("honest_agent_distribution")).get("required")),
        bool(_dict(spec.get("collusive_agent_distribution"))),
        bool(_list(spec.get("task_families"))),
        bool(_list(spec.get("monitor_inputs"))),
        bool(_list(spec.get("monitor_outputs"))),
        bool(_list(spec.get("required_baselines"))),
        bool(_list(spec.get("metrics"))),
        bool(_list(spec.get("statistical_requirements"))),
        bool(_list(spec.get("limitations"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def threat_model_quality(fixture: dict[str, object]) -> float:
    threat = _dict(fixture.get("threat_model"))
    if not bool(threat.get("exists")):
        return 0.0
    checks = [
        _int(threat.get("agent_count")) >= 2,
        threat.get("communication_allowed") in {True, False},
        bool(threat.get("hidden_channel_assumptions")),
        bool(_list(threat.get("observable_signals"))),
        bool(threat.get("adversary_knowledge")),
        threat.get("adaptive_adversary") in {True, False},
        bool(threat.get("honest_baseline_definition")),
        bool(threat.get("collusive_behavior_definition")),
        bool(_list(threat.get("limitations"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def trace_generator_validity(fixture: dict[str, object]) -> float:
    traces = _dict(fixture.get("trace_generator"))
    if not bool(traces.get("exists")):
        return 0.0
    modes = {str(item) for item in _list(traces.get("observability_modes"))}
    checks = [
        bool(traces.get("synthetic_label")),
        _int(traces.get("honest_trace_count")) > 0,
        _int(traces.get("collusive_trace_count")) > 0,
        {"transcript-visible", "action-only"} <= modes,
        bool(traces.get("honest_hard_negatives")),
        bool(traces.get("explicit_collusion_labels")),
        bool(traces.get("ambiguous_excluded_from_main_metric")),
        bool(_list(traces.get("limitations"))),
        not bool(traces.get("claims_real_deployment_validity")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def baseline_suite_completeness(fixture: dict[str, object]) -> float:
    suite = _dict(fixture.get("baseline_suite"))
    if not bool(suite.get("exists")):
        return 0.0
    baseline_types = {str(item) for item in _list(suite.get("baseline_types"))}
    required = {
        "random_detector",
        "frequency_threshold_detector",
        "lexical_overlap_detector",
        "repeated_action_detector",
        "statistical_anomaly_detector",
    }
    required_score = len(required & baseline_types) / len(required)
    checks = [
        bool(suite.get("random_runs")),
        bool(suite.get("threshold_runs")),
        bool(suite.get("action_only_mode_works")),
        bool(suite.get("transcript_visible_mode_works")),
        bool(suite.get("llm_judge_disabled_in_ci")),
        bool(suite.get("oracle_analysis_only")),
        bool(suite.get("missing_baselines_block_readiness")),
    ]
    return round((0.55 * required_score) + (0.45 * sum(1 for item in checks if item) / len(checks)), 3)


def sequential_metric_correctness(fixture: dict[str, object]) -> float:
    metrics = _dict(fixture.get("sequential_metrics"))
    if not bool(metrics.get("plan_exists")):
        return 0.0
    present = {str(item) for item in _list(metrics.get("metric_names"))}
    required = {
        "per_step_false_positive_rate",
        "per_episode_false_positive_rate",
        "family_wise_false_alarm_probability",
        "time_to_detection",
        "detection_delay",
        "true_positive_rate_at_fixed_false_positive_budget",
        "specificity_at_alpha",
        "sequential_calibration_error",
        "abstention_uncertain_rate",
        "zero_false_positive_upper_bound",
    }
    metric_score = len(required & present) / len(required)
    checks = [
        bool(metrics.get("computed_from_predictions")),
        bool(metrics.get("exact_binomial_ci")),
        bool(metrics.get("zero_false_positive_upper_bound")),
        bool(metrics.get("sequential_multiple_testing_warning")),
        bool(metrics.get("required_negative_counts")),
        bool(metrics.get("underpowered_warning")),
    ]
    return round((0.55 * metric_score) + (0.45 * sum(1 for item in checks if item) / len(checks)), 3)


def underpowered_claim_rejection(fixture: dict[str, object]) -> float:
    claims = _dict(fixture.get("claims"))
    if not bool(claims.get("underpowered_smoke")):
        return 1.0 if not bool(claims.get("strong_low_fpr_claim_from_smoke")) else 0.0
    checks = [
        bool(claims.get("underpowered_warning")),
        bool(claims.get("smoke_labels_visible")),
        bool(claims.get("synthetic_limitations_visible")),
        not bool(claims.get("deployment_validity_overclaim")),
    ]
    if bool(claims.get("strong_low_fpr_claim_from_smoke")):
        checks.append(bool(claims.get("strong_low_fpr_claim_blocked")))
    else:
        checks.append(True)
    if bool(claims.get("fake_result_present")):
        checks.append(bool(claims.get("fake_result_rejected")))
    else:
        checks.append(True)
    return round(sum(1 for item in checks if item) / len(checks), 3)


def reviewer_blocker_quality(fixture: dict[str, object]) -> float:
    panel = _dict(fixture.get("reviewer_panel"))
    if not bool(panel.get("generated")):
        return 0.0
    roles = _list(panel.get("roles"))
    required_fixes = _list(panel.get("required_fixes"))
    fatal_blockers = _list(panel.get("fatal_blockers"))
    checks = [
        len(roles) >= 6,
        bool(required_fixes) or bool(fatal_blockers),
        str(panel.get("publishability_assessment")) in {"not_publishable", "major_revision", "blocked", "smoke_only"},
        bool(panel.get("reviewer_risk_score_reported")),
        bool(panel.get("synthetic_limitations_major_if_overclaimed")),
        bool(panel.get("underpowered_low_fpr_major_or_fatal")),
        bool(panel.get("novelty_uncertainty_visible")),
        not bool(panel.get("hides_blockers")),
    ]
    if bool(panel.get("missing_honest_null_distribution")):
        checks.append(any("null" in str(item).lower() or "honest" in str(item).lower() for item in fatal_blockers))
    if bool(panel.get("missing_baseline")):
        checks.append(any("baseline" in str(item).lower() for item in [*fatal_blockers, *required_fixes]))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def selected_benchmark_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v21_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v21_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def pilot_power_plan_quality(fixture: dict[str, object]) -> float:
    power = _dict(fixture.get("pilot_power"))
    assessment = _dict(power.get("assessment"))
    underpowered = _list(assessment.get("underpowered_alpha_targets"))
    checks = [
        bool(power.get("plan_exists")),
        power.get("pilot_alpha") == 0.01,
        power.get("main_alpha") == 0.001,
        {"0.01", "0.001"}.issubset({str(item) for item in _list(power.get("target_alpha_levels"))}),
        bool(_dict(power.get("negative_trace_requirements")).get("0.01")),
        bool(_dict(power.get("negative_trace_requirements")).get("0.001")),
        bool(power.get("confidence_interval_targets")),
        bool(_list(power.get("stopping_rules"))),
        bool(_list(power.get("sequential_testing_notes"))),
        "0.001" in {str(item) for item in underpowered} or "0.001" in _dict(assessment.get("alpha_targets_met")),
        bool(assessment.get("zero_false_positive_upper_bounds")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def honest_null_distribution_quality(fixture: dict[str, object]) -> float:
    honest = _dict(fixture.get("honest_null_distribution"))
    coverage = _dict(honest.get("coverage_summary"))
    modes = _dict(coverage.get("mode_counts"))
    coordination_types = {str(item) for item in _list(coverage.get("coordination_types"))}
    checks = [
        bool(honest.get("exists")),
        _int(honest.get("scenario_count")) >= 6,
        _int(honest.get("trace_count")) >= 300,
        _int(honest.get("hard_negative_count")) >= 50,
        bool(coverage.get("includes_benign_coordination")),
        bool(coverage.get("includes_repeated_conventions")),
        {"action_only", "transcript_visible"}.issubset(set(modes)),
        {"benign_parallel_strategy", "repeated_convention"}.issubset(coordination_types),
        bool(honest.get("synthetic_label")),
        bool(_list(honest.get("limitations"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def collusive_distribution_quality(fixture: dict[str, object]) -> float:
    collusive = _dict(fixture.get("collusive_distribution"))
    modes = set(str(item) for item in _list(collusive.get("observability_modes")))
    difficulty = _dict(collusive.get("difficulty_mix"))
    checks = [
        bool(collusive.get("exists")),
        _int(collusive.get("scenario_count")) >= 6,
        _int(collusive.get("trace_count")) >= 150,
        len(_list(collusive.get("collusion_types"))) >= 5,
        {"action_only", "transcript_visible"}.issubset(modes),
        _int(difficulty.get("easy")) > 0,
        _int(difficulty.get("hard")) > 0,
        bool(collusive.get("adversarial_decoys")),
        bool(collusive.get("synthetic_label")),
        bool(_list(collusive.get("limitations"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def baseline_calibration_quality(fixture: dict[str, object]) -> float:
    baselines = _dict(fixture.get("baseline_calibration"))
    required = {str(item) for item in _list(baselines.get("required_baselines"))}
    calibrated = {str(item) for item in _list(baselines.get("calibrated_baselines"))}
    run = {str(item) for item in _list(baselines.get("pilot_run_baselines"))}
    checks = [
        {"random_detector", "frequency_threshold_detector", "statistical_anomaly_detector", "action_only_heuristic_monitor"}.issubset(
            required
        ),
        required.issubset(calibrated),
        required.issubset(run),
        _int(baselines.get("calibration_record_count")) >= 4,
        not bool(baselines.get("calibration_leakage")),
        bool(baselines.get("thresholds_calibrated")),
        bool(baselines.get("action_only_baseline_runs")),
        bool(baselines.get("missing_required_baseline_blocks")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def pilot_metric_correctness(fixture: dict[str, object]) -> float:
    metrics = _dict(fixture.get("pilot_metrics"))
    checks = [
        bool(metrics.get("artifacts_generated")),
        bool(metrics.get("per_monitor_fpr_tpr")),
        bool(metrics.get("per_episode_false_alarm_probability")),
        bool(metrics.get("time_to_detection")),
        bool(metrics.get("detection_delay")),
        bool(metrics.get("confidence_intervals")),
        bool(metrics.get("zero_false_positive_upper_bounds")),
        bool(metrics.get("underpowered_alpha_levels")),
        bool(metrics.get("hard_negative_false_positives")),
        bool(metrics.get("action_transcript_comparison")),
        bool(metrics.get("failed_baseline_runs_preserved")),
        bool(metrics.get("synthetic_pilot_label")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def low_fpr_overclaim_rejection(fixture: dict[str, object]) -> float:
    claims = _dict(fixture.get("claims"))
    overclaims = [
        bool(claims.get("alpha_001_overclaim")),
        bool(claims.get("deployment_validity_overclaim")),
        bool(claims.get("fake_result_present")),
        bool(claims.get("fake_citation_present")),
    ]
    if not any(overclaims):
        checks = [
            not bool(claims.get("alpha_001_claim_allowed_when_underpowered")),
            bool(claims.get("underpowered_alpha_warning")),
            bool(claims.get("synthetic_limitations_visible")),
        ]
        return round(sum(1 for item in checks if item) / len(checks), 3)
    checks = []
    if claims.get("alpha_001_overclaim"):
        checks.append(bool(claims.get("alpha_001_overclaim_blocked")))
    if claims.get("deployment_validity_overclaim"):
        checks.append(bool(claims.get("deployment_overclaim_blocked")))
    if claims.get("fake_result_present"):
        checks.append(bool(claims.get("fake_result_rejected")))
    if claims.get("fake_citation_present"):
        checks.append(bool(claims.get("fake_citation_rejected")))
    return round(sum(1 for item in checks if item) / len(checks), 3) if checks else 1.0


def related_work_attachment_quality(fixture: dict[str, object]) -> float:
    related = _dict(fixture.get("related_work"))
    checks = [
        bool(related.get("prior_work_recall_attached")),
        bool(related.get("related_work_matrix_attached")),
        len(_list(related.get("required_categories"))) >= 8,
        not bool(_list(related.get("missing_categories"))),
        bool(_list(related.get("closest_prior_work_ids"))),
        str(related.get("contribution_positioning")) == "benchmark/evaluation protocol",
        not bool(related.get("fake_citation_present")),
        bool(related.get("novelty_conservative")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def pilot_reviewer_quality(fixture: dict[str, object]) -> float:
    panel = _dict(fixture.get("pilot_reviewer_panel"))
    claims = _dict(fixture.get("claims"))
    roles = {str(item) for item in _list(panel.get("roles"))}
    fatal = _list(panel.get("fatal_blockers"))
    fixes = _list(panel.get("required_fixes"))
    checks = [
        bool(panel.get("generated")),
        {
            "benchmark validity reviewer",
            "statistics/low-FPR reviewer",
            "baseline reviewer",
            "related-work/novelty reviewer",
            "synthetic data validity reviewer",
            "area chair",
        }.issubset(roles),
        bool(fatal) or bool(fixes),
        bool(panel.get("underpowered_alpha_flagged")),
        bool(panel.get("synthetic_deployment_overclaim_flagged")) or not bool(claims.get("deployment_validity_overclaim")),
        bool(panel.get("weak_baseline_flagged")) or baseline_calibration_quality(fixture) >= 0.85,
        str(panel.get("publishability_assessment", "")).startswith(("not_publishable", "pilot_maturity")),
        not bool(panel.get("hides_blockers")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v22_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v22_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v22_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def main_power_decision_quality(fixture: dict[str, object]) -> float:
    power = _dict(fixture.get("main_power"))
    decision = _dict(power.get("alpha_001_decision"))
    required_counts = _dict(power.get("required_negative_counts"))
    planned_counts = _dict(power.get("planned_negative_counts"))
    required_001 = _int(required_counts.get("0.001"))
    planned_001 = _int(planned_counts.get("0.001"))
    decision_value = str(decision.get("decision", ""))
    checks = [
        bool(power.get("plan_exists")),
        "0.001" in {str(item) for item in _list(power.get("target_alpha_levels"))},
        str(power.get("primary_alpha")) in {"0.01", "0.001"},
        bool(_dict(power.get("required_positive_counts"))),
        required_001 > 0,
        bool(_dict(power.get("confidence_interval_targets"))),
        bool(_list(power.get("stopping_rules"))),
        bool(power.get("sequential_multiple_testing_adjustment")),
        bool(decision),
        decision_value in {"power", "downgrade", "drop", "defer"},
        bool(decision.get("reason")),
        bool(power.get("release_notes_state_alpha_decision")),
    ]
    if decision_value == "power":
        checks.append(planned_001 >= required_001 > 0)
    else:
        checks.append(bool(_list(decision.get("blockers"))) or bool(decision.get("reason")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def related_work_completion_quality(fixture: dict[str, object]) -> float:
    related = _dict(fixture.get("related_work_completion"))
    categories = _list(related.get("required_categories"))
    missing = _list(related.get("missing_categories"))
    statuses = _dict(related.get("category_statuses"))
    complete_statuses = [
        item
        for item in statuses.values()
        if isinstance(item, dict) and str(item.get("status")) == "complete" and bool(_list(item.get("real_paper_ids")))
    ]
    fallback_only = bool(related.get("fallback_only_counts_as_complete"))
    checks = [
        bool(related.get("status_exists")),
        len(categories) >= 8,
        _int(related.get("real_paper_count")) >= len(categories) - len(missing),
        len(complete_statuses) >= len(categories) - len(missing),
        _int(related.get("fallback_paper_count")) >= 0,
        not fallback_only,
        bool(related.get("next_searches_generated")) if missing else True,
        str(related.get("novelty_status")) in {"unknown", "sufficiently_covered", "duplicate"},
        not bool(related.get("missing_real_work_hidden")),
    ]
    if missing:
        checks.append(str(related.get("novelty_status")) == "unknown" or str(related.get("novelty_status")) == "duplicate")
        checks.append(bool(_list(related.get("blockers"))))
    else:
        checks.append(str(related.get("novelty_status")) in {"sufficiently_covered", "duplicate"})
        checks.append(not bool(_list(related.get("blockers"))) or str(related.get("novelty_status")) == "duplicate")
    return round(sum(1 for item in checks if item) / len(checks), 3)


def baseline_strength_quality(fixture: dict[str, object]) -> float:
    baseline = _dict(fixture.get("baseline_strength"))
    required = {str(item) for item in _list(baseline.get("required_baselines"))}
    implemented = {str(item) for item in _list(baseline.get("implemented_baselines"))}
    missing = required - implemented
    required_expected = {
        "sequential_change_point_detector",
        "calibrated_anomaly_detector",
        "permutation_null_distribution_detector",
        "conformal_score_threshold_detector",
        "action_only_transition_detector",
        "transcript_visible_semantic_heuristic_detector",
        "robust_lexical_substitution_monitor",
    }
    checks = [
        bool(baseline.get("assessment_exists")),
        required_expected.issubset(required),
        not bool(required - implemented) or bool(baseline.get("missing_required_baselines_block")),
        str(baseline.get("calibration_status")) in {"calibrated", "blocked_leakage", "incomplete"},
        not bool(baseline.get("calibration_leakage")) or bool(baseline.get("calibration_leakage_blocks")),
        bool(baseline.get("optional_llm_judge_reported_separately")),
        bool(baseline.get("optional_llm_judge_missing_blocks_ci")) is False,
        bool(baseline.get("strong_claim_allowed")) == (not missing and not bool(baseline.get("calibration_leakage"))),
        not bool(baseline.get("missing_baselines_hidden")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def main_result_analysis_quality(fixture: dict[str, object]) -> float:
    result = _dict(fixture.get("main_results"))
    run_type = str(result.get("run_type", ""))
    checks = [
        run_type in {"main", "pilot"},
        bool(result.get("manifest_exists")) or bool(result.get("pilot_only_decision")),
        bool(result.get("executed")) or bool(result.get("pilot_only_decision")),
        bool(result.get("metrics_json")) or run_type == "pilot",
        bool(result.get("predictions_json")) or run_type == "pilot",
        bool(result.get("baseline_comparison")) or run_type == "pilot",
        bool(result.get("error_analysis")) or run_type == "pilot",
        bool(result.get("low_fpr_report")),
        bool(result.get("powered_alpha_status_recorded")),
        bool(result.get("publication_claim_blocked_if_unpowered")),
        bool(result.get("synthetic_limitations_visible")),
        not bool(result.get("deployment_validity_claim")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def go_no_go_decision_quality(fixture: dict[str, object]) -> float:
    decision = _dict(fixture.get("go_no_go"))
    value = str(decision.get("decision", ""))
    blockers = _list(decision.get("blockers"))
    next_steps = _list(decision.get("required_next_steps"))
    checks = [
        bool(decision.get("exists")),
        value in {"go_publication_candidate", "revise_benchmark", "run_more_experiments", "no_go"},
        bool(decision.get("reason")),
        bool(_list(decision.get("evidence"))),
        str(decision.get("confidence")) in {"low", "medium", "high"},
        bool(next_steps) or value == "go_publication_candidate",
        not bool(decision.get("publication_candidate_with_fatal_blockers")),
        not bool(decision.get("hides_blockers")),
    ]
    if value == "go_publication_candidate":
        checks.append(not blockers)
    else:
        checks.append(bool(blockers) or bool(next_steps))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def publication_review_quality(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("publication_review"))
    readiness = str(review.get("readiness", ""))
    fatal = _list(review.get("fatal_blockers"))
    major = _list(review.get("major_blockers"))
    revisions = _list(review.get("required_revisions"))
    checks = [
        bool(review.get("exists")),
        readiness in {"not_ready", "workshop_candidate", "conference_candidate", "no_go"},
        str(review.get("confidence")) in {"low", "medium", "high"},
        bool(review.get("synthetic_deployment_overclaim_fatal")) or not _claims_deployment_overclaim(fixture),
        bool(review.get("underpowered_alpha_claim_fatal")) or not _claims_alpha_overclaim(fixture),
        bool(review.get("missing_real_related_work_major_or_fatal")) or related_work_completion_quality(fixture) >= 0.85,
        bool(review.get("missing_required_baseline_major_or_fatal")) or baseline_strength_quality(fixture) >= 0.85,
        bool(review.get("pilot_only_caveats")) or str(_dict(fixture.get("main_results")).get("run_type")) == "main",
        not bool(review.get("hides_blockers")),
    ]
    if readiness == "conference_candidate":
        checks.append(not fatal and not major and not revisions)
    elif readiness == "no_go":
        checks.append(bool(fatal))
    else:
        checks.append(bool(fatal) or bool(major) or bool(revisions) or readiness == "workshop_candidate")
    return round(sum(1 for item in checks if item) / len(checks), 3)


def manuscript_maturity_honesty(fixture: dict[str, object]) -> float:
    manuscript = _dict(fixture.get("manuscript"))
    status = str(manuscript.get("status", ""))
    maturity = str(manuscript.get("evidence_maturity", ""))
    run_type = str(_dict(fixture.get("main_results")).get("run_type", ""))
    blockers = _list(manuscript.get("unresolved_blockers"))
    checks = [
        bool(manuscript.get("package_exists")),
        status in {"pilot", "workshop_candidate", "publication_candidate", "revise_benchmark", "no_go", "not_ready"},
        maturity in {"pilot", "main"},
        bool(manuscript.get("artifact_package_included")),
        bool(manuscript.get("go_no_go_included")),
        bool(manuscript.get("reviewer_blockers_visible")),
        not bool(manuscript.get("deployment_validity_claim")),
        not bool(manuscript.get("alpha_001_claim")) or _alpha_001_powered_by_fixture(fixture),
        not bool(manuscript.get("publication_ready_with_fatal_blockers")),
    ]
    if run_type == "pilot":
        checks.append(maturity == "pilot" and status in {"pilot", "workshop_candidate", "not_ready"})
    elif status == "publication_candidate":
        checks.append(maturity == "main" and not blockers)
    else:
        checks.append(bool(blockers) or status in {"workshop_candidate", "no_go"})
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v23_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v23_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    computed_pass = _computed_v23_release_gate(fixture)
    if expected_pass:
        return 1.0 if computed_pass else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.7 * int(computed_pass is False)) + (0.3 * int(bool(expected_blockers))), 3)


def related_work_search_quality(fixture: dict[str, object]) -> float:
    search = _dict(fixture.get("related_work_search"))
    categories = _list(search.get("required_categories"))
    queries = _dict(search.get("queries_by_category"))
    rounds = _dicts(search.get("search_rounds"))
    completed = [item for item in rounds if str(item.get("status")) == "complete"]
    checks = [
        bool(search.get("campaign_exists")),
        len(categories) >= 8,
        all(_list(queries.get(str(category))) for category in categories),
        bool(_list(search.get("sources_used"))),
        len(rounds) >= len(categories),
        len(completed) >= len(categories) - len(_list(search.get("blocked_categories"))),
        not bool(search.get("network_required_for_fixture")),
        bool(search.get("fallback_preserved_separately", True)),
    ]
    if _list(search.get("blocked_categories")):
        checks.append(bool(_list(search.get("next_commands"))))
    else:
        checks.append(not _list(search.get("next_commands")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def category_curation_quality(fixture: dict[str, object]) -> float:
    curation = _dict(fixture.get("category_curation"))
    categories = _list(_dict(fixture.get("related_work_search")).get("required_categories"))
    statuses = _dict(curation.get("category_statuses"))
    missing = _list(curation.get("missing_categories"))
    complete = [
        item
        for item in statuses.values()
        if isinstance(item, dict) and str(item.get("status")) == "complete" and bool(_list(item.get("accepted_real_paper_ids")))
    ]
    checks = [
        bool(curation.get("report_exists")),
        len(statuses) >= len(categories) if categories else bool(statuses),
        len(complete) >= len(categories) - len(missing) if categories else bool(complete) or bool(missing),
        _int(curation.get("accepted_real_paper_count")) >= len(complete),
        bool(curation.get("fallback_papers_preserved_separately", True)),
        not bool(curation.get("fallback_only_counts_as_complete")),
        bool(curation.get("fake_citations_rejected", True)),
        not bool(curation.get("missing_categories_hidden")),
    ]
    if missing:
        checks.append(bool(_list(curation.get("blockers"))))
    else:
        checks.append(not bool(_list(curation.get("blockers"))))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def prior_work_dossier_quality(fixture: dict[str, object]) -> float:
    dossier = _dict(fixture.get("prior_work_dossier"))
    missing = _list(_dict(fixture.get("category_curation")).get("missing_categories"))
    dimensions = {str(item) for item in _list(dossier.get("comparison_dimensions"))}
    required_dimensions = {
        "problem setting",
        "low-FPR/specificity focus",
        "sequential evaluation",
        "multi-agent collusion/covert coordination",
        "benchmark/protocol contribution",
        "observability modes",
        "honest null distribution",
        "collusive alternatives",
        "baselines",
        "metrics/statistics",
    }
    novelty = str(dossier.get("novelty_status", ""))
    checks = [
        bool(dossier.get("exists")),
        bool(_list(dossier.get("closest_prior_work_ids"))) or bool(dossier.get("missing_closest_prior_work_allowed")),
        required_dimensions <= dimensions,
        bool(_list(dossier.get("comparison_table"))),
        bool(_list(dossier.get("what_is_new"))) or novelty in {"duplicate", "unknown"},
        bool(_list(dossier.get("what_is_not_new"))) or novelty in {"strong", "unknown"},
        bool(_list(dossier.get("decisive_difference_needed"))),
        novelty in {"duplicate", "weak", "plausible", "strong", "unknown"},
        not missing or novelty == "unknown",
        bool(dossier.get("counterevidence_preserved", True)),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def positioning_safety(fixture: dict[str, object]) -> float:
    positioning = _dict(fixture.get("positioning"))
    revised_claims = [str(item) for item in _list(positioning.get("revised_claims"))]
    text = " ".join(revised_claims).lower()
    overstrong = [" first ", "novel", "sota", "state-of-the-art", "deployment-valid"]
    checks = [
        bool(positioning.get("report_exists")),
        bool(revised_claims),
        bool(positioning.get("claim_softening_applied")),
        not any(term in f" {text} " for term in overstrong),
        bool(positioning.get("synthetic_limitations_included")),
        bool(positioning.get("deployment_claim_blocked")),
        bool(_list(positioning.get("closest_prior_work_citations"))),
        bool(_list(positioning.get("claims_to_avoid"))),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def selected_related_work_matrix_quality(fixture: dict[str, object]) -> float:
    matrix = _dict(fixture.get("related_work_matrix_v2"))
    curation = _dict(fixture.get("category_curation"))
    missing = set(str(item) for item in _list(curation.get("missing_categories")))
    matrix_missing = set(str(item) for item in _list(matrix.get("missing_categories")))
    entries = _dicts(matrix.get("entries"))
    checks = [
        bool(matrix.get("exists")),
        bool(entries) or bool(missing),
        bool(_dict(matrix.get("category_coverage"))),
        missing <= matrix_missing,
        bool(_list(matrix.get("must_cite_ids"))) or bool(missing),
        bool(matrix.get("reviewer_omission_risks_visible", True)),
        bool(matrix.get("directly_solving_triggers_no_go", True)),
        bool(matrix.get("baseline_sources_feed_plan", True)),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def publication_review_correctness(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("publication_review"))
    gate = _dict(fixture.get("v24_release_gate"))
    expected_decision = str(gate.get("expected_decision_status", ""))
    readiness = str(review.get("readiness", ""))
    missing = _list(_dict(fixture.get("category_curation")).get("missing_categories"))
    duplicate = str(_dict(fixture.get("prior_work_dossier")).get("novelty_status")) == "duplicate"
    deployment_overclaim = _claims_deployment_overclaim(fixture)
    checks = [
        bool(review.get("exists")),
        bool(review.get("after_related_work")),
        readiness in {"publication_candidate", "workshop_candidate", "revise_related_work", "revise_benchmark", "no_go"},
        readiness == expected_decision or (expected_decision == "revise_benchmark" and readiness == "revise_related_work"),
        not missing or readiness == "revise_related_work",
        not duplicate or readiness == "no_go",
        not deployment_overclaim or readiness == "revise_benchmark",
        bool(review.get("synthetic_limitations_checked", True)),
        bool(review.get("missing_related_work_blocks_publication", True)),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def manuscript_revision_honesty(fixture: dict[str, object]) -> float:
    revision = _dict(fixture.get("manuscript_revision"))
    missing = set(str(item) for item in _list(_dict(fixture.get("category_curation")).get("missing_categories")))
    revision_missing = set(str(item) for item in _list(revision.get("missing_categories")))
    review_passed = str(_dict(fixture.get("publication_review")).get("readiness")) == "publication_candidate"
    checks = [
        bool(revision.get("exists")),
        bool(revision.get("related_work_section_generated")),
        bool(revision.get("citations_resolve_to_known_papers")),
        missing <= revision_missing,
        bool(revision.get("softened_claims_included")),
        bool(revision.get("synthetic_limitations_preserved")),
        not bool(revision.get("deployment_validity_claim")),
        bool(revision.get("publication_ready")) is review_passed,
        bool(revision.get("must_cite_coverage_visible", True)),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v24_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v24_release_gate"))
    expected_pass = bool(expected.get("expected_pass"))
    expected_decision = str(expected.get("expected_decision_status", ""))
    computed_pass = _computed_v24_release_gate(fixture)
    computed_decision = _v24_decision_status(fixture)
    decision_ok = computed_decision == expected_decision
    if expected_pass:
        return 1.0 if computed_pass and decision_ok else 0.0
    expected_blockers = _list(expected.get("expected_blockers"))
    return round((0.55 * int(computed_pass is False)) + (0.25 * int(decision_ok)) + (0.2 * int(bool(expected_blockers))), 3)


def vetted_benchmark_fit_quality(fixture: dict[str, object]) -> float:
    benchmark = _dict(fixture.get("vetted_benchmark"))
    mapping = _dict(fixture.get("vetted_mapping"))
    eligibility = _dict(fixture.get("eligibility"))
    recommended = str(eligibility.get("recommended_use", mapping.get("recommended_experiment_role", "")))
    mapping_type = str(mapping.get("mapping_type", ""))
    no_fit = bool(mapping.get("no_fit_justification")) or mapping_type == "rejected" or recommended == "not_recommended"
    checks = [
        bool(benchmark.get("registry_record_exists")),
        bool(benchmark.get("license_visible")),
        bool(benchmark.get("terms_visible")),
        benchmark.get("download_required_explicit") is not None,
        benchmark.get("authentication_required_explicit") is not None,
        bool(eligibility.get("fit_assessed")),
        bool(mapping.get("unsupported_claims")),
        not bool(mapping.get("fit_assumed")),
    ]
    if no_fit:
        checks.extend(
            [
                bool(mapping.get("no_fit_justification")),
                recommended == "not_recommended",
                bool(mapping.get("synthetic_protocol_preserved")),
                not bool(mapping.get("pretends_validates_collusion")),
            ]
        )
    else:
        fit_score = _float(eligibility.get("fit_score"))
        checks.extend(
            [
                mapping_type in {"direct", "substrate", "auxiliary", "sanity_check", "analogy"},
                recommended in {"primary", "auxiliary", "sanity_check"},
                fit_score >= (0.75 if recommended == "primary" else 0.45),
                bool(mapping.get("supported_claims")),
                bool(mapping.get("required_adaptation")),
            ]
        )
    return round(sum(1 for item in checks if item) / len(checks), 3)


def adapter_transparency_score(fixture: dict[str, object]) -> float:
    adapter = _dict(fixture.get("adapter"))
    mapping = _dict(fixture.get("vetted_mapping"))
    if bool(adapter.get("not_required_due_to_no_fit")):
        checks = [
            bool(mapping.get("no_fit_justification")),
            bool(adapter.get("no_adapter_report_exists")),
            bool(adapter.get("synthetic_protocol_preserved")),
        ]
        return round(sum(1 for item in checks if item) / len(checks), 3)
    conversion_warning_expected = bool(adapter.get("conversion_destroys_meaning"))
    checks = [
        bool(adapter.get("created")),
        str(adapter.get("adapter_type"))
        in {"direct", "trace_conversion", "label_mapping", "metric_mapping", "monitor_wrapper", "auxiliary"},
        bool(adapter.get("input_schema")),
        bool(adapter.get("output_schema")),
        bool(adapter.get("transformation_recorded")),
        bool(adapter.get("preserves_original_labels")),
        bool(adapter.get("preserves_original_splits")),
        bool(adapter.get("limitations_visible")),
        not bool(adapter.get("calls_adapted_data_real_collusion_traces")),
    ]
    if conversion_warning_expected:
        checks.append(bool(adapter.get("meaning_loss_warning")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def venue_style_safety_score(fixture: dict[str, object]) -> float:
    style = _dict(fixture.get("venue_style"))
    checks = [
        bool(style.get("venue_profile_selected")),
        bool(style.get("style_corpus_allowed_or_synthetic")),
        bool(style.get("style_analysis_generated")),
        bool(style.get("rewrite_generated")),
        bool(style.get("structure_not_prose")),
        not bool(style.get("unsupported_claim_added")),
        bool(style.get("limitations_preserved")),
        bool(style.get("blocker_gates_binding")),
        not bool(style.get("copied_source_prose")),
    ]
    if bool(style.get("corpus_too_small")):
        checks.append(bool(style.get("too_small_warning")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def citation_plagiarism_safety(fixture: dict[str, object]) -> float:
    safety = _dict(fixture.get("safety"))
    copied = bool(safety.get("copied_prose_detected"))
    fake_citation = bool(safety.get("fake_citation_present"))
    fake_result = bool(safety.get("fake_result_present"))
    checks = [
        bool(safety.get("citation_checker_ran")),
        bool(safety.get("plagiarism_checker_ran")),
        bool(safety.get("result_claim_checker_ran")),
        not bool(safety.get("restricted_source_ingested")),
    ]
    if copied:
        checks.extend([bool(safety.get("copied_prose_blocked")), bool(safety.get("release_gate_blocked"))])
    else:
        checks.append(not bool(safety.get("copied_prose_blocked_required", False)))
    if fake_citation:
        checks.extend([bool(safety.get("fake_citation_blocked")), bool(safety.get("release_gate_blocked"))])
    else:
        checks.append(not bool(safety.get("fake_citation_accepted")))
    if fake_result:
        checks.extend([bool(safety.get("fake_result_blocked")), bool(safety.get("release_gate_blocked"))])
    else:
        checks.append(not bool(safety.get("fake_result_accepted")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def review_dataset_integrity(fixture: dict[str, object]) -> float:
    dataset = _dict(fixture.get("review_dataset"))
    checks = [
        bool(dataset.get("created")),
        _int(dataset.get("paper_count")) >= 1,
        _int(dataset.get("review_count")) >= 1,
        bool(dataset.get("scores_parsed")),
        bool(dataset.get("weaknesses_extracted")),
        bool(dataset.get("reviewer_ids_hashed")),
        not bool(dataset.get("private_data_stored")),
        bool(dataset.get("license_warnings_preserved")),
        bool(dataset.get("synthetic_fixture_only")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def review_taxonomy_quality(fixture: dict[str, object]) -> float:
    taxonomy = _dict(fixture.get("taxonomy"))
    issue_types = {str(item) for item in _list(taxonomy.get("issue_types"))}
    expected = {str(item) for item in _list(taxonomy.get("expected_issue_types"))}
    coverage = len(issue_types & expected) / len(expected) if expected else 1.0
    checks = [
        bool(taxonomy.get("labels_generated")),
        coverage >= 0.75,
        bool(taxonomy.get("severity_mapped")),
        bool(taxonomy.get("gate_mapping")),
        bool(taxonomy.get("auditable")),
        not bool(taxonomy.get("claims_ground_truth_without_human_verification")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def reviewer_calibration_score(fixture: dict[str, object]) -> float:
    calibration = _dict(fixture.get("reviewer_calibration"))
    checks = [
        bool(calibration.get("trained_or_calibrated")),
        bool(calibration.get("evaluation_report")),
        _float(calibration.get("issue_recall_proxy")) >= 0.6,
        _float(calibration.get("severity_calibration_score")) >= 0.6,
        _float(calibration.get("review_specificity_score")) >= 0.6,
        _float(calibration.get("evidence_linkage_score")) >= 0.7,
        _float(calibration.get("hallucination_rate")) <= 0.05,
        not bool(calibration.get("claims_human_equivalence")),
    ]
    if bool(calibration.get("small_training_data")):
        checks.append(bool(calibration.get("limitations_reported")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def drastic_review_quality(fixture: dict[str, object]) -> float:
    review = _dict(fixture.get("drastic_review"))
    roles = {str(item) for item in _list(review.get("roles"))}
    required_roles = {"novelty skeptic", "empirical rigor", "benchmark validity", "clarity", "reproducibility", "area chair"}
    fatal_expected = bool(review.get("fatal_expected"))
    checks = [
        bool(review.get("generated")),
        required_roles <= roles,
        bool(review.get("harsher_than_baseline")),
        bool(review.get("evidence_linked")),
        not bool(review.get("fake_citations")),
        not bool(review.get("invented_missing_results")),
        bool(review.get("likely_scores")),
        bool(review.get("borderline_decision_analysis")),
    ]
    if fatal_expected:
        checks.extend([bool(_list(review.get("fatal_flaws"))), str(review.get("likely_decision")) in {"reject", "revise"}])
    return round(sum(1 for item in checks if item) / len(checks), 3)


def revision_plan_actionability(fixture: dict[str, object]) -> float:
    revision = _dict(fixture.get("revision_plan"))
    checks = [
        bool(revision.get("generated")),
        bool(_list(revision.get("fatal_fixes"))) or not bool(revision.get("fatal_expected")),
        bool(_list(revision.get("major_fixes"))) or not bool(revision.get("major_expected")),
        bool(revision.get("new_experiment_requests_created")) or not bool(revision.get("new_experiments_required")),
        bool(revision.get("related_work_requests_created")) or not bool(revision.get("new_related_work_required")),
        bool(revision.get("claim_softening_generated")) or not bool(revision.get("claim_softening_required")),
        bool(revision.get("artifact_updates_created")) or not bool(revision.get("artifact_updates_required")),
        not bool(revision.get("fake_rebuttal_answers")),
        bool(revision.get("publication_status_downgraded_if_blocked")) or not bool(revision.get("fatal_blockers_remaining")),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 3)


def v25_release_gate_correctness(fixture: dict[str, object]) -> float:
    expected = _dict(fixture.get("v25_release_gate"))
    expected_status = str(expected.get("expected_outcome", ""))
    expected_pass = bool(expected.get("expected_pass"))
    computed_status = _v25_decision_status(fixture)
    computed_pass = computed_status in {"conference_candidate", "workshop_candidate", "benchmark_no_fit"}
    decision_ok = computed_status == expected_status
    safety = _dict(fixture.get("safety"))
    copied_or_fake = any(bool(safety.get(key)) for key in ["copied_prose_detected", "fake_citation_present", "fake_result_present"])
    blockers = _list(expected.get("expected_blockers"))
    checks = [
        bool(expected),
        decision_ok,
        computed_pass == expected_pass,
        not bool(_dict(fixture.get("venue_style")).get("copied_source_prose")),
        citation_plagiarism_safety(fixture) >= 0.9,
        bool(blockers) if not expected_pass else not blockers,
    ]
    if copied_or_fake:
        checks.append(bool(safety.get("release_gate_blocked")) and computed_status == "no_go")
    if computed_status == "revise_for_reviews":
        checks.append(bool(_list(_dict(fixture.get("drastic_review")).get("fatal_flaws"))))
    if computed_status == "benchmark_no_fit":
        checks.append(bool(_dict(fixture.get("vetted_mapping")).get("no_fit_justification")))
    return round(sum(1 for item in checks if item) / len(checks), 3)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9-]+", text.lower())


def _overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, object]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _v25_decision_status(fixture: dict[str, object]) -> str:
    safety = _dict(fixture.get("safety"))
    if bool(safety.get("copied_prose_detected")) or bool(safety.get("fake_citation_present")) or bool(safety.get("fake_result_present")):
        return "no_go"
    mapping = _dict(fixture.get("vetted_mapping"))
    adapter = _dict(fixture.get("adapter"))
    if bool(mapping.get("no_fit_justification")) and bool(adapter.get("not_required_due_to_no_fit")):
        return "benchmark_no_fit"
    review = _dict(fixture.get("drastic_review"))
    revision = _dict(fixture.get("revision_plan"))
    if _list(review.get("fatal_flaws")) and bool(revision.get("fatal_blockers_remaining")):
        return "revise_for_reviews"
    gate = _dict(fixture.get("v25_release_gate"))
    requested = str(gate.get("computed_outcome_hint", ""))
    if requested in {"conference_candidate", "workshop_candidate", "revise_for_reviews", "benchmark_no_fit", "no_go"}:
        return requested
    if str(review.get("likely_decision")) == "workshop":
        return "workshop_candidate"
    if all(
        [
            vetted_benchmark_fit_quality(fixture) >= 0.85,
            adapter_transparency_score(fixture) >= 0.85,
            venue_style_safety_score(fixture) >= 0.9,
            review_dataset_integrity(fixture) >= 0.85,
            review_taxonomy_quality(fixture) >= 0.85,
            reviewer_calibration_score(fixture) >= 0.85,
            drastic_review_quality(fixture) >= 0.85,
            revision_plan_actionability(fixture) >= 0.85,
        ]
    ):
        return "conference_candidate"
    return "revise_for_reviews"


def _computed_actual_run_gate(campaigns: list[dict[str, object]]) -> bool:
    accepted_real = [
        item
        for item in campaigns
        if item.get("accepted")
        and item.get("release_gate_eligible")
        and item.get("mode") in {"codex_task_pack", "codex_direct", "manual_handoff"}
        and item.get("attested")
        and item.get("validated_imports")
        and item.get("human_review_accepted")
    ]
    if len(accepted_real) < 3:
        return False
    return (
        any(item.get("experiment_ready") for item in accepted_real)
        and any(item.get("refusal") for item in accepted_real)
        and any(item.get("full_text") for item in accepted_real)
    )


def _computed_v6_release_gate(fixture: dict[str, object]) -> bool:
    executions = _dicts(_dict(fixture.get("execution")).get("executions"))
    successful_fixture = any(
        item.get("status") == "complete" and (item.get("run_type") == "smoke" or item.get("dataset_scope") == "fixture")
        for item in executions
    )
    failed = any(item.get("status") == "failed" for item in executions)
    parsed = bool(_dicts(_dict(fixture.get("result_summary")).get("metric_results")))
    claims = bool(_dicts(_dict(fixture.get("result_summary")).get("empirical_claims")))
    repro = bool(fixture.get("reproducibility"))
    review = bool(fixture.get("empirical_review"))
    package = _dict(fixture.get("paper_package"))
    fake_ok = fake_result_rejection(fixture) == 1.0
    failed_visible = (not failed) or bool(package.get("failed_results_visible"))
    return all(
        [
            successful_fixture,
            failed,
            parsed,
            claims,
            repro,
            review,
            bool(package.get("exported")),
            fake_ok,
            failed_visible,
        ]
    )


def _computed_v7_fixture_gate(fixture: dict[str, object]) -> bool:
    return all(
        [
            benchmark_execution_integrity(fixture) >= 0.85,
            benchmark_failure_path_preservation(fixture) >= 0.8,
            result_aggregation_quality(fixture) >= 0.75,
            error_analysis_quality(fixture) >= 0.75,
            benchmark_comparison_honesty(fixture) >= 0.85,
            replication_package_quality(fixture) >= 0.8,
            reproduction_verification_quality(fixture) >= 0.75,
            low_fpr_underpowered_warning_score(fixture) >= 0.85,
            not bool(_dict(fixture.get("fake_result")).get("accepted")),
        ]
    )


def _computed_v8_release_gate(fixture: dict[str, object]) -> bool:
    return all(
        [
            manuscript_traceability_score(fixture) >= 0.9,
            citation_validity_score(fixture) >= 0.9,
            result_claim_honesty_score(fixture) >= 0.9,
            venue_checklist_score(fixture) >= 0.85,
            artifact_eval_package_score(fixture) >= 0.85,
            reviewer_panel_quality(fixture) >= 0.8,
            rebuttal_actionability(fixture) >= 0.8,
            anonymization_safety(fixture) >= 0.9,
            submission_package_completeness(fixture) >= 0.9,
            not bool(_dict(fixture.get("traceability")).get("unsupported_claim_present")),
            not bool(_dict(fixture.get("traceability")).get("unsupported_claims_unblocked")),
            not bool(_dict(fixture.get("citations")).get("fake_citation_present")),
            not bool(_dict(fixture.get("results")).get("smoke_overclaim_present")),
            not bool(_dict(fixture.get("anonymization")).get("leak_expected")),
            not bool(_dict(fixture.get("rebuttal")).get("open_blockers_expected")),
            not bool(_dict(fixture.get("artifact_evaluation")).get("missing_expected")),
        ]
    )


def _computed_v21_release_gate(fixture: dict[str, object]) -> bool:
    selected = _dict(fixture.get("selected_idea"))
    workspace = _dict(fixture.get("workspace"))
    manuscript = _dict(fixture.get("manuscript"))
    claims = _dict(fixture.get("claims"))
    return all(
        [
            bool(selected.get("v2_release_gate_passes")),
            bool(selected.get("locked")),
            bool(selected.get("project_exists")),
            benchmark_spec_completeness(fixture) >= 0.9,
            threat_model_quality(fixture) >= 0.85,
            trace_generator_validity(fixture) >= 0.85,
            baseline_suite_completeness(fixture) >= 0.85,
            sequential_metric_correctness(fixture) >= 0.85,
            bool(workspace.get("exists")),
            bool(workspace.get("smoke_run_completed")),
            bool(workspace.get("result_artifacts_parsed")),
            not bool(claims.get("underpowered_smoke")) or bool(claims.get("underpowered_warning")),
            reviewer_blocker_quality(fixture) >= 0.8,
            bool(manuscript.get("generated")),
            bool(manuscript.get("paper_package_generated")),
            bool(manuscript.get("smoke_labeled")),
            bool(manuscript.get("limitations_prominent")),
            bool(manuscript.get("reviewer_blockers_included")),
            not bool(claims.get("fake_result_present")),
            not bool(claims.get("deployment_validity_overclaim")),
            not bool(claims.get("strong_low_fpr_claim_from_smoke")),
        ]
    )


def _computed_v22_release_gate(fixture: dict[str, object]) -> bool:
    selected = _dict(fixture.get("selected_idea"))
    run = _dict(fixture.get("pilot_run"))
    manuscript = _dict(fixture.get("pilot_manuscript"))
    claims = _dict(fixture.get("claims"))
    return all(
        [
            bool(selected.get("v21_release_gate_passes")),
            pilot_power_plan_quality(fixture) >= 0.85,
            honest_null_distribution_quality(fixture) >= 0.85,
            collusive_distribution_quality(fixture) >= 0.85,
            baseline_calibration_quality(fixture) >= 0.85,
            bool(run.get("manifest_exists")),
            bool(run.get("executed")),
            bool(run.get("result_artifacts_parsed")),
            pilot_metric_correctness(fixture) >= 0.85,
            related_work_attachment_quality(fixture) >= 0.85,
            pilot_reviewer_quality(fixture) >= 0.8,
            bool(manuscript.get("generated")),
            bool(manuscript.get("paper_package_generated")),
            bool(manuscript.get("pilot_labeled")),
            bool(manuscript.get("limitations_prominent")),
            bool(manuscript.get("reviewer_blockers_included")),
            not bool(claims.get("alpha_001_overclaim")),
            not bool(claims.get("deployment_validity_overclaim")),
            not bool(claims.get("fake_result_present")),
            not bool(claims.get("fake_citation_present")),
            not bool(claims.get("alpha_001_claim_allowed_when_underpowered")),
        ]
    )


def _computed_v23_release_gate(fixture: dict[str, object]) -> bool:
    expected = _dict(fixture.get("v23_release_gate"))
    decision = str(_dict(fixture.get("go_no_go")).get("decision", ""))
    readiness = str(_dict(fixture.get("publication_review")).get("readiness", ""))
    manuscript_status = str(_dict(fixture.get("manuscript")).get("status", ""))
    mature_decision = _v23_decision_status(decision, readiness, manuscript_status)
    publication_candidate = mature_decision == "publication_candidate"
    honest_terminal = mature_decision in {"publication_candidate", "workshop_candidate", "revise_benchmark", "no_go"}
    visible_related = not bool(_dict(fixture.get("related_work_completion")).get("missing_real_work_hidden"))
    visible_baselines = not bool(_dict(fixture.get("baseline_strength")).get("missing_baselines_hidden"))
    no_overclaims = not _claims_alpha_overclaim(fixture) and not _claims_deployment_overclaim(fixture)
    publication_ok = True
    if publication_candidate:
        publication_ok = all(
            [
                _alpha_001_powered_by_fixture(fixture),
                related_work_completion_quality(fixture) >= 0.85,
                baseline_strength_quality(fixture) >= 0.85,
                str(_dict(fixture.get("main_results")).get("run_type")) == "main",
                readiness == "conference_candidate",
                manuscript_status == "publication_candidate",
                not _list(_dict(fixture.get("publication_review")).get("fatal_blockers")),
                not _list(_dict(fixture.get("publication_review")).get("major_blockers")),
                not _list(_dict(fixture.get("manuscript")).get("unresolved_blockers")),
            ]
        )
    return all(
        [
            bool(expected.get("v22_release_gate_passes", True)),
            main_power_decision_quality(fixture) >= 0.85,
            bool(_dict(fixture.get("main_power")).get("alpha_001_decision")),
            bool(_dict(fixture.get("related_work_completion")).get("status_exists")),
            bool(_dict(fixture.get("baseline_strength")).get("assessment_exists")),
            bool(_dict(fixture.get("main_dataset")).get("dataset_exists"))
            or bool(_dict(fixture.get("main_dataset")).get("feasibility_report_exists")),
            bool(_dict(fixture.get("main_results")).get("executed")) or bool(_dict(fixture.get("main_results")).get("pilot_only_decision")),
            main_result_analysis_quality(fixture) >= 0.85,
            go_no_go_decision_quality(fixture) >= 0.85,
            publication_review_quality(fixture) >= 0.85,
            manuscript_maturity_honesty(fixture) >= 0.85,
            honest_terminal,
            no_overclaims,
            visible_related,
            visible_baselines,
            publication_ok,
        ]
    )


def _v23_decision_status(decision: str, readiness: str, manuscript_status: str) -> str:
    if decision == "no_go" or readiness == "no_go" or manuscript_status == "no_go":
        return "no_go"
    if decision == "go_publication_candidate" or readiness == "conference_candidate" or manuscript_status == "publication_candidate":
        return "publication_candidate"
    if readiness == "workshop_candidate" or manuscript_status == "workshop_candidate":
        return "workshop_candidate"
    if decision == "revise_benchmark":
        return "revise_benchmark"
    return "unknown"


def _computed_v24_release_gate(fixture: dict[str, object]) -> bool:
    decision = _v24_decision_status(fixture)
    curation = _dict(fixture.get("category_curation"))
    matrix = _dict(fixture.get("related_work_matrix_v2"))
    manuscript = _dict(fixture.get("manuscript_revision"))
    review = _dict(fixture.get("publication_review"))
    gate = _dict(fixture.get("v24_release_gate"))
    missing = set(str(item) for item in _list(curation.get("missing_categories")))
    matrix_missing = set(str(item) for item in _list(matrix.get("missing_categories")))
    manuscript_missing = set(str(item) for item in _list(manuscript.get("missing_categories")))
    fake_citations = _list(manuscript.get("fake_citation_ids"))
    publication_ready_claim = bool(manuscript.get("publication_ready"))
    publication_review_passed = str(review.get("readiness")) == "publication_candidate"
    novelty = str(_dict(fixture.get("prior_work_dossier")).get("novelty_status", ""))
    publication_candidate = decision == "publication_candidate"
    return all(
        [
            bool(gate.get("v23_release_gate_passes", True)),
            related_work_search_quality(fixture) >= 0.85,
            category_curation_quality(fixture) >= 0.85,
            bool(_dict(fixture.get("reading_pass")).get("report_exists")),
            prior_work_dossier_quality(fixture) >= 0.85,
            positioning_safety(fixture) >= 0.85,
            selected_related_work_matrix_quality(fixture) >= 0.85,
            publication_review_correctness(fixture) >= 0.85,
            manuscript_revision_honesty(fixture) >= 0.85,
            decision in {"publication_candidate", "workshop_candidate", "revise_related_work", "revise_benchmark", "no_go"},
            not missing,
            not fake_citations,
            bool(manuscript.get("citations_resolve_to_known_papers", True)),
            not bool(curation.get("missing_categories_hidden")),
            missing <= matrix_missing,
            missing <= manuscript_missing,
            not publication_ready_claim or publication_review_passed,
            not _claims_deployment_overclaim(fixture),
            not bool(manuscript.get("deployment_validity_claim")),
            not publication_candidate or (not missing and novelty not in {"duplicate", "unknown"}),
        ]
    )


def _v24_decision_status(fixture: dict[str, object]) -> str:
    readiness = str(_dict(fixture.get("publication_review")).get("readiness", ""))
    if readiness in {"publication_candidate", "workshop_candidate", "revise_related_work", "revise_benchmark", "no_go"}:
        return readiness
    if str(_dict(fixture.get("prior_work_dossier")).get("novelty_status")) == "duplicate":
        return "no_go"
    if _list(_dict(fixture.get("category_curation")).get("missing_categories")):
        return "revise_related_work"
    if _claims_deployment_overclaim(fixture):
        return "revise_benchmark"
    return "unknown"


def _claims_alpha_overclaim(fixture: dict[str, object]) -> bool:
    claims = _dict(fixture.get("claims"))
    return bool(claims.get("alpha_001_overclaim"))


def _claims_deployment_overclaim(fixture: dict[str, object]) -> bool:
    claims = _dict(fixture.get("claims"))
    return bool(claims.get("deployment_validity_overclaim"))


def _alpha_001_powered_by_fixture(fixture: dict[str, object]) -> bool:
    power = _dict(fixture.get("main_power"))
    decision = _dict(power.get("alpha_001_decision"))
    required = _int(_dict(power.get("required_negative_counts")).get("0.001"))
    planned = _int(_dict(power.get("planned_negative_counts")).get("0.001"))
    analysis = _dict(fixture.get("main_results"))
    powered_levels = {str(item) for item in _list(analysis.get("powered_alpha_levels"))}
    return str(decision.get("decision")) == "power" and planned >= required > 0 and "0.001" in powered_levels


def _computed_v1_readiness(fixture: dict[str, object]) -> bool:
    outcome = _dict(fixture.get("pilot_outcome"))
    return all(
        [
            str(outcome.get("outcome_type")) in {"defensible_direction", "correct_refusal"},
            bool(_dict(fixture.get("external_review")).get("exists")),
            bool(_dict(fixture.get("external_review")).get("accepted_outcome")),
            not bool(outcome.get("product_failures")),
            not bool(_dict(fixture.get("v1_readiness")).get("unresolved_product_failures")),
            bool(_dict(fixture.get("v1_readiness")).get("full_project_report_exists")),
            migration_audit_score(fixture) >= 0.8 and not bool(_dict(fixture.get("migration_audit")).get("expected_block")),
            cli_audit_score(fixture) >= 0.8,
            docs_audit_score(fixture) >= 0.8,
            artifact_hygiene_score(fixture) >= 0.8,
        ]
    )


def _computed_v9_release_gate(fixture: dict[str, object]) -> bool:
    expected = _dict(fixture.get("expected"))
    outcome = _dict(fixture.get("pilot_outcome"))
    gate = _dict(fixture.get("idea_gate"))
    review = _dict(fixture.get("external_review"))
    return all(
        [
            bool(_dict(fixture.get("v9_release_gate")).get("v8_passed_or_documented")),
            bool(_dict(fixture.get("v9_release_gate")).get("pilot_spec_exists")),
            bool(_dict(fixture.get("v9_release_gate")).get("pilot_run_exists")),
            bool(outcome.get("classified")),
            bool(review.get("exists")),
            bool(gate.get("ran")),
            bool(review.get("accepted_outcome")),
            str(outcome.get("outcome_type")) in {"defensible_direction", "correct_refusal"},
            str(outcome.get("outcome_type")) == str(expected.get("outcome_type")),
            not bool(outcome.get("product_failures")),
            bool(_dict(fixture.get("v1_readiness")).get("generated")),
            bool(_dict(fixture.get("migration_audit")).get("generated")),
            bool(_dict(fixture.get("cli_audit")).get("generated")),
            bool(_dict(fixture.get("docs_audit")).get("generated")),
            bool(_dict(fixture.get("artifact_hygiene")).get("generated")),
        ]
    )


def _computed_v2_idea_gate(fixture: dict[str, object], *, allow_agenda_only: bool) -> bool:
    expected = _dict(fixture.get("expected"))
    metrics = _dict(fixture.get("idea_yield_metrics"))
    tournament = _dict(fixture.get("tournament"))
    selected = str(tournament.get("selected_candidate_id", ""))
    candidates = {str(item.get("id")): item for item in _dicts(fixture.get("candidates"))}
    selected_candidate = candidates.get(selected, {})
    accepted_ids = {str(item.get("idea_id")) for item in _dicts(fixture.get("human_feedback")) if str(item.get("action")) == "accept"}
    core = all(
        [
            bool(fixture.get("topic_portfolio")),
            bool(candidates),
            bool(_dicts(fixture.get("mutations"))),
            bool(_dicts(fixture.get("constructive_gaps"))),
            bool(_dicts(fixture.get("transfers"))),
            bool(fixture.get("codex_task_ran") or fixture.get("codex_explicitly_unavailable")),
            bool(_dicts(fixture.get("novelty_assessments"))),
            bool(tournament.get("ran")),
            bool(_dicts(fixture.get("human_feedback")) or _dicts(fixture.get("human_reviews"))),
            bool(metrics),
            bool(fixture.get("rejected_ideas_preserved")),
        ]
    )
    no_bad_selected = True
    if selected_candidate:
        no_bad_selected = all(
            [
                not bool(_list(selected_candidate.get("unresolved_paper_ids"))),
                not bool(selected_candidate.get("fake_results_claimed")),
                str(selected_candidate.get("novelty_status")) != "likely_duplicate",
                str(selected_candidate.get("maturity")) != "rejected",
                not _generic_idea_title(str(selected_candidate.get("title", ""))),
            ]
        )
    accepted_pass = core and bool(accepted_ids) and bool(selected) and selected in accepted_ids and no_bad_selected
    agenda_pass = core and not accepted_ids and bool(_dict(fixture.get("agenda"))) and not selected and allow_agenda_only
    if bool(expected.get("must_fail_bad_idea")):
        return False
    return bool(accepted_pass or agenda_pass)


def _generic_idea_title(title: str) -> bool:
    normalized = " ".join(title.lower().split())
    return normalized in {"", "research idea", "new method", "better ai", "improve system"} or len(_tokens(normalized)) < 4
