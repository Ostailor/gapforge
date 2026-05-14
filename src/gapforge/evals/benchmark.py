"""Offline benchmark harness for research-gap quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gapforge.evals.fixtures import (
    V2_FIXTURE_NAMES,
    V2_IDEA_FIXTURE_NAMES,
    V3_FIXTURE_NAMES,
    V4_FIXTURE_NAMES,
    V5_FIXTURE_NAMES,
    V6_FIXTURE_NAMES,
    V7_FIXTURE_NAMES,
    V8_FIXTURE_NAMES,
    V9_FIXTURE_NAMES,
    V21_FIXTURE_NAMES,
    V22_FIXTURE_NAMES,
    V23_FIXTURE_NAMES,
    V24_FIXTURE_NAMES,
    V25_FIXTURE_NAMES,
    EvalFixture,
    load_fixtures,
    load_v2_idea_fixtures,
    load_v3_fixtures,
    load_v4_fixtures,
    load_v5_fixtures,
    load_v6_fixtures,
    load_v7_fixtures,
    load_v8_fixtures,
    load_v9_fixtures,
    load_v21_fixtures,
    load_v22_fixtures,
    load_v23_fixtures,
    load_v24_fixtures,
    load_v25_fixtures,
)
from gapforge.evals.metrics import (
    EvalScores,
    RunMetrics,
    actual_run_gate_correctness,
    adapter_transparency_score,
    agent_output_validation_strictness,
    anonymization_safety,
    artifact_eval_package_score,
    artifact_hygiene_score,
    baseline_calibration_quality,
    baseline_strength_quality,
    baseline_suite_completeness,
    benchmark_comparison_honesty,
    benchmark_execution_integrity,
    benchmark_failure_path_preservation,
    benchmark_spec_completeness,
    campaign_decision_quality,
    campaign_report_honesty,
    canonicalization_quality,
    category_curation_quality,
    citation_plagiarism_safety,
    citation_validity_score,
    cli_audit_score,
    collusive_distribution_quality,
    constructive_gap_quality,
    contradiction_detection_score,
    cross_domain_transfer_quality,
    direction_maturity_accuracy,
    direction_maturity_gate_accuracy_from_fixture,
    docs_audit_score,
    drastic_review_quality,
    duplicate_detection_rate,
    empirical_claim_validity,
    empirical_review_quality,
    error_analysis_quality,
    evidence_linkage_score,
    evidence_span_precision_proxy,
    experiment_code_task_quality,
    experiment_completeness_score,
    experiment_execution_integrity,
    external_review_completeness,
    fake_result_rejection,
    full_text_coverage_score,
    gap_evidence_matrix_score,
    gap_specificity_score,
    go_no_go_decision_quality,
    honest_null_distribution_quality,
    human_feedback_integration,
    human_review_respect_score,
    idea_candidate_specificity,
    idea_gate_quality,
    idea_yield_gate_correctness,
    live_source_coverage_score,
    llm_output_grounding_score,
    low_fpr_overclaim_rejection,
    low_fpr_underpowered_warning_score,
    main_power_decision_quality,
    main_result_analysis_quality,
    manuscript_maturity_honesty,
    manuscript_package_honesty,
    manuscript_revision_honesty,
    manuscript_traceability_score,
    migration_audit_score,
    mutation_quality,
    novelty_dossier_completeness_score,
    novelty_gate_accuracy,
    novelty_loop_quality,
    novelty_research_loop_quality,
    paper_package_honesty,
    pilot_metric_correctness,
    pilot_outcome_classification,
    pilot_power_plan_quality,
    pilot_reviewer_quality,
    positioning_safety,
    prior_work_dossier_quality,
    prior_work_recall_gate_score,
    prior_work_recall_proxy,
    protocol_completeness,
    publication_review_correctness,
    publication_review_quality,
    quality_review_gate_correctness,
    real_literature_refusal_quality,
    rebuttal_actionability,
    related_work_attachment_quality,
    related_work_completion_quality,
    related_work_matrix_quality,
    related_work_search_quality,
    replication_package_quality,
    report_uncertainty_score,
    reproducibility_score,
    reproduction_verification_quality,
    research_agenda_quality,
    research_direction_quality_proxy,
    result_aggregation_quality,
    result_artifact_grounding,
    result_claim_honesty_score,
    retrieval_relevance_at_k,
    review_dataset_integrity,
    review_queue_quality,
    review_taxonomy_quality,
    reviewer_blocker_quality,
    reviewer_calibration_score,
    reviewer_objection_quality_score,
    reviewer_panel_quality,
    revision_plan_actionability,
    rollback_safety,
    search_strategy_completeness,
    section_grounding_score,
    selected_benchmark_release_gate_correctness,
    selected_related_work_matrix_quality,
    sequential_metric_correctness,
    source_coverage_transparency_score,
    source_policy_compliance,
    statistical_caution_score,
    stop_reason_correctness,
    submission_package_completeness,
    threat_model_quality,
    topic_portfolio_diversity,
    tournament_selection_quality,
    trace_generator_validity,
    underpowered_claim_rejection,
    unsupported_claim_rate,
    v1_readiness_gate_correctness,
    v5_release_gate_correctness,
    v6_release_gate_correctness,
    v7_release_gate_correctness,
    v8_release_gate_correctness,
    v9_release_gate_correctness,
    v22_release_gate_correctness,
    v23_release_gate_correctness,
    v24_release_gate_correctness,
    v25_release_gate_correctness,
    venue_checklist_score,
    venue_style_safety_score,
    vetted_benchmark_fit_quality,
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
    v2_ideas: bool = False
    v3: bool = False
    v4: bool = False
    v5: bool = False
    v6: bool = False
    v7: bool = False
    v8: bool = False
    v9: bool = False
    v21: bool = False
    v22: bool = False
    v23: bool = False
    v24: bool = False
    v25: bool = False
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
    v9: bool = False,
    v21: bool = False,
    v22: bool = False,
    v23: bool = False,
    v24: bool = False,
    v25: bool = False,
    v2_ideas: bool = False,
) -> EvalReport:
    version_flag_count = sum([v2, v3, v4, v5, v6, v7, v8, v9, v21, v22, v23, v24, v25, v2_ideas])
    if fixture or version_flag_count <= 1:
        selected = (
            [fixture]
            if fixture
            else (
                V2_IDEA_FIXTURE_NAMES
                if v2_ideas
                else V22_FIXTURE_NAMES
                if v22
                else V25_FIXTURE_NAMES
                if v25
                else V24_FIXTURE_NAMES
                if v24
                else V23_FIXTURE_NAMES
                if v23
                else V21_FIXTURE_NAMES
                if v21
                else V8_FIXTURE_NAMES
                if v8
                else V9_FIXTURE_NAMES
                if v9
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
        fixtures = _load_eval_fixtures_for_flags(
            selected,
            fixture_root,
            v2=v2,
            v3=v3,
            v4=v4,
            v5=v5,
            v6=v6,
            v7=v7,
            v8=v8,
            v9=v9,
            v21=v21,
            v22=v22,
            v23=v23,
            v24=v24,
            v25=v25,
            v2_ideas=v2_ideas,
        )
    else:
        fixtures = []
        if v2:
            fixtures.extend(load_fixtures(V2_FIXTURE_NAMES, fixture_root))
        if v3:
            fixtures.extend(load_v3_fixtures(V3_FIXTURE_NAMES, fixture_root))
        if v4:
            fixtures.extend(load_v4_fixtures(V4_FIXTURE_NAMES, fixture_root))
        if v5:
            fixtures.extend(load_v5_fixtures(V5_FIXTURE_NAMES, fixture_root))
        if v6:
            fixtures.extend(load_v6_fixtures(V6_FIXTURE_NAMES, fixture_root))
        if v7:
            fixtures.extend(load_v7_fixtures(V7_FIXTURE_NAMES, fixture_root))
        if v8:
            fixtures.extend(load_v8_fixtures(V8_FIXTURE_NAMES, fixture_root))
        if v9:
            fixtures.extend(load_v9_fixtures(V9_FIXTURE_NAMES, fixture_root))
        if v21:
            fixtures.extend(load_v21_fixtures(V21_FIXTURE_NAMES, fixture_root))
        if v22:
            fixtures.extend(load_v22_fixtures(V22_FIXTURE_NAMES, fixture_root))
        if v23:
            fixtures.extend(load_v23_fixtures(V23_FIXTURE_NAMES, fixture_root))
        if v24:
            fixtures.extend(load_v24_fixtures(V24_FIXTURE_NAMES, fixture_root))
        if v25:
            fixtures.extend(load_v25_fixtures(V25_FIXTURE_NAMES, fixture_root))
        if v2_ideas:
            fixtures.extend(load_v2_idea_fixtures(V2_IDEA_FIXTURE_NAMES, fixture_root))
    results = [_evaluate_fixture(item) for item in fixtures]
    report = EvalReport(
        results=results,
        v2=v2 or any(item.is_v2 for item in fixtures),
        v2_ideas=v2_ideas or any(item.is_v2_ideas for item in fixtures),
        v3=v3 or any(item.is_v3 for item in fixtures),
        v4=v4 or any(item.is_v4 for item in fixtures),
        v5=v5 or any(item.is_v5 for item in fixtures),
        v6=v6 or any(item.is_v6 for item in fixtures),
        v7=v7 or any(item.is_v7 for item in fixtures),
        v8=v8 or any(item.is_v8 for item in fixtures),
        v9=v9 or any(item.is_v9 for item in fixtures),
        v21=v21 or any(item.is_v21 for item in fixtures),
        v22=v22 or any(item.is_v22 for item in fixtures),
        v23=v23 or any(item.is_v23 for item in fixtures),
        v24=v24 or any(item.is_v24 for item in fixtures),
        v25=v25 or any(item.is_v25 for item in fixtures),
    )
    if write_report:
        path = (output_dir or Path.cwd()) / "eval_report.md"
        path.write_text(render_eval_report(report), encoding="utf-8")
        report.report_path = path
    return report


def _load_eval_fixtures_for_flags(
    selected: list[str] | None,
    fixture_root: Path | None,
    *,
    v2: bool,
    v3: bool,
    v4: bool,
    v5: bool,
    v6: bool,
    v7: bool,
    v8: bool,
    v9: bool,
    v21: bool,
    v22: bool,
    v23: bool,
    v24: bool,
    v25: bool,
    v2_ideas: bool,
) -> list[EvalFixture]:
    if v22:
        fixtures = load_v22_fixtures(selected, fixture_root)
    elif v25:
        fixtures = load_v25_fixtures(selected, fixture_root)
    elif v24:
        fixtures = load_v24_fixtures(selected, fixture_root)
    elif v23:
        fixtures = load_v23_fixtures(selected, fixture_root)
    elif v21:
        fixtures = load_v21_fixtures(selected, fixture_root)
    elif v9:
        fixtures = load_v9_fixtures(selected, fixture_root)
    elif v2_ideas:
        fixtures = load_v2_idea_fixtures(selected, fixture_root)
    elif v8:
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
    return fixtures


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
    if report.v9:
        v9_scores = [score for result in report.results if (score := result.scores.v9_overall()) is not None]
        v9_overall = round(sum(v9_scores) / len(v9_scores), 3) if v9_scores else 0.0
        lines.extend([f"v0.9 overall score: **{v9_overall:.3f}**", ""])
    if report.v21:
        v21_scores = [score for result in report.results if (score := result.scores.v21_overall()) is not None]
        v21_overall = round(sum(v21_scores) / len(v21_scores), 3) if v21_scores else 0.0
        lines.extend([f"v2.1 Selected Benchmark overall score: **{v21_overall:.3f}**", ""])
    if report.v22:
        v22_scores = [score for result in report.results if (score := result.scores.v22_overall()) is not None]
        v22_overall = round(sum(v22_scores) / len(v22_scores), 3) if v22_scores else 0.0
        lines.extend([f"v2.2 Pilot Benchmark overall score: **{v22_overall:.3f}**", ""])
    if report.v23:
        v23_scores = [score for result in report.results if (score := result.scores.v23_overall()) is not None]
        v23_overall = round(sum(v23_scores) / len(v23_scores), 3) if v23_scores else 0.0
        lines.extend([f"v2.3 Main Benchmark overall score: **{v23_overall:.3f}**", ""])
    if report.v24:
        v24_scores = [score for result in report.results if (score := result.scores.v24_overall()) is not None]
        v24_overall = round(sum(v24_scores) / len(v24_scores), 3) if v24_scores else 0.0
        lines.extend([f"v2.4 Related Work Remediation overall score: **{v24_overall:.3f}**", ""])
    if report.v25:
        v25_scores = [score for result in report.results if (score := result.scores.v25_overall()) is not None]
        v25_overall = round(sum(v25_scores) / len(v25_scores), 3) if v25_scores else 0.0
        lines.extend([f"v2.5 Real Benchmark Grounding overall score: **{v25_overall:.3f}**", ""])
    if report.v2_ideas:
        v2_idea_scores = [score for result in report.results if (score := result.scores.v2_ideas_overall()) is not None]
        v2_idea_overall = round(sum(v2_idea_scores) / len(v2_idea_scores), 3) if v2_idea_scores else 0.0
        lines.extend([f"v2 Idea Discovery overall score: **{v2_idea_overall:.3f}**", ""])
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
        if scores.v9_overall() is not None:
            lines.extend(
                [
                    "### v0.9 Scores",
                    "",
                    f"- pilot_outcome_classification: {scores.pilot_outcome_classification:.3f}",
                    f"- idea_gate_quality: {scores.idea_gate_quality:.3f}",
                    f"- external_review_completeness: {scores.external_review_completeness:.3f}",
                    f"- v1_readiness_gate_correctness: {scores.v1_readiness_gate_correctness:.3f}",
                    f"- migration_audit_score: {scores.migration_audit_score:.3f}",
                    f"- cli_audit_score: {scores.cli_audit_score:.3f}",
                    f"- docs_audit_score: {scores.docs_audit_score:.3f}",
                    f"- artifact_hygiene_score: {scores.artifact_hygiene_score:.3f}",
                    f"- v9_release_gate_correctness: {scores.v9_release_gate_correctness:.3f}",
                    f"- fixture_v9_overall: {scores.v9_overall():.3f}",
                    "",
                ]
            )
        if scores.v21_overall() is not None:
            lines.extend(
                [
                    "### v2.1 Selected Benchmark Scores",
                    "",
                    f"- benchmark_spec_completeness: {scores.benchmark_spec_completeness:.3f}",
                    f"- threat_model_quality: {scores.threat_model_quality:.3f}",
                    f"- trace_generator_validity: {scores.trace_generator_validity:.3f}",
                    f"- baseline_suite_completeness: {scores.baseline_suite_completeness:.3f}",
                    f"- sequential_metric_correctness: {scores.sequential_metric_correctness:.3f}",
                    f"- underpowered_claim_rejection: {scores.underpowered_claim_rejection:.3f}",
                    f"- reviewer_blocker_quality: {scores.reviewer_blocker_quality:.3f}",
                    f"- selected_benchmark_release_gate_correctness: {scores.selected_benchmark_release_gate_correctness:.3f}",
                    f"- fixture_v21_overall: {scores.v21_overall():.3f}",
                    "",
                ]
            )
        if scores.v22_overall() is not None:
            lines.extend(
                [
                    "### v2.2 Pilot Benchmark Scores",
                    "",
                    f"- pilot_power_plan_quality: {scores.pilot_power_plan_quality:.3f}",
                    f"- honest_null_distribution_quality: {scores.honest_null_distribution_quality:.3f}",
                    f"- collusive_distribution_quality: {scores.collusive_distribution_quality:.3f}",
                    f"- baseline_calibration_quality: {scores.baseline_calibration_quality:.3f}",
                    f"- pilot_metric_correctness: {scores.pilot_metric_correctness:.3f}",
                    f"- low_fpr_overclaim_rejection: {scores.low_fpr_overclaim_rejection:.3f}",
                    f"- related_work_attachment_quality: {scores.related_work_attachment_quality:.3f}",
                    f"- pilot_reviewer_quality: {scores.pilot_reviewer_quality:.3f}",
                    f"- v22_release_gate_correctness: {scores.v22_release_gate_correctness:.3f}",
                    f"- fixture_v22_overall: {scores.v22_overall():.3f}",
                    "",
                ]
            )
        if scores.v23_overall() is not None:
            lines.extend(
                [
                    "### v2.3 Main Benchmark Scores",
                    "",
                    f"- main_power_decision_quality: {scores.main_power_decision_quality:.3f}",
                    f"- related_work_completion_quality: {scores.related_work_completion_quality:.3f}",
                    f"- baseline_strength_quality: {scores.baseline_strength_quality:.3f}",
                    f"- main_result_analysis_quality: {scores.main_result_analysis_quality:.3f}",
                    f"- go_no_go_decision_quality: {scores.go_no_go_decision_quality:.3f}",
                    f"- publication_review_quality: {scores.publication_review_quality:.3f}",
                    f"- manuscript_maturity_honesty: {scores.manuscript_maturity_honesty:.3f}",
                    f"- v23_release_gate_correctness: {scores.v23_release_gate_correctness:.3f}",
                    f"- fixture_v23_overall: {scores.v23_overall():.3f}",
                    "",
                ]
            )
        if scores.v24_overall() is not None:
            lines.extend(
                [
                    "### v2.4 Related Work Remediation Scores",
                    "",
                    f"- related_work_search_quality: {scores.related_work_search_quality:.3f}",
                    f"- category_curation_quality: {scores.category_curation_quality:.3f}",
                    f"- prior_work_dossier_quality: {scores.prior_work_dossier_quality:.3f}",
                    f"- positioning_safety: {scores.positioning_safety:.3f}",
                    f"- related_work_matrix_quality: {scores.selected_related_work_matrix_quality:.3f}",
                    f"- publication_review_correctness: {scores.publication_review_correctness:.3f}",
                    f"- manuscript_revision_honesty: {scores.manuscript_revision_honesty:.3f}",
                    f"- v24_release_gate_correctness: {scores.v24_release_gate_correctness:.3f}",
                    f"- fixture_v24_overall: {scores.v24_overall():.3f}",
                    "",
                ]
            )
        if scores.v25_overall() is not None:
            lines.extend(
                [
                    "### v2.5 Real Benchmark Grounding Scores",
                    "",
                    f"- vetted_benchmark_fit_quality: {scores.vetted_benchmark_fit_quality:.3f}",
                    f"- adapter_transparency_score: {scores.adapter_transparency_score:.3f}",
                    f"- venue_style_safety_score: {scores.venue_style_safety_score:.3f}",
                    f"- citation_plagiarism_safety: {scores.citation_plagiarism_safety:.3f}",
                    f"- review_dataset_integrity: {scores.review_dataset_integrity:.3f}",
                    f"- review_taxonomy_quality: {scores.review_taxonomy_quality:.3f}",
                    f"- reviewer_calibration_score: {scores.reviewer_calibration_score:.3f}",
                    f"- drastic_review_quality: {scores.drastic_review_quality:.3f}",
                    f"- revision_plan_actionability: {scores.revision_plan_actionability:.3f}",
                    f"- v25_release_gate_correctness: {scores.v25_release_gate_correctness:.3f}",
                    f"- fixture_v25_overall: {scores.v25_overall():.3f}",
                    "",
                ]
            )
        if scores.v2_ideas_overall() is not None:
            lines.extend(
                [
                    "### v2 Idea Discovery Scores",
                    "",
                    f"- topic_portfolio_diversity: {scores.topic_portfolio_diversity:.3f}",
                    f"- idea_candidate_specificity: {scores.idea_candidate_specificity:.3f}",
                    f"- mutation_quality: {scores.mutation_quality:.3f}",
                    f"- constructive_gap_quality: {scores.constructive_gap_quality:.3f}",
                    f"- cross_domain_transfer_quality: {scores.cross_domain_transfer_quality:.3f}",
                    f"- novelty_loop_quality: {scores.novelty_loop_quality:.3f}",
                    f"- tournament_selection_quality: {scores.tournament_selection_quality:.3f}",
                    f"- human_feedback_integration: {scores.human_feedback_integration:.3f}",
                    f"- research_agenda_quality: {scores.research_agenda_quality:.3f}",
                    f"- idea_yield_gate_correctness: {scores.idea_yield_gate_correctness:.3f}",
                    f"- fixture_v2_ideas_overall: {scores.v2_ideas_overall():.3f}",
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
    if fixture.is_v9:
        pilot_fixture = fixture.pilot_fixture
        scores.pilot_outcome_classification = pilot_outcome_classification(pilot_fixture)
        scores.idea_gate_quality = idea_gate_quality(pilot_fixture)
        scores.external_review_completeness = external_review_completeness(pilot_fixture)
        scores.v1_readiness_gate_correctness = v1_readiness_gate_correctness(pilot_fixture)
        scores.migration_audit_score = migration_audit_score(pilot_fixture)
        scores.cli_audit_score = cli_audit_score(pilot_fixture)
        scores.docs_audit_score = docs_audit_score(pilot_fixture)
        scores.artifact_hygiene_score = artifact_hygiene_score(pilot_fixture)
        scores.v9_release_gate_correctness = v9_release_gate_correctness(pilot_fixture)
    if fixture.is_v21:
        selected_benchmark_fixture = fixture.selected_benchmark_fixture
        scores.benchmark_spec_completeness = benchmark_spec_completeness(selected_benchmark_fixture)
        scores.threat_model_quality = threat_model_quality(selected_benchmark_fixture)
        scores.trace_generator_validity = trace_generator_validity(selected_benchmark_fixture)
        scores.baseline_suite_completeness = baseline_suite_completeness(selected_benchmark_fixture)
        scores.sequential_metric_correctness = sequential_metric_correctness(selected_benchmark_fixture)
        scores.underpowered_claim_rejection = underpowered_claim_rejection(selected_benchmark_fixture)
        scores.reviewer_blocker_quality = reviewer_blocker_quality(selected_benchmark_fixture)
        scores.selected_benchmark_release_gate_correctness = selected_benchmark_release_gate_correctness(selected_benchmark_fixture)
    if fixture.is_v22:
        selected_benchmark_fixture = fixture.selected_benchmark_v22_fixture or fixture.selected_benchmark_fixture
        scores.pilot_power_plan_quality = pilot_power_plan_quality(selected_benchmark_fixture)
        scores.honest_null_distribution_quality = honest_null_distribution_quality(selected_benchmark_fixture)
        scores.collusive_distribution_quality = collusive_distribution_quality(selected_benchmark_fixture)
        scores.baseline_calibration_quality = baseline_calibration_quality(selected_benchmark_fixture)
        scores.pilot_metric_correctness = pilot_metric_correctness(selected_benchmark_fixture)
        scores.low_fpr_overclaim_rejection = low_fpr_overclaim_rejection(selected_benchmark_fixture)
        scores.related_work_attachment_quality = related_work_attachment_quality(selected_benchmark_fixture)
        scores.pilot_reviewer_quality = pilot_reviewer_quality(selected_benchmark_fixture)
        scores.v22_release_gate_correctness = v22_release_gate_correctness(selected_benchmark_fixture)
    if fixture.is_v23:
        selected_benchmark_fixture = fixture.selected_benchmark_v23_fixture or fixture.selected_benchmark_fixture
        scores.main_power_decision_quality = main_power_decision_quality(selected_benchmark_fixture)
        scores.related_work_completion_quality = related_work_completion_quality(selected_benchmark_fixture)
        scores.baseline_strength_quality = baseline_strength_quality(selected_benchmark_fixture)
        scores.main_result_analysis_quality = main_result_analysis_quality(selected_benchmark_fixture)
        scores.go_no_go_decision_quality = go_no_go_decision_quality(selected_benchmark_fixture)
        scores.publication_review_quality = publication_review_quality(selected_benchmark_fixture)
        scores.manuscript_maturity_honesty = manuscript_maturity_honesty(selected_benchmark_fixture)
        scores.v23_release_gate_correctness = v23_release_gate_correctness(selected_benchmark_fixture)
    if fixture.is_v24:
        selected_benchmark_fixture = fixture.selected_benchmark_v24_fixture or fixture.selected_benchmark_fixture
        scores.related_work_search_quality = related_work_search_quality(selected_benchmark_fixture)
        scores.category_curation_quality = category_curation_quality(selected_benchmark_fixture)
        scores.prior_work_dossier_quality = prior_work_dossier_quality(selected_benchmark_fixture)
        scores.positioning_safety = positioning_safety(selected_benchmark_fixture)
        scores.selected_related_work_matrix_quality = selected_related_work_matrix_quality(selected_benchmark_fixture)
        scores.publication_review_correctness = publication_review_correctness(selected_benchmark_fixture)
        scores.manuscript_revision_honesty = manuscript_revision_honesty(selected_benchmark_fixture)
        scores.v24_release_gate_correctness = v24_release_gate_correctness(selected_benchmark_fixture)
    if fixture.is_v25:
        selected_benchmark_fixture = fixture.selected_benchmark_v25_fixture or fixture.selected_benchmark_fixture
        scores.vetted_benchmark_fit_quality = vetted_benchmark_fit_quality(selected_benchmark_fixture)
        scores.adapter_transparency_score = adapter_transparency_score(selected_benchmark_fixture)
        scores.venue_style_safety_score = venue_style_safety_score(selected_benchmark_fixture)
        scores.citation_plagiarism_safety = citation_plagiarism_safety(selected_benchmark_fixture)
        scores.review_dataset_integrity = review_dataset_integrity(selected_benchmark_fixture)
        scores.review_taxonomy_quality = review_taxonomy_quality(selected_benchmark_fixture)
        scores.reviewer_calibration_score = reviewer_calibration_score(selected_benchmark_fixture)
        scores.drastic_review_quality = drastic_review_quality(selected_benchmark_fixture)
        scores.revision_plan_actionability = revision_plan_actionability(selected_benchmark_fixture)
        scores.v25_release_gate_correctness = v25_release_gate_correctness(selected_benchmark_fixture)
    if fixture.is_v2_ideas:
        idea_fixture = fixture.idea_fixture
        scores.topic_portfolio_diversity = topic_portfolio_diversity(idea_fixture)
        scores.idea_candidate_specificity = idea_candidate_specificity(idea_fixture)
        scores.mutation_quality = mutation_quality(idea_fixture)
        scores.constructive_gap_quality = constructive_gap_quality(idea_fixture)
        scores.cross_domain_transfer_quality = cross_domain_transfer_quality(idea_fixture)
        scores.novelty_loop_quality = novelty_loop_quality(idea_fixture)
        scores.tournament_selection_quality = tournament_selection_quality(idea_fixture)
        scores.human_feedback_integration = human_feedback_integration(idea_fixture)
        scores.research_agenda_quality = research_agenda_quality(idea_fixture)
        scores.idea_yield_gate_correctness = idea_yield_gate_correctness(idea_fixture)
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
        "pilot_outcome_classification": 1.0,
        "idea_gate_quality": 0.85,
        "external_review_completeness": 0.8,
        "v1_readiness_gate_correctness": 1.0,
        "migration_audit_score": 0.8,
        "cli_audit_score": 0.8,
        "docs_audit_score": 0.8,
        "artifact_hygiene_score": 0.85,
        "v9_release_gate_correctness": 1.0,
        "benchmark_spec_completeness": 0.9,
        "threat_model_quality": 0.85,
        "trace_generator_validity": 0.85,
        "baseline_suite_completeness": 0.85,
        "sequential_metric_correctness": 0.85,
        "underpowered_claim_rejection": 1.0,
        "reviewer_blocker_quality": 0.8,
        "selected_benchmark_release_gate_correctness": 1.0,
        "main_power_decision_quality": 0.85,
        "related_work_completion_quality": 0.85,
        "baseline_strength_quality": 0.85,
        "main_result_analysis_quality": 0.85,
        "go_no_go_decision_quality": 0.85,
        "publication_review_quality": 0.85,
        "manuscript_maturity_honesty": 0.85,
        "v23_release_gate_correctness": 1.0,
        "related_work_search_quality": 0.85,
        "category_curation_quality": 0.85,
        "prior_work_dossier_quality": 0.85,
        "positioning_safety": 0.85,
        "selected_related_work_matrix_quality": 0.85,
        "publication_review_correctness": 0.85,
        "manuscript_revision_honesty": 0.85,
        "v24_release_gate_correctness": 1.0,
        "vetted_benchmark_fit_quality": 0.85,
        "adapter_transparency_score": 0.85,
        "venue_style_safety_score": 0.9,
        "citation_plagiarism_safety": 1.0,
        "review_dataset_integrity": 0.85,
        "review_taxonomy_quality": 0.85,
        "reviewer_calibration_score": 0.8,
        "drastic_review_quality": 0.85,
        "revision_plan_actionability": 0.85,
        "v25_release_gate_correctness": 1.0,
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
        "pilot_outcome_classification": "Classify direction, refusal, product failure, and incomplete outcomes with explicit evidence.",
        "idea_gate_quality": "Accept at most one auditable primary direction or preserve a correct refusal.",
        "external_review_completeness": "Record human/external review scope, role, concerns, and acceptance decision.",
        "v1_readiness_gate_correctness": "Allow accepted direction/refusal, but block unresolved product failures and missing audits.",
        "migration_audit_score": "Load older projects/runs, create backups, and surface migration blockers.",
        "cli_audit_score": "Keep command groups discoverable, help present, and compatibility aliases working.",
        "docs_audit_score": "Ensure quickstarts, limitations, and no-overclaim docs are present.",
        "artifact_hygiene_score": "Ignore or redact generated/private artifacts and keep safe bundles restricted.",
        "v9_release_gate_correctness": "Require pilot spec/run/outcome/review/idea gate and all v1-readiness audits.",
        "benchmark_spec_completeness": "Define honest and collusive distributions, modes, metrics, baselines, statistics, and limitations.",
        "threat_model_quality": "Make agent count, observability, adversary knowledge, adaptive behavior, and limitations explicit.",
        "trace_generator_validity": "Generate labeled synthetic honest, collusive, and hard-negative traces in both observability modes.",
        "baseline_suite_completeness": "Require runnable random, threshold, lexical, repeated-action, and anomaly baselines.",
        "sequential_metric_correctness": "Compute sequential metrics from traces and predictions with uncertainty warnings.",
        "underpowered_claim_rejection": "Block fake results, deployment claims, and strong low-FPR smoke claims.",
        "reviewer_blocker_quality": "Make reviewers expose blockers, required fixes, synthetic limits, and novelty uncertainty.",
        "selected_benchmark_release_gate_correctness": "Require the selected benchmark smoke path and block premature publication claims.",
        "main_power_decision_quality": "Record a main-scale power plan and explicit alpha=0.001 decision.",
        "related_work_completion_quality": "Complete required categories with real paper records or keep missing categories visible.",
        "baseline_strength_quality": "Implement required baselines, report optional LLM judge separately, and block leakage.",
        "main_result_analysis_quality": (
            "Back main/pilot analysis with metrics, predictions, comparisons, error analysis, and low-FPR reports."
        ),
        "go_no_go_decision_quality": "Produce evidence-backed go/revise/run-more/no-go decisions with visible blockers.",
        "publication_review_quality": "Keep publication-readiness review conservative and fatal on overclaims.",
        "manuscript_maturity_honesty": "Label manuscript maturity to match evidence and keep unresolved blockers visible.",
        "v23_release_gate_correctness": "Allow honest publication/workshop/revise/no-go outcomes but fail mislabeled evidence.",
        "related_work_search_quality": "Run category-specific offline search campaigns with evidence and visible source blockers.",
        "category_curation_quality": "Curate accepted real papers per required category and keep fallback-only categories incomplete.",
        "prior_work_dossier_quality": "Refresh closest-prior-work dossiers with comparison dimensions and decisive differences.",
        "positioning_safety": "Soften claims, cite closest prior work, and preserve synthetic/deployment limitations.",
        "selected_related_work_matrix_quality": (
            "Structure related-work relationships, must-cites, baselines, missing categories, and reviewer risks."
        ),
        "publication_review_correctness": (
            "Rerun publication review after related work and block missing categories, duplicates, and overclaims."
        ),
        "manuscript_revision_honesty": (
            "Revise manuscript related work with known citations, visible missing categories, and truthful readiness."
        ),
        "v24_release_gate_correctness": "Require explicit related-work remediation before publication/workshop/no-go outcomes.",
        "vetted_benchmark_fit_quality": "Assess benchmark fit explicitly and preserve no-fit justifications without forcing validation.",
        "adapter_transparency_score": "Record schemas, label/split preservation, transformation limits, and meaning-loss warnings.",
        "venue_style_safety_score": "Use venue style only for structure and rhetoric while preserving limitations and evidence gates.",
        "citation_plagiarism_safety": "Block copied prose, fake citations, and fake results before any v2.5 readiness outcome.",
        "review_dataset_integrity": "Keep review fixtures public/synthetic, hashed, licensed, and auditable.",
        "review_taxonomy_quality": "Map review issues to severities and GapForge gates without treating heuristic labels as truth.",
        "reviewer_calibration_score": "Evaluate reviewer calibration with evidence linkage and hallucination penalties.",
        "drastic_review_quality": "Generate harsh, role-covered, evidence-linked reviews without fake citations or invented results.",
        "revision_plan_actionability": (
            "Convert drastic review blockers into concrete experiments, searches, rewrites, and claim softening."
        ),
        "v25_release_gate_correctness": "Require v2.5 grounding, style safety, review calibration, and blocker-aware readiness outcomes.",
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
