"""Drastic OpenReview-style reviewer panel for publication-candidate papers."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.artifact_eval.package import load_artifact_evaluation_package
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import ManuscriptSection, ManuscriptState, ManuscriptTraceabilityReport
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.models import (
    ArtifactEvaluationPackage,
    ExperimentResultArtifact,
    Provenance,
    RelatedWorkMatrix,
    ResearchProgramState,
    ReviewerReview,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.review_training.evaluate import ReviewerEvaluationResult
from gapforge.review_training.taxonomy import ReviewTaxonomyReport
from gapforge.reviewers.scoring import score_from_issues
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.selected_benchmark.vetted_experiment import (
    SelectedVettedBenchmarkExperimentManager,
    VettedBenchmarkExperimentPlan,
    VettedBenchmarkExperimentResult,
)
from gapforge.selected_benchmark.vetted_mapping import SelectedBenchmarkVettedMappingManager, VettedBenchmarkMappingReport
from gapforge.state import ResearchStateManager, utc_now_iso

FAKE_CITATION_PATTERN = re.compile(
    r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)? et al\.?,?\s+(?:19|20)\d{2}\b|"
    r"\[(?:\d+|[A-Z][A-Za-z]+(?:19|20)\d{2})\]|"
    r"\bdoi:\s*\S+",
)


@dataclass(slots=True)
class DrasticReviewPanel:
    id: str
    target_id: str
    target_type: str
    reviewer_reports: list[ReviewerReview] = field(default_factory=list)
    area_chair_summary: str = ""
    fatal_flaws: list[str] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    borderline_decision_analysis: str = ""
    likely_scores: dict[str, float] = field(default_factory=dict)
    likely_decision: str = "unknown"
    workshop_candidate: bool = False
    taxonomy_issue_counts: dict[str, int] = field(default_factory=dict)
    calibration_summary: dict[str, str] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="drastic-review-panel"))


class DrasticReviewPanelBuilder:
    """Build a harsher reviewer panel calibrated by review-taxonomy issue patterns."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscripts = ManuscriptManager(config)
        self.projects = ProjectMemoryManager(config)
        self.runs = ResearchStateManager(config)
        self.workspaces = ExperimentWorkspaceManager(config)
        self.selected_benchmarks = SelectedBenchmarkManager(config)
        self.vetted_mappings = SelectedBenchmarkVettedMappingManager(config)
        self.vetted_experiments = SelectedVettedBenchmarkExperimentManager(config)

    def review_manuscript(self, manuscript_id: str) -> DrasticReviewPanel:
        context = _ManuscriptDrasticContext.from_manuscript(self, manuscript_id)
        return self._build_panel(
            target_id=manuscript_id,
            target_type="manuscript",
            output_dir=self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic",
            reviews=[
                _novelty_skeptic_review(context),
                _empirical_rigor_review(context),
                _benchmark_validity_review(context),
                _clarity_framing_review(context),
                _reproducibility_artifact_review(context),
            ],
            source_ids=context.source_ids(),
            taxonomy_issue_counts=context.taxonomy_issue_counts,
            calibration_summary=context.calibration_summary,
        )

    def review_benchmark(self, benchmark_id: str) -> DrasticReviewPanel:
        context = _BenchmarkDrasticContext.from_benchmark(self, benchmark_id)
        spec = context.spec
        output_dir = self._benchmark_review_dir(spec.project_id)
        return self._build_panel(
            target_id=benchmark_id,
            target_type="benchmark",
            output_dir=output_dir,
            reviews=[
                _benchmark_novelty_skeptic_review(context),
                _benchmark_empirical_rigor_review(context),
                _benchmark_dataset_validity_review(context),
                _benchmark_clarity_review(context),
                _benchmark_artifact_review(context),
            ],
            source_ids=context.source_ids(),
            taxonomy_issue_counts=context.taxonomy_issue_counts,
            calibration_summary=context.calibration_summary,
        )

    def render_manuscript_report(self, manuscript_id: str) -> str:
        panel = self._ensure_manuscript_panel(manuscript_id)
        markdown = render_drastic_review_panel(panel)
        output_dir = self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "drastic_review_panel.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _ensure_manuscript_panel(self, manuscript_id: str) -> DrasticReviewPanel:
        path = self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic" / "drastic_review_panel.json"
        if path.exists():
            return from_dict(DrasticReviewPanel, json.loads(path.read_text(encoding="utf-8")))
        return self.review_manuscript(manuscript_id)

    def _build_panel(
        self,
        *,
        target_id: str,
        target_type: str,
        output_dir: Path,
        reviews: list[ReviewerReview],
        source_ids: list[str],
        taxonomy_issue_counts: dict[str, int],
        calibration_summary: dict[str, str],
    ) -> DrasticReviewPanel:
        for review in reviews:
            _validate_review(review)
        fatal_flaws = _unique(flaw for review in reviews for flaw in review.fatal_flaws)
        required_revisions = _unique(fix for review in reviews for fix in review.required_fixes)
        likely_scores = {review.reviewer_id: review.score for review in reviews}
        likely_decision, workshop_candidate = _decision_from_reviews(reviews, fatal_flaws)
        area_chair = _area_chair_review(reviews, likely_decision, workshop_candidate, fatal_flaws, required_revisions)
        _validate_review(area_chair)
        all_reviews = [*reviews, area_chair]
        likely_scores[area_chair.reviewer_id] = area_chair.score
        panel = DrasticReviewPanel(
            id=f"drastic-review-panel-{target_type}-{target_id}",
            target_id=target_id,
            target_type=target_type,
            reviewer_reports=all_reviews,
            area_chair_summary=area_chair.strengths[0] if area_chair.strengths else "",
            fatal_flaws=fatal_flaws,
            required_revisions=required_revisions,
            borderline_decision_analysis=_borderline_analysis(
                likely_decision=likely_decision,
                workshop_candidate=workshop_candidate,
                fatal_flaws=fatal_flaws,
                required_revisions=required_revisions,
                average_score=_average_score(reviews),
            ),
            likely_scores=likely_scores,
            likely_decision=likely_decision,
            workshop_candidate=workshop_candidate,
            taxonomy_issue_counts=taxonomy_issue_counts,
            calibration_summary=calibration_summary,
            provenance=Provenance(
                created_by_skill="drastic-review-panel",
                source_ids=_unique([target_id, *source_ids]),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Generated a deliberately harsh OpenReview-style panel with evidence-linked criticisms and no invented citations."
                ),
            ),
        )
        self._write_panel(panel, output_dir)
        return panel

    def _write_panel(self, panel: DrasticReviewPanel, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "drastic_review_panel.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (output_dir / "drastic_review_panel.md").write_text(render_drastic_review_panel(panel), encoding="utf-8")
        (output_dir / "fatal_flaws.md").write_text(render_fatal_flaws(panel), encoding="utf-8")
        (output_dir / "borderline_decision_analysis.md").write_text(render_borderline_decision_analysis(panel), encoding="utf-8")
        (output_dir / "required_revision_plan.md").write_text(render_required_revision_plan(panel), encoding="utf-8")
        (output_dir / "likely_scores.json").write_text(json.dumps(panel.likely_scores, indent=2) + "\n", encoding="utf-8")

    def _benchmark_review_dir(self, project_id: str) -> Path:
        program = self.projects.load_project(project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "reviews" / "drastic"


@dataclass(slots=True)
class _ManuscriptDrasticContext:
    state: ManuscriptState
    program: ResearchProgramState
    sections: dict[str, str]
    traceability_report: ManuscriptTraceabilityReport
    related_work_matrix: RelatedWorkMatrix | None
    result_artifacts: list[ExperimentResultArtifact]
    artifact_package: ArtifactEvaluationPackage | None
    artifact_package_error: str
    taxonomy_issue_counts: dict[str, int]
    calibration_summary: dict[str, str]

    @classmethod
    def from_manuscript(cls, builder: DrasticReviewPanelBuilder, manuscript_id: str) -> _ManuscriptDrasticContext:
        state = builder.manuscripts.load_state(manuscript_id)
        program = builder.projects.load_project(state.manuscript.project_id)
        return cls(
            state=state,
            program=program,
            sections=_load_section_texts(builder.manuscripts, state),
            traceability_report=ManuscriptTraceabilityAuditor(builder.config).audit(manuscript_id),
            related_work_matrix=_related_work_matrix(builder, program, state.manuscript.direction_id),
            result_artifacts=_result_artifacts(builder.workspaces, state.manuscript.workspace_id),
            artifact_package=_artifact_package(builder.config, manuscript_id),
            artifact_package_error=_artifact_package_error(builder.config, manuscript_id),
            taxonomy_issue_counts=_latest_taxonomy_issue_counts(builder.config),
            calibration_summary=_latest_calibration_summary(builder.config),
        )

    def source_ids(self) -> list[str]:
        return _unique(
            [
                self.state.manuscript.id,
                self.state.manuscript.project_id,
                self.state.manuscript.workspace_id,
                self.traceability_report.manuscript_id,
                self.related_work_matrix.direction_id if self.related_work_matrix else "",
                self.artifact_package.id if self.artifact_package else "",
                *[artifact.id for artifact in self.result_artifacts],
            ]
        )


@dataclass(slots=True)
class _BenchmarkDrasticContext:
    spec: SequentialSpecificityBenchmarkSpec
    mapping_report: VettedBenchmarkMappingReport | None
    experiment_plan: VettedBenchmarkExperimentPlan | None
    experiment_result: VettedBenchmarkExperimentResult | None
    taxonomy_issue_counts: dict[str, int]
    calibration_summary: dict[str, str]

    @classmethod
    def from_benchmark(cls, builder: DrasticReviewPanelBuilder, benchmark_id: str) -> _BenchmarkDrasticContext:
        spec = builder.selected_benchmarks.load_spec(benchmark_id)
        mapping_report = _load_mapping_report(builder, benchmark_id)
        experiment_plan = _load_vetted_plan(builder, benchmark_id)
        experiment_result = _load_vetted_result(builder, experiment_plan)
        return cls(
            spec=spec,
            mapping_report=mapping_report,
            experiment_plan=experiment_plan,
            experiment_result=experiment_result,
            taxonomy_issue_counts=_latest_taxonomy_issue_counts(builder.config),
            calibration_summary=_latest_calibration_summary(builder.config),
        )

    def source_ids(self) -> list[str]:
        return _unique(
            [
                self.spec.id,
                self.spec.project_id,
                self.mapping_report.id if self.mapping_report else "",
                self.experiment_plan.id if self.experiment_plan else "",
                self.experiment_result.id if self.experiment_result else "",
            ]
        )


def render_drastic_review_panel(panel: DrasticReviewPanel) -> str:
    lines = [
        f"# Drastic Review Panel `{panel.target_id}`",
        "",
        f"- Target type: `{panel.target_type}`",
        f"- Likely decision: `{panel.likely_decision}`",
        f"- Workshop candidate: `{str(panel.workshop_candidate).lower()}`",
        f"- Fatal flaws: {len(panel.fatal_flaws)}",
        f"- Required revisions: {len(panel.required_revisions)}",
        "",
        "## Area Chair",
        "",
        panel.area_chair_summary or "No area-chair summary generated.",
        "",
        "## Reviewer Reports",
        "",
    ]
    for review in panel.reviewer_reports:
        lines.extend(
            [
                f"### {review.reviewer_id}: {review.role}",
                "",
                f"- Likely score: {review.score:.1f}",
                f"- Confidence: {review.confidence}",
                f"- Evidence links: {', '.join(review.evidence_or_prior_work) or 'none'}",
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
        lines.extend(["", "**Required Revisions**", ""])
        lines.extend([f"- {item}" for item in review.required_fixes] or ["- none"])
        lines.extend(["", "**Fatal Flaws**", ""])
        lines.extend([f"- {item}" for item in review.fatal_flaws] or ["- none"])
        lines.append("")
    lines.extend(
        [
            "## Fatal Flaws",
            "",
            render_fatal_flaws(panel).rstrip(),
            "",
            "## Borderline Decision Analysis",
            "",
            panel.borderline_decision_analysis,
            "",
            "## Required Revision Plan",
            "",
            render_required_revision_plan(panel).rstrip(),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_fatal_flaws(panel: DrasticReviewPanel) -> str:
    lines = [f"# Fatal Flaws `{panel.target_id}`", ""]
    lines.extend([f"- {flaw}" for flaw in panel.fatal_flaws] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_borderline_decision_analysis(panel: DrasticReviewPanel) -> str:
    return f"# Borderline Decision Analysis `{panel.target_id}`\n\n{panel.borderline_decision_analysis.rstrip()}\n"


def render_required_revision_plan(panel: DrasticReviewPanel) -> str:
    lines = [
        f"# Required Revision Plan `{panel.target_id}`",
        "",
        "These are revision requirements, not rebuttal talking points. Missing evidence should remain missing until actually produced.",
        "",
    ]
    lines.extend([f"- {item}" for item in panel.required_revisions] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def validate_review_text_no_fake_citations(text: str) -> None:
    if FAKE_CITATION_PATTERN.search(text):
        raise ValueError("Drastic reviewer text contains citation-shaped content that is not tied to a stored source artifact.")


def _novelty_skeptic_review(context: _ManuscriptDrasticContext) -> ReviewerReview:
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    related_text = context.sections.get("related_work", "")
    matrix = context.related_work_matrix
    if not related_text:
        fatal.append("missing:related_work section is absent, so novelty cannot be evaluated against closest prior work.")
        required.append("section:related_work add a closest-prior-work comparison before asking reviewers to accept the contribution.")
    else:
        evidence.append("section:related_work")
    if matrix is None:
        fatal.append("missing:related_work_matrix no auditable related-work matrix is available for novelty calibration.")
        required.append("artifact:related_work_matrix provide must-read papers, baseline papers, and missing-category accounting.")
    else:
        evidence.append(f"related-work-matrix:{matrix.direction_id}")
        if matrix.missing_categories:
            weaknesses.append(
                "related-work-matrix:missing_categories unresolved categories remain: " + ", ".join(matrix.missing_categories)
            )
            required.append("related-work-matrix:missing_categories close or explicitly justify every missing category.")
        if not matrix.must_read_paper_ids:
            weaknesses.append("related-work-matrix:must_read_paper_ids no must-read prior work is recorded.")
    if context.traceability_report.novelty_claim_count == 0:
        weaknesses.append("traceability:novelty_claim_count no explicit novelty claim is tracked for reviewer scrutiny.")
    return _review(
        reviewer_id="R1",
        role="Reviewer 1: novelty skeptic",
        strengths=[
            "section:introduction frames a submission target."
            if context.sections.get("introduction")
            else "No novelty-facing strength survives review."
        ],
        weaknesses=weaknesses,
        questions=["missing:evidence Which exact prior benchmark or audit protocol is closest, and what is the smallest real delta?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _empirical_rigor_review(context: _ManuscriptDrasticContext) -> ReviewerReview:
    body = _all_section_text(context.sections)
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    evidence = [f"workspace:{context.state.manuscript.workspace_id}"]
    if not context.result_artifacts:
        fatal.append("missing:benchmark_results no persisted benchmark result artifacts are available for empirical claims.")
        required.append(
            "artifact:benchmark_results add result artifacts with metrics, seeds, splits, and uncertainty before empirical claims."
        )
    else:
        evidence.extend(f"result:{artifact.id}" for artifact in context.result_artifacts)
    if "baseline" not in body and not _related_baselines(context.related_work_matrix):
        weaknesses.append("missing:baseline evidence no baseline comparison is visible in manuscript text or related-work matrix.")
        required.append("section:experiments add baseline definitions and report baseline performance separately from proposed monitors.")
    if "ablation" not in body:
        weaknesses.append("missing:ablation no ablation or component-isolation evidence is visible.")
        required.append("section:experiments add ablation or explicitly mark the paper as not making component claims.")
    if "confidence interval" not in body and "uncertainty" not in body and "power" not in body:
        weaknesses.append("section:results uncertainty/power accounting is not visible enough for low-FPR claims.")
        required.append("section:results report uncertainty and power gates for low false-positive-rate estimates.")
    return _review(
        reviewer_id="R2",
        role="Reviewer 2: empirical rigor and baselines",
        strengths=["artifact:workspace manuscript is linked to an experiment workspace."],
        weaknesses=weaknesses,
        questions=["missing:evidence Are negative samples sufficient for every stated low-FPR threshold?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _benchmark_validity_review(context: _ManuscriptDrasticContext) -> ReviewerReview:
    body = _all_section_text(context.sections)
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    evidence = ["section:method" if context.sections.get("method") else "missing:method"]
    synthetic = "synthetic" in body
    real_grounding = any(term in body for term in ["vetted", "real benchmark", "adapter", "existing benchmark", "openreview"])
    if synthetic and not real_grounding:
        fatal.append(
            "section:method synthetic-only benchmark evidence lacks vetted-benchmark grounding or an explicit protocol-only boundary."
        )
        required.append(
            "section:limitations label synthetic-only evidence as protocol scaffolding; add vetted auxiliary evidence if available."
        )
    if "low-fpr" in body or "false-positive" in body or "specificity" in body:
        if "sequential" not in body:
            weaknesses.append("section:method low-FPR specificity claims are not visibly tied to sequential evaluation windows.")
            required.append("section:method define per-window and sequence-level evaluation units.")
    if not context.sections.get("limitations"):
        fatal.append("missing:limitations no limitations section is available for benchmark-validity boundaries.")
        required.append("section:limitations add dataset validity, adaptation, and deployment-validity limitations.")
    return _review(
        reviewer_id="R3",
        role="Reviewer 3: benchmark validity and dataset criticism",
        strengths=[
            "section:method benchmark framing is inspectable."
            if context.sections.get("method")
            else "No benchmark-validity strength survives review."
        ],
        weaknesses=weaknesses,
        questions=["missing:evidence Which claims are supported by real task substrates versus new synthetic protocol design?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _clarity_framing_review(context: _ManuscriptDrasticContext) -> ReviewerReview:
    intro = context.sections.get("introduction", "")
    body = _all_section_text(context.sections)
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    evidence = ["section:introduction" if intro else "missing:introduction"]
    if not intro:
        fatal.append("missing:introduction no introduction section exists to frame contribution and audience.")
        required.append("section:introduction add contribution, scope, and non-claim boundaries.")
    if "contribution" not in intro and "we " not in intro:
        weaknesses.append("section:introduction contribution statement is not explicit enough for a top-conference reviewer.")
        required.append("section:introduction state exactly what is contributed: protocol, benchmark, adapters, or empirical evidence.")
    if context.traceability_report.unsupported_claims:
        fatal.append(f"traceability:unsupported_claims {len(context.traceability_report.unsupported_claims)} unsupported claim(s) remain.")
        required.append("traceability:unsupported_claims soften, remove, or support every unsupported claim before submission.")
    if any(term in body for term in ["state-of-the-art", "sota", "first ", "solves "]):
        weaknesses.append("section:claims possible overclaiming language remains visible.")
        required.append("section:claims replace SOTA/first/solves language unless traceability proves it.")
    return _review(
        reviewer_id="R4",
        role="Reviewer 4: clarity/contribution framing",
        strengths=["traceability:claims claim tracking exists."],
        weaknesses=weaknesses,
        questions=["section:introduction What should a reviewer believe even if all auxiliary benchmark results are weak?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _reproducibility_artifact_review(context: _ManuscriptDrasticContext) -> ReviewerReview:
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    package = context.artifact_package
    if package is None:
        fatal.append(f"missing:artifact_package no artifact evaluation package is loadable ({context.artifact_package_error}).")
        required.append("artifact:artifact_evaluation_package export a review-ready artifact package with install and run instructions.")
    else:
        evidence.append(f"artifact-package:{package.id}")
        if package.status != "review_ready":
            fatal.append(f"artifact-package:{package.id} status is `{package.status}`, not review_ready.")
            required.append("artifact:artifact_evaluation_package resolve package blockers before submission.")
        if not package.run_instructions:
            weaknesses.append(f"artifact-package:{package.id} no runnable commands are listed.")
            required.append("artifact:artifact_evaluation_package add exact commands for reproducing reported tables.")
    if not context.result_artifacts:
        weaknesses.append("missing:result_artifacts no result artifacts are available for reproducibility cross-checks.")
    return _review(
        reviewer_id="R5",
        role="Reviewer 5: reproducibility/artifact evaluation",
        strengths=["artifact:package checked for review readiness."],
        weaknesses=weaknesses,
        questions=["artifact:package Can an external reviewer regenerate every reported metric without private state?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _benchmark_novelty_skeptic_review(context: _BenchmarkDrasticContext) -> ReviewerReview:
    fatal: list[str] = []
    required: list[str] = []
    weaknesses: list[str] = []
    if context.mapping_report is None:
        fatal.append("missing:vetted_mapping_report no mapping to existing vetted benchmarks is available.")
        required.append("artifact:vetted_mapping_report map direct, substrate, auxiliary, sanity-check, and rejected benchmark candidates.")
    elif not context.mapping_report.primary_candidate_ids and not context.mapping_report.auxiliary_candidate_ids:
        weaknesses.append("vetted_mapping_report:no_candidates no primary or auxiliary existing benchmark support is identified.")
        required.append(
            "section:limitations explain why a new benchmark protocol is needed instead of claiming existing-benchmark validation."
        )
    return _review(
        reviewer_id="R1",
        role="Reviewer 1: novelty skeptic",
        strengths=["benchmark:spec explicit sequential specificity target exists."],
        weaknesses=weaknesses,
        questions=["missing:evidence What is the closest existing audit or monitoring benchmark, and why is it insufficient?"],
        required=required,
        fatal=fatal,
        evidence=[f"benchmark:{context.spec.id}"],
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _benchmark_empirical_rigor_review(context: _BenchmarkDrasticContext) -> ReviewerReview:
    fatal: list[str] = []
    required: list[str] = []
    weaknesses: list[str] = []
    evidence = [f"benchmark:{context.spec.id}"]
    if context.experiment_plan is None:
        fatal.append("missing:vetted_experiment_plan no vetted-adapter experiment plan exists.")
        required.append(
            "artifact:vetted_experiment_plan create a separate vetted evidence path before using existing benchmarks in claims."
        )
    else:
        evidence.append(f"vetted-experiment-plan:{context.experiment_plan.id}")
    if context.experiment_result is None:
        weaknesses.append("missing:vetted_experiment_result no vetted-adapter result has been run.")
        required.append("artifact:vetted_experiment_result run adapter experiments or label them planned only.")
    else:
        evidence.append(f"vetted-experiment-result:{context.experiment_result.id}")
        if not context.experiment_result.metric_results:
            weaknesses.append("vetted_experiment_result:metric_results no metric results are recorded.")
    if not context.spec.required_baselines:
        weaknesses.append("benchmark:required_baselines required monitor baselines are absent.")
        required.append("benchmark:required_baselines define non-learned, heuristic, and sequential-threshold baselines.")
    return _review(
        reviewer_id="R2",
        role="Reviewer 2: empirical rigor and baselines",
        strengths=[
            "benchmark:metrics low-FPR and specificity metrics are explicit."
            if context.spec.metrics
            else "No empirical strength survives review."
        ],
        weaknesses=weaknesses,
        questions=["missing:evidence Which result is synthetic-only, and which result comes from a vetted adapter?"],
        required=required,
        fatal=fatal,
        evidence=evidence,
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _benchmark_dataset_validity_review(context: _BenchmarkDrasticContext) -> ReviewerReview:
    fatal: list[str] = []
    required: list[str] = []
    weaknesses: list[str] = []
    if context.mapping_report is None:
        fatal.append("missing:vetted_mapping_report benchmark validity is unaudited against existing datasets.")
    else:
        rejected = len(context.mapping_report.rejected_candidate_ids)
        if rejected:
            weaknesses.append(f"vetted_mapping_report:rejected_candidates {rejected} candidate benchmark(s) were rejected for mismatch.")
        unsupported = [
            claim
            for mapping in context.mapping_report.mappings
            for claim in mapping.unsupported_claims
            if mapping.mapping_type != "rejected"
        ]
        if unsupported:
            weaknesses.append("vetted_mapping_report:unsupported_claims " + "; ".join(_unique(unsupported)[:3]))
    if not context.spec.limitations:
        fatal.append("benchmark:limitations limitations are absent from the benchmark spec.")
        required.append("benchmark:limitations add synthetic, real-grounding, low-FPR power, and deployment-validity limits.")
    return _review(
        reviewer_id="R3",
        role="Reviewer 3: benchmark validity and dataset criticism",
        strengths=[
            "benchmark:limitations limitations are explicit."
            if context.spec.limitations
            else "No dataset-validity strength survives review."
        ],
        weaknesses=weaknesses,
        questions=["benchmark:mapping Are auxiliary benchmarks being described as auxiliary, not as real collusion traces?"],
        required=required,
        fatal=fatal,
        evidence=[
            f"benchmark:{context.spec.id}",
            "artifact:vetted_mapping_report" if context.mapping_report else "missing:vetted_mapping_report",
        ],
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _benchmark_clarity_review(context: _BenchmarkDrasticContext) -> ReviewerReview:
    weaknesses: list[str] = []
    required: list[str] = []
    if not context.spec.benchmark_goal:
        weaknesses.append("benchmark:goal benchmark goal is missing.")
    if not context.spec.sequential_setting:
        weaknesses.append("benchmark:sequential_setting sequential setting is missing.")
        required.append("benchmark:sequential_setting define audit windows, sequence-level outcomes, and false-alarm accounting.")
    if not context.spec.monitor_inputs or not context.spec.monitor_outputs:
        weaknesses.append("benchmark:monitor_io monitor input/output contract is incomplete.")
        required.append("benchmark:monitor_io specify what monitors observe and output.")
    return _review(
        reviewer_id="R4",
        role="Reviewer 4: clarity/contribution framing",
        strengths=["benchmark:goal selected benchmark goal is explicit."],
        weaknesses=weaknesses,
        questions=["benchmark:claims Is the contribution a benchmark protocol, dataset, adapter evidence, or all three?"],
        required=required,
        fatal=[],
        evidence=[f"benchmark:{context.spec.id}"],
        major=len(weaknesses),
        fatal_count=0,
    )


def _benchmark_artifact_review(context: _BenchmarkDrasticContext) -> ReviewerReview:
    weaknesses: list[str] = []
    required: list[str] = []
    fatal: list[str] = []
    if context.experiment_result is None:
        fatal.append("missing:vetted_experiment_result no adapter execution artifact exists for artifact review.")
        required.append("artifact:vetted_experiment_result persist adapter executions and warning logs.")
    elif context.experiment_result.error_analysis_ids:
        weaknesses.append("vetted_experiment_result:error_analysis adapter warnings require explicit error analysis.")
        required.append("artifact:error_analysis include adapter warning interpretation in manuscript limitations.")
    return _review(
        reviewer_id="R5",
        role="Reviewer 5: reproducibility/artifact evaluation",
        strengths=["benchmark:spec persisted selected benchmark specification exists."],
        weaknesses=weaknesses,
        questions=["artifact:adapter_outputs Are transformed examples, labels, and splits reproducibly inspectable?"],
        required=required,
        fatal=fatal,
        evidence=[f"benchmark:{context.spec.id}"],
        major=len(weaknesses),
        fatal_count=len(fatal),
    )


def _area_chair_review(
    reviews: list[ReviewerReview],
    likely_decision: str,
    workshop_candidate: bool,
    fatal_flaws: list[str],
    required_revisions: list[str],
) -> ReviewerReview:
    summary = (
        f"area-chair:decision likely `{likely_decision}` with {len(fatal_flaws)} fatal flaw(s) and "
        f"{len(required_revisions)} required revision(s)."
    )
    if likely_decision == "reject_likely":
        summary += " If submitted now, the paper is likely reject."
    if workshop_candidate:
        summary += " The work may be a workshop candidate only after limitations and evidence labels are sharpened."
    return _review(
        reviewer_id="AC",
        role="Area Chair: decision and borderline analysis",
        strengths=[summary],
        weaknesses=[f"area-chair:scores average reviewer score is {_average_score(reviews):.1f}."],
        questions=["area-chair:borderline Can the authors produce evidence rather than rebutting missing evidence rhetorically?"],
        required=required_revisions[:8],
        fatal=fatal_flaws[:8],
        evidence=[review.reviewer_id for review in reviews],
        major=max(1, len(required_revisions) // 3),
        fatal_count=len(fatal_flaws),
    )


def _review(
    *,
    reviewer_id: str,
    role: str,
    strengths: list[str],
    weaknesses: list[str],
    questions: list[str],
    required: list[str],
    fatal: list[str],
    evidence: list[str],
    major: int,
    fatal_count: int,
) -> ReviewerReview:
    review = ReviewerReview(
        reviewer_id=reviewer_id,
        role=role,
        score=score_from_issues(base=6.0, major=major, fatal=fatal_count, minor=len(questions)),
        confidence="high" if evidence and (fatal or required) else "medium",
        strengths=_unique(strengths),
        weaknesses=_unique(weaknesses),
        questions=_unique(questions),
        required_fixes=_unique(required),
        fatal_flaws=_unique(fatal),
        evidence_or_prior_work=_unique(evidence),
        provenance=Provenance(
            created_by_skill="drastic-review-panel",
            source_ids=_unique(evidence),
            timestamp=utc_now_iso(),
            reasoning_summary="Assigned an OpenReview-style harsh reviewer role with evidence-linked criticism.",
        ),
    )
    _validate_review(review)
    return review


def _validate_review(review: ReviewerReview) -> None:
    for text in [
        review.role,
        *review.strengths,
        *review.weaknesses,
        *review.questions,
        *review.required_fixes,
        *review.fatal_flaws,
        *review.evidence_or_prior_work,
    ]:
        validate_review_text_no_fake_citations(text)
    for item in [*review.weaknesses, *review.questions, *review.required_fixes, *review.fatal_flaws]:
        if ":" not in item:
            raise ValueError(f"Drastic reviewer criticism lacks evidence linkage: {item}")


def _decision_from_reviews(reviews: list[ReviewerReview], fatal_flaws: list[str]) -> tuple[str, bool]:
    average = _average_score(reviews)
    if len(fatal_flaws) >= 2 or average < 4.0:
        return "reject_likely", average >= 3.0
    if len(fatal_flaws) == 1 or average < 5.5:
        return "borderline_reject", True
    if average < 6.5:
        return "borderline_workshop_or_weak_accept", True
    return "revise_before_submission", False


def _borderline_analysis(
    *,
    likely_decision: str,
    workshop_candidate: bool,
    fatal_flaws: list[str],
    required_revisions: list[str],
    average_score: float,
) -> str:
    lines = [
        f"Likely decision: `{likely_decision}`.",
        f"Average non-AC score: {average_score:.1f}.",
        f"Fatal flaws: {len(fatal_flaws)}.",
        f"Required revisions: {len(required_revisions)}.",
    ]
    if likely_decision == "reject_likely":
        lines.append("If submitted to a top conference in this state, the panel should be treated as likely reject.")
    if workshop_candidate:
        lines.append(
            "Workshop positioning may be plausible only if the manuscript preserves harsh limitations and labels evidence strength."
        )
    if fatal_flaws:
        lines.append("A rebuttal cannot repair missing evidence; these issues require manuscript or artifact changes.")
    return "\n".join(lines)


def _load_section_texts(manager: ManuscriptManager, state: ManuscriptState) -> dict[str, str]:
    root = manager.manuscript_root(state.manuscript.id)
    sections: dict[str, str] = {}
    for section in state.sections:
        text = _section_text(root, section)
        sections[section.section_type] = "\n".join([sections.get(section.section_type, ""), text]).strip().lower()
    return sections


def _section_text(root: Path, section: ManuscriptSection) -> str:
    path = root / section.content_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _related_work_matrix(builder: DrasticReviewPanelBuilder, program: ResearchProgramState, direction_id: str) -> RelatedWorkMatrix | None:
    for matrix in program.related_work_matrices:
        if matrix.direction_id == direction_id:
            return matrix
    for run_id in program.run_ids:
        try:
            run = builder.runs.load_run(run_id)
        except FileNotFoundError:
            continue
        for matrix in run.related_work_matrices:
            if matrix.direction_id == direction_id:
                return matrix
    return None


def _result_artifacts(manager: ExperimentWorkspaceManager, workspace_id: str) -> list[ExperimentResultArtifact]:
    try:
        return manager.list_result_artifacts(workspace_id)
    except FileNotFoundError:
        return []


def _artifact_package(config: GapForgeConfig, manuscript_id: str) -> ArtifactEvaluationPackage | None:
    try:
        return load_artifact_evaluation_package(config, f"artifact-eval-{manuscript_id}")
    except FileNotFoundError:
        return None


def _artifact_package_error(config: GapForgeConfig, manuscript_id: str) -> str:
    try:
        load_artifact_evaluation_package(config, f"artifact-eval-{manuscript_id}")
    except FileNotFoundError as exc:
        return str(exc)
    return ""


def _load_mapping_report(builder: DrasticReviewPanelBuilder, benchmark_id: str) -> VettedBenchmarkMappingReport | None:
    try:
        return builder.vetted_mappings.load_report(benchmark_id)
    except FileNotFoundError:
        return None


def _load_vetted_plan(builder: DrasticReviewPanelBuilder, benchmark_id: str) -> VettedBenchmarkExperimentPlan | None:
    spec = builder.selected_benchmarks.load_spec(benchmark_id)
    plan_id = f"selected-vetted-experiment-plan-{_slugish(spec.id)}"
    try:
        return builder.vetted_experiments.load_plan(plan_id)
    except FileNotFoundError:
        return None


def _load_vetted_result(
    builder: DrasticReviewPanelBuilder, plan: VettedBenchmarkExperimentPlan | None
) -> VettedBenchmarkExperimentResult | None:
    if plan is None:
        return None
    for project in builder.projects.list_projects():
        path = Path(project.root_dir) / "selected_benchmark" / "vetted_experiments" / f"{plan.id}.result.json"
        if path.exists():
            return from_dict(VettedBenchmarkExperimentResult, json.loads(path.read_text(encoding="utf-8")))
    return None


def _latest_taxonomy_issue_counts(config: GapForgeConfig) -> dict[str, int]:
    reports = []
    for path in sorted((config.data_dir / "review_training" / "datasets").glob("*/taxonomy/review_taxonomy_report.json")):
        try:
            reports.append(from_dict(ReviewTaxonomyReport, json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    counts: Counter[str] = Counter()
    for report in reports:
        counts.update(report.issue_counts)
    return dict(sorted(counts.items()))


def _latest_calibration_summary(config: GapForgeConfig) -> dict[str, str]:
    summary: dict[str, str] = {}
    for path in sorted((config.data_dir / "review_training" / "datasets").glob("*/reviewer_evaluation.json")):
        try:
            result = from_dict(ReviewerEvaluationResult, json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        summary[result.dataset_id] = (
            f"issue_recall={result.issue_recall_proxy:.4f}; specificity={result.review_specificity_score:.4f}; "
            f"hallucination_rate={result.hallucination_rate:.4f}; evidence_linkage={result.evidence_linkage_score:.4f}"
        )
    if not summary:
        summary["warning"] = "No reviewer calibration report found; drastic panel uses built-in taxonomy heuristics only."
    return summary


def _all_section_text(sections: dict[str, str]) -> str:
    return "\n".join(sections.values()).lower()


def _related_baselines(matrix: RelatedWorkMatrix | None) -> list[str]:
    return matrix.baseline_paper_ids if matrix else []


def _average_score(reviews: list[ReviewerReview]) -> float:
    if not reviews:
        return 0.0
    return sum(review.score for review in reviews) / len(reviews)


def _unique(values: Any) -> list[Any]:
    seen = set()
    unique = []
    for value in values:
        if value == "" or value is None:
            continue
        key = json.dumps(to_plain(value), sort_keys=True) if not isinstance(value, (str, int, float, bool)) else value
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def _slugish(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
