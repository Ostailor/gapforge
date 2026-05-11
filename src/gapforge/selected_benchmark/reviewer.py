"""Reviewer panel for the selected sequential specificity benchmark."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
from gapforge.selected_benchmark.baselines import BaselineStrengthAssessment, MonitorBaselineManager, MonitorCalibrationRecord
from gapforge.selected_benchmark.main_analysis import MainAnalysisManager, MainAnalysisResult
from gapforge.selected_benchmark.main_power import MainPowerDecision, MainPowerManager
from gapforge.selected_benchmark.metrics import SequentialMetricManager, SequentialMetricResult
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisManager, PilotAnalysisResult
from gapforge.selected_benchmark.pilot_power import PilotPowerAssessment, PilotPowerManager
from gapforge.selected_benchmark.positioning import PositioningReport, SelectedBenchmarkPositioningManager
from gapforge.selected_benchmark.prior_work_refresh import (
    SelectedBenchmarkPriorWorkDossier,
    SelectedBenchmarkPriorWorkRefreshManager,
)
from gapforge.selected_benchmark.related_work import (
    SelectedBenchmarkRelatedWorkManager,
    SelectedPriorWorkRecall,
    SelectedRelatedWorkMatrix,
)
from gapforge.selected_benchmark.related_work_completion import RelatedWorkCompletionManager, RelatedWorkCompletionStatus
from gapforge.selected_benchmark.related_work_matrix_v2 import (
    SelectedBenchmarkRelatedWorkMatrixV2,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
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


@dataclass(slots=True)
class PublicationReadinessReview:
    id: str
    benchmark_id: str
    readiness: str = "not_ready"
    fatal_blockers: list[str] = field(default_factory=list)
    major_blockers: list[str] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-publication-readiness-review"))


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

    def publication_review(self, benchmark_id: str, *, after_related_work: bool = False) -> PublicationReadinessReview:
        context = _PublicationReadinessContext.from_benchmark(self, benchmark_id, after_related_work=after_related_work)
        fatal_blockers: list[str] = []
        major_blockers: list[str] = []
        required_revisions: list[str] = []

        _review_result_evidence(context, major_blockers, required_revisions)
        _review_related_work_completion(context, fatal_blockers, major_blockers, required_revisions)
        _review_prior_work_dossier(context, fatal_blockers, major_blockers, required_revisions)
        _review_contribution_positioning(context, major_blockers, required_revisions)
        _review_baseline_strength(context, fatal_blockers, major_blockers, required_revisions)
        _review_alpha_power_claims(context, fatal_blockers, major_blockers, required_revisions)
        _review_manuscript_traceability(context, fatal_blockers, major_blockers, required_revisions)

        readiness = _publication_readiness(
            context=context,
            fatal_blockers=fatal_blockers,
            major_blockers=major_blockers,
        )
        if context.main_analysis is None and context.pilot_analysis is not None:
            required_revisions.append("Pilot-only results may support at most workshop positioning unless strong caveats are explicit.")
        confidence = _publication_confidence(readiness, context, fatal_blockers=fatal_blockers, major_blockers=major_blockers)
        review = PublicationReadinessReview(
            id=f"publication-readiness-review-{benchmark_id}{'-after-related-work' if after_related_work else ''}",
            benchmark_id=benchmark_id,
            readiness=readiness,
            fatal_blockers=_unique(fatal_blockers),
            major_blockers=_unique(major_blockers),
            required_revisions=_unique(required_revisions),
            confidence=confidence,
            provenance=Provenance(
                created_by_skill="selected-publication-readiness-review",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.main_analysis.id if context.main_analysis else "",
                        context.pilot_analysis.id if context.pilot_analysis else "",
                        context.related_work_status.id if context.related_work_status else "",
                        context.prior_work_dossier.id if context.prior_work_dossier else "",
                        context.positioning_report.id if context.positioning_report else "",
                        context.related_work_matrix_v2.id if context.related_work_matrix_v2 else "",
                        context.baseline_strength.id if context.baseline_strength else "",
                        context.main_power_decision.id if context.main_power_decision else "",
                        *context.manuscript_paths,
                        *context.traceability_paths,
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Reviewed main/pilot results, related work, baselines, power decisions, manuscript claims, and traceability."
                ),
            ),
        )
        self._write_publication_review(review, after_related_work=after_related_work)
        return review

    def publication_fix_list(self, benchmark_id: str, *, after_related_work: bool = False) -> str:
        review = (
            self._ensure_publication_review_after_related_work(benchmark_id)
            if after_related_work
            else self._ensure_publication_review(benchmark_id)
        )
        report = render_publication_fix_list(review)
        spec = self.benchmark_manager.load_spec(benchmark_id)
        reviews_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        filename = "main_publication_fix_list_after_related_work.md" if after_related_work else "main_publication_fix_list.md"
        (reviews_dir / filename).write_text(report, encoding="utf-8")
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

    def _ensure_publication_review(self, benchmark_id: str) -> PublicationReadinessReview:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._benchmark_dir(spec.project_id) / "reviews" / "main_publication_review.json"
        if path.exists():
            try:
                return from_dict(PublicationReadinessReview, json.loads(path.read_text(encoding="utf-8")))
            except (TypeError, ValueError):
                pass
        return self.publication_review(benchmark_id)

    def _ensure_publication_review_after_related_work(self, benchmark_id: str) -> PublicationReadinessReview:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._benchmark_dir(spec.project_id) / "reviews" / "main_publication_review_after_related_work.json"
        if path.exists():
            try:
                return from_dict(PublicationReadinessReview, json.loads(path.read_text(encoding="utf-8")))
            except (TypeError, ValueError):
                pass
        return self.publication_review(benchmark_id, after_related_work=True)

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

    def _write_publication_review(self, review: PublicationReadinessReview, *, after_related_work: bool = False) -> None:
        spec = self.benchmark_manager.load_spec(review.benchmark_id)
        reviews_dir = self._benchmark_dir(spec.project_id) / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        stem = "main_publication_review_after_related_work" if after_related_work else "main_publication_review"
        fix_list_name = "main_publication_fix_list_after_related_work.md" if after_related_work else "main_publication_fix_list.md"
        (reviews_dir / f"{stem}.json").write_text(json.dumps(to_plain(review), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / f"{stem}.md").write_text(render_publication_readiness_review(review), encoding="utf-8")
        (reviews_dir / fix_list_name).write_text(render_publication_fix_list(review), encoding="utf-8")

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


@dataclass(slots=True)
class _PublicationReadinessContext:
    spec: SequentialSpecificityBenchmarkSpec
    after_related_work: bool
    main_analysis: MainAnalysisResult | None
    pilot_analysis: PilotAnalysisResult | None
    related_work_status: RelatedWorkCompletionStatus | None
    prior_work_dossier: SelectedBenchmarkPriorWorkDossier | None
    positioning_report: PositioningReport | None
    related_work_matrix_v2: SelectedBenchmarkRelatedWorkMatrixV2 | None
    baseline_strength: BaselineStrengthAssessment | None
    main_power_decision: MainPowerDecision | None
    manuscript_payloads: list[dict[str, Any]]
    manuscript_text: str
    manuscript_paths: list[str]
    traceability_payloads: list[dict[str, Any]]
    traceability_paths: list[str]

    @classmethod
    def from_benchmark(
        cls,
        builder: SelectedBenchmarkReviewerPanelBuilder,
        benchmark_id: str,
        *,
        after_related_work: bool = False,
    ) -> _PublicationReadinessContext:
        spec = builder.benchmark_manager.load_spec(benchmark_id)
        main_analysis = _latest_main_analysis(builder, benchmark_id)
        pilot_analysis = _latest_pilot_analysis(builder, benchmark_id)
        related_work_status = _related_work_completion_status(builder, benchmark_id, refresh=False)
        prior_work_dossier = _selected_prior_work_dossier(builder, benchmark_id, refresh=after_related_work)
        positioning_report = _selected_positioning_report(builder, benchmark_id, refresh=after_related_work)
        related_work_matrix_v2 = _selected_related_work_matrix_v2(builder, benchmark_id, refresh=after_related_work)
        baseline_strength = builder.baseline_manager.assess_baseline_strength(benchmark_id)
        main_power_decision = MainPowerManager(builder.config).latest_alpha_decision(benchmark_id, alpha_level=0.001)
        manuscript_payloads, manuscript_text, manuscript_paths = _publication_manuscript_artifacts(builder, spec.project_id)
        traceability_payloads, traceability_paths = _publication_traceability_artifacts(builder, spec.project_id)
        return cls(
            spec=spec,
            after_related_work=after_related_work,
            main_analysis=main_analysis,
            pilot_analysis=pilot_analysis,
            related_work_status=related_work_status,
            prior_work_dossier=prior_work_dossier,
            positioning_report=positioning_report,
            related_work_matrix_v2=related_work_matrix_v2,
            baseline_strength=baseline_strength,
            main_power_decision=main_power_decision,
            manuscript_payloads=manuscript_payloads,
            manuscript_text=manuscript_text,
            manuscript_paths=manuscript_paths,
            traceability_payloads=traceability_payloads,
            traceability_paths=traceability_paths,
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


def render_publication_readiness_review(review: PublicationReadinessReview) -> str:
    lines = [
        f"# Publication Readiness Review `{review.benchmark_id}`",
        "",
        f"- Readiness: `{review.readiness}`",
        f"- Confidence: `{review.confidence}`",
        f"- Fatal blockers: {len(review.fatal_blockers)}",
        f"- Major blockers: {len(review.major_blockers)}",
        "",
        "## Fatal Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in review.fatal_blockers] or ["- none"])
    lines.extend(["", "## Major Blockers", ""])
    lines.extend([f"- {item}" for item in review.major_blockers] or ["- none"])
    lines.extend(["", "## Required Revisions", ""])
    lines.extend([f"- {item}" for item in review.required_revisions] or ["- none"])
    lines.extend(["", "## Conservative Claim Boundary", ""])
    lines.extend(
        [
            "- Synthetic-only evidence cannot support deployment-validity claims.",
            "- Conference-candidate status requires main results, real related-work coverage, required baselines, "
            "powered alpha claims, and traceability.",
            "- Pilot-only results can stop at workshop positioning or not-ready status when caveats are insufficient.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_publication_fix_list(review: PublicationReadinessReview) -> str:
    lines = [
        f"# Publication Readiness Fix List `{review.benchmark_id}`",
        "",
        f"- Readiness: `{review.readiness}`",
        f"- Confidence: `{review.confidence}`",
        "",
        "## Fatal Fixes",
        "",
    ]
    lines.extend([f"- {item}" for item in review.fatal_blockers] or ["- none"])
    lines.extend(["", "## Major Fixes", ""])
    lines.extend([f"- {item}" for item in review.major_blockers] or ["- none"])
    lines.extend(["", "## Required Revisions", ""])
    lines.extend([f"- {item}" for item in review.required_revisions] or ["- none"])
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
    negations = [
        "does not claim deployment validity",
        "do not claim deployment validity",
        "no deployment validity",
        "does not establish deployment validity",
        "does not establish real-world deployment validity",
        "do not establish deployment validity",
        "do not establish real-world deployment validity",
        "do not prove real-world deployment validity",
        "not deployment evidence",
        "not evidence that a deployed monitor",
        "cannot establish deployment validity",
        "cannot establish real-world deployment validity",
        "cannot support deployment validity claims",
        "deployment validity is not established",
        "deployment validity is not claimed",
        "deployment-validity claims are blocked",
        "real-world validity is outside scope",
        "synthetic evidence alone never establishes deployment validity",
        "no synthetic main result establishes deployment validity",
        "cannot support deployment-validity claims",
        "no real-world deployment-validity claim",
        "not real-world deployment-validity claims",
        "do not imply real-world deployment validity",
        "synthetic data does not establish real-world deployment validity",
        "not deployment-validity evidence",
        "must not be read as deployment validity",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", lowered.replace("\n", " "))
    for sentence in sentences:
        if any(marker in sentence for marker in deployment_markers) and not any(negation in sentence for negation in negations):
            return True
    return False


def _latest_main_analysis(builder: SelectedBenchmarkReviewerPanelBuilder, benchmark_id: str) -> MainAnalysisResult | None:
    try:
        return MainAnalysisManager(builder.config).load_latest_for_benchmark(benchmark_id)
    except FileNotFoundError:
        return None


def _related_work_completion_status(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
    *,
    refresh: bool = False,
) -> RelatedWorkCompletionStatus | None:
    try:
        manager = RelatedWorkCompletionManager(builder.config)
        return manager.complete(benchmark_id) if refresh else manager.load_status(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _selected_prior_work_dossier(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
    *,
    refresh: bool = False,
) -> SelectedBenchmarkPriorWorkDossier | None:
    manager = SelectedBenchmarkPriorWorkRefreshManager(builder.config)
    try:
        path = manager.dossier_path(benchmark_id)
    except FileNotFoundError:
        return None
    if refresh:
        try:
            return manager.refresh(benchmark_id)
        except (FileNotFoundError, ValueError, TypeError):
            return None
    if not path.exists():
        return None
    try:
        return manager.load_or_refresh(benchmark_id)
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _selected_positioning_report(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
    *,
    refresh: bool = False,
) -> PositioningReport | None:
    manager = SelectedBenchmarkPositioningManager(builder.config)
    try:
        path = manager.report_path(benchmark_id)
    except FileNotFoundError:
        return None
    if refresh:
        try:
            return manager.build(benchmark_id)
        except (FileNotFoundError, ValueError, TypeError):
            return None
    if not path.exists():
        return None
    try:
        return manager.load_or_build(benchmark_id)
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _selected_related_work_matrix_v2(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    benchmark_id: str,
    *,
    refresh: bool = False,
) -> SelectedBenchmarkRelatedWorkMatrixV2 | None:
    manager = SelectedBenchmarkRelatedWorkMatrixV2Manager(builder.config)
    try:
        path = manager.matrix_path(benchmark_id)
    except FileNotFoundError:
        return None
    if refresh:
        try:
            return manager.build(benchmark_id)
        except (FileNotFoundError, ValueError, TypeError):
            return None
    if not path.exists():
        return None
    try:
        return manager.load_or_build(benchmark_id)
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _publication_manuscript_artifacts(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    project_id: str,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    root = builder._benchmark_dir(project_id)
    payloads: list[dict[str, Any]] = []
    texts: list[str] = []
    paths: list[str] = []
    for directory_name in ["main_manuscript", "pilot_manuscript", "manuscript", "paper_package"]:
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or "traceability" in path.name.lower():
                continue
            if path.suffix == ".json":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    payloads.append(payload)
                    texts.append(json.dumps(payload, sort_keys=True))
                    paths.append(str(path))
            elif path.suffix in {".md", ".txt"}:
                text = path.read_text(encoding="utf-8")
                texts.append(text)
                paths.append(str(path))
    return payloads, "\n".join(texts), paths


def _publication_traceability_artifacts(
    builder: SelectedBenchmarkReviewerPanelBuilder,
    project_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    root = builder._benchmark_dir(project_id)
    payloads: list[dict[str, Any]] = []
    paths: list[str] = []
    for directory_name in ["main_manuscript", "pilot_manuscript", "manuscript", "paper_package"]:
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*traceability*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
                paths.append(str(path))
    return payloads, paths


def _review_result_evidence(
    context: _PublicationReadinessContext,
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    if context.main_analysis is None and context.pilot_analysis is None:
        major_blockers.append("No main or pilot result analysis is available for publication review.")
        required_revisions.append("Run `gapforge selected-main-analysis` or `gapforge selected-pilot-analysis` before readiness review.")
        return
    if context.main_analysis is not None:
        material_blockers = [item for item in context.main_analysis.publication_blockers if not _deployment_validity_only(item)]
        if material_blockers:
            major_blockers.extend(material_blockers)
            required_revisions.append("Resolve main-result publication blockers before claiming publication readiness.")
        return
    required_revisions.append("Results are pilot-only; add main-scale results before conference-candidate positioning.")


def _review_related_work_completion(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    _review_related_work_matrix_v2(context, fatal_blockers, major_blockers, required_revisions)
    if context.after_related_work and context.related_work_matrix_v2 is not None and not context.related_work_matrix_v2.missing_categories:
        return
    status = context.related_work_status
    if status is None:
        major_blockers.append("Related work completion status is missing.")
        required_revisions.append("Run `gapforge selected-related-work-complete` and attach real paper records.")
        return
    if status.real_paper_count == 0:
        fatal_blockers.append("Missing real related work: no required category has real attached paper records.")
    if status.missing_categories:
        major_blockers.append("Missing real related work categories: " + ", ".join(status.missing_categories))
        required_revisions.append("Complete required related-work categories with real paper records; fallback-only records do not count.")
    if status.novelty_status in {"duplicate", "blocked", "fatal_duplicate"}:
        fatal_blockers.append(f"Novelty status is fatal: `{status.novelty_status}`.")


def _review_related_work_matrix_v2(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    matrix = context.related_work_matrix_v2
    if matrix is None:
        return
    if matrix.missing_categories:
        major_blockers.append("Matrix-v2 missing related-work categories: " + ", ".join(matrix.missing_categories))
        required_revisions.append("Complete matrix-v2 missing categories before publication readiness can pass.")
    direct_ids = [entry.paper_id for entry in matrix.entries if entry.relationship == "directly solves"]
    if direct_ids:
        fatal_blockers.append("Matrix-v2 directly-solving prior work triggers no-go/revise: " + ", ".join(direct_ids))
        required_revisions.append("Reframe the contribution or produce a revise/no-go decision before manuscript readiness.")
    if matrix.must_cite_ids:
        required_revisions.append(
            "Ensure matrix-v2 must-cite papers appear in the manuscript bibliography: " + ", ".join(matrix.must_cite_ids)
        )
    if matrix.baseline_source_ids:
        required_revisions.append("Feed matrix-v2 baseline-source papers into the baseline plan: " + ", ".join(matrix.baseline_source_ids))


def _review_prior_work_dossier(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    dossier = context.prior_work_dossier
    if dossier is None:
        if not context.after_related_work:
            return
        major_blockers.append("Closest prior-work dossier is missing.")
        required_revisions.append("Run `gapforge selected-prior-work-refresh` before publication-readiness rerun.")
        return
    if dossier.novelty_status == "duplicate":
        fatal_blockers.append("Closest prior-work dossier marks the contribution as duplicate.")
        required_revisions.append("Issue a no-go or reframe the contribution around a decisive difference.")
    elif dossier.novelty_status == "unknown":
        major_blockers.append("Closest prior-work dossier novelty status is unknown.")
        required_revisions.append("Resolve missing related-work categories or closest-prior-work evidence before readiness can pass.")
    elif dossier.novelty_status == "weak":
        major_blockers.append("Closest prior-work dossier marks novelty as weak; publication claims must be downgraded.")
        required_revisions.append("Use workshop/evaluation-protocol positioning unless a decisive difference is established.")


def _review_contribution_positioning(
    context: _PublicationReadinessContext,
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    report = context.positioning_report
    if report is None:
        if not context.after_related_work:
            return
        required_revisions.append("Generate selected contribution positioning before final manuscript readiness.")
        return
    for risk in report.reviewer_risks:
        if "novelty is unknown" in risk.lower():
            major_blockers.append(risk)
    if report.citation_requirements:
        required_revisions.extend(report.citation_requirements)


def _review_baseline_strength(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    assessment = context.baseline_strength
    if assessment is None:
        major_blockers.append("Baseline strength assessment is missing.")
        required_revisions.append("Run `gapforge selected-baseline-strength` before publication review.")
        return
    if assessment.missing_baselines:
        major_blockers.append("Missing required baselines: " + ", ".join(assessment.missing_baselines))
        required_revisions.append("Implement or restore every required baseline before strong contribution claims.")
    leakage_blockers = [item for item in assessment.blockers if "leakage" in item.lower()]
    if leakage_blockers:
        fatal_blockers.extend(leakage_blockers)
        required_revisions.append("Recalibrate thresholds on honest/null data only before publication claims.")
    elif assessment.blockers:
        major_blockers.extend(assessment.blockers)


def _review_alpha_power_claims(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    claims_alpha_0001 = _claims_alpha_0001(context.manuscript_text)
    decision = context.main_power_decision
    if decision is None and context.main_analysis is not None:
        major_blockers.append("Main alpha=0.001 power decision is missing from the review package.")
        required_revisions.append("Run `gapforge selected-main-alpha-decision --alpha 0.001` and cite the decision in release notes.")
    if claims_alpha_0001:
        powered_by_decision = decision is not None and decision.decision == "power"
        powered_by_results = context.main_analysis is not None and "0.001" in context.main_analysis.powered_alpha_levels
        if not (powered_by_decision and powered_by_results):
            fatal_blockers.append(
                "Underpowered alpha=0.001 claim: manuscript claims alpha=0.001 without a powered main result and power decision."
            )
            required_revisions.append(
                "Remove, downgrade, or defer alpha=0.001 publication claims unless the computed negative trace count is met."
            )
    if decision is not None and decision.decision != "power":
        required_revisions.append(
            f"Release notes must state alpha={decision.alpha_level:g} decision `{decision.decision}`: {decision.reason}"
        )


def _review_manuscript_traceability(
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
    required_revisions: list[str],
) -> None:
    if not context.manuscript_payloads and not context.manuscript_text.strip():
        major_blockers.append("Manuscript package is missing from the publication-readiness review inputs.")
        required_revisions.append("Generate or attach the manuscript package before publication readiness is claimed.")
    if _deployment_overclaim(context.manuscript_text) or _payload_flag(context.manuscript_payloads, "deployment_validity_claim"):
        fatal_blockers.append("Synthetic-only deployment claim is present in the manuscript package.")
        required_revisions.append("Remove deployment-validity claims or replace them with explicit synthetic-evidence limitations.")
    if not context.traceability_payloads:
        major_blockers.append("Traceability report is missing from the manuscript package.")
        required_revisions.append("Generate a traceability report linking claims to artifacts before publication readiness.")
        return
    for payload in context.traceability_payloads:
        fatal_items = _string_list(payload.get("fatal_blockers")) + _string_list(payload.get("fatal_flaws"))
        if fatal_items:
            fatal_blockers.extend(f"Traceability fatal blocker: {item}" for item in fatal_items)
        status = str(payload.get("status", "")).lower()
        traceability_passed = payload.get("traceability_passed", True)
        if status and status not in {"pass", "passed", "ok"}:
            major_blockers.append(f"Traceability report status is `{status}`.")
        if traceability_passed is False:
            major_blockers.append("Traceability report did not pass.")


def _publication_readiness(
    *,
    context: _PublicationReadinessContext,
    fatal_blockers: list[str],
    major_blockers: list[str],
) -> str:
    if any(_no_go_blocker(item) for item in fatal_blockers):
        return "no_go"
    if any(_related_work_blocker(item) for item in [*fatal_blockers, *major_blockers]):
        return "revise_related_work"
    if fatal_blockers:
        return "revise_benchmark"
    if _weak_novelty(context) and (context.main_analysis is not None or context.pilot_analysis is not None):
        return "workshop_candidate"
    if context.main_analysis is not None and not major_blockers:
        return "publication_candidate"
    if context.pilot_analysis is not None and not major_blockers:
        return "workshop_candidate"
    return "revise_benchmark"


def _publication_confidence(
    readiness: str,
    context: _PublicationReadinessContext,
    *,
    fatal_blockers: list[str],
    major_blockers: list[str],
) -> str:
    if readiness == "publication_candidate":
        return "medium"
    if readiness == "workshop_candidate":
        return "medium" if context.related_work_status and context.baseline_strength else "low"
    if fatal_blockers or major_blockers:
        return "high"
    return "low"


def _related_work_blocker(item: str) -> bool:
    lowered = item.lower()
    return any(marker in lowered for marker in ["related work", "related-work", "prior-work", "matrix-v2", "novelty status is unknown"])


def _weak_novelty(context: _PublicationReadinessContext) -> bool:
    return context.prior_work_dossier is not None and context.prior_work_dossier.novelty_status == "weak"


def _claims_alpha_0001(text: str) -> bool:
    lowered = text.lower()
    markers = ["alpha=0.001", "alpha = 0.001", "alpha 0.001", "0.001 specificity", "one-in-a-thousand"]
    safe_context = [
        "not claimed",
        "not claim",
        "unless powered",
        "underpowered",
        "blocked",
        "dropped",
        "defer",
        "missing",
        "decision is",
        "decision:",
    ]
    sentences = lowered.replace("\n", ".").split(".")
    for sentence in sentences:
        if any(marker in sentence for marker in markers) and not any(pattern in sentence for pattern in safe_context):
            return True
    return False


def _payload_flag(payloads: list[dict[str, Any]], key: str) -> bool:
    for payload in payloads:
        value = payload.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.lower() in {"true", "yes", "claimed"}:
            return True
    return False


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _deployment_validity_only(blocker: str) -> bool:
    lowered = blocker.lower()
    return "synthetic-only" in lowered and "deployment-validity" in lowered


def _no_go_blocker(blocker: str) -> bool:
    lowered = blocker.lower()
    return (
        "duplicate" in lowered
        or "directly-solving" in lowered
        or "directly solving" in lowered
        or "no-go" in lowered
        or "novelty status is fatal" in lowered
        or "validity failure" in lowered
    )


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
