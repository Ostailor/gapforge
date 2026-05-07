"""Empirical reviewer simulation for executed experiment results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.metrics.low_fpr_power import LowFPRCheckResult, LowFPRPowerChecker
from gapforge.models import (
    BaselineRecord,
    EmpiricalReviewPanel,
    ExperimentExecutionRecord,
    ExperimentProtocol,
    ExperimentResultArtifact,
    ExperimentWorkspace,
    MetricRecord,
    Provenance,
    RebuttalPlan,
    RelatedWorkMatrix,
    ReproducibilityCheckResult,
    ResultSummary,
    ReviewerReview,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.results import ResultParser, ResultStatisticsAnalyzer
from gapforge.results.statistics import StatisticalAnalysisReport
from gapforge.reviewers.scoring import confidence_from_evidence, score_from_issues
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class _EmpiricalContext:
    workspace: ExperimentWorkspace
    execution: ExperimentExecutionRecord | None
    protocol: ExperimentProtocol | None
    baselines: list[BaselineRecord]
    metrics: list[MetricRecord]
    artifacts: list[ExperimentResultArtifact]
    result_summary: ResultSummary | None
    statistical_analysis: StatisticalAnalysisReport
    low_fpr_power_check: LowFPRCheckResult
    reproducibility: ReproducibilityCheckResult
    related_work_matrix: RelatedWorkMatrix | None


class EmpiricalReviewBuilder:
    """Build deterministic reviewer panels that attack empirical result claims."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.baseline_registry = BaselineRegistry(config)
        self.metric_registry = MetricRegistry(config)
        self.result_parser = ResultParser(config)
        self.statistics = ResultStatisticsAnalyzer(config)
        self.low_fpr_power = LowFPRPowerChecker(config)
        self.reproducibility = ReproducibilityChecker(config)

    def review_workspace(self, workspace_id: str) -> EmpiricalReviewPanel:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        executions = self.workspace_manager.list_execution_records(workspace.id)
        execution = executions[-1] if executions else None
        return self._review(workspace, execution)

    def review_execution(self, execution_id: str) -> EmpiricalReviewPanel:
        workspace, execution = ExperimentRunner(self.config).find_execution(execution_id)
        return self._review(workspace, execution)

    def _review(self, workspace: ExperimentWorkspace, execution: ExperimentExecutionRecord | None) -> EmpiricalReviewPanel:
        context = self._context(workspace, execution)
        reviews = [
            _empirical_rigor_review(context),
            _statistics_review(context),
            _reproducibility_review(context),
            _novelty_with_results_review(context),
        ]
        reviews.append(_area_chair_review(context, reviews))
        required_fixes = _dedupe([fix for review in reviews for fix in review.required_fixes])
        fatal_flaws = _dedupe([flaw for review in reviews for flaw in review.fatal_flaws])
        softening = _claim_softening_recommendations(context, reviews)
        panel = EmpiricalReviewPanel(
            workspace_id=workspace.id,
            execution_id=execution.id if execution is not None else "",
            reviewer_reviews=reviews,
            area_chair_summary=_area_chair_summary(context, fatal_flaws),
            required_fixes=required_fixes,
            fatal_flaws=fatal_flaws,
            rebuttal_plan=[_rebuttal_for(review) for review in reviews if review.required_fixes or review.fatal_flaws],
            result_claim_softening_recommendations=softening,
            provenance=Provenance(
                created_by_skill="empirical-review-panel",
                source_ids=[workspace.id, execution.id if execution is not None else ""],
                timestamp=utc_now_iso(),
                reasoning_summary="Reviewed empirical result artifacts, statistics, and reproducibility checks before paper packaging.",
            ),
        )
        self._write_panel(workspace, panel)
        return panel

    def _context(self, workspace: ExperimentWorkspace, execution: ExperimentExecutionRecord | None) -> _EmpiricalContext:
        artifacts = [
            artifact
            for artifact in self.workspace_manager.list_result_artifacts(workspace.id)
            if execution is not None and artifact.id in execution.result_artifact_ids
        ]
        result_summary = _load_result_summary(self.result_parser, execution)
        if execution is not None:
            statistical_analysis = self.statistics.analyze_execution(execution.id)
            low_fpr_power_check = self.low_fpr_power.check_execution(execution.id)
            reproducibility = self.reproducibility.check_execution(execution.id)
        else:
            statistical_analysis = self.statistics.analyze_workspace(workspace.id)
            low_fpr_power_check = self.low_fpr_power.check_workspace(workspace.id)
            reproducibility = self.reproducibility.check_workspace(workspace.id)
        program = self.project_manager.load_project(workspace.project_id)
        return _EmpiricalContext(
            workspace=workspace,
            execution=execution,
            protocol=_protocol_for_workspace(program.experiment_protocols, workspace),
            baselines=self.baseline_registry.list_baselines(workspace.id),
            metrics=self.metric_registry.list_metrics(workspace.id),
            artifacts=artifacts,
            result_summary=result_summary,
            statistical_analysis=statistical_analysis,
            low_fpr_power_check=low_fpr_power_check,
            reproducibility=reproducibility,
            related_work_matrix=next(
                (matrix for matrix in program.related_work_matrices if matrix.direction_id == workspace.direction_id),
                None,
            ),
        )

    def _write_panel(self, workspace: ExperimentWorkspace, panel: EmpiricalReviewPanel) -> None:
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        stem = f"empirical_review_{panel.execution_id}" if panel.execution_id else "empirical_review"
        (reports / f"{stem}.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (reports / f"{stem}.md").write_text(render_empirical_review_markdown(panel), encoding="utf-8")
        (reports / "empirical_review.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (reports / "empirical_review.md").write_text(render_empirical_review_markdown(panel), encoding="utf-8")


def render_empirical_review_markdown(panel: EmpiricalReviewPanel) -> str:
    lines = [
        "# Empirical Review Panel",
        "",
        f"- Workspace ID: `{panel.workspace_id}`",
        f"- Execution ID: `{panel.execution_id or 'none'}`",
        f"- Fatal flaws: {len(panel.fatal_flaws)}",
        "",
        "## Area Chair Summary",
        "",
        panel.area_chair_summary or "No area chair summary generated.",
        "",
        "## Reviews",
        "",
    ]
    for review in panel.reviewer_reviews:
        lines.extend(
            [
                f"### {review.reviewer_id}: {review.role}",
                "",
                f"- Score: {review.score:.1f}",
                f"- Confidence: {review.confidence}",
                f"- Evidence: {', '.join(f'`{item}`' for item in review.evidence_or_prior_work) or 'none'}",
                "",
                "**Strengths**",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in review.strengths] or ["- none"])
        lines.extend(["", "**Weaknesses**", ""])
        lines.extend([f"- {item}" for item in review.weaknesses] or ["- none"])
        lines.extend(["", "**Required Fixes**", ""])
        lines.extend([f"- {item}" for item in review.required_fixes] or ["- none"])
        lines.extend(["", "**Fatal Flaws**", ""])
        lines.extend([f"- {item}" for item in review.fatal_flaws] or ["- none"])
        lines.append("")
    lines.extend(["## Required Fixes", ""])
    lines.extend([f"- {item}" for item in panel.required_fixes] or ["- none"])
    lines.extend(["", "## Fatal Flaws", ""])
    lines.extend([f"- {item}" for item in panel.fatal_flaws] or ["- none"])
    lines.extend(["", "## Result Claim Softening Recommendations", ""])
    lines.extend([f"- {item}" for item in panel.result_claim_softening_recommendations] or ["- none"])
    lines.extend(["", "## Rebuttal Plan", ""])
    for plan in panel.rebuttal_plan:
        lines.extend(
            [
                f"### `{plan.target_review_id}`",
                "",
                f"- Strategy: {plan.response_strategy}",
                f"- Evidence needed: {', '.join(plan.evidence_needed) or 'none'}",
                f"- Experiments to add: {', '.join(plan.experiments_to_add) or 'none'}",
                f"- Claims to soften: {', '.join(plan.claims_to_soften) or 'none'}",
                "",
            ]
        )
    if not panel.rebuttal_plan:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _empirical_rigor_review(context: _EmpiricalContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = _base_evidence(context)
    if not context.baselines:
        fatal.append("No baseline is registered for this executed experiment.")
        fixes.append("Register and run at least one credible baseline before making empirical claims.")
    if context.execution is None:
        fatal.append("No experiment execution record exists.")
        fixes.append("Run the experiment and record an execution before empirical review.")
    elif context.execution.status == "failed":
        fatal.append("The experiment execution failed and cannot support a success claim.")
        fixes.append("Debug or rerun the experiment; report this execution as failed until a complete run exists.")
    if not context.artifacts:
        fatal.append("No result artifact is linked to the execution.")
        fixes.append("Link hashed result artifacts before interpreting empirical outcomes.")
    if context.result_summary is not None and not context.result_summary.metric_results:
        weaknesses.append("The result summary contains no parsed metric results.")
        fixes.append("Parse metrics_json artifacts and verify metric IDs before claiming results.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "ER1",
        "empirical_rigor",
        score,
        strengths=["Execution has result artifacts and registered baselines."] if context.artifacts and context.baselines else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _statistics_review(context: _EmpiricalContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = _base_evidence(context)
    summary = context.result_summary
    if summary is None:
        fatal.append("No parsed result summary is available for statistical review.")
        fixes.append("Run `gapforge parse-results` before empirical review.")
    elif not summary.metric_results:
        fatal.append("No metric results are available for statistical review.")
        fixes.append("Produce parseable metrics_json output before interpreting the run.")
    else:
        missing_low_fpr_ci = [
            result.metric_id
            for result in summary.metric_results
            if _is_low_fpr(result.metric_id, context.metrics) and not result.confidence_interval
        ]
        if missing_low_fpr_ci:
            weaknesses.append("Low-FPR metrics are missing confidence intervals.")
            fixes.append("Add confidence intervals for low-FPR metrics: " + ", ".join(missing_low_fpr_ci))
        if context.low_fpr_power_check.status == "fail":
            underpowered = ", ".join(context.low_fpr_power_check.underpowered_metric_ids) or "low-FPR metric"
            weaknesses.extend(context.low_fpr_power_check.blockers)
            fixes.append(f"Collect enough negative examples before claiming low-FPR performance for: {underpowered}.")
        elif context.low_fpr_power_check.status == "warning":
            warnings = [
                warning
                for warning in context.low_fpr_power_check.warnings
                if "No low-FPR metric results" not in warning and "No execution summaries" not in warning
            ]
            weaknesses.extend(warnings)
            if warnings:
                fixes.append("Resolve low-FPR power warnings or soften low-FPR claims.")
        if context.statistical_analysis.multiple_testing_warning:
            weaknesses.append(context.statistical_analysis.multiple_testing_warning)
            fixes.append("Declare a primary metric and soften secondary metric claims.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "ER2",
        "statistics",
        score,
        strengths=["Statistical analysis report exists."] if context.statistical_analysis.metric_analyses else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=[*evidence, context.statistical_analysis.id, context.low_fpr_power_check.id],
    )


def _reproducibility_review(context: _EmpiricalContext) -> ReviewerReview:
    ci_blockers = [item for item in context.reproducibility.blockers if "confidence interval" in item and "Low-FPR metric" in item]
    fatal = [item for item in context.reproducibility.blockers if item not in ci_blockers]
    weaknesses = [*context.reproducibility.warnings, *ci_blockers]
    fixes = [f"Fix reproducibility blocker: {item}" for item in fatal]
    fixes.extend(f"Add uncertainty reporting: {item}" for item in ci_blockers)
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "ER3",
        "reproducibility",
        score,
        strengths=["Reproducibility check passed."] if context.reproducibility.status == "pass" else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=[context.workspace.id, context.execution.id if context.execution else ""],
    )


def _novelty_with_results_review(context: _EmpiricalContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = _base_evidence(context)
    if context.related_work_matrix is None:
        weaknesses.append("No related-work matrix is available to position empirical results against prior work.")
        fixes.append("Build a related-work matrix before claiming empirical novelty.")
    else:
        evidence.extend(context.related_work_matrix.must_read_paper_ids[:5])
        directly_solves = [
            entry.paper_id for entry in context.related_work_matrix.entries if entry.relationship in {"directly_solves", "directly solves"}
        ]
        if directly_solves:
            fatal.append("Related-work matrix includes prior work that directly solves the target direction.")
            fixes.append("Reject, revise, or narrow result claims against directly solving prior work.")
            evidence.extend(directly_solves)
    if context.result_summary is not None and context.result_summary.failures:
        fatal.append("Failed experiment results cannot be used as novelty-supporting evidence.")
        fixes.append("Frame failed runs as negative evidence or debugging artifacts, not success.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "ER4",
        "novelty_with_results",
        score,
        strengths=["Related-work matrix is available for result positioning."] if context.related_work_matrix is not None else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=evidence,
    )


def _area_chair_review(context: _EmpiricalContext, reviews: list[ReviewerReview]) -> ReviewerReview:
    fatal_count = sum(bool(review.fatal_flaws) for review in reviews)
    weaknesses = []
    fixes = []
    fatal = []
    if fatal_count:
        fatal.append(f"{fatal_count} empirical reviewer roles found fatal flaws.")
        fixes.append("Do not export paper-ready empirical claims until fatal flaws are resolved.")
    elif any(review.required_fixes for review in reviews):
        weaknesses.append("Empirical claims require revisions before paper package export.")
        fixes.append("Resolve required fixes or soften claims in the manuscript package.")
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return _review(
        "AC",
        "area_chair",
        score,
        strengths=["No fatal empirical flaws found."] if not fatal else [],
        weaknesses=weaknesses,
        required_fixes=fixes,
        fatal_flaws=fatal,
        evidence=_base_evidence(context),
    )


def _review(
    reviewer_id: str,
    role: str,
    score: float,
    *,
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    required_fixes: list[str] | None = None,
    fatal_flaws: list[str] | None = None,
    evidence: list[str] | None = None,
) -> ReviewerReview:
    evidence_items = _dedupe([item for item in evidence or [] if item])
    return ReviewerReview(
        reviewer_id=reviewer_id,
        role=role,
        score=score,
        confidence=confidence_from_evidence(len(evidence_items), has_full_protocol=True),
        strengths=strengths or [],
        weaknesses=weaknesses or [],
        questions=[],
        required_fixes=_dedupe(required_fixes or []),
        fatal_flaws=_dedupe(fatal_flaws or []),
        evidence_or_prior_work=evidence_items,
        provenance=Provenance(
            created_by_skill="empirical-review-panel",
            source_ids=evidence_items,
            timestamp=utc_now_iso(),
            reasoning_summary=f"Deterministic {role} reviewer attacked artifact-backed empirical results.",
        ),
    )


def _rebuttal_for(review: ReviewerReview) -> RebuttalPlan:
    experiments: list[str] = []
    if review.role in {"empirical_rigor", "statistics", "reproducibility"}:
        experiments.append("Add reruns, ablations, or artifact fixes before rebutting empirical concerns.")
    if review.role == "novelty_with_results":
        experiments.append("Update related-work and novelty positioning before claiming result contribution.")
    return RebuttalPlan(
        target_review_id=review.reviewer_id,
        response_strategy="Fix the artifact or soften the claim; do not rebut empirical flaws by assertion.",
        evidence_needed=review.evidence_or_prior_work or ["Execution record, result artifact, and metric summary."],
        experiments_to_add=_dedupe(experiments),
        claims_to_soften=_claims_to_soften_for_review(review),
        risks=["Do not present failed, partial, or fixture-only runs as successful empirical validation."],
        provenance=Provenance(
            created_by_skill="empirical-review-panel",
            source_ids=review.evidence_or_prior_work,
            timestamp=utc_now_iso(),
            reasoning_summary="Converted empirical reviewer issues into rebuttal/fix actions without inventing results.",
        ),
    )


def _claim_softening_recommendations(context: _EmpiricalContext, reviews: list[ReviewerReview]) -> list[str]:
    recommendations = [claim for review in reviews for claim in _claims_to_soften_for_review(review)]
    if context.execution is not None and context.execution.status == "failed":
        recommendations.append("Describe this execution as failed or inconclusive; do not use it as evidence of empirical success.")
    if not context.artifacts:
        recommendations.append("Remove or mark empirical result claims as unsupported until result artifacts exist.")
    return _dedupe(recommendations)


def _claims_to_soften_for_review(review: ReviewerReview) -> list[str]:
    claims: list[str] = []
    if review.role == "statistics" and (review.weaknesses or review.fatal_flaws):
        claims.append("Soften quantitative claims until confidence intervals and multiple-testing context are complete.")
    if review.role == "empirical_rigor" and review.fatal_flaws:
        claims.append("Soften empirical success claims until baselines, executions, and result artifacts are complete.")
    if review.role == "novelty_with_results" and (review.weaknesses or review.fatal_flaws):
        claims.append("Soften result novelty claims until related-work positioning is complete.")
    if review.role == "reproducibility" and review.fatal_flaws:
        claims.append("Do not call the result reproducible until blockers are resolved.")
    return claims


def _area_chair_summary(context: _EmpiricalContext, fatal_flaws: list[str]) -> str:
    target = context.execution.id if context.execution is not None else context.workspace.id
    if fatal_flaws:
        return f"Execution/workspace `{target}` is not paper-ready: {len(fatal_flaws)} fatal empirical flaw(s) remain."
    if context.execution is not None and context.execution.status == "failed":
        return f"Execution `{target}` failed and must be framed as a failed or negative result."
    return f"Execution/workspace `{target}` has no deterministic fatal empirical review blockers, but still requires human review."


def _base_evidence(context: _EmpiricalContext) -> list[str]:
    return [
        context.workspace.id,
        context.execution.id if context.execution is not None else "",
        context.protocol.id if context.protocol is not None else "",
        *[artifact.id for artifact in context.artifacts],
    ]


def _protocol_for_workspace(protocols: list[ExperimentProtocol], workspace: ExperimentWorkspace) -> ExperimentProtocol | None:
    if workspace.experiment_protocol_id:
        return next((protocol for protocol in protocols if protocol.id == workspace.experiment_protocol_id), None)
    return next((protocol for protocol in protocols if protocol.direction_id == workspace.direction_id), None)


def _load_result_summary(parser: ResultParser, execution: ExperimentExecutionRecord | None) -> ResultSummary | None:
    if execution is None:
        return None
    try:
        return parser.load_or_parse_summary(execution.id)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def _is_low_fpr(metric_id: str, metrics: list[MetricRecord]) -> bool:
    text = metric_id.lower()
    for metric in metrics:
        if metric.id == metric_id:
            text += f" {metric.name.lower()} {metric.description.lower()}"
    return any(term in text for term in ["false positive", "false-positive", "false_positive", "fpr", "low-fpr", "low fpr", "specificity"])


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
