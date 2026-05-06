"""Paper package exporter for mature research directions."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.baselines import BaselineRegistry, render_baseline_registry_markdown
from gapforge.claim_ledger import ClaimLedger
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry, render_dataset_registry_markdown
from gapforge.experiments.protocol import render_protocol_markdown
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker, render_reproducibility_check_markdown
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.bibliography import render_bibtex
from gapforge.export.manuscript import (
    render_abstract,
    render_expected_results,
    render_intro_outline,
    render_limitations,
    render_method_outline,
    render_v06_result_boundary,
)
from gapforge.export.rebuttal import render_rebuttal_plan, render_reviewer_objections
from gapforge.metrics import MetricRegistry, render_metric_registry_markdown
from gapforge.models import (
    EmpiricalClaim,
    EvidenceSpan,
    ExperimentExecutionRecord,
    ExperimentPlan,
    ExperimentProtocol,
    ExperimentRunManifest,
    ExperimentWorkspace,
    Gap,
    NoveltyDossier,
    Paper,
    PaperPackage,
    Provenance,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ResultSummary,
    ReviewPanel,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.renderer import render_related_work_matrix_markdown
from gapforge.results import ResultParser, ResultStatisticsAnalyzer, render_analysis_report_markdown, render_result_summary_markdown
from gapforge.reviewers.empirical import EmpiricalReviewBuilder, render_empirical_review_markdown
from gapforge.reviewers.panel import render_review_panel_markdown
from gapforge.reviewers.rebuttal import render_rebuttal_plans_markdown
from gapforge.state import ResearchStateManager, utc_now_iso

EXPECTED_FILES = [
    "README.md",
    "abstract.md",
    "intro_outline.md",
    "related_work_matrix.md",
    "method_outline.md",
    "experiment_protocol.md",
    "expected_results.md",
    "limitations.md",
    "reviewer_objections.md",
    "review_panel.md",
    "rebuttal_plan.md",
    "bibliography.bib",
    "claim_ledger.md",
    "evidence_index.md",
]

V2_EXPECTED_FILES = [
    "README.md",
    "research_direction.md",
    "literature_basis.md",
    "novelty_dossier.md",
    "experiment_protocol.md",
    "datasets.md",
    "baselines.md",
    "metrics.md",
    "execution_records.md",
    "result_summary.md",
    "statistical_analysis.md",
    "reproducibility_check.md",
    "limitations.md",
    "negative_results.md",
    "reviewer_panel.md",
    "rebuttal_plan.md",
    "claim_ledger.md",
    "evidence_index.md",
    "expected_results.md",
]


class PaperPackageExporter:
    """Export conservative writing packages without inventing results."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def export_project_direction(
        self,
        project_id: str,
        direction_id: str,
        *,
        allow_rejected: bool = False,
    ) -> PaperPackage:
        program = self.project_manager.load_project(project_id)
        direction = _require_direction(program, direction_id)
        if direction.maturity == "rejected" and not allow_rejected:
            raise ValueError("Rejected directions cannot be exported unless --allow-rejected is set.")
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        context = _ProjectExportContext.from_program(program, states, direction)
        package_dir = Path(program.project.root_dir) / "paper_packages" / direction.id
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _missing_requirements(direction, context)
        files = _write_package_files(package_dir, direction, context, missing)
        package = PaperPackage(
            id=f"paper-package-{direction.id}",
            direction_id=direction.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=direction.maturity,
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export",
                source_ids=[project_id, direction.id, *program.run_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported an auditable manuscript starter kit from project direction state.",
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def export_workspace_v2(self, workspace_id: str) -> PaperPackage:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        program = self.project_manager.load_project(workspace.project_id)
        direction = next(
            (item for item in program.research_directions if item.id == workspace.direction_id),
            ResearchDirection(
                id=workspace.direction_id,
                project_id=workspace.project_id,
                title=workspace.direction_id,
                summary="Workspace-linked research direction.",
                maturity="experiment_ready" if workspace.status in {"ready", "complete"} else "candidate",
            ),
        )
        context = _V2ExportContext.from_workspace(self.config, program, workspace, direction)
        package_dir = Path(workspace.root_dir) / "paper_package_v2"
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _v2_missing_requirements(context)
        files = _write_v2_package_files(package_dir, context, missing)
        package = PaperPackage(
            id=f"paper-package-v2-{workspace.id}",
            direction_id=direction.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=_v2_readiness(context, missing),
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export-v2",
                source_ids=[workspace.project_id, workspace.id, direction.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Exported a v0.6 empirical paper package that separates planned, smoke, pilot, main, failed, and hypothetical results."
                ),
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def export_direction_v2(self, direction_id: str) -> PaperPackage:
        workspace = _find_workspace_for_direction(self.config, direction_id)
        if workspace is not None:
            return self.export_workspace_v2(workspace.id)
        program = _find_program_for_direction(self.project_manager, direction_id)
        direction = _require_direction(program, direction_id)
        context = _V2ExportContext.from_direction_only(self.config, program, direction)
        package_dir = Path(program.project.root_dir) / "paper_packages_v2" / direction.id
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _v2_missing_requirements(context)
        files = _write_v2_package_files(package_dir, context, missing)
        package = PaperPackage(
            id=f"paper-package-v2-{direction.id}",
            direction_id=direction.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness="planned",
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export-v2",
                source_ids=[program.project.id, direction.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported a planned-only v0.6 paper package because no experiment workspace was linked.",
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def export_run_gap(self, run_id: str, gap_id: str, *, allow_rejected: bool = False) -> PaperPackage:
        state = self.state_manager.load_run(run_id)
        gap = _require_gap(state, gap_id)
        direction = ResearchDirection(
            id=gap.id,
            project_id="",
            title=gap.title or gap.id,
            summary=gap.description,
            linked_gap_ids=[gap.id],
            supporting_paper_ids=gap.supporting_paper_ids,
            maturity="experiment_ready" if state.experiments else "candidate",
            readiness_score=0.75 if state.experiments else 0.35,
        )
        if gap.novelty_status == "likely_not_new" and not allow_rejected:
            raise ValueError("Rejected or likely-not-new gaps cannot be exported unless --allow-rejected is set.")
        context = _ProjectExportContext.from_state(state, direction)
        package_dir = Path(state.run_dir) / "paper_packages" / gap.id
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _missing_requirements(direction, context)
        files = _write_package_files(package_dir, direction, context, missing)
        package = PaperPackage(
            id=f"paper-package-{gap.id}",
            direction_id=gap.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=direction.maturity,
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export",
                source_ids=[run_id, gap.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported an auditable manuscript starter kit from run-level gap state.",
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package


class _ProjectExportContext:
    def __init__(
        self,
        *,
        gap: Gap | None,
        matrix: RelatedWorkMatrix | None,
        protocol: ExperimentProtocol | None,
        experiment: ExperimentPlan | None,
        dossier: NoveltyDossier | None,
        papers: list[Paper],
        evidence_spans: list[EvidenceSpan],
        claims_markdown: str,
        reviewer_objections_markdown: str,
        rebuttal_plan: str,
        review_panel_markdown: str,
        review_panel: ReviewPanel | None,
    ) -> None:
        self.gap = gap
        self.matrix = matrix
        self.protocol = protocol
        self.experiment = experiment
        self.dossier = dossier
        self.papers = papers
        self.evidence_spans = evidence_spans
        self.claims_markdown = claims_markdown
        self.reviewer_objections_markdown = reviewer_objections_markdown
        self.rebuttal_plan = rebuttal_plan
        self.review_panel_markdown = review_panel_markdown
        self.review_panel = review_panel

    @classmethod
    def from_program(
        cls, program: ResearchProgramState, states: list[ResearchRunState], direction: ResearchDirection
    ) -> _ProjectExportContext:
        gap = _first_gap(states, direction.linked_gap_ids)
        experiment = _first_experiment(states, direction.linked_experiment_ids, direction.linked_gap_ids)
        protocol = _first_protocol(
            [*program.experiment_protocols, *[protocol for state in states for protocol in state.experiment_protocols]],
            direction,
            experiment,
        )
        matrix = _first_matrix(
            [*program.related_work_matrices, *[matrix for state in states for matrix in state.related_work_matrices]], direction
        )
        dossier = _first_dossier(states, direction)
        papers = _relevant_papers(states, direction, matrix, dossier)
        objections = _linked_objections(states, experiment)
        panel = _first_review_panel(program.review_panels, direction)
        claims = [claim for state in states for claim in state.claims]
        evidence = [span for state in states for span in state.evidence_spans]
        return cls(
            gap=gap,
            matrix=matrix,
            protocol=protocol,
            experiment=experiment,
            dossier=dossier,
            papers=papers,
            evidence_spans=evidence,
            claims_markdown=ClaimLedger(claims).export_markdown(),
            reviewer_objections_markdown=render_reviewer_objections(objections),
            rebuttal_plan=render_rebuttal_plans_markdown([panel]) if panel is not None else render_rebuttal_plan(objections),
            review_panel_markdown=render_review_panel_markdown(panel)
            if panel is not None
            else "# Review Panel\n\nNo review panel linked yet. Run `gapforge review-panel`.\n",
            review_panel=panel,
        )

    @classmethod
    def from_state(cls, state: ResearchRunState, direction: ResearchDirection) -> _ProjectExportContext:
        gap = _first_gap([state], direction.linked_gap_ids)
        experiment = _first_experiment([state], direction.linked_experiment_ids, direction.linked_gap_ids)
        protocol = _first_protocol(state.experiment_protocols, direction, experiment)
        matrix = _first_matrix(state.related_work_matrices, direction)
        dossier = _first_dossier([state], direction)
        papers = _relevant_papers([state], direction, matrix, dossier)
        objections = _linked_objections([state], experiment)
        return cls(
            gap=gap,
            matrix=matrix,
            protocol=protocol,
            experiment=experiment,
            dossier=dossier,
            papers=papers,
            evidence_spans=state.evidence_spans,
            claims_markdown=ClaimLedger(state.claims).export_markdown(),
            reviewer_objections_markdown=render_reviewer_objections(objections),
            rebuttal_plan=render_rebuttal_plan(objections),
            review_panel_markdown="# Review Panel\n\nNo project-level review panel linked to this run-level export.\n",
            review_panel=None,
        )


class _V2ExportContext:
    def __init__(
        self,
        *,
        program: ResearchProgramState,
        direction: ResearchDirection,
        workspace: ExperimentWorkspace | None,
        project_context: _ProjectExportContext,
        manifests: list[ExperimentRunManifest],
        executions: list[ExperimentExecutionRecord],
        result_summaries: list[ResultSummary],
        statistical_analysis_markdown: str,
        reproducibility_markdown: str,
        empirical_review_markdown: str,
        empirical_rebuttal_markdown: str,
        empirical_claims: list[EmpiricalClaim],
        datasets_markdown: str,
        baselines_markdown: str,
        metrics_markdown: str,
        reproducibility_status: str,
        empirical_fatal_flaws: list[str],
    ) -> None:
        self.program = program
        self.direction = direction
        self.workspace = workspace
        self.project_context = project_context
        self.manifests = manifests
        self.executions = executions
        self.result_summaries = result_summaries
        self.statistical_analysis_markdown = statistical_analysis_markdown
        self.reproducibility_markdown = reproducibility_markdown
        self.empirical_review_markdown = empirical_review_markdown
        self.empirical_rebuttal_markdown = empirical_rebuttal_markdown
        self.empirical_claims = empirical_claims
        self.datasets_markdown = datasets_markdown
        self.baselines_markdown = baselines_markdown
        self.metrics_markdown = metrics_markdown
        self.reproducibility_status = reproducibility_status
        self.empirical_fatal_flaws = empirical_fatal_flaws

    @classmethod
    def from_workspace(
        cls,
        config: GapForgeConfig,
        program: ResearchProgramState,
        workspace: ExperimentWorkspace,
        direction: ResearchDirection,
    ) -> _V2ExportContext:
        state_manager = ResearchStateManager(config)
        states = [state_manager.load_run(run_id) for run_id in program.run_ids]
        project_context = _ProjectExportContext.from_program(program, states, direction)
        workspace_manager = ExperimentWorkspaceManager(config)
        manifests = workspace_manager.list_manifests(workspace.id)
        executions = workspace_manager.list_execution_records(workspace.id)
        parser = ResultParser(config)
        summaries = [_load_result_summary_safely(parser, execution.id) for execution in executions]
        result_summaries = [summary for summary in summaries if summary is not None]
        analysis = ResultStatisticsAnalyzer(config).analyze_workspace(workspace.id)
        reproducibility = ReproducibilityChecker(config).check_workspace(workspace.id)
        empirical_panel = EmpiricalReviewBuilder(config).review_workspace(workspace.id)
        datasets = DatasetRegistry(config).list_datasets(workspace.id)
        baselines = BaselineRegistry(config).list_baselines(workspace.id)
        metrics = MetricRegistry(config).list_metrics(workspace.id)
        return cls(
            program=program,
            direction=direction,
            workspace=workspace,
            project_context=project_context,
            manifests=manifests,
            executions=executions,
            result_summaries=result_summaries,
            statistical_analysis_markdown=render_analysis_report_markdown(analysis),
            reproducibility_markdown=render_reproducibility_check_markdown(reproducibility),
            empirical_review_markdown=render_empirical_review_markdown(empirical_panel),
            empirical_rebuttal_markdown=_render_v2_rebuttal_plan(empirical_panel.rebuttal_plan),
            empirical_claims=[claim for summary in result_summaries for claim in summary.empirical_claims],
            datasets_markdown=render_dataset_registry_markdown(datasets),
            baselines_markdown=render_baseline_registry_markdown(baselines),
            metrics_markdown=render_metric_registry_markdown(metrics),
            reproducibility_status=reproducibility.status,
            empirical_fatal_flaws=empirical_panel.fatal_flaws,
        )

    @classmethod
    def from_direction_only(
        cls,
        config: GapForgeConfig,
        program: ResearchProgramState,
        direction: ResearchDirection,
    ) -> _V2ExportContext:
        state_manager = ResearchStateManager(config)
        states = [state_manager.load_run(run_id) for run_id in program.run_ids]
        project_context = _ProjectExportContext.from_program(program, states, direction)
        return cls(
            program=program,
            direction=direction,
            workspace=None,
            project_context=project_context,
            manifests=[],
            executions=[],
            result_summaries=[],
            statistical_analysis_markdown="# Statistical Analysis\n\nNo experiment workspace is linked; no analysis exists.\n",
            reproducibility_markdown=(
                "# Reproducibility Check\n\nNo experiment workspace is linked; reproducibility has not been audited.\n"
            ),
            empirical_review_markdown="# Empirical Review Panel\n\nNo experiment workspace is linked; empirical review has not run.\n",
            empirical_rebuttal_markdown="# Rebuttal Plan\n\nNo empirical reviewer panel is available.\n",
            empirical_claims=[],
            datasets_markdown="# Dataset Registry\n\nNo experiment workspace is linked.\n",
            baselines_markdown="# Baseline Registry\n\nNo experiment workspace is linked.\n",
            metrics_markdown="# Metric Registry\n\nNo experiment workspace is linked.\n",
            reproducibility_status="fail",
            empirical_fatal_flaws=["No experiment workspace is linked to the direction."],
        )


def _write_v2_package_files(
    package_dir: Path,
    context: _V2ExportContext,
    missing: list[str],
) -> list[Path]:
    project_context = context.project_context
    contents = {
        "README.md": _render_v2_readme(context, missing),
        "research_direction.md": _render_v2_direction(context.direction),
        "literature_basis.md": render_related_work_matrix_markdown(project_context.matrix)
        if project_context.matrix is not None
        else "# Literature Basis\n\nNo related-work matrix is linked.\n",
        "novelty_dossier.md": _render_v2_novelty(project_context.dossier),
        "experiment_protocol.md": render_protocol_markdown(project_context.protocol)
        if project_context.protocol is not None
        else "# Experiment Protocol\n\nNo experiment protocol is linked.\n",
        "datasets.md": context.datasets_markdown,
        "baselines.md": context.baselines_markdown,
        "metrics.md": context.metrics_markdown,
        "execution_records.md": _render_v2_execution_records(context),
        "result_summary.md": _render_v2_result_summary(context),
        "statistical_analysis.md": context.statistical_analysis_markdown,
        "reproducibility_check.md": context.reproducibility_markdown,
        "limitations.md": render_limitations(context.direction, project_context.gap, project_context.dossier, missing),
        "negative_results.md": _render_v2_negative_results(context),
        "reviewer_panel.md": context.empirical_review_markdown,
        "rebuttal_plan.md": context.empirical_rebuttal_markdown,
        "claim_ledger.md": _render_v2_claim_ledger(context),
        "evidence_index.md": _render_evidence_index(project_context),
        "expected_results.md": render_expected_results(project_context.protocol, project_context.experiment),
    }
    paths = []
    for filename in V2_EXPECTED_FILES:
        path = package_dir / filename
        path.write_text(contents[filename], encoding="utf-8")
        paths.append(path)
    return paths


def _render_v2_readme(context: _V2ExportContext, missing: list[str]) -> str:
    lines = [
        f"# Paper Package v2: {context.direction.title or context.direction.id}",
        "",
        "This v0.6 package separates planned experiments, smoke/pilot/main runs, failed runs, and hypothetical expected results.",
        "It must not be read as a completed paper unless reproducibility and empirical review gates pass.",
        "",
        f"- Direction ID: `{context.direction.id}`",
        f"- Workspace ID: `{context.workspace.id if context.workspace else 'none'}`",
        f"- Result state: {_v2_result_state(context)}",
        f"- Paper-ready gate: {'pass' if not missing else 'blocked'}",
        "",
        "## Missing Requirements",
        "",
    ]
    lines.extend([f"- {item}" for item in missing] or ["- none"])
    lines.extend(["", "## Files", ""])
    lines.extend([f"- `{filename}`" for filename in V2_EXPECTED_FILES])
    return "\n".join(lines).rstrip() + "\n"


def _render_v2_direction(direction: ResearchDirection) -> str:
    return "\n".join(
        [
            f"# Research Direction `{direction.id}`",
            "",
            f"- Title: {direction.title or direction.id}",
            f"- Maturity: {direction.maturity}",
            f"- Readiness score: {direction.readiness_score:.2f}",
            "",
            direction.summary or "No summary recorded.",
            "",
        ]
    )


def _render_v2_novelty(dossier: NoveltyDossier | None) -> str:
    if dossier is None:
        return "# Novelty Dossier\n\nNo novelty dossier is linked.\n"
    lines = [
        "# Novelty Dossier",
        "",
        f"- Target ID: `{dossier.target_id}`",
        f"- Verdict: `{dossier.verdict}`",
        f"- Strength: `{dossier.novelty_strength}`",
        f"- Confidence: `{dossier.confidence}`",
        f"- Closest prior work: {', '.join(f'`{item}`' for item in dossier.top_prior_work) or 'unknown'}",
        f"- Missing searches: {', '.join(dossier.missing_searches) or 'none'}",
        "",
        "## Decisive Difference Needed",
        "",
        dossier.decisive_difference_needed or "Not specified.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _render_v2_execution_records(context: _V2ExportContext) -> str:
    lines = ["# Execution Records", ""]
    if not context.executions:
        lines.append("No execution records exist. This is a planned experiment package only.")
        return "\n".join(lines).rstrip() + "\n"
    manifest_by_id = {manifest.id: manifest for manifest in context.manifests}
    for execution in context.executions:
        manifest = manifest_by_id.get(execution.manifest_id)
        run_type = manifest.run_type if manifest is not None else "unknown"
        label = _result_label(run_type, execution.status)
        lines.extend(
            [
                f"## `{execution.id}`",
                "",
                f"- Label: `{label}`",
                f"- Run type: `{run_type}`",
                f"- Status: `{execution.status}`",
                f"- Return code: {execution.returncode if execution.returncode is not None else 'none'}",
                f"- Command: `{execution.command or (manifest.command if manifest else 'none')}`",
                f"- Stdout: `{execution.stdout_path or 'none'}`",
                f"- Stderr: `{execution.stderr_path or 'none'}`",
                f"- Result artifacts: {', '.join(f'`{item}`' for item in execution.result_artifact_ids) or 'none'}",
                f"- Failure reason: {execution.failure_reason or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_v2_result_summary(context: _V2ExportContext) -> str:
    if not context.result_summaries:
        return render_v06_result_boundary(context.executions, [])
    sections = [render_v06_result_boundary(context.executions, context.empirical_claims)]
    for summary in context.result_summaries:
        sections.append(render_result_summary_markdown(summary))
    if not context.empirical_claims:
        sections.append("No artifact-backed empirical claims were created. Do not write a completed Results section.")
    return "\n\n".join(section.rstrip() for section in sections) + "\n"


def _render_v2_negative_results(context: _V2ExportContext) -> str:
    lines = ["# Negative And Failed Results", ""]
    failed = [execution for execution in context.executions if execution.status == "failed" or execution.failure_reason]
    if not failed:
        lines.append("No failed executions are recorded.")
        return "\n".join(lines).rstrip() + "\n"
    for execution in failed:
        lines.extend(
            [
                f"## `{execution.id}`",
                "",
                f"- Status: `{execution.status}`",
                f"- Failure reason: {execution.failure_reason or 'not specified'}",
                "- Interpretation: failed or negative runs must stay visible and cannot be reframed as successful results.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_v2_rebuttal_plan(plans) -> str:
    lines = ["# Rebuttal Plan", ""]
    if not plans:
        lines.append("No empirical rebuttal actions generated.")
        return "\n".join(lines).rstrip() + "\n"
    for plan in plans:
        lines.extend(
            [
                f"## `{plan.target_review_id}`",
                "",
                f"- Strategy: {plan.response_strategy}",
                f"- Evidence needed: {', '.join(plan.evidence_needed) or 'none'}",
                f"- Experiments to add: {', '.join(plan.experiments_to_add) or 'none'}",
                f"- Claims to soften: {', '.join(plan.claims_to_soften) or 'none'}",
                f"- Risks: {', '.join(plan.risks) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_v2_claim_ledger(context: _V2ExportContext) -> str:
    lines = ["# Claim Ledger", ""]
    lines.append(context.project_context.claims_markdown.rstrip())
    lines.extend(["", "## Artifact-Backed Empirical Claims", ""])
    lines.extend(
        [
            f"- `{claim.id}` status=`{claim.status}` confidence=`{claim.confidence}` execution=`{claim.execution_id}`: {claim.text}"
            for claim in context.empirical_claims
        ]
        or ["- none"]
    )
    return "\n".join(lines).rstrip() + "\n"


def _v2_missing_requirements(context: _V2ExportContext) -> list[str]:
    missing = _missing_requirements(context.direction, context.project_context)
    if context.workspace is None:
        missing.append("No experiment workspace is linked; package is planned-only.")
    if not context.executions:
        missing.append("No execution records exist; package is planned-only.")
    if context.reproducibility_status != "pass":
        missing.append(f"Reproducibility gate is `{context.reproducibility_status}`.")
    if context.empirical_fatal_flaws:
        missing.append("Empirical review has fatal flaws: " + "; ".join(context.empirical_fatal_flaws[:3]))
    if not context.empirical_claims and any(execution.status == "complete" for execution in context.executions):
        missing.append("Completed execution has no artifact-backed empirical claims.")
    return _dedupe(missing)


def _v2_readiness(context: _V2ExportContext, missing: list[str]) -> str:
    if missing:
        return _v2_result_state(context)
    return "paper_ready_empirical"


def _v2_result_state(context: _V2ExportContext) -> str:
    if not context.executions:
        return "planned_experiment"
    manifest_by_id = {manifest.id: manifest for manifest in context.manifests}
    labels = []
    for execution in context.executions:
        manifest = manifest_by_id.get(execution.manifest_id)
        labels.append(_result_label(manifest.run_type if manifest is not None else "", execution.status))
    if any(label == "failed_result" for label in labels):
        return "failed_result"
    if "main_result" in labels:
        return "main_result"
    if "pilot_result" in labels:
        return "pilot_result"
    if "smoke_result" in labels:
        return "smoke_result"
    return labels[-1] if labels else "planned_experiment"


def _result_label(run_type: str, status: str) -> str:
    if status == "failed":
        return "failed_result"
    if run_type == "smoke":
        return "smoke_result"
    if run_type == "pilot":
        return "pilot_result"
    if run_type == "main":
        return "main_result"
    if run_type:
        return f"{run_type}_result"
    return "planned_experiment"


def _load_result_summary_safely(parser: ResultParser, execution_id: str) -> ResultSummary | None:
    try:
        return parser.load_or_parse_summary(execution_id)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def _find_workspace_for_direction(config: GapForgeConfig, direction_id: str) -> ExperimentWorkspace | None:
    manager = ExperimentWorkspaceManager(config)
    for project_dir in sorted(config.project_root.glob("*")):
        workspace_root = project_dir / "experiment_workspaces"
        if not workspace_root.exists():
            continue
        for workspace_dir in sorted(workspace_root.glob("*")):
            workspace_path = workspace_dir / "workspace.json"
            if not workspace_path.exists():
                continue
            try:
                workspace = manager.load_workspace(workspace_dir.name)
            except (FileNotFoundError, json.JSONDecodeError, ValueError):
                continue
            if workspace.direction_id == direction_id:
                return workspace
    return None


def _find_program_for_direction(manager: ProjectMemoryManager, direction_id: str) -> ResearchProgramState:
    for project in manager.list_projects():
        program = manager.load_project(project.id)
        if any(direction.id == direction_id for direction in program.research_directions):
            return program
    raise KeyError(f"Unknown research direction: {direction_id}")


def _write_package_files(
    package_dir: Path,
    direction: ResearchDirection,
    context: _ProjectExportContext,
    missing: list[str],
) -> list[Path]:
    contents = {
        "README.md": _render_readme(direction, missing),
        "abstract.md": render_abstract(direction, context.gap, context.protocol),
        "intro_outline.md": render_intro_outline(direction, context.gap, context.dossier),
        "related_work_matrix.md": render_related_work_matrix_markdown(context.matrix)
        if context.matrix is not None
        else "# Related Work Matrix\n\nMissing related-work matrix. Run `gapforge related-work-matrix`.\n",
        "method_outline.md": render_method_outline(context.protocol, context.experiment),
        "experiment_protocol.md": render_protocol_markdown(context.protocol)
        if context.protocol is not None
        else "# Experiment Protocol\n\nMissing experiment protocol. Run `gapforge experiment-protocol`.\n",
        "expected_results.md": render_expected_results(context.protocol, context.experiment),
        "limitations.md": render_limitations(direction, context.gap, context.dossier, missing),
        "reviewer_objections.md": context.reviewer_objections_markdown,
        "review_panel.md": context.review_panel_markdown,
        "rebuttal_plan.md": context.rebuttal_plan,
        "bibliography.bib": render_bibtex(context.papers),
        "claim_ledger.md": context.claims_markdown,
        "evidence_index.md": _render_evidence_index(context),
    }
    paths = []
    for filename in EXPECTED_FILES:
        path = package_dir / filename
        path.write_text(contents[filename], encoding="utf-8")
        paths.append(path)
    return paths


def _render_readme(direction: ResearchDirection, missing: list[str]) -> str:
    lines = [
        f"# Paper Package: {direction.title}",
        "",
        "This package is a writing starter kit. It is not a completed paper and does not claim completed experimental results.",
        "",
        f"- Direction ID: `{direction.id}`",
        f"- Readiness: {direction.maturity}",
        f"- Readiness score: {direction.readiness_score:.2f}",
        "",
        "## Missing Requirements",
        "",
    ]
    lines.extend([f"- {item}" for item in missing] or ["- none"])
    lines.extend(["", "## Files", ""])
    lines.extend([f"- `{filename}`" for filename in EXPECTED_FILES])
    return "\n".join(lines).rstrip() + "\n"


def _render_evidence_index(context: _ProjectExportContext) -> str:
    lines = ["# Evidence Index", ""]
    if context.matrix is not None:
        lines.extend(["## Related Work Evidence", ""])
        for entry in context.matrix.entries:
            lines.append(f"- `{entry.paper_id}` {entry.relationship}: spans={', '.join(entry.evidence_span_ids) or 'none'}")
    lines.extend(["", "## Evidence Spans", ""])
    lines.extend(
        [
            f"- `{span.id}` paper=`{span.paper_id}` type={span.evidence_type} locator={span.locator or 'unknown'}: {span.quote}"
            for span in context.evidence_spans
        ]
        or ["- none"]
    )
    return "\n".join(lines).rstrip() + "\n"


def _missing_requirements(direction: ResearchDirection, context: _ProjectExportContext) -> list[str]:
    missing = []
    if direction.maturity not in {"experiment_ready", "manuscript_ready"}:
        missing.append(f"Direction is {direction.maturity}, not experiment_ready or manuscript_ready.")
    if context.matrix is None:
        missing.append("Related-work matrix is missing.")
    if context.protocol is None:
        missing.append("Experiment protocol is missing.")
    if context.dossier is None:
        missing.append("Novelty dossier is missing.")
    elif context.dossier.missing_searches:
        missing.append("Novelty dossier has missing searches: " + "; ".join(context.dossier.missing_searches))
    if context.review_panel is None:
        missing.append("Review panel is missing.")
    elif context.review_panel.decision_risk in {"reject_likely", "high"}:
        missing.append(f"Review panel decision risk is {context.review_panel.decision_risk}.")
    if context.experiment is None:
        missing.append("Experiment plan is missing.")
    if direction.blocking_issues:
        missing.extend(direction.blocking_issues)
    return _dedupe(missing)


def _require_direction(program: ResearchProgramState, direction_id: str) -> ResearchDirection:
    direction = next((item for item in program.research_directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _require_gap(state: ResearchRunState, gap_id: str) -> Gap:
    gap = next((item for item in state.gaps if item.id == gap_id), None)
    if gap is None:
        raise KeyError(f"Unknown gap: {gap_id}")
    return gap


def _first_gap(states: list[ResearchRunState], gap_ids: list[str]) -> Gap | None:
    return next((gap for state in states for gap in state.gaps if gap.id in gap_ids), None)


def _first_experiment(states: list[ResearchRunState], experiment_ids: list[str], gap_ids: list[str]) -> ExperimentPlan | None:
    return next(
        (
            experiment
            for state in states
            for experiment in state.experiments
            if experiment.id in experiment_ids or set(experiment.linked_gap_ids).intersection(gap_ids)
        ),
        None,
    )


def _first_protocol(
    protocols: list[ExperimentProtocol], direction: ResearchDirection, experiment: ExperimentPlan | None
) -> ExperimentProtocol | None:
    return next(
        (
            protocol
            for protocol in protocols
            if protocol.direction_id == direction.id
            or (experiment is not None and protocol.linked_experiment_plan_id == experiment.id)
            or protocol.direction_id in direction.linked_gap_ids
        ),
        None,
    )


def _first_matrix(matrices: list[RelatedWorkMatrix], direction: ResearchDirection) -> RelatedWorkMatrix | None:
    return next(
        (matrix for matrix in matrices if matrix.direction_id == direction.id or matrix.direction_id in direction.linked_gap_ids), None
    )


def _first_dossier(states: list[ResearchRunState], direction: ResearchDirection) -> NoveltyDossier | None:
    return next(
        (
            dossier
            for state in states
            for dossier in state.novelty_dossiers
            if dossier.target_id in direction.linked_gap_ids or dossier.target_id in direction.linked_novelty_dossier_ids
        ),
        None,
    )


def _linked_objections(states: list[ResearchRunState], experiment: ExperimentPlan | None) -> list:
    if experiment is None:
        return []
    return [objection for state in states for objection in state.reviewer_objections if objection.experiment_id == experiment.id]


def _first_review_panel(panels: list[ReviewPanel], direction: ResearchDirection) -> ReviewPanel | None:
    return next((panel for panel in panels if panel.experiment_or_direction_id == direction.id), None)


def _relevant_papers(
    states: list[ResearchRunState],
    direction: ResearchDirection,
    matrix: RelatedWorkMatrix | None,
    dossier: NoveltyDossier | None,
) -> list[Paper]:
    ids = set(direction.supporting_paper_ids + direction.counterevidence_paper_ids)
    if matrix is not None:
        ids.update(entry.paper_id for entry in matrix.entries)
    if dossier is not None:
        ids.update(dossier.top_prior_work)
        ids.update(dossier.candidates_considered)
        ids.update(str(row.get("paper_id", "")) for row in dossier.comparison_table)
    by_id = {paper.id: paper for state in states for paper in state.papers}
    return [paper for paper_id, paper in by_id.items() if paper_id in ids]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
