"""Programmatic API for notebooks, scripts, and UI adapters.

The functions in this module are intentionally thin wrappers over the same
managers and skills used by the CLI. They provide a stable import surface
without asking callers to shell out to ``gapforge`` commands.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from gapforge.agents.validation import create_actual_run_attestation as create_run_actual_run_attestation
from gapforge.baselines.registry import BaselineRegistry
from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.acceptance import create_campaign_actual_run_attestation
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.decision_policy import CampaignAction
from gapforge.campaigns.import_workflow import find_campaign_task
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.config import GapForgeConfig
from gapforge.datasets.registry import DatasetRegistry
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.experiment_code import ExperimentCodeTaskGenerator
from gapforge.experiment_code.scaffold_v2 import ExperimentCodeScaffolderV2
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker
from gapforge.experiments.runner import ExperimentRunner, ExperimentRunResult
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.ingest import ManualIngestor
from gapforge.metrics.registry import MetricRegistry
from gapforge.models import (
    AgentActualRunAttestation,
    AgentTaskSpec,
    BaselineRecord,
    CampaignAcceptanceSummary,
    CampaignHumanReview,
    CampaignImportRecord,
    CanonicalPaperIdentity,
    DatasetRecord,
    EmpiricalReviewPanel,
    ExperimentCodeTask,
    ExperimentRunManifest,
    ExperimentWorkspace,
    IndexManifest,
    LiveSourceDiagnostic,
    MetricRecord,
    Paper,
    PaperArtifact,
    PaperMergeDecision,
    PaperPackage,
    PaperSection,
    PriorWorkRecallAssessment,
    RealLiteratureCampaignRecord,
    RealLiteratureHumanReview,
    ReproducibilityCheckResult,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ResultSummary,
    SearchStrategy,
    SourceHealthCheck,
)
from gapforge.novelty.recall_gate import assess_campaign_prior_work_recall, assess_run_prior_work_recall
from gapforge.orchestrator import Orchestrator
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature import RealLiteratureCampaignManager, RealLiteratureReviewManager
from gapforge.release_gate import (
    V04ReleaseGateEnforcer,
    V04ReleaseGateResult,
    V05ReleaseGateEnforcer,
    V05ReleaseGateResult,
    V06ReleaseGateEnforcer,
    V06ReleaseGateResult,
)
from gapforge.reporting import write_final_report
from gapforge.results import ResultParser, ResultStatisticsAnalyzer
from gapforge.results.statistics import StatisticalAnalysisReport
from gapforge.retrieval import build_project_index, build_run_index
from gapforge.reviewers.empirical import EmpiricalReviewBuilder
from gapforge.search_strategy import plan_search_strategy as plan_search_strategy_skill
from gapforge.sources.base import ResearchSource
from gapforge.sources.canonical import canonicalize_project, canonicalize_run
from gapforge.sources.health import check_sources
from gapforge.sources.live_diagnostics import run_live_source_diagnostic
from gapforge.state import ResearchStateManager


@dataclass(slots=True)
class AddPdfResult:
    state: ResearchRunState
    paper: Paper
    artifact: PaperArtifact


@dataclass(slots=True)
class ParseFullTextResult:
    state: ResearchRunState
    sections: list[PaperSection]


@dataclass(slots=True)
class ReportResult:
    state: ResearchRunState
    path: Path


@dataclass(slots=True)
class CampaignTaskResult:
    state: CampaignState
    task_id: str
    path: Path


@dataclass(slots=True)
class CampaignReviewResult:
    review: CampaignHumanReview
    summary: CampaignAcceptanceSummary


@dataclass(slots=True)
class RealLiteratureReviewResult:
    review: RealLiteratureHumanReview
    summary: dict[str, object]


def create_project(
    name: str,
    *,
    description: str = "",
    config: GapForgeConfig | None = None,
) -> ResearchProgramState:
    """Create a project-memory workspace."""

    return ProjectMemoryManager(_config(config)).create_project(name, description=description)


def create_run(
    topic: str,
    *,
    project_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Create a durable research run, optionally attaching it to a project."""

    cfg = _config(config)
    state = Orchestrator(cfg).init_topic(topic)
    if project_id:
        state.config["project_id"] = project_id
        ResearchStateManager(cfg).save_run(state)
        ProjectMemoryManager(cfg).attach_run(project_id, state.run_id)
        state = ResearchStateManager(cfg).load_run(state.run_id)
    return state


def source_health(
    topic: str | None = None,
    *,
    profile: str | None = None,
    sources: Iterable[ResearchSource] | None = None,
    config: GapForgeConfig | None = None,
) -> LiveSourceDiagnostic | list[SourceHealthCheck]:
    """Check live-source readiness without shelling out.

    When ``topic`` or ``profile`` is provided, this returns a policy-aware
    ``LiveSourceDiagnostic``. With neither, it returns raw source health checks.
    Tests and notebooks can pass mocked ``sources`` to avoid live network use.
    """

    cfg = _config(config)
    if topic or profile:
        return run_live_source_diagnostic(
            cfg,
            topic=topic or "",
            source_profile=profile or "generic",
            sources=sources,
        )
    return check_sources(cfg, sources=sources)


def plan_search_strategy(
    topic: str,
    source_profile: str = "generic",
    *,
    config: GapForgeConfig | None = None,
) -> SearchStrategy:
    """Plan v0.5 multi-round literature searches for a topic."""

    return plan_search_strategy_skill(_config(config), topic, source_profile=source_profile)


def search_papers(
    run_id: str,
    *,
    query: str | None = None,
    max_results: int = 20,
    sources: list[str] | None = None,
    newest_first: bool = True,
    date_from: str | None = None,
    date_to: str | None = None,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Search configured sources for an existing run and persist papers."""

    cfg = _config(config)
    orchestrator = Orchestrator(cfg)
    state = orchestrator.state_store.load_run(run_id)
    search_query = query or state.topic.text
    papers, failures = orchestrator._search_sources(
        state=state,
        query=search_query,
        max_results=max_results,
        source_names=sources,
        newest_first=newest_first,
        purpose="initial_topic" if not state.search_queries else "manual",
        date_from=date_from,
        date_to=date_to,
    )
    for failure in failures:
        orchestrator._log(state, "warning", "api-search", failure)
    state.papers = orchestrator._merge_ranked_papers(state, papers, search_query, max_results)
    orchestrator._refresh_coverage(state)
    orchestrator.state_store.save_run(state)
    return state


def add_pdf(
    run_id: str,
    pdf_path: str | Path,
    *,
    title: str = "",
    authors: list[str] | None = None,
    year: int = 0,
    parse: bool = False,
    config: GapForgeConfig | None = None,
) -> AddPdfResult:
    """Add a local PDF to a run without using the CLI."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    path = Path(pdf_path)
    paper, artifact = ManualIngestor(cfg).add_pdf(
        state,
        path,
        title=title or path.stem,
        authors=authors or [],
        year=year,
        parse=parse,
    )
    manager.save_run(state)
    return AddPdfResult(state=state, paper=paper, artifact=artifact)


def parse_fulltext(
    run_id: str,
    *,
    paper_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> ParseFullTextResult:
    """Parse available PDF artifacts into paper sections."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    sections = FullTextParser().parse_for_state(state, paper_id=paper_id)
    manager.save_run(state)
    return ParseFullTextResult(state=state, sections=sections)


def build_index(
    *,
    run_id: str | None = None,
    project_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> IndexManifest:
    """Build a persisted hybrid retrieval index for exactly one run or project."""

    cfg = _config(config)
    _require_one_scope(run_id=run_id, project_id=project_id)
    if run_id:
        manager = ResearchStateManager(cfg)
        state = manager.load_run(run_id)
        manifest = build_run_index(state)
        manager.save_run(state)
        return manifest
    program = ProjectMemoryManager(cfg).load_project(project_id or "")
    return build_project_index(program)


def mine_gaps(
    run_id: str,
    *,
    mode: str = "deterministic",
    min_confidence: str = "low",
    include_low_confidence: bool = True,
    fake: bool = False,
    dry_run_prompts: bool = False,
    force: bool = False,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Run deterministic or optional LLM-backed gap mining for a run."""

    orchestrator = Orchestrator(_config(config))
    if mode == "deterministic":
        return orchestrator.mine_gaps(
            run_id=run_id,
            min_confidence=min_confidence,
            include_low_confidence=include_low_confidence,
            force=force,
        )
    if mode == "llm":
        return orchestrator.mine_gaps_llm(
            run_id=run_id,
            dry_run_prompts=dry_run_prompts,
            fake=fake,
            force=force,
        )
    raise ValueError("mode must be 'deterministic' or 'llm'")


def novelty_check(
    run_id: str,
    *,
    gap_id: str | None = None,
    deep: bool = False,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Run the deterministic novelty gate for a run."""

    return Orchestrator(_config(config)).novelty_check(run_id=run_id, gap_id=gap_id, deep=deep)


def create_direction(
    project_id: str,
    gap_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ResearchDirection:
    """Create or fetch a project-level research direction for an attached-run gap."""

    return DirectionMaturationManager(_config(config)).create_direction(project_id, gap_id)


def mature_direction(
    project_id: str,
    direction_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ResearchDirection:
    """Evaluate maturity gates for a project-level research direction."""

    return DirectionMaturationManager(_config(config)).mature_direction(project_id, direction_id)


def export_paper_package(
    project_id: str,
    direction_id: str,
    *,
    allow_rejected: bool = False,
    config: GapForgeConfig | None = None,
) -> PaperPackage:
    """Export a conservative paper starter package for a project direction."""

    return PaperPackageExporter(_config(config)).export_project_direction(
        project_id,
        direction_id,
        allow_rejected=allow_rejected,
    )


def export_report(
    run_id: str,
    *,
    output_format: str = "markdown",
    strict: bool = False,
    config: GapForgeConfig | None = None,
) -> ReportResult:
    """Write ``final_report.md`` or ``final_report.json`` for a run."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    path = write_final_report(state, output_format=output_format, strict=strict)
    return ReportResult(state=state, path=path)


def create_campaign(
    project_id: str,
    topic: str,
    *,
    title: str = "",
    mode: str = "deterministic",
    agent_name: str = "",
    model: str = "",
    source_profile: str = "generic",
    budget_id: str = "small",
    config: GapForgeConfig | None = None,
) -> CampaignState:
    """Create a durable v0.4 campaign under a project."""

    return CampaignManager(_config(config)).create_campaign(
        topic,
        project_id=project_id,
        title=title,
        mode=mode,
        agent_name=agent_name,
        model=model,
        source_profile=source_profile,
        budget_id=budget_id,
    )


def run_campaign(
    campaign_id: str,
    *,
    mode: str | None = None,
    max_iterations: int | None = None,
    config: GapForgeConfig | None = None,
) -> CampaignState:
    """Run the v0.4 campaign controller."""

    return CampaignController(_config(config)).run(campaign_id, mode=mode, max_iterations=max_iterations)


def campaign_next(
    campaign_id: str,
    *,
    max_iterations: int | None = None,
    config: GapForgeConfig | None = None,
) -> CampaignAction:
    """Preview the next campaign controller action."""

    return CampaignController(_config(config)).next_action(campaign_id, max_iterations=max_iterations)


def create_campaign_task(
    campaign_id: str,
    task_type: str,
    *,
    config: GapForgeConfig | None = None,
) -> CampaignTaskResult:
    """Create a validation-gated Codex/GPT-5.4 campaign task pack."""

    cfg = _config(config)
    path = create_campaign_task_pack(cfg, campaign_id, task_type)
    state = CampaignManager(cfg).load_campaign_state(campaign_id)
    return CampaignTaskResult(state=state, task_id=state.campaign.task_ids[-1], path=path)


def validate_campaign_output(
    campaign_id: str,
    task_id: str,
    paths: list[str | Path] | None = None,
    *,
    config: GapForgeConfig | None = None,
) -> CampaignImportRecord:
    """Validate campaign output patches without mutating campaign state."""

    return CampaignOutputImporter(_config(config)).validate(campaign_id, task_id, _paths(paths))


def import_campaign_output(
    campaign_id: str,
    task_id: str,
    paths: list[str | Path] | None = None,
    *,
    dry_run: bool = False,
    config: GapForgeConfig | None = None,
) -> CampaignImportRecord:
    """Validate and import campaign output patches, preserving rollback metadata."""

    return CampaignOutputImporter(_config(config)).import_outputs(campaign_id, task_id, _paths(paths), dry_run=dry_run)


def attest_agent_run(
    task_id: str,
    *,
    agent_name: str = "codex",
    model: str = "gpt-5.4",
    execution_method: str = "task_pack",
    attester: str = "human",
    statement: str = "",
    config: GapForgeConfig | None = None,
) -> AgentActualRunAttestation:
    """Attest that a validated run-level or campaign-level task came from an actual agent.

    Campaign task-pack and handoff attestations count only when a validated import
    already exists for the task. Fake methods never count as actual-run evidence.
    """

    cfg = _config(config)
    try:
        state, _ = find_campaign_task(cfg, task_id)
    except FileNotFoundError:
        return _attest_run_task(
            cfg,
            task_id,
            agent_name=agent_name,
            model=model,
            execution_method=execution_method,
            attester=attester,
            statement=statement,
        )
    return _attest_campaign_task(
        cfg,
        state,
        task_id,
        agent_name=agent_name,
        model=model,
        execution_method=execution_method,
        attester=attester,
        statement=statement,
    )


def review_campaign(
    campaign_id: str,
    *,
    reviewer: str = "human",
    accept: bool = False,
    reject: bool = False,
    reason: str = "",
    notes: str = "",
    source_coverage_score: int = 0,
    full_text_grounding_score: int = 0,
    citation_grounding_score: int = 0,
    retrieval_quality_score: int = 0,
    novelty_honesty_score: int = 0,
    gap_quality_score: int = 0,
    related_work_quality_score: int = 0,
    experiment_quality_score: int = 0,
    reviewer_panel_quality_score: int = 0,
    uncertainty_visibility_score: int = 0,
    stop_reason_quality_score: int = 0,
    fake_citation_found: bool = False,
    unsupported_high_confidence_claim_found: bool = False,
    obvious_prior_work_missed: bool = False,
    overclaimed_novelty: bool = False,
    config: GapForgeConfig | None = None,
) -> CampaignReviewResult:
    """Record structured campaign human review."""

    review, summary = CampaignReviewManager(_config(config)).review(
        campaign_id,
        reviewer=reviewer,
        accept=accept,
        reject=reject,
        reason=reason,
        notes=notes,
        source_coverage_score=source_coverage_score,
        full_text_grounding_score=full_text_grounding_score,
        citation_grounding_score=citation_grounding_score,
        retrieval_quality_score=retrieval_quality_score,
        novelty_honesty_score=novelty_honesty_score,
        gap_quality_score=gap_quality_score,
        related_work_quality_score=related_work_quality_score,
        experiment_quality_score=experiment_quality_score,
        reviewer_panel_quality_score=reviewer_panel_quality_score,
        uncertainty_visibility_score=uncertainty_visibility_score,
        stop_reason_quality_score=stop_reason_quality_score,
        fake_citation_found=fake_citation_found,
        unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
        obvious_prior_work_missed=obvious_prior_work_missed,
        overclaimed_novelty=overclaimed_novelty,
    )
    return CampaignReviewResult(review=review, summary=summary)


def campaign_acceptance(
    campaign_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> CampaignAcceptanceSummary:
    """Compute or load campaign acceptance summary."""

    return CampaignReviewManager(_config(config)).summary(campaign_id)


def v4_release_gate(
    project_id: str | None = None,
    *,
    config: GapForgeConfig | None = None,
) -> V04ReleaseGateResult:
    """Evaluate the v0.4 actual-run release gate."""

    return V04ReleaseGateEnforcer(_config(config)).evaluate(project_id=project_id or "")


def run_real_literature_campaign(
    profile_id: str,
    *,
    sources: Iterable[ResearchSource] | None = None,
    run_ids: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> RealLiteratureCampaignRecord:
    """Create a v0.5 real-literature campaign record from live-source diagnostics."""

    return RealLiteratureCampaignManager(_config(config)).run(profile_id, sources=sources, run_ids=run_ids)


def real_literature_status(
    record_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> RealLiteratureCampaignRecord:
    """Load a persisted v0.5 real-literature campaign record."""

    return RealLiteratureCampaignManager(_config(config)).load_record(record_id)


def canonicalize_papers(
    *,
    run_id: str | None = None,
    project_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> tuple[list[CanonicalPaperIdentity], list[PaperMergeDecision]]:
    """Canonicalize duplicate paper records for exactly one run or project."""

    cfg = _config(config)
    _require_one_scope(run_id=run_id, project_id=project_id)
    if run_id:
        return canonicalize_run(cfg, run_id)
    return canonicalize_project(cfg, project_id or "")


def prior_work_recall(
    *,
    campaign_id: str | None = None,
    run_id: str | None = None,
    gap_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> list[PriorWorkRecallAssessment] | PriorWorkRecallAssessment:
    """Run the v0.5 closest-prior-work recall gate for a campaign or run gap."""

    cfg = _config(config)
    if campaign_id:
        return assess_campaign_prior_work_recall(cfg, campaign_id)
    if not gap_id:
        raise ValueError("Provide campaign_id, or provide gap_id with an optional run_id.")
    resolved_run_id = run_id
    if resolved_run_id is None:
        latest = ResearchStateManager(cfg).load_latest()
        if latest is None:
            raise FileNotFoundError("No run state found for prior-work recall.")
        resolved_run_id = latest.run_id
    return assess_run_prior_work_recall(cfg, resolved_run_id, gap_id=gap_id)


def real_literature_review(
    campaign_id: str,
    *,
    reviewer: str = "human",
    accept_workflow: bool = True,
    accept_quality: bool = False,
    reason: str = "",
    source_quality_score: int = 0,
    paper_relevance_score: int = 0,
    prior_work_recall_score: int = 0,
    evidence_grounding_score: int = 0,
    novelty_honesty_score: int = 0,
    gap_importance_score: int = 0,
    experiment_feasibility_score: int = 0,
    reviewer_objection_quality_score: int = 0,
    report_honesty_score: int = 0,
    missed_obvious_prior_work: bool = False,
    fake_citation_found: bool = False,
    unsupported_high_confidence_claim_found: bool = False,
    overclaimed_novelty: bool = False,
    config: GapForgeConfig | None = None,
) -> RealLiteratureReviewResult:
    """Record v0.5 workflow and research-quality human review."""

    review, summary = RealLiteratureReviewManager(_config(config)).review(
        campaign_id,
        reviewer=reviewer,
        accept_workflow=accept_workflow,
        accept_quality=accept_quality,
        reason=reason,
        source_quality_score=source_quality_score,
        paper_relevance_score=paper_relevance_score,
        prior_work_recall_score=prior_work_recall_score,
        evidence_grounding_score=evidence_grounding_score,
        novelty_honesty_score=novelty_honesty_score,
        gap_importance_score=gap_importance_score,
        experiment_feasibility_score=experiment_feasibility_score,
        reviewer_objection_quality_score=reviewer_objection_quality_score,
        report_honesty_score=report_honesty_score,
        missed_obvious_prior_work=missed_obvious_prior_work,
        fake_citation_found=fake_citation_found,
        unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
        overclaimed_novelty=overclaimed_novelty,
    )
    return RealLiteratureReviewResult(review=review, summary=summary)


def v5_release_gate(
    project_id: str | None = None,
    *,
    config: GapForgeConfig | None = None,
) -> V05ReleaseGateResult:
    """Evaluate the v0.5 real-literature quality release gate."""

    return V05ReleaseGateEnforcer(_config(config)).evaluate(project_id=project_id or "")


def generate_code_tasks(
    campaign_id: str,
    direction_id: str,
    *,
    allow_rejected: bool = False,
    config: GapForgeConfig | None = None,
) -> list[ExperimentCodeTask]:
    """Generate Codex handoff tasks for experiment implementation."""

    return ExperimentCodeTaskGenerator(_config(config)).generate_tasks(
        campaign_id=campaign_id,
        direction_id=direction_id,
        allow_rejected=allow_rejected,
    )


def create_experiment_workspace(
    project_id: str,
    direction_id: str,
    *,
    campaign_id: str = "",
    experiment_protocol_id: str = "",
    config: GapForgeConfig | None = None,
) -> ExperimentWorkspace:
    """Create a durable v0.6 experiment workspace for a research direction."""

    return ExperimentWorkspaceManager(_config(config)).create_workspace(
        project_id=project_id,
        direction_id=direction_id,
        campaign_id=campaign_id,
        experiment_protocol_id=experiment_protocol_id,
    )


def register_dataset(
    workspace_id: str,
    name: str,
    path: str | Path,
    *,
    dataset_type: str = "unknown",
    description: str = "",
    source: str = "",
    source_url: str = "",
    version: str = "",
    license: str = "",
    intended_use: str = "",
    limitations: list[str] | None = None,
    safety_notes: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> DatasetRecord:
    """Register a workspace dataset and write its dataset card."""

    return DatasetRegistry(_config(config)).register_dataset(
        workspace_id=workspace_id,
        name=name,
        path=path,
        dataset_type=dataset_type,
        description=description,
        source=source,
        source_url=source_url,
        version=version,
        license=license,
        intended_use=intended_use,
        limitations=limitations,
        safety_notes=safety_notes,
    )


def register_baseline(
    workspace_id: str,
    name: str,
    *,
    description: str = "",
    baseline_type: str = "unknown",
    source_paper_ids: list[str] | None = None,
    related_work_entry_ids: list[str] | None = None,
    code_available: bool = False,
    code_url: str = "",
    implementation_path: str = "",
    required_for_submission: bool = False,
    risk_if_missing: str = "",
    expected_inputs: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> BaselineRecord:
    """Register an explicit experiment baseline."""

    return BaselineRegistry(_config(config)).register_baseline(
        workspace_id=workspace_id,
        name=name,
        description=description,
        baseline_type=baseline_type,
        source_paper_ids=source_paper_ids,
        related_work_entry_ids=related_work_entry_ids,
        code_available=code_available,
        code_url=code_url,
        implementation_path=implementation_path,
        required_for_submission=required_for_submission,
        risk_if_missing=risk_if_missing,
        expected_inputs=expected_inputs,
        expected_outputs=expected_outputs,
    )


def register_metric(
    workspace_id: str,
    name: str,
    *,
    description: str = "",
    metric_type: str = "custom",
    formula: str = "",
    higher_is_better: bool = True,
    required_inputs: list[str] | None = None,
    edge_cases: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> MetricRecord:
    """Register an experiment metric, using built-in templates when available."""

    return MetricRegistry(_config(config)).register_metric(
        workspace_id=workspace_id,
        name=name,
        description=description,
        metric_type=metric_type,
        formula=formula,
        higher_is_better=higher_is_better,
        required_inputs=required_inputs,
        edge_cases=edge_cases,
    )


def scaffold_experiment_code(
    workspace_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> Path:
    """Generate the v0.6 runnable code scaffold for a workspace."""

    return ExperimentCodeScaffolderV2(_config(config)).scaffold(workspace_id)


def create_experiment_manifest(
    workspace_id: str,
    *,
    run_type: str = "smoke",
    run_name: str = "",
    dataset_ids: list[str] | None = None,
    baseline_ids: list[str] | None = None,
    metric_ids: list[str] | None = None,
    command: str = "",
    expected_outputs: list[str] | None = None,
    random_seed: int = 0,
    config: GapForgeConfig | None = None,
) -> ExperimentRunManifest:
    """Create a run manifest. This records intent, not execution."""

    return ExperimentWorkspaceManager(_config(config)).create_manifest(
        workspace_id=workspace_id,
        run_type=run_type,
        run_name=run_name,
        dataset_ids=dataset_ids,
        baseline_ids=baseline_ids,
        metric_ids=metric_ids,
        command=command,
        expected_outputs=expected_outputs,
        random_seed=random_seed,
    )


def run_experiment(
    workspace_id: str,
    *,
    manifest_id: str = "",
    run_type: str = "",
    timeout_seconds: int = 300,
    dry_run: bool = False,
    config: GapForgeConfig | None = None,
) -> ExperimentRunResult:
    """Execute an experiment manifest and persist logs/result-artifact metadata."""

    return ExperimentRunner(_config(config)).run(
        workspace_id=workspace_id,
        manifest_id=manifest_id,
        run_type=run_type,
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
    )


def parse_results(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ResultSummary:
    """Parse artifact-backed metric results for an execution."""

    return ResultParser(_config(config)).parse_execution(execution_id)


def analyze_results(
    *,
    execution_id: str | None = None,
    workspace_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> StatisticalAnalysisReport:
    """Analyze parsed result uncertainty for exactly one execution or workspace."""

    cfg = _config(config)
    _require_one_identifier("execution_id", execution_id, "workspace_id", workspace_id)
    analyzer = ResultStatisticsAnalyzer(cfg)
    if execution_id:
        return analyzer.analyze_execution(execution_id)
    return analyzer.analyze_workspace(workspace_id or "")


def reproducibility_check(
    *,
    workspace_id: str | None = None,
    execution_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> ReproducibilityCheckResult:
    """Run the v0.6 reproducibility audit for exactly one workspace or execution."""

    cfg = _config(config)
    _require_one_identifier("workspace_id", workspace_id, "execution_id", execution_id)
    checker = ReproducibilityChecker(cfg)
    if execution_id:
        return checker.check_execution(execution_id)
    return checker.check_workspace(workspace_id or "")


def empirical_review(
    *,
    workspace_id: str | None = None,
    execution_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> EmpiricalReviewPanel:
    """Build a deterministic empirical reviewer panel for one workspace or execution."""

    cfg = _config(config)
    _require_one_identifier("workspace_id", workspace_id, "execution_id", execution_id)
    builder = EmpiricalReviewBuilder(cfg)
    if execution_id:
        return builder.review_execution(execution_id)
    return builder.review_workspace(workspace_id or "")


def export_paper_package_v2(
    *,
    workspace_id: str | None = None,
    direction_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> PaperPackage:
    """Export the v0.6 empirical paper package for a workspace or direction."""

    cfg = _config(config)
    _require_one_identifier("workspace_id", workspace_id, "direction_id", direction_id)
    exporter = PaperPackageExporter(cfg)
    if workspace_id:
        return exporter.export_workspace_v2(workspace_id)
    return exporter.export_direction_v2(direction_id or "")


def v6_release_gate(
    *,
    config: GapForgeConfig | None = None,
) -> V06ReleaseGateResult:
    """Evaluate the v0.6 empirical validation release gate."""

    return V06ReleaseGateEnforcer(_config(config)).evaluate()


def get_state(run_id: str, *, config: GapForgeConfig | None = None) -> ResearchRunState:
    """Load a persisted run state."""

    return ResearchStateManager(_config(config)).load_run(run_id)


def get_project(project_id: str, *, config: GapForgeConfig | None = None) -> ResearchProgramState:
    """Load a persisted project state."""

    return ProjectMemoryManager(_config(config)).load_project(project_id)


def _config(config: GapForgeConfig | None) -> GapForgeConfig:
    return config or GapForgeConfig.from_cwd()


def _require_one_scope(*, run_id: str | None, project_id: str | None) -> None:
    if bool(run_id) == bool(project_id):
        raise ValueError("Provide exactly one of run_id or project_id.")


def _require_one_identifier(first_name: str, first: str | None, second_name: str, second: str | None) -> None:
    if bool(first) == bool(second):
        raise ValueError(f"Provide exactly one of {first_name} or {second_name}.")


def _paths(paths: list[str | Path] | None) -> list[Path]:
    return [Path(path) for path in paths or []]


def _attest_run_task(
    config: GapForgeConfig,
    task_id: str,
    *,
    agent_name: str,
    model: str,
    execution_method: str,
    attester: str,
    statement: str,
) -> AgentActualRunAttestation:
    manager = ResearchStateManager(config)
    state, task_spec = _find_run_task(manager, task_id)
    attestation = create_run_actual_run_attestation(
        state,
        task_spec,
        agent_name=agent_name,
        model=model,
        execution_method=execution_method,
        attester=attester,
        statement=statement,
    )
    manager.save_run(state)
    return attestation


def _find_run_task(manager: ResearchStateManager, task_id: str) -> tuple[ResearchRunState, AgentTaskSpec]:
    if not manager.config.runs_dir.exists():
        raise FileNotFoundError(f"No run task found for {task_id}")
    for run_dir in sorted(path for path in manager.config.runs_dir.iterdir() if path.is_dir()):
        try:
            state = manager.load_run(run_dir.name)
        except (FileNotFoundError, ValueError):
            continue
        for task_spec in state.agent_task_specs:
            if task_spec.id == task_id:
                return state, task_spec
    raise FileNotFoundError(f"No run task found for {task_id}")


def _attest_campaign_task(
    config: GapForgeConfig,
    state: CampaignState,
    task_id: str,
    *,
    agent_name: str,
    model: str,
    execution_method: str,
    attester: str,
    statement: str,
) -> AgentActualRunAttestation:
    attestation = create_campaign_actual_run_attestation(
        state,
        task_id,
        agent_name=agent_name,
        model=model,
        execution_method=execution_method,
        attester=attester,
        statement=statement,
    )
    CampaignManager(config).save_campaign_state(state)
    return attestation


__all__ = [
    "AddPdfResult",
    "CampaignReviewResult",
    "CampaignTaskResult",
    "ParseFullTextResult",
    "RealLiteratureReviewResult",
    "ReportResult",
    "add_pdf",
    "attest_agent_run",
    "build_index",
    "campaign_acceptance",
    "campaign_next",
    "canonicalize_papers",
    "create_campaign",
    "create_campaign_task",
    "create_direction",
    "create_experiment_manifest",
    "create_experiment_workspace",
    "create_project",
    "create_run",
    "empirical_review",
    "export_paper_package",
    "export_paper_package_v2",
    "export_report",
    "generate_code_tasks",
    "get_project",
    "get_state",
    "import_campaign_output",
    "mature_direction",
    "mine_gaps",
    "novelty_check",
    "parse_results",
    "parse_fulltext",
    "plan_search_strategy",
    "prior_work_recall",
    "real_literature_review",
    "real_literature_status",
    "register_baseline",
    "register_dataset",
    "register_metric",
    "reproducibility_check",
    "review_campaign",
    "run_real_literature_campaign",
    "run_campaign",
    "run_experiment",
    "search_papers",
    "scaffold_experiment_code",
    "source_health",
    "v4_release_gate",
    "v5_release_gate",
    "v6_release_gate",
    "validate_campaign_output",
]
