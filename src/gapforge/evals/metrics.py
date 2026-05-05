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


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9-]+", text.lower())


def _overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
