"""Offline benchmark harness for research-gap quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gapforge.evals.fixtures import (
    V2_FIXTURE_NAMES,
    V3_FIXTURE_NAMES,
    V4_FIXTURE_NAMES,
    V5_FIXTURE_NAMES,
    V6_FIXTURE_NAMES,
    V7_FIXTURE_NAMES,
    V8_FIXTURE_NAMES,
    EvalFixture,
    load_fixtures,
    load_v3_fixtures,
    load_v4_fixtures,
    load_v5_fixtures,
    load_v6_fixtures,
    load_v7_fixtures,
    load_v8_fixtures,
)
from gapforge.evals.metrics import (
    EvalScores,
    RunMetrics,
    actual_run_gate_correctness,
    agent_output_validation_strictness,
    anonymization_safety,
    artifact_eval_package_score,
    benchmark_comparison_honesty,
    benchmark_execution_integrity,
    benchmark_failure_path_preservation,
    campaign_decision_quality,
    campaign_report_honesty,
    canonicalization_quality,
    citation_validity_score,
    contradiction_detection_score,
    direction_maturity_accuracy,
    direction_maturity_gate_accuracy_from_fixture,
    duplicate_detection_rate,
    empirical_claim_validity,
    empirical_review_quality,
    error_analysis_quality,
    evidence_linkage_score,
    evidence_span_precision_proxy,
    experiment_code_task_quality,
    experiment_completeness_score,
    experiment_execution_integrity,
    fake_result_rejection,
    full_text_coverage_score,
    gap_evidence_matrix_score,
    gap_specificity_score,
    human_review_respect_score,
    live_source_coverage_score,
    llm_output_grounding_score,
    low_fpr_underpowered_warning_score,
    manuscript_package_honesty,
    manuscript_traceability_score,
    novelty_dossier_completeness_score,
    novelty_gate_accuracy,
    novelty_research_loop_quality,
    paper_package_honesty,
    prior_work_recall_gate_score,
    prior_work_recall_proxy,
    protocol_completeness,
    quality_review_gate_correctness,
    real_literature_refusal_quality,
    rebuttal_actionability,
    related_work_matrix_quality,
    replication_package_quality,
    report_uncertainty_score,
    reproducibility_score,
    reproduction_verification_quality,
    research_direction_quality_proxy,
    result_aggregation_quality,
    result_artifact_grounding,
    result_claim_honesty_score,
    retrieval_relevance_at_k,
    review_queue_quality,
    reviewer_objection_quality_score,
    reviewer_panel_quality,
    rollback_safety,
    search_strategy_completeness,
    section_grounding_score,
    source_coverage_transparency_score,
    source_policy_compliance,
    statistical_caution_score,
    stop_reason_correctness,
    submission_package_completeness,
    unsupported_claim_rate,
    v5_release_gate_correctness,
    v6_release_gate_correctness,
    v7_release_gate_correctness,
    v8_release_gate_correctness,
    venue_checklist_score,
)
from gapforge.experiments.protocol import build_protocol_from_state
from gapforge.export.manuscript import render_expected_results
from gapforge.models import Claim, Evidence, ExperimentPlan, Gap, HumanReviewRecord, Provenance, ResearchRunState, ResearchTopic
from gapforge.skills.experiment_designer import ExperimentDesigner
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.skills.reviewer_simulation import ReviewerSimulation
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class BenchmarkResult:
    run_id: str
    metrics: RunMetrics
    passed: bool


@dataclass(slots=True)
class FixtureEvalResult:
    fixture_name: str
    topic: str
    scores: EvalScores
    unsupported_claims: list[str] = field(default_factory=list)
    accepted_gaps: list[str] = field(default_factory=list)
    rejected_gaps: list[str] = field(default_factory=list)
    novelty_gate_failures: list[str] = field(default_factory=list)
    missing_baselines: list[str] = field(default_factory=list)
    recommended_improvements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvalReport:
    results: list[FixtureEvalResult]
    v2: bool = False
    v3: bool = False
    v4: bool = False
    v5: bool = False
    v6: bool = False
    v7: bool = False
    v8: bool = False
    report_path: Path | None = None

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(result.scores.overall() for result in self.results) / len(self.results), 3)


def evaluate_run(state: ResearchRunState) -> BenchmarkResult:
    metrics = RunMetrics.from_state(state)
    return BenchmarkResult(run_id=state.run_id, metrics=metrics, passed=metrics.experiment_count > 0 and metrics.claim_count > 0)


def run_evals(
    *,
    fixture: str | None = None,
    fixture_root: Path | None = None,
    output_dir: Path | None = None,
    write_report: bool = True,
    v2: bool = False,
    v3: bool = False,
    v4: bool = False,
    v5: bool = False,
    v6: bool = False,
    v7: bool = False,
    v8: bool = False,
) -> EvalReport:
    selected = (
        [fixture]
        if fixture
        else (
            V8_FIXTURE_NAMES
            if v8
            else V7_FIXTURE_NAMES
            if v7
            else V6_FIXTURE_NAMES
            if v6
            else V5_FIXTURE_NAMES
            if v5
            else V4_FIXTURE_NAMES
            if v4
            else V3_FIXTURE_NAMES
            if v3
            else V2_FIXTURE_NAMES
            if v2
            else None
        )
    )
    if v8:
        fixtures = load_v8_fixtures(selected, fixture_root)
    elif v7:
        fixtures = load_v7_fixtures(selected, fixture_root)
    elif v6:
        fixtures = load_v6_fixtures(selected, fixture_root)
    elif v5:
        fixtures = load_v5_fixtures(selected, fixture_root)
    elif v4:
        fixtures = load_v4_fixtures(selected, fixture_root)
    elif v3:
        fixtures = load_v3_fixtures(selected, fixture_root)
    else:
        fixtures = load_fixtures(selected, fixture_root)
    results = [_evaluate_fixture(item) for item in fixtures]
    report = EvalReport(
        results=results,
        v2=v2 or any(item.is_v2 for item in fixtures),
        v3=v3 or any(item.is_v3 for item in fixtures),
        v4=v4 or any(item.is_v4 for item in fixtures),
        v5=v5 or any(item.is_v5 for item in fixtures),
        v6=v6 or any(item.is_v6 for item in fixtures),
        v7=v7 or any(item.is_v7 for item in fixtures),
        v8=v8 or any(item.is_v8 for item in fixtures),
    )
    if write_report:
        path = (output_dir or Path.cwd()) / "eval_report.md"
        path.write_text(render_eval_report(report), encoding="utf-8")
        report.report_path = path
    return report


def render_eval_report(report: EvalReport) -> str:
    lines = ["# GapForge Evaluation Report", "", f"Overall score: **{report.overall_score:.3f}**", ""]
    if report.v2:
        v2_scores = [score for result in report.results if (score := result.scores.v2_overall()) is not None]
        v2_overall = round(sum(v2_scores) / len(v2_scores), 3) if v2_scores else 0.0
        lines.extend([f"v0.2 overall score: **{v2_overall:.3f}**", ""])
    if report.v3:
        v3_scores = [score for result in report.results if (score := result.scores.v3_overall()) is not None]
        v3_overall = round(sum(v3_scores) / len(v3_scores), 3) if v3_scores else 0.0
        lines.extend([f"v0.3 overall score: **{v3_overall:.3f}**", ""])
    if report.v4:
        v4_scores = [score for result in report.results if (score := result.scores.v4_overall()) is not None]
        v4_overall = round(sum(v4_scores) / len(v4_scores), 3) if v4_scores else 0.0
        lines.extend([f"v0.4 overall score: **{v4_overall:.3f}**", ""])
    if report.v5:
        v5_scores = [score for result in report.results if (score := result.scores.v5_overall()) is not None]
        v5_overall = round(sum(v5_scores) / len(v5_scores), 3) if v5_scores else 0.0
        lines.extend([f"v0.5 overall score: **{v5_overall:.3f}**", ""])
    if report.v6:
        v6_scores = [score for result in report.results if (score := result.scores.v6_overall()) is not None]
        v6_overall = round(sum(v6_scores) / len(v6_scores), 3) if v6_scores else 0.0
        lines.extend([f"v0.6 overall score: **{v6_overall:.3f}**", ""])
    if report.v7:
        v7_scores = [score for result in report.results if (score := result.scores.v7_overall()) is not None]
        v7_overall = round(sum(v7_scores) / len(v7_scores), 3) if v7_scores else 0.0
        lines.extend([f"v0.7 overall score: **{v7_overall:.3f}**", ""])
    if report.v8:
        v8_scores = [score for result in report.results if (score := result.scores.v8_overall()) is not None]
        v8_overall = round(sum(v8_scores) / len(v8_scores), 3) if v8_scores else 0.0
        lines.extend([f"v0.8 overall score: **{v8_overall:.3f}**", ""])
    for result in report.results:
        scores = result.scores
        lines.extend(
            [
                f"## {result.fixture_name}",
                "",
                f"Topic: {result.topic}",
                "",
                "### v0.1 Scores",
                "",
                f"- gap_specificity_score: {scores.gap_specificity_score:.3f}",
                f"- evidence_linkage_score: {scores.evidence_linkage_score:.3f}",
                f"- novelty_gate_accuracy: {scores.novelty_gate_accuracy:.3f}",
                f"- duplicate_detection_rate: {scores.duplicate_detection_rate:.3f}",
                f"- unsupported_claim_rate: {scores.unsupported_claim_rate:.3f}",
                f"- experiment_completeness_score: {scores.experiment_completeness_score:.3f}",
                f"- reviewer_objection_quality_score: {scores.reviewer_objection_quality_score:.3f}",
                f"- fixture_overall: {scores.overall():.3f}",
                "",
            ]
        )
        if scores.v2_overall() is not None:
            lines.extend(
                [
                    "### v0.2 Scores",
                    "",
                    f"- full_text_coverage_score: {scores.full_text_coverage_score:.3f}",
                    f"- evidence_span_precision_proxy: {scores.evidence_span_precision_proxy:.3f}",
                    f"- section_grounding_score: {scores.section_grounding_score:.3f}",
                    f"- gap_evidence_matrix_score: {scores.gap_evidence_matrix_score:.3f}",
                    f"- novelty_dossier_completeness_score: {scores.novelty_dossier_completeness_score:.3f}",
                    f"- source_coverage_transparency_score: {scores.source_coverage_transparency_score:.3f}",
                    f"- human_review_respect_score: {scores.human_review_respect_score:.3f}",
                    f"- report_uncertainty_score: {scores.report_uncertainty_score:.3f}",
                    f"- fixture_v2_overall: {scores.v2_overall():.3f}",
                    "",
                ]
            )
        if scores.v3_overall() is not None:
            lines.extend(
                [
                    "### v0.3 Scores",
                    "",
                    f"- retrieval_relevance_at_k: {scores.retrieval_relevance_at_k:.3f}",
                    f"- prior_work_recall_proxy: {scores.prior_work_recall_proxy:.3f}",
                    f"- related_work_matrix_quality: {scores.related_work_matrix_quality:.3f}",
                    f"- direction_maturity_accuracy: {scores.direction_maturity_accuracy:.3f}",
                    f"- protocol_completeness: {scores.protocol_completeness:.3f}",
                    f"- manuscript_package_honesty: {scores.manuscript_package_honesty:.3f}",
                    f"- contradiction_detection_score: {scores.contradiction_detection_score:.3f}",
                    f"- source_policy_compliance: {scores.source_policy_compliance:.3f}",
                    f"- llm_output_grounding_score: {scores.llm_output_grounding_score:.3f}",
                    f"- fixture_v3_overall: {scores.v3_overall():.3f}",
                    "",
                ]
            )
        if scores.v4_overall() is not None:
            lines.extend(
                [
                    "### v0.4 Scores",
                    "",
                    f"- campaign_decision_quality: {scores.campaign_decision_quality:.3f}",
                    f"- stop_reason_correctness: {scores.stop_reason_correctness:.3f}",
                    f"- agent_output_validation_strictness: {scores.agent_output_validation_strictness:.3f}",
                    f"- actual_run_gate_correctness: {scores.actual_run_gate_correctness:.3f}",
                    f"- novelty_research_loop_quality: {scores.novelty_research_loop_quality:.3f}",
                    f"- direction_maturity_gate_accuracy: {scores.direction_maturity_gate_accuracy:.3f}",
                    f"- campaign_report_honesty: {scores.campaign_report_honesty:.3f}",
                    f"- review_queue_quality: {scores.review_queue_quality:.3f}",
                    f"- experiment_code_task_quality: {scores.experiment_code_task_quality:.3f}",
                    f"- rollback_safety: {scores.rollback_safety:.3f}",
                    f"- fixture_v4_overall: {scores.v4_overall():.3f}",
                    "",
                ]
            )
        if scores.v5_overall() is not None:
            lines.extend(
                [
                    "### v0.5 Scores",
                    "",
                    f"- live_source_coverage_score: {scores.live_source_coverage_score:.3f}",
                    f"- search_strategy_completeness: {scores.search_strategy_completeness:.3f}",
                    f"- prior_work_recall_gate_score: {scores.prior_work_recall_gate_score:.3f}",
                    f"- canonicalization_quality: {scores.canonicalization_quality:.3f}",
                    f"- real_literature_refusal_quality: {scores.real_literature_refusal_quality:.3f}",
                    f"- research_direction_quality_proxy: {scores.research_direction_quality_proxy:.3f}",
                    f"- quality_review_gate_correctness: {scores.quality_review_gate_correctness:.3f}",
                    f"- v5_release_gate_correctness: {scores.v5_release_gate_correctness:.3f}",
                    f"- fixture_v5_overall: {scores.v5_overall():.3f}",
                    "",
                ]
            )
        if scores.v6_overall() is not None:
            lines.extend(
                [
                    "### v0.6 Scores",
                    "",
                    f"- experiment_execution_integrity: {scores.experiment_execution_integrity:.3f}",
                    f"- result_artifact_grounding: {scores.result_artifact_grounding:.3f}",
                    f"- empirical_claim_validity: {scores.empirical_claim_validity:.3f}",
                    f"- statistical_caution_score: {scores.statistical_caution_score:.3f}",
                    f"- reproducibility_score: {scores.reproducibility_score:.3f}",
                    f"- empirical_review_quality: {scores.empirical_review_quality:.3f}",
                    f"- fake_result_rejection: {scores.fake_result_rejection:.3f}",
                    f"- paper_package_honesty: {scores.paper_package_honesty:.3f}",
                    f"- v6_release_gate_correctness: {scores.v6_release_gate_correctness:.3f}",
                    f"- fixture_v6_overall: {scores.v6_overall():.3f}",
                    "",
                ]
            )
        if scores.v7_overall() is not None:
            lines.extend(
                [
                    "### v0.7 Scores",
                    "",
                    f"- benchmark_execution_integrity: {scores.benchmark_execution_integrity:.3f}",
                    f"- benchmark_failure_path_preservation: {scores.benchmark_failure_path_preservation:.3f}",
                    f"- result_aggregation_quality: {scores.result_aggregation_quality:.3f}",
                    f"- error_analysis_quality: {scores.error_analysis_quality:.3f}",
                    f"- benchmark_comparison_honesty: {scores.benchmark_comparison_honesty:.3f}",
                    f"- replication_package_quality: {scores.replication_package_quality:.3f}",
                    f"- reproduction_verification_quality: {scores.reproduction_verification_quality:.3f}",
                    f"- low_fpr_underpowered_warning_score: {scores.low_fpr_underpowered_warning_score:.3f}",
                    f"- v7_release_gate_correctness: {scores.v7_release_gate_correctness:.3f}",
                    f"- fixture_v7_overall: {scores.v7_overall():.3f}",
                    "",
                ]
            )
        if scores.v8_overall() is not None:
            lines.extend(
                [
                    "### v0.8 Scores",
                    "",
                    f"- manuscript_traceability_score: {scores.manuscript_traceability_score:.3f}",
                    f"- citation_validity_score: {scores.citation_validity_score:.3f}",
                    f"- result_claim_honesty_score: {scores.result_claim_honesty_score:.3f}",
                    f"- venue_checklist_score: {scores.venue_checklist_score:.3f}",
                    f"- artifact_eval_package_score: {scores.artifact_eval_package_score:.3f}",
                    f"- reviewer_panel_quality: {scores.reviewer_panel_quality:.3f}",
                    f"- rebuttal_actionability: {scores.rebuttal_actionability:.3f}",
                    f"- anonymization_safety: {scores.anonymization_safety:.3f}",
                    f"- submission_package_completeness: {scores.submission_package_completeness:.3f}",
                    f"- v8_release_gate_correctness: {scores.v8_release_gate_correctness:.3f}",
                    f"- fixture_v8_overall: {scores.v8_overall():.3f}",
                    "",
                ]
            )
        failed_checks = _failed_checks(scores, result)
        lines.extend(["### Failed Checks And Suggested Improvements", ""])
        lines.extend(["| Check | Suggested improvement |", "| --- | --- |"])
        if failed_checks:
            lines.extend([f"| {check} | {suggestion} |" for check, suggestion in failed_checks])
        else:
            lines.append("| none | Maintain current eval quality; add harder fixtures. |")
        lines.append("")
        for title, values in [
            ("Unsupported Claims", result.unsupported_claims),
            ("Accepted Gaps", result.accepted_gaps),
            ("Rejected Gaps", result.rejected_gaps),
            ("Novelty Gate Failures", result.novelty_gate_failures),
            ("Missing Baselines", result.missing_baselines),
            ("Recommended Improvements", result.recommended_improvements),
        ]:
            lines.extend([f"### {title}", ""])
            lines.extend([f"- {value}" for value in values] or ["- none"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _evaluate_fixture(fixture: EvalFixture) -> FixtureEvalResult:
    state = _state_from_fixture(fixture)
    NoveltyGate().run(state)
    ExperimentDesigner().design(state)
    _inject_baseline_failure_if_needed(state)
    ReviewerSimulation().review(state)

    scores = EvalScores(
        gap_specificity_score=gap_specificity_score(state.gaps),
        evidence_linkage_score=evidence_linkage_score(state.gaps),
        novelty_gate_accuracy=novelty_gate_accuracy(state.novelty_assessments, fixture.duplicate_ideas, state.novelty_dossiers),
        duplicate_detection_rate=duplicate_detection_rate(state.novelty_assessments),
        unsupported_claim_rate=unsupported_claim_rate(state.claims, state),
        experiment_completeness_score=experiment_completeness_score(state.experiments, state.novelty_dossiers),
        reviewer_objection_quality_score=reviewer_objection_quality_score(state.reviewer_objections),
    )
    if fixture.is_v2:
        scores.full_text_coverage_score = full_text_coverage_score(state)
        scores.evidence_span_precision_proxy = evidence_span_precision_proxy(state)
        scores.section_grounding_score = section_grounding_score(state)
        scores.gap_evidence_matrix_score = gap_evidence_matrix_score(state.gaps, state.gap_evidence_matrices)
        scores.novelty_dossier_completeness_score = novelty_dossier_completeness_score(state.novelty_dossiers, fixture.duplicate_ideas)
        scores.source_coverage_transparency_score = source_coverage_transparency_score(state)
        scores.human_review_respect_score = human_review_respect_score(state)
        scores.report_uncertainty_score = report_uncertainty_score(state)
    if fixture.is_v3:
        _prepare_v3_state(state, fixture)
        gold_prior_ids = [str(item.get("paper_id", "")) for item in fixture.human_gold_prior_work if item.get("paper_id")]
        retrieved_ids = [paper.id for paper in state.papers]
        scores.retrieval_relevance_at_k = retrieval_relevance_at_k(retrieved_ids, gold_prior_ids, k=5)
        scores.prior_work_recall_proxy = prior_work_recall_proxy(state.novelty_dossiers, fixture.human_gold_prior_work)
        scores.related_work_matrix_quality = related_work_matrix_quality(
            state.related_work_matrices, fixture.human_gold_related_work_matrix
        )
        inferred_maturity = "candidate" if fixture.expected_not_ready_reasons else "experiment_ready"
        scores.direction_maturity_accuracy = direction_maturity_accuracy(inferred_maturity, fixture.expected_not_ready_reasons)
        scores.protocol_completeness = protocol_completeness(state.experiment_protocols)
        scores.manuscript_package_honesty = manuscript_package_honesty(
            [
                render_expected_results(
                    state.experiment_protocols[0] if state.experiment_protocols else None,
                    state.experiments[0] if state.experiments else None,
                )
            ]
        )
        scores.contradiction_detection_score = contradiction_detection_score([], [])
        scores.source_policy_compliance = source_policy_compliance(state, _required_sources_for_fixture(fixture))
        scores.llm_output_grounding_score = llm_output_grounding_score(
            [{"evidence_locators": [span.locator for span in state.evidence_spans[:1]]}],
            [span.locator for span in state.evidence_spans],
        )
    if fixture.is_v4:
        campaign_fixture = fixture.campaign_fixture
        scores.campaign_decision_quality = campaign_decision_quality(campaign_fixture)
        scores.stop_reason_correctness = stop_reason_correctness(campaign_fixture)
        scores.agent_output_validation_strictness = agent_output_validation_strictness(campaign_fixture)
        scores.actual_run_gate_correctness = actual_run_gate_correctness(campaign_fixture)
        scores.novelty_research_loop_quality = novelty_research_loop_quality(campaign_fixture)
        scores.direction_maturity_gate_accuracy = direction_maturity_gate_accuracy_from_fixture(campaign_fixture)
        scores.campaign_report_honesty = campaign_report_honesty(campaign_fixture)
        scores.review_queue_quality = review_queue_quality(campaign_fixture)
        scores.experiment_code_task_quality = experiment_code_task_quality(campaign_fixture)
        scores.rollback_safety = rollback_safety(campaign_fixture)
    if fixture.is_v5:
        real_fixture = fixture.real_literature_fixture
        scores.live_source_coverage_score = live_source_coverage_score(real_fixture)
        scores.search_strategy_completeness = search_strategy_completeness(real_fixture)
        scores.prior_work_recall_gate_score = prior_work_recall_gate_score(real_fixture)
        scores.canonicalization_quality = canonicalization_quality(real_fixture)
        scores.real_literature_refusal_quality = real_literature_refusal_quality(real_fixture)
        scores.research_direction_quality_proxy = research_direction_quality_proxy(real_fixture)
        scores.quality_review_gate_correctness = quality_review_gate_correctness(real_fixture)
        scores.v5_release_gate_correctness = v5_release_gate_correctness(real_fixture)
    if fixture.is_v6:
        experiment_fixture = fixture.experiment_fixture
        scores.experiment_execution_integrity = experiment_execution_integrity(experiment_fixture)
        scores.result_artifact_grounding = result_artifact_grounding(experiment_fixture)
        scores.empirical_claim_validity = empirical_claim_validity(experiment_fixture)
        scores.statistical_caution_score = statistical_caution_score(experiment_fixture)
        scores.reproducibility_score = reproducibility_score(experiment_fixture)
        scores.empirical_review_quality = empirical_review_quality(experiment_fixture)
        scores.fake_result_rejection = fake_result_rejection(experiment_fixture)
        scores.paper_package_honesty = paper_package_honesty(experiment_fixture)
        scores.v6_release_gate_correctness = v6_release_gate_correctness(experiment_fixture)
    if fixture.is_v7:
        benchmark_fixture = fixture.benchmark_fixture
        scores.benchmark_execution_integrity = benchmark_execution_integrity(benchmark_fixture)
        scores.benchmark_failure_path_preservation = benchmark_failure_path_preservation(benchmark_fixture)
        scores.result_aggregation_quality = result_aggregation_quality(benchmark_fixture)
        scores.error_analysis_quality = error_analysis_quality(benchmark_fixture)
        scores.benchmark_comparison_honesty = benchmark_comparison_honesty(benchmark_fixture)
        scores.replication_package_quality = replication_package_quality(benchmark_fixture)
        scores.reproduction_verification_quality = reproduction_verification_quality(benchmark_fixture)
        scores.low_fpr_underpowered_warning_score = low_fpr_underpowered_warning_score(benchmark_fixture)
        scores.v7_release_gate_correctness = v7_release_gate_correctness(benchmark_fixture)
    if fixture.is_v8:
        manuscript_fixture = fixture.manuscript_fixture
        scores.manuscript_traceability_score = manuscript_traceability_score(manuscript_fixture)
        scores.citation_validity_score = citation_validity_score(manuscript_fixture)
        scores.result_claim_honesty_score = result_claim_honesty_score(manuscript_fixture)
        scores.venue_checklist_score = venue_checklist_score(manuscript_fixture)
        scores.artifact_eval_package_score = artifact_eval_package_score(manuscript_fixture)
        scores.reviewer_panel_quality = reviewer_panel_quality(manuscript_fixture)
        scores.rebuttal_actionability = rebuttal_actionability(manuscript_fixture)
        scores.anonymization_safety = anonymization_safety(manuscript_fixture)
        scores.submission_package_completeness = submission_package_completeness(manuscript_fixture)
        scores.v8_release_gate_correctness = v8_release_gate_correctness(manuscript_fixture)
    unsupported = [
        claim.id
        for claim in state.claims
        if claim.status == "supported"
        and not claim.supporting_evidence
        or claim.type == "novelty"
        and not claim.closest_prior_work
        or claim.status == "unsupported"
    ]
    human_rejected_gap_ids = {
        review.object_id for review in state.human_reviews if review.object_type == "gap" and review.action == "reject"
    }
    accepted = [gap.id for gap in state.gaps if gap.novelty_status not in {"likely_not_new"} and gap.id not in human_rejected_gap_ids]
    rejected = [gap.id for gap in state.gaps if gap.novelty_status == "likely_not_new" or gap.id in human_rejected_gap_ids]
    novelty_failures = _novelty_failures(state, fixture)
    missing_baselines = [experiment.id for experiment in state.experiments if not experiment.baselines]
    return FixtureEvalResult(
        fixture_name=fixture.name,
        topic=fixture.topic,
        scores=scores,
        unsupported_claims=unsupported,
        accepted_gaps=accepted,
        rejected_gaps=rejected,
        novelty_gate_failures=novelty_failures,
        missing_baselines=missing_baselines,
        recommended_improvements=_recommended_improvements(scores, unsupported, novelty_failures, missing_baselines),
    )


def _state_from_fixture(fixture: EvalFixture) -> ResearchRunState:
    topic = ResearchTopic(text=fixture.topic, slug=fixture.name, created_at=utc_now_iso())
    state = ResearchRunState(
        run_id=f"eval-{fixture.name}",
        topic=topic,
        run_dir=str(fixture.path),
        papers=fixture.papers,
        paper_sections=fixture.paper_sections,
        evidence_spans=fixture.evidence_spans,
        paper_notes=fixture.paper_notes,
        gaps=[*fixture.known_good_gaps, *_duplicate_gaps(fixture), *fixture.known_bad_gaps],
        gap_evidence_matrices=fixture.expected_gap_evidence_matrix,
        novelty_dossiers=fixture.expected_novelty_dossiers,
        source_coverage=fixture.expected_source_coverage,
    )
    if fixture.is_v3:
        state.related_work_matrices = fixture.human_gold_related_work_matrix
        state.novelty_dossiers = [_dossier_from_gold_prior_work(fixture)]
    state.claims = [
        Claim(
            id=f"claim-supported-{fixture.name}",
            text=f"Fixture evidence supports topic-specific gaps for {fixture.topic}.",
            type="gap",
            status="supported",
            confidence="medium",
            supporting_evidence=[
                Evidence(
                    source_id=fixture.papers[0].id,
                    source_paper_id=fixture.papers[0].id,
                    quote=fixture.papers[0].abstract,
                    locator=fixture.papers[0].url,
                )
            ],
            source_paper_ids=[fixture.papers[0].id],
            created_by_skill="eval-fixture",
            needs_verification=False,
        ),
        Claim(
            id=f"claim-unsupported-{fixture.name}",
            text="Intentionally unsupported fixture claim for validation and eval accounting.",
            type="background",
            status="supported",
            confidence="high",
            created_by_skill="eval-fixture",
            needs_verification=False,
        ),
    ]
    if fixture.known_bad_gaps:
        state.human_reviews.append(
            HumanReviewRecord(
                id=f"review-reject-{fixture.known_bad_gaps[0].id}",
                object_type="gap",
                object_id=fixture.known_bad_gaps[0].id,
                action="reject",
                note="Synthetic eval fixture marks this gap as bad.",
                reviewer="eval-fixture",
                timestamp=utc_now_iso(),
                provenance=Provenance(
                    created_by_skill="eval-fixture",
                    source_ids=[fixture.known_bad_gaps[0].id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Synthetic human review control for evaluator scoring.",
                ),
            )
        )
    return state


def _prepare_v3_state(state: ResearchRunState, fixture: EvalFixture) -> None:
    if fixture.human_gold_related_work_matrix:
        state.related_work_matrices = fixture.human_gold_related_work_matrix
    if state.experiments:
        matrix = state.related_work_matrices[0] if state.related_work_matrices else None
        state.experiment_protocols = [build_protocol_from_state(state, state.experiments[0], direction_id=state.gaps[0].id, matrix=matrix)]


def _dossier_from_gold_prior_work(fixture: EvalFixture):
    from gapforge.models import NoveltyDossier

    top = [str(item.get("paper_id", "")) for item in fixture.human_gold_prior_work if item.get("paper_id")]
    return NoveltyDossier(
        target_id=fixture.known_good_gaps[0].id if fixture.known_good_gaps else fixture.name,
        idea_summary=f"Curated prior-work dossier for {fixture.topic}.",
        query_plan=[f"{fixture.topic} closest prior work"],
        candidates_considered=top,
        top_prior_work=top[:3],
        comparison_table=[{"paper_id": paper_id, "overall_similarity": 0.55} for paper_id in top],
        decisive_difference_needed="Use the curated annotations to state the measurable difference from prior work.",
        verdict="unknown" if fixture.expected_not_ready_reasons else "pursue",
        novelty_strength="unknown" if fixture.expected_not_ready_reasons else "medium",
        confidence="medium",
        recommended_action="Resolve curated not-ready reasons before manuscript export.",
    )


def _required_sources_for_fixture(fixture: EvalFixture) -> list[str]:
    if fixture.expected_source_coverage is None:
        return ["fixture-source"]
    return fixture.expected_source_coverage.searched_sources or ["fixture-source"]


def _duplicate_gaps(fixture: EvalFixture) -> list[Gap]:
    return [
        Gap(
            id=str(item["id"]),
            title=str(item["title"]),
            description=str(item["description"]),
            type="benchmark gap",
            supporting_paper_ids=[fixture.papers[0].id] if fixture.papers else [],
            why_existing_work_does_not_solve_it="This duplicate is intentionally present to test novelty rejection.",
            minimum_experiment_needed="Do not run; should be rejected as duplicate.",
            risk_that_gap_is_fake="It is intentionally a duplicate of fixture prior work.",
            confidence="medium",
        )
        for item in fixture.duplicate_ideas
    ]


def _inject_baseline_failure_if_needed(state: ResearchRunState) -> None:
    if not state.experiments:
        return
    weak = ExperimentPlan(
        id="experiment-missing-baseline-control",
        title="Intentional missing-baseline control",
        linked_gap_ids=[state.gaps[0].id] if state.gaps else [],
        hypothesis="This intentionally incomplete control checks reviewer scoring.",
        minimum_viable_experiment="Run without baselines to confirm review flags the issue.",
        metrics=["effect-size"],
        what_result_would_falsify_the_idea="Any baseline comparison would invalidate this control.",
        reviewer_killer_result="This should not be publishable.",
        novelty_assessment_id=state.gaps[0].id if state.gaps else "",
    )
    state.experiments.append(weak)


def _novelty_failures(state: ResearchRunState, fixture: EvalFixture) -> list[str]:
    failures = []
    for duplicate in fixture.duplicate_ideas:
        duplicate_id = str(duplicate["id"])
        matching = [item for item in state.novelty_assessments if item.target_gap_or_hypothesis_id == duplicate_id]
        if not matching or matching[0].verdict != duplicate.get("expected_verdict", "reject"):
            failures.append(duplicate_id)
    return failures


def _recommended_improvements(
    scores: EvalScores, unsupported: list[str], novelty_failures: list[str], missing_baselines: list[str]
) -> list[str]:
    improvements = []
    if scores.gap_specificity_score < 0.7:
        improvements.append("Make gaps more specific by naming mechanisms, settings, and measurable failure modes.")
    if scores.evidence_linkage_score < 0.9:
        improvements.append("Require every accepted gap to link papers/claims and fake-gap risk.")
    if novelty_failures:
        improvements.append("Tighten novelty gate duplicate detection against title and abstract overlap.")
    if unsupported:
        improvements.append("Prevent supported claims without evidence from entering the ledger.")
    if missing_baselines:
        improvements.append("Require closest-prior-work and simple baselines before experiment review.")
    if scores.reviewer_objection_quality_score < 0.7:
        improvements.append("Make reviewer objections more concrete with category, evidence, and fixes.")
    return improvements or ["Maintain current eval quality; add harder fixtures."]


def _failed_checks(scores: EvalScores, result: FixtureEvalResult) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = []
    thresholds = {
        "gap_specificity_score": 0.7,
        "evidence_linkage_score": 0.8,
        "novelty_gate_accuracy": 0.8,
        "duplicate_detection_rate": 0.8,
        "experiment_completeness_score": 0.75,
        "reviewer_objection_quality_score": 0.65,
        "full_text_coverage_score": 0.7,
        "evidence_span_precision_proxy": 0.8,
        "section_grounding_score": 0.7,
        "gap_evidence_matrix_score": 0.7,
        "novelty_dossier_completeness_score": 0.75,
        "source_coverage_transparency_score": 0.75,
        "human_review_respect_score": 1.0,
        "report_uncertainty_score": 0.3,
        "retrieval_relevance_at_k": 0.6,
        "prior_work_recall_proxy": 0.8,
        "related_work_matrix_quality": 0.7,
        "direction_maturity_accuracy": 0.8,
        "protocol_completeness": 0.7,
        "manuscript_package_honesty": 0.8,
        "contradiction_detection_score": 0.8,
        "source_policy_compliance": 0.8,
        "llm_output_grounding_score": 0.9,
        "campaign_decision_quality": 0.75,
        "stop_reason_correctness": 0.8,
        "agent_output_validation_strictness": 0.9,
        "actual_run_gate_correctness": 1.0,
        "novelty_research_loop_quality": 0.8,
        "direction_maturity_gate_accuracy": 0.9,
        "campaign_report_honesty": 0.85,
        "review_queue_quality": 0.8,
        "experiment_code_task_quality": 0.8,
        "rollback_safety": 0.9,
        "experiment_execution_integrity": 0.85,
        "result_artifact_grounding": 0.9,
        "empirical_claim_validity": 0.9,
        "statistical_caution_score": 0.85,
        "reproducibility_score": 0.8,
        "empirical_review_quality": 0.8,
        "fake_result_rejection": 1.0,
        "paper_package_honesty": 0.9,
        "v6_release_gate_correctness": 1.0,
        "benchmark_execution_integrity": 0.85,
        "benchmark_failure_path_preservation": 0.8,
        "result_aggregation_quality": 0.75,
        "error_analysis_quality": 0.75,
        "benchmark_comparison_honesty": 0.85,
        "replication_package_quality": 0.8,
        "reproduction_verification_quality": 0.75,
        "low_fpr_underpowered_warning_score": 0.85,
        "v7_release_gate_correctness": 1.0,
        "manuscript_traceability_score": 0.9,
        "citation_validity_score": 0.9,
        "result_claim_honesty_score": 0.9,
        "venue_checklist_score": 0.85,
        "artifact_eval_package_score": 0.85,
        "reviewer_panel_quality": 0.8,
        "rebuttal_actionability": 0.8,
        "anonymization_safety": 0.9,
        "submission_package_completeness": 0.9,
        "v8_release_gate_correctness": 1.0,
    }
    suggestions = {
        "full_text_coverage_score": "Parse more full text before evaluating research quality.",
        "evidence_span_precision_proxy": "Anchor evidence spans to quotes that appear in known sections.",
        "section_grounding_score": "Link full-text paper notes to section IDs and evidence locators.",
        "gap_evidence_matrix_score": "Require evidence rows and counterevidence accounting for every gap.",
        "novelty_dossier_completeness_score": "Add query plans, candidates, top prior work, and comparison tables to dossiers.",
        "source_coverage_transparency_score": "Record search queries, source failures, full-text coverage, and fallback warnings.",
        "human_review_respect_score": "Prevent rejected human-reviewed gaps from producing experiments.",
        "report_uncertainty_score": "Make uncertainty, missing searches, and fake-gap risks explicit.",
        "retrieval_relevance_at_k": "Improve hybrid retrieval so curated relevant prior work appears near the top.",
        "prior_work_recall_proxy": "Recover more human-gold closest prior work in novelty dossiers.",
        "related_work_matrix_quality": "Classify prior work relationships, must-cite papers, and baseline candidates more accurately.",
        "direction_maturity_accuracy": "Keep directions below experiment-ready when curated not-ready reasons remain.",
        "protocol_completeness": (
            "Generate protocols with datasets, baselines, metrics, statistics, reproducibility, and falsification details."
        ),
        "manuscript_package_honesty": "Label expected results as hypothetical and avoid presenting unrun experiments as findings.",
        "contradiction_detection_score": "Surface expected claim contradictions before manuscript or direction promotion.",
        "source_policy_compliance": "Satisfy required source policies or explicitly warn that coverage is insufficient.",
        "llm_output_grounding_score": "Require every model-produced claim to cite known evidence locators.",
        "campaign_decision_quality": "Record campaign decisions with evidence, reason, status, and expected next action.",
        "stop_reason_correctness": "Use explicit stop reasons and refuse recommendations when coverage or novelty is weak.",
        "agent_output_validation_strictness": "Reject fake citations, unsupported high-confidence claims, and unvalidated imports.",
        "actual_run_gate_correctness": "Keep fake-agent campaigns separate from accepted actual Codex/GPT-5.4 campaigns.",
        "novelty_research_loop_quality": "Iterate unknown novelty through recorded searches, retrieval rebuilds, and dossier refreshes.",
        "direction_maturity_gate_accuracy": "Require protocol, novelty dossier, and related-work matrix before experiment-ready maturity.",
        "campaign_report_honesty": "Show campaign mode, stop reason, uncertainty, and fake-vs-real status without overclaiming.",
        "review_queue_quality": "Create prioritized review items for unresolved risks and human acceptance gates.",
        "experiment_code_task_quality": (
            "Generate code tasks with required files, expected outputs, validation commands, and no fake results."
        ),
        "rollback_safety": "Create rollback snapshots and audit records before applying campaign imports.",
        "experiment_execution_integrity": "Record complete and failed execution paths with commands, logs, and expected outputs.",
        "result_artifact_grounding": "Require metric results to cite hashed result artifacts.",
        "empirical_claim_validity": "Generate empirical claims only from parsed metric result artifacts.",
        "statistical_caution_score": "Include confidence intervals, low-FPR warnings, and no overstated significance.",
        "reproducibility_score": "Run reproducibility checks covering datasets, baselines, metrics, manifests, logs, and hashes.",
        "empirical_review_quality": "Make empirical reviewers flag missing baselines, missing artifacts, fake results, and failed runs.",
        "fake_result_rejection": "Reject fixture/synthetic/generated results as real empirical acceptance.",
        "paper_package_honesty": "Label planned, smoke, pilot, failed, and hypothetical results explicitly.",
        "v6_release_gate_correctness": "Require executed artifacts, failed paths, reproducibility, review, and package honesty.",
        "benchmark_execution_integrity": (
            "Register benchmark records with linked datasets, baselines, metrics, and artifact-backed executions."
        ),
        "benchmark_failure_path_preservation": "Preserve failed benchmark jobs with logs and explicit failure reasons.",
        "result_aggregation_quality": "Build result tables and aggregates without mixing smoke, pilot, and main runs.",
        "error_analysis_quality": "Run artifact-backed error analysis and make missing predictions visible.",
        "benchmark_comparison_honesty": ("Generate benchmark comparisons that show missing baselines and avoid unsupported SOTA claims."),
        "replication_package_quality": "Export replication packages with manifests, commands, seeds, hashes, and safe data handling.",
        "reproduction_verification_quality": "Attempt replication verification and report environment-specific differences.",
        "low_fpr_underpowered_warning_score": ("Warn when low-FPR claims are underpowered and report upper confidence bounds."),
        "v7_release_gate_correctness": (
            "Require benchmark success/failure canaries, aggregation, error analysis, and replication evidence."
        ),
        "manuscript_traceability_score": "Block unsupported manuscript claims unless explicitly marked hypothesis/speculation.",
        "citation_validity_score": "Reject fake or unknown citation strings and tie citations to known paper records.",
        "result_claim_honesty_score": "Require result claims to cite artifacts and block smoke/pilot overclaims.",
        "venue_checklist_score": "Generate venue-aware checklists with explicit blockers.",
        "artifact_eval_package_score": (
            "Export artifact evaluation packages with replication, hashes, instructions, and safe data handling."
        ),
        "reviewer_panel_quality": "Run manuscript reviewers that cite sections/evidence and report fatal flaws.",
        "rebuttal_actionability": "Convert reviewer objections into evidence, experiment, search, citation, and softening tasks.",
        "anonymization_safety": "Detect identity leaks and block anonymous submissions when leaks remain.",
        "submission_package_completeness": "Export auditable submission packages with manuscript, assets, bibliography, and reports.",
        "v8_release_gate_correctness": "Require traceability, artifacts, review/rebuttal, and submission packages before v0.8 readiness.",
    }
    for name, threshold in thresholds.items():
        value = getattr(scores, name)
        if value is not None and value < threshold:
            checks.append((name, suggestions.get(name, "Improve this metric before treating the run as research-useful.")))
    if result.novelty_gate_failures:
        checks.append(("novelty_gate_failures", "Reject fixture duplicate ideas with closest-prior-work dossiers."))
    if result.missing_baselines:
        checks.append(("missing_baselines", "Require baselines for every generated experiment."))
    return checks
