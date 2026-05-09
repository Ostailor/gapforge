"""Reviewer panel for the selected sequential specificity benchmark."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    NoveltyDossier,
    PriorWorkRecallAssessment,
    Provenance,
    RelatedWorkMatrix,
    ReviewerReview,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaselineManager, MonitorCalibrationRecord
from gapforge.selected_benchmark.metrics import SequentialMetricManager, SequentialMetricResult
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisManager, PilotAnalysisResult
from gapforge.selected_benchmark.pilot_power import PilotPowerAssessment, PilotPowerManager
from gapforge.selected_benchmark.related_work import (
    SelectedBenchmarkRelatedWorkManager,
    SelectedPriorWorkRecall,
    SelectedRelatedWorkMatrix,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.selected_benchmark.threat_model import CollusionThreatModel
from gapforge.selected_benchmark.trace_generator import SyntheticTraceGenerator, TraceDataset
from gapforge.state import ResearchStateManager, utc_now_iso

REVIEWER_ROLES = [
    "benchmark validity reviewer",
    "statistics/low-FPR reviewer",
    "AI safety relevance reviewer",
    "baseline/reproducibility reviewer",
    "skeptical novelty reviewer",
    "area chair",
]

PILOT_REVIEWER_ROLES = [
    "benchmark validity reviewer",
    "statistics/low-FPR reviewer",
    "baseline reviewer",
    "related-work/novelty reviewer",
    "synthetic data validity reviewer",
    "area chair",
]


@dataclass(slots=True)
class SelectedBenchmarkReviewPanel:
    benchmark_id: str
    reviewer_reports: list[ReviewerReview] = field(default_factory=list)
    area_chair_summary: str = ""
    fatal_blockers: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    publishability_assessment: str = "unknown"
    reviewer_risk_score: float = 1.0
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-reviewer-panel"))


class SelectedBenchmarkReviewerPanelBuilder:
    """Attack selected-benchmark readiness with deterministic reviewer roles."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.trace_generator = SyntheticTraceGenerator(config)
        self.metric_manager = SequentialMetricManager(config)
        self.power_manager = PilotPowerManager(config)
        self.analysis_manager = PilotAnalysisManager(config)
        self.related_work_manager = SelectedBenchmarkRelatedWorkManager(config)

    def review(self, benchmark_id: str) -> SelectedBenchmarkReviewPanel:
        context = _ReviewContext.from_benchmark(self, benchmark_id)
        reviews = [
            _benchmark_validity_review(context),
            _statistics_low_fpr_review(context),
            _ai_safety_relevance_review(context),
            _baseline_reproducibility_review(context),
            _skeptical_novelty_review(context),
        ]
        fatal_blockers = _unique(flaw for review in reviews for flaw in review.fatal_flaws)
        required_fixes = _unique(fix for review in reviews for fix in review.required_fixes)
        risk_score = _reviewer_risk_score(reviews)
        publishability = _publishability_assessment(context, fatal_blockers)
        area_chair = _area_chair_review(context, reviews, fatal_blockers, required_fixes, publishability, risk_score)
        panel = SelectedBenchmarkReviewPanel(
            benchmark_id=benchmark_id,
            reviewer_reports=[*reviews, area_chair],
            area_chair_summary=area_chair.strengths[0] if area_chair.strengths else "",
            fatal_blockers=fatal_blockers,
            required_fixes=required_fixes,
            publishability_assessment=publishability,
            reviewer_risk_score=risk_score,
            limitations=context.limitations,
            provenance=Provenance(
                created_by_skill="selected-benchmark-reviewer-panel",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.threat_model.id if context.threat_model else "",
                        *[dataset.id for dataset in context.datasets],
                        *[result.id for result in context.metric_results],
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary="Ran deterministic reviewer roles against selected-benchmark artifacts and limitations.",
            ),
        )
        self._write_panel(panel)
        return panel

    def fix_list(self, benchmark_id: str) -> str:
        panel = self._ensure_panel(benchmark_id)
        report = render_selected_benchmark_fix_list(panel)
        spec = self.benchmark_manager.load_spec(benchmark_id)
        reports_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "fix_list.md").write_text(report, encoding="utf-8")
        return report

    def pilot_review(self, benchmark_id: str) -> SelectedBenchmarkReviewPanel:
        context = _PilotReviewContext.from_benchmark(self, benchmark_id)
        reviews = [
            _pilot_benchmark_validity_review(context),
            _pilot_statistics_low_fpr_review(context),
            _pilot_baseline_review(context),
            _pilot_related_work_novelty_review(context),
            _pilot_synthetic_validity_review(context),
        ]
        fatal_blockers = _unique(flaw for review in reviews for flaw in review.fatal_flaws)
        required_fixes = _unique(fix for review in reviews for fix in review.required_fixes)
        risk_score = _reviewer_risk_score(reviews)
        publishability = _pilot_publishability_assessment(context, fatal_blockers)
        area_chair = _pilot_area_chair_review(context, reviews, fatal_blockers, required_fixes, publishability, risk_score)
        panel = SelectedBenchmarkReviewPanel(
            benchmark_id=benchmark_id,
            reviewer_reports=[*reviews, area_chair],
            area_chair_summary=area_chair.strengths[0] if area_chair.strengths else "",
            fatal_blockers=fatal_blockers,
            required_fixes=required_fixes,
            publishability_assessment=publishability,
            reviewer_risk_score=risk_score,
            limitations=context.limitations,
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-reviewer-panel",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.threat_model.id if context.threat_model else "",
                        *[dataset.id for dataset in context.pilot_datasets],
                        *[record.id for record in context.calibration_records],
                        context.pilot_analysis.id if context.pilot_analysis else "",
                        context.prior_work_recall.id if context.prior_work_recall else "",
                        context.related_work_matrix.id if context.related_work_matrix else "",
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary="Ran pilot-evidence reviewer roles against selected benchmark v2.2 artifacts.",
            ),
        )
        self._write_pilot_panel(panel)
        return panel

    def pilot_fix_list(self, benchmark_id: str) -> str:
        panel = self._ensure_pilot_panel(benchmark_id)
        report = render_pilot_required_fixes(panel)
        spec = self.benchmark_manager.load_spec(benchmark_id)
        reviews_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "required_fixes.md").write_text(report, encoding="utf-8")
        (reviews_dir / "required_fixes.json").write_text(json.dumps(to_plain(panel.required_fixes), indent=2) + "\n", encoding="utf-8")
        return report

    def _ensure_panel(self, benchmark_id: str) -> SelectedBenchmarkReviewPanel:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._benchmark_dir(spec.project_id) / "reviews" / "selected_benchmark_review_panel.json"
        if path.exists():
            return from_dict(SelectedBenchmarkReviewPanel, json.loads(path.read_text(encoding="utf-8")))
        return self.review(benchmark_id)

    def _ensure_pilot_panel(self, benchmark_id: str) -> SelectedBenchmarkReviewPanel:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._benchmark_dir(spec.project_id) / "reviews" / "pilot_review_panel.json"
        if path.exists():
            return from_dict(SelectedBenchmarkReviewPanel, json.loads(path.read_text(encoding="utf-8")))
        return self.pilot_review(benchmark_id)

    def _write_panel(self, panel: SelectedBenchmarkReviewPanel) -> None:
        spec = self.benchmark_manager.load_spec(panel.benchmark_id)
        reviews_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "selected_benchmark_review_panel.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "selected_benchmark_review_panel.md").write_text(render_selected_benchmark_review_panel(panel), encoding="utf-8")
        (reviews_dir / "reviewer_reports.json").write_text(json.dumps(to_plain(panel.reviewer_reports), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "fix_list.md").write_text(render_selected_benchmark_fix_list(panel), encoding="utf-8")

    def _write_pilot_panel(self, panel: SelectedBenchmarkReviewPanel) -> None:
        spec = self.benchmark_manager.load_spec(panel.benchmark_id)
        reviews_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "pilot_review_panel.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "pilot_review_panel.md").write_text(render_pilot_review_panel(panel), encoding="utf-8")
        (reviews_dir / "required_fixes.json").write_text(json.dumps(to_plain(panel.required_fixes), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "required_fixes.md").write_text(render_pilot_required_fixes(panel), encoding="utf-8")
        (reviews_dir / "publishability_assessment.md").write_text(render_publishability_assessment(panel), encoding="utf-8")

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(slots=True)
class _ReviewContext:
    spec: SequentialSpecificityBenchmarkSpec
    threat_model: CollusionThreatModel | None
    datasets: list[TraceDataset]
    metric_results: list[SequentialMetricResult]
    baseline_blockers: list[str]
    spec_blockers: list[str]
    prior_work_recall: list[PriorWorkRecallAssessment]
    related_work_matrices: list[RelatedWorkMatrix]
    novelty_dossiers: list[NoveltyDossier]
    limitations: list[str]

    @classmethod
    def from_benchmark(cls, builder: SelectedBenchmarkReviewerPanelBuilder, benchmark_id: str) -> _ReviewContext:
        spec = builder.benchmark_manager.load_spec(benchmark_id)
        program = builder.project_manager.load_project(spec.project_id)
        runs = []
        for run_id in program.run_ids:
            try:
                runs.append(builder.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        threat_model = builder.benchmark_manager.load_threat_model(benchmark_id)
        datasets = _datasets(builder, spec)
        metric_results = _metric_results(builder, datasets)
        limitations = _unique(
            [
                *spec.limitations,
                *([*threat_model.limitations] if threat_model else []),
                *[limitation for dataset in datasets for limitation in dataset.limitations],
                *[limitation for result in metric_results for limitation in result.limitations],
            ]
        )
        return cls(
            spec=spec,
            threat_model=threat_model,
            datasets=datasets,
            metric_results=metric_results,
            baseline_blockers=builder.baseline_manager.readiness_blockers(benchmark_id),
            spec_blockers=builder.benchmark_manager.readiness_blockers(spec),
            prior_work_recall=[
                item
                for run in runs
                for item in run.prior_work_recall_assessments
                if item.target_id in {benchmark_id, spec.project_id} or benchmark_id in item.target_id
            ],
            related_work_matrices=[
                item
                for item in program.related_work_matrices
                if item.direction_id in {benchmark_id, f"selected-benchmark-{benchmark_id}", spec.project_id}
                or benchmark_id in item.direction_id
            ],
            novelty_dossiers=[
                item
                for run in runs
                for item in run.novelty_dossiers
                if item.target_id in {benchmark_id, spec.project_id} or benchmark_id in item.target_id
            ],
            limitations=limitations,
        )


@dataclass(slots=True)
class _PilotReviewContext:
    spec: SequentialSpecificityBenchmarkSpec
    threat_model: CollusionThreatModel | None
    pilot_datasets: list[TraceDataset]
    metric_results: list[SequentialMetricResult]
    baseline_blockers: list[str]
    calibration_records: list[MonitorCalibrationRecord]
    pilot_power_assessment: PilotPowerAssessment | None
    pilot_analysis: PilotAnalysisResult | None
    prior_work_recall: SelectedPriorWorkRecall | None
    related_work_matrix: SelectedRelatedWorkMatrix | None
    manuscript_text: str
    limitations: list[str]

    @classmethod
    def from_benchmark(cls, builder: SelectedBenchmarkReviewerPanelBuilder, benchmark_id: str) -> _PilotReviewContext:
        spec = builder.benchmark_manager.load_spec(benchmark_id)
        threat_model = builder.benchmark_manager.load_threat_model(benchmark_id)
        datasets = [dataset for dataset in _datasets(builder, spec) if dataset.split == "pilot"]
        metric_results = _metric_results(builder, datasets)
        calibration_records = _calibration_records(builder, benchmark_id)
        power_assessment = _latest_power_assessment(builder, datasets)
        pilot_analysis = _latest_pilot_analysis(builder, benchmark_id)
        prior_work_recall = _selected_prior_work_recall(builder, benchmark_id)
        related_work_matrix = _selected_related_work_matrix(builder, benchmark_id)
        manuscript_text = _manuscript_package_text(builder, spec.project_id)
        limitations = _unique(
            [
                *spec.limitations,
                *([*threat_model.limitations] if threat_model else []),
                *[limitation for dataset in datasets for limitation in dataset.limitations],
                *[limitation for result in metric_results for limitation in result.limitations],
                *(power_assessment.warnings if power_assessment else []),
                "Pilot review treats synthetic pilot evidence as pilot-only evidence.",
            ]
        )
        return cls(
            spec=spec,
            threat_model=threat_model,
            pilot_datasets=datasets,
            metric_results=metric_results,
            baseline_blockers=builder.baseline_manager.pilot_readiness_blockers(benchmark_id),
            calibration_records=calibration_records,
            pilot_power_assessment=power_assessment,
            pilot_analysis=pilot_analysis,
            prior_work_recall=prior_work_recall,
            related_work_matrix=related_work_matrix,
            manuscript_text=manuscript_text,
            limitations=limitations,
        )


def render_selected_benchmark_review_panel(panel: SelectedBenchmarkReviewPanel) -> str:
    lines = [
        f"# Selected Benchmark Review Panel `{panel.benchmark_id}`",
        "",
        f"- Publishability assessment: `{panel.publishability_assessment}`",
        f"- Reviewer-risk score: {panel.reviewer_risk_score:.2f}",
        f"- Fatal blockers: {len(panel.fatal_blockers)}",
        f"- Required fixes: {len(panel.required_fixes)}",
        "",
        "## Area Chair Summary",
        "",
        panel.area_chair_summary or "No area chair summary generated.",
        "",
        "## Reviewer Reports",
        "",
    ]
    for review in panel.reviewer_reports:
        lines.extend(
            [
                f"### {review.reviewer_id}: {review.role}",
                "",
                f"- Score: {review.score:.1f}",
                f"- Confidence: {review.confidence}",
                f"- Evidence: {', '.join(review.evidence_or_prior_work) or 'none'}",
                "",
                "**Strengths**",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in review.strengths] or ["- none"])
        lines.extend(["", "**Weaknesses**", ""])
        lines.extend([f"- {item}" for item in review.weaknesses] or ["- none"])
        lines.extend(["", "**Questions**", ""])
        lines.extend([f"- {item}" for item in review.questions] or ["- none"])
        lines.extend(["", "**Required Fixes**", ""])
        lines.extend([f"- {item}" for item in review.required_fixes] or ["- none"])
        lines.extend(["", "**Fatal Flaws**", ""])
        lines.extend([f"- {item}" for item in review.fatal_flaws] or ["- none", ""])
    lines.extend(["## Fatal Blockers", ""])
    lines.extend([f"- {item}" for item in panel.fatal_blockers] or ["- none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {item}" for item in panel.required_fixes] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in panel.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_selected_benchmark_fix_list(panel: SelectedBenchmarkReviewPanel) -> str:
    lines = [
        f"# Selected Benchmark Fix List `{panel.benchmark_id}`",
        "",
        f"- Publishability assessment: `{panel.publishability_assessment}`",
        f"- Reviewer-risk score: {panel.reviewer_risk_score:.2f}",
        "",
        "## Fatal Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in panel.fatal_blockers] or ["- none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {item}" for item in panel.required_fixes] or ["- none"])
    lines.extend(["", "## Reviewer Weaknesses", ""])
    weaknesses = _unique(weakness for review in panel.reviewer_reports for weakness in review.weaknesses)
    lines.extend([f"- {item}" for item in weaknesses] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_pilot_review_panel(panel: SelectedBenchmarkReviewPanel) -> str:
    text = render_selected_benchmark_review_panel(panel)
    return text.replace("# Selected Benchmark Review Panel", "# Pilot Review Panel", 1)


def render_pilot_required_fixes(panel: SelectedBenchmarkReviewPanel) -> str:
    text = render_selected_benchmark_fix_list(panel)
    return text.replace("# Selected Benchmark Fix List", "# Selected Pilot Required Fixes", 1)


def render_publishability_assessment(panel: SelectedBenchmarkReviewPanel) -> str:
    lines = [
        f"# Publishability Assessment `{panel.benchmark_id}`",
        "",
        f"- Assessment: `{panel.publishability_assessment}`",
        f"- Reviewer-risk score: {panel.reviewer_risk_score:.2f}",
        "",
        "## Summary",
        "",
        panel.area_chair_summary or "No area chair summary generated.",
        "",
        "## Remaining Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in panel.fatal_blockers] or ["- none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {item}" for item in panel.required_fixes] or ["- none"])
    lines.extend(["", "## Honest Boundary", ""])
    lines.extend(
        [
            "- Pilot evidence is not deployment evidence.",
            "- Publishability remains blocked while fatal reviewer blockers are present.",
            "- The area chair may recommend main-scale data or stronger scenarios before contribution claims.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _pilot_benchmark_validity_review(context: _PilotReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = [context.spec.id]
    if context.threat_model:
        evidence.append(context.threat_model.id)
    if not context.pilot_datasets:
        fatal.append("No pilot dataset is attached; pilot evidence cannot be reviewed.")
        fixes.append("Build a pilot trace dataset and rerun pilot analysis.")
    if not context.pilot_analysis:
        weaknesses.append("Pilot result analysis is missing or stale.")
        fixes.append("Run `gapforge selected-pilot-analysis` before pilot review.")
    if context.threat_model is None:
        fatal.append("Threat model is missing from the pilot evidence package.")
        fixes.append("Attach the selected benchmark threat model before pilot review.")
    return _review(
        "selected-pilot-benchmark-validity-reviewer",
        "benchmark validity reviewer",
        strengths=["Pilot evidence includes a locked benchmark spec and pilot-labeled dataset."] if context.pilot_datasets else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence + [dataset.id for dataset in context.pilot_datasets],
    )


def _pilot_statistics_low_fpr_review(context: _PilotReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = [result.id for result in context.metric_results[:8]]
    assessment = context.pilot_power_assessment
    if assessment is None:
        fatal.append("Pilot power assessment is missing, so alpha claims cannot be reviewed.")
        fixes.append("Run selected pilot power checks against the pilot dataset.")
    else:
        evidence.append(assessment.id)
        for alpha, payload in sorted(assessment.alpha_targets_underpowered.items()):
            fatal.append(
                f"Underpowered alpha target alpha={alpha}: "
                f"{payload['observed_negative_count']} observed / {payload['required_negative_count']} required."
            )
        if assessment.blockers:
            fatal.extend(assessment.blockers)
        if "0.001" in assessment.alpha_targets_underpowered:
            fixes.append("Treat alpha=0.001 as main-scale only or collect enough honest negative pilot/main traces.")
    if not any(result.metric_name == "zero_false_positive_upper_bound" for result in context.metric_results):
        weaknesses.append("Zero-false-positive upper-bound metric is absent from pilot metrics.")
        fixes.append("Regenerate pilot metrics with zero-FP upper-bound artifacts.")
    return _review(
        "selected-pilot-statistics-low-fpr-reviewer",
        "statistics/low-FPR reviewer",
        strengths=["Pilot power checks and sequential metrics are reviewer-visible."] if assessment else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _pilot_baseline_review(context: _PilotReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    if context.baseline_blockers:
        fatal.extend(context.baseline_blockers)
        fixes.append("Resolve missing pilot baselines, missing runs, and calibration blockers.")
    if not context.calibration_records:
        fatal.append("Pilot baseline calibration records are missing.")
        fixes.append("Calibrate required monitors on honest/null data before pilot comparison.")
    weak = _weak_baseline_suite(context)
    if weak:
        fatal.append("Weak baseline suite blocks strong contribution claims.")
        fixes.append("Add stronger prior-work baselines or limit claims to pilot benchmark plumbing and descriptive comparisons.")
    return _review(
        "selected-pilot-baseline-reviewer",
        "baseline reviewer",
        strengths=["Required pilot baselines and calibration records are explicit."] if context.calibration_records else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=[*[record.id for record in context.calibration_records], *context.baseline_blockers],
    )


def _pilot_related_work_novelty_review(context: _PilotReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    if context.prior_work_recall is None:
        fatal.append("Prior-work recall is missing for pilot maturity.")
        fixes.append("Run selected benchmark prior-work recall before pilot novelty claims.")
    else:
        evidence.append(context.prior_work_recall.id)
        if context.prior_work_recall.missing_categories:
            fatal.append(f"Missing prior-work categories: {', '.join(context.prior_work_recall.missing_categories)}.")
            fixes.append("Attach papers for every required prior-work category or keep novelty weak/unknown.")
    if context.related_work_matrix is None:
        fatal.append("Related-work matrix is missing for pilot maturity.")
        fixes.append("Run selected benchmark related-work matrix before publishability assessment.")
    else:
        evidence.append(context.related_work_matrix.id)
        if context.related_work_matrix.missing_categories:
            fatal.append(f"Missing related-work matrix categories: {', '.join(context.related_work_matrix.missing_categories)}.")
    return _review(
        "selected-pilot-related-work-novelty-reviewer",
        "related-work/novelty reviewer",
        strengths=(
            ["Closest prior work and matrix artifacts are attached."] if context.prior_work_recall and context.related_work_matrix else []
        ),
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _pilot_synthetic_validity_review(context: _PilotReviewContext) -> ReviewerReview:
    weaknesses = ["Synthetic-only pilot evidence cannot support deployment validity claims."]
    fixes = ["Keep all pilot claims labeled synthetic/pilot and recommend main-scale or real-world validation separately."]
    fatal: list[str] = []
    if _deployment_overclaim(context.manuscript_text):
        fatal.append("Synthetic-only validity blocks deployment claims found in manuscript/package artifacts.")
        fixes.append("Remove deployment-validity language from the manuscript package.")
    return _review(
        "selected-pilot-synthetic-data-validity-reviewer",
        "synthetic data validity reviewer",
        strengths=["Pilot outputs are labeled synthetic/pilot in the artifact path."] if context.pilot_datasets else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=[dataset.id for dataset in context.pilot_datasets],
    )


def _pilot_area_chair_review(
    context: _PilotReviewContext,
    reviews: list[ReviewerReview],
    fatal_blockers: list[str],
    required_fixes: list[str],
    publishability: str,
    risk_score: float,
) -> ReviewerReview:
    summary = (
        f"Area chair assessment: `{publishability}` with reviewer-risk score {risk_score:.2f}. "
        "Pilot evidence is useful but remains bounded by synthetic data, alpha power, related-work coverage, and baseline strength."
    )
    if fatal_blockers:
        summary += " Main-scale data, stronger scenarios, or stronger baselines may be required before publication claims."
    return ReviewerReview(
        reviewer_id="selected-pilot-area-chair",
        role="area chair",
        score=max(1.0, round(10.0 - risk_score * 9.0, 1)),
        confidence="high",
        strengths=[summary],
        weaknesses=_unique(item for review in reviews for item in review.weaknesses),
        questions=["Which blocker must be cleared before this can move beyond pilot maturity?"],
        required_fixes=required_fixes,
        fatal_flaws=fatal_blockers,
        evidence_or_prior_work=[context.spec.id],
        provenance=Provenance(
            created_by_skill="selected-benchmark-pilot-reviewer-panel",
            source_ids=[context.spec.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Aggregated selected benchmark pilot-review findings into an area-chair assessment.",
        ),
    )


def _benchmark_validity_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = [context.spec.id]
    if context.threat_model:
        evidence.append(context.threat_model.id)
    if not context.spec.honest_agent_distribution:
        fatal.append("Missing honest null distribution makes specificity evaluation invalid.")
        fixes.append("Define and persist the honest-agent null distribution before benchmark readiness.")
    elif not context.spec.honest_agent_distribution.get("required", False):
        fatal.append("Honest null distribution is present but not required by the benchmark spec.")
        fixes.append("Mark the honest-agent null distribution as required and gate readiness on it.")
    if not context.threat_model:
        weaknesses.append("Threat model is missing, so observability and adversary assumptions are not reviewable.")
        fixes.append("Generate and review the collusion threat model before pilot/main runs.")
    if not context.datasets:
        weaknesses.append("Trace generator has not produced a reviewable smoke or pilot dataset.")
        fixes.append("Run the synthetic trace generator and include trace dataset reports in the benchmark package.")
    if _synthetic_overclaim(context):
        weaknesses.append("Synthetic data limitations are at risk of being overclaimed.")
        fixes.append("Keep synthetic fixture claims limited to benchmark wiring and explicitly forbid real-deployment validity claims.")
    return _review(
        "selected-benchmark-validity-reviewer",
        "benchmark validity reviewer",
        strengths=["The benchmark target is explicit and scoped to sequential specificity."] if context.spec.benchmark_goal else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _statistics_low_fpr_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = [result.id for result in context.metric_results[:8]]
    if not context.metric_results:
        weaknesses.append("No sequential metric results are available for review.")
        fixes.append("Run a smoke benchmark path and compute sequential metrics from traces and monitor predictions.")
    underpowered = [item for result in context.metric_results for item in result.limitations if "underpowered" in item.lower()]
    if underpowered:
        fatal.append("Underpowered low-FPR evidence cannot support pilot/main or publication claims.")
        fixes.append("Increase honest negative trace counts or label all low-FPR conclusions as underpowered smoke-only wiring checks.")
    if any(dataset.split == "smoke" for dataset in context.datasets):
        weaknesses.append("Smoke-only result artifacts are useful for wiring but not publishable scientific evidence.")
        fixes.append("Define pilot and main sample-size gates before any publishability claim.")
    if not any(result.metric_name == "zero_false_positive_upper_bound" for result in context.metric_results):
        weaknesses.append("Zero-false-positive upper-bound metric is absent from available results.")
        fixes.append("Report exact/binomial upper bounds whenever zero false positives are observed.")
    return _review(
        "selected-benchmark-statistics-reviewer",
        "statistics/low-FPR reviewer",
        strengths=["Sequential specificity metrics include low-FPR caution machinery."] if context.metric_results else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _ai_safety_relevance_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    evidence = [context.spec.id]
    if context.threat_model:
        evidence.append(context.threat_model.id)
    if not context.threat_model or not context.threat_model.observable_signals:
        weaknesses.append("Safety relevance is hard to assess without observable monitor inputs.")
        fixes.append("Document monitor observability assumptions for transcript-visible and action-only settings.")
    if not context.spec.collusive_agent_distribution:
        weaknesses.append("Collusive alternative distribution is missing or underspecified.")
        fixes.append("Define collusive-agent alternatives with explicit prohibited-objective labels.")
    if context.threat_model and not context.threat_model.limitations:
        weaknesses.append("Safety limitations are not explicit enough for a benchmark artifact.")
        fixes.append("State out-of-scope channels, adaptive adversary limits, and synthetic-fixture limits.")
    return _review(
        "selected-benchmark-ai-safety-reviewer",
        "AI safety relevance reviewer",
        strengths=["The benchmark asks a monitor-evaluation question relevant to low-FPR collusion auditing."],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=[],
        evidence=evidence,
    )


def _baseline_reproducibility_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    if context.baseline_blockers:
        weaknesses.extend(context.baseline_blockers)
        fixes.append("Register required baselines and run smoke predictions for all required CI-enabled monitors.")
        missing_required_baselines = any(
            "missing required baseline type" in blocker or "missing monitor baseline registry" in blocker
            for blocker in context.baseline_blockers
        )
        if missing_required_baselines:
            fatal.append("Missing required baseline coverage prevents experiment readiness.")
    if not context.datasets:
        weaknesses.append("No trace dataset exists to reproduce baseline predictions.")
        fixes.append("Generate smoke traces before baseline review.")
    return _review(
        "selected-benchmark-baseline-reproducibility-reviewer",
        "baseline/reproducibility reviewer",
        strengths=["Baseline registry is explicit and CI-disabled placeholders are labeled."] if not context.baseline_blockers else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=[*context.baseline_blockers, *[dataset.id for dataset in context.datasets[:3]]],
    )


def _skeptical_novelty_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    evidence = [
        *[item.id for item in context.prior_work_recall],
        *[item.direction_id for item in context.related_work_matrices],
        *[item.target_id for item in context.novelty_dossiers],
    ]
    if not context.prior_work_recall:
        weaknesses.append("Prior-work recall evidence is missing for the selected benchmark idea.")
        fixes.append("Run or attach prior-work recall before making novelty claims.")
    elif any(item.recall_confidence != "high" for item in context.prior_work_recall):
        weaknesses.append("Prior-work recall confidence is not high, so novelty uncertainty remains visible.")
        fixes.append("Complete missing prior-work searches or weaken novelty claims.")
    if not context.related_work_matrices:
        weaknesses.append("Related-work matrix is absent for the selected benchmark artifact.")
        fixes.append("Attach a related-work matrix listing must-read and baseline papers.")
    if context.novelty_dossiers and any(item.verdict in {"duplicate", "blocked"} for item in context.novelty_dossiers):
        fixes.append("Resolve blocking novelty dossier findings before manuscript readiness.")
    return _review(
        "selected-benchmark-skeptical-novelty-reviewer",
        "skeptical novelty reviewer",
        strengths=["The selected idea remains frozen, reducing silent drift from the accepted v2 target."],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=[],
        evidence=evidence,
    )


def _area_chair_review(
    context: _ReviewContext,
    reviews: list[ReviewerReview],
    fatal_blockers: list[str],
    required_fixes: list[str],
    publishability: str,
    risk_score: float,
) -> ReviewerReview:
    weaknesses = _unique(item for review in reviews for item in review.weaknesses)
    summary = (
        f"Area chair assessment: `{publishability}` with reviewer-risk score {risk_score:.2f}. "
        "The panel treats smoke artifacts as engineering evidence only, not final scientific results."
    )
    if fatal_blockers:
        summary += " Fatal blockers must be resolved before pilot/main claims."
    elif required_fixes:
        summary += " Required fixes remain before manuscript readiness."
    return ReviewerReview(
        reviewer_id="selected-benchmark-area-chair",
        role="area chair",
        score=max(1.0, round(10.0 - risk_score * 9.0, 1)),
        confidence="high",
        strengths=[summary],
        weaknesses=weaknesses,
        questions=["Can the benchmark demonstrate specificity beyond synthetic fixture wiring?"],
        required_fixes=required_fixes,
        fatal_flaws=fatal_blockers,
        evidence_or_prior_work=[context.spec.id],
        provenance=Provenance(
            created_by_skill="selected-benchmark-reviewer-panel",
            source_ids=[context.spec.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Aggregated selected-benchmark reviewer findings into an area-chair assessment.",
        ),
    )


def _review(
    reviewer_id: str,
    role: str,
    *,
    strengths: list[str],
    weaknesses: list[str],
    required_fixes: list[str],
    fatal_flaws: list[str],
    evidence: list[str],
) -> ReviewerReview:
    major = len(weaknesses)
    fatal = len(fatal_flaws)
    score = max(1.0, min(10.0, round(8.0 - 1.1 * major - 3.5 * fatal, 1)))
    confidence = "high" if evidence else "medium" if weaknesses or fatal_flaws else "low"
    return ReviewerReview(
        reviewer_id=reviewer_id,
        role=role,
        score=score,
        confidence=confidence,
        strengths=strengths,
        weaknesses=_unique(weaknesses),
        questions=_questions_for(role, weaknesses, fatal_flaws),
        required_fixes=_unique(required_fixes),
        fatal_flaws=_unique(fatal_flaws),
        evidence_or_prior_work=_unique(evidence),
        provenance=Provenance(
            created_by_skill="selected-benchmark-reviewer-panel",
            source_ids=_unique(evidence),
            timestamp=utc_now_iso(),
            reasoning_summary=f"Generated deterministic selected-benchmark review for role `{role}`.",
        ),
    )


def _questions_for(role: str, weaknesses: list[str], fatal_flaws: list[str]) -> list[str]:
    if fatal_flaws:
        return [f"What artifact would resolve the fatal blocker raised by the {role}?"]
    if weaknesses:
        return [f"What evidence would turn the {role} weakness into an accepted benchmark criterion?"]
    return ["What remaining assumption is most likely to fail in pilot/main runs?"]


def _datasets(builder: SelectedBenchmarkReviewerPanelBuilder, spec: SequentialSpecificityBenchmarkSpec) -> list[TraceDataset]:
    root = builder._benchmark_dir(spec.project_id) / "trace_datasets"
    datasets: list[TraceDataset] = []
    for path in sorted(root.glob("*/dataset.json")):
        dataset = from_dict(TraceDataset, json.loads(path.read_text(encoding="utf-8")))
        if dataset.benchmark_id == spec.id:
            datasets.append(dataset)
    return datasets


def _metric_results(builder: SelectedBenchmarkReviewerPanelBuilder, datasets: list[TraceDataset]) -> list[SequentialMetricResult]:
    results: list[SequentialMetricResult] = []
    for dataset in datasets:
        dataset_dir = _dataset_dir(builder, dataset.id)
        metrics_path = dataset_dir / "sequential_metrics.json"
        if metrics_path.exists():
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
            results.extend(from_dict(SequentialMetricResult, item) for item in raw)
    return results


def _dataset_dir(builder: SelectedBenchmarkReviewerPanelBuilder, dataset_id: str) -> Path:
    for project in builder.project_manager.list_projects():
        path = builder._benchmark_dir(project.id) / "trace_datasets" / dataset_id
        if path.exists():
            return path
    raise FileNotFoundError(f"No selected benchmark trace dataset `{dataset_id}` found.")


def _calibration_records(builder: SelectedBenchmarkReviewerPanelBuilder, benchmark_id: str) -> list[MonitorCalibrationRecord]:
    spec = builder.benchmark_manager.load_spec(benchmark_id)
    root = builder._benchmark_dir(spec.project_id) / "monitor_calibrations"
    records: list[MonitorCalibrationRecord] = []
    for path in sorted(root.glob("*.json")):
        records.append(from_dict(MonitorCalibrationRecord, json.loads(path.read_text(encoding="utf-8"))))
    return records


def _latest_power_assessment(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    datasets: list[TraceDataset],
) -> PilotPowerAssessment | None:
    if not datasets:
        return None
    try:
        return builder.power_manager.check_dataset(datasets[-1].id)
    except (FileNotFoundError, ValueError):
        return None


def _latest_pilot_analysis(builder: SelectedBenchmarkReviewerPanelBuilder, benchmark_id: str) -> PilotAnalysisResult | None:
    try:
        return builder.analysis_manager.load_latest_for_benchmark(benchmark_id)
    except FileNotFoundError:
        return None


def _selected_prior_work_recall(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
) -> SelectedPriorWorkRecall | None:
    try:
        return builder.related_work_manager.load_prior_work_recall(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _selected_related_work_matrix(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
) -> SelectedRelatedWorkMatrix | None:
    try:
        return builder.related_work_manager.load_related_work_matrix(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _manuscript_package_text(builder: SelectedBenchmarkReviewerPanelBuilder, project_id: str) -> str:
    root = builder._benchmark_dir(project_id)
    texts = []
    for directory_name in ["manuscript", "paper_package"]:
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            texts.append(path.read_text(encoding="utf-8"))
    return "\n".join(texts)


def _synthetic_overclaim(context: _ReviewContext) -> bool:
    text = " ".join(context.limitations).lower()
    return "real deployment" not in text and bool(context.datasets)


def _deployment_overclaim(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    deployment_markers = ["deployment validity", "operational validity", "real-world deployment", "deployed monitor"]
    negations = ["does not claim deployment validity", "do not claim deployment validity", "not deployment evidence"]
    return any(marker in lowered for marker in deployment_markers) and not any(negation in lowered for negation in negations)


def _weak_baseline_suite(context: _PilotReviewContext) -> bool:
    if context.baseline_blockers:
        return True
    if len(context.calibration_records) < 4:
        return True
    return True


def _publishability_assessment(context: _ReviewContext, fatal_blockers: list[str]) -> str:
    if fatal_blockers:
        return "not_publishable_fatal_blockers"
    if not context.metric_results or any(dataset.split == "smoke" for dataset in context.datasets):
        return "not_publishable_smoke_only"
    if context.baseline_blockers or not context.prior_work_recall:
        return "not_publishable_required_fixes"
    return "potentially_publishable_after_review"


def _pilot_publishability_assessment(context: _PilotReviewContext, fatal_blockers: list[str]) -> str:
    if fatal_blockers:
        return "not_publishable_pilot_blockers"
    if not context.pilot_analysis:
        return "not_publishable_missing_pilot_results"
    return "pilot_maturity_only_not_publication_ready"


def _reviewer_risk_score(reviews: list[ReviewerReview]) -> float:
    fatal_count = sum(len(review.fatal_flaws) for review in reviews)
    major_count = sum(len(review.weaknesses) for review in reviews)
    score_penalty = sum(max(0.0, 8.0 - review.score) for review in reviews) / max(1, len(reviews)) / 8.0
    risk = min(1.0, 0.15 + fatal_count * 0.25 + major_count * 0.06 + score_penalty)
    return round(risk, 2)


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
