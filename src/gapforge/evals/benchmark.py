"""Offline benchmark harness for research-gap quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gapforge.evals.fixtures import EvalFixture, load_fixtures
from gapforge.evals.metrics import (
    EvalScores,
    RunMetrics,
    duplicate_detection_rate,
    evidence_linkage_score,
    experiment_completeness_score,
    gap_specificity_score,
    novelty_gate_accuracy,
    reviewer_objection_quality_score,
    unsupported_claim_rate,
)
from gapforge.models import Claim, Evidence, ExperimentPlan, Gap, ResearchRunState, ResearchTopic
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
) -> EvalReport:
    fixtures = load_fixtures([fixture] if fixture else None, fixture_root)
    results = [_evaluate_fixture(item) for item in fixtures]
    report = EvalReport(results=results)
    if write_report:
        path = (output_dir or Path.cwd()) / "eval_report.md"
        path.write_text(render_eval_report(report), encoding="utf-8")
        report.report_path = path
    return report


def render_eval_report(report: EvalReport) -> str:
    lines = ["# GapForge Evaluation Report", "", f"Overall score: **{report.overall_score:.3f}**", ""]
    for result in report.results:
        scores = result.scores
        lines.extend(
            [
                f"## {result.fixture_name}",
                "",
                f"Topic: {result.topic}",
                "",
                "### Scores",
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
        novelty_gate_accuracy=novelty_gate_accuracy(state.novelty_assessments, fixture.duplicate_ideas),
        duplicate_detection_rate=duplicate_detection_rate(state.novelty_assessments),
        unsupported_claim_rate=unsupported_claim_rate(state.claims),
        experiment_completeness_score=experiment_completeness_score(state.experiments),
        reviewer_objection_quality_score=reviewer_objection_quality_score(state.reviewer_objections),
    )
    unsupported = [
        claim.id
        for claim in state.claims
        if claim.status == "supported"
        and not claim.supporting_evidence
        or claim.type == "novelty"
        and not claim.closest_prior_work
        or claim.status == "unsupported"
    ]
    accepted = [gap.id for gap in state.gaps if gap.novelty_status not in {"likely_not_new"}]
    rejected = [gap.id for gap in state.gaps if gap.novelty_status == "likely_not_new"]
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
        paper_notes=fixture.paper_notes,
        gaps=[*fixture.known_good_gaps, *_duplicate_gaps(fixture), *fixture.known_bad_gaps],
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
