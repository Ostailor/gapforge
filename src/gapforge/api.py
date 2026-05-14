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
from gapforge.artifact_eval import ArtifactEvaluationPackageExporter
from gapforge.baselines.registry import BaselineRegistry
from gapforge.benchmarks.comparison import BenchmarkComparisonBuilder
from gapforge.benchmarks.registry import BenchmarkRegistry
from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.acceptance import create_campaign_actual_run_attestation
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.decision_policy import CampaignAction
from gapforge.campaigns.import_workflow import find_campaign_task
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.compute import detect_compute_environments
from gapforge.config import GapForgeConfig
from gapforge.datasets.download import DatasetDownloadManager
from gapforge.datasets.registry import DatasetRegistry
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.experiment_code import ExperimentCodeTaskGenerator
from gapforge.experiment_code.scaffold_v2 import ExperimentCodeScaffolderV2
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker
from gapforge.experiments.runner import ExperimentRunner, ExperimentRunResult
from gapforge.experiments.sweeps import ExperimentSweepManager
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.ideas import (
    ConstructiveGapGenerator,
    ConstructiveGapResult,
    CrossDomainIdeaTransferEngine,
    IdeaBank,
    IdeaFeedbackManager,
    IdeaFeedbackRecord,
    IdeaGenerationResult,
    IdeaMutationEngine,
    IdeaMutationResult,
    IdeaNoveltyAssessment,
    IdeaNoveltyLoop,
    IdeaNoveltyRunResult,
    IdeaSeedGenerator,
    IdeaStore,
    IdeaTournament,
    IdeaTournamentRunner,
    IdeaTransferResult,
    IdeaYieldMetricCalculator,
    IdeaYieldMetrics,
    ResearchAgenda,
    ResearchAgendaManager,
    SelectedIdeaLock,
    SelectedIdeaProject,
    SelectedIdeaProjectManager,
    TopicPortfolio,
    TopicPortfolioGenerator,
)
from gapforge.ingest import ManualIngestor
from gapforge.jobs import JobScheduler
from gapforge.manuscript import (
    AnonymizationReport,
    BibliographyRecord,
    ManuscriptFigure,
    ManuscriptManager,
    ManuscriptReviewPanel,
    ManuscriptState,
    ManuscriptTable,
    ManuscriptTraceabilityReport,
    ManuscriptVenueManager,
    RevisionPlan,
    SubmissionChecklist,
    SubmissionChecklistManager,
    SubmissionPackage,
)
from gapforge.manuscript.anonymization import ManuscriptAnonymizer
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.drastic_rebuttal import DrasticRevisionManager, DrasticRevisionPlan
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager
from gapforge.manuscript.reviewer_panel import ManuscriptReviewPanelBuilder
from gapforge.manuscript.submission import SubmissionPackageExporter
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.manuscript.venue_rewriter import VenueManuscriptRewriter, VenueRewriteResult
from gapforge.metrics.registry import MetricRegistry
from gapforge.models import (
    AgentActualRunAttestation,
    AgentTaskSpec,
    AggregateResult,
    ArtifactEvaluationPackage,
    BaselineRecord,
    BenchmarkComparison,
    BenchmarkRecord,
    BenchmarkSuite,
    CampaignAcceptanceSummary,
    CampaignHumanReview,
    CampaignImportRecord,
    CanonicalPaperIdentity,
    ComputeEnvironment,
    DatasetDownloadRecord,
    DatasetRecord,
    EmpiricalReviewPanel,
    ErrorAnalysisReport,
    ExperimentCodeTask,
    ExperimentJob,
    ExperimentRunManifest,
    ExperimentSweep,
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
    ReplicationPackage,
    ReplicationVerificationResult,
    ReproducibilityCheckResult,
    ReproductionRecord,
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
from gapforge.release_gate.v07 import V07ReleaseGateEnforcer, V07ReleaseGateResult
from gapforge.release_gate.v08 import V08ReleaseGateEnforcer, V08ReleaseGateResult
from gapforge.release_gate.v2 import V2ReleaseGateEnforcer, V2ReleaseGateResult
from gapforge.release_gate.v21 import V21ReleaseGateEnforcer, V21ReleaseGateResult
from gapforge.release_gate.v22 import V22ReleaseGateEnforcer, V22ReleaseGateResult
from gapforge.release_gate.v23 import V23ReleaseGateEnforcer, V23ReleaseGateResult
from gapforge.release_gate.v24 import V24ReleaseGateEnforcer, V24ReleaseGateResult
from gapforge.release_gate.v25 import V25ReleaseGateEnforcer, V25ReleaseGateResult
from gapforge.replication import ReplicationPackageExporter, ReplicationPackageVerifier, ReproductionRunner
from gapforge.reporting import write_final_report
from gapforge.results import ErrorAnalysisBuilder, ResultAggregator, ResultParser, ResultStatisticsAnalyzer
from gapforge.results.statistics import StatisticalAnalysisReport
from gapforge.retrieval import build_project_index, build_run_index
from gapforge.review_training import (
    ReviewDataset,
    ReviewDatasetBuilder,
    ReviewerEvaluationManager,
    ReviewerEvaluationResult,
    ReviewerTrainingManager,
    ReviewerTrainingRun,
)
from gapforge.reviewers.drastic_panel import DrasticReviewPanel, DrasticReviewPanelBuilder
from gapforge.reviewers.empirical import EmpiricalReviewBuilder
from gapforge.search_strategy import plan_search_strategy as plan_search_strategy_skill
from gapforge.selected_benchmark import (
    BaselineStrengthAssessment,
    CollusiveAlternativeManager,
    GoNoGoManager,
    HonestNullManager,
    MainAnalysisManager,
    MainAnalysisResult,
    MainDatasetBuilder,
    MainPowerDecision,
    MainPowerManager,
    MainPowerPlan,
    MainRunManager,
    MainTraceDataset,
    MonitorBaseline,
    MonitorBaselineManager,
    MonitorCalibrationRecord,
    PilotAnalysisManager,
    PilotAnalysisResult,
    PilotDatasetBuilder,
    PilotPowerManager,
    PilotPowerPlan,
    PilotRunManager,
    PilotTraceDataset,
    PositioningReport,
    PublicationReadinessReview,
    RelatedWorkCategoryAttachment,
    RelatedWorkCompletionManager,
    RelatedWorkCompletionStatus,
    RelatedWorkCurationManager,
    RelatedWorkReadingManager,
    RelatedWorkReadingStatus,
    RequiredRelatedWorkSearchCampaign,
    RequiredRelatedWorkSearchManager,
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkGoNoGo,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscript,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkPaperPackage,
    SelectedBenchmarkPositioningManager,
    SelectedBenchmarkPriorWorkDossier,
    SelectedBenchmarkPriorWorkRefreshManager,
    SelectedBenchmarkRelatedWorkManager,
    SelectedBenchmarkRelatedWorkManuscriptManager,
    SelectedBenchmarkRelatedWorkMatrixV2,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkReviewPanel,
    SelectedBenchmarkRunResult,
    SelectedBenchmarkVettedMappingManager,
    SelectedBenchmarkWorkspaceManager,
    SelectedMainExecution,
    SelectedMainManuscript,
    SelectedMainManuscriptManager,
    SelectedMainPaperPackage,
    SelectedMainRunManifest,
    SelectedPilotExecution,
    SelectedPilotManuscript,
    SelectedPilotManuscriptManager,
    SelectedPilotPaperPackage,
    SelectedRelatedWorkManuscriptRevision,
    SelectedRelatedWorkMatrix,
    SelectedVettedBenchmarkExperimentManager,
    SequentialMetricManager,
    SequentialMetricResult,
    SequentialSpecificityBenchmarkSpec,
    SyntheticTraceGenerator,
    TraceDataset,
    VettedBenchmarkExperimentPlan,
    VettedBenchmarkExperimentResult,
    VettedBenchmarkMappingReport,
)
from gapforge.sources.base import ResearchSource
from gapforge.sources.canonical import canonicalize_project, canonicalize_run
from gapforge.sources.health import check_sources
from gapforge.sources.live_diagnostics import run_live_source_diagnostic
from gapforge.state import ResearchStateManager
from gapforge.style_corpus import StyleCorpusIngestRecord, StyleCorpusManager, VenueStyleAnalyzer, VenueStyleProfile
from gapforge.venues import VenueProfileManager
from gapforge.vetted_benchmarks import (
    BenchmarkAdapter,
    BenchmarkAdapterRegistry,
    BenchmarkAdapterRun,
    BenchmarkEligibilityAssessment,
    VettedBenchmarkRecord,
    VettedBenchmarkRegistry,
)


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


@dataclass(slots=True)
class ManuscriptAssetsResult:
    figures: list[ManuscriptFigure]
    tables: list[ManuscriptTable]


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


def create_manuscript(
    project_id: str,
    direction_id: str,
    workspace_id: str,
    title: str,
    *,
    campaign_id: str = "",
    short_title: str = "",
    target_venue: str = "",
    config: GapForgeConfig | None = None,
) -> ManuscriptState:
    """Create durable v0.8 manuscript project state."""

    return ManuscriptManager(_config(config)).create_manuscript(
        project_id=project_id,
        direction_id=direction_id,
        workspace_id=workspace_id,
        title=title,
        campaign_id=campaign_id,
        short_title=short_title,
        target_venue=target_venue,
    )


def build_bibliography(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BibliographyRecord:
    """Build a reproducible manuscript bibliography from known paper records."""

    return ManuscriptBibliographyManager(_config(config)).build(manuscript_id)


def draft_manuscript(
    manuscript_id: str,
    *,
    sections: list[str] | None = None,
    section_links: dict[str, dict[str, list[str]]] | None = None,
    claim_uses: list[dict[str, object]] | None = None,
    status: str = "drafted",
    config: GapForgeConfig | None = None,
) -> ManuscriptState:
    """Create or update manuscript section stubs and optional claim-use links.

    ``section_links`` is keyed by section type and may contain
    ``source_claim_ids``, ``source_paper_ids``, ``source_result_ids``,
    ``source_artifact_ids``, and ``warnings``. ``claim_uses`` items should
    include at least ``section_type`` or ``section_id``, ``claim_id``,
    ``claim_text``, ``use_type``, and ``support_status``.
    """

    cfg = _config(config)
    manager = ManuscriptManager(cfg)
    state = manager.load_state(manuscript_id)
    requested_sections = sections or _default_manuscript_sections()
    section_by_type = {section.section_type: section for section in state.sections}
    links = section_links or {}
    for section_type in requested_sections:
        section_link = links.get(section_type, {})
        if section_type in section_by_type:
            manager.update_section_links(
                manuscript_id=manuscript_id,
                section_id=section_by_type[section_type].id,
                source_claim_ids=_string_list(section_link.get("source_claim_ids")),
                source_paper_ids=_string_list(section_link.get("source_paper_ids")),
                source_result_ids=_string_list(section_link.get("source_result_ids")),
                source_artifact_ids=_string_list(section_link.get("source_artifact_ids")),
                status=status,
                warnings=_string_list(section_link.get("warnings")),
            )
        else:
            section = manager.create_section(
                manuscript_id=manuscript_id,
                section_type=section_type,
                title=section_type.replace("_", " ").title(),
                source_claim_ids=_string_list(section_link.get("source_claim_ids")),
                source_paper_ids=_string_list(section_link.get("source_paper_ids")),
                source_result_ids=_string_list(section_link.get("source_result_ids")),
                source_artifact_ids=_string_list(section_link.get("source_artifact_ids")),
                status=status,
                warnings=_string_list(section_link.get("warnings")),
            )
            section_by_type[section_type] = section
    state = manager.load_state(manuscript_id)
    section_by_id = {section.id: section for section in state.sections}
    section_by_type = {section.section_type: section for section in state.sections}
    for claim in claim_uses or []:
        section_id = str(claim.get("section_id") or "")
        if not section_id:
            section_type = str(claim.get("section_type") or "")
            if section_type not in section_by_type:
                raise ValueError(f"Unknown claim section_type `{section_type}` for manuscript `{manuscript_id}`.")
            section_id = section_by_type[section_type].id
        if section_id not in section_by_id:
            raise ValueError(f"Unknown claim section_id `{section_id}` for manuscript `{manuscript_id}`.")
        manager.link_claim_use(
            manuscript_id=manuscript_id,
            section_id=section_id,
            claim_id=str(claim.get("claim_id") or ""),
            claim_text=str(claim.get("claim_text") or ""),
            use_type=str(claim.get("use_type") or "background"),
            support_status=str(claim.get("support_status") or "unsupported"),
            evidence_locators=_string_list(claim.get("evidence_locators")),
            citation_keys=_string_list(claim.get("citation_keys")),
            requires_softening=bool(claim.get("requires_softening", False)),
        )
    return manager.load_state(manuscript_id)


def render_manuscript(
    manuscript_id: str,
    *,
    output_path: str | Path | None = None,
    config: GapForgeConfig | None = None,
) -> str:
    """Render the current manuscript draft by concatenating section files."""

    cfg = _config(config)
    manager = ManuscriptManager(cfg)
    state = manager.load_state(manuscript_id)
    markdown = _render_manuscript_draft(manager.manuscript_root(manuscript_id), state)
    if output_path is not None:
        Path(output_path).write_text(markdown, encoding="utf-8")
    return markdown


def generate_manuscript_assets(
    manuscript_id: str,
    *,
    table_types: list[str] | None = None,
    figure_types: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> ManuscriptAssetsResult:
    """Generate artifact-backed manuscript figures and tables."""

    cfg = _config(config)
    table_generator = ManuscriptTableGenerator(cfg)
    figure_generator = ManuscriptFigureGenerator(cfg)
    tables = [table_generator.generate(manuscript_id, table_type) for table_type in (table_types or ["result_table"])]
    figures = [figure_generator.generate(manuscript_id, figure_type) for figure_type in (figure_types or ["metric_plot"])]
    return ManuscriptAssetsResult(figures=figures, tables=tables)


def run_traceability_check(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ManuscriptTraceabilityReport:
    """Audit manuscript claim uses against evidence, citations, and result artifacts."""

    return ManuscriptTraceabilityAuditor(_config(config)).audit(manuscript_id)


def set_venue(
    manuscript_id: str,
    venue_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ManuscriptState:
    """Assign a built-in venue template to a manuscript."""

    return ManuscriptVenueManager(_config(config)).set_venue(manuscript_id, venue_id)


def submission_checklist(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SubmissionChecklist:
    """Build a venue-aware manuscript submission checklist."""

    return SubmissionChecklistManager(_config(config)).build(manuscript_id)


def anonymize_manuscript(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> AnonymizationReport:
    """Generate an anonymized submission copy and identity-leak report."""

    return ManuscriptAnonymizer(_config(config)).anonymize(manuscript_id)


def create_artifact_eval_package(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ArtifactEvaluationPackage:
    """Export a review-ready artifact evaluation package from manuscript and replication state."""

    return ArtifactEvaluationPackageExporter(_config(config)).export(manuscript_id)


def manuscript_review(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ManuscriptReviewPanel:
    """Run the deterministic full-manuscript reviewer panel."""

    return ManuscriptReviewPanelBuilder(_config(config)).review(manuscript_id)


def rebuttal_plan(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> RevisionPlan:
    """Convert manuscript reviewer objections into actionable rebuttal items."""

    return ManuscriptRebuttalManager(_config(config)).build(manuscript_id)


def submission_package(
    manuscript_id: str,
    package_type: str = "review",
    *,
    config: GapForgeConfig | None = None,
) -> SubmissionPackage:
    """Export a gated manuscript submission package."""

    return SubmissionPackageExporter(_config(config)).export(manuscript_id, package_type)


def v6_release_gate(
    *,
    config: GapForgeConfig | None = None,
) -> V06ReleaseGateResult:
    """Evaluate the v0.6 empirical validation release gate."""

    return V06ReleaseGateEnforcer(_config(config)).evaluate()


def register_benchmark(
    workspace_id: str,
    name: str,
    *,
    description: str = "",
    domain: str = "",
    task_type: str = "custom",
    source_url: str = "",
    dataset_ids: list[str] | None = None,
    baseline_ids: list[str] | None = None,
    metric_ids: list[str] | None = None,
    license: str = "",
    expected_splits: list[str] | None = None,
    evaluation_protocol: str = "",
    leaderboard_url: str = "",
    paper_ids: list[str] | None = None,
    limitations: list[str] | None = None,
    safety_notes: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> BenchmarkRecord:
    """Register a v0.7 benchmark artifact for an experiment workspace."""

    return BenchmarkRegistry(_config(config)).register_benchmark(
        workspace_id=workspace_id,
        name=name,
        description=description,
        domain=domain,
        task_type=task_type,
        source_url=source_url,
        dataset_ids=dataset_ids,
        baseline_ids=baseline_ids,
        metric_ids=metric_ids,
        license=license,
        expected_splits=expected_splits,
        evaluation_protocol=evaluation_protocol,
        leaderboard_url=leaderboard_url,
        paper_ids=paper_ids,
        limitations=limitations,
        safety_notes=safety_notes,
    )


def create_benchmark_suite(
    project_id: str,
    name: str,
    *,
    description: str = "",
    benchmark_ids: list[str] | None = None,
    required_tasks: list[str] | None = None,
    optional_tasks: list[str] | None = None,
    source_profile: str = "generic",
    config: GapForgeConfig | None = None,
) -> BenchmarkSuite:
    """Create a project-level benchmark suite."""

    return BenchmarkRegistry(_config(config)).create_suite(
        project_id=project_id,
        name=name,
        description=description,
        benchmark_ids=benchmark_ids,
        required_tasks=required_tasks,
        optional_tasks=optional_tasks,
        source_profile=source_profile,
    )


def download_dataset(
    dataset_id: str,
    *,
    accept_license: bool = False,
    user: str = "",
    config: GapForgeConfig | None = None,
) -> DatasetDownloadRecord:
    """Download or plan/refuse a registered dataset using the v0.7 consent rules."""

    return DatasetDownloadManager(_config(config)).download(dataset_id, accept_license=accept_license, user=user)


def compute_status(*, config: GapForgeConfig | None = None) -> list[ComputeEnvironment]:
    """Detect local/Docker/GPU/Slurm compute availability.

    The ``config`` parameter is accepted for API consistency; detection is
    environment-local and does not require GapForge state.
    """

    _config(config)
    return detect_compute_environments()


def submit_job(
    workspace_id: str,
    manifest_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ExperimentJob:
    """Queue an experiment manifest through the v0.7 job scheduler."""

    return JobScheduler(_config(config)).submit(workspace_id=workspace_id, manifest_id=manifest_id)


def create_sweep(
    workspace_id: str,
    manifest_id: str,
    parameters: dict[str, list[str]],
    *,
    name: str = "parameter sweep",
    confirm_large: bool = False,
    config: GapForgeConfig | None = None,
) -> ExperimentSweep:
    """Create parameter-sweep manifests from a base experiment manifest."""

    return ExperimentSweepManager(_config(config)).create_parameter_sweep(
        workspace_id=workspace_id,
        base_manifest_id=manifest_id,
        name=name,
        parameters=parameters,
        confirm_large=confirm_large,
    )


def aggregate_results(
    workspace_id: str,
    *,
    include_smoke: bool = False,
    config: GapForgeConfig | None = None,
) -> list[AggregateResult]:
    """Aggregate artifact-backed result rows for a workspace."""

    return ResultAggregator(_config(config)).aggregate(workspace_id, include_smoke=include_smoke)


def run_error_analysis(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ErrorAnalysisReport:
    """Create an artifact-backed error analysis report for an execution."""

    return ErrorAnalysisBuilder(_config(config)).analyze_execution(execution_id)


def benchmark_compare(
    workspace_id: str,
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BenchmarkComparison:
    """Compare internal result rows for one benchmark."""

    return BenchmarkComparisonBuilder(_config(config)).compare(workspace_id=workspace_id, benchmark_id=benchmark_id)


def export_replication_package(
    workspace_id: str,
    *,
    execution_ids: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> ReplicationPackage:
    """Export a safe-by-default replication package."""

    return ReplicationPackageExporter(_config(config)).export_workspace(workspace_id, execution_ids=execution_ids)


def verify_replication_package(
    package_path: str | Path,
    *,
    config: GapForgeConfig | None = None,
) -> ReplicationVerificationResult:
    """Verify a replication package manifest, commands, seeds, and hashes."""

    return ReplicationPackageVerifier(_config(config)).verify(package_path)


def reproduce_package(
    package_path: str | Path,
    *,
    dry_run: bool = False,
    config: GapForgeConfig | None = None,
) -> ReproductionRecord:
    """Attempt or dry-run reproduction from a replication package."""

    return ReproductionRunner(_config(config)).reproduce(package_path, dry_run=dry_run)


def v7_release_gate(
    *,
    claim_real_benchmark_validation: bool = False,
    config: GapForgeConfig | None = None,
) -> V07ReleaseGateResult:
    """Evaluate the v0.7 benchmark execution and replication release gate."""

    return V07ReleaseGateEnforcer(_config(config)).evaluate(claim_real_benchmark_validation=claim_real_benchmark_validation)


def v8_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V08ReleaseGateResult:
    """Evaluate the v0.8 manuscript, artifact-evaluation, and rebuttal release gate."""

    enforcer = V08ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


def generate_topic_portfolio(
    root_topic: str = "",
    *,
    project_id: str = "",
    config: GapForgeConfig | None = None,
) -> TopicPortfolio:
    """Generate and persist a v2 topic portfolio for idea discovery."""

    return TopicPortfolioGenerator(_config(config)).generate(root_topic=root_topic, project_id=project_id)


def create_idea_bank(
    project_id: str,
    root_topic: str,
    *,
    config: GapForgeConfig | None = None,
) -> IdeaBank:
    """Create first-class v2 idea-bank state for a project."""

    return IdeaStore(_config(config)).create_bank(project_id=project_id, root_topic=root_topic)


def generate_ideas(
    *,
    project_id: str = "",
    portfolio_id: str = "",
    max_candidates: int = 50,
    config: GapForgeConfig | None = None,
) -> IdeaGenerationResult:
    """Generate seed idea candidates from a v2 portfolio and project memory."""

    return IdeaSeedGenerator(_config(config)).generate(
        project_id=project_id,
        portfolio_id=portfolio_id,
        max_candidates=max_candidates,
    )


def mutate_idea(
    idea_id: str,
    *,
    strategy: str = "",
    config: GapForgeConfig | None = None,
) -> IdeaMutationResult:
    """Create an auditable mutation of a weak or rejected idea candidate."""

    return IdeaMutationEngine(_config(config)).mutate_idea(idea_id, strategy=strategy)


def generate_constructive_gaps(
    *,
    project_id: str = "",
    campaign_id: str = "",
    config: GapForgeConfig | None = None,
) -> ConstructiveGapResult:
    """Generate constructive benchmark, measurement, protocol, dataset, or negative-result gaps."""

    _require_one_identifier("project_id", project_id, "campaign_id", campaign_id)
    generator = ConstructiveGapGenerator(_config(config))
    if project_id:
        return generator.generate_for_project(project_id)
    return generator.generate_for_campaign(campaign_id)


def transfer_ideas(
    *,
    project_id: str = "",
    topic: str = "",
    config: GapForgeConfig | None = None,
) -> IdeaTransferResult:
    """Run v2 cross-domain idea transfer for a project or standalone topic."""

    _require_one_identifier("project_id", project_id, "topic", topic)
    engine = CrossDomainIdeaTransferEngine(_config(config))
    if project_id:
        return engine.transfer_for_project(project_id)
    return engine.transfer_for_topic(topic)


def run_idea_novelty(
    *,
    idea_id: str = "",
    project_id: str = "",
    top_k: int = 10,
    counterevidence_only: bool = False,
    config: GapForgeConfig | None = None,
) -> IdeaNoveltyAssessment | IdeaNoveltyRunResult:
    """Run idea-specific novelty and counterevidence assessment."""

    _require_one_identifier("idea_id", idea_id, "project_id", project_id)
    loop = IdeaNoveltyLoop(_config(config))
    if idea_id:
        return loop.assess_idea(idea_id, top_k=top_k, counterevidence_only=counterevidence_only)
    return loop.assess_project(project_id, top_k=top_k)


def run_idea_tournament(
    project_id: str,
    *,
    top_k: int = 5,
    config: GapForgeConfig | None = None,
) -> IdeaTournament:
    """Score v2 idea candidates and select one viable candidate or an agenda fallback."""

    return IdeaTournamentRunner(_config(config)).run(project_id, top_k=top_k)


def add_idea_feedback(
    idea_id: str,
    action: str,
    *,
    reviewer: str = "human",
    rationale: str = "",
    preferred_mutations: list[str] | None = None,
    notes: str = "",
    config: GapForgeConfig | None = None,
) -> IdeaFeedbackRecord:
    """Record auditable human feedback for a v2 idea candidate."""

    return IdeaFeedbackManager(_config(config)).add_feedback(
        idea_id=idea_id,
        action=action,
        reviewer=reviewer,
        rationale=rationale,
        preferred_mutations=preferred_mutations,
        notes=notes,
    )


def generate_research_agenda(
    project_id: str,
    *,
    blocker_summary: str = "",
    source_ids: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> ResearchAgenda:
    """Generate an honest staged research agenda when no idea is defensible yet."""

    return ResearchAgendaManager(_config(config)).generate(
        project_id,
        blocker_summary=blocker_summary,
        source_ids=source_ids,
    )


def idea_yield(
    project_id: str,
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> IdeaYieldMetrics:
    """Compute v2 idea-yield metrics for a project."""

    calculator = IdeaYieldMetricCalculator(_config(config))
    if write_report:
        calculator.write_report(project_id)
    return calculator.compute(project_id)


def v2_release_gate(
    *,
    allow_agenda_only: bool = False,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V2ReleaseGateResult:
    """Evaluate the v2 Idea Discovery Engine release gate."""

    enforcer = V2ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate(allow_agenda_only=allow_agenda_only)
    if write_report:
        enforcer.write_outputs(result)
    return result


def lock_selected_idea(
    idea_id: str,
    *,
    locked_by: str = "human",
    lock_reason: str = "Freeze the v2 selected idea as the canonical v2.1 research target.",
    force: bool = False,
    config: GapForgeConfig | None = None,
) -> SelectedIdeaLock:
    """Lock a v2 selected idea so v2.1 execution cannot silently drift."""

    return SelectedIdeaProjectManager(_config(config)).lock_selected_idea(
        idea_id,
        locked_by=locked_by,
        lock_reason=lock_reason,
        force=force,
    )


def create_selected_idea_project(
    idea_id: str,
    *,
    locked_by: str = "human",
    lock_reason: str = "Freeze the v2 selected idea as the canonical v2.1 research target.",
    force: bool = False,
    config: GapForgeConfig | None = None,
) -> SelectedIdeaProject:
    """Convert a locked v2 idea into the durable v2.1 selected-idea project."""

    return SelectedIdeaProjectManager(_config(config)).create_selected_project(
        idea_id,
        locked_by=locked_by,
        lock_reason=lock_reason,
        force=force,
    )


def create_selected_benchmark_spec(
    project_id: str,
    *,
    include_dependencies: bool = True,
    config: GapForgeConfig | None = None,
) -> SequentialSpecificityBenchmarkSpec:
    """Create the selected benchmark spec, optionally with threat model and task families."""

    manager = SelectedBenchmarkManager(_config(config))
    spec = manager.create_spec(project_id)
    if include_dependencies:
        manager.create_threat_model(spec.id)
        manager.create_task_families(spec.id)
        spec = manager.load_spec(spec.id)
    return spec


def generate_traces(
    benchmark_id: str,
    *,
    count: int = 100,
    split: str = "smoke",
    config: GapForgeConfig | None = None,
) -> TraceDataset:
    """Generate synthetic selected-benchmark traces for smoke or pilot execution."""

    return SyntheticTraceGenerator(_config(config)).generate(benchmark_id, count=count, split=split)


def create_monitor_baselines(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> list[MonitorBaseline]:
    """Register the selected benchmark baseline monitor suite."""

    return MonitorBaselineManager(_config(config)).create_baselines(benchmark_id)


def assess_selected_baseline_strength(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BaselineStrengthAssessment:
    """Assess whether selected benchmark baselines support stronger contribution claims."""

    return MonitorBaselineManager(_config(config)).assess_baseline_strength(benchmark_id)


def assess_baseline_strength(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BaselineStrengthAssessment:
    """Alias for the v2.3 selected benchmark baseline-strength assessment."""

    return assess_selected_baseline_strength(benchmark_id, config=config)


def build_main_dataset(
    benchmark_id: str,
    *,
    negative_count: int | None = None,
    positive_count: int | None = None,
    config: GapForgeConfig | None = None,
) -> MainTraceDataset:
    """Build or feasibility-gate the v2.3 selected benchmark main trace dataset."""

    return MainDatasetBuilder(_config(config)).build(
        benchmark_id,
        negative_count=negative_count,
        positive_count=positive_count,
    )


def create_selected_main_manifest(
    benchmark_id: str,
    *,
    dataset_id: str,
    config: GapForgeConfig | None = None,
) -> SelectedMainRunManifest:
    """Create the v2.3 selected benchmark main run manifest."""

    return MainRunManager(_config(config)).create_manifest(benchmark_id, dataset_id)


def run_selected_main_benchmark(
    benchmark_id: str,
    *,
    manifest_id: str,
    config: GapForgeConfig | None = None,
) -> SelectedMainExecution:
    """Run a v2.3 selected benchmark main manifest."""

    return MainRunManager(_config(config)).run(benchmark_id, manifest_id)


def run_selected_main(
    benchmark_id: str,
    *,
    manifest_id: str | None = None,
    dataset_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> SelectedMainExecution:
    """Run the v2.3 selected main benchmark, creating a manifest when given a dataset."""

    cfg = _config(config)
    manager = MainRunManager(cfg)
    resolved_manifest_id = manifest_id
    if not resolved_manifest_id:
        if not dataset_id:
            raise ValueError("run_selected_main requires either manifest_id or dataset_id.")
        resolved_manifest_id = manager.create_manifest(benchmark_id, dataset_id).id
    return manager.run(benchmark_id, resolved_manifest_id)


def analyze_selected_main_benchmark(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> MainAnalysisResult:
    """Analyze saved v2.3 selected benchmark main run artifacts."""

    return MainAnalysisManager(_config(config)).analyze(execution_id)


def analyze_selected_main(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> MainAnalysisResult:
    """Alias for the v2.3 selected main analysis workflow."""

    return analyze_selected_main_benchmark(execution_id, config=config)


def selected_benchmark_go_no_go(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkGoNoGo:
    """Compute the v2.3 selected benchmark go/no-go decision."""

    return GoNoGoManager(_config(config)).decide(benchmark_id)


def selected_go_no_go(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkGoNoGo:
    """Alias for the v2.3 selected benchmark go/no-go decision."""

    return selected_benchmark_go_no_go(benchmark_id, config=config)


def run_selected_benchmark_smoke(
    benchmark_id: str,
    *,
    workspace_id: str = "",
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkRunResult:
    """Create or reuse a selected-benchmark workspace and run the smoke path."""

    cfg = _config(config)
    resolved_workspace_id = workspace_id
    if not resolved_workspace_id:
        workspace = SelectedBenchmarkWorkspaceManager(cfg).create_workspace(benchmark_id)
        resolved_workspace_id = workspace.id
    return SelectedBenchmarkExperimentRunner(cfg).run(resolved_workspace_id, run_type="smoke")


def compute_sequential_metrics(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> list[SequentialMetricResult]:
    """Compute sequential specificity metrics for a selected-benchmark dataset/execution id."""

    return SequentialMetricManager(_config(config)).compute(execution_id)


def selected_benchmark_review(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkReviewPanel:
    """Run the deterministic reviewer panel for selected-benchmark artifacts."""

    return SelectedBenchmarkReviewerPanelBuilder(_config(config)).review(benchmark_id)


def selected_publication_review(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PublicationReadinessReview:
    """Run the v2.3 publication-readiness reviewer panel for the selected benchmark."""

    return SelectedBenchmarkReviewerPanelBuilder(_config(config)).publication_review(benchmark_id)


def selected_publication_readiness_review(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PublicationReadinessReview:
    """Alias for the v2.3 selected benchmark publication-readiness review."""

    return selected_publication_review(benchmark_id, config=config)


def selected_main_manuscript(
    benchmark_id: str,
    *,
    include_paper_package: bool = True,
    config: GapForgeConfig | None = None,
) -> SelectedMainManuscript | SelectedMainPaperPackage:
    """Generate the v2.3 main/pilot-ready selected benchmark manuscript package."""

    manager = SelectedMainManuscriptManager(_config(config))
    if include_paper_package:
        return manager.paper_package(benchmark_id)
    return manager.generate(benchmark_id)


def selected_benchmark_manuscript(
    benchmark_id: str,
    *,
    include_paper_package: bool = True,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkManuscript | SelectedBenchmarkPaperPackage:
    """Generate the selected-benchmark manuscript, optionally exporting its paper package too.

    When ``include_paper_package`` is true, the paper package is persisted for the
    v2.1 release gate and returned. Set it to false to return only the manuscript
    draft.
    """

    manager = SelectedBenchmarkManuscriptManager(_config(config))
    if include_paper_package:
        return manager.paper_package(benchmark_id)
    return manager.generate(benchmark_id)


def v21_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V21ReleaseGateResult:
    """Evaluate the v2.1 selected-idea execution release gate."""

    enforcer = V21ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


def create_pilot_power_plan(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PilotPowerPlan:
    """Create the v2.2 pilot/main low-FPR power plan for the selected benchmark."""

    return PilotPowerManager(_config(config)).create_plan(benchmark_id)


def generate_honest_null(
    benchmark_id: str,
    *,
    count: int = 300,
    config: GapForgeConfig | None = None,
) -> TraceDataset:
    """Generate synthetic pilot honest/null traces and distribution report."""

    return HonestNullManager(_config(config)).generate(benchmark_id, count=count)


def generate_collusive_alternatives(
    benchmark_id: str,
    *,
    count: int = 150,
    config: GapForgeConfig | None = None,
) -> TraceDataset:
    """Generate synthetic pilot collusive alternative traces and distribution report."""

    return CollusiveAlternativeManager(_config(config)).generate(benchmark_id, count=count)


def build_pilot_dataset(
    benchmark_id: str,
    *,
    negative_count: int = 300,
    positive_count: int = 150,
    config: GapForgeConfig | None = None,
) -> PilotTraceDataset:
    """Build the selected-benchmark pilot trace dataset card and alpha support fields."""

    return PilotDatasetBuilder(_config(config)).build(
        benchmark_id,
        negative_count=negative_count,
        positive_count=positive_count,
    )


def calibrate_pilot_baselines(
    benchmark_id: str,
    *,
    target_alpha: float = 0.01,
    config: GapForgeConfig | None = None,
) -> list[MonitorCalibrationRecord]:
    """Calibrate all required pilot baselines that declare calibration requirements."""

    manager = MonitorBaselineManager(_config(config))
    baselines = manager.load_baselines(benchmark_id) or manager.create_baselines(benchmark_id)
    records: list[MonitorCalibrationRecord] = []
    for baseline in baselines:
        required = bool(baseline.parameters.get("required", False))
        calibration_required = bool(baseline.parameters.get("calibration_required", False))
        runnable = baseline.parameters.get("ci_enabled") is not False and baseline.parameters.get("analysis_only") is not True
        if required and calibration_required and runnable:
            records.append(manager.calibrate_monitor(benchmark_id, baseline.id, target_alpha=target_alpha))
    return records


def run_selected_pilot(
    benchmark_id: str,
    *,
    dataset_id: str = "",
    random_seed: int = 20260221,
    config: GapForgeConfig | None = None,
) -> SelectedPilotExecution:
    """Create a pilot manifest and execute required selected-benchmark pilot monitors."""

    cfg = _config(config)
    resolved_dataset_id = dataset_id or PilotDatasetBuilder(cfg).build(benchmark_id).id
    manager = PilotRunManager(cfg)
    manifest = manager.create_manifest(benchmark_id, resolved_dataset_id, random_seed=random_seed)
    return manager.run(benchmark_id, manifest.id)


def analyze_selected_pilot(
    execution_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PilotAnalysisResult:
    """Analyze a saved selected-benchmark pilot execution."""

    return PilotAnalysisManager(_config(config)).analyze(execution_id)


def selected_pilot_review(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkReviewPanel:
    """Run the v2.2 pilot reviewer panel for selected-benchmark evidence."""

    return SelectedBenchmarkReviewerPanelBuilder(_config(config)).pilot_review(benchmark_id)


def selected_pilot_manuscript(
    benchmark_id: str,
    *,
    include_paper_package: bool = True,
    config: GapForgeConfig | None = None,
) -> SelectedPilotManuscript | SelectedPilotPaperPackage:
    """Generate the v2.2 pilot manuscript, optionally exporting the pilot paper package."""

    manager = SelectedPilotManuscriptManager(_config(config))
    if include_paper_package:
        return manager.paper_package(benchmark_id)
    return manager.generate(benchmark_id)


def v22_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V22ReleaseGateResult:
    """Evaluate the v2.2 selected pilot benchmark release gate."""

    enforcer = V22ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


def create_main_sample_size_plan(
    benchmark_id: str,
    *,
    planned_negative_count: int | None = None,
    planned_positive_count: int | None = None,
    config: GapForgeConfig | None = None,
) -> MainPowerPlan:
    """Create the v2.3 main-scale power plan for the selected benchmark."""

    return MainPowerManager(_config(config)).create_plan(
        benchmark_id,
        planned_negative_count=planned_negative_count,
        planned_positive_count=planned_positive_count,
    )


def create_main_power_plan(
    benchmark_id: str,
    *,
    planned_negative_count: int | None = None,
    planned_positive_count: int | None = None,
    config: GapForgeConfig | None = None,
) -> MainPowerPlan:
    """Alias for the v2.3 main-scale power plan workflow."""

    return create_main_sample_size_plan(
        benchmark_id,
        planned_negative_count=planned_negative_count,
        planned_positive_count=planned_positive_count,
        config=config,
    )


def decide_alpha_target(
    benchmark_id: str,
    *,
    alpha: float,
    config: GapForgeConfig | None = None,
) -> MainPowerDecision:
    """Record the v2.3 formal decision for a main-scale alpha target."""

    return MainPowerManager(_config(config)).decide_alpha(benchmark_id, alpha_level=alpha)


def complete_selected_related_work(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> RelatedWorkCompletionStatus:
    """Run the v2.3 selected benchmark related-work completion campaign."""

    return RelatedWorkCompletionManager(_config(config)).complete(benchmark_id)


def complete_related_work(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> RelatedWorkCompletionStatus:
    """Alias for the v2.3 selected benchmark related-work completion campaign."""

    return complete_selected_related_work(benchmark_id, config=config)


def complete_selected_related_work_matrix(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedRelatedWorkMatrix:
    """Build the selected benchmark related-work matrix from attached records."""

    return SelectedBenchmarkRelatedWorkManager(_config(config)).build_related_work_matrix(benchmark_id)


def plan_selected_related_work_search(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> RequiredRelatedWorkSearchCampaign:
    """Create the v2.4 required related-work search campaign plan."""

    return RequiredRelatedWorkSearchManager(_config(config)).plan(benchmark_id)


def run_selected_related_work_search(
    benchmark_id: str,
    *,
    max_results_per_query: int = 5,
    config: GapForgeConfig | None = None,
) -> RequiredRelatedWorkSearchCampaign:
    """Execute the v2.4 required related-work search campaign when sources are available."""

    return RequiredRelatedWorkSearchManager(_config(config)).run(benchmark_id, max_results_per_query=max_results_per_query)


def attach_related_paper(
    benchmark_id: str,
    *,
    category: str,
    paper_id: str,
    relationship: str = "background",
    relevance_score: float = 1.0,
    curator: str = "api",
    evidence_span_ids: list[str] | None = None,
    notes: str = "",
    config: GapForgeConfig | None = None,
) -> RelatedWorkCategoryAttachment:
    """Attach a known real paper record to a v2.4 selected-benchmark related-work category."""

    return RelatedWorkCurationManager(_config(config)).attach_paper(
        benchmark_id,
        category=category,
        paper_id=paper_id,
        relationship=relationship,
        relevance_score=relevance_score,
        curator=curator,
        evidence_span_ids=evidence_span_ids,
        notes=notes,
    )


def read_selected_related_work(
    benchmark_id: str,
    *,
    paper_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> list[RelatedWorkReadingStatus]:
    """Run the v2.4 full-text or abstract reading pass for attached related-work papers."""

    return RelatedWorkReadingManager(_config(config)).read(benchmark_id, paper_id=paper_id)


def refresh_selected_prior_work(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkPriorWorkDossier:
    """Refresh the selected benchmark closest-prior-work dossier from curated v2.4 related work."""

    return SelectedBenchmarkPriorWorkRefreshManager(_config(config)).refresh(benchmark_id)


def position_selected_contribution(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PositioningReport:
    """Build publication-safe contribution positioning from the refreshed v2.4 dossier."""

    return SelectedBenchmarkPositioningManager(_config(config)).build(benchmark_id)


def build_selected_related_work_matrix_v2(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedBenchmarkRelatedWorkMatrixV2:
    """Build the v2.4 manuscript-grade related-work matrix."""

    return SelectedBenchmarkRelatedWorkMatrixV2Manager(_config(config)).build(benchmark_id)


def rerun_selected_publication_review(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> PublicationReadinessReview:
    """Rerun selected-benchmark publication review after v2.4 related-work remediation."""

    return SelectedBenchmarkReviewerPanelBuilder(_config(config)).publication_review(benchmark_id, after_related_work=True)


def revise_selected_manuscript_related_work(
    benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> SelectedRelatedWorkManuscriptRevision:
    """Revise the selected benchmark manuscript related-work and positioning sections for v2.4."""

    return SelectedBenchmarkRelatedWorkManuscriptManager(_config(config)).revise_related_work(benchmark_id)


def v23_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V23ReleaseGateResult:
    """Evaluate the v2.3 selected benchmark mature decision release gate."""

    enforcer = V23ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


def v24_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V24ReleaseGateResult:
    """Evaluate the v2.4 related-work remediation release gate."""

    enforcer = V24ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


def register_vetted_benchmark(
    name: str,
    *,
    domain: str = "",
    source: str = "",
    source_url: str = "",
    benchmark_type: str = "unknown",
    task_types: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    metric_ids: list[str] | None = None,
    baseline_ids: list[str] | None = None,
    paper_ids: list[str] | None = None,
    leaderboard_url: str = "",
    license: str = "",
    terms_of_use: str = "",
    download_required: bool = False,
    authentication_required: bool = False,
    size_estimate: str = "",
    citation: str = "",
    vetted_status: str = "uncertain",
    limitations: list[str] | None = None,
    config: GapForgeConfig | None = None,
) -> VettedBenchmarkRecord:
    """Register an existing benchmark as an auditable v2.5 grounding option."""

    return VettedBenchmarkRegistry(_config(config)).register(
        name=name,
        domain=domain,
        source=source,
        source_url=source_url,
        benchmark_type=benchmark_type,
        task_types=task_types,
        dataset_ids=dataset_ids,
        metric_ids=metric_ids,
        baseline_ids=baseline_ids,
        paper_ids=paper_ids,
        leaderboard_url=leaderboard_url,
        license=license,
        terms_of_use=terms_of_use,
        download_required=download_required,
        authentication_required=authentication_required,
        size_estimate=size_estimate,
        citation=citation,
        vetted_status=vetted_status,
        limitations=limitations,
    )


def assess_benchmark_fit(
    benchmark_id: str,
    selected_idea_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BenchmarkEligibilityAssessment:
    """Assess fit instead of assuming a vetted benchmark validates the selected idea."""

    return VettedBenchmarkRegistry(_config(config)).assess_eligibility(
        benchmark_id=benchmark_id,
        selected_idea_id=selected_idea_id,
    )


def map_selected_benchmark_to_vetted(
    benchmark_id: str,
    *,
    vetted_benchmark_id: str = "",
    config: GapForgeConfig | None = None,
) -> VettedBenchmarkMappingReport:
    """Map the selected benchmark to registered vetted benchmarks with unsupported claims visible."""

    return SelectedBenchmarkVettedMappingManager(_config(config)).map_benchmarks(
        benchmark_id,
        vetted_benchmark_id=vetted_benchmark_id,
    )


def create_benchmark_adapter(
    selected_benchmark_id: str,
    vetted_benchmark_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BenchmarkAdapter:
    """Create a transparent adapter from a vetted benchmark to the selected benchmark protocol."""

    return BenchmarkAdapterRegistry(_config(config)).create_adapter(
        selected_benchmark_id=selected_benchmark_id,
        vetted_benchmark_id=vetted_benchmark_id,
    )


def run_benchmark_adapter(
    adapter_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> BenchmarkAdapterRun:
    """Run a vetted benchmark adapter while preserving source labels, splits, and warnings."""

    return BenchmarkAdapterRegistry(_config(config)).run_adapter(adapter_id)


def run_vetted_experiment(
    benchmark_id: str | None = None,
    *,
    plan_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> VettedBenchmarkExperimentPlan | VettedBenchmarkExperimentResult:
    """Plan or run selected-benchmark experiments on vetted adapters, separate from synthetic results."""

    manager = SelectedVettedBenchmarkExperimentManager(_config(config))
    if plan_id:
        return manager.run_plan(plan_id)
    if benchmark_id:
        return manager.create_plan(benchmark_id)
    raise ValueError("Provide benchmark_id to create a plan or plan_id to run a vetted experiment.")


def select_venue_profile(
    manuscript_id: str,
    venue: str,
    *,
    config: GapForgeConfig | None = None,
) -> ManuscriptState:
    """Assign a venue profile for structure and reviewer expectations, not acceptance claims."""

    return VenueProfileManager(_config(config)).set_profile(manuscript_id, venue)


def ingest_style_corpus(
    source: str | Path,
    venue: str = "generic_ml_conference",
    *,
    source_url: str = "",
    year: int = 0,
    dry_run: bool = False,
    config: GapForgeConfig | None = None,
) -> StyleCorpusIngestRecord:
    """Ingest allowed TeX/source as structural style features only."""

    manager = StyleCorpusManager(_config(config))
    if dry_run:
        return manager.ingest_source(str(source), dry_run=True)
    return manager.add_tex(source, venue, source_url=source_url, year=year)


def analyze_venue_style(
    venue: str,
    *,
    config: GapForgeConfig | None = None,
) -> VenueStyleProfile:
    """Analyze structural/rhetorical venue patterns without copying source-paper prose."""

    return VenueStyleAnalyzer(_config(config)).analyze(venue)


def rewrite_manuscript_for_venue(
    manuscript_id: str,
    venue: str,
    *,
    config: GapForgeConfig | None = None,
) -> VenueRewriteResult:
    """Rewrite manuscript structure for a venue while preserving evidence gates and limitations."""

    return VenueManuscriptRewriter(_config(config)).rewrite(manuscript_id, venue)


def create_review_dataset(
    name: str = "openreview_like",
    *,
    source: str = "manual",
    ingest_fixture: bool = False,
    venue: str = "",
    year: int | None = None,
    config: GapForgeConfig | None = None,
) -> ReviewDataset:
    """Create or ingest an OpenReview-style critique calibration dataset."""

    builder = ReviewDatasetBuilder(_config(config))
    if ingest_fixture:
        return builder.ingest_fixture()
    if source == "openreview" and venue and year is not None:
        return builder.ingest_openreview(venue=venue, year=year)
    return builder.create(name, source=source)


def train_reviewer(
    dataset_id: str,
    *,
    mode: str = "heuristic",
    config: GapForgeConfig | None = None,
) -> ReviewerTrainingRun:
    """Train or calibrate a reviewer rubric/model without claiming human-reviewer equivalence."""

    return ReviewerTrainingManager(_config(config)).train(dataset_id, mode=mode)


def evaluate_reviewer(
    dataset_id: str,
    *,
    model_id: str = "",
    config: GapForgeConfig | None = None,
) -> ReviewerEvaluationResult:
    """Evaluate reviewer calibration with hallucination and evidence-linkage metrics."""

    return ReviewerEvaluationManager(_config(config)).evaluate(dataset_id, model_id=model_id)


def run_drastic_review(
    *,
    manuscript_id: str | None = None,
    benchmark_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> DrasticReviewPanel:
    """Run a harsh evidence-linked reviewer panel without fake citations or invented results."""

    builder = DrasticReviewPanelBuilder(_config(config))
    if manuscript_id:
        return builder.review_manuscript(manuscript_id)
    if benchmark_id:
        return builder.review_benchmark(benchmark_id)
    raise ValueError("Provide manuscript_id or benchmark_id.")


def create_drastic_revision_plan(
    manuscript_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> DrasticRevisionPlan:
    """Convert drastic-review blockers into concrete revision tasks and status downgrades."""

    return DrasticRevisionManager(_config(config)).build(manuscript_id)


def v25_release_gate(
    *,
    write_report: bool = False,
    config: GapForgeConfig | None = None,
) -> V25ReleaseGateResult:
    """Evaluate the v2.5 real benchmark grounding and reviewer calibration release gate."""

    enforcer = V25ReleaseGateEnforcer(_config(config))
    result = enforcer.evaluate()
    if write_report:
        enforcer.write_outputs(result)
    return result


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


def _default_manuscript_sections() -> list[str]:
    return [
        "abstract",
        "introduction",
        "related_work",
        "method",
        "experiments",
        "results",
        "limitations",
        "conclusion",
    ]


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _render_manuscript_draft(root: Path, state: ManuscriptState) -> str:
    lines = [f"# {state.manuscript.title}", ""]
    for section in state.sections:
        section_path = root / section.content_path
        if section_path.exists():
            lines.append(section_path.read_text(encoding="utf-8").rstrip())
        else:
            lines.extend([f"## {section.title}", "", "_Section file missing in manuscript workspace._"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
    "ConstructiveGapResult",
    "IdeaGenerationResult",
    "IdeaMutationResult",
    "IdeaNoveltyRunResult",
    "IdeaTransferResult",
    "IdeaYieldMetrics",
    "ManuscriptAssetsResult",
    "ParseFullTextResult",
    "RealLiteratureReviewResult",
    "ReportResult",
    "add_pdf",
    "add_idea_feedback",
    "analyze_venue_style",
    "aggregate_results",
    "benchmark_compare",
    "attest_agent_run",
    "anonymize_manuscript",
    "build_index",
    "build_bibliography",
    "campaign_acceptance",
    "campaign_next",
    "canonicalize_papers",
    "compute_status",
    "create_campaign",
    "create_campaign_task",
    "create_idea_bank",
    "create_benchmark_suite",
    "create_direction",
    "create_experiment_manifest",
    "create_experiment_workspace",
    "create_artifact_eval_package",
    "create_benchmark_adapter",
    "create_project",
    "create_drastic_revision_plan",
    "create_manuscript",
    "create_review_dataset",
    "create_run",
    "create_sweep",
    "download_dataset",
    "draft_manuscript",
    "empirical_review",
    "export_paper_package",
    "export_paper_package_v2",
    "export_replication_package",
    "export_report",
    "evaluate_reviewer",
    "generate_code_tasks",
    "generate_constructive_gaps",
    "generate_ideas",
    "generate_manuscript_assets",
    "generate_research_agenda",
    "generate_topic_portfolio",
    "get_project",
    "get_state",
    "import_campaign_output",
    "idea_yield",
    "mature_direction",
    "mine_gaps",
    "ingest_style_corpus",
    "assess_benchmark_fit",
    "map_selected_benchmark_to_vetted",
    "mutate_idea",
    "novelty_check",
    "parse_results",
    "parse_fulltext",
    "plan_search_strategy",
    "prior_work_recall",
    "real_literature_review",
    "real_literature_status",
    "register_baseline",
    "register_benchmark",
    "register_dataset",
    "register_metric",
    "register_vetted_benchmark",
    "render_manuscript",
    "reproducibility_check",
    "reproduce_package",
    "review_campaign",
    "rebuttal_plan",
    "run_error_analysis",
    "run_benchmark_adapter",
    "run_drastic_review",
    "run_idea_novelty",
    "run_idea_tournament",
    "run_traceability_check",
    "run_real_literature_campaign",
    "run_campaign",
    "run_experiment",
    "run_vetted_experiment",
    "search_papers",
    "scaffold_experiment_code",
    "set_venue",
    "select_venue_profile",
    "submit_job",
    "submission_checklist",
    "submission_package",
    "source_health",
    "train_reviewer",
    "transfer_ideas",
    "rewrite_manuscript_for_venue",
    "v2_release_gate",
    "v25_release_gate",
    "v4_release_gate",
    "v5_release_gate",
    "v6_release_gate",
    "v7_release_gate",
    "v8_release_gate",
    "validate_campaign_output",
    "verify_replication_package",
]
