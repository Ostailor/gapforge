"""Offline benchmark harness for research-gap quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gapforge.evals.fixtures import V2_FIXTURE_NAMES, EvalFixture, load_fixtures
from gapforge.evals.metrics import (
    EvalScores,
    RunMetrics,
    duplicate_detection_rate,
    evidence_linkage_score,
    evidence_span_precision_proxy,
    experiment_completeness_score,
    full_text_coverage_score,
    gap_evidence_matrix_score,
    gap_specificity_score,
    human_review_respect_score,
    novelty_dossier_completeness_score,
    novelty_gate_accuracy,
    report_uncertainty_score,
    reviewer_objection_quality_score,
    section_grounding_score,
    source_coverage_transparency_score,
    unsupported_claim_rate,
)
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
) -> EvalReport:
    selected = [fixture] if fixture else (V2_FIXTURE_NAMES if v2 else None)
    fixtures = load_fixtures(selected, fixture_root)
    results = [_evaluate_fixture(item) for item in fixtures]
    report = EvalReport(results=results, v2=v2 or any(item.is_v2 for item in fixtures))
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
