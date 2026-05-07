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
